from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.models.anuncio import Anuncio
from app.models.entrega import Entrega
from app.models.enums import PagamentoStatus, PedidoStatus, ReembolsoStatus, RepasseStatus
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.schemas.pedido import ReembolsoResponse
from app.services.conta_pagamento import ContaPagamentoService
from app.services.pedido import PedidoService


class ReembolsoService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        gateway: MercadoPagoGateway | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.gateway = gateway or MercadoPagoGateway(self.settings.mercado_pago_api_url)

    async def solicitar(self, pedido_id: UUID, comprador_id: UUID) -> ReembolsoResponse:
        preparado = await self._preparar(pedido_id, comprador_id)
        if isinstance(preparado, ReembolsoResponse):
            return preparado
        vendedor_id, pagamento_id, pagamento_externo_id, reembolso_id = preparado
        try:
            _, access_token = await ContaPagamentoService(
                self.session, settings=self.settings, gateway=self.gateway
            ).obter_access_token(vendedor_id)
            reembolso = await self.session.get(Reembolso, reembolso_id)
            if reembolso is None:
                raise self._erro(500, "Reembolso não encontrado.", "REFUND_NOT_FOUND")
            idempotency_key = reembolso.idempotency_key
            await self.session.rollback()
            resposta = await self.gateway.reembolsar_pagamento(
                access_token=access_token,
                pagamento_externo_id=pagamento_externo_id,
                idempotency_key=idempotency_key,
            )
        except MercadoPagoIntegrationError as exc:
            await self._marcar_falha(reembolso_id)
            raise self._erro(
                409,
                "O Mercado Pago não concluiu o reembolso. Verifique o saldo do vendedor.",
                "MP_REFUND_FAILED",
            ) from exc
        except AppError:
            await self._marcar_falha(reembolso_id)
            raise

        status_mp = str(resposta.data.get("status") or "")
        externo_id = str(resposta.data.get("id") or "") or None
        async with self.session.begin():
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            pagamento = await self.session.scalar(
                select(Pagamento).where(Pagamento.id == pagamento_id).with_for_update()
            )
            reembolso = await self.session.scalar(
                select(Reembolso)
                .where(Reembolso.id == reembolso_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if reembolso is None or pagamento is None or pedido is None:
                raise self._erro(500, "Dados do reembolso não encontrados.", "REFUND_DATA_MISSING")
            if reembolso.status == ReembolsoStatus.CONCLUIDO:
                return self._resposta(reembolso)
            reembolso.reembolso_externo_id = externo_id
            if status_mp in {"approved", "refunded"}:
                await self._concluir(reembolso, pagamento, pedido)
            elif status_mp in {"rejected", "cancelled", "failed"}:
                reembolso.status = ReembolsoStatus.FALHOU
                reembolso.falhou_em = datetime.now(UTC)
            else:
                reembolso.status = ReembolsoStatus.PROCESSANDO
            await self.session.flush()
            resposta_local = self._resposta(reembolso)
        return resposta_local

    async def _preparar(
        self, pedido_id: UUID, comprador_id: UUID
    ) -> tuple[UUID, UUID, str, UUID] | ReembolsoResponse:
        agora = datetime.now(UTC)
        async with self.session.begin():
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id, Pedido.comprador_id == comprador_id)
                .with_for_update()
            )
            if pedido is None:
                raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")
            existente = await self.session.scalar(
                select(Reembolso).where(Reembolso.pedido_id == pedido.id)
            )
            if existente is not None and (
                existente.status == ReembolsoStatus.CONCLUIDO
                or (
                    existente.status == ReembolsoStatus.PROCESSANDO
                    and existente.reembolso_externo_id is not None
                )
            ):
                return self._resposta(existente)
            if pedido.status not in {
                PedidoStatus.PAGAMENTO_APROVADO,
                PedidoStatus.PREPARANDO_ENTREGA,
                PedidoStatus.CANCELADO,
            }:
                raise self._erro(409, "Este pedido não pode ser reembolsado.", "REFUND_NOT_ALLOWED")
            entrega = await self.session.scalar(
                select(Entrega).where(Entrega.pedido_id == pedido.id)
            )
            if entrega is not None and entrega.confirmado_em is not None:
                raise self._erro(
                    409,
                    "Após a confirmação da entrega, abra uma contestação.",
                    "REFUND_DELIVERY_CONFIRMED",
                )
            pagamento = await self.session.scalar(
                select(Pagamento).where(
                    Pagamento.pedido_id == pedido.id,
                    Pagamento.status == PagamentoStatus.APROVADO,
                )
            )
            if pagamento is None or not pagamento.pagamento_externo_id:
                raise self._erro(
                    409,
                    "Pagamento aprovado não encontrado.",
                    "APPROVED_PAYMENT_NOT_FOUND",
                )
            anuncio = await self.session.get(Anuncio, pedido.anuncio_id)
            if anuncio is None:
                raise self._erro(500, "Anúncio do pedido não encontrado.", "ORDER_AD_NOT_FOUND")
            reembolso = await self.session.scalar(
                select(Reembolso).where(Reembolso.pagamento_id == pagamento.id).with_for_update()
            )
            if reembolso is None:
                reembolso = Reembolso(
                    pedido_id=pedido.id,
                    pagamento_id=pagamento.id,
                    contestacao_id=None,
                    reembolso_externo_id=None,
                    idempotency_key=str(uuid4()),
                    valor=pagamento.valor,
                    motivo="Cancelamento solicitado pelo comprador antes da entrega",
                    status=ReembolsoStatus.SOLICITADO,
                    solicitado_por=comprador_id,
                    processado_em=None,
                    falhou_em=None,
                )
                self.session.add(reembolso)
                await self.session.flush()
            elif reembolso.status == ReembolsoStatus.CONCLUIDO:
                return self._resposta(reembolso)
            else:
                reembolso.status = ReembolsoStatus.PROCESSANDO
                reembolso.falhou_em = None
            pedido.status = PedidoStatus.CANCELADO
            pedido.cancelado_em = agora
            return (
                anuncio.vendedor_id,
                pagamento.id,
                pagamento.pagamento_externo_id,
                reembolso.id,
            )

    async def _concluir(self, reembolso: Reembolso, pagamento: Pagamento, pedido: Pedido) -> None:
        agora = datetime.now(UTC)
        anuncio = await self.session.scalar(
            select(Anuncio).where(Anuncio.id == pedido.anuncio_id).with_for_update()
        )
        if anuncio is None:
            raise self._erro(500, "Anúncio do pedido não encontrado.", "ORDER_AD_NOT_FOUND")
        reembolso.status = ReembolsoStatus.CONCLUIDO
        reembolso.processado_em = agora
        pagamento.status = PagamentoStatus.REEMBOLSADO
        pedido.status = PedidoStatus.REEMBOLSADO
        PedidoService._liberar_estoque(pedido, anuncio, agora)
        repasse = await self.session.scalar(
            select(Repasse).where(Repasse.pagamento_id == pagamento.id)
        )
        if repasse:
            repasse.status = RepasseStatus.REEMBOLSADO

    async def _marcar_falha(self, reembolso_id: UUID) -> None:
        if self.session.in_transaction():
            await self.session.rollback()
        async with self.session.begin():
            reembolso = await self.session.scalar(
                select(Reembolso)
                .where(Reembolso.id == reembolso_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if reembolso and reembolso.status != ReembolsoStatus.CONCLUIDO:
                reembolso.status = ReembolsoStatus.FALHOU
                reembolso.falhou_em = datetime.now(UTC)

    @staticmethod
    def _resposta(reembolso: Reembolso) -> ReembolsoResponse:
        return ReembolsoResponse(
            id=reembolso.id,
            pedido_id=reembolso.pedido_id,
            status=reembolso.status,
            valor=reembolso.valor,
            reembolso_externo_id=reembolso.reembolso_externo_id,
        )

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)
