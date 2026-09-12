from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CategoriaStatus


class Categoria(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categorias"
    __table_args__ = (
        UniqueConstraint("nome", name="uq_categorias_nome"),
        CheckConstraint("status IN ('ATIVA', 'INATIVA')", name="ck_categorias_status"),
        Index("ix_categorias_status", "status"),
    )

    nome: Mapped[str] = mapped_column(String(100))
    descricao: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[CategoriaStatus] = mapped_column(
        String(20),
        default=CategoriaStatus.ATIVA,
        server_default=CategoriaStatus.ATIVA.value,
    )
