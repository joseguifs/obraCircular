from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_JWT_SECRET = "local-development-only-change-this-jwt-secret-key"


class Settings(BaseSettings):
    app_name: str = "Obra Circular API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: str = "postgresql+asyncpg://postgres@localhost:5432/obra_circular_web"
    jwt_secret_key: SecretStr = SecretStr(_LOCAL_JWT_SECRET)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "obra-circular-api"
    jwt_audience: str = "obra-circular-web"
    jwt_access_token_expire_minutes: int = Field(default=15, ge=1)
    jwt_refresh_token_expire_days: int = Field(default=7, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="OBRA_CIRCULAR_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validar_segredo_jwt(self) -> "Settings":
        segredo = self.jwt_secret_key.get_secret_value()
        if len(segredo) < 32:
            raise ValueError("OBRA_CIRCULAR_JWT_SECRET_KEY deve ter ao menos 32 caracteres.")
        if self.environment == "production" and segredo == _LOCAL_JWT_SECRET:
            raise ValueError("Configure OBRA_CIRCULAR_JWT_SECRET_KEY em produção.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
