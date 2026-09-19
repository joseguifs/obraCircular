import { apiRequest } from '../../lib/api'
import type {
  Anuncio,
  AnuncioPayload,
  Categoria,
  Endereco,
  EnderecoPayload,
  ListResponse,
} from './types'

export async function listarCategoriasAtivas(): Promise<Categoria[]> {
  const resposta = await apiRequest<ListResponse<Categoria>>(
    '/categories?status=ATIVA&limit=100',
  )
  return resposta.items
}

export async function listarEnderecos(): Promise<Endereco[]> {
  const resposta = await apiRequest<ListResponse<Endereco>>('/users/me/addresses?limit=100')
  return resposta.items
}

export function cadastrarEndereco(dados: EnderecoPayload): Promise<Endereco> {
  return apiRequest<Endereco>('/users/me/addresses', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
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
