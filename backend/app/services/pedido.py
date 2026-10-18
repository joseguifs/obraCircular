import logging
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.integrations.mercado_pago import MercadoPagoGateway, MercadoPagoIntegrationError
from app.models.anuncio import Anuncio
from app.models.endereco import Endereco
from app.models.enums import (
    AnuncioStatus,
    PagamentoStatus,
    PedidoStatus,
)
from app.models.pagamento import Pagamento
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.schemas.pedido import (
    CheckoutCreate,
    CheckoutResponse,
    PagamentoResumo,
    PedidoListResponse,
    PedidoResponse,
    ReembolsoResponse,
)
from app.services.conta_pagamento import ContaPagamentoService

CENTAVOS = Decimal("0.01")
logger = logging.getLogger(__name__)


class PedidoService:
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

    async def criar_checkout(
        self,
        dados: CheckoutCreate,
        *,
        comprador_id: UUID,
        comprador_email: str,
        comprador_nome: str = "",
        comprador_criado_em: datetime | None = None,
    ) -> CheckoutResponse:
        """Cria uma Preference em /checkout/preferences e retorna seu init_point."""
        vendedor_id = await self._obter_vendedor(dados.anuncio_id)
        conta, access_token = await ContaPagamentoService(
            self.session, settings=self.settings, gateway=self.gateway
        ).obter_access_token(vendedor_id)

        agora = datetime.now(UTC)
        checkout_ativo = await self._retomar_checkout_ativo(
            dados,
            comprador_id=comprador_id,
            access_token=access_token,
            agora=agora,
        )
        if checkout_ativo is not None:
            return checkout_ativo

        expira_em = agora + timedelta(minutes=self.settings.stock_reservation_minutes)
        async with self.session.begin():
            expirados = list(
                await self.session.scalars(
                    select(Pedido)
                    .where(
                        Pedido.anuncio_id == dados.anuncio_id,
                        Pedido.status == PedidoStatus.AGUARDANDO_PAGAMENTO,
                        Pedido.estoque_liberado_em.is_(None),
                        Pedido.reserva_expira_em <= agora,
                    )
                    .with_for_update()
                )
            )
            anuncio = await self.session.scalar(
                select(Anuncio).where(Anuncio.id == dados.anuncio_id).with_for_update()
            )
            if anuncio is None or anuncio.deletado_em is not None:
                raise self._erro(404, "Anúncio não encontrado.", "AD_NOT_FOUND")
            self._liberar_reservas_expiradas(expirados, anuncio, agora)
            for pedido_expirado in expirados:
                pagamentos_expirados = await self.session.scalars(
                    select(Pagamento).where(Pagamento.pedido_id == pedido_expirado.id)
                )
                for pagamento_expirado in pagamentos_expirados:
                    if pagamento_expirado.status != PagamentoStatus.APROVADO:
                        pagamento_expirado.status = PagamentoStatus.CANCELADO
                        pagamento_expirado.cancelado_em = agora
            self._validar_compra(anuncio, comprador_id, dados.quantidade)
            existente = await self.session.scalar(
                select(Pedido).where(
                    Pedido.comprador_id == comprador_id,
                    Pedido.anuncio_id == anuncio.id,
                    Pedido.status == PedidoStatus.AGUARDANDO_PAGAMENTO,
                    Pedido.estoque_liberado_em.is_(None),
                    Pedido.reserva_expira_em > agora,
                )
            )
            if existente is not None:
                raise self._erro(
                    409,
                    "Já existe um checkout ativo para este anúncio.",
                    "CHECKOUT_ALREADY_ACTIVE",
                )

            snapshot = await self._snapshot_endereco(dados.endereco_entrega_id, comprador_id)
            valor_total = (anuncio.preco * dados.quantidade).quantize(
                CENTAVOS, rounding=ROUND_HALF_UP
            )
            anuncio.quantidade -= dados.quantidade
            if anuncio.quantidade == 0:
                anuncio.status = AnuncioStatus.ESGOTADO
            pedido = Pedido(
                comprador_id=comprador_id,
                anuncio_id=anuncio.id,
                endereco_entrega_id=dados.endereco_entrega_id,
                endereco_entrega_snapshot=snapshot,
                modalidade_entrega=dados.modalidade_entrega,
                quantidade=dados.quantidade,
                preco_unitario=anuncio.preco,
                valor_total=valor_total,
                status=PedidoStatus.AGUARDANDO_PAGAMENTO,
                estoque_reservado_em=agora,
                reserva_expira_em=expira_em,
                estoque_liberado_em=None,
            )
            self.session.add(pedido)
            await self.session.flush()
            pagamento = Pagamento(
                pedido_id=pedido.id,
                pagamento_externo_id=None,
                preferencia_externa_id=None,
                ordem_externa_id=None,
                idempotency_key=str(uuid4()),
                metodo=None,
                valor=valor_total,
                parcelas=None,
                status=PagamentoStatus.CRIADO,
                motivo_recusa=None,
                status_detalhe=None,
            )
            self.session.add(pagamento)
            await self.session.flush()
            pedido_id = pedido.id
            pagamento_id = pagamento.id
            titulo = anuncio.titulo
            descricao = anuncio.descricao

        taxa_marketplace = self.calcular_taxa_marketplace(
            valor_total, self.settings.marketplace_fee_percent
        )
        try:
            payload = self._payload_preferencia(
                pedido_id=pedido_id,
                pagamento_id=pagamento_id,
                anuncio_id=dados.anuncio_id,
                titulo=titulo,
                descricao=descricao,
                quantidade=dados.quantidade,
                preco_unitario=valor_total / dados.quantidade,
                taxa_marketplace=taxa_marketplace,
                comprador_email=comprador_email,
                comprador_nome=comprador_nome,
                comprador_criado_em=comprador_criado_em,
                expira_em=expira_em,
            )
            resposta = await self.gateway.criar_preferencia(
                access_token=access_token,
                payload=payload,
            )
            preferencia_id = str(resposta.data["id"])
            init_point = str(resposta.data.get("init_point"))
            if not init_point or init_point == "None":
                raise KeyError("init_point")
        except (MercadoPagoIntegrationError, KeyError, AppError) as exc:
            if isinstance(exc, MercadoPagoIntegrationError):
                payload_erro = exc.payload if isinstance(exc.payload, dict) else {}
                logger.warning(
                    "Falha ao criar Preference no Mercado Pago: "
                    "status=%s code=%s message=%s details=%s",
                    exc.status_code,
                    payload_erro.get("error") or payload_erro.get("code"),
                    payload_erro.get("message") or payload_erro.get("error_description"),
                    payload_erro.get("details"),
                )
            else:
                logger.warning(
                    "Resposta invalida ao criar Preference no Mercado Pago: tipo=%s campo=%s",
                    type(exc).__name__,
                    str(exc),
                )
            await self._cancelar_e_liberar(pedido_id, pagamento_id)
            if isinstance(exc, MercadoPagoIntegrationError) and exc.status_code == 401:
                raise self._erro(
                    409,
                    "A autorização Mercado Pago do vendedor está inválida. "
                    "O vendedor precisa reconectar a conta.",
                    "MP_SELLER_RECONNECT_REQUIRED",
                ) from exc
            raise self._erro(
                502,
                "Não foi possível iniciar o checkout no Mercado Pago.",
                "MP_CHECKOUT_CREATE_FAILED",
            ) from exc

        async with self.session.begin():
            pagamento_atualizado = await self.session.get(Pagamento, pagamento_id)
            if pagamento_atualizado is None:
                raise self._erro(500, "Tentativa de pagamento não encontrada.", "PAYMENT_NOT_FOUND")
            pagamento_atualizado.preferencia_externa_id = preferencia_id
            pagamento_atualizado.status = PagamentoStatus.PENDENTE
            await self.session.flush()

        return CheckoutResponse(
            pedido_id=pedido_id,
            pagamento_id=pagamento_id,
            preferencia_externa_id=preferencia_id,
            init_point=init_point,
            reserva_expira_em=expira_em,
            valor_total=valor_total,
            taxa_marketplace=taxa_marketplace,
        )

    async def buscar(self, pedido_id: UUID, comprador_id: UUID) -> PedidoResponse:
        pedido = await self.session.scalar(
            select(Pedido).where(Pedido.id == pedido_id, Pedido.comprador_id == comprador_id)
        )
        if pedido is None:
            raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")
        pagamento = await self.session.scalar(
            select(Pagamento)
            .where(Pagamento.pedido_id == pedido.id)
            .order_by(Pagamento.criado_em.desc())
        )
        reembolso = await self.session.scalar(
            select(Reembolso).where(Reembolso.pedido_id == pedido.id)
        )
        return self._resposta(pedido, pagamento, reembolso)

    async def listar(self, comprador_id: UUID) -> PedidoListResponse:
        pedidos = list(
            await self.session.scalars(
                select(Pedido)
                .where(Pedido.comprador_id == comprador_id)
                .order_by(Pedido.criado_em.desc())
            )
        )
        items: list[PedidoResponse] = []
        for pedido in pedidos:
            pagamento = await self.session.scalar(
                select(Pagamento)
                .where(Pagamento.pedido_id == pedido.id)
                .order_by(Pagamento.criado_em.desc())
            )
            reembolso = await self.session.scalar(
                select(Reembolso).where(Reembolso.pedido_id == pedido.id)
            )
            items.append(self._resposta(pedido, pagamento, reembolso))
        return PedidoListResponse(items=items, total=len(items))

    async def cancelar(self, pedido_id: UUID, comprador_id: UUID) -> None:
        agora = datetime.now(UTC)
        async with self.session.begin():
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id, Pedido.comprador_id == comprador_id)
                .with_for_update()
            )
            if pedido is None:
                raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")
            if pedido.status != PedidoStatus.AGUARDANDO_PAGAMENTO:
                raise self._erro(
                    409,
                    "Este pedido não pode mais ser cancelado sem reembolso.",
                    "ORDER_REFUND_REQUIRED",
                )
            anuncio = await self.session.scalar(
                select(Anuncio).where(Anuncio.id == pedido.anuncio_id).with_for_update()
            )
            if anuncio is None:
                raise self._erro(500, "Anúncio do pedido não encontrado.", "ORDER_AD_NOT_FOUND")
            self._liberar_estoque(pedido, anuncio, agora)
            pedido.status = PedidoStatus.CANCELADO
            pedido.cancelado_em = agora
            pagamentos = await self.session.scalars(
                select(Pagamento).where(Pagamento.pedido_id == pedido.id)
            )
            for pagamento in pagamentos:
                if pagamento.status not in {PagamentoStatus.APROVADO, PagamentoStatus.REEMBOLSADO}:
                    pagamento.status = PagamentoStatus.CANCELADO
                    pagamento.cancelado_em = agora
            await self.session.flush()

    async def _obter_vendedor(self, anuncio_id: UUID) -> UUID:
        anuncio = await self.session.get(Anuncio, anuncio_id)
        if anuncio is None or anuncio.deletado_em is not None:
            raise self._erro(404, "Anúncio não encontrado.", "AD_NOT_FOUND")
        vendedor_id = anuncio.vendedor_id
        await self.session.rollback()
        return vendedor_id

    async def _retomar_checkout_ativo(
        self,
        dados: CheckoutCreate,
        *,
        comprador_id: UUID,
        access_token: str,
        agora: datetime,
    ) -> CheckoutResponse | None:
        pedido = await self.session.scalar(
            select(Pedido)
            .where(
                Pedido.comprador_id == comprador_id,
                Pedido.anuncio_id == dados.anuncio_id,
                Pedido.status == PedidoStatus.AGUARDANDO_PAGAMENTO,
                Pedido.estoque_liberado_em.is_(None),
                Pedido.reserva_expira_em > agora,
            )
            .order_by(Pedido.criado_em.desc())
        )
        if pedido is None:
            await self.session.rollback()
            return None
        if (
            pedido.quantidade != dados.quantidade
            or pedido.modalidade_entrega != dados.modalidade_entrega
            or pedido.endereco_entrega_id != dados.endereco_entrega_id
        ):
            await self.session.rollback()
            raise self._erro(
                409,
                "Existe um checkout ativo com quantidade ou entrega diferente. "
                "Aguarde a reserva expirar ou cancele o pedido atual.",
                "CHECKOUT_ACTIVE_DIFFERENT_CONFIGURATION",
            )
        pagamento = await self.session.scalar(
            select(Pagamento)
            .where(
                Pagamento.pedido_id == pedido.id,
                Pagamento.preferencia_externa_id.is_not(None),
                Pagamento.status.in_(
                    {
                        PagamentoStatus.CRIADO,
                        PagamentoStatus.PENDENTE,
                        PagamentoStatus.EM_PROCESSAMENTO,
                        PagamentoStatus.RECUSADO,
                    }
                ),
            )
            .order_by(Pagamento.criado_em.desc())
        )
        if pagamento is None or pagamento.preferencia_externa_id is None:
            await self.session.rollback()
            return None

        pedido_id = pedido.id
        pagamento_id = pagamento.id
        preferencia_id = pagamento.preferencia_externa_id
        reserva_expira_em = pedido.reserva_expira_em
        valor_total = pedido.valor_total
        await self.session.rollback()

        if reserva_expira_em is None:
            return None
        try:
            resposta = await self.gateway.obter_preferencia(
                access_token=access_token,
                preferencia_id=preferencia_id,
            )
            init_point = str(resposta.data.get("init_point"))
            if not init_point or init_point == "None":
                raise KeyError("init_point")
        except (MercadoPagoIntegrationError, KeyError) as exc:
            raise self._erro(
                502,
                "Não foi possível retomar o checkout ativo no Mercado Pago.",
                "MP_CHECKOUT_RESUME_FAILED",
            ) from exc

        return CheckoutResponse(
            pedido_id=pedido_id,
            pagamento_id=pagamento_id,
            preferencia_externa_id=preferencia_id,
            init_point=init_point,
            reserva_expira_em=reserva_expira_em,
            valor_total=valor_total,
            taxa_marketplace=self.calcular_taxa_marketplace(
                valor_total, self.settings.marketplace_fee_percent
            ),
        )

    @staticmethod
    def _liberar_reservas_expiradas(
        expirados: list[Pedido], anuncio: Anuncio, agora: datetime
    ) -> None:
        for pedido in expirados:
            PedidoService._liberar_estoque(pedido, anuncio, agora)
            pedido.status = PedidoStatus.CANCELADO
            pedido.cancelado_em = agora

    async def _snapshot_endereco(
        self, endereco_id: UUID | None, comprador_id: UUID
    ) -> dict[str, Any] | None:
        if endereco_id is None:
            return None
        endereco = await self.session.scalar(
            select(Endereco).where(
                Endereco.id == endereco_id,
                Endereco.usuario_id == comprador_id,
                Endereco.deletado_em.is_(None),
            )
        )
        if endereco is None:
            raise self._erro(
                400,
                "O endereço de entrega é inválido ou não pertence ao comprador.",
                "DELIVERY_ADDRESS_INVALID",
            )
        return {
            "cep": endereco.cep,
            "logradouro": endereco.logradouro,
            "numero": endereco.numero,
            "complemento": endereco.complemento,
            "bairro": endereco.bairro,
            "cidade": endereco.cidade,
            "estado": endereco.estado,
        }

    def _payload_preferencia(
        self,
        *,
        pedido_id: UUID,
        pagamento_id: UUID,
        anuncio_id: UUID,
        titulo: str,
        descricao: str,
        quantidade: int,
        preco_unitario: Decimal,
        taxa_marketplace: Decimal,
        comprador_email: str,
        comprador_nome: str,
        comprador_criado_em: datetime | None,
        expira_em: datetime,
    ) -> dict[str, Any]:
        if not self.settings.mp_public_base_url or not self.settings.mp_webhook_url:
            raise self._erro(
                503,
                "As URLs públicas do Mercado Pago não foram configuradas.",
                "MP_PUBLIC_URLS_NOT_CONFIGURED",
            )
        retorno = (
            f"{self.settings.mp_public_base_url.rstrip('/')}"
            f"{self.settings.api_v1_prefix}/integrations/mercado-pago/checkout/return"
        )
        partes_nome = comprador_nome.strip().split(maxsplit=1)
        payer: dict[str, Any] = {}
        if self.settings.mp_live_mode:
            payer["email"] = comprador_email
        if partes_nome:
            payer["name"] = partes_nome[0]
        if len(partes_nome) > 1:
            payer["surname"] = partes_nome[1]
        if comprador_criado_em is not None:
            payer["date_created"] = self._data_mp(comprador_criado_em)
        payload: dict[str, Any] = {
            "external_reference": str(pedido_id),
            "marketplace_fee": float(taxa_marketplace),
            "notification_url": self.settings.mp_webhook_url,
            "statement_descriptor": "OBRACIRCULAR",
            "payer": payer,
            "items": [
                {
                    "id": str(anuncio_id),
                    "title": titulo,
                    "description": descricao,
                    "category_id": "home",
                    "currency_id": "BRL",
                    "quantity": quantidade,
                    "unit_price": float(preco_unitario),
                }
            ],
            "metadata": {
                "pedido_id": str(pedido_id),
                "pagamento_id": str(pagamento_id),
            },
            "back_urls": {
                "success": f"{retorno}?result=success",
                "pending": f"{retorno}?result=pending",
                "failure": f"{retorno}?result=failure",
            },
            "expires": True,
            "expiration_date_to": self._data_mp(expira_em),
            "payment_methods": {"excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}]},
        }
        if self._url_publica_https(self.settings.mp_public_base_url):
            payload["auto_return"] = "approved"
        return payload

    @staticmethod
    def _data_mp(valor: datetime) -> str:
        return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _url_publica_https(url: str) -> bool:
        partes = urlsplit(url)
        return partes.scheme == "https" and partes.hostname not in {
            None,
            "localhost",
            "127.0.0.1",
            "::1",
        }

    async def _cancelar_e_liberar(self, pedido_id: UUID, pagamento_id: UUID) -> None:
        agora = datetime.now(UTC)
        async with self.session.begin():
            pedido = await self.session.scalar(
                select(Pedido).where(Pedido.id == pedido_id).with_for_update()
            )
            pagamento = await self.session.get(Pagamento, pagamento_id)
            if pedido is None or pagamento is None:
                return
            anuncio = await self.session.scalar(
                select(Anuncio).where(Anuncio.id == pedido.anuncio_id).with_for_update()
            )
            if anuncio is not None:
                self._liberar_estoque(pedido, anuncio, agora)
            pedido.status = PedidoStatus.CANCELADO
            pedido.cancelado_em = agora
            pagamento.status = PagamentoStatus.CANCELADO
            pagamento.cancelado_em = agora

    @staticmethod
    def _validar_compra(anuncio: Anuncio, comprador_id: UUID, quantidade: int) -> None:
        if anuncio.vendedor_id == comprador_id:
            raise PedidoService._erro(
                409, "Você não pode comprar o próprio anúncio.", "SELF_PURCHASE_NOT_ALLOWED"
            )
        if anuncio.status not in {AnuncioStatus.ATIVO, AnuncioStatus.ESGOTADO}:
            raise PedidoService._erro(409, "O anúncio não está disponível.", "AD_NOT_AVAILABLE")
        if anuncio.quantidade < quantidade:
            raise PedidoService._erro(
                409, "A quantidade solicitada não está disponível.", "INSUFFICIENT_STOCK"
            )

    @staticmethod
    def _liberar_estoque(pedido: Pedido, anuncio: Anuncio, agora: datetime) -> None:
        if pedido.estoque_liberado_em is not None:
            return
        anuncio.quantidade += pedido.quantidade
        if anuncio.status == AnuncioStatus.ESGOTADO and anuncio.deletado_em is None:
            anuncio.status = AnuncioStatus.ATIVO
        pedido.estoque_liberado_em = agora

    @staticmethod
    def calcular_taxa_marketplace(valor: Decimal, percentual: Decimal) -> Decimal:
        return (valor * percentual / Decimal("100")).quantize(CENTAVOS, rounding=ROUND_HALF_UP)

    @staticmethod
    def _resposta(
        pedido: Pedido, pagamento: Pagamento | None, reembolso: Reembolso | None = None
    ) -> PedidoResponse:
        return PedidoResponse(
            id=pedido.id,
            anuncio_id=pedido.anuncio_id,
            comprador_id=pedido.comprador_id,
            quantidade=pedido.quantidade,
            preco_unitario=pedido.preco_unitario,
            valor_total=pedido.valor_total,
            modalidade_entrega=pedido.modalidade_entrega,
            status=pedido.status,
            criado_em=pedido.criado_em,
            reserva_expira_em=pedido.reserva_expira_em,
            pagamento=PagamentoResumo.model_validate(pagamento) if pagamento else None,
            reembolso=ReembolsoResponse.model_validate(reembolso) if reembolso else None,
        )

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)
