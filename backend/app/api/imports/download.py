"""Read-only blob downloads; native Workspace files are explicitly skipped."""

from collections.abc import Iterator
from time import monotonic

from google.auth.exceptions import GoogleAuthError
from requests import RequestException

from app.api.drive.client import BASE_URL, GoogleDriveClient
from app.api.imports.storage import ImportFailure


def download_chunks(
    client: GoogleDriveClient, file_id: str, timeout: float, deadline_seconds: int
) -> Iterator[bytes]:
    deadline = monotonic() + deadline_seconds
    try:
        with client.session.get(
            f"{BASE_URL}/{file_id}",
            params={"alt": "media", "supportsAllDrives": "true"},
            stream=True,
            timeout=timeout,
            allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise ImportFailure(
                    "download_denied"
                    if response.status_code in (401, 403, 404)
                    else "download_unavailable"
                )
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if monotonic() >= deadline:
                    raise ImportFailure("download_timeout")
                if chunk:
                    yield chunk
    except (RequestException, GoogleAuthError):
        raise ImportFailure("download_unavailable") from None
