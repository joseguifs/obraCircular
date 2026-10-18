from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ContaPagamentoStatus


class ConexaoMercadoPagoResponse(BaseModel):
    authorization_url: str
    expires_in: int


class ContaPagamentoResponse(BaseModel):
    provedor: str = "MERCADO_PAGO"
    status: ContaPagamentoStatus
    conta_externa_id: str | None
    autorizado_em: datetime | None
    token_expira_em: datetime | None


class OAuthCallbackResponse(BaseModel):
    conectado: bool
