"""Geração e validação do PIN que confirma a entrega (ou retirada) de um pedido.

Regras em `docs/domain/entrega.md`:
- somente o comprador obtém o PIN; somente o hash é armazenado;
- somente o vendedor do anúncio confirma, informando o PIN recebido do comprador;
- cinco tentativas incorretas bloqueiam o PIN; o PIN expira em 24 horas;
- gerar um novo PIN substitui o hash, zera as tentativas e invalida o anterior;
- a confirmação move entrega e pedido para ENTREGUE, abre a janela de contestação
  de 7 dias e move o repasse para EM_PERIODO_CONTESTACAO, tudo na mesma transação.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import gerar_pin_entrega, hash_pin_entrega, verificar_pin_entrega
from app.models.anuncio import Anuncio
from app.models.entrega import Entrega
from app.models.enums import EntregaStatus, PedidoStatus, ReembolsoStatus, RepasseStatus
from app.models.pedido import Pedido
from app.models.reembolso import Reembolso
from app.models.repasse import Repasse
from app.schemas.entrega import EntregaPinResponse, EntregaResponse

PRAZO_CONTESTACAO = timedelta(days=7)

# Pedido pago e ainda não entregue: única janela em que o PIN faz sentido.
_PEDIDO_STATUS_AGUARDANDO_ENTREGA = frozenset(
    {
        PedidoStatus.PAGAMENTO_APROVADO,
        PedidoStatus.PREPARANDO_ENTREGA,
        PedidoStatus.EM_ENTREGA,
    }
)
_ENTREGA_STATUS_FINAIS = frozenset(
    {EntregaStatus.ENTREGUE, EntregaStatus.RECUSADA, EntregaStatus.CANCELADA}
)
_REEMBOLSO_STATUS_ENCERRADOS = frozenset(
    {ReembolsoStatus.RECUSADO, ReembolsoStatus.FALHOU, ReembolsoStatus.CANCELADO}
)


@dataclass(frozen=True, slots=True)
class _TentativaIncorreta:
    restantes: int


class EntregaService:
    def __init__(self, session: AsyncSession, *, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def gerar_pin(self, pedido_id: UUID, comprador_id: UUID) -> EntregaPinResponse:
        """Gera (ou regenera) o PIN do pedido e o devolve em texto puro ao comprador."""
        agora = datetime.now(UTC)
        async with self.session.begin():
            pedido = await self.session.scalar(
                select(Pedido)
                .where(Pedido.id == pedido_id, Pedido.comprador_id == comprador_id)
                .with_for_update()
            )
            if pedido is None:
                raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")
            self._exigir_pedido_aguardando_entrega(pedido)

            entrega = await self._entrega_bloqueada(pedido.id)
            if entrega is None:
                entrega = Entrega(id=uuid4(), pedido_id=pedido.id)
                self.session.add(entrega)
            elif entrega.status in _ENTREGA_STATUS_FINAIS:
                raise self._erro(409, "Esta entrega já foi encerrada.", "DELIVERY_ALREADY_FINISHED")

            pin = gerar_pin_entrega()
            entrega.pin_hash = hash_pin_entrega(pin, entrega.id, self.settings)
            entrega.pin_tentativas = 0
            entrega.pin_bloqueado_em = None
            entrega.pin_expira_em = agora + timedelta(hours=self.settings.delivery_pin_expire_hours)
            await self.session.flush()
            return EntregaPinResponse(
                pin=pin,
                expira_em=entrega.pin_expira_em,
                tentativas_restantes=entrega.pin_max_tentativas,
            )

    async def confirmar(self, pedido_id: UUID, vendedor_id: UUID, pin: str) -> EntregaResponse:
        """Valida o PIN informado pelo vendedor e conclui a entrega."""
        agora = datetime.now(UTC)
        async with self.session.begin():
            pedido = await self.session.scalar(
                select(Pedido)
                .join(Anuncio, Anuncio.id == Pedido.anuncio_id)
                .where(Pedido.id == pedido_id, Anuncio.vendedor_id == vendedor_id)
                .with_for_update(of=Pedido)
            )
            if pedido is None:
                raise self._erro(404, "Pedido não encontrado.", "ORDER_NOT_FOUND")
            entrega = await self._entrega_bloqueada(pedido.id)
            if entrega is None:
                raise self._erro(
                    409, "O comprador ainda não gerou o PIN.", "DELIVERY_PIN_NOT_GENERATED"
                )
            # Repetição de uma confirmação já aceita: idempotente, sem nova validação.
            if entrega.status == EntregaStatus.ENTREGUE and entrega.confirmado_por == vendedor_id:
                return EntregaResponse.model_validate(entrega)
            if entrega.status in _ENTREGA_STATUS_FINAIS:
                raise self._erro(409, "Esta entrega já foi encerrada.", "DELIVERY_ALREADY_FINISHED")
            self._exigir_pedido_aguardando_entrega(pedido)
            await self._exigir_sem_reembolso(pedido.id)
            if entrega.pin_bloqueado_em is not None:
                raise self._pin_bloqueado()
            if entrega.pin_expira_em is not None and entrega.pin_expira_em <= agora:
                raise self._erro(
                    409,
                    "O PIN expirou. Peça ao comprador para gerar um novo.",
                    "DELIVERY_PIN_EXPIRED",
                )

            if verificar_pin_entrega(pin, entrega.id, entrega.pin_hash, self.settings):
                resposta: EntregaResponse | _TentativaIncorreta = await self._concluir(
                    pedido, entrega, vendedor_id, agora
                )
            else:
                resposta = self._registrar_tentativa_incorreta(entrega, agora)
            await self.session.flush()

        # Fora do bloco transacional: a tentativa incorreta precisa ser persistida
        # antes de o erro ser devolvido; levantá-lo dentro do bloco faria rollback.
        if isinstance(resposta, _TentativaIncorreta):
            if resposta.restantes == 0:
                raise self._pin_bloqueado()
            raise self._erro(
                400,
                f"PIN incorreto. Tentativas restantes: {resposta.restantes}.",
                "DELIVERY_PIN_INVALID",
            )
        return resposta

    async def _concluir(
        self, pedido: Pedido, entrega: Entrega, vendedor_id: UUID, agora: datetime
    ) -> EntregaResponse:
        prazo = agora + PRAZO_CONTESTACAO
        entrega.status = EntregaStatus.ENTREGUE
        entrega.confirmado_em = agora
        entrega.confirmado_por = vendedor_id
        entrega.prazo_contestacao_em = prazo
        entrega.pin_expira_em = None
        pedido.status = PedidoStatus.ENTREGUE
        repasse = await self.session.scalar(
            select(Repasse).where(Repasse.pedido_id == pedido.id).with_for_update()
        )
        if repasse is not None and repasse.status in {
            RepasseStatus.PAGO,
            RepasseStatus.AGUARDANDO_ENTREGA,
        }:
            repasse.status = RepasseStatus.EM_PERIODO_CONTESTACAO
            repasse.liberacao_prevista_em = prazo
        return EntregaResponse(
            id=entrega.id,
            pedido_id=pedido.id,
            status=entrega.status,
            confirmado_em=entrega.confirmado_em,
            prazo_contestacao_em=entrega.prazo_contestacao_em,
        )

    @staticmethod
    def _registrar_tentativa_incorreta(entrega: Entrega, agora: datetime) -> _TentativaIncorreta:
        entrega.pin_tentativas += 1
        restantes = max(entrega.pin_max_tentativas - entrega.pin_tentativas, 0)
        if restantes == 0:
            entrega.pin_bloqueado_em = agora
        return _TentativaIncorreta(restantes=restantes)

    async def _entrega_bloqueada(self, pedido_id: UUID) -> Entrega | None:
        entrega: Entrega | None = await self.session.scalar(
            select(Entrega).where(Entrega.pedido_id == pedido_id).with_for_update()
        )
        return entrega

    async def _exigir_sem_reembolso(self, pedido_id: UUID) -> None:
        reembolso = await self.session.scalar(
            select(Reembolso).where(
                Reembolso.pedido_id == pedido_id,
                Reembolso.status.not_in(_REEMBOLSO_STATUS_ENCERRADOS),
            )
        )
        if reembolso is not None:
            raise self._erro(
                409, "Há um reembolso em andamento para este pedido.", "DELIVERY_REFUND_PENDING"
            )

    def _exigir_pedido_aguardando_entrega(self, pedido: Pedido) -> None:
        if pedido.status not in _PEDIDO_STATUS_AGUARDANDO_ENTREGA:
            raise self._erro(
                409,
                "O pedido não está aguardando entrega.",
                "ORDER_NOT_AWAITING_DELIVERY",
            )

    def _pin_bloqueado(self) -> AppError:
        return self._erro(
            409,
            "PIN bloqueado após tentativas incorretas. Peça ao comprador para gerar um novo.",
            "DELIVERY_PIN_BLOCKED",
        )

    @staticmethod
    def _erro(status: int, detail: str, code: str) -> AppError:
        return AppError(status_code=status, detail=detail, code=code)
