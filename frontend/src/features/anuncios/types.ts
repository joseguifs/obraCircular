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
  imagem_capa_url: string | null
  quantidade: number
  status: 'ATIVO' | 'ESGOTADO' | 'ENCERRADO'
  postado_em: string
  atualizado_em: string
  encerrado_em: string | null
}

export interface AnuncioImagem {
  id: string
  anuncio_id: string
  url: string
  nome_original: string
  mime_type: string
  tamanho_bytes: number
  ordem: number
  criado_em: string
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
