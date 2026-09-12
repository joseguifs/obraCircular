from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ContaPagamentoStatus, ProvedorPagamento


class ContaPagamento(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contas_pagamento"
    __table_args__ = (
        UniqueConstraint("usuario_id", "provedor", name="uq_contas_pagamento_usuario_provedor"),
        UniqueConstraint(
            "provedor",
            "conta_externa_id",
            name="uq_contas_pagamento_provedor_externa",
        ),
        CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_contas_pagamento_provedor"),
        CheckConstraint(
            "status IN ('PENDENTE', 'ATIVA', 'BLOQUEADA', 'DESCONECTADA')",
            name="ck_contas_pagamento_status",
        ),
        Index("ix_contas_pagamento_usuario_id", "usuario_id"),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_contas_pagamento_usuario")
    )
    provedor: Mapped[ProvedorPagamento] = mapped_column(
        String(30),
        default=ProvedorPagamento.MERCADO_PAGO,
        server_default=ProvedorPagamento.MERCADO_PAGO.value,
    )
    conta_externa_id: Mapped[str] = mapped_column(String(255))
    access_token_criptografado: Mapped[str | None] = mapped_column(Text)
    refresh_token_criptografado: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ContaPagamentoStatus] = mapped_column(
        String(20),
        default=ContaPagamentoStatus.PENDENTE,
        server_default=ContaPagamentoStatus.PENDENTE.value,
    )
    autorizado_em: Mapped[datetime | None]
    token_expira_em: Mapped[datetime | None]
