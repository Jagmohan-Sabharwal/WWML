"""Stable errors that never expose tokens or upstream response bodies."""

from typing import Literal

DriveErrorCode = Literal[
    "not_configured",
    "credentials_unavailable",
    "access_denied",
    "folder_unavailable",
    "not_a_folder",
    "upstream_unavailable",
    "invalid_response",
    "scan_limit_exceeded",
    "scan_timeout",
]


class DriveReadError(Exception):
    """A safe, classified error for the folder reader."""

    def __init__(self, code: DriveErrorCode) -> None:
        self.code = code
        super().__init__(code)
