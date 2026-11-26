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

  return (
    <main className="home-main">
      <nav className="home-lateral" aria-labelledby="home-categorias-titulo">
        <h2 id="home-categorias-titulo" className="home-lateral-titulo">Categorias</h2>
        <div
          ref={filtrosRef}
          className="home-filtros rolagem-horizontal"
          role="group"
          aria-label="Filtrar por categoria"
          {...filtrosRolagem}
        >
          <button
            type="button"
            className="home-filtro"
            aria-pressed={categoriaId === null}
            onClick={() => setCategoriaId(null)}
          >
            Todas
          </button>
          {categorias.map((categoria) => (
            <button
              key={categoria.id}
              type="button"
              className="home-filtro"
              aria-pressed={categoriaId === categoria.id}
              onClick={() => setCategoriaId(categoria.id)}
            >
              {categoria.nome}
            </button>
          ))}
        </div>
      </nav>

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
          {anuncios.map((anuncio) => {
            const meu = anuncio.vendedor_id === usuario.id && anuncio.status === 'ATIVO'
            const capa = imagemCapa(anuncio)
            const categoria = categoriasPorId.get(anuncio.categoria_id)
            const classes = ['home-item']
            if (anuncio.em_destaque) classes.push('home-item--destaque')
            if (meu) classes.push('home-item--meu')
            return (
              <li key={anuncio.id} className={classes.join(' ')}>
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
                    <h3>{anuncio.titulo}</h3>
                    <p className="home-item-preco">
                      {formatarMoeda(anuncio.preco)}
                      <span> por unidade</span>
                    </p>
                    <p className="home-item-quantidade">
                      {anuncio.quantidade} {anuncio.quantidade === 1 ? 'unidade disponível' : 'unidades disponíveis'}
                    </p>
                    <p className="home-item-rodape">
                      {categoria && <span>{categoria}</span>}
                      <span>Publicado {formatarTempoRelativo(anuncio.postado_em)}</span>
                    </p>
                  </div>
                </Link>
                {meu && (
                  <div className="home-item-acoes">
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
              </li>
            )
          })}
        </ul>
      </section>

      {totalMeusAtivos > 0 && <ConviteDestaque aoDestacar={() => setDestacar(null)} />}

      {destacar !== undefined && <DestaqueDialog anuncio={destacar} aoFechar={fecharDestaque} />}
    </main>
  )
}

/** Convite discreto ao destaque pago: o amarelo fica reservado aos anúncios pagos. */
function ConviteDestaque({ aoDestacar }: { aoDestacar: () => void }) {
  return (
    <aside className="home-destaque-chamada" aria-label="Destacar um anúncio seu">
      <p className="home-destaque-chamada-titulo">Quer vender mais rápido?</p>
      <p>Anúncios em destaque aparecem primeiro na página inicial e nas buscas.</p>
      <div className="home-destaque-chamada-acoes">
        <button type="button" className="home-botao-contorno" onClick={aoDestacar}>
          Destacar um anúncio
        </button>
        <Link to="/anuncios/meus" className="home-destaque-chamada-link">
          Gerenciar em Meus anúncios
        </Link>
      </div>
    </aside>
  )
}
