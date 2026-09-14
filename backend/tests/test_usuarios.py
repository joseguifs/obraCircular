from httpx import AsyncClient

USUARIO_PADRAO = {
    "nome": "Ana Silva",
    "email": "Ana.Silva@Example.com",
    "senha": "senha-forte-123",
    "telefone": "(11) 98765-4321",
}


async def _criar_usuario(client: AsyncClient, **sobrescritas: object) -> dict:
    payload = {**USUARIO_PADRAO, **sobrescritas}
    resposta = await client.post("/api/v1/users", json=payload)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


async def _headers_autenticacao(
    client: AsyncClient,
    *,
    email: str = USUARIO_PADRAO["email"],
    senha: str = USUARIO_PADRAO["senha"],
) -> dict[str, str]:
    resposta = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


async def test_criar_usuario_normaliza_email_telefone_e_omite_senha_hash(
    client: AsyncClient,
) -> None:
    usuario = await _criar_usuario(client)

    assert usuario["email"] == "ana.silva@example.com"
    assert usuario["telefone"] == "+5511987654321"
    assert usuario["status"] == "ATIVO"
    assert "senha" not in usuario
    assert "senha_hash" not in usuario
    assert "deletado_em" not in usuario


async def test_criar_usuario_nome_vazio_e_rejeitado(client: AsyncClient) -> None:
    resposta = await client.post("/api/v1/users", json={**USUARIO_PADRAO, "nome": "   "})
    assert resposta.status_code == 422


async def test_criar_usuario_telefone_invalido_e_rejeitado(client: AsyncClient) -> None:
    resposta = await client.post("/api/v1/users", json={**USUARIO_PADRAO, "telefone": "123"})
    assert resposta.status_code == 422


async def test_criar_usuario_status_invalido_e_rejeitado(client: AsyncClient) -> None:
    resposta = await client.post("/api/v1/users", json={**USUARIO_PADRAO, "status": "REMOVIDO"})
    assert resposta.status_code == 422


async def test_criar_usuario_email_duplicado_sem_diferenciar_maiusculas(
    client: AsyncClient,
) -> None:
    await _criar_usuario(client)

    resposta = await client.post(
        "/api/v1/users",
        json={**USUARIO_PADRAO, "email": "ANA.SILVA@EXAMPLE.COM"},
    )
    assert resposta.status_code == 409


async def test_obter_usuario_por_id(client: AsyncClient) -> None:
    criado = await _criar_usuario(client)
    headers = await _headers_autenticacao(client)

    resposta = await client.get(f"/api/v1/users/{criado['id']}", headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["id"] == criado["id"]


async def test_obter_outro_usuario_retorna_403(client: AsyncClient) -> None:
    await _criar_usuario(client)
    headers = await _headers_autenticacao(client)
    resposta = await client.get(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resposta.status_code == 403


async def test_listar_usuarios_nao_inclui_excluidos(client: AsyncClient) -> None:
    visivel = await _criar_usuario(client, email="visivel@example.com")
    excluido = await _criar_usuario(client, email="excluido@example.com")
    headers_excluido = await _headers_autenticacao(client, email="excluido@example.com")

    resposta_delete = await client.delete(
        f"/api/v1/users/{excluido['id']}", headers=headers_excluido
    )
    assert resposta_delete.status_code == 204

    headers_visivel = await _headers_autenticacao(client, email="visivel@example.com")
    resposta_lista = await client.get("/api/v1/users", headers=headers_visivel)
    assert resposta_lista.status_code == 200
    corpo = resposta_lista.json()
    ids_listados = {item["id"] for item in corpo["items"]}

    assert visivel["id"] in ids_listados
    assert excluido["id"] not in ids_listados


async def test_usuario_excluido_nao_aparece_mais_no_get_por_id(client: AsyncClient) -> None:
    criado = await _criar_usuario(client)
    headers = await _headers_autenticacao(client)

    await client.delete(f"/api/v1/users/{criado['id']}", headers=headers)

    resposta = await client.get(f"/api/v1/users/{criado['id']}", headers=headers)
    assert resposta.status_code == 401


async def test_token_de_usuario_excluido_deixa_de_ser_valido(client: AsyncClient) -> None:
    criado = await _criar_usuario(client)
    headers = await _headers_autenticacao(client)

    primeira = await client.delete(f"/api/v1/users/{criado['id']}", headers=headers)
    segunda = await client.delete(f"/api/v1/users/{criado['id']}", headers=headers)

    assert primeira.status_code == 204
    assert segunda.status_code == 401


async def test_atualizar_usuario_parcial(client: AsyncClient) -> None:
    criado = await _criar_usuario(client)
    headers = await _headers_autenticacao(client)

    resposta = await client.patch(
        f"/api/v1/users/{criado['id']}",
        json={"nome": "Ana Maria Silva"},
        headers=headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Ana Maria Silva"
    assert corpo["status"] == "ATIVO"
    assert corpo["email"] == criado["email"]


async def test_atualizar_usuario_para_email_ja_usado_retorna_409(
    client: AsyncClient,
) -> None:
    await _criar_usuario(client, email="primeiro@example.com")
    segundo = await _criar_usuario(client, email="segundo@example.com")
    headers = await _headers_autenticacao(client, email="segundo@example.com")

    resposta = await client.patch(
        f"/api/v1/users/{segundo['id']}",
        json={"email": "PRIMEIRO@example.com"},
        headers=headers,
    )

    assert resposta.status_code == 409


async def test_atualizar_outro_usuario_retorna_403(client: AsyncClient) -> None:
    await _criar_usuario(client)
    headers = await _headers_autenticacao(client)
    resposta = await client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        json={"nome": "Qualquer"},
        headers=headers,
    )
    assert resposta.status_code == 403


async def test_cadastro_publico_nao_permite_escolher_status(client: AsyncClient) -> None:
    resposta = await client.post(
        "/api/v1/users",
        json={**USUARIO_PADRAO, "status": "ATIVO"},
    )

    assert resposta.status_code == 422


async def test_usuario_nao_pode_alterar_o_proprio_status(client: AsyncClient) -> None:
    criado = await _criar_usuario(client)
    headers = await _headers_autenticacao(client)

    resposta = await client.patch(
        f"/api/v1/users/{criado['id']}",
        json={"status": "BLOQUEADO"},
        headers=headers,
    )

    assert resposta.status_code == 422
