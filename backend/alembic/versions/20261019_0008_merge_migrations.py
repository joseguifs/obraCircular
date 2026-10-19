"""Une as migrations de autenticacao, administracao, perguntas e pagamentos.

Revision ID: 20261019_0008
Revises: 20261013_0005, 20261017_0005_admin, 20261017_0005, 20261018_0007
Create Date: 2026-10-19
"""

from collections.abc import Sequence

revision: str = "20261019_0008"
down_revision: tuple[str, ...] = (
    "20261013_0005",
    "20261017_0005_admin",
    "20261017_0005",
    "20261018_0007",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
