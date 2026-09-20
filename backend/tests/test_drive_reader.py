"""Deterministic folder traversal tests; no Google account or network required."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.drive.errors import DriveReadError
from app.api.drive.router import get_folder_reader
from app.api.drive.schemas import FOLDER_MIME_TYPE, ProviderFile, ProviderPage
from app.api.drive.service import DriveFolderReader
from app.core.config import Settings


def file(
    identifier: str, name: str, mime_type: str = "video/mp4", **extra: Any
) -> dict[str, Any]:
    return {"id": identifier, "name": name, "mimeType": mime_type, **extra}


class FakeDrive:
    def __init__(
        self,
        pages: dict[tuple[str, str | None], dict[str, Any]],
        root: dict[str, Any] | None = None,
    ) -> None:
        self.root = ProviderFile.model_validate(
            root or file("root", "Documentary sources", FOLDER_MIME_TYPE)
        )
        self.pages = pages
        self.calls: list[tuple[str, str | None, str | None]] = []

    def get_folder(self, folder_id: str, timeout: float) -> ProviderFile:
        return self.root

    def list_children(
        self,
        folder_id: str,
        page_token: str | None,
        drive_id: str | None,
        timeout: float,
    ) -> ProviderPage:
        self.calls.append((folder_id, page_token, drive_id))
        return ProviderPage.model_validate(self.pages[(folder_id, page_token)])


def settings(**overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        **({"google_drive_folder_id": "root"} | overrides),
    )


def test_recursive_pages_metadata_deduplication_and_shortcuts() -> None:
    drive = FakeDrive(
        {
            ("root", None): {
                "files": [
                    file("folder", "Interviews", FOLDER_MIME_TYPE),
                    file(
                        "video",
                        "Zebra.mp4",
                        size="2048",
                        md5Checksum="abc",
                        sha256Checksum="a" * 64,
                        modifiedTime="2026-09-20T12:00:00Z",
                        parents=["root"],
                        webViewLink="https://drive.google.com/file/d/video",
                    ),
                ],
                "nextPageToken": "next",
            },
            ("root", "next"): {
                "files": [
                    file("video", "Zebra.mp4"),
                    file("trash", "Removed.mp4", trashed=True),
                    file(
                        "shortcut",
                        "Reference",
                        "application/vnd.google-apps.shortcut",
                        shortcutDetails={
                            "targetId": "outside",
                            "targetMimeType": FOLDER_MIME_TYPE,
                        },
                    ),
                ]
            },
            ("folder", None): {
                "files": [
                    file(
                        "document",
                        "Notes / script",
                        "application/vnd.google-apps.document",
                    ),
                    file("root", "Cycle", FOLDER_MIME_TYPE),
                ]
            },
        },
        root=file("root", "Sources", FOLDER_MIME_TYPE, driveId="shared-drive"),
    )
    result = DriveFolderReader(drive, settings()).read()
    assert result.total_files == 3
    by_id = {item.id: item for item in result.files}
    assert by_id["video"].size_bytes == 2048
    assert by_id["video"].sha256_checksum == "a" * 64
    assert by_id["video"].modified_time is not None
    assert by_id["video"].modified_time.tzinfo is not None
    assert by_id["document"].size_bytes is None
    assert by_id["document"].sha256_checksum is None
    assert by_id["document"].path_parts == ["Interviews", "Notes / script"]
    assert by_id["shortcut"].shortcut_details is not None
    assert by_id["shortcut"].shortcut_details.target_id == "outside"
    assert drive.calls == [
        ("root", None, "shared-drive"),
        ("root", "next", "shared-drive"),
        ("folder", None, "shared-drive"),
    ]


def test_non_recursive_still_reads_all_root_pages() -> None:
    drive = FakeDrive(
        {
            ("root", None): {
                "files": [file("child", "Subfolder", FOLDER_MIME_TYPE)],
                "nextPageToken": "second",
            },
            ("root", "second"): {"files": [file("clip", "Clip")]},
        }
    )
    result = DriveFolderReader(drive, settings()).read(recursive=False)
    assert [item.id for item in result.files] == ["clip"]
    assert not result.recursive
    assert len(drive.calls) == 2


def test_empty_folder() -> None:
    result = DriveFolderReader(FakeDrive({("root", None): {}}), settings()).read()
    assert result.total_files == 0 and result.files == []


@pytest.mark.parametrize(
    ("root", "code"),
    [
        (file("root", "A file"), "not_a_folder"),
        (file("root", "Removed", FOLDER_MIME_TYPE, trashed=True), "folder_unavailable"),
    ],
)
def test_invalid_root(root: dict[str, Any], code: str) -> None:
    with pytest.raises(DriveReadError, match=code):
        DriveFolderReader(FakeDrive({}, root), settings()).read()


@pytest.mark.parametrize(
    ("config", "files"),
    [
        ({"google_drive_max_files": 1}, [file("a", "A"), file("b", "B")]),
        ({"google_drive_max_folders": 1}, [file("child", "Child", FOLDER_MIME_TYPE)]),
        ({"google_drive_max_requests": 1}, []),
    ],
)
def test_limits_fail_instead_of_returning_partial_results(
    config: dict[str, int],
    files: list[dict[str, Any]],
) -> None:
    drive = FakeDrive({("root", None): {"files": files}})
    with pytest.raises(DriveReadError, match="scan_limit_exceeded"):
        DriveFolderReader(drive, settings(**config)).read()


def test_scan_deadline_between_requests() -> None:
    ticks = iter([0.0, 0.0, 61.0])
    with pytest.raises(DriveReadError, match="scan_timeout"):
        DriveFolderReader(FakeDrive({}), settings(), clock=lambda: next(ticks)).read()


def test_deadline_after_last_response() -> None:
    ticks = iter([0.0, 0.0, 0.0, 61.0])
    with pytest.raises(DriveReadError, match="scan_timeout"):
        DriveFolderReader(
            FakeDrive({("root", None): {}}), settings(), clock=lambda: next(ticks)
        ).read()


@pytest.mark.parametrize(
    "page",
    [
        {"incompleteSearch": True},
        {"files": [], "nextPageToken": "loop"},
    ],
)
def test_incomplete_search_or_repeated_page_token(page: dict[str, Any]) -> None:
    drive = FakeDrive({("root", None): page, ("root", "loop"): page})
    with pytest.raises(DriveReadError, match="invalid_response"):
        DriveFolderReader(drive, settings()).read()


def test_missing_configuration_is_explicit() -> None:
    with pytest.raises(DriveReadError, match="not_configured"):
        DriveFolderReader(FakeDrive({}), settings(google_drive_folder_id="")).read()


def test_route_metadata_contract_and_recursion(application: FastAPI) -> None:
    drive = FakeDrive({("root", None): {"files": [file("file", "Résumé.mp4")]}})
    application.dependency_overrides[get_folder_reader] = lambda: DriveFolderReader(
        drive, settings()
    )
    with TestClient(application) as client:
        response = client.get("/integrations/google-drive/files?recursive=false")
        assert response.status_code == 200
        body = response.json()
        assert body["recursive"] is False and body["total_files"] == 1
        assert body["files"][0]["mime_type"] == "video/mp4"
        assert body["files"][0]["relative_path"] == "Résumé.mp4"
        assert (
            client.get("/integrations/google-drive/files?folder_id=outside").status_code
            == 422
        )


def test_disabled_route_leaves_health_available(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    response = client.get("/integrations/google-drive/files")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "not_configured"


@pytest.mark.parametrize(
    "value",
    ["folder' or trashed = true", "../escape", "https://drive.google.com/folders/id"],
)
def test_folder_id_cannot_inject_query_or_url(value: str) -> None:
    with pytest.raises(ValidationError):
        settings(google_drive_folder_id=value)


def test_swagger_documents_reader(application: FastAPI) -> None:
    operation = application.openapi()["paths"]["/integrations/google-drive/files"][
        "get"
    ]
    assert operation["tags"] == ["google-drive"]
    assert operation["parameters"][0]["name"] == "recursive"
    assert {"200", "403", "404", "413", "422", "502", "503", "504"} <= set(
        operation["responses"]
    )


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("access_denied", 403),
        ("folder_unavailable", 404),
        ("not_a_folder", 503),
        ("invalid_response", 502),
        ("upstream_unavailable", 503),
        ("scan_timeout", 504),
        ("scan_limit_exceeded", 413),
        ("credentials_unavailable", 503),
    ],
)
def test_route_maps_reader_errors(
    application: FastAPI,
    code: str,
    status: int,
) -> None:
    from unittest.mock import MagicMock

    reader = MagicMock(spec=DriveFolderReader)
    reader.read.side_effect = DriveReadError(code)
    application.dependency_overrides[get_folder_reader] = lambda: reader
    with TestClient(application) as client:
        response = client.get("/integrations/google-drive/files")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    if code == "upstream_unavailable":
        assert response.headers["retry-after"] == "30"
