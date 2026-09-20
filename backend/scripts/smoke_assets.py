"""Verify the deployed Assets API against a running development or production stack."""

import hashlib
import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

BASE_URL = "http://localhost:8000"


def request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any] | None]:
    payload = json.dumps(body).encode() if body is not None else None
    req = Request(
        BASE_URL + path,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=10) as response:
            data = response.read()
            return response.status, json.loads(data) if data else None
    except HTTPError as error:
        return error.code, json.loads(error.read())


def main() -> None:
    checksum = hashlib.sha256(uuid4().bytes).hexdigest()
    status, asset = request(
        "POST",
        "/assets",
        {
            "name": "CI documentary footage",
            "storage_uri": "gs://wwml-ci/footage.mp4",
            "media_type": "video",
            "mime_type": "video/mp4",
            "size_bytes": 0,
            "sha256": checksum,
        },
    )
    assert status == 201 and asset is not None, (status, asset)
    path = f"/assets/{asset['id']}"
    try:
        assert request("GET", path)[0] == 200
        status, page = request(
            "GET",
            "/assets?"
            + urlencode(
                {
                    "q": "documentary",
                    "media_type": "video",
                    "sha256": checksum,
                    "page": 1,
                    "page_size": 1,
                }
            ),
        )
        assert status == 200 and page is not None and page["total"] == 1
        assert page["items"][0]["id"] == asset["id"]
        status, changed = request("PATCH", path, {"name": "Reusable CI footage"})
        assert status == 200 and changed is not None
        assert changed["name"] == "Reusable CI footage"
    finally:
        assert request("DELETE", path)[0] == 204
    assert request("GET", path)[0] == 404
    print("Assets CRUD, search, filters and pagination passed.")


if __name__ == "__main__":
    main()
