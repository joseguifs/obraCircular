"""Leitura das dimensões das fotos de anúncio e orientação sobre o padrão 4:3.

As fotos fora do padrão são aceitas: o vendedor pode não ter outra melhor. A análise
só gera avisos para a interface orientar o vendedor.
"""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

FOTO_RECOMENDADA = (1200, 900)
FOTO_MINIMA = (640, 480)
PROPORCAO_MAXIMA = 1.9
FORMATOS_ACEITOS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

# Orientações EXIF em que a câmera gravou a foto deitada (a largura real é a altura).
_ORIENTACOES_GIRADAS = {5, 6, 7, 8}
_TAG_ORIENTACAO = 0x0112


@dataclass(frozen=True)
class ImagemAnalisada:
    mime_type: str
    largura: int
    altura: int


@dataclass(frozen=True)
class AvisoDimensao:
    codigo: str
    mensagem: str


def analisar_imagem(conteudo: bytes) -> ImagemAnalisada | None:
    """Confirma que o conteúdo é uma imagem íntegra e retorna o tipo e as dimensões
    como exibidas (já aplicando a rotação EXIF). Retorna None se não for uma imagem
    JPEG, PNG ou WebP válida."""
    try:
        with Image.open(BytesIO(conteudo)) as imagem:
            imagem.verify()
        # verify() invalida o objeto; reabre para ler tamanho e EXIF.
        with Image.open(BytesIO(conteudo)) as imagem:
            mime_type = FORMATOS_ACEITOS.get(imagem.format or "")
            if mime_type is None:
                return None
            largura, altura = imagem.size
            if imagem.getexif().get(_TAG_ORIENTACAO) in _ORIENTACOES_GIRADAS:
                largura, altura = altura, largura
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return None
    return ImagemAnalisada(mime_type=mime_type, largura=largura, altura=altura)


def aviso_de_dimensao(largura: int, altura: int) -> AvisoDimensao | None:
    """Orientação sobre o padrão 4:3 (recomendado 1200 × 900 px, mínimo 640 × 480 px).
    A resposta já traz largura e altura, então a mensagem não repete a medida."""
    minimo = f"{FOTO_MINIMA[0]} × {FOTO_MINIMA[1]} px"
    recomendado = f"{FOTO_RECOMENDADA[0]} × {FOTO_RECOMENDADA[1]} px"

    if max(largura, altura) < FOTO_MINIMA[0] or min(largura, altura) < FOTO_MINIMA[1]:
        return AvisoDimensao(
            codigo="AD_IMAGE_BELOW_MINIMUM",
            mensagem=(
                f"Abaixo do mínimo de {minimo}. A foto foi publicada, mas pode aparecer borrada."
            ),
        )
    proporcao = largura / altura
    if proporcao < 1:
        return AvisoDimensao(
            codigo="AD_IMAGE_PORTRAIT",
            mensagem="A foto está na vertical: na página inicial aparece só a parte central.",
        )
    if proporcao > PROPORCAO_MAXIMA:
        return AvisoDimensao(
            codigo="AD_IMAGE_TOO_WIDE",
            mensagem="A foto é muito larga: as laterais ficam cortadas na página inicial.",
        )
    if largura < FOTO_RECOMENDADA[0] or altura < FOTO_RECOMENDADA[1]:
        return AvisoDimensao(
            codigo="AD_IMAGE_BELOW_RECOMMENDED",
            mensagem=f"Abaixo do recomendado de {recomendado}. Pode perder nitidez ao ampliar.",
        )
    return None
