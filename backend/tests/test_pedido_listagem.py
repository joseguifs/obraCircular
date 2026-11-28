from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anuncio import Anuncio
from app.models.anuncio_imagem import AnuncioImagem
from app.models.categoria import Categoria
from app.models.endereco import Endereco
from app.models.enums import (
    AnuncioStatus,
    CategoriaStatus,
    ModalidadeEntrega,
    PedidoStatus,
)
from app.models.pedido import Pedido
from app.models.usuario import Usuario
from app.services.pedido import PedidoService


async def _criar_pedido(
    db_session: AsyncSession, *, com_foto: bool, imagem_legada: str | None = None
) -> tuple[UUID, UUID, UUID]:
    """Cria vendedor, comprador, anúncio e um pedido; devolve (comprador, vendedor, anúncio)."""
    async with db_session.begin():
        vendedor = Usuario(nome="Vendedor", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        comprador = Usuario(nome="Comprador", email=f"{uuid4()}@test.invalid", senha_hash="hash")
        categoria = Categoria(nome=str(uuid4()), status=CategoriaStatus.ATIVA)
        db_session.add_all([vendedor, comprador, categoria])
        await db_session.flush()
        endereco = Endereco(
            usuario_id=vendedor.id,
            cep="01001000",
            logradouro="Rua",
            numero="1",
            bairro="Centro",
            cidade="São Paulo",
            estado="SP",
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
            quantidade=0,
            status=AnuncioStatus.ESGOTADO,
            imagem_url=imagem_legada,
        )
        db_session.add(anuncio)
        await db_session.flush()
        if com_foto:
            db_session.add_all(
                [
                    AnuncioImagem(
                        anuncio_id=anuncio.id,
                        chave_objeto=f"anuncios/{anuncio.id}/capa.webp",
                        nome_original="capa.webp",
                        mime_type="image/webp",
                        tamanho_bytes=100,
                        ordem=0,
                    ),
                    AnuncioImagem(
                        anuncio_id=anuncio.id,
                        chave_objeto=f"anuncios/{anuncio.id}/segunda.webp",
                        nome_original="segunda.webp",
                        mime_type="image/webp",
                        tamanho_bytes=100,
                        ordem=1,
                    ),
                ]
            )
        db_session.add(
            Pedido(
                comprador_id=comprador.id,
                anuncio_id=anuncio.id,
                modalidade_entrega=ModalidadeEntrega.RETIRADA,
                quantidade=2,
                preco_unitario=Decimal("89.90"),
                valor_total=Decimal("179.80"),
                status=PedidoStatus.AGUARDANDO_PAGAMENTO,
            )
        )
        return comprador.id, vendedor.id, anuncio.id


async def test_listagem_do_comprador_traz_o_anuncio_com_a_capa(db_session: AsyncSession) -> None:
    comprador_id, _, anuncio_id = await _criar_pedido(db_session, com_foto=True)

    resposta = await PedidoService(db_session).listar(comprador_id)

    assert resposta.total == 1
    resumo = resposta.items[0].anuncio
    assert resumo is not None
    assert resumo.id == anuncio_id
    assert resumo.titulo == "Porcelanato 60x60 acetinado"
    assert resumo.status == AnuncioStatus.ESGOTADO
    assert resumo.imagem_capa_url == f"/uploads/anuncios/{anuncio_id}/capa.webp"


async def test_sem_fotos_usa_a_imagem_legada_do_anuncio(db_session: AsyncSession) -> None:
    comprador_id, _, _ = await _criar_pedido(
        db_session, com_foto=False, imagem_legada="https://exemplo.test/antiga.png"
    )

    resposta = await PedidoService(db_session).listar(comprador_id)

    resumo = resposta.items[0].anuncio
    assert resumo is not None
    assert resumo.imagem_capa_url == "https://exemplo.test/antiga.png"


async def test_listagem_de_vendas_tambem_traz_o_anuncio(db_session: AsyncSession) -> None:
    _, vendedor_id, anuncio_id = await _criar_pedido(db_session, com_foto=False)

    resposta = await PedidoService(db_session).listar_vendas(vendedor_id)

    resumo = resposta.items[0].anuncio
    assert resumo is not None
    assert resumo.id == anuncio_id
    assert resumo.imagem_capa_url is None
