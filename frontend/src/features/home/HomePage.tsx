import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { listarAnuncios, listarAnunciosDoVendedor } from '../anuncios/anuncioApi'
import type { Anuncio } from '../anuncios/types'
import { listarCategoriasAtivas } from '../categorias/categoriaApi'
import type { Categoria } from '../categorias/types'
import { ApiError, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { useRolagemHorizontal } from '../../lib/useRolagemHorizontal'
import { useAuth } from '../autenticacao/useAuth'
import { DestaqueDialog } from '../anuncios/DestaqueDialog'
import { SeloDestaque } from '../anuncios/DestaqueOferta'

/** Quantos anúncios pagos cabem na vitrine do topo; os demais seguem na grade. */
const MAXIMO_VITRINE = 5
/** Tempo de exibição de cada anúncio na vitrine antes de passar ao próximo. */
const INTERVALO_VITRINE_MS = 6000

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

function imagemCapa(anuncio: Anuncio): string | null {
  const url = anuncio.imagem_capa_url ?? anuncio.imagem_url
  return url ? resolverUrlDaApi(url) : null
}

function textoQuantidade(quantidade: number): string {
  return `${quantidade} ${quantidade === 1 ? 'unidade disponível' : 'unidades disponíveis'}`
}

/** Sigla de duas letras da categoria, no estilo do código de lote de material. */
function siglaCategoria(nome: string): string {
  const palavras = nome.trim().split(/\s+/).filter((palavra) => palavra.length > 2)
  if (palavras.length >= 2) return (palavras[0][0] + palavras[1][0]).toUpperCase()
  const unica = palavras[0] ?? nome.trim()
  return (unica.slice(0, 1).toUpperCase() + unica.slice(1, 2).toLowerCase()) || '—'
}

export function HomePage() {
  const { sessao } = useAuth()
  const usuario = sessao!.usuario
  const [searchParams] = useSearchParams()
  const buscaUrl = searchParams.get('q') ?? ''

  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [categoriaId, setCategoriaId] = useState<string | null>(null)
  const [buscaAtiva, setBuscaAtiva] = useState(buscaUrl)
  const [anuncios, setAnuncios] = useState<Anuncio[]>([])
  const [totalDisponiveis, setTotalDisponiveis] = useState(0)
  // Só quem tem anúncio disponível vê o convite para destacar.
  const [totalMeusAtivos, setTotalMeusAtivos] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  // undefined = janela fechada; null = escolher na lista; Anuncio = já escolhido.
  const [destacar, setDestacar] = useState<Anuncio | null | undefined>(undefined)
  const fecharDestaque = useCallback(() => setDestacar(undefined), [])
  const abrirEscolhaDestaque = useCallback(() => setDestacar(null), [])
  const { ref: categoriasRef, atributos: categoriasRolagem } = useRolagemHorizontal<HTMLDivElement>()

  useEffect(() => {
    const temporizador = window.setTimeout(() => setBuscaAtiva(buscaUrl), 350)
    return () => window.clearTimeout(temporizador)
  }, [buscaUrl])

  useEffect(() => {
    listarCategoriasAtivas()
      .then(setCategorias)
      .catch(() => setCategorias([]))
  }, [])

  useEffect(() => {
    listarAnunciosDoVendedor(usuario.id, { status: 'ATIVO', limit: 1 })
      .then((resposta) => setTotalMeusAtivos(resposta.total))
      .catch(() => setTotalMeusAtivos(0))
  }, [usuario.id])

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    setErro('')
    listarAnuncios({
      status: 'ATIVO',
      category_id: categoriaId ?? undefined,
      search: buscaAtiva || undefined,
      limit: 24,
    })
      .then((resposta) => {
        if (!ativo) return
        setAnuncios(resposta.items)
        setTotalDisponiveis(resposta.total)
      })
      .catch((erroRecebido) => {
        if (!ativo) return
        setErro(
          erroRecebido instanceof ApiError
            ? erroRecebido.message
            : 'Não foi possível carregar os anúncios.',
        )
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [categoriaId, buscaAtiva])

  const categoriasPorId = useMemo(
    () => new Map(categorias.map((categoria) => [categoria.id, categoria.nome])),
    [categorias],
  )

  const filtrando = Boolean(buscaAtiva || categoriaId)
  const temAnunciosAtivos = totalMeusAtivos > 0

  // Sem filtro, os anúncios pagos (que a API já devolve primeiro) sobem para a vitrine
  // do topo e saem da grade, para não aparecerem duas vezes.
  const vitrine = useMemo(
    () => (filtrando ? [] : anuncios.filter((anuncio) => anuncio.em_destaque).slice(0, MAXIMO_VITRINE)),
    [anuncios, filtrando],
  )
  const grade = useMemo(() => {
    const naVitrine = new Set(vitrine.map((anuncio) => anuncio.id))
    return anuncios.filter((anuncio) => !naVitrine.has(anuncio.id))
  }, [anuncios, vitrine])

  const resumoBusca = carregando
    ? 'Carregando anúncios…'
    : totalDisponiveis === 0
      ? 'Nada encontrado com esses filtros.'
      : `${totalDisponiveis} ${totalDisponiveis === 1 ? 'anúncio' : 'anúncios'} ${
          filtrando
            ? totalDisponiveis === 1 ? 'encontrado' : 'encontrados'
            : 'à venda agora'
        }.`

  return (
    <main className="home-main">
      {!filtrando && !erro && (
        carregando ? (
          <div className="home-vitrine home-vitrine--carregando" aria-hidden="true" />
        ) : vitrine.length > 0 ? (
          <VitrineDestaque
            anuncios={vitrine}
            categoriasPorId={categoriasPorId}
            podeDestacar={temAnunciosAtivos}
            aoDestacar={abrirEscolhaDestaque}
          />
        ) : (
          <VitrineVazia podeDestacar={temAnunciosAtivos} aoDestacar={abrirEscolhaDestaque} />
        )
      )}

      <section className="home-categorias" aria-labelledby="home-categorias-titulo">
        <h2 id="home-categorias-titulo" className="home-secao-titulo">Explore por categoria</h2>
        <div
          ref={categoriasRef}
          className="home-categorias-lista rolagem-horizontal"
          role="group"
          aria-label="Filtrar por categoria"
          {...categoriasRolagem}
        >
          <button
            type="button"
            className="home-categoria"
            aria-pressed={categoriaId === null}
            onClick={() => setCategoriaId(null)}
          >
            <span className="home-categoria-sigla" aria-hidden="true">✱</span>
            <span className="home-categoria-nome">Todas</span>
          </button>
          {categorias.map((categoria) => (
            <button
              key={categoria.id}
              type="button"
              className="home-categoria"
              aria-pressed={categoriaId === categoria.id}
              onClick={() => setCategoriaId(categoria.id)}
            >
              <span className="home-categoria-sigla" aria-hidden="true">{siglaCategoria(categoria.nome)}</span>
              <span className="home-categoria-nome">{categoria.nome}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="home-resultados" aria-labelledby="home-resultados-titulo">
        <header className="home-resultados-cabecalho">
          <h1 id="home-resultados-titulo">
            {buscaAtiva ? `Resultados para “${buscaAtiva}”` : 'Materiais disponíveis'}
          </h1>
          <p aria-live="polite">{resumoBusca}</p>
        </header>

        {erro && <div className="home-alert" role="alert">{erro}</div>}

        {!erro && !carregando && anuncios.length === 0 && (
          <div className="home-vazio">
            <p className="home-vazio-titulo">Nenhum anúncio encontrado</p>
            <p>Ajuste a busca ou escolha outra categoria.</p>
          </div>
        )}

        <ul className="home-lista">
          {grade.map((anuncio) => (
            <CartaoAnuncio
              key={anuncio.id}
              anuncio={anuncio}
              categoria={categoriasPorId.get(anuncio.categoria_id)}
              meu={anuncio.vendedor_id === usuario.id && anuncio.status === 'ATIVO'}
              aoDestacar={() => setDestacar(anuncio)}
            />
          ))}
        </ul>
      </section>

      <FaixaVender podeDestacar={temAnunciosAtivos} aoDestacar={abrirEscolhaDestaque} />

      <ul className="home-garantias" aria-label="Como a Obra Circular protege a negociação">
        <li>
          <strong>Pagamento pelo Mercado Pago</strong>
          <span>Você paga no checkout do Mercado Pago, sem passar dados ao vendedor.</span>
        </li>
        <li>
          <strong>Entrega confirmada com PIN</strong>
          <span>O comprador só libera o código quando recebe o material.</span>
        </li>
        <li>
          <strong>7 dias para contestar</strong>
          <span>O vendedor recebe só depois da entrega e do prazo de contestação.</span>
        </li>
        <li>
          <strong>Pergunte antes de comprar</strong>
          <span>Tire dúvidas com o vendedor direto na página do anúncio.</span>
        </li>
      </ul>

      {destacar !== undefined && <DestaqueDialog anuncio={destacar} aoFechar={fecharDestaque} />}
    </main>
  )
}

interface VitrineDestaqueProps {
  anuncios: Anuncio[]
  categoriasPorId: Map<string, string>
  podeDestacar: boolean
  aoDestacar: () => void
}

/**
 * Vitrine paga do topo da página: o anúncio da vez ocupa o espaço mais nobre da home
 * e os demais pagantes ficam enfileirados ao lado, revezando sozinhos para que todos
 * recebam a mesma exposição.
 */
function VitrineDestaque({ anuncios, categoriasPorId, podeDestacar, aoDestacar }: VitrineDestaqueProps) {
  const [indice, setIndice] = useState(0)
  const [pausado, setPausado] = useState(false)
  const reduzirMovimento = usePrefereMenosMovimento()
  const ativo = anuncios[Math.min(indice, anuncios.length - 1)]
  const varios = anuncios.length > 1

  useEffect(() => {
    if (!varios || pausado || reduzirMovimento) return
    const temporizador = window.setInterval(
      () => setIndice((atual) => (atual + 1) % anuncios.length),
      INTERVALO_VITRINE_MS,
    )
    return () => window.clearInterval(temporizador)
  }, [anuncios.length, varios, pausado, reduzirMovimento])

  const capa = imagemCapa(ativo)
  const categoria = categoriasPorId.get(ativo.categoria_id)

  return (
    <section
      className={varios ? 'home-vitrine' : 'home-vitrine home-vitrine--unico'}
      aria-labelledby="home-vitrine-titulo"
      aria-roledescription="vitrine"
      onMouseEnter={() => setPausado(true)}
      onMouseLeave={() => setPausado(false)}
      onFocus={() => setPausado(true)}
      onBlur={(evento) => {
        if (!evento.currentTarget.contains(evento.relatedTarget as Node | null)) setPausado(false)
      }}
    >
      <header className="home-vitrine-cabecalho">
        <h2 id="home-vitrine-titulo">Vitrine em destaque</h2>
        <p>Anúncios pagos pelos vendedores para aparecer aqui primeiro.</p>
        {podeDestacar && (
          <button type="button" className="home-vitrine-convite" onClick={aoDestacar}>
            Quero meu anúncio aqui
          </button>
        )}
      </header>

      <div className="home-vitrine-corpo">
        <Link
          key={ativo.id}
          to={`/anuncios/${ativo.id}`}
          className="home-vitrine-principal"
          aria-label={`Ver anúncio ${ativo.titulo} (em destaque)`}
        >
          <div className="home-vitrine-foto" style={{ background: corPlaceholder(ativo.id) }}>
            {capa ? (
              <img src={capa} alt={`Foto de ${ativo.titulo}`} className="home-vitrine-imagem" />
            ) : (
              <span className="home-vitrine-foto-legenda">Sem foto ainda</span>
            )}
            <SeloDestaque className="home-vitrine-selo" />
          </div>
          <div className="home-vitrine-info">
            {categoria && <p className="home-vitrine-categoria">{categoria}</p>}
            <h3>{ativo.titulo}</h3>
            <p className="home-vitrine-preco">
              <strong>{formatarMoeda(ativo.preco)}</strong>
              <span> por unidade</span>
            </p>
            <p className="home-vitrine-quantidade">{textoQuantidade(ativo.quantidade)}</p>
            <span className="home-vitrine-acao" aria-hidden="true">
              Ver anúncio <span className="home-seta">→</span>
            </span>
          </div>
          {varios && !pausado && !reduzirMovimento && (
            <span
              key={`${ativo.id}-progresso`}
              className="home-vitrine-progresso"
              style={{ animationDuration: `${INTERVALO_VITRINE_MS}ms` }}
              aria-hidden="true"
            />
          )}
        </Link>

        {varios && (
          <ol className="home-vitrine-fila" aria-label="Outros anúncios da vitrine">
            {anuncios.map((anuncio, posicao) => {
              const miniatura = imagemCapa(anuncio)
              const atual = anuncio.id === ativo.id
              return (
                <li key={anuncio.id}>
                  <button
                    type="button"
                    className="home-vitrine-item"
                    aria-current={atual || undefined}
                    aria-label={`Mostrar ${anuncio.titulo} na vitrine (${posicao + 1} de ${anuncios.length})`}
                    onClick={() => setIndice(posicao)}
                  >
                    <span
                      className="home-vitrine-item-foto"
                      style={{ background: corPlaceholder(anuncio.id) }}
                      aria-hidden="true"
                    >
                      {miniatura && <img src={miniatura} alt="" />}
                    </span>
                    <span className="home-vitrine-item-texto" aria-hidden="true">
                      <span className="home-vitrine-item-titulo">{anuncio.titulo}</span>
                      <span className="home-vitrine-item-preco">{formatarMoeda(anuncio.preco)}</span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </section>
  )
}

/** Sem anúncios pagos no momento, o espaço da vitrine vira um convite para ocupá-lo. */
function VitrineVazia({ podeDestacar, aoDestacar }: { podeDestacar: boolean; aoDestacar: () => void }) {
  return (
    <section className="home-vitrine home-vitrine--vazia" aria-labelledby="home-vitrine-titulo">
      <div className="home-vitrine-boas-vindas">
        <p className="home-vitrine-sobretitulo">Obra Circular</p>
        <h2 id="home-vitrine-titulo">Sobra de obra de um é material bom para outro.</h2>
        <p>Compre material de construção que sobrou de outras obras, com pagamento protegido e entrega confirmada.</p>
      </div>
      <div className="home-vitrine-espaco">
        <SeloDestaque />
        <p className="home-vitrine-espaco-titulo">Este espaço está livre</p>
        <p>O anúncio em destaque aparece aqui, no topo da página inicial, antes de todos os outros.</p>
        {podeDestacar ? (
          <button type="button" className="home-vitrine-convite" onClick={aoDestacar}>
            Colocar meu anúncio aqui
          </button>
        ) : (
          <Link to="/anuncios/novo" className="home-vitrine-convite">
            Anunciar um material
          </Link>
        )}
      </div>
    </section>
  )
}

interface CartaoAnuncioProps {
  anuncio: Anuncio
  categoria?: string
  meu: boolean
  aoDestacar: () => void
}

/** Card da grade. Pagantes que não couberem na vitrine ocupam duas colunas. */
function CartaoAnuncio({ anuncio, categoria, meu, aoDestacar }: CartaoAnuncioProps) {
  const capa = imagemCapa(anuncio)
  const classes = ['home-item']
  if (anuncio.em_destaque) classes.push('home-item--destaque')
  if (meu) classes.push('home-item--meu')

  return (
    <li className={classes.join(' ')}>
      <Link
        to={`/anuncios/${anuncio.id}`}
        className="home-item-link"
        aria-label={`Ver anúncio ${anuncio.titulo}${anuncio.em_destaque ? ' (em destaque)' : ''}`}
      >
        <div className="home-item-foto" style={{ background: corPlaceholder(anuncio.id) }}>
          {capa ? (
            <img src={capa} alt={`Foto de ${anuncio.titulo}`} className="home-item-imagem" />
          ) : (
            <span className="home-item-foto-legenda">Sem foto ainda</span>
          )}
          {anuncio.em_destaque && <SeloDestaque className="home-item-selo" />}
        </div>
        <div className="home-item-info">
          {categoria && <p className="home-item-categoria">{categoria}</p>}
          <h3>{anuncio.titulo}</h3>
          <p className="home-item-preco">
            {formatarMoeda(anuncio.preco)}
            <span> por unidade</span>
          </p>
          <p className="home-item-quantidade">{textoQuantidade(anuncio.quantidade)}</p>
          <p className="home-item-rodape">Publicado {formatarTempoRelativo(anuncio.postado_em)}</p>
        </div>
      </Link>
      {meu && (
        <div className="home-item-acoes">
          <span>Seu anúncio</span>
          <button
            type="button"
            className="home-botao-contorno"
            onClick={aoDestacar}
            aria-label={`${anuncio.em_destaque ? 'Estender destaque de' : 'Destacar'} ${anuncio.titulo}`}
          >
            {anuncio.em_destaque ? 'Estender' : 'Destacar'}
          </button>
        </div>
      )}
    </li>
  )
}

/** Faixa escura para quem quer vender; quem já anuncia também é convidado ao destaque. */
function FaixaVender({ podeDestacar, aoDestacar }: { podeDestacar: boolean; aoDestacar: () => void }) {
  return (
    <section className="home-vender" aria-labelledby="home-vender-titulo">
      <div className="home-vender-texto">
        <h2 id="home-vender-titulo">
          {podeDestacar ? 'Quer vender mais rápido?' : 'Sobrou material na sua obra?'}
        </h2>
        <p>
          {podeDestacar
            ? 'Coloque um anúncio seu na vitrine do topo da página inicial e à frente dos outros nas buscas.'
            : 'Anuncie em poucos minutos e receba pelo Mercado Pago depois que a entrega for confirmada.'}
        </p>
      </div>
      <ol className="home-vender-passos" aria-label="Como vender">
        <li><strong>1</strong> Publique com fotos</li>
        <li><strong>2</strong> Combine a entrega</li>
        <li><strong>3</strong> Receba o repasse</li>
      </ol>
      <div className="home-vender-acoes">
        {podeDestacar ? (
          <>
            <button type="button" className="home-vender-destacar" onClick={aoDestacar}>
              Destacar um anúncio
            </button>
            <Link to="/anuncios/meus" className="home-vender-link">
              Gerenciar em Meus anúncios
            </Link>
          </>
        ) : (
          <Link to="/anuncios/novo" className="home-vender-anunciar">
            Anunciar agora
          </Link>
        )}
      </div>
    </section>
  )
}

function usePrefereMenosMovimento(): boolean {
  const consulta = '(prefers-reduced-motion: reduce)'
  const [reduzir, setReduzir] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia(consulta).matches,
  )
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const midia = window.matchMedia(consulta)
    const aoMudar = () => setReduzir(midia.matches)
    midia.addEventListener?.('change', aoMudar)
    return () => midia.removeEventListener?.('change', aoMudar)
  }, [])
  return reduzir
}
