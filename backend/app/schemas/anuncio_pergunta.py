from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnuncioStatus

PERGUNTA_MAX = 500
RESPOSTA_MAX = 1000


class AnuncioPerguntaCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    pergunta: str = Field(min_length=3, max_length=PERGUNTA_MAX)


class AnuncioRespostaCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    resposta: str = Field(min_length=1, max_length=RESPOSTA_MAX)


class AnuncioPerguntaFilters(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=50)


class AnuncioPerguntaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    anuncio_id: UUID
    autor_id: UUID
    pergunta: str
    resposta: str | None
    criado_em: datetime
    respondido_em: datetime | None


class AnuncioPerguntaListResponse(BaseModel):
    items: list[AnuncioPerguntaResponse]
    total: int
    offset: int
    limit: int


class TipoPerguntaUsuario(StrEnum):
    """Recorte da listagem de perguntas do usuário autenticado."""

    FEITAS = "FEITAS"
    RECEBIDAS = "RECEBIDAS"


class PerguntaUsuarioFilters(BaseModel):
    # Obrigatório: cada recorte é carregado separadamente, sob demanda.
    tipo: TipoPerguntaUsuario
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=50)


class AnuncioResumoPergunta(BaseModel):
    id: UUID
    titulo: str
    status: AnuncioStatus
    imagem_capa_url: str | None


class PerguntaUsuarioResponse(AnuncioPerguntaResponse):
    anuncio: AnuncioResumoPergunta


class PerguntaUsuarioListResponse(BaseModel):
    items: list[PerguntaUsuarioResponse]
    total: int
    offset: int
    limit: int
