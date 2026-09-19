import { Link, useLocation, useParams } from 'react-router'

export function AnuncioPublicadoPage() {
  const { anuncioId } = useParams()
  const localizacao = useLocation()
  const estado = localizacao.state as { titulo?: string; quantidadeImagens?: number } | null

  return (
    <main className="published-page">
      <div className="published-card">
        <div className="published-icon" aria-hidden="true">✓</div>
        <span className="step-label">Anúncio publicado</span>
        <h1>Seu material já está no marketplace</h1>
        <p>
          {estado?.titulo ? <><strong>{estado.titulo}</strong> foi publicado com sucesso.</> : 'O anúncio foi publicado com sucesso.'}
          {' '}Você pode compartilhar o identificador <code>{anuncioId}</code>.
        </p>
        <div className="published-actions">
          <Link to="/anuncios/novo">Publicar outro</Link>
          <Link to="/home" className="published-primary">Voltar para a home</Link>
        </div>
      </div>
    </main>
  )
}
