import type { Anuncio, AnuncioPergunta } from '../anuncios/types'

/** FEITAS: perguntas do usuário em anúncios de outros. RECEBIDAS: perguntas nos anúncios dele. */
export type TipoPerguntaUsuario = 'FEITAS' | 'RECEBIDAS'

export interface PerguntaUsuario extends AnuncioPergunta {
  anuncio: {
    id: string
    titulo: string
    status: Anuncio['status']
    imagem_capa_url: string | null
  }
}
