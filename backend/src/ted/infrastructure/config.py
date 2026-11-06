"""Validated operator configuration; development trust is always explicit."""

from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


def validate_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("Origin must have a valid port") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or "*" in value
    ):
        raise ValueError("Use an exact http(s) origin without a path, credentials or wildcard")
    host = parsed.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    suffix = f":{port}" if port and port != (443 if parsed.scheme == "https" else 80) else ""
    return f"{parsed.scheme}://{host}{suffix}"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ROOT / "backend/.env"), extra="ignore", hide_input_in_errors=True
    )
    database_url: str = Field(repr=False)

    @field_validator("database_url")
    @classmethod
    def postgres_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://") or not urlsplit(value).path.strip("/"):
            raise ValueError(
                "DATABASE_URL must name a PostgreSQL database using postgresql+asyncpg://"
            )
        return value


class Settings(DatabaseSettings):
    app_env: Literal["production", "development"] = "production"
    app_origin: str = "http://localhost:8000"
    dev_origins: Annotated[tuple[str, ...], NoDecode] = ()
    secure_cookies: bool = True
    session_hours: int = Field(default=12, ge=1, le=168)
    webhook_hosts: str = ""

    @field_validator("app_origin")
    @classmethod
    def origin(cls, value: str) -> str:
        return validate_origin(value)

    @field_validator("dev_origins", mode="before")
    @classmethod
    def origins(cls, value: object) -> tuple[str, ...]:
        values = value.split(",") if isinstance(value, str) else value
        if not isinstance(values, (list, tuple)):
            raise ValueError("DEV_ORIGINS must be comma-separated exact origins")
        return tuple(
            dict.fromkeys(validate_origin(str(v).strip()) for v in values if str(v).strip())
        )

    @model_validator(mode="after")
    def production_security(self) -> "Settings":
        if self.app_env == "production":
            if self.dev_origins:
                raise ValueError("DEV_ORIGINS requires APP_ENV=development")
            if not self.secure_cookies:
                raise ValueError("Disabling Secure cookies requires APP_ENV=development")
            if urlsplit(self.app_origin).hostname not in {
                "localhost",
                "127.0.0.1",
                "::1",
            } and not self.app_origin.startswith("https://"):
                raise ValueError("Production APP_ORIGIN must use HTTPS")
        return self

    @property
    def allowed_origins(self) -> frozenset[str]:
        return frozenset((self.app_origin, *self.dev_origins))

    def accepts_origin(self, value: str) -> bool:
        try:
            return value == validate_origin(value) and value in self.allowed_origins
        except ValueError:
            return False
