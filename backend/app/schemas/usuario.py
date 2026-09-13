from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.validators import normalizar_telefone
from app.models.enums import UsuarioStatus


class UsuarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str = Field(min_length=1, max_length=150)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)
    telefone: str | None = Field(default=None, max_length=20)

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, valor: str) -> str:
        return _nome_obrigatorio(valor)

    @field_validator("email")
    @classmethod
    def _validar_email(cls, valor: EmailStr) -> str:
        return str(valor).lower()

    @field_validator("telefone")
    @classmethod
    def _validar_telefone(cls, valor: str | None) -> str | None:
        return normalizar_telefone(valor) if valor is not None else None


class UsuarioUpdate(BaseModel):
    """Todos os campos são opcionais: apenas os enviados são alterados (PATCH)."""

    model_config = ConfigDict(extra="forbid")

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=8, max_length=72)
    telefone: str | None = Field(default=None, max_length=20)

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, valor: str | None) -> str | None:
        return _nome_obrigatorio(valor) if valor is not None else None

    @field_validator("email")
    @classmethod
    def _validar_email(cls, valor: EmailStr | None) -> str | None:
        return str(valor).lower() if valor is not None else None

    @field_validator("telefone")
    @classmethod
    def _validar_telefone(cls, valor: str | None) -> str | None:
        return normalizar_telefone(valor) if valor is not None else None


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    telefone: str | None
    status: UsuarioStatus
    criado_em: datetime
    atualizado_em: datetime


class UsuarioListResponse(BaseModel):
    items: list[UsuarioRead]
    total: int
    limit: int
    offset: int


def _nome_obrigatorio(valor: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError("Nome é obrigatório.")
    return valor
