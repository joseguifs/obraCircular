import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { listarAnuncios, listarAnunciosDoVendedor } from '../anuncios/anuncioApi'
import type { Anuncio } from '../anuncios/types'
import { listarCategoriasAtivas } from '../categorias/categoriaApi'
import type { Categoria } from '../categorias/types'
import { ApiError } from '../../lib/api'
import { formatarMoeda, formatarTempoRelativo } from '../../lib/formatarTempo'
import { primeiroNome } from '../../lib/texto'
import { useAuth } from '../autenticacao/useAuth'

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
  const [totalMeusAnuncios, setTotalMeusAnuncios] = useState<number | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

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
    listarAnunciosDoVendedor(usuario.id, { limit: 1 })
      .then((resposta) => setTotalMeusAnuncios(resposta.total))
      .catch(() => setTotalMeusAnuncios(null))
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

  const resumoBusca = carregando
    ? 'Carregando anúncios…'
    : totalDisponiveis === 0
      ? 'Nada encontrado com esses filtros.'
      : `${totalDisponiveis} ${totalDisponiveis === 1 ? 'anúncio disponível' : 'anúncios disponíveis'} na sua região agora.`

  return (
    <main className="home-main">
      <div className="home-intro">
        <div>
          <span className="step-label">Bom te ver de novo</span>
          <h1>Olá, {primeiroNome(usuario.nome)}</h1>
          <p>{resumoBusca}</p>
        </div>
        <div className="home-stats">
          <div className="home-stat">
            <strong>{totalMeusAnuncios ?? '—'}</strong>
            <span>Anúncios seus</span>
          </div>
          <div className="home-stat">
            <strong>{totalDisponiveis}</strong>
            <span>Anúncios disponíveis</span>
          </div>
        </div>
      </div>

      <div className="home-filtros" role="group" aria-label="Filtrar por categoria">
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

      <h2 className="home-secao-titulo">Anúncios perto de você</h2>

      {erro && <div className="home-alert" role="alert">{erro}</div>}

      {!erro && !carregando && anuncios.length === 0 && (
        <div className="home-vazio">
          <p className="home-vazio-titulo">Nenhum anúncio encontrado</p>
          <p>Ajuste a busca ou escolha outra categoria.</p>
        </div>
      )}

      <div className="home-grid">
        {anuncios.map((anuncio) => (
          <Link key={anuncio.id} to={`/anuncios/${anuncio.id}`} className="home-card" aria-label={`Ver anúncio ${anuncio.titulo}`}>
            <div className="home-card-foto" style={{ background: corPlaceholder(anuncio.id) }}>
              {categoriasPorId.get(anuncio.categoria_id) && (
                <span className="home-card-categoria">{categoriasPorId.get(anuncio.categoria_id)}</span>
              )}
              <span className="home-card-foto-legenda">
                {anuncio.imagem_url ? 'Foto do anúncio' : 'Sem foto ainda'}
              </span>
              {anuncio.imagem_url && (
                <img src={anuncio.imagem_url} alt="" className="home-card-imagem" />
              )}
            </div>
            <div className="home-card-corpo">
              <h3>{anuncio.titulo}</h3>
              <p className="home-card-tempo">{formatarTempoRelativo(anuncio.postado_em)}</p>
              <div className="home-card-rodape">
                <div>
                  <p className="home-card-preco">{formatarMoeda(anuncio.preco)}</p>
                  <p className="home-card-quantidade">{anuncio.quantidade} unidades</p>
                </div>
                <span className="home-card-link">Ver anúncio →</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </main>
  )
}
