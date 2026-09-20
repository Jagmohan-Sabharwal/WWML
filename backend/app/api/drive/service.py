"""Bounded iterative traversal of the configured Google Drive folder."""

from collections import deque
from collections.abc import Callable
from time import monotonic

from app.api.drive.client import DriveClient
from app.api.drive.errors import DriveReadError
from app.api.drive.schemas import (
    FOLDER_MIME_TYPE,
    DriveFileMetadata,
    FolderReadResponse,
)
from app.core.config import Settings


class DriveFolderReader:
    """Read complete metadata or fail explicitly; never return a silent partial scan."""

    def __init__(
        self,
        client: DriveClient,
        settings: Settings,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.client = client
        self.settings = settings
        self.clock = clock

    def read(self, recursive: bool = True) -> FolderReadResponse:
        folder_id = self.settings.google_drive_folder_id
        if not folder_id:
            raise DriveReadError("not_configured")
        deadline = self.clock() + self.settings.google_drive_scan_timeout_seconds
        requests = 0

        def request_timeout() -> float:
            nonlocal requests
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise DriveReadError("scan_timeout")
            if requests >= self.settings.google_drive_max_requests:
                raise DriveReadError("scan_limit_exceeded")
            requests += 1
            return min(
                float(self.settings.google_drive_request_timeout_seconds), remaining
            )

        root = self.client.get_folder(folder_id, request_timeout())
        if root.trashed:
            raise DriveReadError("folder_unavailable")
        if root.mime_type != FOLDER_MIME_TYPE:
            raise DriveReadError("not_a_folder")
        # Resolve special root aliases to the canonical provider ID.
        pending: deque[tuple[str, tuple[str, ...]]] = deque([(root.id, ())])
        seen_folders = {root.id}
        seen_files: set[str] = set()
        files: list[DriveFileMetadata] = []
        while pending:
            parent_id, path = pending.popleft()
            token: str | None = None
            used_tokens: set[str] = set()
            while True:
                page = self.client.list_children(
                    parent_id, token, root.drive_id, request_timeout()
                )
                if page.incomplete_search:
                    raise DriveReadError("invalid_response")
                for item in page.files:
                    if item.trashed:
                        continue
                    if item.mime_type == FOLDER_MIME_TYPE:
                        if recursive and item.id not in seen_folders:
                            if (
                                len(seen_folders)
                                >= self.settings.google_drive_max_folders
                            ):
                                raise DriveReadError("scan_limit_exceeded")
                            seen_folders.add(item.id)
                            pending.append((item.id, (*path, item.name)))
                        continue
                    if item.id in seen_files:
                        continue
                    if len(files) >= self.settings.google_drive_max_files:
                        raise DriveReadError("scan_limit_exceeded")
                    seen_files.add(item.id)
                    parts = [*path, item.name]
                    files.append(
                        DriveFileMetadata(
                            **item.model_dump(exclude={"trashed"}),
                            path_parts=parts,
                            relative_path="/".join(parts),
                        )
                    )
                token = page.next_page_token
                if not token:
                    break
                if token in used_tokens:
                    raise DriveReadError("invalid_response")
                used_tokens.add(token)
        if self.clock() >= deadline:
            raise DriveReadError("scan_timeout")
        files.sort(
            key=lambda file: (tuple(p.casefold() for p in file.path_parts), file.id)
        )
        return FolderReadResponse(
            folder_id=root.id, recursive=recursive, total_files=len(files), files=files
        )
