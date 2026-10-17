from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.provider_security import TokenCipher
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoResponse
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.conta_pagamento import ContaPagamento
from app.models.endereco import Endereco
from app.models.enums import (
    AnuncioStatus,
    CategoriaStatus,
    ContaPagamentoStatus,
    ModalidadeEntrega,
    UsuarioStatus,
)
from app.models.pedido import Pedido
from app.models.usuario import Usuario
from app.schemas.pedido import CheckoutCreate
from app.services.pedido import PedidoService
from app.services.reserva_estoque import ReservaEstoqueService


class FakeGateway:
    async def criar_preferencia(
        self, *, access_token: str, payload: dict[str, Any]
    ) -> MercadoPagoResponse:
        assert access_token == "token-vendedor"
        assert payload["marketplace_fee"] == 25.0
        return MercadoPagoResponse(
            data={
                "id": "pref-teste-1",
                "sandbox_init_point": "https://sandbox.mercadopago.test/checkout",
            }
        )


async def test_checkout_reserva_e_job_devolve_estoque_expirado(
    db_session: AsyncSession,
) -> None:
    chave = "chave-de-teste-segura-com-mais-de-32-caracteres"
    cipher = TokenCipher(chave)
    agora = datetime.now(UTC)
    async with db_session.begin():
        vendedor = Usuario(
            nome="Vendedor Checkout",
            email="vendedor-checkout@example.com",
            senha_hash="hash",
            telefone=None,
            status=UsuarioStatus.ATIVO,
        )
        comprador = Usuario(
            nome="Comprador Checkout",
            email="comprador-checkout@example.com",
            senha_hash="hash",
            telefone=None,
            status=UsuarioStatus.ATIVO,
        )
        categoria = Categoria(
            nome="Categoria checkout integrada",
            descricao=None,
            status=CategoriaStatus.ATIVA,
        )
        db_session.add_all([vendedor, comprador, categoria])
        await db_session.flush()
        endereco_vendedor = Endereco(
            usuario_id=vendedor.id,
            cep="01310100",
            logradouro="Avenida Paulista",
            numero="1",
            complemento=None,
            bairro="Bela Vista",
            cidade="São Paulo",
            estado="SP",
            deletado_em=None,
        )
        endereco_comprador = Endereco(
            usuario_id=comprador.id,
            cep="01001000",
            logradouro="Praça da Sé",
            numero="2",
            complemento=None,
            bairro="Sé",
            cidade="São Paulo",
            estado="SP",
            deletado_em=None,
        )
        db_session.add_all([endereco_vendedor, endereco_comprador])
        await db_session.flush()
        anuncio = Anuncio(
            titulo="Última unidade",
            descricao="Material para testar reserva concorrente.",
            categoria_id=categoria.id,
            vendedor_id=vendedor.id,
            endereco_id=endereco_vendedor.id,
            preco=Decimal("100.00"),
            imagem_url=None,
            quantidade=1,
            status=AnuncioStatus.ATIVO,
            encerrado_em=None,
            deletado_em=None,
        )
        conta = ContaPagamento(
            usuario_id=vendedor.id,
            conta_externa_id="seller-mp-1",
            access_token_criptografado=cipher.encrypt("token-vendedor"),
            refresh_token_criptografado=cipher.encrypt("refresh-vendedor"),
            status=ContaPagamentoStatus.ATIVA,
            autorizado_em=agora,
            token_expira_em=agora + timedelta(days=10),
        )
        db_session.add_all([anuncio, conta])

    settings = Settings(
        environment="test",
        mp_client_id="client-id",
        mp_client_secret=SecretStr("client-secret"),
        mp_token_encryption_key=SecretStr(chave),
        mp_oauth_redirect_uri="https://example.test/oauth/callback",
        mp_webhook_url="https://example.test/webhook",
        mp_public_base_url="https://example.test",
        stock_reservation_minutes=30,
    )
    resposta = await PedidoService(
        db_session,
        settings=settings,
        gateway=cast(MercadoPagoGateway, FakeGateway()),
    ).criar_checkout(
        CheckoutCreate(
            anuncio_id=anuncio.id,
            quantidade=1,
            modalidade_entrega=ModalidadeEntrega.ENTREGA,
            endereco_entrega_id=endereco_comprador.id,
        ),
        comprador_id=comprador.id,
        comprador_email=comprador.email,
    )

    assert resposta.taxa_marketplace == Decimal("25.00")

    async with db_session.begin():
        await db_session.refresh(anuncio)
        assert anuncio.quantidade == 0
        assert anuncio.status == AnuncioStatus.ESGOTADO
        pedido = await db_session.get(Pedido, resposta.pedido_id)
        assert pedido is not None
        pedido.reserva_expira_em = datetime.now(UTC) - timedelta(seconds=1)

    assert await ReservaEstoqueService(db_session).liberar_expiradas() == 1
    assert await ReservaEstoqueService(db_session).liberar_expiradas() == 0
    async with db_session.begin():
        await db_session.refresh(anuncio)
        assert anuncio.quantidade == 1
        assert anuncio.status == AnuncioStatus.ATIVO
