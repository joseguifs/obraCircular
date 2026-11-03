from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.enums import (
    AnuncioStatus,
    ContestacaoStatus,
    PagamentoStatus,
    PedidoStatus,
    ReembolsoStatus,
    RepasseStatus,
)
from app.models.reembolso import Reembolso
from app.schemas.admin import AdminContestacaoDecisao
from app.services.conta_pagamento import ContaPagamentoService
from app.services.contestacao import ContestacaoService
from app.services.reembolso import ReembolsoService


class FakeTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_):
        return None


class FakeSession:
    def __init__(self):
        self.scalar = AsyncMock()
        self.get = AsyncMock()
        self.rollback = AsyncMock()
        self.adicionados = []
        self.flush = AsyncMock(side_effect=self.atribuir_ids)

    def begin(self):
        return FakeTransaction()

    def in_transaction(self):
        return False

    def add(self, objeto):
        self.adicionados.append(objeto)

    def atribuir_ids(self):
        for objeto in self.adicionados:
            if objeto.id is None:
                objeto.id = uuid4()


def preparar(status=ContestacaoStatus.ABERTA):
    session = FakeSession()
    reembolsos = AsyncMock(spec=ReembolsoService)
    service = ContestacaoService(cast(AsyncSession, session), reembolsos)
    service.repository = AsyncMock()
    contestacao = SimpleNamespace(
        id=uuid4(),
        status=status,
        resolucao=None,
        resolvida_em=None,
        resolvida_por=None,
    )
    pedido = SimpleNamespace(id=uuid4(), anuncio_id=uuid4(), status=PedidoStatus.EM_CONTESTACAO)
    repasse = SimpleNamespace(status=RepasseStatus.BLOQUEADO)
    return session, service, contestacao, pedido, repasse


@pytest.mark.parametrize(
    "dias, esperado", [(2, RepasseStatus.EM_PERIODO_CONTESTACAO), (-2, RepasseStatus.PAGO)]
)
async def test_recusa_atualiza_pedido_e_repasse_conforme_prazo(dias, esperado):
    session, service, contestacao, pedido, repasse = preparar()
    entrega = SimpleNamespace(prazo_contestacao_em=datetime.now(UTC) + timedelta(days=dias))
    session.scalar.side_effect = [pedido.id, pedido, contestacao, repasse, entrega]
    admin = uuid4()
    await service.decidir(
        contestacao.id,
        AdminContestacaoDecisao(status="RECUSADA", resolucao="Produto entregue corretamente."),
        admin,
    )
    assert contestacao.status == ContestacaoStatus.RECUSADA
    assert contestacao.resolvida_por == admin
    assert contestacao.resolvida_em.tzinfo == UTC
    assert pedido.status == PedidoStatus.ENTREGUE
    assert repasse.status == esperado
    assert not session.adicionados
    service.reembolso_service.processar_preparado.assert_not_awaited()


async def test_aceita_cria_reembolso_integral_vinculado_sem_desbloquear_pedido():
    session, service, contestacao, pedido, repasse = preparar()
    pagamento = SimpleNamespace(id=uuid4(), pagamento_externo_id="123", valor=Decimal("150.00"))
    session.scalar.side_effect = [pedido.id, pedido, contestacao, repasse, pagamento, None]
    session.get.return_value = SimpleNamespace(vendedor_id=uuid4())
    admin = uuid4()
    await service.decidir(
        contestacao.id,
        AdminContestacaoDecisao(status="ACEITA", resolucao="Produto danificado."),
        admin,
    )
    assert contestacao.status == ContestacaoStatus.ACEITA
    assert pedido.status == PedidoStatus.EM_CONTESTACAO
    assert repasse.status == RepasseStatus.BLOQUEADO
    reembolso = session.adicionados[0]
    assert isinstance(reembolso, Reembolso)
    assert reembolso.valor == pagamento.valor
    assert reembolso.contestacao_id == contestacao.id
    assert reembolso.solicitado_por == admin
    service.reembolso_service.processar_preparado.assert_awaited_once()


