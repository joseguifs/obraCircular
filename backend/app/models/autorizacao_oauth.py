from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class AutorizacaoOAuth(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "autorizacoes_oauth"
    __table_args__ = (
        Index("uq_autorizacoes_oauth_state_hash", "state_hash", unique=True),
        Index("ix_autorizacoes_oauth_expira_em", "expira_em"),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_autorizacoes_oauth_usuario")
    )
    state_hash: Mapped[str] = mapped_column(String(64))
    code_verifier_criptografado: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    expira_em: Mapped[datetime]
    utilizado_em: Mapped[datetime | None]
