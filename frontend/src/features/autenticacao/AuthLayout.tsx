import type { ReactNode } from 'react'

interface AuthLayoutProps {
  children: ReactNode
  /** Atalho no canto direito do cabeçalho (ex.: "Criar conta" no login). */
  acaoCabecalho?: ReactNode
}

/**
 * Moldura das telas públicas (login, cadastro e recuperação de senha): cabeçalho
 * grafite, formulário num card branco e um painel escuro de apresentação. O formulário
 * vem primeiro no HTML, para o foco e o celular começarem por ele; no desktop o painel
 * ocupa a coluna da esquerda.
 */
export function AuthLayout({ children, acaoCabecalho }: AuthLayoutProps) {
  return (
    <div className="app-shell auth-shell">
      <header className="app-header">
        <div className="app-header-bar auth-header-bar">
          <div className="app-logo">
            <Logo />
          </div>
          {acaoCabecalho && <div className="auth-header-acao">{acaoCabecalho}</div>}
        </div>
      </header>

      <main className="auth-main">
        <section className="auth-formulario">{children}</section>

        <section className="auth-intro" aria-label="Sobre a Obra Circular">
          <div>
            <p className="auth-sobretitulo">Marketplace de sobras de obra</p>
            <h1>A sobra da sua obra é o material de outra.</h1>
            <p className="auth-intro-texto">
              Compre e venda materiais de construção que sobraram, perto de você, com pagamento
              protegido pelo Mercado Pago.
            </p>
          </div>

          <ul className="auth-beneficios" aria-label="Benefícios da plataforma">
            <li>
              <strong>Menos entulho</strong>
              <span>Cada material revendido deixa de virar descarte.</span>
            </li>
            <li>
              <strong>Pagamento protegido</strong>
              <span>Você paga pelo Mercado Pago, sem passar dados ao vendedor.</span>
            </li>
            <li>
              <strong>Entrega com PIN</strong>
              <span>O vendedor só recebe depois que você confere o material.</span>
            </li>
          </ul>

        </section>
      </main>
    </div>
  )
}

export function Logo() {
  return (
    <div className="brand-logo" aria-label="Obra Circular">
      <LogoMarca />
      <span className="logo-type">
        Obra <strong>Circular</strong>
      </span>
    </div>
  )
}

/** Tijolos assentados dentro de uma seta circular: material de obra que volta a circular. */
function LogoMarca() {
  return (
    <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
      <path className="logo-mark-seta" d="M26.2 12.4A10.6 10.6 0 1 0 26.6 19" />
      <path className="logo-mark-seta" d="M27.2 6.6v6h-6" />
      <g className="logo-mark-tijolos">
        <rect x="13.2" y="11.8" width="5.6" height="3.8" rx="0.7" />
        <rect x="10" y="16.4" width="5.6" height="3.8" rx="0.7" />
        <rect x="16.4" y="16.4" width="5.6" height="3.8" rx="0.7" />
      </g>
    </svg>
  )
}
