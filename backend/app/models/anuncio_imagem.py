from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnuncioImagem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "anuncio_imagens"
    __table_args__ = (
        UniqueConstraint("chave_objeto", name="uq_anuncio_imagens_chave_objeto"),
        UniqueConstraint("anuncio_id", "ordem", name="uq_anuncio_imagens_anuncio_ordem"),
        CheckConstraint("tamanho_bytes > 0", name="ck_anuncio_imagens_tamanho"),
        CheckConstraint("ordem >= 0", name="ck_anuncio_imagens_ordem"),
        Index("ix_anuncio_imagens_anuncio_id", "anuncio_id"),
    )

    anuncio_id: Mapped[UUID] = mapped_column(
        ForeignKey("anuncios.id", name="fk_anuncio_imagens_anuncio", ondelete="CASCADE")
    )
    chave_objeto: Mapped[str] = mapped_column(Text)
    nome_original: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    ordem: Mapped[int] = mapped_column(SmallInteger)
