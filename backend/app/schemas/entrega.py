from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EntregaStatus


class EntregaPinResponse(BaseModel):
    """PIN em texto puro: exibido uma única vez ao comprador, nunca persistido."""

    pin: str
    expira_em: datetime
    tentativas_restantes: int


class EntregaConfirmacaoCreate(BaseModel):
    pin: str = Field(pattern=r"^\d{5}$", description="PIN de 5 dígitos informado pelo comprador.")


class EntregaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pedido_id: UUID
    status: EntregaStatus
    confirmado_em: datetime | None
    prazo_contestacao_em: datetime | None
