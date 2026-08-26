from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Clyra API"
    environment: str = "development"
    debug: bool = True
    database_url: str = "postgresql+psycopg://clyra:clyra@localhost:5432/clyra"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
