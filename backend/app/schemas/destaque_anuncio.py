from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DestaqueAnuncioStatus, MetodoPagamento, PagamentoStatus


class DestaquePrecoResponse(BaseModel):
    valor: Decimal
    duracao_dias: int
    moeda: str = "BRL"


class DestaqueCheckoutCreate(BaseModel):
    anuncio_id: UUID


class DestaqueCheckoutResponse(BaseModel):
    destaque_id: UUID
    anuncio_id: UUID
    preferencia_externa_id: str
    init_point: str
    valor: Decimal
    duracao_dias: int
    checkout_expira_em: datetime


class DestaqueAnuncioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    anuncio_id: UUID
    valor: Decimal
    duracao_dias: int
    status: DestaqueAnuncioStatus
    status_pagamento: PagamentoStatus
    metodo: MetodoPagamento | None
    checkout_expira_em: datetime
    aprovado_em: datetime | None
    inicia_em: datetime | None
    expira_em: datetime | None
    cancelado_em: datetime | None
    criado_em: datetime


class DestaqueAnuncioListResponse(BaseModel):
    items: list[DestaqueAnuncioResponse]
    total: int
