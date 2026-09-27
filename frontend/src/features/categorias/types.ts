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

export interface ListaCategorias {
  items: Categoria[]
  total: number
  offset: number
  limit: number
}

export type FiltroStatus = '' | CategoriaStatus

export type ErrosCategoria = Partial<Record<'nome' | 'descricao' | 'geral', string>>
