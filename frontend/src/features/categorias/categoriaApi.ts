import { apiRequest } from '../../lib/api'
import type {
  Categoria,
  CategoriaAtualizacao,
  CategoriaCriacao,
  FiltroStatus,
  ListaCategorias,
} from './types'

interface ParametrosListagem {
  status: FiltroStatus
  offset: number
  limit: number
}

export function listarCategorias({
  status,
  offset,
  limit,
}: ParametrosListagem): Promise<ListaCategorias> {
  const parametros = new URLSearchParams({ offset: String(offset), limit: String(limit) })
  if (status) parametros.set('status', status)
  return apiRequest<ListaCategorias>(`/categories?${parametros.toString()}`)
}

export function buscarCategoria(categoriaId: string): Promise<Categoria> {
  return apiRequest<Categoria>(`/categories/${categoriaId}`)
}

export function criarCategoria(dados: CategoriaCriacao): Promise<Categoria> {
  return apiRequest<Categoria>('/categories', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
}

export function atualizarCategoria(
  categoriaId: string,
  dados: CategoriaAtualizacao,
): Promise<Categoria> {
  return apiRequest<Categoria>(`/categories/${categoriaId}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
}
