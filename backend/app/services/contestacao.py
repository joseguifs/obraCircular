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
    EntregaStatus,
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
from app.schemas.contestacao import (
    ContestacaoCreate,
    ContestacaoListResponse,
    ContestacaoResponse,
)
from app.services.reembolso import ReembolsoService

# Contestações ainda aguardando decisão do administrador.
STATUS_PENDENTES = frozenset(
    {
        ContestacaoStatus.ABERTA,
        ContestacaoStatus.EM_ANALISE,
        ContestacaoStatus.AGUARDANDO_VENDEDOR,
    }
)
# Contestações que impedem a abertura de outra no mesmo pedido.
STATUS_ATIVOS = STATUS_PENDENTES | {ContestacaoStatus.ACEITA}


class ContestacaoService:
    def __init__(
        self, session: AsyncSession, reembolso_service: ReembolsoService | None = None
    ) -> None:
        self.session = session
        self.repository = ContestacaoRepository(session)
        self.reembolso_service = reembolso_service or ReembolsoService(session)

    async def abrir(
        self, pedido_id: UUID, dados: ContestacaoCreate, comprador_id: UUID
    ) -> ContestacaoResponse:
        async with self.session.begin():
            # Serializa aberturas e transições do pedido, inclusive as de webhooks.
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id, Pedido.comprador_id == comprador_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if pedido is None:
                raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")

            ativa = await self.session.scalar(
                select(Contestacao.id).where(
                    Contestacao.pedido_id == pedido.id, Contestacao.status.in_(STATUS_ATIVOS)
                )
            )
            if ativa is not None:
                raise self._erro(
                    409,
                    "Este pedido já possui uma contestação ativa.",
                    "DISPUTE_ALREADY_ACTIVE",
                )
            if pedido.status != PedidoStatus.ENTREGUE:
                raise self._erro(
                    409,
                    "Somente pedidos entregues podem ser contestados.",
                    "DISPUTE_ORDER_NOT_DELIVERED",
                )

            entrega = await self.session.scalar(
                select(Entrega)
                .where(Entrega.pedido_id == pedido.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                entrega is None
                or entrega.status != EntregaStatus.ENTREGUE
                or entrega.confirmado_em is None
                or entrega.prazo_contestacao_em is None
            ):
                raise self._erro(
                    409,
                    "A entrega precisa estar confirmada e ter um prazo de contestação.",
                    "DISPUTE_DELIVERY_NOT_CONFIRMED",
                )

            repasse = await self.session.scalar(
                select(Repasse)
                .where(Repasse.pedido_id == pedido.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if repasse is None:
                raise self._erro(
                    409, "Repasse do pedido não encontrado.", "DISPUTE_PAYOUT_NOT_FOUND"
                )
            if repasse.status in {
                RepasseStatus.PROCESSANDO,
                RepasseStatus.PAGO,
                RepasseStatus.CANCELADO,
                RepasseStatus.REEMBOLSADO,
            }:
                raise self._erro(
                    409,
                    "O estado do repasse não permite abrir uma contestação.",
                    "DISPUTE_PAYOUT_NOT_ALLOWED",
                )

            # Verifica o prazo após adquirir os bloqueios, que podem ter aguardado.
            agora = datetime.now(UTC)
            if agora > entrega.prazo_contestacao_em:
                raise self._erro(
                    409,
                    "O prazo para abrir uma contestação terminou.",
                    "DISPUTE_DEADLINE_EXPIRED",
                )

            contestacao = Contestacao(
                pedido_id=pedido.id,
                comprador_id=comprador_id,
                motivo=dados.motivo,
                descricao=dados.descricao,
                status=ContestacaoStatus.ABERTA,
            )
            self.session.add(contestacao)
            pedido.status = PedidoStatus.EM_CONTESTACAO
            # Impede a liberação no repasse posterior; no split legado, é apenas operacional.
            repasse.status = RepasseStatus.BLOQUEADO
            repasse.bloqueado_em = agora
            await self.session.flush()
            return ContestacaoResponse.model_validate(contestacao)

    async def listar(self, pedido_id: UUID, comprador_id: UUID) -> ContestacaoListResponse:
        pedido = await self.session.scalar(
            select(Pedido.id).where(Pedido.id == pedido_id, Pedido.comprador_id == comprador_id)
        )
        if pedido is None:
            raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")
        contestacoes = await self.session.scalars(
            select(Contestacao)
            .where(Contestacao.pedido_id == pedido_id)
            .order_by(Contestacao.criado_em.desc(), Contestacao.id.desc())
        )
        items = [ContestacaoResponse.model_validate(item) for item in contestacoes]
        return ContestacaoListResponse(items=items, total=len(items))

    async def listar_admin(self, filtros: AdminContestacaoFilters) -> AdminContestacaoListResponse:
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
                raise self._erro(404, "Contestação não encontrada.", "DISPUTE_NOT_FOUND")
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
                raise self._erro(404, "Contestação não encontrada.", "DISPUTE_NOT_FOUND")
            repetida = contestacao.status == dados.status or (
                contestacao.status == ContestacaoStatus.RESOLVIDA and dados.status == "ACEITA"
            )
            if not repetida and contestacao.status not in STATUS_PENDENTES:
                raise self._erro(
                    409, "Esta contestação já foi analisada.", "DISPUTE_ALREADY_DECIDED"
                )

            if not repetida:
                if pedido.status != PedidoStatus.EM_CONTESTACAO:
                    raise self._erro(
                        409, "O pedido não está em contestação.", "DISPUTE_ORDER_STATUS"
                    )
                repasse = await self.session.scalar(
                    select(Repasse).where(Repasse.pedido_id == pedido.id).with_for_update()
                )
                if repasse is None or repasse.status != RepasseStatus.BLOQUEADO:
                    raise self._erro(
                        409, "O repasse não está bloqueado.", "DISPUTE_TRANSFER_STATUS"
                    )
                agora = datetime.now(UTC)
                if dados.status == "RECUSADA":
                    entrega = await self.session.scalar(
                        select(Entrega).where(Entrega.pedido_id == pedido.id)
                    )
                    if entrega is None or entrega.prazo_contestacao_em is None:
                        raise self._erro(
                            409, "Prazo de contestação não encontrado.", "DISPUTE_DEADLINE_MISSING"
                        )
                    pedido.status = PedidoStatus.ENTREGUE
                    # No repasse posterior a transferência ainda não ocorreu: o repasse
                    # volta ao período de contestação e `atualizar_estados` decide a
                    # liberação. No split legado, PAGO é apenas o registro contábil.
                    repasse.status = (
                        RepasseStatus.EM_PERIODO_CONTESTACAO
                        if pedido.repasse_posterior or agora <= entrega.prazo_contestacao_em
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
            raise self._erro(
                409, "Pagamento aprovado não encontrado.", "APPROVED_PAYMENT_NOT_FOUND"
            )
        reembolso = await self.session.scalar(
            select(Reembolso).where(Reembolso.pagamento_id == pagamento.id).with_for_update()
        )
        if reembolso is not None and reembolso.contestacao_id != contestacao.id:
            raise self._erro(409, "O pagamento já possui outro reembolso.", "REFUND_ALREADY_EXISTS")
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
            raise self._erro(409, "Anúncio do pedido não encontrado.", "ORDER_AD_NOT_FOUND")
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

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)
