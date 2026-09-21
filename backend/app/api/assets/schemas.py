"""Validated contracts for the Assets API."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

MediaType = Literal["video", "audio", "image", "document", "other"]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
StorageURI = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)
]
Checksum = Annotated[
    str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
]
MimeType = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=127,
        pattern=r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$",
    ),
]
ByteSize = Annotated[int, Field(ge=0, le=9223372036854775807, strict=True)]
Description = Annotated[str, StringConstraints(max_length=10000)]


class AssetCreate(BaseModel):
    """Register an existing file; this endpoint does not generate or upload media."""

    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Description | None = None
    storage_uri: StorageURI = Field(
        description="Durable URI; do not include credentials."
    )
    media_type: MediaType
    mime_type: MimeType
    size_bytes: ByteSize
    sha256: Checksum = Field(description="Lowercase SHA-256 of the actual file bytes.")
    asset_metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    """Partial update; only description can explicitly be set to null."""

    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    description: Description | None = None
    storage_uri: StorageURI | None = None
    media_type: MediaType | None = None
    mime_type: MimeType | None = None
    size_bytes: ByteSize | None = None
    sha256: Checksum | None = None
    asset_metadata: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        changes = self.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("At least one field must be provided")
        for name, value in changes.items():
            if value is None and name != "description":
                raise ValueError(f"{name} cannot be null")
        return self


class AssetResponse(BaseModel):
    """Persisted asset, including its server-managed identity and timestamps."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    storage_uri: str
    media_type: MediaType
    mime_type: str
    size_bytes: int
    sha256: str
    asset_metadata: dict[str, JsonValue]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class AssetQuery(BaseModel):
    """Combine filters with AND; q matches either name or description."""

    model_config = ConfigDict(extra="forbid")
    sort_by: Literal["created_at", "updated_at", "name", "size_bytes"] = Field(
        default="created_at", description="Allowlisted sort column; UUID breaks ties."
    )
    sort_order: Literal["asc", "desc"] = "desc"
    min_size_bytes: int | None = Field(default=None, ge=0, le=9223372036854775807)
    max_size_bytes: int | None = Field(default=None, ge=0, le=9223372036854775807)
    created_after: AwareDatetime | None = Field(
        default=None, description="Inclusive creation lower bound, with timezone."
    )
    created_before: AwareDatetime | None = Field(
        default=None, description="Inclusive creation upper bound, with timezone."
    )
    page: int = Field(default=1, ge=1, le=1000000)
    page_size: int = Field(default=20, ge=1, le=100)
    q: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
        ]
        | None
    ) = Field(default=None, description="Case-insensitive literal substring.")
    media_type: MediaType | None = None
    mime_type: MimeType | None = None
    sha256: Checksum | None = Field(
        default=None, description="Exact file lookup for reuse."
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if (
            self.min_size_bytes is not None
            and self.max_size_bytes is not None
            and self.min_size_bytes > self.max_size_bytes
        ):
            raise ValueError("min_size_bytes must not exceed max_size_bytes")
        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise ValueError("created_after must not exceed created_before")
        return self


class AssetPage(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AssetErrorDetail(BaseModel):
    code: Literal["asset_not_found", "duplicate_asset", "asset_deleted"]
    message: str
    existing_asset_id: UUID | None = None


class AssetErrorResponse(BaseModel):
    detail: AssetErrorDetail
