from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import CategoriaStatus


def _normalizar_nome(valor: str) -> str:
    """Remove espaços no início/fim e colapsa espaços internos duplicados."""
    nome = " ".join(valor.split())
    if not nome:
        raise ValueError("Nome é obrigatório.")
    return nome


def _normalizar_descricao(valor: str | None) -> str | None:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


class CategoriaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    descricao: str | None = Field(default=None, max_length=255)

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, valor: str) -> str:
        return _normalizar_nome(valor)

    @field_validator("descricao")
    @classmethod
    def _validar_descricao(cls, valor: str | None) -> str | None:
        return _normalizar_descricao(valor)


class CategoriaUpdate(BaseModel):
    """Apenas os campos enviados são alterados (PATCH).

    `status` também pode ser informado aqui: é o mecanismo de reativação
    previsto em `docs/domain/categoria.md` ("A reativação permite
    novamente a criação de anúncios na categoria."). Para inativar, o
    caminho normal é o `DELETE` (exclusão lógica).
    """

    nome: str | None = Field(default=None, min_length=1, max_length=100)
    descricao: str | None = Field(default=None, max_length=255)
    status: CategoriaStatus | None = None

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, valor: str | None) -> str | None:
        return _normalizar_nome(valor) if valor is not None else None

    @field_validator("descricao")
    @classmethod
    def _validar_descricao(cls, valor: str | None) -> str | None:
        return _normalizar_descricao(valor)

    @model_validator(mode="after")
    def _validar_campos_informados(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")

        campos_nulos_invalidos = self.model_fields_set - {"descricao"}
        if any(getattr(self, campo) is None for campo in campos_nulos_invalidos):
            raise ValueError("Campos obrigatórios não podem receber null.")

        return self


class CategoriaFilters(BaseModel):
    status: CategoriaStatus | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class CategoriaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    descricao: str | None
    status: CategoriaStatus
    criado_em: datetime
    atualizado_em: datetime


class CategoriaListResponse(BaseModel):
    items: list[CategoriaResponse]
    total: int
    offset: int
    limit: int
