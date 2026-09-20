import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { listarAnunciosDoVendedor, listarEnderecos } from '../anuncios/anuncioApi'
import type { Endereco } from '../anuncios/types'
import { useAuth } from '../autenticacao/useAuth'
import { formatarMesAno } from '../../lib/formatarTempo'
import { obterIniciais } from '../../lib/texto'

export function PerfilPage() {
  const { sessao, encerrarSessao } = useAuth()
  const usuario = sessao!.usuario
  const navegar = useNavigate()
  const [endereco, setEndereco] = useState<Endereco | null>(null)
  const [totalAnuncios, setTotalAnuncios] = useState<number | null>(null)

  useEffect(() => {
    listarEnderecos()
      .then((enderecos) => setEndereco(enderecos[0] ?? null))
      .catch(() => setEndereco(null))
    listarAnunciosDoVendedor(usuario.id, { limit: 1 })
      .then((resposta) => setTotalAnuncios(resposta.total))
      .catch(() => setTotalAnuncios(null))
  }, [usuario.id])

  function sair() {
    encerrarSessao()
    navegar('/login', { replace: true })
  }

  return (
    <main className="profile-page">
      <Link to="/home" className="back-button">
        ← Voltar para a home
      </Link>

      <div className="profile-grid">
        <div className="profile-card">
          <div className="profile-capa" />
          <div className="profile-corpo">
            <div className="profile-cabecalho">
              <span className="profile-avatar">{obterIniciais(usuario.nome)}</span>
              <div>
                <h1>{usuario.nome}</h1>
                {endereco && (
                  <p className="profile-local">
                    {endereco.cidade}, {endereco.estado}
                  </p>
                )}
                <p className="profile-desde">na plataforma desde {formatarMesAno(usuario.criado_em)}</p>
              </div>
            </div>

            <div className="profile-stats">
              <div className="profile-stat">
                <strong>{totalAnuncios ?? '—'}</strong>
                <span>Anúncios publicados</span>
              </div>
            </div>

            <h2>Dados da conta</h2>
            <div className="profile-dados">
              <div className="profile-dado">
                <p className="profile-dado-label">E-mail</p>
                <p className="profile-dado-valor">{usuario.email}</p>
              </div>
              <div className="profile-dado">
                <p className="profile-dado-label">Telefone</p>
                <p className="profile-dado-valor">{usuario.telefone ?? 'Não informado'}</p>
              </div>
            </div>

            <button type="button" className="secondary-button" onClick={sair}>
              Sair da conta
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}
