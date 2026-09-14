import { Outlet, useNavigate } from 'react-router'
import { Logo } from '../features/autenticacao/AuthLayout'
import { useAuth } from '../features/autenticacao/useAuth'

export function MarketplaceLayout() {
  const { sessao, encerrarSessao } = useAuth()
  const navegar = useNavigate()

  function sair() {
    encerrarSessao()
    navegar('/login', { replace: true })
  }

  return (
    <div className="home-shell">
      <header className="home-header">
        <Logo />
        <div className="home-user">
          <span>{sessao?.usuario.nome}</span>
          <button type="button" onClick={sair}>
            Sair
          </button>
        </div>
      </header>
      <Outlet />
    </div>
  )
}
