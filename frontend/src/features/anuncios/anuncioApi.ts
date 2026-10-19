import { apiRequest, type ListResponse } from '../../lib/api'
import type {
  Anuncio,
  AnuncioFiltros,
  AnuncioImagem,
  AnuncioPayload,
  AnuncioPergunta,
} from './types'

export function listarAnuncios(filtros: AnuncioFiltros = {}): Promise<ListResponse<Anuncio>> {
  return apiRequest<ListResponse<Anuncio>>(`/ads${queryString(filtros)}`)
}

export function buscarAnuncio(anuncioId: string): Promise<Anuncio> {
  return apiRequest<Anuncio>(`/ads/${anuncioId}`)
}

export async function buscarImagensAnuncio(anuncioId: string): Promise<AnuncioImagem[]> {
  const resposta = await apiRequest<{ items: AnuncioImagem[] }>(
    `/ads/${anuncioId}/images`,
  )
  return resposta.items
}

export function listarAnunciosDoVendedor(
  vendedorId: string,
  filtros: AnuncioFiltros = {},
): Promise<ListResponse<Anuncio>> {
  return apiRequest<ListResponse<Anuncio>>(`/users/${vendedorId}/ads${queryString(filtros)}`)
}

function queryString(filtros: AnuncioFiltros): string {
  const parametros = new URLSearchParams()
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor === undefined || valor === '') continue
    parametros.set(chave, String(valor))
  }
  const texto = parametros.toString()
  return texto ? `?${texto}` : ''
}

export function criarAnuncio(dados: AnuncioPayload): Promise<Anuncio> {
  return apiRequest<Anuncio>('/ads', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export async function enviarImagens(anuncioId: string, imagens: File[]): Promise<void> {
  const formulario = new FormData()
  imagens.forEach((imagem) => formulario.append('files', imagem))
  await apiRequest(`/ads/${anuncioId}/images`, {
    method: 'POST',
    body: formulario,
  })
}

export function excluirAnuncio(anuncioId: string): Promise<void> {
  return apiRequest<void>(`/ads/${anuncioId}`, { method: 'DELETE' })
}

export function listarPerguntas(
  anuncioId: string,
  paginacao: { offset?: number; limit?: number } = {},
): Promise<ListResponse<AnuncioPergunta>> {
  return apiRequest<ListResponse<AnuncioPergunta>>(
    `/ads/${anuncioId}/questions${queryString(paginacao)}`,
  )
}

export function criarPergunta(anuncioId: string, pergunta: string): Promise<AnuncioPergunta> {
  return apiRequest<AnuncioPergunta>(`/ads/${anuncioId}/questions`, {
    method: 'POST',
    body: JSON.stringify({ pergunta }),
  })
}

export function responderPergunta(
  anuncioId: string,
  perguntaId: string,
  resposta: string,
): Promise<AnuncioPergunta> {
  return apiRequest<AnuncioPergunta>(`/ads/${anuncioId}/questions/${perguntaId}/answer`, {
    method: 'POST',
    body: JSON.stringify({ resposta }),
  })
}
