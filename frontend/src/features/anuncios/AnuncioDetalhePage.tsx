import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { buscarCategoria } from '../categorias/categoriaApi'
import type { Categoria } from '../categorias/types'
import { buscarAnuncio, buscarImagensAnuncio } from './anuncioApi'
import type { Anuncio, AnuncioImagem } from './types'

const STATUS_LABEL: Record<Anuncio['status'], string> = {
  ATIVO: 'Disponível',
  ESGOTADO: 'Esgotado',
  ENCERRADO: 'Encerrado',
}

export function AnuncioDetalhePage() {
  const { anuncioId } = useParams()
  const [anuncio, setAnuncio] = useState<Anuncio | null>(null)
  const [categoria, setCategoria] = useState<Categoria | null>(null)
  const [imagens, setImagens] = useState<AnuncioImagem[]>([])
  const [imagemAtiva, setImagemAtiva] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    if (!anuncioId) {
      setErro('Anúncio inválido.')
      setCarregando(false)
      return
    }
    let ativo = true
    setCarregando(true)
    setErro('')
    setAnuncio(null)
    setCategoria(null)
    setImagens([])
    setImagemAtiva('')
    buscarAnuncio(anuncioId)
      .then(async (anuncioRecebido) => {
        if (!ativo) return
        setAnuncio(anuncioRecebido)

        const [resultadoCategoria, resultadoImagens] = await Promise.allSettled([
          buscarCategoria(anuncioRecebido.categoria_id),
          buscarImagensAnuncio(anuncioRecebido.id),
        ])
        if (!ativo) return

        if (resultadoCategoria.status === 'fulfilled') {
          setCategoria(resultadoCategoria.value)
        }
        if (resultadoImagens.status === 'fulfilled') {
          setImagens(resultadoImagens.value)
          const primeiraImagem = resultadoImagens.value[0]?.url
          if (primeiraImagem) setImagemAtiva(resolverUrlDaApi(primeiraImagem))
        }
        if (resultadoImagens.status === 'rejected' || resultadoImagens.value.length === 0) {
          if (anuncioRecebido.imagem_url) {
            setImagemAtiva(resolverUrlDaApi(anuncioRecebido.imagem_url))
          }
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
  }, [anuncioId, tentativa])

  return (
    <main className="ad-detail-page">
      <Link to="/home" className="back-button">
        ← Voltar para os anúncios
      </Link>

      {carregando && <div className="ad-detail-loading">Carregando anúncio…</div>}
      {!carregando && erro && (
        <div className="ad-detail-error">
          <div className="publish-alert" role="alert">
            {erro}
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setTentativa((atual) => atual + 1)}
          >
            Tentar novamente
          </button>
        </div>
      )}

      {!carregando && !erro && anuncio && (
        <div className="ad-detail-grid">
          <div className="ad-detail-card">
            <div className="ad-detail-foto">
              <span className="ad-detail-categoria">{categoria?.nome ?? 'Material'}</span>
              {anuncio.status !== 'ATIVO' && (
                <span className="ad-detail-status">{STATUS_LABEL[anuncio.status]}</span>
              )}
              {imagemAtiva ? (
                <img src={imagemAtiva} alt={`Foto do anúncio ${anuncio.titulo}`} />
              ) : (
                <span className="ad-detail-sem-foto">Sem foto disponível</span>
              )}
            </div>
            {imagens.length > 1 && (
              <div className="ad-detail-miniaturas" aria-label="Fotos do anúncio">
                {imagens.map((imagem, indice) => {
                  const url = resolverUrlDaApi(imagem.url)
                  return (
                    <button
                      key={imagem.id}
                      type="button"
                      className={url === imagemAtiva ? 'ad-detail-miniatura ad-detail-miniatura--ativa' : 'ad-detail-miniatura'}
                      aria-label={`Ver foto ${indice + 1}`}
                      aria-pressed={url === imagemAtiva}
                      onClick={() => setImagemAtiva(url)}
                    >
                      <img src={url} alt="" />
                    </button>
                  )
                })}
              </div>
            )}
            <div className="ad-detail-corpo">
              <h1>{anuncio.titulo}</h1>
              <p className="ad-detail-meta">publicado {formatarTempoRelativo(anuncio.postado_em)}</p>

              <div className="ad-detail-tags">
                <span className="ad-detail-tag">
                  {anuncio.quantidade} {anuncio.quantidade === 1 ? 'unidade disponível' : 'unidades disponíveis'}
                </span>
                <span className="ad-detail-tag">{STATUS_LABEL[anuncio.status]}</span>
              </div>

              <h2>Descrição</h2>
              <p className="ad-detail-descricao">{anuncio.descricao}</p>
            </div>
          </div>

          <div className="ad-detail-lateral">
            <div className="ad-detail-card ad-detail-preco-card">
              <p className="ad-detail-preco-label">Preço por unidade</p>
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
