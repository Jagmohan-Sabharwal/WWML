"""Google Drive v3 metadata adapter using Application Default Credentials."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

import google.auth
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from pydantic import ValidationError
from requests import RequestException, Session, Timeout

from app.api.drive.errors import DriveReadError
from app.api.drive.schemas import ProviderFile, ProviderPage

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.metadata.readonly"
BASE_URL = "https://www.googleapis.com/drive/v3/files"
FILE_FIELDS = (
    "id,name,mimeType,size,createdTime,modifiedTime,md5Checksum,sha256Checksum,"
    "webViewLink,description,parents,driveId,trashed,version,capabilities(canDownload),"
    "shortcutDetails(targetId,targetMimeType)"
)


class DriveClient(Protocol):
    """Small adapter boundary for deterministic tests and alternative transports."""

    def get_folder(self, folder_id: str, timeout: float) -> ProviderFile: ...

    def list_children(
        self,
        folder_id: str,
        page_token: str | None,
        drive_id: str | None,
        timeout: float,
    ) -> ProviderPage: ...


class GoogleDriveClient:
    """Only metadata GET requests to a fixed Google endpoint are supported."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _get(self, suffix: str, params: dict[str, str], timeout: float) -> object:
        try:
            with self.session.get(
                BASE_URL + suffix, params=params, timeout=timeout, allow_redirects=False
            ) as response:
                if response.status_code == 401:
                    raise DriveReadError("credentials_unavailable")
                if response.status_code == 403:
                    # Drive can report quota exhaustion as HTTP 403.
                    try:
                        body = response.json()
                        reasons = {
                            item.get("reason")
                            for item in body.get("error", {}).get("errors", [])
                            if isinstance(item, dict)
                        }
                    except (ValueError, AttributeError, TypeError):
                        reasons = set()
                    if reasons & {
                        "rateLimitExceeded",
                        "userRateLimitExceeded",
                        "dailyLimitExceeded",
                    }:
                        raise DriveReadError("upstream_unavailable")
                    raise DriveReadError("access_denied")
                if response.status_code == 404:
                    raise DriveReadError("folder_unavailable")
                if response.status_code == 429 or response.status_code >= 500:
                    raise DriveReadError("upstream_unavailable")
                if response.status_code != 200:
                    raise DriveReadError("invalid_response")
                try:
                    return response.json()
                except ValueError:
                    raise DriveReadError("invalid_response") from None
        except Timeout:
            raise DriveReadError("scan_timeout") from None
        except GoogleAuthError:
            raise DriveReadError("credentials_unavailable") from None
        except RequestException:
            raise DriveReadError("upstream_unavailable") from None
        except ValueError:
            raise DriveReadError("invalid_response") from None

    def get_folder(self, folder_id: str, timeout: float) -> ProviderFile:
        data = self._get(
            "/" + folder_id,
            {"fields": FILE_FIELDS, "supportsAllDrives": "true"},
            timeout,
        )
        try:
            return ProviderFile.model_validate(data)
        except ValidationError:
            raise DriveReadError("invalid_response") from None

    def list_children(
        self,
        folder_id: str,
        page_token: str | None,
        drive_id: str | None,
        timeout: float,
    ) -> ProviderPage:
        # IDs are validated by configuration/provider schemas before interpolation.
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": f"nextPageToken,incompleteSearch,files({FILE_FIELDS})",
            "pageSize": "1000",
            "orderBy": "name_natural",
            "spaces": "drive",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "drive" if drive_id else "user",
        }
        if drive_id:
            params["driveId"] = drive_id
        if page_token:
            params["pageToken"] = page_token
        data = self._get("", params, timeout)
        try:
            return ProviderPage.model_validate(data)
        except ValidationError:
            raise DriveReadError("invalid_response") from None


@contextmanager
def authenticated_client(
    timeout: float, *, download: bool = False
) -> Iterator[GoogleDriveClient]:
    """Load credentials lazily and close the authorized transport after each scan."""
    try:
        scope = (
            "https://www.googleapis.com/auth/drive.readonly"
            if download
            else DRIVE_SCOPE
        )
        credentials, _ = google.auth.default(scopes=[scope])
        # google-auth does not annotate this constructor; isolate the boundary.
        session: Session = AuthorizedSession(  # type: ignore[no-untyped-call]
            credentials, refresh_timeout=timeout, max_refresh_attempts=1
        )
    except (GoogleAuthError, OSError, ValueError):
        raise DriveReadError("credentials_unavailable") from None
    try:
        yield GoogleDriveClient(session)
    finally:
        session.close()
