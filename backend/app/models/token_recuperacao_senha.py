from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TokenRecuperacaoSenha(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Token de uso único enviado por e-mail para redefinir a senha.

    Apenas o hash SHA-256 do token é armazenado: quem tiver acesso ao banco não
    consegue reconstruir o link enviado ao usuário.
    """

    __tablename__ = "tokens_recuperacao_senha"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_tokens_recuperacao_senha_token_hash"),
        Index("ix_tokens_recuperacao_senha_usuario_id", "usuario_id"),
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "usuarios.id",
            name="fk_tokens_recuperacao_senha_usuario",
            ondelete="CASCADE",
        )
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    expira_em: Mapped[datetime]
    usado_em: Mapped[datetime | None]
