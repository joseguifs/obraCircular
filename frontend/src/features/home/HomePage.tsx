import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { listarAnuncios, listarAnunciosDoVendedor } from '../anuncios/anuncioApi'
import type { Anuncio } from '../anuncios/types'
import { listarCategoriasAtivas } from '../categorias/categoriaApi'
import type { Categoria } from '../categorias/types'
import { ApiError, resolverUrlDaApi } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { primeiroNome } from '../../lib/texto'
import { useRolagemHorizontal } from '../../lib/useRolagemHorizontal'
import { useAuth } from '../autenticacao/useAuth'
import { DestaqueDialog } from '../anuncios/DestaqueDialog'
import { SeloDestaque } from '../anuncios/DestaqueOferta'

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
  const { ref: filtrosRef, atributos: filtrosRolagem } = useRolagemHorizontal<HTMLDivElement>()
  const gradeRef = useRef<HTMLDivElement>(null)
  const [colunas, setColunas] = useState(4)

  // O convite de destaque entra logo após a primeira fileira, que varia com a largura.
  useEffect(() => {
    const grade = gradeRef.current
    if (!grade || typeof ResizeObserver === 'undefined') return
    const observador = new ResizeObserver(() => {
      const trilhas = getComputedStyle(grade).gridTemplateColumns.split(' ').filter(Boolean)
      setColunas(Math.max(1, trilhas.length))
    })
    observador.observe(grade)
    return () => observador.disconnect()
  }, [])

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
  const resumoBusca = carregando
    ? 'Carregando anúncios…'
    : totalDisponiveis === 0
      ? 'Nada encontrado com esses filtros.'
      : `${totalDisponiveis} ${totalDisponiveis === 1 ? 'anúncio' : 'anúncios'} ${
          filtrando
            ? totalDisponiveis === 1 ? 'encontrado' : 'encontrados'
            : 'à venda agora'
        }.`
  const posicaoConvite =
    totalMeusAtivos > 0 && anuncios.length > 0 ? Math.min(colunas, anuncios.length) : null

  return (
    <main className="home-main">
      <div className="home-intro">
        <h1>Olá, {primeiroNome(usuario.nome)}</h1>
        <p>{resumoBusca}</p>
      </div>

      <div
        ref={filtrosRef}
        className="home-filtros rolagem-horizontal"
        role="group"
        aria-label="Filtrar por categoria"
        {...filtrosRolagem}
      >
        <button
          type="button"
          className={categoriaId === null ? 'home-filtro home-filtro--ativo' : 'home-filtro'}
          onClick={() => setCategoriaId(null)}
        >
          Todos
        </button>
        {categorias.map((categoria) => (
          <button
            key={categoria.id}
            type="button"
            className={categoriaId === categoria.id ? 'home-filtro home-filtro--ativo' : 'home-filtro'}
            onClick={() => setCategoriaId(categoria.id)}
          >
            {categoria.nome}
          </button>
        ))}
      </div>

      <h2 className="home-secao-titulo">
        {buscaAtiva ? `Resultados para “${buscaAtiva}”` : 'Materiais disponíveis'}
      </h2>

      {erro && <div className="home-alert" role="alert">{erro}</div>}

      {!erro && !carregando && anuncios.length === 0 && (
        <div className="home-vazio">
          <p className="home-vazio-titulo">Nenhum anúncio encontrado</p>
          <p>Ajuste a busca ou escolha outra categoria.</p>
        </div>
      )}

      <div className="home-grid" ref={gradeRef}>
        {anuncios.map((anuncio, indice) => {
          const meu = anuncio.vendedor_id === usuario.id
          const capa = imagemCapa(anuncio)
          return (
          <Fragment key={anuncio.id}>
          {indice === posicaoConvite && (
            <ConviteDestaque aoDestacar={() => setDestacar(null)} />
          )}
          <article
            className={anuncio.em_destaque ? 'home-card home-card--destaque' : 'home-card'}
          >
          <Link
            to={`/anuncios/${anuncio.id}`}
            className="home-card-link"
            aria-label={`Ver anúncio ${anuncio.titulo}${anuncio.em_destaque ? ' (em destaque)' : ''}`}
          >
            <div className="home-card-foto" style={{ background: corPlaceholder(anuncio.id) }}>
              {categoriasPorId.get(anuncio.categoria_id) && (
                <span className="home-card-categoria">{categoriasPorId.get(anuncio.categoria_id)}</span>
              )}
              {anuncio.em_destaque && <SeloDestaque className="home-card-destaque" />}
              {capa ? (
                <img
                  src={capa}
                  alt={`Foto de ${anuncio.titulo}`}
                  className="home-card-imagem"
                />
              ) : (
                <span className="home-card-foto-legenda">Sem foto ainda</span>
              )}
            </div>
            <div className="home-card-corpo">
              <div className="home-card-cabecalho">
                <h3>{anuncio.titulo}</h3>
                <p className="home-card-tempo">Publicado {formatarTempoRelativo(anuncio.postado_em)}</p>
              </div>
              <dl className="home-card-ficha">
                <div>
                  <dt>Preço por unidade</dt>
                  <dd className="home-card-preco">{formatarMoeda(anuncio.preco)}</dd>
                </div>
                <div>
                  <dt>Disponível</dt>
                  <dd>{anuncio.quantidade} un.</dd>
                </div>
              </dl>
            </div>
          </Link>
          {meu && anuncio.status === 'ATIVO' && (
            <div className="home-card-acoes">
              <span>Seu anúncio</span>
              <button
                type="button"
                className="home-botao-contorno"
                onClick={() => setDestacar(anuncio)}
                aria-label={`${anuncio.em_destaque ? 'Estender destaque de' : 'Destacar'} ${anuncio.titulo}`}
              >
                {anuncio.em_destaque ? 'Estender destaque' : 'Destacar'}
              </button>
            </div>
          )}
          </article>
          </Fragment>
          )
        })}
        {posicaoConvite === anuncios.length && posicaoConvite > 0 && (
          <ConviteDestaque aoDestacar={() => setDestacar(null)} />
        )}
      </div>

      {destacar !== undefined && <DestaqueDialog anuncio={destacar} aoFechar={fecharDestaque} />}
    </main>
  )
}

/** Convite discreto ao destaque pago: o amarelo fica reservado aos anúncios pagos. */
function ConviteDestaque({ aoDestacar }: { aoDestacar: () => void }) {
  return (
    <section className="home-destaque-chamada" aria-label="Destacar um anúncio seu">
      <p>
        <strong>Quer vender mais rápido?</strong> Destaque um anúncio seu para ele aparecer
        primeiro na página inicial e nas buscas.
      </p>
      <div className="home-destaque-chamada-acoes">
        <button type="button" className="home-botao-contorno" onClick={aoDestacar}>
          Destacar um anúncio
        </button>
        <Link to="/anuncios/meus" className="home-destaque-chamada-link">
          Gerenciar em Meus anúncios
        </Link>
      </div>
    </section>
  )
}
