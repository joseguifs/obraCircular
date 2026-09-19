export interface Categoria {
  id: string
  nome: string
  descricao: string | null
  status: 'ATIVA' | 'INATIVA'
}

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
  quantidade: number
  status: 'ATIVO' | 'ESGOTADO' | 'ENCERRADO'
}

export interface ListResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}

export type ErrosAnuncio = Partial<
  Record<'titulo' | 'descricao' | 'categoria' | 'endereco' | 'preco' | 'quantidade' | 'imagens', string>
>
