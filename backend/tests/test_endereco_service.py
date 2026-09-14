from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.endereco import Endereco
from app.models.enums import UsuarioStatus
from app.repositories.endereco import EnderecoRepository
from app.schemas.endereco import EnderecoCreate, EnderecoFilters, EnderecoUpdate
from app.services.endereco import EnderecoService

DADOS_VALIDOS = {
    "cep": "01001000",
    "logradouro": "Praça da Sé",
    "numero": "100",
    "bairro": "Sé",
    "cidade": "São Paulo",
    "estado": "SP",
}


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.flush = AsyncMock()
        self.refresh = AsyncMock()
        self.delete = AsyncMock()

    def begin(self) -> FakeTransaction:
        return FakeTransaction()


def criar_servico() -> tuple[EnderecoService, AsyncMock, FakeSession]:
    session = FakeSession()
    repository = AsyncMock(spec=EnderecoRepository)
    repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    service = EnderecoService(
        cast(AsyncSession, session),
        cast(EnderecoRepository, repository),
    )
    return service, repository, session


def endereco_falso(usuario_id: object) -> Endereco:
    return cast(
        Endereco,
        SimpleNamespace(usuario_id=usuario_id, deletado_em=None, **DADOS_VALIDOS),
    )


async def test_criar_endereco_vincula_usuario_atual() -> None:
    service, repository, _ = criar_servico()
    usuario_id = uuid4()
    repository.criar.side_effect = lambda endereco: endereco

    endereco = await service.criar(EnderecoCreate(**DADOS_VALIDOS), usuario_id)

    assert endereco.usuario_id == usuario_id
    assert endereco.cep == "01001000"
    repository.criar.assert_awaited_once()


async def test_criar_endereco_para_usuario_inexistente_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_usuario.return_value = None

    with pytest.raises(AppError) as erro:
        await service.criar(EnderecoCreate(**DADOS_VALIDOS), uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "USER_NOT_FOUND"


async def test_criar_endereco_para_usuario_bloqueado_retorna_400() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.BLOQUEADO)

    with pytest.raises(AppError) as erro:
        await service.criar(EnderecoCreate(**DADOS_VALIDOS), uuid4())

    assert erro.value.status_code == 400
    assert erro.value.code == "USER_NOT_ACTIVE"


async def test_buscar_endereco_de_outro_usuario_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.buscar(uuid4(), uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "ADDRESS_NOT_FOUND"


async def test_listar_restringe_consulta_ao_usuario_atual() -> None:
    service, repository, _ = criar_servico()
    usuario_id = uuid4()
    repository.listar.return_value = ([], 0)

    resposta = await service.listar(EnderecoFilters(offset=5, limit=10), usuario_id)

    assert resposta.total == 0
    assert (resposta.offset, resposta.limit) == (5, 10)
    assert repository.listar.await_args.args[0] == usuario_id


async def test_atualizar_altera_somente_campos_enviados() -> None:
    service, repository, _ = criar_servico()
    usuario_id = uuid4()
    endereco = endereco_falso(usuario_id)
    repository.buscar_por_id.return_value = endereco

    atualizado = await service.atualizar(
        uuid4(), EnderecoUpdate(numero="200", estado="rj"), usuario_id
    )

    assert atualizado.numero == "200"
    assert atualizado.estado == "RJ"
    assert atualizado.logradouro == "Praça da Sé"


async def test_atualizar_endereco_inexistente_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.atualizar(uuid4(), EnderecoUpdate(numero="200"), uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "ADDRESS_NOT_FOUND"


async def test_atualizar_bloqueia_a_linha_antes_de_alterar() -> None:
    service, repository, _ = criar_servico()
    usuario_id = uuid4()
    repository.buscar_por_id.return_value = endereco_falso(usuario_id)

    await service.atualizar(uuid4(), EnderecoUpdate(numero="200"), usuario_id)

    assert repository.buscar_por_id.await_args.kwargs["bloquear"] is True


async def test_excluir_e_logico_e_preserva_a_linha_dos_snapshots() -> None:
    """A linha continua no banco para não quebrar as FKs de anúncios e pedidos."""
    service, repository, session = criar_servico()
    usuario_id = uuid4()
    endereco = endereco_falso(usuario_id)
    repository.buscar_por_id.return_value = endereco

    await service.excluir(uuid4(), usuario_id)

    assert endereco.deletado_em is not None
    session.delete.assert_not_awaited()


async def test_excluir_endereco_de_outro_usuario_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.excluir(uuid4(), uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "ADDRESS_NOT_FOUND"
