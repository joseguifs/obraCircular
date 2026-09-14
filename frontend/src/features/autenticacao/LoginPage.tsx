import { useState, type ChangeEvent, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import { emailEhValido } from '../usuarios/validacaoCadastro'
import { AuthLayout } from './AuthLayout'
import { autenticar } from './autenticacaoApi'
import type { Sessao } from './types'

interface LoginPageProps {
  aoAutenticar: (sessao: Sessao) => void
  aoCadastrar: () => void
}

interface ErrosLogin {
  email?: string
  senha?: string
}

export function LoginPage({ aoAutenticar, aoCadastrar }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [erros, setErros] = useState<ErrosLogin>({})
  const [erroGeral, setErroGeral] = useState('')
  const [enviando, setEnviando] = useState(false)

  function atualizarEmail(evento: ChangeEvent<HTMLInputElement>) {
    setEmail(evento.target.value)
    setErros((atuais) => ({ ...atuais, email: undefined }))
    setErroGeral('')
  }

  function atualizarSenha(evento: ChangeEvent<HTMLInputElement>) {
    setSenha(evento.target.value)
    setErros((atuais) => ({ ...atuais, senha: undefined }))
    setErroGeral('')
  }

  async function enviarFormulario(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const novosErros = validarLogin(email, senha)
    setErros(novosErros)
    setErroGeral('')

    if (Object.keys(novosErros).length > 0) return

    setEnviando(true)
    try {
      const sessao = await autenticar({ email: email.trim().toLowerCase(), senha })
      aoAutenticar(sessao)
    } catch (erro) {
      setErroGeral(
        erro instanceof ApiError
          ? erro.message
          : 'Ocorreu um erro inesperado. Tente novamente.',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <AuthLayout>
      <div className="form-card login-card">
        <header className="form-heading">
          <span className="step-label">Acesse sua conta</span>
          <h2>Bem-vindo de volta</h2>
          <p>Entre para continuar comprando, vendendo e reaproveitando materiais.</p>
        </header>

        <form className="login-form" onSubmit={enviarFormulario} aria-busy={enviando} noValidate>
          <div className="field-group">
            <label htmlFor="login-email">E-mail</label>
            <div className={`field-box ${erros.email ? 'field-box--erro' : ''}`}>
              <span className="field-icon">
                <MailIcon />
              </span>
              <input
                id="login-email"
                name="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="voce@exemplo.com"
                value={email}
                onChange={atualizarEmail}
                aria-invalid={Boolean(erros.email)}
                aria-describedby={erros.email ? 'login-email-error' : undefined}
                required
              />
            </div>
            {erros.email && (
              <p className="field-error" id="login-email-error">
                {erros.email}
              </p>
            )}
          </div>

          <div className="field-group">
            <label htmlFor="login-senha">Senha</label>
            <div className={`field-box ${erros.senha ? 'field-box--erro' : ''}`}>
              <span className="field-icon">
                <LockIcon />
              </span>
              <input
                id="login-senha"
                name="senha"
                type={mostrarSenha ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Digite sua senha"
                value={senha}
                onChange={atualizarSenha}
                maxLength={72}
                aria-invalid={Boolean(erros.senha)}
                aria-describedby={erros.senha ? 'login-senha-error' : undefined}
                required
              />
            </div>
            {erros.senha && (
              <p className="field-error" id="login-senha-error">
                {erros.senha}
              </p>
            )}
          </div>

          <div className="login-options">
            <div className="check-option">
              <button
                type="button"
                role="checkbox"
                aria-checked={mostrarSenha}
                aria-label="Mostrar senha"
                className={`check-toggle ${mostrarSenha ? 'check-toggle--marcado' : ''}`}
                onClick={() => setMostrarSenha((atual) => !atual)}
              >
                <CheckIcon />
              </button>
              <span>Mostrar senha</span>
            </div>
          </div>

          {erroGeral && (
            <div className="form-alert" role="alert">
              <AlertIcon />
              <span>{erroGeral}</span>
            </div>
          )}

          <button className="submit-button" type="submit" disabled={enviando}>
            {enviando ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Entrando...
              </>
            ) : (
              <>
                Entrar na plataforma
                <ArrowIcon />
              </>
            )}
          </button>
        </form>

        <div className="form-divider" />
        <p className="login-hint">
          Ainda não possui uma conta?{' '}
          <button type="button" onClick={aoCadastrar}>
            Criar conta
          </button>
        </p>
      </div>
    </AuthLayout>
  )
}

function validarLogin(email: string, senha: string): ErrosLogin {
  const erros: ErrosLogin = {}
  if (!email.trim()) erros.email = 'Informe seu e-mail.'
  else if (!emailEhValido(email)) erros.email = 'Informe um e-mail válido.'

  if (!senha) erros.senha = 'Informe sua senha.'
  return erros
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="3" />
      <path d="M4 8l8 5 8-5" />
    </svg>
  )
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4.5" y="10" width="15" height="11" rx="3" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14.5v2.5" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6.8 12.3 3.3 3.4 7.3-7.5" />
    </svg>
  )
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.8v5.3M12 16.4v.1" />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </svg>
  )
}
