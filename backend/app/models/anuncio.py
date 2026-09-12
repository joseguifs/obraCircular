from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import AnuncioStatus


class Anuncio(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "anuncios"
    __table_args__ = (
        ForeignKeyConstraint(
            ["endereco_id", "vendedor_id"],
            ["enderecos.id", "enderecos.usuario_id"],
            name="fk_anuncios_endereco_vendedor",
        ),
        CheckConstraint("preco >= 0", name="ck_anuncios_preco"),
        CheckConstraint("quantidade >= 0", name="ck_anuncios_quantidade"),
        CheckConstraint(
            "status IN ('ATIVO', 'ESGOTADO', 'ENCERRADO')",
            name="ck_anuncios_status",
        ),
        Index("ix_anuncios_categoria_id", "categoria_id"),
        Index("ix_anuncios_vendedor_id", "vendedor_id"),
        Index("ix_anuncios_endereco_id", "endereco_id"),
        Index(
            "ix_anuncios_busca_ativos",
            "categoria_id",
            text("postado_em DESC"),
            postgresql_where=text("status = 'ATIVO' AND deletado_em IS NULL"),
        ),
    )

    titulo: Mapped[str] = mapped_column(String(150))
    descricao: Mapped[str] = mapped_column(Text)
    categoria_id: Mapped[UUID] = mapped_column(
        ForeignKey("categorias.id", name="fk_anuncios_categoria")
    )
    vendedor_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_anuncios_vendedor")
    )
    endereco_id: Mapped[UUID]
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    imagem_url: Mapped[str | None] = mapped_column(Text)
    quantidade: Mapped[int] = mapped_column(Integer)
    status: Mapped[AnuncioStatus] = mapped_column(
        String(20),
        default=AnuncioStatus.ATIVO,
        server_default=AnuncioStatus.ATIVO.value,
    )
    postado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
    encerrado_em: Mapped[datetime | None]
    deletado_em: Mapped[datetime | None]
