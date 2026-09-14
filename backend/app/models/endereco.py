from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Endereco(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enderecos"
    __table_args__ = (
        UniqueConstraint("id", "usuario_id", name="uq_enderecos_id_usuario"),
        CheckConstraint("cep ~ '^[0-9]{8}$'", name="ck_enderecos_cep"),
        CheckConstraint("estado ~ '^[A-Z]{2}$'", name="ck_enderecos_estado"),
        Index("ix_enderecos_usuario_id", "usuario_id"),
        Index("ix_enderecos_ativos", "usuario_id", postgresql_where=text("deletado_em IS NULL")),
    )

    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", name="fk_enderecos_usuario"))
    cep: Mapped[str] = mapped_column(String(8))
    logradouro: Mapped[str] = mapped_column(String(150))
    numero: Mapped[str] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str] = mapped_column(String(100))
    cidade: Mapped[str] = mapped_column(String(100))
    estado: Mapped[str] = mapped_column(CHAR(2))
    deletado_em: Mapped[datetime | None]
