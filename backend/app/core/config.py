from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Obra Circular API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+asyncpg://postgres@localhost:5432/obra_circular_web"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OBRA_CIRCULAR_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
