import { useEffect, useState } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router'
import { obterUsuarioAtual } from '../features/autenticacao/autenticacaoApi'
import { atualizarUsuarioDaSessao } from '../features/autenticacao/sessaoStorage'
import { useAuth } from '../features/autenticacao/useAuth'

export function AdminRoute() {
  const { sessao } = useAuth()
  const localizacao = useLocation()
  const [verificado, setVerificado] = useState(false)
  const administrador = sessao?.usuario.administrador === true
  const possuiSessao = Boolean(sessao)

  // Sessões abertas antes da concessão do perfil não trazem o campo atualizado:
  // consulta o usuário atual uma vez antes de negar o acesso.
  useEffect(() => {
    if (!possuiSessao || administrador || verificado) return
    let ativo = true
    obterUsuarioAtual()
      .then((usuario) => {
        if (ativo) atualizarUsuarioDaSessao(usuario)
      })
      .catch(() => undefined)
      .finally(() => {
        if (ativo) setVerificado(true)
      })
    return () => {
      ativo = false
    }
  }, [possuiSessao, administrador, verificado])

  if (!sessao) {
    return <Navigate to="/login" replace state={{ origem: localizacao.pathname }} />
  }

  if (administrador) return <Outlet />

  if (!verificado) {
    return (
      <main className="publish-page">
        <p className="publish-loading">Verificando acesso…</p>
      </main>
    )
  }

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <span className="step-label">Administração</span>
        <h1>Acesso restrito</h1>
        <p>Esta área é exclusiva para administradores do Obra Circular.</p>
      </header>
      <Link to="/home" className="publish-button admin-link-button">
        Voltar para o início
      </Link>
    </main>
  )
}
