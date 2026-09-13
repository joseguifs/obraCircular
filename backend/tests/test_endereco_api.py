from typing import Any
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

import app.api.routes.enderecos as enderecos_routes
from app.core.exceptions import AppError
from app.main import app
from app.schemas.endereco import EnderecoFilters, EnderecoListResponse

DADOS_VALIDOS = {
    "cep": "01001-000",
    "logradouro": "Praça da Sé",
    "numero": "100",
    "bairro": "Sé",
    "cidade": "São Paulo",
    "estado": "sp",
}


def cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_listagem_expoe_paginacao_e_usuario_atual(monkeypatch: Any) -> None:
    chamadas: list[tuple[EnderecoFilters, object]] = []

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def listar(
            self, filtros: EnderecoFilters, usuario_id: object
        ) -> EnderecoListResponse:
            chamadas.append((filtros, usuario_id))
            return EnderecoListResponse(
                items=[], total=0, offset=filtros.offset, limit=filtros.limit
            )

    monkeypatch.setattr(enderecos_routes, "EnderecoService", FakeService)
    usuario_id = uuid4()
    async with cliente() as client:
        response = await client.get(
            "/api/v1/users/me/addresses",
            params={"offset": 5, "limit": 10},
            headers={"X-User-Id": str(usuario_id)},
        )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "offset": 5, "limit": 10}
    assert chamadas[0][0].offset == 5
    assert chamadas[0][1] == usuario_id


async def test_erro_de_dominio_possui_formato_padronizado(monkeypatch: Any) -> None:
    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def buscar(self, *_: object) -> None:
            raise AppError(
                status_code=404,
                detail="Endereço não encontrado.",
                code="ADDRESS_NOT_FOUND",
            )

    monkeypatch.setattr(enderecos_routes, "EnderecoService", FakeService)
    async with cliente() as client:
        response = await client.get(
            f"/api/v1/users/me/addresses/{uuid4()}",
            headers={"X-User-Id": str(uuid4())},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Endereço não encontrado.", "code": "ADDRESS_NOT_FOUND"}


async def test_endpoints_exigem_usuario_atual() -> None:
    async with cliente() as client:
        response = await client.get("/api/v1/users/me/addresses")

    assert response.status_code == 422


async def test_criacao_normaliza_cep_e_estado_antes_do_servico(monkeypatch: Any) -> None:
    recebidos: list[Any] = []

    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def criar(self, dados: Any, usuario_id: Any) -> Any:
            recebidos.append(dados)
            return type(
                "EnderecoFalso",
                (),
                {
                    "id": uuid4(),
                    "usuario_id": usuario_id,
                    "complemento": None,
                    "criado_em": "2026-09-12T00:00:00Z",
                    "atualizado_em": "2026-09-12T00:00:00Z",
                    **dados.model_dump(),
                },
            )()

    monkeypatch.setattr(enderecos_routes, "EnderecoService", FakeService)
    async with cliente() as client:
        response = await client.post(
            "/api/v1/users/me/addresses",
            json=DADOS_VALIDOS,
            headers={"X-User-Id": str(uuid4())},
        )

    assert response.status_code == 201
    assert recebidos[0].cep == "01001000"
    assert recebidos[0].estado == "SP"
    assert response.json()["cep"] == "01001000"


async def test_cep_invalido_retorna_422(monkeypatch: Any) -> None:
    async with cliente() as client:
        response = await client.post(
            "/api/v1/users/me/addresses",
            json={**DADOS_VALIDOS, "cep": "123"},
            headers={"X-User-Id": str(uuid4())},
        )

    assert response.status_code == 422


async def test_exclusao_retorna_204(monkeypatch: Any) -> None:
    class FakeService:
        def __init__(self, _: object) -> None:
            pass

        async def excluir(self, *_: object) -> None:
            return None

    monkeypatch.setattr(enderecos_routes, "EnderecoService", FakeService)
    async with cliente() as client:
        response = await client.delete(
            f"/api/v1/users/me/addresses/{uuid4()}",
            headers={"X-User-Id": str(uuid4())},
        )

    assert response.status_code == 204
