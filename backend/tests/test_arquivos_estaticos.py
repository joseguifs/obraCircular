from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.arquivos_estaticos import CACHE_IMUTAVEL, ArquivosImutaveis


def _app_com_uploads(diretorio: Path) -> FastAPI:
    app = FastAPI()
    app.mount("/uploads", ArquivosImutaveis(directory=diretorio), name="uploads")
    return app


async def test_upload_existente_recebe_cache_longo(tmp_path: Path) -> None:
    (tmp_path / "foto.webp").write_bytes(b"conteudo")
    transport = ASGITransport(app=_app_com_uploads(tmp_path))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resposta = await client.get("/uploads/foto.webp")

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == CACHE_IMUTAVEL


async def test_revalidacao_tambem_mantem_o_cache(tmp_path: Path) -> None:
    (tmp_path / "foto.webp").write_bytes(b"conteudo")
    transport = ASGITransport(app=_app_com_uploads(tmp_path))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        primeira = await client.get("/uploads/foto.webp")
        segunda = await client.get(
            "/uploads/foto.webp", headers={"If-None-Match": primeira.headers["etag"]}
        )

    assert segunda.status_code == 304
    assert segunda.headers["cache-control"] == CACHE_IMUTAVEL


async def test_arquivo_inexistente_nao_fica_em_cache(tmp_path: Path) -> None:
    transport = ASGITransport(app=_app_com_uploads(tmp_path))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resposta = await client.get("/uploads/nao-existe.webp")

    assert resposta.status_code == 404
    assert "cache-control" not in resposta.headers


async def test_app_principal_serve_uploads_com_cache_longo() -> None:
    from app.main import app

    montagem = next(rota for rota in app.routes if getattr(rota, "name", None) == "uploads")
    assert isinstance(getattr(montagem, "app", None), ArquivosImutaveis)
