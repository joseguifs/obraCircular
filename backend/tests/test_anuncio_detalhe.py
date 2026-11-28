from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anuncio import Anuncio
from app.models.categoria import Categoria
from app.models.endereco import Endereco
from app.models.enums import AnuncioStatus, CategoriaStatus
from app.models.usuario import Usuario
from app.services.anuncio import AnuncioService


async def _criar_anuncio(db_session: AsyncSession) -> UUID:
    async with db_session.begin():
        vendedor = Usuario(
            nome="Carlos Mendes",
            email=f"{uuid4()}@test.invalid",
            senha_hash="hash",
            telefone="63999990000",
        )
        categoria = Categoria(nome=str(uuid4()), status=CategoriaStatus.ATIVA)
        db_session.add_all([vendedor, categoria])
        await db_session.flush()
        endereco = Endereco(
            usuario_id=vendedor.id,
            cep="77001000",
            logradouro="Rua",
            numero="1",
            bairro="Centro",
            cidade="Palmas",
            estado="TO",
        )
        db_session.add(endereco)
        await db_session.flush()
        anuncio = Anuncio(
            vendedor_id=vendedor.id,
            categoria_id=categoria.id,
            endereco_id=endereco.id,
            titulo="Porcelanato 60x60 acetinado",
            descricao="Caixas fechadas do mesmo lote",
            preco=Decimal("89.90"),
            quantidade=22,
            status=AnuncioStatus.ATIVO,
        )
        db_session.add(anuncio)
        await db_session.flush()
        return anuncio.id


async def test_detalhe_traz_o_nome_do_vendedor(db_session: AsyncSession) -> None:
    anuncio_id = await _criar_anuncio(db_session)

    detalhe = await AnuncioService(db_session).buscar_detalhe(anuncio_id)

    assert detalhe.id == anuncio_id
    assert detalhe.vendedor_nome == "Carlos Mendes"
    assert detalhe.titulo == "Porcelanato 60x60 acetinado"


async def test_api_expoe_so_o_nome_do_vendedor(
    db_session: AsyncSession, client: AsyncClient
) -> None:
    anuncio_id = await _criar_anuncio(db_session)

    resposta = await client.get(f"/api/v1/ads/{anuncio_id}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["vendedor_nome"] == "Carlos Mendes"
    assert corpo["em_destaque"] is False
    texto = resposta.text
    assert "@test.invalid" not in texto
    assert "63999990000" not in texto
