from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnuncioPergunta(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pergunta pública feita por um usuário ao vendedor de um anúncio."""

    __tablename__ = "anuncio_perguntas"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(pergunta)) BETWEEN 1 AND 500",
            name="ck_anuncio_perguntas_pergunta",
        ),
        CheckConstraint(
            "resposta IS NULL OR char_length(btrim(resposta)) BETWEEN 1 AND 1000",
            name="ck_anuncio_perguntas_resposta",
        ),
        CheckConstraint(
            "(resposta IS NULL) = (respondido_em IS NULL)",
            name="ck_anuncio_perguntas_respondido_em",
        ),
        Index(
            "ix_anuncio_perguntas_anuncio_criado_em",
            "anuncio_id",
            text("criado_em DESC"),
        ),
        Index("ix_anuncio_perguntas_autor_id", "autor_id"),
    )

    anuncio_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "anuncios.id",
            name="fk_anuncio_perguntas_anuncio",
            ondelete="CASCADE",
        )
    )
    autor_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_anuncio_perguntas_autor")
    )
    pergunta: Mapped[str] = mapped_column(Text)
    resposta: Mapped[str | None] = mapped_column(Text)
    respondido_em: Mapped[datetime | None]
