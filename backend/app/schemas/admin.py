from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnuncioStatus, UsuarioStatus


class ContagemPorStatus(BaseModel):
    total: int
    por_status: dict[str, int]


class AdminResumoResponse(BaseModel):
    usuarios: ContagemPorStatus
    anuncios: ContagemPorStatus
    categorias: ContagemPorStatus
    administradores: int


class AdminUsuarioFilters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: UsuarioStatus | None = None
    search: str | None = Field(default=None, min_length=1, max_length=100)
    incluir_excluidos: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class AdminUsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: str
    telefone: str | None
    status: UsuarioStatus
    administrador: bool = False
    criado_em: datetime
    atualizado_em: datetime
    deletado_em: datetime | None


class AdminUsuarioListResponse(BaseModel):
    items: list[AdminUsuarioResponse]
    total: int
    offset: int
    limit: int


class AdminUsuarioStatusUpdate(BaseModel):
    status: UsuarioStatus


class AdminAnuncioFilters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: AnuncioStatus | None = None
    search: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: UUID | None = None
    vendedor_id: UUID | None = None
    incluir_excluidos: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class AdminAnuncioResponse(BaseModel):
    id: UUID
    titulo: str
    preco: Decimal
    quantidade: int
    status: AnuncioStatus
    categoria_id: UUID
    categoria_nome: str
    vendedor_id: UUID
    vendedor_nome: str
    vendedor_email: str
    imagem_capa_url: str | None
    postado_em: datetime
    atualizado_em: datetime
    encerrado_em: datetime | None
    deletado_em: datetime | None


class AdminAnuncioListResponse(BaseModel):
    items: list[AdminAnuncioResponse]
    total: int
    offset: int
    limit: int
