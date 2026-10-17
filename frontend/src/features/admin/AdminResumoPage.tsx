import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { obterResumoAdmin } from './adminApi'
import { ROTULOS_STATUS_ANUNCIO, ROTULOS_STATUS_USUARIO } from './rotulos'
import type { ContagemPorStatus, ResumoAdmin } from './types'

const ROTULOS_STATUS_CATEGORIA: Record<string, string> = { ATIVA: 'Ativas', INATIVA: 'Inativas' }

export function AdminResumoPage() {
  const [resumo, setResumo] = useState<ResumoAdmin | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    obterResumoAdmin()
      .then((resposta) => {
        if (ativo) setResumo(resposta)
      })
      .catch((falha) => {
        if (ativo) setErro(mensagemApiErro(falha, 'Não foi possível carregar o resumo.'))
      })
    return () => {
      ativo = false
    }
  }, [])

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração</span>
        <h1>Visão geral</h1>
        <p>Acompanhe os números do marketplace e acesse as áreas de gestão.</p>
      </header>

      {erro && (
        <div className="publish-alert" role="alert">
          {erro}
        </div>
      )}

      {!resumo && !erro && <p className="publish-loading">Carregando resumo…</p>}

      {resumo && (
        <div className="admin-cards">
          <CartaoResumo
            titulo="Anúncios"
            para="/admin/anuncios"
            contagem={resumo.anuncios}
            rotulos={ROTULOS_STATUS_ANUNCIO}
          />
          <CartaoResumo
            titulo="Usuários"
            para="/admin/usuarios"
            contagem={resumo.usuarios}
            rotulos={ROTULOS_STATUS_USUARIO}
            extra={`${resumo.administradores} administrador(es)`}
          />
          <CartaoResumo
            titulo="Categorias"
            para="/admin/categorias"
            contagem={resumo.categorias}
            rotulos={ROTULOS_STATUS_CATEGORIA}
          />
        </div>
      )}
    </main>
  )
}

interface CartaoResumoProps {
  titulo: string
  para: string
  contagem: ContagemPorStatus
  rotulos: Record<string, string>
  extra?: string
}

function CartaoResumo({ titulo, para, contagem, rotulos, extra }: CartaoResumoProps) {
  return (
    <section className="publish-card admin-card" aria-label={titulo}>
      <h2>{titulo}</h2>
      <strong className="admin-card-total">{contagem.total}</strong>
      <ul>
        {Object.entries(rotulos).map(([status, rotulo]) => (
          <li key={status}>
            <span>{rotulo}</span>
            <span>{contagem.por_status[status] ?? 0}</span>
          </li>
        ))}
      </ul>
      {extra && <small>{extra}</small>}
      <Link to={para} className="secondary-button admin-link-button">
        Gerenciar {titulo.toLowerCase()}
      </Link>
    </section>
  )
}
