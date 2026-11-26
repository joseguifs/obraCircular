import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { Link, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router'
import { Logo } from '../features/autenticacao/AuthLayout'
import { useAuth } from '../features/autenticacao/useAuth'
import { obterIniciais } from '../lib/texto'
import { useRolagemHorizontal } from '../lib/useRolagemHorizontal'

export function MarketplaceLayout() {
  const { sessao } = useAuth()
  const location = useLocation()
  const navegar = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const naHome = location.pathname === '/home'
  const naAdministracao = location.pathname === '/admin' || location.pathname.startsWith('/admin/')
  const [buscaDigitada, setBuscaDigitada] = useState('')
  const { ref: navRef, atributos: navRolagem } = useRolagemHorizontal<HTMLElement>()
  const { ref: barraRef, compacto } = useCabecalhoCompacto<HTMLDivElement>()
  const busca = naHome ? searchParams.get('q') ?? '' : buscaDigitada

  function alterarBusca(valor: string) {
    if (!naHome) {
      setBuscaDigitada(valor)
      return
    }
    const proximosParametros = new URLSearchParams(searchParams)
    if (valor) proximosParametros.set('q', valor)
    else proximosParametros.delete('q')
    setSearchParams(proximosParametros, { replace: true })
  }

  function enviarBusca(evento: FormEvent) {
    evento.preventDefault()
    if (naHome) return
    setBuscaDigitada('')
    navegar(busca ? `/home?q=${encodeURIComponent(busca)}` : '/home')
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div ref={barraRef} className="app-header-bar" data-compacto={compacto || undefined}>
          <Link to="/home" className="app-logo">
            <Logo />
          </Link>

          <nav
            ref={navRef}
            className="app-nav rolagem-horizontal"
            aria-label="Navegação principal"
            {...navRolagem}
          >
            <Link to="/home" className={naHome ? 'app-nav-link app-nav-link--ativo' : 'app-nav-link'}>
              Explorar
            </Link>
            {sessao && (
              <Link to="/anuncios/meus" className={location.pathname === '/anuncios/meus'
                ? 'app-nav-link app-nav-link--ativo' : 'app-nav-link'}>
                Meus anúncios
              </Link>
            )}
            {sessao && (
              <Link to="/pedidos" className={location.pathname.startsWith('/pedidos')
                ? 'app-nav-link app-nav-link--ativo' : 'app-nav-link'}>
                Meus pedidos
              </Link>
            )}
            {sessao && <Link to="/vendas" className={location.pathname === '/vendas'
              ? 'app-nav-link app-nav-link--ativo' : 'app-nav-link'}>Minhas vendas</Link>}
            <span className="app-nav-item app-nav-item--futuro">Perguntas</span>
            {sessao?.usuario.administrador && (
              <Link
                to="/admin"
                className={
                  location.pathname.startsWith('/admin')
                    ? 'app-nav-link app-nav-link--ativo'
                    : 'app-nav-link'
                }
              >
                Administração
              </Link>
            )}
          </nav>

          <form className="app-search" role="search" onSubmit={enviarBusca}>
            <SearchIcon />
            <input
              type="search"
              placeholder="Buscar materiais, marcas, cidades…"
              aria-label="Buscar anúncios"
              value={busca}
              onChange={(evento) => alterarBusca(evento.target.value)}
            />
          </form>

          <div className="app-header-actions">
            <span className="app-icon-button" aria-hidden="true">
              <BellIcon />
            </span>

            {!naAdministracao && (
              <Link to="/anuncios/novo" className="app-button-primary">
                <PlusIcon />
                <span>Anunciar</span>
              </Link>
            )}

            {sessao && (
              <Link
                to="/perfil"
                className={
                  location.pathname.startsWith('/perfil')
                    ? 'app-profile-button app-profile-button--ativo'
                    : 'app-profile-button'
                }
                aria-label="Ver meu perfil"
              >
                <span className="app-avatar">{obterIniciais(sessao.usuario.nome)}</span>
              </Link>
            )}
          </div>
        </div>
      </header>
      <Outlet />
    </div>
  )
}

/** Largura mínima para a busca continuar usável na mesma linha do menu. */
const LARGURA_MINIMA_BUSCA = 240

/**
 * Decide se logo, menu, busca e ações cabem numa linha só. Quando não cabem (telas
 * menores ou menu com mais itens, como o de administradores), o menu desce para uma
 * segunda linha em vez de empurrar as ações para baixo da busca.
 *
 * A conta usa só larguras que não mudam com o modo (itens do menu, logo e ações),
 * então alternar o modo não provoca nova alternância.
 */
function useCabecalhoCompacto<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [compacto, setCompacto] = useState(false)

  const medir = useRef(() => {
    const barra = ref.current
    const logo = barra?.querySelector<HTMLElement>('.app-logo')
    const nav = barra?.querySelector<HTMLElement>('.app-nav')
    const acoes = barra?.querySelector<HTMLElement>('.app-header-actions')
    if (!barra || !logo || !nav || !acoes) return

    const estiloBarra = getComputedStyle(barra)
    const vao = parseFloat(estiloBarra.columnGap) || 0
    const espaco =
      barra.clientWidth - parseFloat(estiloBarra.paddingLeft) - parseFloat(estiloBarra.paddingRight)
    const itens = Array.from(nav.children) as HTMLElement[]
    const vaoNav = parseFloat(getComputedStyle(nav).columnGap) || 0
    const larguraNav =
      itens.reduce((total, item) => total + item.getBoundingClientRect().width, 0) +
      vaoNav * Math.max(0, itens.length - 1)
    const necessario =
      logo.getBoundingClientRect().width +
      larguraNav +
      LARGURA_MINIMA_BUSCA +
      acoes.getBoundingClientRect().width +
      vao * 3
    setCompacto(necessario > espaco)
  })

  // Mede antes da primeira pintura para o cabeçalho não "pular" ao carregar.
  useLayoutEffect(() => medir.current(), [])

  useEffect(() => {
    const barra = ref.current
    if (!barra) return
    const atualizar = () => medir.current()
    const redimensionamento =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(atualizar)
    redimensionamento?.observe(barra)
    // Itens do menu e ações mudam com a sessão (ex.: "Administração" só para admins).
    const mutacoes = typeof MutationObserver === 'undefined' ? null : new MutationObserver(atualizar)
    mutacoes?.observe(barra, { childList: true, subtree: true })
    // A fonte web muda a largura dos textos quando termina de carregar.
    document.fonts?.ready.then(atualizar).catch(() => {})
    return () => {
      redimensionamento?.disconnect()
      mutacoes?.disconnect()
    }
  }, [])

  return { ref, compacto }
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16l4 4" />
    </svg>
  )
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 15V10a6 6 0 10-12 0v5l-1.5 2.5h15L18 15z" />
      <path d="M10 19.5a2.2 2.2 0 004 0" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}
