import { useAuth } from '../autenticacao/useAuth'

export function HomePage() {
  const { sessao } = useAuth()
  const usuario = sessao!.usuario
  const primeiroNome = usuario.nome.trim().split(/\s+/)[0]

  return (
    <main className="home-main">
      <section className="home-hero">
        <div>
          <span className="step-label">Sua construção circular começa aqui</span>
          <h1>Bem-vindo à home, {primeiroNome}!</h1>
          <p>
            Esta é a base da futura home do marketplace. A partir daqui você poderá
            encontrar materiais, publicar excedentes e acompanhar suas negociações.
          </p>
        </div>
        <div className="home-hero-mark" aria-hidden="true">
          <CircularIcon />
        </div>
      </section>

      <section className="home-actions" aria-label="Próximas funcionalidades">
        <article>
          <SearchIcon />
          <span>Explorar</span>
          <h2>Comprar materiais</h2>
          <p>Encontre materiais disponíveis para sua próxima obra.</p>
        </article>
        <article>
          <PlusIcon />
          <span>Reaproveitar</span>
          <h2>Anunciar excedentes</h2>
          <p>Transforme materiais parados em novas oportunidades.</p>
        </article>
        <article>
          <BoxIcon />
          <span>Acompanhar</span>
          <h2>Meus pedidos</h2>
          <p>Consulte suas compras e vendas em um só lugar.</p>
        </article>
      </section>
    </main>
  )
}

function CircularIcon() {
  return (
    <svg viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="12" />
      <ellipse cx="50" cy="50" rx="42" ry="18" transform="rotate(30 50 50)" />
      <ellipse cx="50" cy="50" rx="42" ry="18" transform="rotate(90 50 50)" />
      <ellipse cx="50" cy="50" rx="42" ry="18" transform="rotate(150 50 50)" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 5 5" />
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

function BoxIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 7 8-4 8 4-8 4-8-4Z" />
      <path d="M4 7v10l8 4 8-4V7M12 11v10" />
    </svg>
  )
}
