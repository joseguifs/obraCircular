from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Administrador(Base):
    """Usuário com acesso ao painel administrativo.

    Fica em tabela própria para não misturar o perfil administrativo com o
    status do usuário (`docs/domain/administrador.md`).
    """

    __tablename__ = "administradores"

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", name="fk_administradores_usuario", ondelete="CASCADE"),
        primary_key=True,
    )
    concedido_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", name="fk_administradores_concedido_por", ondelete="SET NULL")
    )
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
