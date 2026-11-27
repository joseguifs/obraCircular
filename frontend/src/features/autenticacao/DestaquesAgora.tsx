import { useEffect, useState } from 'react'
import { listarAnuncios } from '../anuncios/anuncioApi'
import type { Anuncio } from '../anuncios/types'
import { resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda } from '../../lib/formatarTempo'

/** Quantos anúncios pagos aparecem no painel das telas públicas. */
const MAXIMO_DESTAQUES = 2

const GRADIENTES_PLACEHOLDER = [
  'linear-gradient(140deg,#33526F,#16314B)',
  'linear-gradient(140deg,#4A3B34,#2A211C)',
  'linear-gradient(140deg,#3E4A57,#222B34)',
  'linear-gradient(140deg,#5A4531,#31241A)',
]

function corPlaceholder(id: string): string {
  const soma = Array.from(id).reduce((acumulado, caractere) => acumulado + caractere.charCodeAt(0), 0)
  return GRADIENTES_PLACEHOLDER[soma % GRADIENTES_PLACEHOLDER.length]
}

/**
 * Vitrine paga também antes do login: a listagem de anúncios é pública e devolve os
 * destaques vigentes primeiro. Sem destaque no momento (ou sem conexão), nada aparece.
 */
export function DestaquesAgora() {
  const [destaques, setDestaques] = useState<Anuncio[]>([])

  useEffect(() => {
    let ativo = true
    listarAnuncios({ status: 'ATIVO', limit: 8 })
      .then((resposta) => {
        if (!ativo) return
        const itens = resposta?.items ?? []
        setDestaques(itens.filter((item) => item.em_destaque).slice(0, MAXIMO_DESTAQUES))
      })
      .catch(() => {
        if (ativo) setDestaques([])
      })
    return () => {
      ativo = false
    }
  }, [])

  if (destaques.length === 0) return null

  return (
    <section className="auth-destaques" aria-labelledby="auth-destaques-titulo">
      <header>
        <h2 id="auth-destaques-titulo">Em destaque agora</h2>
        <p>Anúncios pagos pelos vendedores</p>
      </header>
      <ul>
        {destaques.map((item) => {
          const capa = item.imagem_capa_url ?? item.imagem_url
          return (
            <li key={item.id}>
              <span className="auth-destaques-foto" style={{ background: corPlaceholder(item.id) }}>
                {capa && <img src={resolverUrlDaApi(capa)} alt="" />}
              </span>
              <span className="auth-destaques-info">
                <span className="auth-destaques-titulo">{item.titulo}</span>
                <span className="auth-destaques-preco">{formatarMoeda(item.preco)}</span>
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
