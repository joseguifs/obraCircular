from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class DestinoRepasse(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "destinos_repasse"

    vendedor_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id"), unique=True)
    tipo_chave: Mapped[str] = mapped_column(String(20))
    chave_criptografada: Mapped[str] = mapped_column(Text)
    validado_por: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id"))
    validado_em: Mapped[datetime]
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class InstrucaoRepasse(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "instrucoes_repasse"

    repasse_id: Mapped[UUID] = mapped_column(ForeignKey("repasses.id"), unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    corpo_criptografado: Mapped[str] = mapped_column(Text)
    recurso_externo_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    transferencia_externa_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    status_provedor: Mapped[str | None] = mapped_column(String(50))
    solicitado_por: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    lease_ate: Mapped[datetime | None]
    test_mode: Mapped[bool]


class EventoRepasse(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "eventos_repasse"

    repasse_id: Mapped[UUID] = mapped_column(ForeignKey("repasses.id"))
    operador_id: Mapped[UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    acao: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
