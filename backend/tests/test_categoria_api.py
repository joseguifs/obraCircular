from typing import Any
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

import app.api.routes.categorias as categorias_routes
from app.core.exceptions import AppError
from app.main import app
from app.models.usuario import Usuario
from app.schemas.categoria import CategoriaFilters, CategoriaListResponse

DADOS_VALIDOS = {"nome": "Ferramentas", "descricao": "Ferramentas manuais e elétricas"}


def cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_criacao_normaliza_nome_antes_do_servico(
    monkeypatch: Any,
    usuario_autenticado: Usuario,
) -> None:
    recebidos: list[Any] = []

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def criar(self, dados: Any) -> Any:
            recebidos.append(dados)
            return type(
                "CategoriaFalsa",
                (),
                {
                    "id": uuid4(),
                    "status": "ATIVA",
                    "criado_em": "2026-09-13T00:00:00Z",
                    "atualizado_em": "2026-09-13T00:00:00Z",
                    **dados.model_dump(),
                },
            )()

    monkeypatch.setattr(categorias_routes, "CategoriaService", FakeService)
    async with cliente() as client:
        response = await client.post(
            "/api/v1/categories", json={**DADOS_VALIDOS, "nome": "  Ferramentas  "}
        )

    assert response.status_code == 201
    assert recebidos[0].nome == "Ferramentas"
    assert response.json()["nome"] == "Ferramentas"


async def test_nome_vazio_retorna_422(usuario_autenticado: Usuario) -> None:
    async with cliente() as client:
        response = await client.post("/api/v1/categories", json={"nome": "   "})

    assert response.status_code == 422


async def test_listagem_expoe_paginacao(monkeypatch: Any) -> None:
    chamadas: list[CategoriaFilters] = []

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def listar(self, filtros: CategoriaFilters) -> CategoriaListResponse:
            chamadas.append(filtros)
            return CategoriaListResponse(
                items=[], total=0, offset=filtros.offset, limit=filtros.limit
            )

    monkeypatch.setattr(categorias_routes, "CategoriaService", FakeService)
    async with cliente() as client:
        response = await client.get("/api/v1/categories", params={"offset": 5, "limit": 10})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "offset": 5, "limit": 10}
    assert chamadas[0].offset == 5


async def test_listagem_filtra_por_status(monkeypatch: Any) -> None:
    chamadas: list[CategoriaFilters] = []

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def listar(self, filtros: CategoriaFilters) -> CategoriaListResponse:
            chamadas.append(filtros)
            return CategoriaListResponse(
                items=[], total=0, offset=filtros.offset, limit=filtros.limit
            )

    monkeypatch.setattr(categorias_routes, "CategoriaService", FakeService)
    async with cliente() as client:
        response = await client.get("/api/v1/categories", params={"status": "INATIVA"})

    assert response.status_code == 200
    assert chamadas[0].status == "INATIVA"


async def test_erro_de_dominio_possui_formato_padronizado(monkeypatch: Any) -> None:
    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def buscar(self, *_: object) -> None:
            raise AppError(
                status_code=404,
                detail="Categoria não encontrada.",
                code="CATEGORY_NOT_FOUND",
            )

    monkeypatch.setattr(categorias_routes, "CategoriaService", FakeService)
    async with cliente() as client:
        response = await client.get(f"/api/v1/categories/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Categoria não encontrada.", "code": "CATEGORY_NOT_FOUND"}


async def test_exclusao_retorna_204(
    monkeypatch: Any,
    usuario_autenticado: Usuario,
) -> None:
    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def excluir(self, *_: object) -> None:
            return None

    monkeypatch.setattr(categorias_routes, "CategoriaService", FakeService)
    async with cliente() as client:
        response = await client.delete(f"/api/v1/categories/{uuid4()}")

    assert response.status_code == 204


async def test_atualizacao_sem_campos_retorna_422(usuario_autenticado: Usuario) -> None:
    async with cliente() as client:
        response = await client.patch(f"/api/v1/categories/{uuid4()}", json={})

    assert response.status_code == 422


async def test_escrita_exige_autenticacao() -> None:
    async with cliente() as client:
        response = await client.post("/api/v1/categories", json=DADOS_VALIDOS)

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
