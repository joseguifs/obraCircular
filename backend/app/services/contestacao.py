from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.contestacao import Contestacao
from app.models.entrega import Entrega
from app.models.enums import ContestacaoStatus, EntregaStatus, PedidoStatus, RepasseStatus
from app.models.pedido import Pedido
from app.models.repasse import Repasse
from app.schemas.contestacao import (
    ContestacaoCreate,
    ContestacaoListResponse,
    ContestacaoResponse,
)

STATUS_ATIVOS = (
    ContestacaoStatus.ABERTA,
    ContestacaoStatus.EM_ANALISE,
    ContestacaoStatus.AGUARDANDO_VENDEDOR,
    ContestacaoStatus.ACEITA,
)


class ContestacaoService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)
