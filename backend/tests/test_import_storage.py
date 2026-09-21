"""Storage boundaries and downloads do not need live Drive credentials."""

import hashlib
from unittest.mock import MagicMock

import pytest

from app.api.drive.client import GoogleDriveClient
from app.api.imports.download import download_chunks
from app.api.imports.storage import AssetStorage, ImportFailure, safe_name
from app.main import create_app


@pytest.fixture
def tmp_path(tmp_path_factory):
    # Keep Windows paths below MAX_PATH even with full checksum directories.
    return tmp_path_factory.mktemp("s")


@pytest.mark.parametrize(
    "name", ["../../x.mp4", r"..\..\CON.mp4", "", "你好.mp4", "a" * 400]
)
def test_safe_names_stay_inside_checksum_directory(tmp_path, name):
    storage = AssetStorage(tmp_path, 100)
    staged = storage.stage([b"abc"])
    destination = storage.publish(staged, name)
    assert destination.parent == tmp_path / hashlib.sha256(b"abc").hexdigest()
    assert destination.read_bytes() == b"abc"
    assert len(destination.name) <= 135
    assert destination.name.startswith("asset-")
    assert not list(storage.staging.iterdir())


def test_size_limit_cleans_partial_file(tmp_path):
    storage = AssetStorage(tmp_path, 2)
    with pytest.raises(ImportFailure, match="file_too_large"):
        storage.stage([b"a", b"bc"])
    assert not list(storage.staging.iterdir())


def test_failed_stream_cleans_partial_file(tmp_path):
    def chunks():
        yield b"a"
        raise ImportFailure("download_unavailable")

    storage = AssetStorage(tmp_path, 100)
    with pytest.raises(ImportFailure):
        storage.stage(chunks())
    assert not list(storage.staging.iterdir())


def test_retry_publish_same_content_is_idempotent(tmp_path):
    storage = AssetStorage(tmp_path, 100)
    first = storage.publish(storage.stage([b"abc"]), "file.mp4")
    second = storage.publish(storage.stage([b"abc"]), "file.mp4")
    assert first == second
    assert len(list(tmp_path.glob("*/*.mp4"))) == 1


def test_safe_name_rejects_untrusted_checksum():
    with pytest.raises(ValueError):
        safe_name("file", "../escape")


def test_download_is_streamed_read_only_and_closes_response():
    session = MagicMock()
    response = session.get.return_value.__enter__.return_value
    response.status_code = 200
    response.iter_content.return_value = [b"abc", b"", b"def"]
    assert list(download_chunks(GoogleDriveClient(session), "file-id", 10, 30)) == [
        b"abc",
        b"def",
    ]
    _, kwargs = session.get.call_args
    assert kwargs["stream"] is True
    assert kwargs["allow_redirects"] is False
    assert kwargs["params"]["alt"] == "media"
    session.get.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 302])
def test_download_errors_are_redacted(status):
    session = MagicMock()
    response = session.get.return_value.__enter__.return_value
    response.status_code = status
    response.text = "SECRET"
    with pytest.raises(ImportFailure) as error:
        list(download_chunks(GoogleDriveClient(session), "file-id", 10, 30))
    assert "SECRET" not in str(error.value)


def test_import_progress_documented_in_swagger():
    paths = create_app().openapi()["paths"]
    assert "/integrations/google-drive/imports" in paths
    assert "/integrations/google-drive/imports/{import_id}" in paths