async def test_falha_do_provedor_preserva_decisao_aceita_e_bloqueio():
    session, service, contestacao, pedido, repasse = preparar()
    pagamento = SimpleNamespace(id=uuid4(), pagamento_externo_id="123", valor=Decimal("150.00"))
    session.scalar.side_effect = [pedido.id, pedido, contestacao, repasse, pagamento, None]
    session.get.return_value = SimpleNamespace(vendedor_id=uuid4())
    service.reembolso_service.processar_preparado.side_effect = AppError(
        status_code=409, detail="Falhou", code="MP_REFUND_FAILED"
    )
    with pytest.raises(AppError):
        await service.decidir(
            contestacao.id,
            AdminContestacaoDecisao(status="ACEITA", resolucao="Dano confirmado."),
            uuid4(),
        )
    assert contestacao.status == ContestacaoStatus.ACEITA
    assert repasse.status == RepasseStatus.BLOQUEADO
    assert pedido.status == PedidoStatus.EM_CONTESTACAO


async def test_repetir_aceite_reutiliza_reembolso_e_chave_sem_alterar_autor_da_decisao():
    session, service, contestacao, pedido, _ = preparar(ContestacaoStatus.ACEITA)
    admin_original = uuid4()
    contestacao.resolvida_por = admin_original
    contestacao.resolucao = "Decisão original."
    reembolso = SimpleNamespace(
        id=uuid4(),
        contestacao_id=contestacao.id,
        status=ReembolsoStatus.FALHOU,
        reembolso_externo_id=None,
        idempotency_key="mesma-chave",
        falhou_em=datetime.now(UTC),
    )
    pagamento = SimpleNamespace(id=uuid4(), pagamento_externo_id="123")
    session.scalar.side_effect = [pedido.id, pedido, contestacao, pagamento, reembolso]
    session.get.return_value = SimpleNamespace(vendedor_id=uuid4())
    await service.decidir(
        contestacao.id,
        AdminContestacaoDecisao(status="ACEITA", resolucao="Nova tentativa."),
        uuid4(),
    )
    assert not session.adicionados
    assert reembolso.idempotency_key == "mesma-chave"
    assert reembolso.status == ReembolsoStatus.PROCESSANDO
    assert contestacao.resolvida_por == admin_original
    assert contestacao.resolucao == "Decisão original."


@pytest.mark.parametrize(
    "status, decisao",
    [(ContestacaoStatus.RECUSADA, "RECUSADA"), (ContestacaoStatus.RESOLVIDA, "ACEITA")],
)
async def test_repetir_decisao_final_e_idempotente(status, decisao):
    session, service, contestacao, pedido, _ = preparar(status)
    session.scalar.side_effect = [pedido.id, pedido, contestacao]
    await service.decidir(
        contestacao.id,
        AdminContestacaoDecisao(status=decisao, resolucao="Decisão repetida."),
        uuid4(),
    )
    service.reembolso_service.processar_preparado.assert_not_awaited()
    assert contestacao.status == status


@pytest.mark.parametrize(
    "status", [ContestacaoStatus.RECUSADA, ContestacaoStatus.CANCELADA, ContestacaoStatus.RESOLVIDA]
)
async def test_decisao_conflitante_nao_altera_contestacao(status):
    session, service, contestacao, pedido, _ = preparar(status)
    session.scalar.side_effect = [pedido.id, pedido, contestacao]
    decisao = "RECUSADA" if status == ContestacaoStatus.RESOLVIDA else "ACEITA"
    with pytest.raises(AppError) as erro:
        await service.decidir(
            contestacao.id,
            AdminContestacaoDecisao(status=decisao, resolucao="Analisada novamente."),
            uuid4(),
        )
    assert erro.value.code == "DISPUTE_ALREADY_DECIDED"
    assert contestacao.status == status


