import { useState, type FormEvent } from 'react'
import { Link, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router'
import { Logo } from '../features/autenticacao/AuthLayout'
import { useAuth } from '../features/autenticacao/useAuth'
import { obterIniciais } from '../lib/texto'

export function MarketplaceLayout() {
  const { sessao } = useAuth()
  const location = useLocation()
  const navegar = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const naHome = location.pathname === '/home'
  const [buscaDigitada, setBuscaDigitada] = useState('')
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
        <div className="app-header-bar">
          <Link to="/home" className="app-logo">
            <Logo />
          </Link>

          <nav className="app-nav" aria-label="Navegação principal">
            <Link to="/home" className={naHome ? 'app-nav-link app-nav-link--ativo' : 'app-nav-link'}>
              Explorar
            </Link>
            <span className="app-nav-item app-nav-item--futuro">Meus anúncios</span>
            <span className="app-nav-item app-nav-item--futuro">Mensagens</span>
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

            <Link to="/anuncios/novo" className="app-button-primary">
              <PlusIcon />
              <span>Anunciar</span>
            </Link>

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
                <span>{sessao.usuario.nome}</span>
              </Link>
            )}
          </div>
        </div>
      </header>
      <Outlet />
    </div>
  )
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
