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
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.usuario import Usuario
from app.schemas.pedido import CheckoutCreate
from app.services.pedido import PedidoService
from app.services.reserva_estoque import ReservaEstoqueService


class FakeGateway:
    def __init__(self) -> None:
        self.preferencias_criadas = 0
        self.preferencias_consultadas = 0

    async def criar_preferencia(
        self,
        *,
        access_token: str,
        payload: dict[str, Any],
    ) -> MercadoPagoResponse:
        self.preferencias_criadas += 1
        assert self.preferencias_criadas == 1
        assert access_token == "token-vendedor"
        assert payload["marketplace_fee"] == 25.0
        assert payload["statement_descriptor"] == "OBRACIRCULAR"
        assert payload["notification_url"] == "https://example.test/webhook"
        assert payload["items"][0]["category_id"] == "home"
        assert payload["items"][0]["currency_id"] == "BRL"
        assert "email" not in payload["payer"]
        assert payload["payer"]["name"] == "Comprador"
        assert payload["payer"]["surname"] == "Checkout"
        assert payload["metadata"]["pagamento_id"]
        assert payload["external_reference"] == payload["metadata"]["pedido_id"]
        assert payload["auto_return"] == "approved"
        return MercadoPagoResponse(
            data={
                "id": "PREF-1",
                "init_point": "https://www.mercadopago.test/checkout",
            }
        )

    async def obter_preferencia(
        self, *, access_token: str, preferencia_id: str
    ) -> MercadoPagoResponse:
        assert access_token == "token-vendedor"
        assert preferencia_id == "PREF-1"
        self.preferencias_consultadas += 1
        return MercadoPagoResponse(
            data={
                "id": preferencia_id,
                "init_point": "https://www.mercadopago.test/checkout",
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
        mp_oauth_test_token=True,
        stock_reservation_minutes=30,
    )
    gateway = FakeGateway()
    servico = PedidoService(
        db_session,
        settings=settings,
        gateway=cast(MercadoPagoGateway, gateway),
    )
    dados_checkout = CheckoutCreate(
        anuncio_id=anuncio.id,
        quantidade=1,
        modalidade_entrega=ModalidadeEntrega.RETIRADA,
        endereco_entrega_id=None,
    )
    comprador_id = comprador.id
    comprador_email = comprador.email
    comprador_nome = comprador.nome
    comprador_criado_em = comprador.criado_em
    resposta = await servico.criar_checkout(
        dados_checkout,
        comprador_id=comprador_id,
        comprador_email=comprador_email,
        comprador_nome=comprador_nome,
        comprador_criado_em=comprador_criado_em,
    )

    assert resposta.taxa_marketplace == Decimal("25.00")

    retomada = await servico.criar_checkout(
        dados_checkout,
        comprador_id=comprador_id,
        comprador_email=comprador_email,
        comprador_nome=comprador_nome,
        comprador_criado_em=comprador_criado_em,
    )
    assert retomada.pedido_id == resposta.pedido_id
    assert retomada.pagamento_id == resposta.pagamento_id
    assert retomada.preferencia_externa_id == resposta.preferencia_externa_id
    assert retomada.init_point == resposta.init_point
    assert gateway.preferencias_criadas == 1
    assert gateway.preferencias_consultadas == 1

    async with db_session.begin():
        await db_session.refresh(anuncio)
        assert anuncio.quantidade == 0
        assert anuncio.status == AnuncioStatus.ESGOTADO
        pedido = await db_session.get(Pedido, resposta.pedido_id)
        assert pedido is not None
        assert pedido.endereco_entrega_snapshot is None
        pagamento = await db_session.get(Pagamento, resposta.pagamento_id)
        assert pagamento is not None
        assert pagamento.preferencia_externa_id == "PREF-1"
        assert pagamento.ordem_externa_id is None
        pedido.reserva_expira_em = datetime.now(UTC) - timedelta(seconds=1)

    assert await ReservaEstoqueService(db_session).liberar_expiradas() == 1
    assert await ReservaEstoqueService(db_session).liberar_expiradas() == 0
    async with db_session.begin():
        await db_session.refresh(anuncio)
        assert anuncio.quantidade == 1
        assert anuncio.status == AnuncioStatus.ATIVO
