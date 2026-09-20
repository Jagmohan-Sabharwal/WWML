"""Validated runtime settings; credentials remain server-side."""

from typing import Literal

from fastapi import Request
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load environment variables, then optional .env values, then defaults."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "WWML API"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    postgres_host: str = "postgres"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "wwml"
    postgres_user: str = "wwml"
    postgres_password: SecretStr = SecretStr("")
    redis_url: SecretStr = SecretStr("redis://redis:6379/0")
    google_drive_folder_id: str = Field(
        default="", pattern=r"^[A-Za-z0-9_-]*$", max_length=256
    )
    google_drive_max_files: int = Field(default=10000, ge=1, le=100000)
    google_drive_max_folders: int = Field(default=1000, ge=1, le=10000)
    google_drive_max_requests: int = Field(default=1000, ge=1, le=10000)
    google_drive_request_timeout_seconds: int = Field(default=10, ge=1, le=60)
    google_drive_scan_timeout_seconds: int = Field(default=60, ge=1, le=300)


def get_settings(request: Request) -> Settings:
    """Return this application's settings for FastAPI dependency injection."""
    settings: Settings = request.app.state.settings
    return settings
