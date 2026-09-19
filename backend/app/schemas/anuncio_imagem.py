from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnuncioImagemResponse(BaseModel):
    id: UUID
    anuncio_id: UUID
    url: str
    nome_original: str
    mime_type: str
    tamanho_bytes: int
    ordem: int
    criado_em: datetime


class AnuncioImagemListResponse(BaseModel):
    items: list[AnuncioImagemResponse]
