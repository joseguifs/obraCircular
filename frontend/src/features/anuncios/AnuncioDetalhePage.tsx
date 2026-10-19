import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { buscarCategoria } from '../categorias/categoriaApi'
import type { Categoria } from '../categorias/types'
import { listarEnderecos } from '../enderecos/enderecoApi'
import type { Endereco } from '../enderecos/types'
import { useAuth } from '../autenticacao/useAuth'
import { createPreferenceCheckout } from '../pagamentos/pagamentoApi'
import { buscarAnuncio, buscarImagensAnuncio } from './anuncioApi'
import { PerguntasAnuncio } from './PerguntasAnuncio'
import type { Anuncio, AnuncioImagem } from './types'

const STATUS_LABEL: Record<Anuncio['status'], string> = {
  ATIVO: 'Disponível',
  ESGOTADO: 'Esgotado',
  ENCERRADO: 'Encerrado',
}

export function AnuncioDetalhePage() {
  const { sessao } = useAuth()
  const { anuncioId } = useParams()
  const [anuncio, setAnuncio] = useState<Anuncio | null>(null)
  const [categoria, setCategoria] = useState<Categoria | null>(null)
  const [imagens, setImagens] = useState<AnuncioImagem[]>([])
  const [imagemAtiva, setImagemAtiva] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [compraErro, setCompraErro] = useState('')
  const [enderecos, setEnderecos] = useState<Endereco[]>([])
  const [quantidade, setQuantidade] = useState(1)
  const [modalidade, setModalidade] = useState<'ENTREGA' | 'RETIRADA'>('ENTREGA')
  const [enderecoId, setEnderecoId] = useState('')
  const [enviando, setEnviando] = useState(false)
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

  useEffect(() => {
    if (!anuncio || anuncio.vendedor_id === sessao?.usuario.id) return
    listarEnderecos()
      .then((items) => {
        setEnderecos(items)
        setEnderecoId((atual) => atual || items[0]?.id || '')
      })
      .catch(() => {
        // Retirada continua disponível mesmo quando não há endereço cadastrado.
      })
  }, [anuncio, sessao?.usuario.id])

  async function comprar() {
    if (!anuncio || enviando) return
    if (modalidade === 'ENTREGA' && !enderecoId) {
      setCompraErro('Cadastre e selecione um endereço ou escolha retirada.')
      return
    }
    setEnviando(true)
    setCompraErro('')
    try {
      const preference = await createPreferenceCheckout(
        {
          anuncio_id: anuncio.id,
          quantidade,
          modalidade_entrega: modalidade,
          endereco_entrega_id: modalidade === 'ENTREGA' ? enderecoId : null,
        },
        '/orders/checkout',
      )
      window.location.assign(preference.init_point)
    } catch (falha) {
      setCompraErro(
        falha instanceof ApiError
          ? falha.message
          : 'Não foi possível iniciar o pagamento.',
      )
      setEnviando(false)
    }
  }

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

              <PerguntasAnuncio anuncio={anuncio} />
            </div>
          </div>

          <div className="ad-detail-lateral">
            <div className="ad-detail-card ad-detail-preco-card">
              <p className="ad-detail-preco-label">Preço por unidade</p>
              <p className="ad-detail-preco">{formatarMoeda(anuncio.preco)}</p>
              <p className="ad-detail-preco-nota">
                Ficou com alguma dúvida? Pergunte ao vendedor na seção de perguntas do anúncio.
                O pagamento é processado em ambiente seguro pelo Mercado Pago.
              </p>
              {anuncio.vendedor_id === sessao?.usuario.id ? (
                <p className="payment-status">Este anúncio pertence a você.</p>
              ) : anuncio.status === 'ATIVO' ? (
                <div className="checkout-form">
                  <label>
                    Quantidade
                    <input
                      type="number"
                      min={1}
                      max={anuncio.quantidade}
                      value={quantidade}
                      onChange={(evento) =>
                        setQuantidade(
                          Math.max(1, Math.min(anuncio.quantidade, Number(evento.target.value))),
                        )
                      }
                    />
                  </label>
                  <label>
                    Recebimento
                    <select
                      value={modalidade}
                      onChange={(evento) =>
                        setModalidade(evento.target.value as 'ENTREGA' | 'RETIRADA')
                      }
                    >
                      <option value="ENTREGA">Entrega</option>
                      <option value="RETIRADA">Retirada com o vendedor</option>
                    </select>
                  </label>
                  {modalidade === 'ENTREGA' && (
                    <label>
                      Endereço de entrega
                      <select value={enderecoId} onChange={(evento) => setEnderecoId(evento.target.value)}>
                        <option value="">Selecione</option>
                        {enderecos.map((endereco) => (
                          <option key={endereco.id} value={endereco.id}>
                            {endereco.logradouro}, {endereco.numero} — {endereco.cidade}/{endereco.estado}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <p className="ad-detail-preco-nota">
                    Total: {formatarMoeda(String(Number(anuncio.preco) * quantidade))}
                  </p>
                  {compraErro && <p className="form-alert" role="alert">{compraErro}</p>}
                  <button
                    type="button"
                    className="submit-button"
                    aria-label="Comprar com Mercado Pago"
                    data-mp-checkout-cta="checkout-pro"
                    data-mp-marketplace-checkout="checkout-pro"
                    disabled={enviando}
                    onClick={comprar}
                  >
                    {enviando ? 'Abrindo Mercado Pago...' : 'Comprar com Mercado Pago'}
                  </button>
                </div>
              ) : null}
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
