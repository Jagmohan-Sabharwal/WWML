"""Provider parsing and public metadata contracts."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.api.drive.errors import DriveErrorCode

DriveId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]+$", max_length=256)]
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class ShortcutDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    target_id: str | None = Field(default=None, validation_alias="targetId")
    target_mime_type: str | None = Field(
        default=None, validation_alias="targetMimeType"
    )


class ProviderFile(BaseModel):
    """Parse optional Google fields without inventing sizes or checksums."""

    model_config = ConfigDict(populate_by_name=True)
    id: DriveId
    name: str
    mime_type: str = Field(validation_alias="mimeType")
    size_bytes: int | None = Field(default=None, ge=0, validation_alias="size")
    created_time: datetime | None = Field(default=None, validation_alias="createdTime")
    modified_time: datetime | None = Field(
        default=None, validation_alias="modifiedTime"
    )
    md5_checksum: str | None = Field(default=None, validation_alias="md5Checksum")
    sha256_checksum: str | None = Field(default=None, validation_alias="sha256Checksum")
    web_view_link: str | None = Field(default=None, validation_alias="webViewLink")
    description: str | None = None
    parents: list[str] = Field(default_factory=list)
    drive_id: DriveId | None = Field(default=None, validation_alias="driveId")
    shortcut_details: ShortcutDetails | None = Field(
        default=None, validation_alias="shortcutDetails"
    )
    trashed: bool = False


class ProviderPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    files: list[ProviderFile] = Field(default_factory=list)
    next_page_token: str | None = Field(default=None, validation_alias="nextPageToken")
    incomplete_search: bool = Field(default=False, validation_alias="incompleteSearch")


class DriveFileMetadata(BaseModel):
    id: str
    name: str
    mime_type: str
    size_bytes: int | None
    created_time: datetime | None
    modified_time: datetime | None
    md5_checksum: str | None
    sha256_checksum: str | None
    web_view_link: str | None
    description: str | None
    parents: list[str]
    drive_id: str | None
    shortcut_details: ShortcutDetails | None
    path_parts: list[str]
    relative_path: str


class FolderReadQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recursive: bool = Field(default=True, description="Include descendant folders.")


class FolderReadResponse(BaseModel):
    folder_id: str
    recursive: bool
    total_files: int
    files: list[DriveFileMetadata]


class DriveErrorDetail(BaseModel):
    code: DriveErrorCode
    message: str


class DriveErrorResponse(BaseModel):
    detail: DriveErrorDetail
