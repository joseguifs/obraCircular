from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import gerar_pin_entrega, hash_pin_entrega, verificar_pin_entrega
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.conta_pagamento import ContaPagamento
from app.models.endereco import Endereco
from app.models.entrega import Entrega
from app.models.enums import (
    AnuncioStatus,
    CategoriaStatus,
    ContaPagamentoStatus,
    EntregaStatus,
    ModalidadeEntrega,
    PagamentoStatus,
    PedidoStatus,
    RepasseStatus,
)
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.repasse import Repasse
from app.models.usuario import Usuario
from app.services.entrega import PRAZO_CONTESTACAO, EntregaService


@dataclass
class Venda:
    pedido_id: UUID
    comprador_id: UUID
    vendedor_id: UUID


async def _criar_venda(session: AsyncSession, status: PedidoStatus) -> Venda:
    async with session.begin():
        vendedor = Usuario(nome="Vendedor", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        comprador = Usuario(nome="Comprador", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        categoria = Categoria(nome=str(uuid4()), status=CategoriaStatus.ATIVA)
        session.add_all([vendedor, comprador, categoria])
        await session.flush()
        endereco = Endereco(
            usuario_id=vendedor.id,
            cep="01001000",
            logradouro="Rua",
            numero="1",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
        )
        session.add(endereco)
        await session.flush()
        anuncio = Anuncio(
            vendedor_id=vendedor.id,
            categoria_id=categoria.id,
            endereco_id=endereco.id,
            titulo="Material",
            descricao="Material para teste",
            preco=Decimal("25.00"),
            quantidade=0,
            status=AnuncioStatus.ESGOTADO,
        )
        conta = ContaPagamento(
            usuario_id=vendedor.id,
            conta_externa_id=str(uuid4()),
            status=ContaPagamentoStatus.ATIVA,
            access_token_criptografado="fake",
            refresh_token_criptografado="fake",
        )
        session.add_all([anuncio, conta])
        await session.flush()
        pedido = Pedido(
            comprador_id=comprador.id,
            anuncio_id=anuncio.id,
            modalidade_entrega=ModalidadeEntrega.RETIRADA,
            quantidade=2,
            preco_unitario=Decimal("25.00"),
            valor_total=Decimal("50.00"),
            status=status,
            estoque_reservado_em=datetime.now(UTC),
        )
        session.add(pedido)
        await session.flush()
        pagamento = Pagamento(
            pedido_id=pedido.id,
            idempotency_key=str(uuid4()),
            valor=Decimal("50.00"),
            status=PagamentoStatus.APROVADO,
            preferencia_externa_id=str(uuid4()),
            pagamento_externo_id=str(uuid4()),
            aprovado_em=datetime.now(UTC),
        )
        session.add(pagamento)
        await session.flush()
        session.add(
            Repasse(
                pedido_id=pedido.id,
                pagamento_id=pagamento.id,
                vendedor_id=vendedor.id,
                conta_pagamento_id=conta.id,
                valor_bruto=Decimal("50.00"),
                taxa_provedor=Decimal("0.00"),
                taxa_marketplace=Decimal("12.50"),
                valor_liquido=Decimal("37.50"),
                percentual_marketplace=Decimal("25.00"),
                status=RepasseStatus.PAGO,
                pago_em=datetime.now(UTC),
            )
        )
        await session.flush()
        return Venda(pedido.id, comprador.id, vendedor.id)


@pytest.fixture
async def venda(db_session: AsyncSession) -> Venda:
    return await _criar_venda(db_session, PedidoStatus.PAGAMENTO_APROVADO)


async def _entrega(session: AsyncSession, pedido_id: UUID) -> Entrega:
    async with session.begin():
        entrega = await session.scalar(select(Entrega).where(Entrega.pedido_id == pedido_id))
        assert entrega is not None
        await session.refresh(entrega)
        return entrega


def _pin_diferente(pin: str) -> str:
    return f"{(int(pin) + 1) % 100000:05d}"


# --- hash do PIN ----------------------------------------------------------------------


def test_pin_gerado_tem_cinco_digitos() -> None:
    pins = {gerar_pin_entrega() for _ in range(200)}
    assert all(len(pin) == 5 and pin.isdigit() for pin in pins)
    assert len(pins) > 150


def test_hash_do_pin_depende_da_entrega_e_da_chave() -> None:
    settings = get_settings()
    entrega_a, entrega_b = uuid4(), uuid4()
    hash_a = hash_pin_entrega("01234", entrega_a, settings)

    assert "01234" not in hash_a
    assert verificar_pin_entrega("01234", entrega_a, hash_a, settings)
    assert not verificar_pin_entrega("01235", entrega_a, hash_a, settings)
    assert not verificar_pin_entrega("01234", entrega_b, hash_a, settings)

    outra_chave = Settings(delivery_pin_secret_key=SecretStr("x" * 32))
    assert not verificar_pin_entrega("01234", entrega_a, hash_a, outra_chave)


def test_chave_do_pin_curta_e_rejeitada() -> None:
    with pytest.raises(ValueError, match="DELIVERY_PIN_SECRET_KEY"):
        Settings(delivery_pin_secret_key=SecretStr("curta"))


# --- geração --------------------------------------------------------------------------


async def test_comprador_gera_pin_e_somente_o_hash_e_salvo(
    db_session: AsyncSession, venda: Venda
) -> None:
    antes = datetime.now(UTC)
    resposta = await EntregaService(db_session).gerar_pin(venda.pedido_id, venda.comprador_id)

    assert len(resposta.pin) == 5 and resposta.pin.isdigit()
    assert resposta.tentativas_restantes == 5
    entrega = await _entrega(db_session, venda.pedido_id)
    assert entrega.status == EntregaStatus.AGUARDANDO_ENVIO
    assert resposta.pin not in entrega.pin_hash
    assert entrega.pin_expira_em is not None
    depois = datetime.now(UTC)
    assert antes + timedelta(hours=24) <= entrega.pin_expira_em <= depois + timedelta(hours=24)


async def test_regenerar_pin_invalida_o_anterior(db_session: AsyncSession, venda: Venda) -> None:
    service = EntregaService(db_session)
    primeiro = await service.gerar_pin(venda.pedido_id, venda.comprador_id)
    segundo = await service.gerar_pin(venda.pedido_id, venda.comprador_id)
    if primeiro.pin == segundo.pin:  # 1 em 100 mil: gera de novo para o teste ser válido
        segundo = await service.gerar_pin(venda.pedido_id, venda.comprador_id)

    with pytest.raises(AppError) as erro:
        await service.confirmar(venda.pedido_id, venda.vendedor_id, primeiro.pin)
    assert erro.value.code == "DELIVERY_PIN_INVALID"

    resposta = await service.confirmar(venda.pedido_id, venda.vendedor_id, segundo.pin)
    assert resposta.status == EntregaStatus.ENTREGUE


async def test_somente_o_comprador_gera_o_pin(db_session: AsyncSession, venda: Venda) -> None:
    for usuario_id in (venda.vendedor_id, uuid4()):
        with pytest.raises(AppError) as erro:
            await EntregaService(db_session).gerar_pin(venda.pedido_id, usuario_id)
        assert erro.value.status_code == 404


async def test_pin_nao_e_gerado_para_pedido_sem_pagamento(db_session: AsyncSession) -> None:
    venda = await _criar_venda(db_session, PedidoStatus.AGUARDANDO_PAGAMENTO)
    with pytest.raises(AppError) as erro:
        await EntregaService(db_session).gerar_pin(venda.pedido_id, venda.comprador_id)
    assert erro.value.code == "ORDER_NOT_AWAITING_DELIVERY"


# --- confirmação ----------------------------------------------------------------------


async def test_vendedor_confirma_com_pin_correto(db_session: AsyncSession, venda: Venda) -> None:
    service = EntregaService(db_session)
    pin = (await service.gerar_pin(venda.pedido_id, venda.comprador_id)).pin

    resposta = await service.confirmar(venda.pedido_id, venda.vendedor_id, pin)

    assert resposta.status == EntregaStatus.ENTREGUE
    assert resposta.confirmado_em is not None
    assert resposta.prazo_contestacao_em == resposta.confirmado_em + PRAZO_CONTESTACAO
    async with db_session.begin():
        pedido = await db_session.get(Pedido, venda.pedido_id, populate_existing=True)
        repasse = await db_session.scalar(
            select(Repasse).where(Repasse.pedido_id == venda.pedido_id)
        )
        assert repasse is not None
        await db_session.refresh(repasse)
    assert pedido is not None and pedido.status == PedidoStatus.ENTREGUE
    assert repasse.status == RepasseStatus.EM_PERIODO_CONTESTACAO
    assert repasse.liberacao_prevista_em == resposta.prazo_contestacao_em
    entrega = await _entrega(db_session, venda.pedido_id)
    assert entrega.confirmado_por == venda.vendedor_id
    assert entrega.pin_expira_em is None


async def test_confirmacao_repetida_e_idempotente(db_session: AsyncSession, venda: Venda) -> None:
    service = EntregaService(db_session)
    pin = (await service.gerar_pin(venda.pedido_id, venda.comprador_id)).pin
    primeira = await service.confirmar(venda.pedido_id, venda.vendedor_id, pin)
    segunda = await service.confirmar(venda.pedido_id, venda.vendedor_id, pin)
    assert segunda == primeira

    with pytest.raises(AppError) as erro:
        await service.gerar_pin(venda.pedido_id, venda.comprador_id)
    assert erro.value.code == "ORDER_NOT_AWAITING_DELIVERY"


async def test_somente_o_vendedor_confirma(db_session: AsyncSession, venda: Venda) -> None:
    service = EntregaService(db_session)
    pin = (await service.gerar_pin(venda.pedido_id, venda.comprador_id)).pin
    for usuario_id in (venda.comprador_id, uuid4()):
        with pytest.raises(AppError) as erro:
            await service.confirmar(venda.pedido_id, usuario_id, pin)
        assert erro.value.status_code == 404


async def test_confirmar_sem_pin_gerado(db_session: AsyncSession, venda: Venda) -> None:
    with pytest.raises(AppError) as erro:
        await EntregaService(db_session).confirmar(venda.pedido_id, venda.vendedor_id, "12345")
    assert erro.value.code == "DELIVERY_PIN_NOT_GENERATED"


async def test_cinco_tentativas_incorretas_bloqueiam_o_pin(
    db_session: AsyncSession, venda: Venda
) -> None:
    service = EntregaService(db_session)
    pin = (await service.gerar_pin(venda.pedido_id, venda.comprador_id)).pin
    errado = _pin_diferente(pin)

    for restantes in (4, 3, 2, 1):
        with pytest.raises(AppError) as erro:
            await service.confirmar(venda.pedido_id, venda.vendedor_id, errado)
        assert erro.value.code == "DELIVERY_PIN_INVALID"
        assert f"Tentativas restantes: {restantes}" in erro.value.detail
    with pytest.raises(AppError) as erro:
        await service.confirmar(venda.pedido_id, venda.vendedor_id, errado)
    assert erro.value.code == "DELIVERY_PIN_BLOCKED"

    entrega = await _entrega(db_session, venda.pedido_id)
    assert entrega.pin_tentativas == 5
    assert entrega.pin_bloqueado_em is not None

    # Bloqueado, nem o PIN correto é aceito.
    with pytest.raises(AppError) as erro:
        await service.confirmar(venda.pedido_id, venda.vendedor_id, pin)
    assert erro.value.code == "DELIVERY_PIN_BLOCKED"

    # Um novo PIN gerado pelo comprador desbloqueia e zera as tentativas.
    novo = await service.gerar_pin(venda.pedido_id, venda.comprador_id)
    assert novo.tentativas_restantes == 5
    resposta = await service.confirmar(venda.pedido_id, venda.vendedor_id, novo.pin)
    assert resposta.status == EntregaStatus.ENTREGUE


async def test_pin_expirado_e_recusado(db_session: AsyncSession, venda: Venda) -> None:
    service = EntregaService(db_session)
    pin = (await service.gerar_pin(venda.pedido_id, venda.comprador_id)).pin
    entrega = await _entrega(db_session, venda.pedido_id)
    async with db_session.begin():
        entrega.pin_expira_em = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(AppError) as erro:
        await service.confirmar(venda.pedido_id, venda.vendedor_id, pin)
    assert erro.value.code == "DELIVERY_PIN_EXPIRED"


async def test_pedido_cancelado_nao_confirma(db_session: AsyncSession, venda: Venda) -> None:
    service = EntregaService(db_session)
    pin = (await service.gerar_pin(venda.pedido_id, venda.comprador_id)).pin
    async with db_session.begin():
        pedido = await db_session.get(Pedido, venda.pedido_id)
        assert pedido is not None
        pedido.status = PedidoStatus.CANCELADO

    with pytest.raises(AppError) as erro:
        await service.confirmar(venda.pedido_id, venda.vendedor_id, pin)
    assert erro.value.code == "ORDER_NOT_AWAITING_DELIVERY"


# --- rotas ----------------------------------------------------------------------------


@pytest.mark.parametrize("pin", ["1234", "123456", "12a45", ""])
async def test_rota_de_confirmacao_valida_formato_do_pin(
    client: AsyncClient, usuario_autenticado: Usuario, pin: str
) -> None:
    resposta = await client.post(f"/api/v1/orders/{uuid4()}/delivery/confirm", json={"pin": pin})
    assert resposta.status_code == 422


async def test_rota_de_pin_de_pedido_inexistente(
    client: AsyncClient, usuario_autenticado: Usuario
) -> None:
    resposta = await client.post(f"/api/v1/orders/{uuid4()}/delivery/pin")
    assert resposta.status_code == 404
    assert resposta.json()["code"] == "ORDER_NOT_FOUND"
