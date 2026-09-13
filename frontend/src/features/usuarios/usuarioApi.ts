import { apiRequest } from '../../lib/api'
import type { Usuario, UsuarioCreatePayload } from './types'

export function cadastrarUsuario(dados: UsuarioCreatePayload): Promise<Usuario> {
  return apiRequest<Usuario>('/users', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}
