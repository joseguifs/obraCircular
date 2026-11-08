import warnings
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_tem_identificadores_unicos_e_um_unico_head() -> None:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        scripts = ScriptDirectory.from_config(config)
        revisoes = list(scripts.walk_revisions())
        head = scripts.get_current_head()

    assert head is not None
    assert revisoes[0].revision == head
    assert len(revisoes) == len(list((backend / "alembic" / "versions").glob("*.py")))
