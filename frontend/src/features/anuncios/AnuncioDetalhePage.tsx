import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, resolverUrlDaApi } from '../../lib/api'
import { formatarDataHora, formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { obterIniciais } from '../../lib/texto'
import { buscarCategoria } from '../categorias/categoriaApi'
import type { Categoria } from '../categorias/types'
import { listarEnderecos } from '../enderecos/enderecoApi'
import type { Endereco } from '../enderecos/types'
import { useAuth } from '../autenticacao/useAuth'
import { createPreferenceCheckout } from '../pagamentos/pagamentoApi'
import { buscarAnuncio, buscarImagensAnuncio, listarAnuncios } from './anuncioApi'
import { PerguntasAnuncio } from './PerguntasAnuncio'
import type { Anuncio, AnuncioImagem } from './types'
import { DestaqueOferta, SeloDestaque } from './DestaqueOferta'

const STATUS_LABEL: Record<Anuncio['status'], string> = {
  ATIVO: 'Disponível',
  ESGOTADO: 'Esgotado',
  ENCERRADO: 'Encerrado',
}

/** Quantos outros anúncios pagos aparecem no rodapé da página. */
const MAXIMO_OUTROS_DESTAQUES = 4

const GRADIENTES_PLACEHOLDER = [
  'linear-gradient(140deg,#33526F,#16314B)',
  'linear-gradient(140deg,#4A3B34,#2A211C)',
  'linear-gradient(140deg,#3E4A57,#222B34)',
  'linear-gradient(140deg,#5A4531,#31241A)',
  'linear-gradient(140deg,#42566B,#1F2E3E)',
  'linear-gradient(140deg,#4C5358,#262B2F)',
]

function corPlaceholder(id: string): string {
  const soma = Array.from(id).reduce((acumulado, caractere) => acumulado + caractere.charCodeAt(0), 0)
  return GRADIENTES_PLACEHOLDER[soma % GRADIENTES_PLACEHOLDER.length]
}

function textoUnidades(quantidade: number): string {
  return `${quantidade} ${quantidade === 1 ? 'unidade' : 'unidades'}`
}

type Modalidade = 'ENTREGA' | 'RETIRADA'

export function AnuncioDetalhePage() {
  const { sessao } = useAuth()
  const [ofertaAberta, setOfertaAberta] = useState(false)
  const { anuncioId } = useParams()
  const [anuncio, setAnuncio] = useState<Anuncio | null>(null)
  const [categoria, setCategoria] = useState<Categoria | null>(null)
  const [imagens, setImagens] = useState<AnuncioImagem[]>([])
  const [imagemAtiva, setImagemAtiva] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [compraErro, setCompraErro] = useState('')
  const [enderecos, setEnderecos] = useState<Endereco[] | null>(null)
  const [quantidade, setQuantidade] = useState(1)
  const [modalidade, setModalidade] = useState<Modalidade>('ENTREGA')
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
    setQuantidade(1)
    setOfertaAberta(false)
    setCompraErro('')
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

  const ehDono = Boolean(anuncio && anuncio.vendedor_id === sessao?.usuario.id)

  useEffect(() => {
    if (!anuncio || ehDono) return
    listarEnderecos()
      .then((items) => {
        setEnderecos(items)
        setEnderecoId((atual) => atual || items[0]?.id || '')
      })
      .catch(() => {
        // Retirada continua disponível mesmo quando os endereços não carregam.
      })
  }, [anuncio, ehDono])

  function alterarQuantidade(valor: number) {
    if (!anuncio) return
    const inteiro = Number.isFinite(valor) ? Math.trunc(valor) : 1
    setQuantidade(Math.max(1, Math.min(anuncio.quantidade, inteiro)))
  }

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

  const indiceFoto = imagens.findIndex((imagem) => resolverUrlDaApi(imagem.url) === imagemAtiva)
  const nomeCategoria = categoria?.nome ?? 'Material'

  return (
    <main className="ad-detail-page">
      <nav className="ad-detail-trilha" aria-label="Você está em">
        <Link to="/home">Explorar</Link>
        {anuncio && (
          <>
            <span aria-hidden="true">›</span>
            <span>{nomeCategoria}</span>
            <span aria-hidden="true">›</span>
            <span aria-current="page" className="ad-detail-trilha-atual">{anuncio.titulo}</span>
          </>
        )}
      </nav>

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
        <>
          <div className="ad-detail-grid">
            <div className="ad-detail-principal">
              <section className="ad-detail-card ad-detail-galeria" aria-label="Fotos do anúncio">
                <div className="ad-detail-foto">
                  {imagemAtiva ? (
                    <>
                      {/* Fundo desfocado preenche as sobras quando a foto não é 4:3. */}
                      <img src={imagemAtiva} alt="" aria-hidden="true" className="ad-detail-foto-fundo" />
                      <img
                        src={imagemAtiva}
                        alt={`Foto do anúncio ${anuncio.titulo}`}
                        className="ad-detail-foto-imagem"
                      />
                    </>
                  ) : (
                    <span className="ad-detail-sem-foto">Sem foto disponível</span>
                  )}
                  <div className="ad-detail-foto-selos">
                    {anuncio.em_destaque && <SeloDestaque className="ad-detail-selo" />}
                    {anuncio.status !== 'ATIVO' && (
                      <span className="ad-detail-status">{STATUS_LABEL[anuncio.status]}</span>
                    )}
                  </div>
                  {imagens.length > 1 && indiceFoto >= 0 && (
                    <span className="ad-detail-foto-contador">
                      {indiceFoto + 1} / {imagens.length}
                    </span>
                  )}
                </div>
                {imagens.length > 1 && (
                  <div className="ad-detail-miniaturas" role="group" aria-label="Escolher foto">
                    {imagens.map((imagem, indice) => {
                      const url = resolverUrlDaApi(imagem.url)
                      return (
                        <button
                          key={imagem.id}
                          type="button"
                          className="ad-detail-miniatura"
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
              </section>

              <section className="ad-detail-card ad-detail-ficha" aria-labelledby="ad-ficha-titulo">
                <h2 id="ad-ficha-titulo">Ficha do material</h2>
                <dl className="ad-detail-ficha-lista">
                  <div>
                    <dt>Categoria</dt>
                    <dd>{nomeCategoria}</dd>
                  </div>
                  <div>
                    <dt>Disponível</dt>
                    <dd>{textoUnidades(anuncio.quantidade)}</dd>
                  </div>
                  <div>
                    <dt>Situação</dt>
                    <dd>{STATUS_LABEL[anuncio.status]}</dd>
                  </div>
                  <div>
                    <dt>Publicado</dt>
                    <dd>{formatarTempoRelativo(anuncio.postado_em)}</dd>
                  </div>
                </dl>
                <h2>Descrição</h2>
                <p className="ad-detail-descricao">{anuncio.descricao}</p>
              </section>

              <div id="perguntas" className="ad-detail-card ad-detail-perguntas">
                <PerguntasAnuncio anuncio={anuncio} />
              </div>
            </div>

            <aside className="ad-detail-lateral" aria-label="Preço e compra">
              <section
                className={
                  anuncio.em_destaque
                    ? 'ad-detail-card ad-detail-compra ad-detail-compra--destaque'
                    : 'ad-detail-card ad-detail-compra'
                }
              >
                <p className="ad-detail-sobretitulo">{nomeCategoria}</p>
                <h1>{anuncio.titulo}</h1>
                <p className="ad-detail-meta">Publicado {formatarTempoRelativo(anuncio.postado_em)}</p>

                <div className="ad-detail-preco-linha">
                  <p className="ad-detail-preco">{formatarMoeda(anuncio.preco)}</p>
                  <span>por unidade</span>
                </div>

                {ehDono ? (
                  <div className="ad-detail-dono">
                    <p className="payment-status">Este anúncio pertence a você.</p>
                    {anuncio.em_destaque && anuncio.destaque_ate && (
                      <p className="ad-detail-dono-destaque">
                        <SeloDestaque /> até {formatarDataHora(anuncio.destaque_ate)}
                      </p>
                    )}
                    {anuncio.status === 'ATIVO' &&
                      (ofertaAberta ? (
                        <DestaqueOferta
                          anuncioId={anuncio.id}
                          emDestaque={anuncio.em_destaque}
                          destaqueAte={anuncio.destaque_ate}
                          aoFechar={() => setOfertaAberta(false)}
                        />
                      ) : (
                        <button type="button" className="destaque-abrir" onClick={() => setOfertaAberta(true)}>
                          {anuncio.em_destaque ? 'Estender destaque' : 'Destacar anúncio'}
                        </button>
                      ))}
                  </div>
                ) : anuncio.status === 'ATIVO' ? (
                  <div className="ad-detail-checkout">
                    <div className="ad-detail-quantidade">
                      <label htmlFor="ad-quantidade">
                        Quantidade
                        <span>
                          {anuncio.quantidade}{' '}
                          {anuncio.quantidade === 1 ? 'unidade disponível' : 'unidades disponíveis'}
                        </span>
                      </label>
                      <div className="ad-detail-passo">
                        <button
                          type="button"
                          aria-label="Diminuir quantidade"
                          disabled={quantidade <= 1}
                          onClick={() => alterarQuantidade(quantidade - 1)}
                        >
                          −
                        </button>
                        <input
                          id="ad-quantidade"
                          type="number"
                          inputMode="numeric"
                          min={1}
                          max={anuncio.quantidade}
                          value={quantidade}
                          onChange={(evento) => alterarQuantidade(Number(evento.target.value))}
                        />
                        <button
                          type="button"
                          aria-label="Aumentar quantidade"
                          disabled={quantidade >= anuncio.quantidade}
                          onClick={() => alterarQuantidade(quantidade + 1)}
                        >
                          +
                        </button>
                      </div>
                    </div>

                    <div>
                      <span id="ad-recebimento" className="ad-detail-rotulo">Como você quer receber?</span>
                      <div className="ad-detail-recebimento" role="group" aria-labelledby="ad-recebimento">
                        <button
                          type="button"
                          aria-pressed={modalidade === 'ENTREGA'}
                          onClick={() => setModalidade('ENTREGA')}
                        >
                          <strong>Entrega</strong>
                          <span>No seu endereço</span>
                        </button>
                        <button
                          type="button"
                          aria-pressed={modalidade === 'RETIRADA'}
                          onClick={() => setModalidade('RETIRADA')}
                        >
                          <strong>Retirada</strong>
                          <span>Com o vendedor</span>
                        </button>
                      </div>
                    </div>

                    {modalidade === 'ENTREGA' &&
                      (enderecos !== null && enderecos.length === 0 ? (
                        <p className="ad-detail-sem-endereco">
                          Você ainda não tem endereço cadastrado.{' '}
                          <Link to="/perfil/enderecos">Cadastrar endereço</Link>
                        </p>
                      ) : (
                        <label className="ad-detail-campo">
                          Endereço de entrega
                          <select value={enderecoId} onChange={(evento) => setEnderecoId(evento.target.value)}>
                            <option value="">Selecione</option>
                            {(enderecos ?? []).map((endereco) => (
                              <option key={endereco.id} value={endereco.id}>
                                {endereco.logradouro}, {endereco.numero} — {endereco.cidade}/{endereco.estado}
                              </option>
                            ))}
                          </select>
                        </label>
                      ))}

                    <p className="ad-detail-total">
                      <span>Total</span>
                      <strong>{formatarMoeda(String(Number(anuncio.preco) * quantidade))}</strong>
                    </p>
                    {compraErro && <p className="form-alert" role="alert">{compraErro}</p>}
                    <button
                      type="button"
                      className="ad-detail-comprar"
                      aria-label="Comprar com Mercado Pago"
                      data-mp-checkout-cta="checkout-pro"
                      data-mp-marketplace-checkout="checkout-pro"
                      disabled={enviando}
                      onClick={comprar}
                    >
                      {enviando ? 'Abrindo Mercado Pago...' : 'Comprar com Mercado Pago'}
                    </button>
                    <a href="#perguntas" className="ad-detail-duvida">Tirar uma dúvida antes</a>
                  </div>
                ) : (
                  <p className="ad-detail-indisponivel">
                    Este anúncio está {STATUS_LABEL[anuncio.status].toLowerCase()} e não aceita novas compras.
                  </p>
                )}
              </section>

              {!ehDono && (
                <ul className="ad-detail-card ad-detail-protecoes" aria-label="Proteções da compra">
                  <li>
                    <strong>Pagamento pelo Mercado Pago</strong>
                    <span>Você paga no checkout deles, sem passar dados ao vendedor.</span>
                  </li>
                  <li>
                    <strong>Entrega confirmada com PIN</strong>
                    <span>Você só passa o código quando receber o material.</span>
                  </li>
                  <li>
                    <strong>7 dias para contestar</strong>
                    <span>O vendedor só recebe depois da entrega e desse prazo.</span>
                  </li>
                </ul>
              )}

              {!ehDono && anuncio.vendedor_nome && (
                <section className="ad-detail-card ad-detail-vendedor" aria-label="Vendedor">
                  <span className="ad-detail-vendedor-avatar" aria-hidden="true">
                    {obterIniciais(anuncio.vendedor_nome)}
                  </span>
                  <span className="ad-detail-vendedor-texto">
                    <span>Vendido por</span>
                    <strong>{anuncio.vendedor_nome}</strong>
                  </span>
                  <a href="#perguntas" className="ad-detail-vendedor-perguntar">Perguntar</a>
                </section>
              )}
            </aside>
          </div>

          <OutrosDestaques anuncioAtualId={anuncio.id} />
        </>
      )}
    </main>
  )
}

/** Rodapé com outros anúncios pagos: mais uma vitrine para quem comprou o destaque. */
function OutrosDestaques({ anuncioAtualId }: { anuncioAtualId: string }) {
  const [destaques, setDestaques] = useState<Anuncio[]>([])

  useEffect(() => {
    let ativo = true
    // A API devolve os anúncios com destaque vigente primeiro.
    listarAnuncios({ status: 'ATIVO', limit: 12 })
      .then((resposta) => {
        if (!ativo) return
        setDestaques(
          resposta.items
            .filter((item) => item.em_destaque && item.id !== anuncioAtualId)
            .slice(0, MAXIMO_OUTROS_DESTAQUES),
        )
      })
      .catch(() => {
        if (ativo) setDestaques([])
      })
    return () => {
      ativo = false
    }
  }, [anuncioAtualId])

  if (destaques.length === 0) return null

  return (
    <section className="ad-detail-outros" aria-labelledby="ad-outros-titulo">
      <header>
        <h2 id="ad-outros-titulo">Também em destaque</h2>
        <p>Anúncios pagos pelos vendedores.</p>
      </header>
      <ul>
        {destaques.map((item) => {
          const capa = item.imagem_capa_url ?? item.imagem_url
          return (
            <li key={item.id}>
              <Link
                to={`/anuncios/${item.id}`}
                aria-label={`Ver anúncio ${item.titulo} (em destaque)`}
                onClick={() => window.scrollTo({ top: 0 })}
              >
                <span className="ad-detail-outros-foto" style={{ background: corPlaceholder(item.id) }}>
                  {capa && <img src={resolverUrlDaApi(capa)} alt="" />}
                </span>
                <span className="ad-detail-outros-info">
                  <span className="ad-detail-outros-titulo">{item.titulo}</span>
                  <span className="ad-detail-outros-preco">{formatarMoeda(item.preco)}</span>
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
