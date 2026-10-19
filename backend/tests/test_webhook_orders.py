from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conta_pagamento import ContaPagamento
from app.models.enums import (
    ContaPagamentoStatus,
    EventoProcessamentoStatus,
    ProvedorPagamento,
    UsuarioStatus,
)
from app.models.evento_provedor import EventoProvedor
from app.models.usuario import Usuario
from app.services.webhook_mercado_pago import WebhookMercadoPagoService


def test_normaliza_order_processada_para_pagamento_aprovado() -> None:
    dados = WebhookMercadoPagoService._normalizar_order(
        {
            "id": "ORDTST-1",
            "external_reference": "906388b1-917b-46b3-ad13-e620018e1480",
            "status": "processed",
            "status_detail": "accredited",
            "total_amount": "50.00",
            "transactions": {
                "payments": [
                    {
                        "id": "PAY-1",
                        "reference_id": "123456",
                        "status": "processed",
                        "status_detail": "accredited",
                        "payment_method": {
                            "id": "visa",
                            "type": "credit_card",
                            "installments": 2,
                        },
                    }
                ]
            },
        },
        {"live_mode": False},
    )

    assert dados["id"] == "123456"
    assert dados["status"] == "approved"
    assert dados["transaction_amount"] == "50.00"
    assert dados["payment_type_id"] == "credit_card"
    assert dados["installments"] == 2
    assert dados["live_mode"] is False


async def test_mp_connect_desconecta_conta_e_remove_tokens(
    db_session: AsyncSession,
) -> None:
    async with db_session.begin():
        usuario = Usuario(
            nome="Vendedor OAuth",
            email="vendedor-oauth@example.com",
            senha_hash="hash",
            telefone=None,
            status=UsuarioStatus.ATIVO,
        )
        db_session.add(usuario)
        await db_session.flush()
        conta = ContaPagamento(
            usuario_id=usuario.id,
            provedor=ProvedorPagamento.MERCADO_PAGO,
            conta_externa_id="987654321",
            access_token_criptografado="access-encriptado",
            refresh_token_criptografado="refresh-encriptado",
            status=ContaPagamentoStatus.ATIVA,
            autorizado_em=datetime.now(UTC),
            token_expira_em=datetime.now(UTC),
        )
        evento = EventoProvedor(
            provedor=ProvedorPagamento.MERCADO_PAGO,
            evento_externo_id="mp-connect-event-1",
            tipo="application.deauthorized",
            recurso_externo_id="987654321",
            payload={},
            status_processamento=EventoProcessamentoStatus.PENDENTE,
            tentativas=0,
            processado_em=None,
            erro=None,
        )
        db_session.add_all([conta, evento])
        await db_session.flush()
        evento_id = evento.id
        conta_id = conta.id

    await WebhookMercadoPagoService(db_session)._processar_mp_connect(
        evento_id,
        {
            "type": "mp-connect",
            "action": "application.deauthorized",
            "user_id": "987654321",
            "data": {"id": "987654321"},
        },
    )

    async with db_session.begin():
        conta_atualizada = await db_session.get(ContaPagamento, conta_id)
        evento_atualizado = await db_session.get(EventoProvedor, evento_id)
        assert conta_atualizada is not None
        assert conta_atualizada.status == ContaPagamentoStatus.DESCONECTADA
        assert conta_atualizada.access_token_criptografado is None
        assert conta_atualizada.refresh_token_criptografado is None
        assert evento_atualizado is not None
        assert evento_atualizado.status_processamento == EventoProcessamentoStatus.PROCESSADO
