from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clyra API"
    environment: str = "development"
    debug: bool = True
    database_url: str = "postgresql+psycopg://clyra:clyra@localhost:5432/clyra"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    anthropic_api_key: str = ""
    # Swaps 02-reasoning-agent/03-recommendation-agent's Claude client for a
    # deterministic fake (app.testing.fake_anthropic) — for E2E tests that
    # need the real HTTP app/DB/Commander pipeline without real API calls or
    # nondeterministic output. Never set true outside a test run.
    mock_anthropic: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Render (and most managed Postgres hosts) hand out a DATABASE_URL with a
        # bare `postgres://` or `postgresql://` scheme. SQLAlchemy + psycopg 3
        # needs the `postgresql+psycopg://` driver scheme, so rewrite it here
        # rather than requiring the dashboard value to be hand-edited.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
