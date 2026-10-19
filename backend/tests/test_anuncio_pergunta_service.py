from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.enums import AnuncioStatus, UsuarioStatus
from app.repositories.anuncio import AnuncioRepository
from app.repositories.anuncio_pergunta import AnuncioPerguntaRepository
from app.schemas.anuncio_pergunta import AnuncioPerguntaCreate, AnuncioRespostaCreate
from app.services.anuncio_pergunta import AnuncioPerguntaService


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


def criar_servico() -> tuple[AnuncioPerguntaService, AsyncMock, AsyncMock]:
    repository = AsyncMock(spec=AnuncioPerguntaRepository)
    anuncio_repository = AsyncMock(spec=AnuncioRepository)
    service = AnuncioPerguntaService(
        cast(AsyncSession, FakeSession()),
        cast(AnuncioPerguntaRepository, repository),
        cast(AnuncioRepository, anuncio_repository),
    )
    return service, repository, anuncio_repository


def anuncio_fake(
    vendedor_id: object, status: AnuncioStatus = AnuncioStatus.ATIVO
) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), vendedor_id=vendedor_id, status=status)


async def test_perguntar_cria_pergunta_sem_resposta() -> None:
    service, repository, anuncio_repository = criar_servico()
    autor_id = uuid4()
    anuncio = anuncio_fake(vendedor_id=uuid4())
    anuncio_repository.buscar_por_id.return_value = anuncio
    anuncio_repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    repository.criar.side_effect = lambda pergunta: pergunta

    pergunta = await service.perguntar(
        anuncio.id,
        AnuncioPerguntaCreate(pergunta="  Ainda tem as 40 unidades?  "),
        autor_id,
    )

    assert pergunta.autor_id == autor_id
    assert pergunta.anuncio_id == anuncio.id
    assert pergunta.pergunta == "Ainda tem as 40 unidades?"
    assert pergunta.resposta is None
    repository.criar.assert_awaited_once()


async def test_vendedor_nao_pode_perguntar_no_proprio_anuncio() -> None:
    service, repository, anuncio_repository = criar_servico()
    vendedor_id = uuid4()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(vendedor_id)

    with pytest.raises(AppError) as erro:
        await service.perguntar(uuid4(), AnuncioPerguntaCreate(pergunta="Teste?"), vendedor_id)

    assert erro.value.status_code == 403
    assert erro.value.code == "QUESTION_OWN_AD"
    repository.criar.assert_not_awaited()


async def test_anuncio_encerrado_nao_recebe_perguntas() -> None:
    service, _, anuncio_repository = criar_servico()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(
        uuid4(), status=AnuncioStatus.ENCERRADO
    )

    with pytest.raises(AppError) as erro:
        await service.perguntar(uuid4(), AnuncioPerguntaCreate(pergunta="Ainda tem?"), uuid4())

    assert erro.value.code == "AD_CLOSED"


async def test_anuncio_esgotado_ainda_recebe_perguntas() -> None:
    service, repository, anuncio_repository = criar_servico()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(
        uuid4(), status=AnuncioStatus.ESGOTADO
    )
    anuncio_repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    repository.criar.side_effect = lambda pergunta: pergunta

    pergunta = await service.perguntar(
        uuid4(), AnuncioPerguntaCreate(pergunta="Vai repor o estoque?"), uuid4()
    )

    assert pergunta.pergunta == "Vai repor o estoque?"


async def test_perguntar_em_anuncio_inexistente_retorna_404() -> None:
    service, _, anuncio_repository = criar_servico()
    anuncio_repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.perguntar(uuid4(), AnuncioPerguntaCreate(pergunta="Tem?"), uuid4())

    assert erro.value.status_code == 404
    assert erro.value.code == "AD_NOT_FOUND"


async def test_usuario_bloqueado_nao_pode_perguntar() -> None:
    service, _, anuncio_repository = criar_servico()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(uuid4())
    anuncio_repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.BLOQUEADO)

    with pytest.raises(AppError) as erro:
        await service.perguntar(uuid4(), AnuncioPerguntaCreate(pergunta="Tem?"), uuid4())

    assert erro.value.code == "USER_NOT_ACTIVE"


async def test_vendedor_responde_pergunta_pendente() -> None:
    service, repository, anuncio_repository = criar_servico()
    vendedor_id = uuid4()
    anuncio = anuncio_fake(vendedor_id)
    pergunta = SimpleNamespace(resposta=None, respondido_em=None)
    anuncio_repository.buscar_por_id.return_value = anuncio
    anuncio_repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    repository.buscar_por_id.return_value = pergunta

    resultado = await service.responder(
        anuncio.id,
        uuid4(),
        AnuncioRespostaCreate(resposta=" Sim, todas disponíveis. "),
        vendedor_id,
    )

    assert resultado.resposta == "Sim, todas disponíveis."
    assert isinstance(resultado.respondido_em, datetime)
    assert resultado.respondido_em.tzinfo == UTC
    assert repository.buscar_por_id.await_args.kwargs == {"bloquear": True}


async def test_somente_vendedor_pode_responder() -> None:
    service, repository, anuncio_repository = criar_servico()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(uuid4())

    with pytest.raises(AppError) as erro:
        await service.responder(uuid4(), uuid4(), AnuncioRespostaCreate(resposta="Sim"), uuid4())

    assert erro.value.status_code == 403
    assert erro.value.code == "QUESTION_ANSWER_FORBIDDEN"
    repository.buscar_por_id.assert_not_awaited()


async def test_pergunta_ja_respondida_retorna_conflito() -> None:
    service, repository, anuncio_repository = criar_servico()
    vendedor_id = uuid4()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(vendedor_id)
    anuncio_repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    repository.buscar_por_id.return_value = SimpleNamespace(
        resposta="Resposta anterior", respondido_em=datetime.now(UTC)
    )

    with pytest.raises(AppError) as erro:
        await service.responder(
            uuid4(), uuid4(), AnuncioRespostaCreate(resposta="Nova"), vendedor_id
        )

    assert erro.value.status_code == 409
    assert erro.value.code == "QUESTION_ALREADY_ANSWERED"


async def test_responder_pergunta_inexistente_retorna_404() -> None:
    service, repository, anuncio_repository = criar_servico()
    vendedor_id = uuid4()
    anuncio_repository.buscar_por_id.return_value = anuncio_fake(vendedor_id)
    anuncio_repository.buscar_usuario.return_value = SimpleNamespace(status=UsuarioStatus.ATIVO)
    repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as erro:
        await service.responder(
            uuid4(), uuid4(), AnuncioRespostaCreate(resposta="Sim"), vendedor_id
        )

    assert erro.value.code == "QUESTION_NOT_FOUND"


@pytest.mark.parametrize("texto", ["", "   ", "ab", "x" * 501])
def test_schema_rejeita_pergunta_invalida(texto: str) -> None:
    with pytest.raises(ValidationError):
        AnuncioPerguntaCreate(pergunta=texto)


@pytest.mark.parametrize("texto", ["", "   ", "x" * 1001])
def test_schema_rejeita_resposta_invalida(texto: str) -> None:
    with pytest.raises(ValidationError):
        AnuncioRespostaCreate(resposta=texto)
