from decimal import Decimal
from functools import lru_cache
from pathlib import Path
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
    storage_path: Path = Path("storage")
    max_ad_images: int = Field(default=5, ge=1, le=10)
    max_image_size_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    # Endereço do frontend usado para montar links enviados por e-mail.
    frontend_url: str = "http://localhost:5173"
    password_reset_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    # Sem `smtp_host` os e-mails não são enviados: o conteúdo vai para o log do servidor.
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Obra Circular"
    # STARTTLS na porta 587 (Gmail) ou SSL direto na porta 465.
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_timeout_seconds: int = Field(default=10, ge=1)
    mp_client_id: str | None = None
    mp_client_secret: SecretStr | None = None
    # Fallback para instalações que recebem webhooks de apenas um ambiente.
    mp_webhook_secret: SecretStr | None = None
    mp_webhook_secret_test: SecretStr | None = None
    mp_webhook_secret_production: SecretStr | None = None
    mp_token_encryption_key: SecretStr | None = None
    mp_oauth_redirect_uri: str | None = None
    mp_oauth_test_token: bool = False
    mp_live_mode: bool = False
    mp_webhook_url: str | None = None
    mp_public_base_url: str | None = None
    mp_oauth_success_url: str = "http://localhost:5173/perfil/mercado-pago?mercado_pago=conectado"
    mp_checkout_success_url: str = "http://localhost:5173/pagamento/retorno?status=success"
    mp_checkout_pending_url: str = "http://localhost:5173/pagamento/retorno?status=pending"
    mp_checkout_failure_url: str = "http://localhost:5173/pagamento/retorno?status=failure"
    marketplace_fee_percent: Decimal = Field(default=Decimal("25.00"), ge=0, le=100)
    stock_reservation_minutes: int = Field(default=30, ge=5, le=1440)
    webhook_retry_max_attempts: int = Field(default=8, ge=1, le=50)
    webhook_retry_base_seconds: int = Field(default=30, ge=1, le=3600)
    webhook_retry_max_seconds: int = Field(default=3600, ge=30, le=86400)
    webhook_processing_lease_seconds: int = Field(default=120, ge=30, le=3600)
    webhook_retry_batch_size: int = Field(default=100, ge=1, le=1000)
    webhook_worker_enabled: bool = True
    webhook_worker_interval_seconds: int = Field(default=30, ge=1, le=3600)
    mercado_pago_api_url: str = "https://api.mercadopago.com"
    mercado_pago_auth_url: str = "https://auth.mercadopago.com.br/authorization"

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
