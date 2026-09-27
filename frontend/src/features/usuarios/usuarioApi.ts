import { apiRequest } from '../../lib/api'
import type { Usuario, UsuarioCreatePayload } from './types'

export function cadastrarUsuario(dados: UsuarioCreatePayload): Promise<Usuario> {
  return apiRequest<Usuario>('/users', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function obterUsuario(id: string): Promise<Usuario> {
  return apiRequest<Usuario>(`/users/${id}`)
}

export function atualizarUsuario(
  id: string,
  dados: { nome: string; email: string; telefone: string | null },
): Promise<Usuario> {
  return apiRequest<Usuario>(`/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
}
