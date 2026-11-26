/**
 * Padrão das fotos de anúncio. A página inicial e o detalhe exibem as fotos em 4:3
 * na horizontal, então é esse o formato que orientamos na publicação.
 */
export const PROPORCAO_FOTO = 4 / 3
export const FOTO_RECOMENDADA = { largura: 1200, altura: 900 }
/** Abaixo disso a foto fica borrada mesmo na miniatura. É aceita, mas com aviso. */
export const FOTO_MINIMA = { largura: 640, altura: 480 }

export interface Dimensoes {
  largura: number
  altura: number
}

/**
 * Lê largura e altura reais do arquivo, já considerando a rotação gravada pelo
 * celular (EXIF). Retorna null quando o navegador não consegue ler a imagem.
 */
export async function lerDimensoes(arquivo: File): Promise<Dimensoes | null> {
  if (typeof createImageBitmap !== 'function') return null
  try {
    const bitmap = await createImageBitmap(arquivo, { imageOrientation: 'from-image' })
    const dimensoes = { largura: bitmap.width, altura: bitmap.height }
    bitmap.close()
    return dimensoes
  } catch {
    return null
  }
}

/** A regra mínima vale para qualquer orientação: compara lado maior e lado menor. */
export function abaixoDoMinimo({ largura, altura }: Dimensoes): boolean {
  return (
    Math.max(largura, altura) < FOTO_MINIMA.largura ||
    Math.min(largura, altura) < FOTO_MINIMA.altura
  )
}

/**
 * Orientação para o vendedor, sem bloquear a publicação: ele pode não ter foto melhor.
 * Mesmas regras do backend (docs/domain/anuncio.md).
 */
export function avisoDaFoto(dimensoes: Dimensoes): string | undefined {
  const { largura, altura } = dimensoes
  if (abaixoDoMinimo(dimensoes)) {
    return `Abaixo do mínimo de ${FOTO_MINIMA.largura} × ${FOTO_MINIMA.altura} px: pode aparecer borrada. Se tiver uma foto maior, prefira ela.`
  }
  const proporcao = largura / altura
  if (proporcao < 1) return 'Foto na vertical: na página inicial aparece só a parte central.'
  if (proporcao > 1.9) return 'Foto muito larga: as laterais ficam cortadas na página inicial.'
  if (largura < FOTO_RECOMENDADA.largura || altura < FOTO_RECOMENDADA.altura) {
    return `Abaixo de ${FOTO_RECOMENDADA.largura} × ${FOTO_RECOMENDADA.altura} px: pode perder nitidez ao ampliar.`
  }
  return undefined
}

export function descreverDimensoes({ largura, altura }: Dimensoes): string {
  return `${largura} × ${altura} px`
}
