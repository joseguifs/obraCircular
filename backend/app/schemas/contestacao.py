from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ContestacaoMotivo, ContestacaoStatus


class ContestacaoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    motivo: ContestacaoMotivo
    descricao: str = Field(min_length=1, max_length=5000)


class ContestacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pedido_id: UUID
    comprador_id: UUID
    motivo: ContestacaoMotivo
    descricao: str
    status: ContestacaoStatus
    resolucao: str | None
    resolvida_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime


class ContestacaoListResponse(BaseModel):
    items: list[ContestacaoResponse]
    total: int
