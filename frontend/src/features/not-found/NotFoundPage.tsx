import { Link } from 'react-router'
import { Logo } from '../autenticacao/AuthLayout'

export function NotFoundPage() {
  return (
    <main className="not-found-page">
      <Logo />
      <div className="not-found-card">
        <span className="step-label">Erro 404</span>
        <h1>Página não encontrada</h1>
        <p>O endereço informado não existe ou foi movido.</p>
        <Link to="/">Voltar ao início</Link>
      </div>
    </main>
  )
}
