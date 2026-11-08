"""Fluxo completo de perguntas e respostas usando o banco e a autenticação reais."""

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categoria import Categoria
from app.models.conta_pagamento import ContaPagamento
from app.models.enums import ContaPagamentoStatus

SENHA = "senha-segura-123"


async def _cadastrar_e_entrar(client: AsyncClient, email: str) -> tuple[str, dict[str, str]]:
    cadastro = await client.post(
        "/api/v1/users",
        json={"nome": "Usuário Perguntas", "email": email, "senha": SENHA},
    )
    assert cadastro.status_code == 201, cadastro.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "senha": SENHA})
    assert login.status_code == 200, login.text
    return cadastro.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _criar_anuncio(
    client: AsyncClient, db_session: AsyncSession, headers: dict[str, str]
) -> str:
    # A categoria é criada direto no banco: a rota pública de categorias abre uma
    # transação própria que conflita com a sessão compartilhada usada nos testes.
    categoria = Categoria(nome=f"Categoria {uuid4().hex[:8]}", descricao="Categoria de teste")
    db_session.add(categoria)
    await db_session.commit()
    categoria_id = str(categoria.id)
    endereco = await client.post(
        "/api/v1/users/me/addresses",
        headers=headers,
        json={
            "cep": "77001-000",
            "logradouro": "Quadra 104 Norte",
            "numero": "10",
            "bairro": "Plano Diretor Norte",
            "cidade": "Palmas",
            "estado": "TO",
        },
    )
    assert endereco.status_code == 201, endereco.text
    vendedor_id = UUID(endereco.json()["usuario_id"])
    conta = await db_session.scalar(
        select(ContaPagamento).where(ContaPagamento.usuario_id == vendedor_id)
    )
    if conta is None:
        # Publicar exige uma conta ativa; o teste de perguntas não executa OAuth.
        db_session.add(
            ContaPagamento(
                usuario_id=vendedor_id,
                conta_externa_id=f"vendedor-perguntas-{vendedor_id}",
                status=ContaPagamentoStatus.ATIVA,
            )
        )
    await db_session.commit()
    anuncio = await client.post(
        "/api/v1/ads",
        headers=headers,
        json={
            "titulo": "Telhas cerâmicas",
            "descricao": "Lote de telhas cerâmicas que sobraram da obra.",
            "categoria_id": categoria_id,
            "endereco_id": endereco.json()["id"],
            "preco": "1.80",
            "quantidade": 300,
        },
    )
    assert anuncio.status_code == 201, anuncio.text
    return str(anuncio.json()["id"])


async def test_fluxo_completo_de_pergunta_e_resposta(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, vendedor = await _cadastrar_e_entrar(client, "vendedor-perguntas@example.com")
    comprador_id, comprador = await _cadastrar_e_entrar(client, "comprador-perguntas@example.com")
    anuncio_id = await _criar_anuncio(client, db_session, vendedor)
    base = f"/api/v1/ads/{anuncio_id}/questions"

    sem_login = await client.post(base, json={"pergunta": "Ainda tem?"})
    assert sem_login.status_code == 401

    propria = await client.post(base, headers=vendedor, json={"pergunta": "Teste próprio?"})
    assert propria.status_code == 403
    assert propria.json()["code"] == "QUESTION_OWN_AD"

    criada = await client.post(
        base, headers=comprador, json={"pergunta": "  Entregam no Plano Diretor Sul?  "}
    )
    assert criada.status_code == 201, criada.text
    pergunta = criada.json()
    assert pergunta["pergunta"] == "Entregam no Plano Diretor Sul?"
    assert pergunta["autor_id"] == comprador_id
    assert pergunta["resposta"] is None
    assert pergunta["respondido_em"] is None

    resposta_url = f"{base}/{pergunta['id']}/answer"
    negada = await client.post(resposta_url, headers=comprador, json={"resposta": "Sim"})
    assert negada.status_code == 403
    assert negada.json()["code"] == "QUESTION_ANSWER_FORBIDDEN"

    respondida = await client.post(
        resposta_url, headers=vendedor, json={"resposta": "Entregamos, sim. Frete a combinar."}
    )
    assert respondida.status_code == 200, respondida.text
    assert respondida.json()["resposta"] == "Entregamos, sim. Frete a combinar."
    assert respondida.json()["respondido_em"] is not None

    duplicada = await client.post(resposta_url, headers=vendedor, json={"resposta": "De novo"})
    assert duplicada.status_code == 409
    assert duplicada.json()["code"] == "QUESTION_ALREADY_ANSWERED"

    await client.post(base, headers=comprador, json={"pergunta": "Aceitam Pix?"})
    lista = await client.get(base)
    assert lista.status_code == 200
    corpo = lista.json()
    assert corpo["total"] == 2
    # Dentro da transação do teste o `now()` é igual para as duas perguntas, por isso a
    # verificação não depende da ordem (em produção a mais recente vem primeiro).
    respostas = {item["pergunta"]: item["resposta"] for item in corpo["items"]}
    assert respostas == {
        "Aceitam Pix?": None,
        "Entregam no Plano Diretor Sul?": "Entregamos, sim. Frete a combinar.",
    }


async def test_pergunta_de_outro_anuncio_nao_pode_ser_respondida(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, vendedor = await _cadastrar_e_entrar(client, "vendedor-dois-anuncios@example.com")
    _, comprador = await _cadastrar_e_entrar(client, "comprador-dois-anuncios@example.com")
    anuncio_a = await _criar_anuncio(client, db_session, vendedor)
    anuncio_b = await _criar_anuncio(client, db_session, vendedor)

    criada = await client.post(
        f"/api/v1/ads/{anuncio_a}/questions", headers=comprador, json={"pergunta": "Tem nota?"}
    )
    pergunta_id = criada.json()["id"]

    resposta = await client.post(
        f"/api/v1/ads/{anuncio_b}/questions/{pergunta_id}/answer",
        headers=vendedor,
        json={"resposta": "Tem sim"},
    )
    assert resposta.status_code == 404
    assert resposta.json()["code"] == "QUESTION_NOT_FOUND"


async def test_anuncio_encerrado_bloqueia_novas_perguntas(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, vendedor = await _cadastrar_e_entrar(client, "vendedor-encerrado@example.com")
    _, comprador = await _cadastrar_e_entrar(client, "comprador-encerrado@example.com")
    anuncio_id = await _criar_anuncio(client, db_session, vendedor)
    encerrar = await client.patch(
        f"/api/v1/ads/{anuncio_id}", headers=vendedor, json={"status": "ENCERRADO"}
    )
    assert encerrar.status_code == 200, encerrar.text

    resposta = await client.post(
        f"/api/v1/ads/{anuncio_id}/questions", headers=comprador, json={"pergunta": "Ainda tem?"}
    )
    assert resposta.status_code == 400
    assert resposta.json()["code"] == "AD_CLOSED"


async def test_listar_perguntas_de_anuncio_inexistente_retorna_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resposta = await client.get(f"/api/v1/ads/{uuid4()}/questions")
    assert resposta.status_code == 404
    assert resposta.json()["code"] == "AD_NOT_FOUND"
