from io import BytesIO

from PIL import Image

from app.services.analise_imagem import analisar_imagem, aviso_de_dimensao


def imagem_bytes(largura: int, altura: int, formato: str = "JPEG", orientacao: int = 1) -> bytes:
    buffer = BytesIO()
    imagem = Image.new("RGB", (largura, altura), (40, 80, 120))
    exif = Image.Exif()
    exif[0x0112] = orientacao
    imagem.save(buffer, format=formato, exif=exif.tobytes())
    return buffer.getvalue()


def test_le_dimensoes_e_tipo_da_imagem() -> None:
    analisada = analisar_imagem(imagem_bytes(1600, 1200))

    assert analisada is not None
    assert (analisada.mime_type, analisada.largura, analisada.altura) == (
        "image/jpeg",
        1600,
        1200,
    )


def test_considera_a_rotacao_gravada_pelo_celular() -> None:
    # Celulares gravam 4032 × 3024 e marcam no EXIF que a foto foi tirada em pé.
    analisada = analisar_imagem(imagem_bytes(1600, 1200, orientacao=6))

    assert analisada is not None
    assert (analisada.largura, analisada.altura) == (1200, 1600)


def test_nao_reconhece_conteudo_que_nao_e_imagem() -> None:
    assert analisar_imagem(b"nao e uma imagem") is None
    assert analisar_imagem(b"\x89PNG\r\n\x1a\nfoto") is None


def test_avisos_seguem_o_padrao_4_3() -> None:
    assert aviso_de_dimensao(1600, 1200) is None
    assert aviso_de_dimensao(1920, 1080) is None
    assert aviso_de_dimensao(1200, 900) is None
    assert aviso_de_dimensao(639, 480).codigo == "AD_IMAGE_BELOW_MINIMUM"  # type: ignore[union-attr]
    assert aviso_de_dimensao(480, 640) is not None
    assert aviso_de_dimensao(480, 640).codigo == "AD_IMAGE_PORTRAIT"  # type: ignore[union-attr]
    assert aviso_de_dimensao(2400, 1000).codigo == "AD_IMAGE_TOO_WIDE"  # type: ignore[union-attr]
    assert aviso_de_dimensao(800, 600).codigo == "AD_IMAGE_BELOW_RECOMMENDED"  # type: ignore[union-attr]
