from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import criar_par_tokens
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.contestacao import Contestacao
from app.models.endereco import Endereco
from app.models.entrega import Entrega
from app.models.enums import (
    ContestacaoMotivo,
    ContestacaoStatus,
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
from app.schemas.contestacao import ContestacaoCreate
from app.services.contestacao import ContestacaoService

AGORA = datetime(2026, 10, 31, 12, tzinfo=UTC)
DADOS = {"motivo": "PRODUTO_DANIFICADO", "descricao": "  Parte das telhas chegou quebrada.  "}


class RelogioFixo(datetime):
    @classmethod
    def now(cls, tz: object = None) -> datetime:
        return AGORA


@dataclass
class CompraEntregue:
    pedido_id: UUID
    comprador_id: UUID
    vendedor_id: UUID
    repasse_id: UUID
    entrega_id: UUID
    anuncio_id: UUID
    pagamento_id: UUID

    @property
    def url(self) -> str:
        return f"/api/v1/orders/{self.pedido_id}/disputes"

    def headers(self, usuario_id: UUID | None = None) -> dict[str, str]:
        tokens = criar_par_tokens(usuario_id or self.comprador_id, get_settings())
        return {"Authorization": f"Bearer {tokens.access_token}"}


@pytest.fixture(params=[False, True], ids=["split-legado", "repasse-posterior"])
async def compra_entregue(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> CompraEntregue:
    centralizado = getattr(request, "param", False)
    monkeypatch.setattr("app.services.contestacao.datetime", RelogioFixo)
    async with db_session.begin():
        vendedor = Usuario(nome="Vendedor", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        comprador = Usuario(nome="Comprador", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        categoria = Categoria(nome=str(uuid4()))
        db_session.add_all([vendedor, comprador, categoria])
        await db_session.flush()
        endereco = Endereco(
            usuario_id=vendedor.id,
            cep="01001000",
            logradouro="Rua",
            numero="1",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
        )
        db_session.add(endereco)
        await db_session.flush()
        anuncio = Anuncio(
            vendedor_id=vendedor.id,
            categoria_id=categoria.id,
            endereco_id=endereco.id,
            titulo="Telhas",
            descricao="Telhas de teste",
            preco=Decimal("50.00"),
            quantidade=5,
        )
        db_session.add(anuncio)
        await db_session.flush()
        pedido = Pedido(
            comprador_id=comprador.id,
            anuncio_id=anuncio.id,
            modalidade_entrega=ModalidadeEntrega.RETIRADA,
            quantidade=2,
            preco_unitario=Decimal("50.00"),
            valor_total=Decimal("100.00"),
            status=PedidoStatus.ENTREGUE,
            modelo_financeiro="REPASSE_POSTERIOR" if centralizado else "SPLIT_LEGADO",
            percentual_marketplace=Decimal("20.00") if centralizado else Decimal("25.00"),
            taxa_marketplace=Decimal("20.00") if centralizado else None,
            valor_vendedor=Decimal("80.00") if centralizado else None,
            recebedor_externo_id="marketplace-test" if centralizado else None,
            estoque_reservado_em=AGORA - timedelta(days=2),
        )
        db_session.add(pedido)
        await db_session.flush()
        pagamento = Pagamento(
            pedido_id=pedido.id,
            idempotency_key=str(uuid4()),
            valor=pedido.valor_total,
            status=PagamentoStatus.APROVADO,
        )
        entrega = Entrega(
            pedido_id=pedido.id,
            status=EntregaStatus.ENTREGUE,
            pin_hash="hash-nao-exposto",
            confirmado_em=AGORA - timedelta(days=1),
            confirmado_por=vendedor.id,
            prazo_contestacao_em=AGORA + timedelta(days=6),
        )
        db_session.add_all([pagamento, entrega])
        await db_session.flush()
        repasse = Repasse(
            pedido_id=pedido.id,
            pagamento_id=pagamento.id,
            vendedor_id=vendedor.id,
            valor_bruto=pedido.valor_total,
            taxa_marketplace=Decimal("20.00") if centralizado else Decimal("25.00"),
            taxa_provedor=Decimal("5.00"),
            valor_liquido=Decimal("80.00") if centralizado else Decimal("70.00"),
            percentual_marketplace=Decimal("20.00") if centralizado else Decimal("25.00"),
            taxas_por_conta_marketplace=centralizado,
            status=RepasseStatus.EM_PERIODO_CONTESTACAO,
            liberacao_prevista_em=entrega.prazo_contestacao_em,
            pago_em=None if centralizado else AGORA - timedelta(days=2),
            liberado_em=None if centralizado else AGORA - timedelta(days=2),
            repasse_externo_id=None if centralizado else str(uuid4()),
        )
        db_session.add(repasse)
        await db_session.flush()
        return CompraEntregue(
            pedido.id, comprador.id, vendedor.id, repasse.id, entrega.id, anuncio.id, pagamento.id
        )


async def _verificar_sem_abertura(db_session: AsyncSession, compra: CompraEntregue) -> None:
    # As consultas GET deixam uma transação implícita na sessão compartilhada do teste.
    await db_session.rollback()
    async with db_session.begin():
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(Contestacao)
                .where(Contestacao.pedido_id == compra.pedido_id)
            )
            == 0
        )
        pedido = await db_session.get(Pedido, compra.pedido_id, populate_existing=True)
        repasse = await db_session.get(Repasse, compra.repasse_id, populate_existing=True)
        assert pedido is not None and pedido.status == PedidoStatus.ENTREGUE
        assert repasse is not None and repasse.bloqueado_em is None


async def test_abertura_e_consulta_com_autenticacao_real(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue
) -> None:
    compra = compra_entregue
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["comprador_id"] == str(compra.comprador_id)
    assert corpo["pedido_id"] == str(compra.pedido_id)
    assert corpo["status"] == "ABERTA"
    assert corpo["motivo"] == DADOS["motivo"]
    assert corpo["descricao"] == DADOS["descricao"].strip()
    assert corpo["resolucao"] is None
    assert corpo["resolvida_em"] is None
    assert "pin_hash" not in corpo

    async with db_session.begin():
        pedido = await db_session.get(Pedido, compra.pedido_id, populate_existing=True)
        repasse = await db_session.get(Repasse, compra.repasse_id, populate_existing=True)
        pagamento = await db_session.get(Pagamento, compra.pagamento_id)
        anuncio = await db_session.get(Anuncio, compra.anuncio_id)
        assert pedido is not None and pedido.status == PedidoStatus.EM_CONTESTACAO
        assert repasse is not None and repasse.status == RepasseStatus.BLOQUEADO
        assert repasse.bloqueado_em == AGORA
        assert repasse.liberacao_prevista_em == AGORA + timedelta(days=6)
        if pedido.modelo_financeiro == "REPASSE_POSTERIOR":
            assert repasse.pago_em is None and repasse.liberado_em is None
            assert repasse.repasse_externo_id is None
            assert repasse.valor_liquido == Decimal("80.00")
        else:
            assert repasse.pago_em == repasse.liberado_em == AGORA - timedelta(days=2)
            assert repasse.valor_liquido == Decimal("70.00")
        assert pagamento is not None and pagamento.status == PagamentoStatus.APROVADO
        assert anuncio is not None and anuncio.quantidade == 5

    consulta = await client.get(compra.url, headers=compra.headers())
    assert consulta.status_code == 200, consulta.text
    assert consulta.json() == {"items": [corpo], "total": 1}


async def test_fluxo_pin_venda_entrega_e_abertura_pela_api(
    client: AsyncClient,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.contestacao.datetime", datetime)
    compra = compra_entregue
    async with db_session.begin():
        pedido = await db_session.get(Pedido, compra.pedido_id)
        entrega = await db_session.get(Entrega, compra.entrega_id)
        repasse = await db_session.get(Repasse, compra.repasse_id)
        assert pedido is not None and entrega is not None and repasse is not None
        pedido.status = PedidoStatus.PAGAMENTO_APROVADO
        entrega.status = EntregaStatus.PREPARANDO
        entrega.confirmado_em = None
        entrega.confirmado_por = None
        entrega.prazo_contestacao_em = None
        repasse.status = (
            RepasseStatus.AGUARDANDO_ENTREGA if pedido.repasse_posterior else RepasseStatus.PAGO
        )

    base = f"/api/v1/orders/{compra.pedido_id}"
    pin = await client.post(f"{base}/delivery/pin", headers=compra.headers())
    assert pin.status_code == 201, pin.text
    assert len(pin.json()["pin"]) == 5
    vendedor_headers = compra.headers(compra.vendedor_id)
    # Consultar vendas não concede ao vendedor acesso às compras ou ao PIN do comprador.
    assert (await client.get(base, headers=vendedor_headers)).status_code == 404
    assert (
        await client.post(f"{base}/delivery/pin", headers=vendedor_headers)
    ).status_code == 404
    assert (await client.get("/api/v1/orders/sales")).status_code == 401
    vendas_comprador = await client.get("/api/v1/orders/sales", headers=compra.headers())
    assert vendas_comprador.json() == {"items": [], "total": 0}

    confirmacao = await client.post(
        f"{base}/delivery/confirm", headers=vendedor_headers, json={"pin": pin.json()["pin"]}
    )
    assert confirmacao.status_code == 200, confirmacao.text
    dados_entrega = confirmacao.json()
    assert dados_entrega["status"] == "ENTREGUE"
    confirmado = datetime.fromisoformat(dados_entrega["confirmado_em"].replace("Z", "+00:00"))
    prazo = datetime.fromisoformat(dados_entrega["prazo_contestacao_em"].replace("Z", "+00:00"))
    assert prazo - confirmado == timedelta(days=7)

    consulta = await client.get(base, headers=compra.headers())
    assert consulta.status_code == 200, consulta.text
    assert consulta.json()["status"] == "ENTREGUE"
    assert consulta.json()["entrega"] == dados_entrega
    assert consulta.json()["repasse_status"] == "EM_PERIODO_CONTESTACAO"
    vendas = await client.get("/api/v1/orders/sales", headers=vendedor_headers)
    assert vendas.status_code == 200, vendas.text
    assert vendas.json()["items"] == [consulta.json()]
    assert "pin" not in vendas.text

    abertura = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert abertura.status_code == 201, abertura.text
    consulta = await client.get(base, headers=compra.headers())
    assert consulta.json()["status"] == "EM_CONTESTACAO"
    assert consulta.json()["repasse_status"] == "BLOQUEADO"


async def test_abertura_tambem_atende_entrega_domiciliar(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        endereco = Endereco(
            usuario_id=compra.comprador_id,
            cep="01001000",
            logradouro="Rua do comprador",
            numero="2",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
        )
        db_session.add(endereco)
        await db_session.flush()
        pedido = await db_session.get(Pedido, compra.pedido_id)
        assert pedido is not None
        pedido.modalidade_entrega = ModalidadeEntrega.ENTREGA
        pedido.endereco_entrega_id = endereco.id
        pedido.endereco_entrega_snapshot = {"logradouro": endereco.logradouro, "numero": "2"}
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 201, resposta.text


async def test_repeticao_nao_duplica_contestacao(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue
) -> None:
    compra = compra_entregue
    primeira = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    segunda = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert primeira.status_code == 201, primeira.text
    assert segunda.status_code == 409
    assert segunda.json()["code"] == "DISPUTE_ALREADY_ACTIVE"
    async with db_session.begin():
        assert (
            await db_session.scalar(
                select(func.count())
                .select_from(Contestacao)
                .where(Contestacao.pedido_id == compra.pedido_id)
            )
            == 1
        )


@pytest.mark.parametrize("status", ["ABERTA", "EM_ANALISE", "AGUARDANDO_VENDEDOR", "ACEITA"])
async def test_todos_estados_ativos_impedem_nova_abertura(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue, status: str
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        db_session.add(
            Contestacao(
                pedido_id=compra.pedido_id,
                comprador_id=compra.comprador_id,
                motivo=ContestacaoMotivo.OUTRO,
                descricao="Contestação anterior",
                status=status,
            )
        )
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "DISPUTE_ALREADY_ACTIVE"


@pytest.mark.parametrize("status", [ContestacaoStatus.RECUSADA, ContestacaoStatus.CANCELADA])
async def test_historico_encerrado_permite_reabertura_dentro_do_prazo(
    client: AsyncClient,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    status: ContestacaoStatus,
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        db_session.add(
            Contestacao(
                pedido_id=compra.pedido_id,
                comprador_id=compra.comprador_id,
                motivo=ContestacaoMotivo.OUTRO,
                descricao="Contestação anterior",
                status=status,
                criado_em=AGORA - timedelta(days=1),
            )
        )
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 201, resposta.text
    historico = await client.get(compra.url, headers=compra.headers())
    assert historico.status_code == 200
    assert historico.json()["total"] == 2
    assert historico.json()["items"][0]["id"] == resposta.json()["id"]


@pytest.mark.parametrize("status", [s for s in PedidoStatus if s != PedidoStatus.ENTREGUE])
async def test_pedido_precisa_estar_entregue(
    client: AsyncClient,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    status: PedidoStatus,
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        pedido = await db_session.get(Pedido, compra.pedido_id)
        assert pedido is not None
        pedido.status = status
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "DISPUTE_ORDER_NOT_DELIVERED"


@pytest.mark.parametrize(
    "status",
    [
        RepasseStatus.PROCESSANDO,
        RepasseStatus.PAGO,
        RepasseStatus.CANCELADO,
        RepasseStatus.REEMBOLSADO,
    ],
)
async def test_repasse_em_estado_incompativel_impede_abertura(
    client: AsyncClient,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    status: RepasseStatus,
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        repasse = await db_session.get(Repasse, compra.repasse_id)
        assert repasse is not None
        repasse.status = status
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "DISPUTE_PAYOUT_NOT_ALLOWED"
    await _verificar_sem_abertura(db_session, compra)


@pytest.mark.parametrize("campo", ["confirmado_em", "prazo_contestacao_em", "status", "registro"])
async def test_entrega_sem_confirmacao_ou_prazo_nao_permite_abertura(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue, campo: str
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        entrega = await db_session.get(Entrega, compra.entrega_id)
        assert entrega is not None
        if campo == "registro":
            await db_session.delete(entrega)
        elif campo == "status":
            entrega.status = EntregaStatus.PREPARANDO
        else:
            setattr(entrega, campo, None)
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "DISPUTE_DELIVERY_NOT_CONFIRMED"
    await _verificar_sem_abertura(db_session, compra)


@pytest.mark.parametrize("microssegundos,esperado", [(0, 201), (-1, 409), (1, 201)])
async def test_limite_do_prazo_e_inclusivo(
    client: AsyncClient,
    db_session: AsyncSession,
    compra_entregue: CompraEntregue,
    microssegundos: int,
    esperado: int,
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        entrega = await db_session.get(Entrega, compra.entrega_id)
        assert entrega is not None
        entrega.prazo_contestacao_em = AGORA + timedelta(microseconds=microssegundos)
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == esperado, resposta.text
    if esperado == 409:
        assert resposta.json()["code"] == "DISPUTE_DEADLINE_EXPIRED"
        await _verificar_sem_abertura(db_session, compra)


async def test_repasse_ausente_impede_abertura(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        repasse = await db_session.get(Repasse, compra.repasse_id)
        assert repasse is not None
        await db_session.delete(repasse)
    resposta = await client.post(compra.url, headers=compra.headers(), json=DADOS)
    assert resposta.status_code == 409
    assert resposta.json()["code"] == "DISPUTE_PAYOUT_NOT_FOUND"


async def test_apenas_comprador_pode_abrir_e_consultar(
    client: AsyncClient, db_session: AsyncSession, compra_entregue: CompraEntregue
) -> None:
    compra = compra_entregue
    async with db_session.begin():
        terceiro = Usuario(nome="Terceiro", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        db_session.add(terceiro)
        await db_session.flush()
        terceiro_id = terceiro.id
    for usuario_id in (compra.vendedor_id, terceiro_id):
        headers = compra.headers(usuario_id)
        abertura = await client.post(compra.url, headers=headers, json=DADOS)
        consulta = await client.get(compra.url, headers=headers)
        assert abertura.status_code == consulta.status_code == 404
        assert abertura.json()["code"] == consulta.json()["code"] == "ORDER_NOT_FOUND"
    await _verificar_sem_abertura(db_session, compra)


async def test_autenticacao_obrigatoria(
    client: AsyncClient, compra_entregue: CompraEntregue
) -> None:
    abertura = await client.post(compra_entregue.url, json=DADOS)
    consulta = await client.get(compra_entregue.url)
    assert abertura.status_code == consulta.status_code == 401


async def test_pedido_inexistente_e_lista_vazia(
    client: AsyncClient, compra_entregue: CompraEntregue
) -> None:
    compra = compra_entregue
    url = f"/api/v1/orders/{uuid4()}/disputes"
    abertura = await client.post(url, headers=compra.headers(), json=DADOS)
    consulta = await client.get(url, headers=compra.headers())
    assert abertura.status_code == consulta.status_code == 404
    vazia = await client.get(compra.url, headers=compra.headers())
    assert vazia.status_code == 200
    assert vazia.json() == {"items": [], "total": 0}


async def test_falha_apos_persistir_desfaz_contestacao_pedido_e_bloqueio(
    db_session: AsyncSession, compra_entregue: CompraEntregue, monkeypatch: pytest.MonkeyPatch
) -> None:
    flush_original = db_session.flush

    async def flush_com_falha() -> None:
        await flush_original()
        raise RuntimeError("Falha depois de gravar as alterações")

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "flush", flush_com_falha)
        with pytest.raises(RuntimeError, match="Falha depois de gravar"):
            await ContestacaoService(db_session).abrir(
                compra_entregue.pedido_id, ContestacaoCreate(**DADOS), compra_entregue.comprador_id
            )
    await _verificar_sem_abertura(db_session, compra_entregue)


@pytest.mark.parametrize(
    "dados",
    [
        {},
        {"motivo": "INVALIDO", "descricao": "Teste"},
        {"motivo": "OUTRO", "descricao": "   "},
        {"motivo": "OUTRO", "descricao": "x" * 5001},
        {"motivo": "OUTRO", "descricao": "Teste", "comprador_id": str(uuid4())},
        {"motivo": "OUTRO", "descricao": "Teste", "status": "ACEITA"},
    ],
)
async def test_api_rejeita_dados_invalidos(
    client: AsyncClient, compra_entregue: CompraEntregue, dados: dict[str, str]
) -> None:
    resposta = await client.post(compra_entregue.url, headers=compra_entregue.headers(), json=dados)
    assert resposta.status_code == 422


@pytest.mark.parametrize("motivo", list(ContestacaoMotivo))
def test_schema_aceita_motivos_documentados(motivo: ContestacaoMotivo) -> None:
    dados = ContestacaoCreate(motivo=motivo, descricao="  Problema no pedido.  ")
    assert dados.descricao == "Problema no pedido."


def test_schema_nao_aceita_descricao_nula() -> None:
    with pytest.raises(ValidationError):
        ContestacaoCreate.model_validate({"motivo": "OUTRO", "descricao": None})
