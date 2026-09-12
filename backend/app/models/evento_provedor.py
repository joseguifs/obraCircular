from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import EventoProcessamentoStatus, ProvedorPagamento


class EventoProvedor(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "eventos_provedor"
    __table_args__ = (
        UniqueConstraint("provedor", "evento_externo_id", name="uq_eventos_provedor_externo"),
        CheckConstraint("provedor IN ('MERCADO_PAGO')", name="ck_eventos_provedor"),
        CheckConstraint("tentativas >= 0", name="ck_eventos_tentativas"),
        CheckConstraint(
            "status_processamento IN ('PENDENTE', 'PROCESSADO', 'FALHOU', 'IGNORADO')",
            name="ck_eventos_status",
        ),
        Index(
            "ix_eventos_status_processamento",
            "status_processamento",
            "recebido_em",
        ),
        Index("ix_eventos_recurso_externo", "provedor", "recurso_externo_id"),
    )

    provedor: Mapped[ProvedorPagamento] = mapped_column(
        String(30),
        default=ProvedorPagamento.MERCADO_PAGO,
        server_default=ProvedorPagamento.MERCADO_PAGO.value,
    )
    evento_externo_id: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(100))
    recurso_externo_id: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status_processamento: Mapped[EventoProcessamentoStatus] = mapped_column(
        String(20),
        default=EventoProcessamentoStatus.PENDENTE,
        server_default=EventoProcessamentoStatus.PENDENTE.value,
    )
    tentativas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    recebido_em: Mapped[datetime] = mapped_column(server_default=func.now())
    processado_em: Mapped[datetime | None]
    erro: Mapped[str | None] = mapped_column(Text)
