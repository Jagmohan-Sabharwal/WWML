"""Validated contracts for the Assets API."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
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


class AssetQuery(BaseModel):
    """Combine filters with AND; q matches either name or description."""

    model_config = ConfigDict(extra="forbid")
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


class AssetPage(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AssetErrorDetail(BaseModel):
    code: Literal["asset_not_found", "duplicate_asset"]
    message: str
    existing_asset_id: UUID | None = None


class AssetErrorResponse(BaseModel):
    detail: AssetErrorDetail
