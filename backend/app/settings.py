from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore")
    app_env: Literal["local", "test", "public"] = "local"
    release_id: str = Field(default="development", min_length=1, max_length=64)
    allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080"
    channel_name: str = Field(default="global_chat_channel", pattern=r"^[a-z0-9_-]{3,64}$")
    redis_url: SecretStr | None = None
    redis_url_file: Path | None = None
    max_connections_per_replica: int = Field(default=64, ge=10, le=256)
    rate_messages_per_second: float = Field(default=2, ge=0.5, le=10)
    rate_burst: int = Field(default=5, ge=1, le=20)
    publish_rate_per_second: float = Field(default=20, ge=5, le=100)
    publish_burst: int = Field(default=40, ge=10, le=200)
    outbound_queue_events: int = Field(default=32, ge=8, le=128)
    outbound_queue_bytes: int = Field(default=262144, ge=65536, le=1048576)
    send_timeout_seconds: float = Field(default=2, ge=0.5, le=10)
    redis_command_timeout_seconds: float = Field(default=1, ge=0.2, le=5)
    subscriber_heartbeat_seconds: float = Field(default=5, ge=1, le=15)
    subscriber_stale_seconds: float = Field(default=10, ge=3, le=30)
    shutdown_drain_seconds: float = Field(default=10, ge=2, le=15)

    @property
    def origins(self) -> set[str]:
        return {item.strip() for item in self.allowed_origins.split(",") if item.strip()}

    def resolve_redis_url(self) -> str:
        if self.redis_url_file:
            try:
                return self.redis_url_file.read_text(encoding="utf-8").strip()
            except OSError:
                raise ValueError("Redis secret file cannot be read") from None
        return self.redis_url.get_secret_value() if self.redis_url else ""

    @model_validator(mode="after")
    def validate_contract(self):
        if bool(self.redis_url) == bool(self.redis_url_file):
            raise ValueError("Set exactly one Redis credential source")
        if self.subscriber_heartbeat_seconds >= self.subscriber_stale_seconds:
            raise ValueError("Subscriber heartbeat must be shorter than stale threshold")
        if not self.origins:
            raise ValueError("At least one explicit origin is required")
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                    or parsed.path or parsed.query or parsed.fragment
                    or parsed.username or "*" in origin or origin == "null"):
                raise ValueError("Origins must be exact HTTP(S) origins without paths")
            if self.app_env == "public" and parsed.scheme != "https":
                raise ValueError("Public origins require HTTPS")
        try:
            uri = urlsplit(self.resolve_redis_url())
            valid = (uri.scheme in {"redis", "rediss"} and uri.hostname
                     and not uri.query and not uri.fragment and uri.path in {"", "/", "/0"})
            _ = uri.port
        except (ValueError, OSError):
            raise ValueError("Invalid Redis credential source") from None
        if not valid:
            raise ValueError("Invalid Redis URI")
        if self.app_env == "public":
            if not self.redis_url_file or not uri.username or not uri.password:
                raise ValueError("Public mode requires an authenticated Redis secret file")
            if self.release_id == "development":
                raise ValueError("Public mode requires a release ID")
        return self
