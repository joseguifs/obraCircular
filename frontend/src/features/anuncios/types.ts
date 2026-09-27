export type { Categoria } from '../categorias/types'

export interface Endereco {
  id: string
  cep: string
  logradouro: string
  numero: string
  complemento: string | null
  bairro: string
  cidade: string
  estado: string
}

export interface EnderecoPayload {
  cep: string
  logradouro: string
  numero: string
  complemento?: string
  bairro: string
  cidade: string
  estado: string
}

export interface AnuncioPayload {
  titulo: string
  descricao: string
  categoria_id: string
  endereco_id: string
  preco: string
  quantidade: number
}

export interface Anuncio {
  id: string
  titulo: string
  descricao: string
  categoria_id: string
  vendedor_id: string
  endereco_id: string
  preco: string
  imagem_url: string | null
  quantidade: number
  status: 'ATIVO' | 'ESGOTADO' | 'ENCERRADO'
  postado_em: string
  atualizado_em: string
  encerrado_em: string | null
}

export interface ListResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}

export interface AnuncioFiltros {
  category_id?: string
  status?: 'ATIVO' | 'ESGOTADO' | 'ENCERRADO'
  search?: string
  min_price?: string
  max_price?: string
  offset?: number
  limit?: number
}

export type ErrosAnuncio = Partial<
  Record<'titulo' | 'descricao' | 'categoria' | 'endereco' | 'preco' | 'quantidade' | 'imagens', string>
>
