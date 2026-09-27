import type { AnuncioPayload, ErrosAnuncio } from './types'

const TIPOS_IMAGEM = new Set(['image/jpeg', 'image/png', 'image/webp'])
const TAMANHO_MAXIMO = 5 * 1024 * 1024

export function validarAnuncio(
  dados: AnuncioPayload,
  precoInformado: string,
  quantidadeInformada: string,
  imagens: File[],
): ErrosAnuncio {
  const erros: ErrosAnuncio = {}
  if (dados.titulo.length < 3) erros.titulo = 'Informe um título com pelo menos 3 caracteres.'
  if (dados.descricao.length < 10) {
    erros.descricao = 'Descreva o material com pelo menos 10 caracteres.'
  }
  if (!dados.categoria_id) erros.categoria = 'Selecione uma categoria.'
  if (!dados.endereco_id) erros.endereco = 'Selecione o local onde está o material.'
  if (!precoInformado || Number(precoInformado) < 0) erros.preco = 'Informe um preço válido.'
  if (!quantidadeInformada || !Number.isInteger(Number(quantidadeInformada)) || dados.quantidade < 1) {
    erros.quantidade = 'A quantidade deve ser de pelo menos 1.'
  }
  const erroImagens = validarImagens(imagens)
  if (erroImagens) erros.imagens = erroImagens
  return erros
}

export function validarImagens(imagens: File[]): string | undefined {
  if (imagens.length > 5) return 'Selecione no máximo 5 imagens.'
  if (imagens.some((imagem) => !TIPOS_IMAGEM.has(imagem.type))) {
    return 'Use somente imagens JPEG, PNG ou WebP.'
  }
  if (imagens.some((imagem) => imagem.size > TAMANHO_MAXIMO)) {
    return 'Cada imagem deve ter no máximo 5 MB.'
  }
  return undefined
}