async def test_contestacao_inexistente():
    session, service, *_ = preparar()
    session.scalar.return_value = None
    with pytest.raises(AppError) as erro:
        await service.decidir(
            uuid4(),
            AdminContestacaoDecisao(status="RECUSADA", resolucao="Pedido inválido."),
            uuid4(),
        )
    assert erro.value.status_code == 404


@pytest.mark.parametrize("status", [ContestacaoStatus.ACEITA, ContestacaoStatus.RECUSADA])
async def test_confirmacao_do_reembolso_so_resolve_contestacao_aceita(status):
    session, _, contestacao, *_ = preparar(status)
    session.scalar.return_value = contestacao
    service = ReembolsoService(cast(AsyncSession, session))
    await service.resolver_contestacao(SimpleNamespace(contestacao_id=contestacao.id))
    assert contestacao.status == (
        ContestacaoStatus.RESOLVIDA if status == ContestacaoStatus.ACEITA else status
    )


@pytest.mark.parametrize(
    "dados",
    [
        {},
        {"status": "RESOLVIDA", "resolucao": "Teste"},
        {"status": "ACEITA", "resolucao": "   "},
        {"status": "ACEITA", "resolucao": "Válida", "resolvida_por": str(uuid4())},
    ],
)
def test_validacao_da_decisao(dados):
    with pytest.raises(ValidationError):
        AdminContestacaoDecisao.model_validate(dados)


@pytest.mark.parametrize(
    "status_mp, esperado",
    [
        ("approved", ReembolsoStatus.CONCLUIDO),
        ("pending", ReembolsoStatus.PROCESSANDO),
        ("rejected", ReembolsoStatus.FALHOU),
    ],
)
async def test_processa_resposta_do_provedor_e_so_resolve_apos_confirmacao(
    status_mp, esperado, monkeypatch
):
    session, _, contestacao, pedido, repasse = preparar(ContestacaoStatus.ACEITA)
    pedido.quantidade = 2
    pedido.estoque_liberado_em = None
    anuncio = SimpleNamespace(quantidade=0, status=AnuncioStatus.ESGOTADO, deletado_em=None)
    pagamento = SimpleNamespace(id=uuid4(), status=PagamentoStatus.APROVADO)
    reembolso = SimpleNamespace(
        id=uuid4(),
        pedido_id=pedido.id,
        contestacao_id=contestacao.id,
        status=ReembolsoStatus.SOLICITADO,
        valor=Decimal("150.00"),
        idempotency_key="chave-original",
        reembolso_externo_id=None,
    )
    session.get.return_value = reembolso
    session.scalar.side_effect = (
        [pedido, pagamento, reembolso, anuncio, repasse, contestacao]
        if status_mp == "approved"
        else [pedido, pagamento, reembolso]
    )
    gateway = SimpleNamespace(
        reembolsar_pagamento=AsyncMock(
            return_value=SimpleNamespace(data={"status": status_mp, "id": "refund-123"})
        )
    )
    monkeypatch.setattr(
        ContaPagamentoService,
        "obter_access_token",
        AsyncMock(return_value=(None, "token-de-teste")),
    )
    service = ReembolsoService(cast(AsyncSession, session), gateway=gateway)
    resposta = await service.processar_preparado(
        pedido.id, (uuid4(), pagamento.id, "123", reembolso.id)
    )
    assert resposta.status == esperado
    assert gateway.reembolsar_pagamento.await_args.kwargs["idempotency_key"] == "chave-original"
    if status_mp == "approved":
        assert contestacao.status == ContestacaoStatus.RESOLVIDA
        assert pedido.status == PedidoStatus.REEMBOLSADO
        assert pagamento.status == PagamentoStatus.REEMBOLSADO
        assert repasse.status == RepasseStatus.REEMBOLSADO
        assert anuncio.quantidade == 2
        session.scalar.side_effect = [anuncio, repasse, contestacao]
        await service._concluir(reembolso, pagamento, pedido)
        assert anuncio.quantidade == 2
    else:
        assert contestacao.status == ContestacaoStatus.ACEITA
        assert repasse.status == RepasseStatus.BLOQUEADO
