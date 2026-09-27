from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.anuncio_imagem import AnuncioImagem
from app.models.enums import AnuncioStatus
from app.repositories.anuncio import AnuncioRepository
from app.repositories.anuncio_imagem import AnuncioImagemRepository
from app.services.anuncio_imagem import AnuncioImagemService
from app.services.armazenamento import ArmazenamentoLocal, ArquivoArmazenado


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class FakeSession:
    def begin(self) -> FakeTransaction:
        return FakeTransaction()


def criar_servico() -> tuple[
    AnuncioImagemService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    repository = AsyncMock(spec=AnuncioImagemRepository)
    anuncio_repository = AsyncMock(spec=AnuncioRepository)
    armazenamento = AsyncMock(spec=ArmazenamentoLocal)
    armazenamento.url_publica = Mock(side_effect=lambda chave: f"/uploads/{chave}")
    service = AnuncioImagemService(
        cast(AsyncSession, FakeSession()),
        cast(AnuncioImagemRepository, repository),
        cast(AnuncioRepository, anuncio_repository),
        cast(ArmazenamentoLocal, armazenamento),
    )
    return service, repository, anuncio_repository, armazenamento


@pytest.mark.asyncio
async def test_adiciona_imagem_valida_com_ordem_sequencial() -> None:
    service, repository, anuncio_repository, armazenamento = criar_servico()
    anuncio_id = uuid4()
    vendedor_id = uuid4()
    anuncio_repository.buscar_por_id.return_value = SimpleNamespace(
        vendedor_id=vendedor_id,
        status=AnuncioStatus.ATIVO,
    )
    repository.proxima_ordem.return_value = 1
    armazenamento.salvar_imagem.return_value = ArquivoArmazenado(
        chave_objeto=f"anuncios/{anuncio_id}/imagem.png",
        mime_type="image/png",
        tamanho_bytes=12,
    )

    async def preencher_campos(imagens: list[AnuncioImagem]) -> list[AnuncioImagem]:
        for imagem in imagens:
            imagem.id = uuid4()
            imagem.criado_em = datetime.now(UTC)
        return imagens

    repository.criar_varias.side_effect = preencher_campos
    arquivo = UploadFile(filename="material.png", file=BytesIO(b"\x89PNG\r\n\x1a\nfoto"))

    resposta = await service.adicionar(anuncio_id, vendedor_id, [arquivo])

    assert len(resposta.items) == 1
    assert resposta.items[0].ordem == 1
    assert resposta.items[0].url.endswith("/imagem.png")
    armazenamento.salvar_imagem.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejeita_arquivo_que_nao_e_imagem() -> None:
    service, repository, anuncio_repository, armazenamento = criar_servico()
    anuncio_id = uuid4()
    vendedor_id = uuid4()
    anuncio_repository.buscar_por_id.return_value = SimpleNamespace(
        vendedor_id=vendedor_id,
        status=AnuncioStatus.ATIVO,
    )
    repository.proxima_ordem.return_value = 0
    arquivo = UploadFile(filename="material.txt", file=BytesIO(b"nao e uma imagem"))

    with pytest.raises(AppError) as error:
        await service.adicionar(anuncio_id, vendedor_id, [arquivo])

    assert error.value.code == "AD_IMAGE_INVALID_TYPE"
    armazenamento.salvar_imagem.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejeita_upload_de_outro_vendedor() -> None:
    service, _, anuncio_repository, armazenamento = criar_servico()
    anuncio_repository.buscar_por_id.return_value = SimpleNamespace(
        vendedor_id=uuid4(),
        status=AnuncioStatus.ATIVO,
    )
    arquivo = UploadFile(filename="material.png", file=BytesIO(b"\x89PNG\r\n\x1a\nfoto"))

    with pytest.raises(AppError) as error:
        await service.adicionar(uuid4(), uuid4(), [arquivo])

    assert error.value.code == "AD_FORBIDDEN"
    armazenamento.salvar_imagem.assert_not_awaited()


@pytest.mark.asyncio
async def test_lista_imagens_na_ordem_com_urls_publicas() -> None:
    service, repository, anuncio_repository, _ = criar_servico()
    anuncio_id = uuid4()
    anuncio_repository.buscar_por_id.return_value = SimpleNamespace(id=anuncio_id)
    repository.listar.return_value = [
        SimpleNamespace(
            id=uuid4(),
            anuncio_id=anuncio_id,
            chave_objeto=f"anuncios/{anuncio_id}/foto-1.png",
            nome_original="foto-1.png",
            mime_type="image/png",
            tamanho_bytes=12,
            ordem=0,
            criado_em=datetime.now(UTC),
        ),
        SimpleNamespace(
            id=uuid4(),
            anuncio_id=anuncio_id,
            chave_objeto=f"anuncios/{anuncio_id}/foto-2.webp",
            nome_original="foto-2.webp",
            mime_type="image/webp",
            tamanho_bytes=24,
            ordem=1,
            criado_em=datetime.now(UTC),
        ),
    ]

    resposta = await service.listar(anuncio_id)

    assert [imagem.ordem for imagem in resposta.items] == [0, 1]
    assert resposta.items[0].url.endswith("/foto-1.png")
    repository.listar.assert_awaited_once_with(anuncio_id)


@pytest.mark.asyncio
async def test_listagem_de_imagens_rejeita_anuncio_inexistente() -> None:
    service, repository, anuncio_repository, _ = criar_servico()
    anuncio_repository.buscar_por_id.return_value = None

    with pytest.raises(AppError) as error:
        await service.listar(uuid4())

    assert error.value.code == "AD_NOT_FOUND"
    repository.listar.assert_not_awaited()
