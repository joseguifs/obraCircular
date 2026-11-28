import { useState, type ChangeEvent, type FormEvent } from 'react'
import { ApiError } from '../../lib/api'
import { emailEhValido } from '../usuarios/validacaoCadastro'
import { AuthLayout } from './AuthLayout'
import { autenticar } from './autenticacaoApi'
import type { Sessao } from './types'

interface LoginPageProps {
  aoAutenticar: (sessao: Sessao) => void
  aoCadastrar: () => void
  aoRecuperarSenha: () => void
  /** E-mail já preenchido, por exemplo o da conta recém-criada. */
  emailInicial?: string
  /** Mensagem de sucesso exibida no topo do formulário (ex.: conta criada). */
  aviso?: string
}

interface ErrosLogin {
  email?: string
  senha?: string
}

export function LoginPage({
  aoAutenticar,
  aoCadastrar,
  aoRecuperarSenha,
  emailInicial = '',
  aviso,
}: LoginPageProps) {
  const [email, setEmail] = useState(emailInicial)
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
    <AuthLayout
      acaoCabecalho={
        <p className="auth-header-texto">
          Ainda não tem conta?{' '}
          <button type="button" onClick={aoCadastrar}>
            Criar conta
          </button>
        </p>
      }
    >
      <div className="form-card login-card">
        <header className="form-heading">
          <h2>Entrar</h2>
          <p>Continue comprando, vendendo e reaproveitando materiais.</p>
        </header>

        {aviso && (
          <div className="form-alert form-alert--sucesso login-aviso" role="status">
            <CheckIcon />
            <span>{aviso}</span>
          </div>
        )}

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
            <div className="login-senha-rotulo">
              <label htmlFor="login-senha">Senha</label>
              <button type="button" className="login-esqueci" onClick={aoRecuperarSenha}>
                Esqueci minha senha
              </button>
            </div>
            <div className={`field-box login-senha-campo ${erros.senha ? 'field-box--erro' : ''}`}>
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
                autoFocus={Boolean(emailInicial)}
                required
              />
              <button
                type="button"
                className="login-olho"
                aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                aria-pressed={mostrarSenha}
                onClick={() => setMostrarSenha((atual) => !atual)}
              >
                {mostrarSenha ? <OlhoFechadoIcon /> : <OlhoIcon />}
              </button>
            </div>
            {erros.senha && (
              <p className="field-error" id="login-senha-error">
                {erros.senha}
              </p>
            )}
          </div>

          {erroGeral && (
            <div className="form-alert" role="alert">
              <AlertIcon />
              <span>{erroGeral}</span>
            </div>
          )}

          <button className="submit-button login-entrar" type="submit" disabled={enviando}>
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

        <p className="login-separador">Primeira vez na Obra Circular?</p>
        <button type="button" className="login-criar" onClick={aoCadastrar}>
          Criar uma conta
        </button>
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

function OlhoIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12C3.5 10.3 7 6 12 6s8.5 4.3 9.5 6c-1 1.7-4.5 6-9.5 6s-8.5-4.3-9.5-6z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function OlhoFechadoIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.6 6.2A9.8 9.8 0 0 1 12 6c5 0 8.5 4.3 9.5 6-.4.7-1.3 2-2.6 3.2M6.6 7.7C4.7 9 3.2 10.9 2.5 12c1 1.7 4.5 6 9.5 6 1.6 0 3-.4 4.3-1.1" />
      <path d="M9.9 10a3 3 0 0 0 4.1 4.1" />
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
