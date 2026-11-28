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
  destaque_ate?: string | null
  /** Só na consulta de um anúncio (`GET /ads/{id}`). */
  vendedor_nome?: string
  em_destaque?: boolean
}

export interface DestaquePreco {
  valor: string
  duracao_dias: number
  moeda: string
}

export interface DestaqueCheckout {
  destaque_id: string
  anuncio_id: string
  preferencia_externa_id: string
  init_point: string
  valor: string
  duracao_dias: number
  checkout_expira_em: string
}

export type StatusDestaque = 'AGUARDANDO_PAGAMENTO' | 'ATIVO' | 'CANCELADO' | 'REEMBOLSADO'

export interface DestaqueCompra {
  id: string
  anuncio_id: string
  valor: string
  duracao_dias: number
  status: StatusDestaque
  status_pagamento:
    | 'CRIADO'
    | 'PENDENTE'
    | 'EM_PROCESSAMENTO'
    | 'APROVADO'
    | 'RECUSADO'
    | 'CANCELADO'
    | 'REEMBOLSADO_PARCIAL'
    | 'REEMBOLSADO'
  metodo: string | null
  checkout_expira_em: string
  aprovado_em: string | null
  inicia_em: string | null
  expira_em: string | null
  cancelado_em: string | null
  criado_em: string
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

/** Orientação do servidor sobre uma foto aceita que foge do padrão 4:3. */
export interface AvisoImagem {
  imagem_id: string
  nome_original: string
  largura: number
  altura: number
  codigo:
    | 'AD_IMAGE_BELOW_MINIMUM'
    | 'AD_IMAGE_PORTRAIT'
    | 'AD_IMAGE_TOO_WIDE'
    | 'AD_IMAGE_BELOW_RECOMMENDED'
  mensagem: string
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

export interface AnuncioPergunta {
  id: string
  anuncio_id: string
  autor_id: string
  pergunta: string
  resposta: string | null
  criado_em: string
  respondido_em: string | null
}
