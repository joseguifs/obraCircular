import type { ListResponse } from '../../lib/api'

export type CategoriaStatus = 'ATIVA' | 'INATIVA'

export interface Categoria {
  id: string
  nome: string
  descricao: string | null
  status: CategoriaStatus
  criado_em: string
  atualizado_em: string
}

export interface CategoriaCriacao {
  nome: string
  descricao?: string
}

export interface CategoriaAtualizacao {
  nome?: string
  descricao?: string | null
  status?: CategoriaStatus
}

export type ListaCategorias = ListResponse<Categoria>

export type FiltroStatus = '' | CategoriaStatus

export type ErrosCategoria = Partial<Record<'nome' | 'descricao' | 'geral', string>>
