import type { ListResponse } from '../../lib/api'
import type { Anuncio } from '../anuncios/types'
import type { Usuario } from '../usuarios/types'

export type UsuarioStatus = Usuario['status']
export type AnuncioStatus = Anuncio['status']

export interface ContagemPorStatus {
  total: number
  por_status: Record<string, number>
}

export interface ResumoAdmin {
  usuarios: ContagemPorStatus
  anuncios: ContagemPorStatus
  categorias: ContagemPorStatus
  administradores: number
}

export interface UsuarioAdmin extends Usuario {
  administrador: boolean
  deletado_em: string | null
}

export interface AnuncioAdmin {
  id: string
  titulo: string
  preco: string
  quantidade: number
  status: AnuncioStatus
  categoria_id: string
  categoria_nome: string
  vendedor_id: string
  vendedor_nome: string
  vendedor_email: string
  imagem_capa_url: string | null
  postado_em: string
  atualizado_em: string
  encerrado_em: string | null
  deletado_em: string | null
}

export type ListaUsuariosAdmin = ListResponse<UsuarioAdmin>
export type ListaAnunciosAdmin = ListResponse<AnuncioAdmin>

export interface FiltrosUsuariosAdmin {
  status: '' | UsuarioStatus
  busca: string
  incluirExcluidos: boolean
  offset: number
  limit: number
}

export interface FiltrosAnunciosAdmin {
  status: '' | AnuncioStatus
  busca: string
  incluirExcluidos: boolean
  offset: number
  limit: number
}
