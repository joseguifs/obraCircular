from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.anuncio import Anuncio
from app.models.contestacao import Contestacao
from app.models.entrega import Entrega
from app.models.enums import (
    ContestacaoStatus,
    PagamentoStatus,
    PedidoStatus,
    ReembolsoStatus,
    RepasseStatus,
)
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.repositories.contestacao import ContestacaoRepository
from app.schemas.admin import (
    AdminContestacaoDecisao,
    AdminContestacaoFilters,
    AdminContestacaoListResponse,
    AdminContestacaoResponse,
)
from app.services.reembolso import ReembolsoService


class ContestacaoService:
    def __init__(
        self, session: AsyncSession, reembolso_service: ReembolsoService | None = None
    ) -> None:
        self.session = session
        self.repository = ContestacaoRepository(session)
        self.reembolso_service = reembolso_service or ReembolsoService(session)

    async def listar(self, filtros: AdminContestacaoFilters) -> AdminContestacaoListResponse:
        itens, total = await self.repository.listar(filtros)
        return AdminContestacaoListResponse(
            items=itens, total=total, offset=filtros.offset, limit=filtros.limit
        )

    async def decidir(
        self, contestacao_id: UUID, dados: AdminContestacaoDecisao, administrador_id: UUID
    ) -> AdminContestacaoResponse:
        preparado = None
        async with self.session.begin():
            pedido_id = await self.session.scalar(
                select(Contestacao.pedido_id).where(Contestacao.id == contestacao_id)
            )
            if pedido_id is None:
                raise AppError(
                    status_code=404, detail="Contestação não encontrada.", code="DISPUTE_NOT_FOUND"
                )
            # Pedido primeiro, como nos fluxos de reembolso e confirmação do provedor.
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            contestacao = await self.session.scalar(
                select(Contestacao)
                .where(Contestacao.id == contestacao_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if contestacao is None or pedido is None:
                raise AppError(
                    status_code=404, detail="Contestação não encontrada.", code="DISPUTE_NOT_FOUND"
                )
            repetida = contestacao.status == dados.status or (
                contestacao.status == ContestacaoStatus.RESOLVIDA and dados.status == "ACEITA"
            )
            if not repetida and contestacao.status not in {
                ContestacaoStatus.ABERTA,
                ContestacaoStatus.EM_ANALISE,
                ContestacaoStatus.AGUARDANDO_VENDEDOR,
            }:
                raise AppError(
                    status_code=409,
                    detail="Esta contestação já foi analisada.",
                    code="DISPUTE_ALREADY_DECIDED",
                )

            if not repetida:
                if pedido.status != PedidoStatus.EM_CONTESTACAO:
                    raise AppError(
                        status_code=409,
                        detail="O pedido não está em contestação.",
                        code="DISPUTE_ORDER_STATUS",
                    )
                repasse = await self.session.scalar(
                    select(Repasse).where(Repasse.pedido_id == pedido.id).with_for_update()
                )
                if repasse is None or repasse.status != RepasseStatus.BLOQUEADO:
                    raise AppError(
                        status_code=409,
                        detail="O repasse não está bloqueado.",
                        code="DISPUTE_TRANSFER_STATUS",
                    )
                agora = datetime.now(UTC)
                if dados.status == "RECUSADA":
                    entrega = await self.session.scalar(
                        select(Entrega).where(Entrega.pedido_id == pedido.id)
                    )
                    if entrega is None or entrega.prazo_contestacao_em is None:
                        raise AppError(
                            status_code=409,
                            detail="Prazo de contestação não encontrado.",
                            code="DISPUTE_DEADLINE_MISSING",
                        )
                    pedido.status = PedidoStatus.ENTREGUE
                    repasse.status = (
                        RepasseStatus.EM_PERIODO_CONTESTACAO
                        if agora <= entrega.prazo_contestacao_em
                        else RepasseStatus.PAGO
                    )
                contestacao.status = ContestacaoStatus(dados.status)
                contestacao.resolucao = dados.resolucao
                contestacao.resolvida_por = administrador_id
                contestacao.resolvida_em = agora

            if dados.status == "ACEITA" and contestacao.status != ContestacaoStatus.RESOLVIDA:
                preparado = await self._preparar_reembolso(contestacao, pedido, administrador_id)
            await self.session.flush()

        # A decisão é persistida antes da chamada externa. Uma falha mantém ACEITA e
        # permite repetir a operação com o mesmo reembolso e chave de idempotência.
        if preparado is not None:
            await self.reembolso_service.processar_preparado(pedido_id, preparado)
        return await self.repository.buscar_resposta(contestacao_id)

    async def _preparar_reembolso(
        self, contestacao: Contestacao, pedido: Pedido, administrador_id: UUID
    ) -> tuple[UUID, UUID, str, UUID] | None:
        pagamento = await self.session.scalar(
            select(Pagamento)
            .where(Pagamento.pedido_id == pedido.id, Pagamento.status == PagamentoStatus.APROVADO)
            .with_for_update()
        )
        if pagamento is None or not pagamento.pagamento_externo_id:
            raise AppError(
                status_code=409,
                detail="Pagamento aprovado não encontrado.",
                code="APPROVED_PAYMENT_NOT_FOUND",
            )
        reembolso = await self.session.scalar(
            select(Reembolso).where(Reembolso.pagamento_id == pagamento.id).with_for_update()
        )
        if reembolso is not None and reembolso.contestacao_id != contestacao.id:
            raise AppError(
                status_code=409,
                detail="O pagamento já possui outro reembolso.",
                code="REFUND_ALREADY_EXISTS",
            )
        if reembolso is not None and (
            reembolso.status == ReembolsoStatus.CONCLUIDO
            or (
                reembolso.status == ReembolsoStatus.PROCESSANDO
                and reembolso.reembolso_externo_id is not None
            )
        ):
            return None
        anuncio = await self.session.get(Anuncio, pedido.anuncio_id)
        if anuncio is None:
            raise AppError(
                status_code=409,
                detail="Anúncio do pedido não encontrado.",
                code="ORDER_AD_NOT_FOUND",
            )
        if reembolso is None:
            reembolso = Reembolso(
                pedido_id=pedido.id,
                pagamento_id=pagamento.id,
                contestacao_id=contestacao.id,
                valor=pagamento.valor,
                motivo=f"Contestação aceita: {contestacao.id}",
                solicitado_por=administrador_id,
                idempotency_key=str(uuid4()),
                status=ReembolsoStatus.SOLICITADO,
            )
            self.session.add(reembolso)
            await self.session.flush()
        else:
            reembolso.status = ReembolsoStatus.PROCESSANDO
            reembolso.falhou_em = None
        return anuncio.vendedor_id, pagamento.id, pagamento.pagamento_externo_id, reembolso.id
