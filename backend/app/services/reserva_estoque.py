from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anuncio import Anuncio
from app.models.enums import PagamentoStatus, PedidoStatus
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.services.pedido import PedidoService


class ReservaEstoqueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def liberar_expiradas(self, *, limite: int = 100) -> int:
        agora = datetime.now(UTC)
        processados = 0
        async with self.session.begin():
            pedidos = list(
                await self.session.scalars(
                    select(Pedido)
                    .where(
                        Pedido.status == PedidoStatus.AGUARDANDO_PAGAMENTO,
                        Pedido.estoque_liberado_em.is_(None),
                        Pedido.reserva_expira_em <= agora,
                    )
                    .order_by(Pedido.reserva_expira_em)
                    .limit(limite)
                    .with_for_update(skip_locked=True)
                )
            )
            for pedido in pedidos:
                anuncio = await self.session.scalar(
                    select(Anuncio).where(Anuncio.id == pedido.anuncio_id).with_for_update()
                )
                if anuncio is None:
                    continue
                PedidoService._liberar_estoque(pedido, anuncio, agora)
                pedido.status = PedidoStatus.CANCELADO
                pedido.cancelado_em = agora
                pagamentos = await self.session.scalars(
                    select(Pagamento).where(Pagamento.pedido_id == pedido.id)
                )
                for pagamento in pagamentos:
                    if pagamento.status != PagamentoStatus.APROVADO:
                        pagamento.status = PagamentoStatus.CANCELADO
                        pagamento.cancelado_em = agora
                processados += 1
        return processados
