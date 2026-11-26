import { apiRequest, type ListResponse } from '../../lib/api'
import type { PerguntaUsuario, TipoPerguntaUsuario } from './types'

export function listarMinhasPerguntas(
  tipo: TipoPerguntaUsuario,
  paginacao: { offset: number; limit: number },
): Promise<ListResponse<PerguntaUsuario>> {
  const parametros = new URLSearchParams({
    tipo,
    offset: String(paginacao.offset),
    limit: String(paginacao.limit),
  })
  return apiRequest<ListResponse<PerguntaUsuario>>(`/users/me/questions?${parametros}`)
}
