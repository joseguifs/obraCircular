from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AnuncioStatus

Preco = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class AnuncioCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(min_length=3, max_length=150)
    descricao: str = Field(min_length=10)
    categoria_id: UUID
    endereco_id: UUID
    preco: Preco
    imagem_url: AnyHttpUrl | None = None
    quantidade: int = Field(ge=0)


class AnuncioUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=150)
    descricao: str | None = Field(default=None, min_length=10)
    categoria_id: UUID | None = None
    endereco_id: UUID | None = None
    preco: Preco | None = None
    imagem_url: AnyHttpUrl | None = None
    quantidade: int | None = Field(default=None, ge=0)
    status: AnuncioStatus | None = None

    @model_validator(mode="after")
    def validar_campos_informados(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")

        campos_nulos_invalidos = self.model_fields_set - {"imagem_url"}
        if any(getattr(self, campo) is None for campo in campos_nulos_invalidos):
            raise ValueError("Campos obrigatórios não podem receber null.")

        return self


class AnuncioFilters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: UUID | None = None
    status: AnuncioStatus | None = None
    search: str | None = Field(default=None, min_length=1, max_length=100)
    min_price: Preco | None = None
    max_price: Preco | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validar_faixa_preco(self) -> Self:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price não pode ser maior que max_price.")
        return self


class AnuncioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    descricao: str
    categoria_id: UUID
    vendedor_id: UUID
    endereco_id: UUID
    preco: Decimal
    imagem_url: str | None
    quantidade: int
    status: AnuncioStatus
    postado_em: datetime
    atualizado_em: datetime
    encerrado_em: datetime | None


class AnuncioListResponse(BaseModel):
    items: list[AnuncioResponse]
    total: int
    offset: int
    limit: int
