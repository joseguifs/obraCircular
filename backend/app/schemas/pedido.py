from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ModalidadeEntrega, PagamentoStatus, PedidoStatus, ReembolsoStatus


class CheckoutCreate(BaseModel):
    anuncio_id: UUID
    quantidade: int = Field(ge=1)
    modalidade_entrega: ModalidadeEntrega
    endereco_entrega_id: UUID | None = None

    @model_validator(mode="after")
    def validar_endereco(self) -> Self:
        if self.modalidade_entrega == ModalidadeEntrega.ENTREGA and not self.endereco_entrega_id:
            raise ValueError("Selecione um endereço para entrega.")
        if self.modalidade_entrega == ModalidadeEntrega.RETIRADA and self.endereco_entrega_id:
            raise ValueError("Retirada não utiliza endereço de entrega.")
        return self


class CheckoutResponse(BaseModel):
    pedido_id: UUID
    pagamento_id: UUID
    checkout_url: str
    reserva_expira_em: datetime
    valor_total: Decimal
    taxa_marketplace: Decimal


class PagamentoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: PagamentoStatus
    pagamento_externo_id: str | None
    status_detalhe: str | None


class PedidoResponse(BaseModel):
    id: UUID
    anuncio_id: UUID
    comprador_id: UUID
    quantidade: int
    preco_unitario: Decimal
    valor_total: Decimal
    modalidade_entrega: ModalidadeEntrega
    status: PedidoStatus
    criado_em: datetime
    reserva_expira_em: datetime | None
    pagamento: PagamentoResumo | None = None


class PedidoListResponse(BaseModel):
    items: list[PedidoResponse]
    total: int


class ReembolsoResponse(BaseModel):
    id: UUID
    pedido_id: UUID
    status: ReembolsoStatus
    valor: Decimal
    reembolso_externo_id: str | None
