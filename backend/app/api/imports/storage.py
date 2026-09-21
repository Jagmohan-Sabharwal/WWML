"""Stream to private staging, verify bytes, then publish under a safe name."""

import hashlib
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


class ImportFailure(Exception):
    """Only the stable error code may be persisted or logged."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def safe_name(original: str, checksum: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Invalid SHA-256")
    # Treat both platform separators as untrusted, including on Linux.
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", original).strip("._-") or "asset"
    suffix = Path(name).suffix[:16]
    stem = (name[: -len(suffix)] if suffix else name)[:100].rstrip("._-") or "asset"
    # Prefix also avoids Windows reserved device names.
    return f"asset-{stem}-{checksum[:12]}{suffix}"


@dataclass(frozen=True)
class StagedFile:
    path: Path
    checksum: str
    size: int


class AssetStorage:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes
        self.staging = self.root / ".staging"
        self.staging.mkdir(parents=True, exist_ok=True)

    def stage(self, chunks: Iterable[bytes]) -> StagedFile:
        digest = hashlib.sha256()
        size = 0
        with NamedTemporaryFile(dir=self.staging, delete=False) as stream:
            path = Path(stream.name)
            try:
                for chunk in chunks:
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ImportFailure("file_too_large")
                    stream.write(chunk)
                    digest.update(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                stream.close()
                path.unlink(missing_ok=True)
                raise
        return StagedFile(path, digest.hexdigest(), size)

    def publish(self, staged: StagedFile, original: str) -> Path:
        # Full digest directory prevents truncated suffix collisions.
        directory = self.root / staged.checksum
        directory.mkdir(exist_ok=True)
        destination = directory / safe_name(original, staged.checksum)
        os.replace(staged.path, destination)
        return destination

    def clear_staging(self) -> None:
        """Called only while holding the exclusive importer database lock."""
        for path in self.staging.iterdir():
            if path.is_file() and not path.is_symlink():
                path.unlink()
