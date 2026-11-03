from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_admin, get_current_user
from app.core.database import get_db_session
from app.main import app
from app.repositories.administrador import AdministradorRepository
from app.services.contestacao import ContestacaoService


@pytest.fixture
async def api_contestacao():
    session = AsyncMock()

    async def banco_fake():
        yield session

    app.dependency_overrides[get_db_session] = banco_fake
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_rotas_contestacoes_exigem_login_e_perfil(api_contestacao, monkeypatch):
    decisao = {"status": "ACEITA", "resolucao": "Produto danificado."}
    caminho = f"/api/v1/admin/disputes/{uuid4()}/decision"
    assert (await api_contestacao.get("/api/v1/admin/disputes")).status_code == 401
    assert (await api_contestacao.post(caminho, json=decisao)).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    monkeypatch.setattr(AdministradorRepository, "eh_administrador", AsyncMock(return_value=False))
    assert (await api_contestacao.get("/api/v1/admin/disputes")).status_code == 403
    assert (await api_contestacao.post(caminho, json=decisao)).status_code == 403


async def test_listagem_encaminha_filtros(api_contestacao, monkeypatch):
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=uuid4())
    listar = AsyncMock(return_value={"items": [], "total": 0, "offset": 20, "limit": 10})
    monkeypatch.setattr(ContestacaoService, "listar", listar)
    resposta = await api_contestacao.get("/api/v1/admin/disputes?status=ABERTA&offset=20&limit=10")
    assert resposta.status_code == 200
    filtros = listar.await_args.args[0]
    assert filtros.status == "ABERTA"
    assert filtros.offset == 20
    assert filtros.limit == 10
    assert (await api_contestacao.get("/api/v1/admin/disputes?offset=-1")).status_code == 422
    assert (await api_contestacao.get("/api/v1/admin/disputes?status=INVALIDO")).status_code == 422


async def test_decisao_usa_admin_da_sessao(api_contestacao, monkeypatch):
    admin_id, contestacao_id = uuid4(), uuid4()
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(id=admin_id)
    decidir = AsyncMock(
        return_value={
            "id": contestacao_id,
            "pedido_id": uuid4(),
            "anuncio_titulo": "Tijolos",
            "comprador_nome": "Comprador",
            "vendedor_nome": "Vendedor",
            "motivo": "OUTRO",
            "descricao": "Quantidade incorreta.",
            "status": "RECUSADA",
            "criado_em": "2026-10-30T12:00:00Z",
            "resolucao": "Entrega conferida.",
            "resolvida_por": admin_id,
            "resolvida_em": "2026-11-02T12:00:00Z",
            "reembolso_status": None,
            "reembolso_externo_id": None,
        }
    )
    monkeypatch.setattr(ContestacaoService, "decidir", decidir)
    caminho = f"/api/v1/admin/disputes/{contestacao_id}/decision"
    resposta = await api_contestacao.post(
        caminho, json={"status": "RECUSADA", "resolucao": "Entrega conferida."}
    )
    assert resposta.status_code == 200, resposta.text
    assert decidir.await_args.args[0] == contestacao_id
    assert decidir.await_args.args[2] == admin_id
    assert (
        await api_contestacao.post(caminho, json={"status": "RESOLVIDA", "resolucao": "Teste"})
    ).status_code == 422
