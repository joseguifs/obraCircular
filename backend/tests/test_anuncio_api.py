from typing import Any
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

import app.api.routes.anuncios as anuncios_routes
from app.core.exceptions import AppError
from app.main import app
from app.schemas.anuncio import AnuncioFilters, AnuncioListResponse


async def test_listagem_expoe_filtros_e_paginacao(monkeypatch: Any) -> None:
    filtros_recebidos: list[AnuncioFilters] = []

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def listar(
            self,
            filtros: AnuncioFilters,
            *,
            vendedor_id: object | None = None,
        ) -> AnuncioListResponse:
            assert vendedor_id is None
            filtros_recebidos.append(filtros)
            return AnuncioListResponse(
                items=[], total=0, offset=filtros.offset, limit=filtros.limit
            )

    monkeypatch.setattr(anuncios_routes, "AnuncioService", FakeService)
    transport = ASGITransport(app=app)
    categoria_id = uuid4()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/ads",
            params={
                "category_id": str(categoria_id),
                "status": "ATIVO",
                "search": "cimento",
                "min_price": "10.00",
                "max_price": "50.00",
                "offset": 5,
                "limit": 10,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "offset": 5, "limit": 10}
    assert filtros_recebidos[0].category_id == categoria_id
    assert filtros_recebidos[0].search == "cimento"


async def test_erro_de_dominio_possui_formato_padronizado(monkeypatch: Any) -> None:
    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def buscar(self, _: object) -> None:
            raise AppError(status_code=404, detail="Anúncio não encontrado.", code="AD_NOT_FOUND")

    monkeypatch.setattr(anuncios_routes, "AnuncioService", FakeService)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/ads/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Anúncio não encontrado.", "code": "AD_NOT_FOUND"}


async def test_criacao_exige_usuario_atual() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ads",
            json={
                "titulo": "Tijolos cerâmicos",
                "descricao": "Lote de tijolos cerâmicos sem uso.",
                "categoria_id": str(uuid4()),
                "endereco_id": str(uuid4()),
                "preco": "2.50",
                "quantidade": 100,
            },
        )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
