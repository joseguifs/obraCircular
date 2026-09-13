from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.categoria import Categoria
from app.models.enums import CategoriaStatus
from app.repositories.categoria import CategoriaRepository
from app.schemas.categoria import CategoriaCreate, CategoriaFilters, CategoriaUpdate
from app.services.categoria import CategoriaService

DADOS_VALIDOS = {"nome": "Ferramentas", "descricao": "Ferramentas manuais e elétricas"}


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


def criar_servico() -> tuple[CategoriaService, AsyncMock, FakeSession]:
    session = FakeSession()
    repository = AsyncMock(spec=CategoriaRepository)
    repository.buscar_por_nome.return_value = None
    service = CategoriaService(
        cast(AsyncSession, session),
        cast(CategoriaRepository, repository),
    )
    return service, repository, session


def categoria_falsa(**sobrescritas: object) -> Categoria:
    dados = {
        "id": uuid4(),
        "nome": DADOS_VALIDOS["nome"],
        "descricao": DADOS_VALIDOS["descricao"],
        "status": CategoriaStatus.ATIVA,
        **sobrescritas,
    }
    return cast(Categoria, SimpleNamespace(**dados))


async def test_criar_categoria_com_nome_disponivel() -> None:
    service, repository, _ = criar_servico()
    repository.criar.side_effect = lambda categoria: categoria

    categoria = await service.criar(CategoriaCreate(**DADOS_VALIDOS))

    assert categoria.nome == "Ferramentas"
    repository.criar.assert_awaited_once()


async def test_criar_categoria_com_nome_repetido_retorna_409() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_nome.return_value = categoria_falsa()

    with pytest.raises(AppError) as erro:
        await service.criar(CategoriaCreate(**DADOS_VALIDOS))

    assert erro.value.status_code == 409
    assert erro.value.code == "CATEGORY_NAME_TAKEN"


async def test_buscar_categoria_inexistente_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.buscar(uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "CATEGORY_NOT_FOUND"


async def test_listar_repassa_total_e_paginacao() -> None:
    service, repository, _ = criar_servico()
    repository.listar.return_value = ([], 0)

    resposta = await service.listar(CategoriaFilters(offset=5, limit=10))

    assert resposta.total == 0
    assert (resposta.offset, resposta.limit) == (5, 10)


async def test_atualizar_altera_somente_campos_enviados() -> None:
    service, repository, _ = criar_servico()
    categoria = categoria_falsa()
    repository.buscar_por_id.return_value = categoria

    atualizada = await service.atualizar(uuid4(), CategoriaUpdate(descricao="Nova descrição"))

    assert atualizada.descricao == "Nova descrição"
    assert atualizada.nome == "Ferramentas"


async def test_atualizar_categoria_inexistente_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.atualizar(uuid4(), CategoriaUpdate(nome="Outro nome"))

    assert erro.value.status_code == 404
    assert erro.value.code == "CATEGORY_NOT_FOUND"


async def test_atualizar_bloqueia_a_linha_antes_de_alterar() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = categoria_falsa()

    await service.atualizar(uuid4(), CategoriaUpdate(descricao="Nova descrição"))

    assert repository.buscar_por_id.await_args.kwargs["bloquear"] is True


async def test_atualizar_para_nome_ja_usado_por_outra_categoria_retorna_409() -> None:
    service, repository, _ = criar_servico()
    categoria = categoria_falsa()
    repository.buscar_por_id.return_value = categoria
    repository.buscar_por_nome.return_value = categoria_falsa(nome="Outra categoria")

    with pytest.raises(AppError) as erro:
        await service.atualizar(uuid4(), CategoriaUpdate(nome="Outra categoria"))

    assert erro.value.status_code == 409
    assert erro.value.code == "CATEGORY_NAME_TAKEN"


async def test_atualizar_para_o_proprio_nome_nao_gera_conflito() -> None:
    service, repository, _ = criar_servico()
    categoria = categoria_falsa()
    repository.buscar_por_id.return_value = categoria

    atualizada = await service.atualizar(
        uuid4(), CategoriaUpdate(nome="Ferramentas", descricao="Atualizada")
    )

    assert atualizada.nome == "Ferramentas"
    repository.buscar_por_nome.assert_not_awaited()


async def test_excluir_e_logico_e_altera_status_para_inativa() -> None:
    service, repository, _ = criar_servico()
    categoria = categoria_falsa()
    repository.buscar_por_id.return_value = categoria

    await service.excluir(uuid4())

    assert categoria.status == CategoriaStatus.INATIVA


async def test_excluir_categoria_inexistente_retorna_404() -> None:
    service, repository, _ = criar_servico()
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.excluir(uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "CATEGORY_NOT_FOUND"


async def test_reativar_categoria_via_atualizacao_de_status() -> None:
    service, repository, _ = criar_servico()
    categoria = categoria_falsa(status=CategoriaStatus.INATIVA)
    repository.buscar_por_id.return_value = categoria

    atualizada = await service.atualizar(uuid4(), CategoriaUpdate(status=CategoriaStatus.ATIVA))

    assert atualizada.status == CategoriaStatus.ATIVA
