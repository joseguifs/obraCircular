import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { buscarAnuncio, buscarCategoria } from './anuncioApi'
import type { Anuncio, Categoria } from './types'

const STATUS_LABEL: Record<Anuncio['status'], string> = {
  ATIVO: 'Disponível',
  ESGOTADO: 'Esgotado',
  ENCERRADO: 'Encerrado',
}

export function AnuncioDetalhePage() {
  const { anuncioId } = useParams()
  const [anuncio, setAnuncio] = useState<Anuncio | null>(null)
  const [categoria, setCategoria] = useState<Categoria | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    if (!anuncioId) return
    let ativo = true
    setCarregando(true)
    setErro('')
    buscarAnuncio(anuncioId)
      .then(async (anuncioRecebido) => {
        if (!ativo) return
        setAnuncio(anuncioRecebido)
        try {
          const categoriaRecebida = await buscarCategoria(anuncioRecebido.categoria_id)
          if (ativo) setCategoria(categoriaRecebida)
        } catch {
          // A categoria é só um detalhe visual; a tela funciona sem ela.
        }
      })
      .catch((erroRecebido) => {
        if (!ativo) return
        setErro(
          erroRecebido instanceof ApiError
            ? erroRecebido.message
            : 'Não foi possível carregar este anúncio.',
        )
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [anuncioId])

  return (
    <main className="ad-detail-page">
      <Link to="/home" className="back-button">
        ← Voltar para os anúncios
      </Link>

      {carregando && <div className="ad-detail-loading">Carregando anúncio…</div>}
      {!carregando && erro && (
        <div className="publish-alert" role="alert">
          {erro}
        </div>
      )}

      {!carregando && !erro && anuncio && (
        <div className="ad-detail-grid">
          <div className="ad-detail-card">
            <div className="ad-detail-foto" style={{ background: '#3E4A57' }}>
              <span className="ad-detail-categoria">{categoria?.nome ?? 'Material'}</span>
              {anuncio.status !== 'ATIVO' && (
                <span className="ad-detail-status">{STATUS_LABEL[anuncio.status]}</span>
              )}
              {anuncio.imagem_url && <img src={anuncio.imagem_url} alt="" />}
            </div>
            <div className="ad-detail-corpo">
              <h1>{anuncio.titulo}</h1>
              <p className="ad-detail-meta">publicado {formatarTempoRelativo(anuncio.postado_em)}</p>

              <div className="ad-detail-tags">
                <span className="ad-detail-tag">Quantidade: {anuncio.quantidade}</span>
                <span className="ad-detail-tag">{STATUS_LABEL[anuncio.status]}</span>
              </div>

              <h2>Descrição</h2>
              <p className="ad-detail-descricao">{anuncio.descricao}</p>
            </div>
          </div>

          <div className="ad-detail-lateral">
            <div className="ad-detail-card ad-detail-preco-card">
              <p className="ad-detail-preco-label">Valor total</p>
              <p className="ad-detail-preco">{formatarMoeda(anuncio.preco)}</p>
              <p className="ad-detail-preco-nota">
                As mensagens diretas com o vendedor ainda não estão disponíveis nesta versão.
              </p>
            </div>

            <div className="ad-detail-card ad-detail-destaque">
              <h2>Reaproveitar compensa</h2>
              <p>
                Materiais reaproveitados costumam sair abaixo do preço de loja e evitam
                descarte em caçamba.
              </p>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
