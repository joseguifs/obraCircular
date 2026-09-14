from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EntregaStatus


class Entrega(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entregas"
    __table_args__ = (
        UniqueConstraint("pedido_id", name="uq_entregas_pedido"),
        CheckConstraint(
            "pin_tentativas >= 0 AND pin_max_tentativas > 0 "
            "AND pin_tentativas <= pin_max_tentativas",
            name="ck_entregas_tentativas",
        ),
        CheckConstraint(
            "status IN ('AGUARDANDO_ENVIO', 'PREPARANDO', 'EM_ROTA', "
            "'ENTREGUE', 'RECUSADA', 'CANCELADA')",
            name="ck_entregas_status",
        ),
        Index("ix_entregas_status", "status"),
        Index(
            "ix_entregas_prazo_contestacao",
            "prazo_contestacao_em",
            postgresql_where=text("status = 'ENTREGUE'"),
        ),
    )

    pedido_id: Mapped[UUID] = mapped_column(ForeignKey("pedidos.id", name="fk_entregas_pedido"))
    status: Mapped[EntregaStatus] = mapped_column(
        String(30),
        default=EntregaStatus.AGUARDANDO_ENVIO,
        server_default=EntregaStatus.AGUARDANDO_ENVIO.value,
    )
    pin_hash: Mapped[str] = mapped_column(String(255))
    pin_tentativas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pin_max_tentativas: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    pin_expira_em: Mapped[datetime | None]
    pin_bloqueado_em: Mapped[datetime | None]
    saiu_para_entrega_em: Mapped[datetime | None]
    confirmado_em: Mapped[datetime | None]
    confirmado_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", name="fk_entregas_confirmado_por")
    )
    prazo_contestacao_em: Mapped[datetime | None]
