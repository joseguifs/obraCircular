import { apiRequest } from '../../lib/api'
import type { ListResponse } from '../anuncios/types'
import type { Endereco, EnderecoUpdatePayload } from './types'

export function listarMeusEnderecos(offset = 0): Promise<ListResponse<Endereco>> {
  return apiRequest<ListResponse<Endereco>>(
    `/users/me/addresses?limit=10&offset=${offset}`,
  )
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
