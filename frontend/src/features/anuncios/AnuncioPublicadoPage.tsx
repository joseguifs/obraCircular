import { Link, useLocation, useParams } from 'react-router'
import type { AvisoImagem } from './types'

export function AnuncioPublicadoPage() {
  const { anuncioId } = useParams()
  const localizacao = useLocation()
  const estado = localizacao.state as {
    titulo?: string
    quantidadeImagens?: number
    avisosImagens?: AvisoImagem[]
  } | null
  const avisos = estado?.avisosImagens ?? []

  return (
    <main className="published-page">
      <div className="published-card">
        <div className="published-icon" aria-hidden="true">✓</div>
        <h1>Seu material já está no marketplace</h1>
        <p>
          {estado?.titulo ? <><strong>{estado.titulo}</strong> foi publicado com sucesso.</> : 'O anúncio foi publicado com sucesso.'}
          {' '}Você pode compartilhar o identificador <code>{anuncioId}</code>.
        </p>
        {avisos.length > 0 && (
          <section className="published-avisos" aria-labelledby="published-avisos-titulo">
            <h2 id="published-avisos-titulo">
              {avisos.length === 1 ? 'Uma foto está fora do padrão' : `${avisos.length} fotos estão fora do padrão`}
            </h2>
            <p>O anúncio já está no ar com elas. Veja o que pode acontecer na exibição:</p>
            <ul>
              {avisos.map((aviso) => (
                <li key={aviso.imagem_id}>
                  <strong>{aviso.nome_original}</strong> ({aviso.largura} × {aviso.altura} px):{' '}
                  {aviso.mensagem}
                </li>
              ))}
            </ul>
          </section>
        )}
        <div className="published-actions">
          <Link to="/anuncios/novo">Publicar outro</Link>
          <Link to="/home" className="published-primary">Voltar para a home</Link>
        </div>
      </div>
    </main>
  )
}
