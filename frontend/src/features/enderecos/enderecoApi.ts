import { apiRequest, type ListResponse } from '../../lib/api'
import type { Endereco, EnderecoPayload, EnderecoUpdatePayload } from './types'

export function listarMeusEnderecos(offset = 0): Promise<ListResponse<Endereco>> {
  return apiRequest<ListResponse<Endereco>>(
    `/users/me/addresses?limit=10&offset=${offset}`,
  )
}

export async function listarEnderecos(): Promise<Endereco[]> {
  const resposta = await apiRequest<ListResponse<Endereco>>(
    '/users/me/addresses?limit=100',
  )
  return resposta.items
}

export function cadastrarEndereco(dados: EnderecoPayload): Promise<Endereco> {
  return apiRequest<Endereco>('/users/me/addresses', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function atualizarEndereco(
  id: string,
  dados: EnderecoUpdatePayload,
): Promise<Endereco> {
  return apiRequest<Endereco>(`/users/me/addresses/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
}
