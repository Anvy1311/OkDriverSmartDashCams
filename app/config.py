from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "okDriver Smart CCTV"
    environment: str = "development"
    database_url: str = "sqlite:///./okdriver.db"
    secret_key: str = "development-only-secret-change-me"
    demo_admin_password: str = "ChangeMe123!"
    demo_operator_password: str = "Operator123!"
    analytics_api_key: str | None = None
    token_ttl_minutes: int = 480
    cookie_secure: bool = False
    simulator_enabled: bool = True
    simulator_interval_seconds: int = 20
    heartbeat_enabled: bool = True
    heartbeat_interval_seconds: int = 30
    seed_demo_data: bool = True
    cors_origins: str = "http://localhost:8000"
    rate_limit_per_minute: int = 120
    map_tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    map_attribution: str = Field(
        default=(
            '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">'
            "OpenStreetMap contributors</a> · "
            '<a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noopener">Report a map issue</a>'
        ),
        min_length=1,
        max_length=500,
    )
    map_max_zoom: int = Field(default=19, ge=1, le=22)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("map_tile_url")
    @classmethod
    def validate_map_tile_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MAP_TILE_URL must be an HTTP(S) tile template")
        if parsed.username or parsed.password:
            raise ValueError("MAP_TILE_URL must not contain URL credentials")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("MAP_TILE_URL must use HTTPS except for localhost development")
        if not all(token in value for token in ("{z}", "{x}", "{y}")):
            raise ValueError("MAP_TILE_URL must contain {z}, {x}, and {y} placeholders")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() not in {"production", "prod"}:
            return self
        secret_key_lower = self.secret_key.lower()
        weak_secret_markers = ("replace-this", "development-only", "change-me", "changeme")
        if len(self.secret_key) < 32 or any(marker in secret_key_lower for marker in weak_secret_markers):
            raise ValueError("SECRET_KEY must be a long random value without placeholder text in production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be enabled in production")
        if self.seed_demo_data:
            raise ValueError("SEED_DEMO_DATA must be disabled in production")
        if self.simulator_enabled:
            raise ValueError("SIMULATOR_ENABLED must be disabled in production")
        if self.heartbeat_enabled:
            raise ValueError("HEARTBEAT_ENABLED must be disabled in production")
        if self.demo_admin_password == "ChangeMe123!" or self.demo_operator_password == "Operator123!":
            raise ValueError("Demo passwords must be replaced or unset in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
