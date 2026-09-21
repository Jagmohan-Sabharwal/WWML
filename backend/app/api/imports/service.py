"""Watch → import → rename → register → done, with byte-level asset reuse."""

import logging
from collections.abc import Callable, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.drive.client import GoogleDriveClient
from app.api.drive.errors import DriveReadError
from app.api.drive.schemas import DriveFileMetadata, ProviderFile
from app.api.drive.service import DriveFolderReader
from app.api.imports.download import download_chunks
from app.api.imports.storage import AssetStorage, ImportFailure, StagedFile
from app.core.config import Settings
from app.models.asset import Asset
from app.models.drive_import import DriveImport

logger = logging.getLogger("wwml")


def media_type(mime: str) -> str:
    category = mime.split("/", 1)[0]
    if category in {"video", "audio", "image"}:
        return category
    if category == "text" or mime == "application/pdf":
        return "document"
    return "other"


class ImportService:
    """Caller must hold the worker's PostgreSQL advisory lock for the entire cycle."""

    def __init__(
        self,
        session: Session,
        client: GoogleDriveClient,
        settings: Settings,
        storage: AssetStorage,
        downloader: Callable[
            [GoogleDriveClient, str, float, int], Iterable[bytes]
        ] = download_chunks,
    ) -> None:
        self.session = session
        self.client = client
        self.settings = settings
        self.storage = storage
        self.downloader = downloader

    def transition(
        self, job: DriveImport, status: str, error: str | None = None
    ) -> None:
        job.status = status
        job.error_code = error
        self.session.commit()
        logger.info("Drive import %s: %s", job.id, status)

    def cycle(self) -> int:
        snapshot = DriveFolderReader(self.client, self.settings).read()
        self.storage.clear_staging()
        completed = 0
        for file in snapshot.files:
            # Version is Google's monotonically increasing change identifier.
            if not file.version:
                raise ImportFailure("missing_source_version")
            self.session.execute(
                insert(DriveImport)
                .values(
                    file_id=file.id,
                    source_version=file.version,
                    source_name=file.name[:1024],
                    status="watch",
                    attempts=0,
                )
                .on_conflict_do_nothing(index_elements=["file_id", "source_version"])
            )
            self.session.commit()
            job = self.session.scalars(
                select(DriveImport).where(
                    DriveImport.file_id == file.id,
                    DriveImport.source_version == file.version,
                )
            ).one()
            if job.status in {"done", "skipped"}:
                continue
            if job.attempts >= self.settings.import_max_attempts:
                if job.status != "failed":
                    self.transition(job, "failed", "attempts_exhausted")
                continue
            job.attempts += 1
            self.transition(job, "import")
            try:
                self.process(job, file)
                completed += job.status == "done"
            except ImportFailure as error:
                self.transition(job, "failed", error.code)
            except DriveReadError as error:
                self.transition(job, "failed", error.code)
            except OSError:
                self.transition(job, "failed", "storage_unavailable")
        return completed

    def metadata(self, file: DriveFileMetadata) -> ProviderFile:
        current = self.client.get_folder(
            file.id, self.settings.google_drive_request_timeout_seconds
        )
        if current.trashed or current.version != file.version:
            raise ImportFailure("source_changed")
        return current

    def process(self, job: DriveImport, file: DriveFileMetadata) -> None:
        if file.mime_type.startswith("application/vnd.google-apps."):
            self.transition(job, "skipped", "unsupported_google_native_file")
            return
        current = self.metadata(file)
        if current.capabilities is None or not current.capabilities.can_download:
            raise ImportFailure("download_denied")
        if (
            current.size_bytes is not None
            and current.size_bytes > self.settings.import_max_bytes
        ):
            raise ImportFailure("file_too_large")
        # Reuse registered content without downloading whenever Drive supplies SHA-256.
        if current.sha256_checksum:
            existing = self.session.scalar(
                select(Asset).where(Asset.sha256 == current.sha256_checksum)
            )
            if existing:
                job.asset_id = existing.id
                self.transition(job, "done")
                return
        staged: StagedFile | None = None
        try:
            staged = self.storage.stage(
                self.downloader(
                    self.client,
                    file.id,
                    self.settings.google_drive_request_timeout_seconds,
                    self.settings.import_download_timeout_seconds,
                )
            )
            self.metadata(file)  # Reject a file changed during transfer.
            if current.size_bytes is not None and staged.size != current.size_bytes:
                raise ImportFailure("size_mismatch")
            if current.sha256_checksum and staged.checksum != current.sha256_checksum:
                raise ImportFailure("checksum_mismatch")
            existing = self.session.scalar(
                select(Asset).where(Asset.sha256 == staged.checksum)
            )
            if existing:
                job.asset_id = existing.id
                self.transition(job, "done")
                return
            self.transition(job, "rename")
            destination = self.storage.publish(staged, file.name)
            self.transition(job, "register")
            # Resolve concurrent registration by the Assets API in PostgreSQL.
            self.session.execute(
                insert(Asset)
                .values(
                    name=destination.name,
                    storage_uri=destination.as_uri(),
                    media_type=media_type(file.mime_type),
                    mime_type=file.mime_type,
                    size_bytes=staged.size,
                    sha256=staged.checksum,
                    description=file.description,
                    asset_metadata={
                        "source": "google_drive",
                        "file_id": file.id,
                        "version": file.version,
                        "original_name": file.name,
                        "relative_path": file.relative_path,
                    },
                )
                .on_conflict_do_nothing(index_elements=["sha256"])
            )
            job.asset_id = self.session.scalars(
                select(Asset.id).where(Asset.sha256 == staged.checksum)
            ).one()
            # Registration and completion are committed together.
            self.transition(job, "done")
        finally:
            if staged:
                staged.path.unlink(missing_ok=True)
