from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

import app.api.routes.anuncios as anuncios_routes
from app.core.exceptions import AppError
from app.main import app
from app.schemas.anuncio import AnuncioFilters, AnuncioListResponse
from app.schemas.anuncio_imagem import AnuncioImagemListResponse, AnuncioImagemResponse


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


async def test_lista_imagens_do_anuncio(monkeypatch: Any) -> None:
    anuncio_id = uuid4()
    imagem_id = uuid4()

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def listar(self, id_recebido: object) -> AnuncioImagemListResponse:
            assert id_recebido == anuncio_id
            return AnuncioImagemListResponse(
                items=[
                    AnuncioImagemResponse(
                        id=imagem_id,
                        anuncio_id=anuncio_id,
                        url=f"/uploads/anuncios/{anuncio_id}/foto.png",
                        nome_original="foto.png",
                        mime_type="image/png",
                        tamanho_bytes=120,
                        ordem=0,
                        criado_em=datetime.now(UTC),
                    )
                ]
            )

    monkeypatch.setattr(anuncios_routes, "AnuncioImagemService", FakeService)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v1/ads/{anuncio_id}/images")

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(imagem_id)
    assert response.json()["items"][0]["ordem"] == 0
