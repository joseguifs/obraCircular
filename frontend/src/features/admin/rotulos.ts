import type { AnuncioStatus, UsuarioStatus } from './types'

export const ROTULOS_STATUS_ANUNCIO: Record<AnuncioStatus, string> = {
  ATIVO: 'Ativo',
  ESGOTADO: 'Esgotado',
  ENCERRADO: 'Encerrado',
}

export const ROTULOS_STATUS_USUARIO: Record<UsuarioStatus, string> = {
  ATIVO: 'Ativo',
  INATIVO: 'Inativo',
  BLOQUEADO: 'Bloqueado',
}

export function formatarData(iso: string): string {
  const data = new Date(iso)
  return Number.isNaN(data.getTime()) ? '—' : data.toLocaleDateString('pt-BR')
}
