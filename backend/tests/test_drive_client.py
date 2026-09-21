"""Verify Drive query construction, credential scope and sanitized failures."""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from requests import Response, Session, Timeout

from app.api.drive.client import DRIVE_SCOPE, GoogleDriveClient, authenticated_client
from app.api.drive.errors import DriveReadError
from app.api.drive.schemas import FOLDER_MIME_TYPE


def response(status: int = 200, body: Any = None) -> Response:
    result = Response()
    result.status_code = status
    result._content = json.dumps(body if body is not None else {}).encode()
    result._content_consumed = True
    return result


def session_with(result: Response) -> MagicMock:
    session = MagicMock(spec=Session)
    session.get.return_value = result
    return session


def test_get_folder_and_shared_drive_query_are_read_only() -> None:
    session = session_with(
        response(
            body={
                "id": "folder",
                "name": "Sources",
                "mimeType": FOLDER_MIME_TYPE,
            }
        )
    )
    client = GoogleDriveClient(session)
    assert client.get_folder("folder", 5).id == "folder"
    assert session.get.call_args.args[0].endswith("/files/folder")
    assert session.get.call_args.kwargs["timeout"] == 5
    assert session.get.call_args.kwargs["allow_redirects"] is False
    session.get.return_value = response(body={"files": [], "nextPageToken": "next"})
    page = client.list_children("folder", "previous", "shared", 7)
    params = session.get.call_args.kwargs["params"]
    assert page.next_page_token == "next"
    assert params["q"] == "'folder' in parents and trashed = false"
    assert params["pageToken"] == "previous"
    assert params["driveId"] == "shared" and params["corpora"] == "drive"
    assert params["supportsAllDrives"] == "true"
    assert params["includeItemsFromAllDrives"] == "true"
    assert "sha256Checksum" in params["fields"]
    assert params["pageSize"] == "1000"
    session.post.assert_not_called()


def test_my_drive_omits_shared_drive_and_initial_page_token() -> None:
    session = session_with(response())
    GoogleDriveClient(session).list_children("folder", None, None, 5)
    params = session.get.call_args.kwargs["params"]
    assert params["corpora"] == "user"
    assert "driveId" not in params and "pageToken" not in params


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "credentials_unavailable"),
        (403, "access_denied"),
        (404, "folder_unavailable"),
        (429, "upstream_unavailable"),
        (500, "upstream_unavailable"),
        (302, "invalid_response"),
    ],
)
def test_http_errors_never_echo_upstream_secrets(status: int, code: str) -> None:
    session = session_with(response(status, {"error": {"message": "private-token"}}))
    with pytest.raises(DriveReadError, match=code) as error:
        GoogleDriveClient(session).list_children("folder", None, None, 5)
    assert "private-token" not in str(error.value)


def test_quota_403_is_retryable() -> None:
    session = session_with(
        response(403, {"error": {"errors": [{"reason": "userRateLimitExceeded"}]}})
    )
    with pytest.raises(DriveReadError, match="upstream_unavailable"):
        GoogleDriveClient(session).get_folder("folder", 5)


@pytest.mark.parametrize(
    ("exception", "code"),
    [
        (Timeout("private-token"), "scan_timeout"),
        (RefreshError("private-token"), "credentials_unavailable"),
    ],
)
def test_transport_and_refresh_errors_are_sanitized(
    exception: Exception, code: str
) -> None:
    session = MagicMock(spec=Session)
    session.get.side_effect = exception
    with pytest.raises(DriveReadError, match=code):
        GoogleDriveClient(session).get_folder("folder", 5)


@pytest.mark.parametrize(
    "body",
    [
        {"files": [{"id": "a", "name": "Missing MIME"}]},
        {"files": [{"id": "../unsafe", "name": "Unsafe", "mimeType": "video/mp4"}]},
        {"files": "malformed"},
    ],
)
def test_malformed_metadata_fails_explicitly(body: Any) -> None:
    with pytest.raises(DriveReadError, match="invalid_response"):
        GoogleDriveClient(session_with(response(body=body))).list_children(
            "folder", None, None, 5
        )


def test_invalid_json_is_sanitized() -> None:
    malformed = response()
    malformed._content = b"not-json-private-token"
    with pytest.raises(DriveReadError, match="invalid_response"):
        GoogleDriveClient(session_with(malformed)).get_folder("folder", 5)


@pytest.mark.parametrize("download", [False, True])
@pytest.mark.parametrize("fail_during_scan", [False, True])
def test_adc_scope_and_session_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    fail_during_scan: bool,
    download: bool,
) -> None:
    default = MagicMock(return_value=(object(), "project"))
    session = MagicMock(spec=Session)
    authorized = MagicMock(return_value=session)
    monkeypatch.setattr("app.api.drive.client.google.auth.default", default)
    monkeypatch.setattr("app.api.drive.client.AuthorizedSession", authorized)
    try:
        with authenticated_client(10, download=download):
            if fail_during_scan:
                raise DriveReadError("scan_timeout")
    except DriveReadError:
        pass
    scope = (
        "https://www.googleapis.com/auth/drive.readonly" if download else DRIVE_SCOPE
    )
    default.assert_called_once_with(scopes=[scope])
    assert authorized.call_args.kwargs["max_refresh_attempts"] == 1
    assert authorized.call_args.kwargs["refresh_timeout"] == 10
    session.close.assert_called_once()


def test_missing_credentials_are_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    default = MagicMock(side_effect=DefaultCredentialsError("secret-file-path"))
    monkeypatch.setattr("app.api.drive.client.google.auth.default", default)
    with pytest.raises(DriveReadError, match="credentials_unavailable") as error:
        with authenticated_client(5):
            pytest.fail("Should not yield a client")
    assert "secret-file-path" not in str(error.value)
