from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.anuncio import Anuncio
from app.models.enums import AnuncioStatus, CategoriaStatus, UsuarioStatus
from app.repositories.anuncio import AnuncioRepository
from app.schemas.anuncio import AnuncioCreate, AnuncioUpdate
from app.services.anuncio import AnuncioService


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.flush = AsyncMock()
        self.refresh = AsyncMock()

    def begin(self) -> FakeTransaction:
        return FakeTransaction()


def criar_servico() -> tuple[AnuncioService, AsyncMock, FakeSession]:
    session = FakeSession()
    repository = AsyncMock(spec=AnuncioRepository)
    service = AnuncioService(
        cast(AsyncSession, session),
        cast(AnuncioRepository, repository),
    )
    return service, repository, session


@pytest.mark.asyncio
async def test_criar_anuncio_sem_estoque_define_status_esgotado() -> None:
    service, repository, _ = criar_servico()
    vendedor_id = uuid4()
    endereco_id = uuid4()
    categoria_id = uuid4()
    repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    repository.buscar_categoria.return_value = SimpleNamespace(status=CategoriaStatus.ATIVA)
    repository.buscar_endereco.return_value = SimpleNamespace(usuario_id=vendedor_id)
    repository.criar.side_effect = lambda anuncio: anuncio
    dados = AnuncioCreate(
        titulo="Tijolos cerâmicos",
        descricao="Lote de tijolos cerâmicos sem uso.",
        categoria_id=categoria_id,
        endereco_id=endereco_id,
        preco="2.50",
        quantidade=0,
    )

    anuncio = await service.criar(dados, vendedor_id)

    assert anuncio.vendedor_id == vendedor_id
    assert anuncio.status == AnuncioStatus.ESGOTADO
    repository.criar.assert_awaited_once()


@pytest.mark.asyncio
async def test_atualizar_anuncio_de_outro_vendedor_retorna_proibido() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = SimpleNamespace(vendedor_id=uuid4())

    with pytest.raises(AppError) as error:
        await service.atualizar(uuid4(), AnuncioUpdate(titulo="Título atualizado"), uuid4())

    assert error.value.status_code == 403
    assert error.value.code == "AD_FORBIDDEN"


@pytest.mark.asyncio
async def test_excluir_anuncio_faz_exclusao_logica() -> None:
    service, repository, session = criar_servico()
    vendedor_id = uuid4()
    anuncio = cast(
        Anuncio,
        SimpleNamespace(
            vendedor_id=vendedor_id,
            deletado_em=None,
            encerrado_em=None,
            status=AnuncioStatus.ATIVO,
        ),
    )
    repository.buscar_por_id.return_value = anuncio
    repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)

    await service.excluir(uuid4(), vendedor_id)

    assert anuncio.deletado_em is not None
    assert anuncio.encerrado_em is not None
    assert anuncio.status == AnuncioStatus.ENCERRADO
    session.flush.assert_awaited_once()


def test_status_precisa_corresponder_ao_estoque() -> None:
    with pytest.raises(AppError) as error:
        AnuncioService._definir_status(
            status_atual=AnuncioStatus.ATIVO,
            status_solicitado=AnuncioStatus.ATIVO,
            quantidade=0,
        )

    assert error.value.code == "AD_STATUS_INVALID"
