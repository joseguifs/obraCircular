from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.administrador import Administrador
from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.endereco import Endereco
from app.models.enums import AnuncioStatus

SENHA = "senha-segura-123"


async def _criar_usuario(client: AsyncClient, email: str, nome: str = "Usuário") -> UUID:
    resposta = await client.post(
        "/api/v1/users", json={"nome": nome, "email": email, "senha": SENHA}
    )
    assert resposta.status_code == 201, resposta.text
    return UUID(resposta.json()["id"])


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    resposta = await client.post("/api/v1/auth/login", json={"email": email, "senha": SENHA})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


async def _criar_admin(client: AsyncClient, db_session: AsyncSession) -> tuple[UUID, dict]:
    admin_id = await _criar_usuario(client, "admin@example.com", "Ana Admin")
    db_session.add(Administrador(usuario_id=admin_id))
    await db_session.commit()
    return admin_id, await _headers(client, "admin@example.com")


async def _criar_anuncio(db_session: AsyncSession, vendedor_id: UUID) -> Anuncio:
    categoria = Categoria(nome=f"Categoria {uuid4().hex[:8]}")
    endereco = Endereco(
        usuario_id=vendedor_id,
        cep="01001000",
        logradouro="Praça da Sé",
        numero="1",
        bairro="Sé",
        cidade="São Paulo",
        estado="SP",
    )
    db_session.add_all([categoria, endereco])
    await db_session.flush()
    anuncio = Anuncio(
        titulo="Tijolos baianos",
        descricao="Sobra de obra em bom estado",
        categoria_id=categoria.id,
        vendedor_id=vendedor_id,
        endereco_id=endereco.id,
        preco=Decimal("120.00"),
        quantidade=10,
    )
    db_session.add(anuncio)
    await db_session.commit()
    return anuncio


async def test_rotas_admin_exigem_perfil_administrador(client: AsyncClient) -> None:
    await _criar_usuario(client, "comum@example.com")
    headers = await _headers(client, "comum@example.com")

    sem_login = await client.get("/api/v1/admin/summary")
    sem_perfil = await client.get("/api/v1/admin/summary", headers=headers)

    assert sem_login.status_code == 401
    assert sem_perfil.status_code == 403
    assert sem_perfil.json()["code"] == "FORBIDDEN"


