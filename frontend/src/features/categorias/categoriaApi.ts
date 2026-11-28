import { apiRequest } from '../../lib/api'
import { criarCacheMemoria } from '../../lib/cacheMemoria'
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

/** Categorias mudam raramente (só pela administração); 5 minutos evitam buscar a cada tela. */
const VALIDADE_CATEGORIAS_MS = 5 * 60_000
const cacheCategoriasAtivas = criarCacheMemoria<Categoria[]>(VALIDADE_CATEGORIAS_MS)
const cacheCategoria = criarCacheMemoria<Categoria>(VALIDADE_CATEGORIAS_MS)

/** Chamado depois de criar ou alterar uma categoria, para esta aba ver a mudança na hora. */
function invalidarCacheDeCategorias() {
  cacheCategoriasAtivas.invalidar()
  cacheCategoria.invalidar()
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
  return cacheCategoria.obter(categoriaId, () => apiRequest<Categoria>(`/categories/${categoriaId}`))
}

export function listarCategoriasAtivas(): Promise<Categoria[]> {
  return cacheCategoriasAtivas.obter('ativas', async () => {
    const resposta = await listarCategorias({ status: 'ATIVA', offset: 0, limit: 100 })
    return resposta.items
  })
}

export async function criarCategoria(dados: CategoriaCriacao): Promise<Categoria> {
  const categoria = await apiRequest<Categoria>('/categories', {
    method: 'POST',
    body: JSON.stringify(dados),
  })
  invalidarCacheDeCategorias()
  return categoria
}

export async function atualizarCategoria(
  categoriaId: string,
  dados: CategoriaAtualizacao,
): Promise<Categoria> {
  const categoria = await apiRequest<Categoria>(`/categories/${categoriaId}`, {
    method: 'PATCH',
    body: JSON.stringify(dados),
  })
  invalidarCacheDeCategorias()
  return categoria
}
