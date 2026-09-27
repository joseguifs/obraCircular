import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { CampoConta } from '../../components/CampoConta'
import { ApiError } from '../../lib/api'
import { obterIniciais } from '../../lib/texto'
import { atualizarUsuarioDaSessao } from '../autenticacao/sessaoStorage'
import { useAuth } from '../autenticacao/useAuth'
import type { Usuario } from './types'
import { atualizarUsuario, obterUsuario } from './usuarioApi'
import { validarPerfil, type PerfilForm } from './validacaoPerfil'

function dadosDoUsuario(usuario: Usuario): PerfilForm {
  return { nome: usuario.nome, email: usuario.email, telefone: usuario.telefone ?? '' }
}

export function PerfilPage() {
  const { sessao, encerrarSessao } = useAuth()
  const navegar = useNavigate()
  const usuarioId = sessao!.usuario.id
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [formulario, setFormulario] = useState<PerfilForm>({
    nome: '',
    email: '',
    telefone: '',
  })
  const [editando, setEditando] = useState(false)
  const [carregando, setCarregando] = useState(true)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [erros, setErros] = useState<Partial<Record<keyof PerfilForm, string>>>({})
  const [tentativa, setTentativa] = useState(0)

  useEffect(() => {
    let ativo = true
    obterUsuario(usuarioId)
      .then((dados) => {
        if (!ativo) return
        setUsuario(dados)
        setFormulario(dadosDoUsuario(dados))
        atualizarUsuarioDaSessao(dados)
      })
      .catch((falha: unknown) => {
        if (ativo)
          setErro(
            falha instanceof ApiError
              ? falha.message
              : 'Não foi possível carregar seu perfil.',
          )
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [usuarioId, tentativa])

  function cancelar() {
    setFormulario(dadosDoUsuario(usuario!))
    setEditando(false)
    setErros({})
    setErro('')
  }

  function sair() {
    encerrarSessao()
    navegar('/login', { replace: true })
  }

  async function salvar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando) return
    const novosErros = validarPerfil(formulario)
    setErros(novosErros)
    setErro('')
    setSucesso('')
    if (Object.keys(novosErros).length) return
    setEnviando(true)
    try {
      const atualizado = await atualizarUsuario(usuarioId, {
        nome: formulario.nome.trim(),
        email: formulario.email.trim().toLowerCase(),
        telefone: formulario.telefone.trim() || null,
      })
      setUsuario(atualizado)
      setFormulario(dadosDoUsuario(atualizado))
      atualizarUsuarioDaSessao(atualizado)
      setEditando(false)
      setSucesso('Seus dados foram atualizados com sucesso.')
    } catch (falha) {
      if (falha instanceof ApiError && falha.status === 409) {
        setErros({ email: falha.message })
      } else {
        setErro(
          falha instanceof ApiError
            ? falha.message
            : 'Não foi possível salvar seu perfil. Tente novamente.',
        )
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="profile-page">
      <Link to="/home" className="back-button">
        ← Voltar para a home
      </Link>
      <nav className="account-nav" aria-label="Minha conta">
        <Link to="/perfil" aria-current="page">
          Meu perfil
        </Link>
        <Link to="/perfil/enderecos">Meus endereços</Link>
      </nav>
      {carregando ? (
        <p role="status">Carregando seu perfil...</p>
      ) : !usuario ? (
        <div className="publish-card">
          <p role="alert">{erro}</p>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setCarregando(true)
              setErro('')
              setTentativa((atual) => atual + 1)
            }}
          >
            Tentar novamente
          </button>
        </div>
      ) : (
        <div className="profile-grid">
          <section className="profile-card" aria-label="Meu perfil">
            <div className="profile-capa" />
            <div className="profile-corpo">
              <div className="profile-cabecalho">
                <span className="profile-avatar" aria-hidden="true">
                  {obterIniciais(usuario.nome)}
                </span>
                <div>
                  <h1>{usuario.nome}</h1>
                  <p className="profile-desde">
                    Meu perfil ·{' '}
                    {usuario.status === 'ATIVO' ? 'Conta ativa' : 'Conta inativa'}
                  </p>
                </div>
              </div>
              <h2>Dados da conta</h2>
              {sucesso && (
                <p className="account-success" role="status">
                  {sucesso}
                </p>
              )}
              {erro && (
                <p className="form-alert" role="alert">
                  {erro}
                </p>
              )}
              {editando ? (
                <form onSubmit={salvar} noValidate aria-busy={enviando}>
                  <fieldset className="account-fields" disabled={enviando}>
                    <legend className="account-legend">Editar dados básicos</legend>
                    {(
                      [
                        ['nome', 'Nome completo', 'text', 'name', 150],
                        ['email', 'E-mail', 'email', 'email', 255],
                        ['telefone', 'Telefone (opcional)', 'tel', 'tel', 20],
                      ] as const
                    ).map(([campo, label, type, autoComplete, maxLength]) => (
                      <CampoConta
                        key={campo}
                        id={campo}
                        name={campo}
                        label={label}
                        type={type}
                        autoComplete={autoComplete}
                        maxLength={maxLength}
                        required={campo !== 'telefone'}
                        value={formulario[campo]}
                        erro={erros[campo]}
                        onChange={(evento) => {
                          setFormulario((atual) => ({
                            ...atual,
                            [campo]: evento.target.value,
                          }))
                          setErros((atual) => ({ ...atual, [campo]: undefined }))
                          setErro('')
                        }}
                      />
                    ))}
                    <div className="account-actions">
                      <button type="submit" className="submit-button">
                        {enviando ? 'Salvando...' : 'Salvar alterações'}
                      </button>
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={cancelar}
                      >
                        Cancelar
                      </button>
                    </div>
                  </fieldset>
                </form>
              ) : (
                <>
                  <dl className="profile-dados">
                    <div className="profile-dado">
                      <dt className="profile-dado-label">E-mail</dt>
                      <dd className="profile-dado-valor">{usuario.email}</dd>
                    </div>
                    <div className="profile-dado">
                      <dt className="profile-dado-label">Telefone</dt>
                      <dd className="profile-dado-valor">
                        {usuario.telefone ?? 'Não informado'}
                      </dd>
                    </div>
                  </dl>
                  <div className="account-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => {
                        setEditando(true)
                        setSucesso('')
                      }}
                    >
                      Editar dados
                    </button>
                    <button type="button" className="secondary-button" onClick={sair}>
                      Sair da conta
                    </button>
                  </div>
                </>
              )}
            </div>
          </section>
          <aside className="account-aside">
            <span className="step-label">Seus locais</span>
            <h2>Meus endereços</h2>
            <p>
              Mantenha os dados de seus endereços atualizados para suas próximas
              negociações.
            </p>
            <Link className="secondary-button" to="/perfil/enderecos">
              Visualizar endereços →
            </Link>
          </aside>
        </div>
      )}
    </main>
  )
}
