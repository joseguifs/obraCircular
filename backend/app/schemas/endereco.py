import re
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UFS_VALIDAS = frozenset(
    "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
)

_NAO_DIGITOS = re.compile(r"\D")


def normalizar_cep(valor: str) -> str:
    """Remove a pontuação do CEP e exige exatamente oito dígitos."""
    digitos = _NAO_DIGITOS.sub("", valor)
    if len(digitos) != 8:
        raise ValueError("CEP inválido: informe oito dígitos.")
    return digitos


def normalizar_estado(valor: str) -> str:
    """Converte a sigla do estado para maiúsculas e valida a UF."""
    estado = valor.strip().upper()
    if estado not in UFS_VALIDAS:
        raise ValueError("Estado inválido: informe a sigla de uma UF brasileira.")
    return estado


class EnderecoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cep: str
    logradouro: str = Field(min_length=1, max_length=150)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str = Field(min_length=1, max_length=100)
    cidade: str = Field(min_length=1, max_length=100)
    estado: str

    @field_validator("cep")
    @classmethod
    def _validar_cep(cls, valor: str) -> str:
        return normalizar_cep(valor)

    @field_validator("estado")
    @classmethod
    def _validar_estado(cls, valor: str) -> str:
        return normalizar_estado(valor)


class EnderecoUpdate(BaseModel):
    """Apenas os campos enviados são alterados (PATCH)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    cep: str | None = None
    logradouro: str | None = Field(default=None, min_length=1, max_length=150)
    numero: str | None = Field(default=None, min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, min_length=1, max_length=100)
    cidade: str | None = Field(default=None, min_length=1, max_length=100)
    estado: str | None = None

    @field_validator("cep")
    @classmethod
    def _validar_cep(cls, valor: str | None) -> str | None:
        return normalizar_cep(valor) if valor is not None else None

    @field_validator("estado")
    @classmethod
    def _validar_estado(cls, valor: str | None) -> str | None:
        return normalizar_estado(valor) if valor is not None else None

    @model_validator(mode="after")
    def validar_campos_informados(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")

        campos_nulos_invalidos = self.model_fields_set - {"complemento"}
        if any(getattr(self, campo) is None for campo in campos_nulos_invalidos):
            raise ValueError("Campos obrigatórios não podem receber null.")

        return self


class EnderecoFilters(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class EnderecoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    cep: str
    logradouro: str
    numero: str
    complemento: str | None
    bairro: str
    cidade: str
    estado: str
    criado_em: datetime
    atualizado_em: datetime


class EnderecoListResponse(BaseModel):
    items: list[EnderecoResponse]
    total: int
    offset: int
    limit: int
