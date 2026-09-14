from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ReembolsoStatus


class Reembolso(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reembolsos"
    __table_args__ = (
        UniqueConstraint("pagamento_id", name="uq_reembolsos_pagamento"),
        UniqueConstraint("reembolso_externo_id", name="uq_reembolsos_externo"),
        UniqueConstraint("idempotency_key", name="uq_reembolsos_idempotency_key"),
        CheckConstraint("valor > 0", name="ck_reembolsos_valor"),
        CheckConstraint(
            "status IN ('SOLICITADO', 'PROCESSANDO', 'CONCLUIDO', "
            "'RECUSADO', 'FALHOU', 'CANCELADO')",
            name="ck_reembolsos_status",
        ),
        Index("ix_reembolsos_pedido_id", "pedido_id"),
    )

    pedido_id: Mapped[UUID] = mapped_column(ForeignKey("pedidos.id", name="fk_reembolsos_pedido"))
    pagamento_id: Mapped[UUID] = mapped_column(
        ForeignKey("pagamentos.id", name="fk_reembolsos_pagamento")
    )
    contestacao_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contestacoes.id", name="fk_reembolsos_contestacao")
    )
    reembolso_externo_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    motivo: Mapped[str] = mapped_column(String(255))
    status: Mapped[ReembolsoStatus] = mapped_column(
        String(30),
        default=ReembolsoStatus.SOLICITADO,
        server_default=ReembolsoStatus.SOLICITADO.value,
    )
    solicitado_por: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_reembolsos_solicitado_por")
    )
    processado_em: Mapped[datetime | None]
    falhou_em: Mapped[datetime | None]
