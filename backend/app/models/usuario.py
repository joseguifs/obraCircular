from datetime import datetime

from sqlalchemy import CheckConstraint, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UsuarioStatus


class Usuario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ATIVO', 'INATIVO', 'BLOQUEADO')",
            name="ck_usuarios_status",
        ),
        Index("uq_usuarios_email_normalizado", text("lower(email)"), unique=True),
        Index("ix_usuarios_status", "status"),
        Index("ix_usuarios_ativos", "id", postgresql_where=text("deletado_em IS NULL")),
    )

    nome: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255))
    senha_hash: Mapped[str] = mapped_column(String(255))
    telefone: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[UsuarioStatus] = mapped_column(
        String(20),
        default=UsuarioStatus.ATIVO,
        server_default=UsuarioStatus.ATIVO.value,
    )
    deletado_em: Mapped[datetime | None]
