from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnuncioImagemResponse(BaseModel):
    id: UUID
    anuncio_id: UUID
    url: str
    nome_original: str
    mime_type: str
    tamanho_bytes: int
    ordem: int
    criado_em: datetime


class AvisoImagemResponse(BaseModel):
    """Orientação sobre uma foto aceita que foge do padrão 4:3 recomendado."""

    imagem_id: UUID
    nome_original: str
    largura: int
    altura: int
    codigo: str
    mensagem: str


class AnuncioImagemListResponse(BaseModel):
    items: list[AnuncioImagemResponse]
    avisos: list[AvisoImagemResponse] = Field(default_factory=list)
