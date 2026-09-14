import type { ReactNode } from 'react'

interface AuthLayoutProps {
  children: ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <main className="signup-shell">
      <section className="brand-panel" aria-label="Sobre a Obra Circular">
        <Logo />

        <div className="brand-copy">
          <span className="eyebrow">Construir também é reaproveitar</span>
          <h1>Materiais com história. Obras com futuro.</h1>
          <p>
            Compre e venda excedentes de obra com segurança, reduzindo custos e evitando
            desperdícios.
          </p>
        </div>

        <ul className="benefit-list" aria-label="Benefícios da plataforma">
          <li>
            <LeafIcon />
            <span>
              <strong>Economia circular</strong>
              Cada material reaproveitado deixa de virar descarte.
            </span>
          </li>
          <li>
            <ShieldIcon />
            <span>
              <strong>Negociações mais seguras</strong>
              Uma comunidade feita para quem compra, vende e constrói.
            </span>
          </li>
        </ul>
      </section>

      <section className="form-panel">
        <div className="mobile-logo">
          <Logo />
        </div>
        {children}
      </section>
    </main>
  )
}

export function Logo() {
  return (
    <div className="brand-logo" aria-label="Obra Circular">
      <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="4.4" />
        <ellipse cx="16" cy="16" rx="13" ry="6" transform="rotate(30 16 16)" />
        <ellipse cx="16" cy="16" rx="13" ry="6" transform="rotate(90 16 16)" />
        <ellipse cx="16" cy="16" rx="13" ry="6" transform="rotate(150 16 16)" />
      </svg>
      <span className="logo-type">
        Obra <strong>Circular</strong>
      </span>
    </div>
  )
}

function LeafIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 4.5C12.5 4.5 6 8.1 6 14.1c0 2.9 2.1 5.4 5.4 5.4 5.8 0 8.6-6.4 8.6-15Z" />
      <path d="M4 20c2.5-4.4 6.2-7.5 11.2-9.4" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 4.8 6v5.2c0 4.7 2.9 8.2 7.2 9.8 4.3-1.6 7.2-5.1 7.2-9.8V6L12 3Z" />
      <path d="m8.8 12.1 2.1 2.1 4.5-4.7" />
    </svg>
  )
}