async def test_usuario_atual_informa_perfil_administrador(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await _criar_admin(client, db_session)
    await _criar_usuario(client, "comum@example.com")

    admin = await client.get("/api/v1/auth/me", headers=headers)
    comum = await client.get("/api/v1/auth/me", headers=await _headers(client, "comum@example.com"))

    assert admin.json()["administrador"] is True
    assert comum.json()["administrador"] is False


async def test_resumo_conta_registros_por_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await _criar_admin(client, db_session)
    vendedor_id = await _criar_usuario(client, "vendedor@example.com")
    await _criar_anuncio(db_session, vendedor_id)

    resposta = await client.get("/api/v1/admin/summary", headers=headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["usuarios"]["por_status"]["ATIVO"] >= 2
    assert corpo["anuncios"]["por_status"]["ATIVO"] >= 1
    assert corpo["administradores"] >= 1


async def test_lista_usuarios_com_busca_e_perfil(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_id, headers = await _criar_admin(client, db_session)
    await _criar_usuario(client, "maria.busca@example.com", "Maria Busca")

    resposta = await client.get("/api/v1/admin/users", params={"search": "busca"}, headers=headers)
    admins = await client.get("/api/v1/admin/users", params={"search": "Ana"}, headers=headers)

    assert resposta.status_code == 200
    assert [item["email"] for item in resposta.json()["items"]] == ["maria.busca@example.com"]
    assert resposta.json()["items"][0]["administrador"] is False
    item_admin = next(item for item in admins.json()["items"] if item["id"] == str(admin_id))
    assert item_admin["administrador"] is True


async def test_bloquear_usuario_impede_login(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers = await _criar_admin(client, db_session)
    usuario_id = await _criar_usuario(client, "alvo@example.com")

    resposta = await client.patch(
        f"/api/v1/admin/users/{usuario_id}/status",
        json={"status": "BLOQUEADO"},
        headers=headers,
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "alvo@example.com", "senha": SENHA}
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "BLOQUEADO"
    assert login.status_code == 401


async def test_admin_nao_altera_o_proprio_status_nem_perfil(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin_id, headers = await _criar_admin(client, db_session)

    status = await client.patch(
        f"/api/v1/admin/users/{admin_id}/status",
        json={"status": "INATIVO"},
        headers=headers,
    )
    revogacao = await client.delete(f"/api/v1/admin/users/{admin_id}/admin", headers=headers)

    assert status.status_code == 400
    assert status.json()["code"] == "ADMIN_SELF_STATUS"
    assert revogacao.status_code == 400
    assert revogacao.json()["code"] == "ADMIN_SELF_REVOKE"


async def test_concede_e_revoga_perfil_administrador(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await _criar_admin(client, db_session)
    usuario_id = await _criar_usuario(client, "novo.admin@example.com")
    url = f"/api/v1/admin/users/{usuario_id}/admin"

    concessao = await client.put(url, headers=headers)
    repeticao = await client.put(url, headers=headers)
    acesso = await client.get(
        "/api/v1/admin/summary", headers=await _headers(client, "novo.admin@example.com")
    )
    revogacao = await client.delete(url, headers=headers)

    assert concessao.json()["administrador"] is True
    assert repeticao.status_code == 200
    assert acesso.status_code == 200
    assert revogacao.json()["administrador"] is False


async def test_nao_concede_perfil_a_usuario_inativo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await _criar_admin(client, db_session)
    usuario_id = await _criar_usuario(client, "inativo@example.com")
    await client.patch(
        f"/api/v1/admin/users/{usuario_id}/status", json={"status": "INATIVO"}, headers=headers
    )

    resposta = await client.put(f"/api/v1/admin/users/{usuario_id}/admin", headers=headers)

    assert resposta.status_code == 400
    assert resposta.json()["code"] == "USER_NOT_ACTIVE"


async def test_lista_anuncios_com_vendedor_e_categoria(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await _criar_admin(client, db_session)
    vendedor_id = await _criar_usuario(client, "vendedor@example.com", "Carlos Vendedor")
    anuncio = await _criar_anuncio(db_session, vendedor_id)

    resposta = await client.get("/api/v1/admin/ads", params={"search": "Carlos"}, headers=headers)

    assert resposta.status_code == 200
    item = resposta.json()["items"][0]
    assert item["id"] == str(anuncio.id)
    assert item["vendedor_nome"] == "Carlos Vendedor"
    assert item["categoria_nome"].startswith("Categoria ")


async def test_encerra_e_exclui_anuncio(client: AsyncClient, db_session: AsyncSession) -> None:
    _, headers = await _criar_admin(client, db_session)
    vendedor_id = await _criar_usuario(client, "vendedor@example.com")
    anuncio = await _criar_anuncio(db_session, vendedor_id)
    # O 404 da segunda exclusão desfaz a transação e expira os objetos da sessão.
    anuncio_id = str(anuncio.id)

    encerramento = await client.post(f"/api/v1/admin/ads/{anuncio_id}/close", headers=headers)
    await db_session.refresh(anuncio)
    assert encerramento.status_code == 204
    assert anuncio.status == AnuncioStatus.ENCERRADO
    assert anuncio.encerrado_em is not None

    exclusao = await client.delete(f"/api/v1/admin/ads/{anuncio_id}", headers=headers)
    visivel = await client.get("/api/v1/admin/ads", headers=headers)
    com_excluidos = await client.get(
        "/api/v1/admin/ads", params={"incluir_excluidos": True}, headers=headers
    )
    repeticao = await client.delete(f"/api/v1/admin/ads/{anuncio_id}", headers=headers)

    assert exclusao.status_code == 204
    assert anuncio_id not in [item["id"] for item in visivel.json()["items"]]
    excluido = next(i for i in com_excluidos.json()["items"] if i["id"] == anuncio_id)
    assert excluido["deletado_em"] is not None
    assert repeticao.status_code == 404
