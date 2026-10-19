import { useState, type ChangeEvent, type FormEvent } from 'react'
import { mensagemApiErro } from '../../lib/api'
import { emailEhValido } from '../usuarios/validacaoCadastro'
import { AuthLayout } from './AuthLayout'
import { solicitarRecuperacaoSenha } from './autenticacaoApi'
import { AlertIcon, ArrowIcon, BackIcon, MailIcon } from './icones'

interface EsqueciSenhaPageProps {
  aoVoltarParaLogin: () => void
}

export function EsqueciSenhaPage({ aoVoltarParaLogin }: EsqueciSenhaPageProps) {
  const [email, setEmail] = useState('')
  const [erroEmail, setErroEmail] = useState('')
  const [erroGeral, setErroGeral] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [emailEnviado, setEmailEnviado] = useState<string | null>(null)

  function atualizarEmail(evento: ChangeEvent<HTMLInputElement>) {
    setEmail(evento.target.value)
    setErroEmail('')
    setErroGeral('')
  }

  async function enviar(emailNormalizado: string) {
    setEnviando(true)
    setErroGeral('')
    try {
      await solicitarRecuperacaoSenha(emailNormalizado)
      setEmailEnviado(emailNormalizado)
    } catch (erro) {
      setErroGeral(mensagemApiErro(erro, 'Ocorreu um erro inesperado. Tente novamente.'))
    } finally {
      setEnviando(false)
    }
  }

  async function enviarFormulario(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!email.trim()) {
      setErroEmail('Informe seu e-mail.')
      return
    }
    if (!emailEhValido(email)) {
      setErroEmail('Informe um e-mail válido.')
      return
    }
    await enviar(email.trim().toLowerCase())
  }

  return (
    <AuthLayout>
      <div className="form-card recuperacao-card">
        {emailEnviado ? (
          <div className="success-state recuperacao-status" role="status">
            <div className="success-icon" aria-hidden="true">
              <MailIcon />
            </div>
            <span className="step-label">Verifique seu e-mail</span>
            <h2>Link enviado</h2>
            <p>
              Se existir uma conta com o e-mail <strong>{emailEnviado}</strong>, você receberá
              um link para criar uma nova senha. Confira também a caixa de spam.
            </p>
            <button className="submit-button" type="button" onClick={aoVoltarParaLogin}>
              Voltar para o login
              <ArrowIcon />
            </button>
            {erroGeral && (
              <div className="form-alert recuperacao-alerta" role="alert">
                <AlertIcon />
                <span>{erroGeral}</span>
              </div>
            )}
            <p className="login-hint recuperacao-reenvio">
              Não recebeu?{' '}
              <button type="button" onClick={() => enviar(emailEnviado)} disabled={enviando}>
                {enviando ? 'Reenviando...' : 'Enviar novamente'}
              </button>
            </p>
          </div>
        ) : (
          <>
            <button type="button" className="recuperacao-voltar" onClick={aoVoltarParaLogin}>
              <BackIcon />
              Voltar para o login
            </button>

            <header className="form-heading">
              <span className="step-label">Recuperar acesso</span>
              <h2>Esqueceu sua senha?</h2>
              <p>
                Informe o e-mail da sua conta. Enviaremos um link para você criar uma nova
                senha.
              </p>
            </header>

            <form
              className="recuperacao-form"
              onSubmit={enviarFormulario}
              aria-busy={enviando}
              noValidate
            >
              <div className="field-group">
                <label htmlFor="recuperacao-email">E-mail</label>
                <div className={`field-box ${erroEmail ? 'field-box--erro' : ''}`}>
                  <span className="field-icon">
                    <MailIcon />
                  </span>
                  <input
                    id="recuperacao-email"
                    name="email"
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    placeholder="voce@exemplo.com"
                    value={email}
                    onChange={atualizarEmail}
                    aria-invalid={Boolean(erroEmail)}
                    aria-describedby={erroEmail ? 'recuperacao-email-error' : undefined}
                    required
                  />
                </div>
                {erroEmail && (
                  <p className="field-error" id="recuperacao-email-error">
                    {erroEmail}
                  </p>
                )}
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
                    Enviando...
                  </>
                ) : (
                  <>
                    Enviar link de recuperação
                    <ArrowIcon />
                  </>
                )}
              </button>
            </form>
          </>
        )}
      </div>
    </AuthLayout>
  )
}
