import { apiRequest } from '../../lib/api'
import type {
  FiltrosAnunciosAdmin,
  FiltrosUsuariosAdmin,
  ListaAnunciosAdmin,
  ListaUsuariosAdmin,
  ResumoAdmin,
  UsuarioAdmin,
  UsuarioStatus,
} from './types'

export function obterResumoAdmin(): Promise<ResumoAdmin> {
  return apiRequest<ResumoAdmin>('/admin/summary')
}

export function listarUsuariosAdmin(filtros: FiltrosUsuariosAdmin): Promise<ListaUsuariosAdmin> {
  return apiRequest<ListaUsuariosAdmin>(`/admin/users?${parametrosListagem(filtros)}`)
}

export function alterarStatusUsuario(
  usuarioId: string,
  status: UsuarioStatus,
): Promise<UsuarioAdmin> {
  return apiRequest<UsuarioAdmin>(`/admin/users/${usuarioId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export function definirAdministrador(
  usuarioId: string,
  administrador: boolean,
): Promise<UsuarioAdmin> {
  return apiRequest<UsuarioAdmin>(`/admin/users/${usuarioId}/admin`, {
    method: administrador ? 'PUT' : 'DELETE',
  })
}

export function listarAnunciosAdmin(filtros: FiltrosAnunciosAdmin): Promise<ListaAnunciosAdmin> {
  return apiRequest<ListaAnunciosAdmin>(`/admin/ads?${parametrosListagem(filtros)}`)
}

export function encerrarAnuncioAdmin(anuncioId: string): Promise<void> {
  return apiRequest<void>(`/admin/ads/${anuncioId}/close`, { method: 'POST' })
}

export function excluirAnuncioAdmin(anuncioId: string): Promise<void> {
  return apiRequest<void>(`/admin/ads/${anuncioId}`, { method: 'DELETE' })
}

function parametrosListagem(filtros: FiltrosUsuariosAdmin | FiltrosAnunciosAdmin): string {
  const parametros = new URLSearchParams({
    offset: String(filtros.offset),
    limit: String(filtros.limit),
  })
  if (filtros.status) parametros.set('status', filtros.status)
  if (filtros.busca.trim()) parametros.set('search', filtros.busca.trim())
  if (filtros.incluirExcluidos) parametros.set('incluir_excluidos', 'true')
  return parametros.toString()
}
