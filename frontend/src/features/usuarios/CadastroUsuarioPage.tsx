import { useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import { ApiError } from '../../lib/api'
import type { CadastroUsuarioForm, CampoCadastro, ErrosCadastro, Usuario } from './types'
import { cadastrarUsuario } from './usuarioApi'
import { emailEhValido, forcaDaSenha, validarCadastro } from './validacaoCadastro'

const formularioInicial: CadastroUsuarioForm = {
  nome: '',
  email: '',
  telefone: '',
  senha: '',
  confirmarSenha: '',
}

const TEXTO_FORCA = ['', 'Fraca', 'Média', 'Forte'] as const

export function CadastroUsuarioPage() {
  const [formulario, setFormulario] = useState(formularioInicial)
  const [termos, setTermos] = useState(false)
  const [erros, setErros] = useState<ErrosCadastro>({})
  const [erroGeral, setErroGeral] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [usuarioCriado, setUsuarioCriado] = useState<Usuario | null>(null)

  function atualizarCampo(evento: ChangeEvent<HTMLInputElement>) {
    const campo = evento.target.name as CampoCadastro
    const valor = evento.target.value
    setFormulario((atual) => ({ ...atual, [campo]: valor }))
    setErros((atuais) => ({ ...atuais, [campo]: undefined }))
    setErroGeral('')
  }

  function alternarTermos() {
    setTermos((atual) => !atual)
    setErros((atuais) => ({ ...atuais, termos: undefined }))
    setErroGeral('')
  }

  async function enviarFormulario(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const novosErros = validarCadastro(formulario, termos)
    setErros(novosErros)
    setErroGeral('')

    if (Object.keys(novosErros).length > 0) {
      return
    }

    setEnviando(true)
    try {
      const telefone = formulario.telefone.trim()
      const usuario = await cadastrarUsuario({
        nome: formulario.nome.trim(),
        email: formulario.email.trim().toLowerCase(),
        senha: formulario.senha,
        ...(telefone ? { telefone } : {}),
      })
      setUsuarioCriado(usuario)
      setFormulario(formularioInicial)
      setTermos(false)
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

  function iniciarNovoCadastro() {
    setUsuarioCriado(null)
    setErros({})
    setErroGeral('')
  }

  const forca = forcaDaSenha(formulario.senha)
  const emailValido = !!formulario.email && emailEhValido(formulario.email)

  return (
    <main className="signup-shell">
      <section className="brand-panel" aria-label="Sobre a Obra Circular">
        <Logo />

        <div className="brand-copy">
          <span className="eyebrow">Construir também é reaproveitar</span>
          <h1>Materiais com história. Obras com futuro.</h1>
          <p>
            Compre e venda excedentes de obra com segurança, reduzindo custos e evitando
            desperdícios.
          </p>
        </div>

        <ul className="benefit-list" aria-label="Benefícios da plataforma">
          <li>
            <LeafIcon />
            <span>
              <strong>Economia circular</strong>
              Cada material reaproveitado deixa de virar descarte.
            </span>
          </li>
          <li>
            <ShieldIcon />
            <span>
              <strong>Negociações mais seguras</strong>
              Uma comunidade feita para quem compra, vende e constrói.
            </span>
          </li>
        </ul>
      </section>

      <section className="form-panel">
        <div className="mobile-logo">
          <Logo />
        </div>

        <div className="form-card">
          {usuarioCriado ? (
            <CadastroConcluido usuario={usuarioCriado} aoReiniciar={iniciarNovoCadastro} />
          ) : (
            <>
              <header className="form-heading">
                <span className="step-label">Comece por aqui</span>
                <h2>Crie sua conta</h2>
                <p>Leva menos de dois minutos. Comece a comprar, vender e reaproveitar materiais.</p>
              </header>

              <form
                className="signup-form"
                onSubmit={enviarFormulario}
                aria-busy={enviando}
                noValidate
              >
                <CampoTexto
                  id="nome"
                  label="Nome completo"
                  name="nome"
                  autoComplete="name"
                  placeholder="Como devemos chamar você?"
                  value={formulario.nome}
                  error={erros.nome}
                  onChange={atualizarCampo}
                  maxLength={150}
                  icon={<UserIcon />}
                />

                <CampoTexto
                  id="email"
                  label="E-mail"
                  name="email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="voce@exemplo.com"
                  value={formulario.email}
                  error={erros.email}
                  onChange={atualizarCampo}
                  icon={<MailIcon />}
                  adorno={emailValido ? <CheckIcon /> : null}
                />

                <CampoTexto
                  id="telefone"
                  label="Telefone"
                  optional
                  name="telefone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="(11) 98765-4321"
                  value={formulario.telefone}
                  error={erros.telefone}
                  onChange={atualizarCampo}
                  maxLength={20}
                  icon={<PhoneIcon />}
                />

                <div className="password-grid">
                  <CampoTexto
                    id="senha"
                    label="Senha"
                    name="senha"
                    type={mostrarSenha ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Mínimo de 8 caracteres"
                    value={formulario.senha}
                    error={erros.senha}
                    onChange={atualizarCampo}
                    maxLength={72}
                  />

                  <CampoTexto
                    id="confirmarSenha"
                    label="Confirmar senha"
                    name="confirmarSenha"
                    type={mostrarSenha ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Digite novamente"
                    value={formulario.confirmarSenha}
                    error={erros.confirmarSenha}
                    onChange={atualizarCampo}
                    maxLength={72}
                  />
                </div>

                {formulario.senha && (
                  <div className="password-strength">
                    <div className="password-strength-bars">
                      {[1, 2, 3].map((nivel) => (
                        <div
                          key={nivel}
                          className={`password-strength-bar ${
                            forca >= nivel ? `password-strength-bar--${forca}` : ''
                          }`}
                        />
                      ))}
                    </div>
                    <span>{TEXTO_FORCA[forca]}</span>
                  </div>
                )}

                <div className="check-option">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={mostrarSenha}
                    aria-label="Mostrar senhas"
                    className={`check-toggle ${mostrarSenha ? 'check-toggle--marcado' : ''}`}
                    onClick={() => setMostrarSenha((atual) => !atual)}
                  >
                    <CheckIcon />
                  </button>
                  <span>Mostrar senhas</span>
                </div>

                <div className="check-option check-option--termos">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={termos}
                    aria-label="Aceitar termos de uso"
                    aria-describedby={erros.termos ? 'termos-error' : undefined}
                    className={`check-toggle ${termos ? 'check-toggle--marcado' : ''} ${
                      erros.termos ? 'check-toggle--erro' : ''
                    }`}
                    onClick={alternarTermos}
                  >
                    <CheckIcon />
                  </button>
                  <p>
                    Li e aceito os <a href="#">Termos de Uso</a> e a{' '}
                    <a href="#">Política de Privacidade</a>.
                  </p>
                </div>
                {erros.termos && (
                  <p className="field-error field-error--termos" id="termos-error">
                    {erros.termos}
                  </p>
                )}

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
                      Criando sua conta...
                    </>
                  ) : (
                    <>
                      Criar minha conta
                      <ArrowIcon />
                    </>
                  )}
                </button>

                <p className="privacy-note">
                  Ao continuar, você concorda em usar a plataforma de forma responsável e
                  manter seus dados atualizados.
                </p>
              </form>

              <div className="form-divider" />
              <p className="login-hint">
                Já possui uma conta? <a href="#">Entrar</a>
              </p>
            </>
          )}
        </div>
      </section>
    </main>
  )
}

interface CampoTextoProps {
  id: string
  label: string
  name: CampoCadastro
  value: string
  error?: string
  optional?: boolean
  type?: string
  inputMode?: 'email' | 'tel' | 'text'
  autoComplete?: string
  placeholder?: string
  maxLength?: number
  icon?: ReactNode
  /** Elemento exibido dentro da caixa, depois do input (ex.: ícone de "e-mail válido"). */
  adorno?: ReactNode
  onChange: (evento: ChangeEvent<HTMLInputElement>) => void
}

function CampoTexto({ label, error, optional, icon, adorno, ...inputProps }: CampoTextoProps) {
  const errorId = `${inputProps.id}-error`
  return (
    <div className="field-group">
      <label htmlFor={inputProps.id}>
        {label}
        {optional && <span>Opcional</span>}
      </label>
      <div className={`field-box ${error ? 'field-box--erro' : ''}`}>
        {icon && <span className="field-icon">{icon}</span>}
        <input
          {...inputProps}
          required={!optional}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
        />
        {adorno && <span className="field-adorno">{adorno}</span>}
      </div>
      {error && (
        <p className="field-error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  )
}

function CadastroConcluido({
  usuario,
  aoReiniciar,
}: {
  usuario: Usuario
  aoReiniciar: () => void
}) {
  return (
    <div className="success-state" role="status">
      <div className="success-icon" aria-hidden="true">
        <CheckIcon />
      </div>
      <span className="step-label">Cadastro concluído</span>
      <h2>Boas-vindas, {usuario.nome.split(' ')[0]}!</h2>
      <p>
        Sua conta foi criada com o e-mail <strong>{usuario.email}</strong>. Agora você já faz
        parte da comunidade Obra Circular.
      </p>
      <button className="submit-button" type="button" onClick={aoReiniciar}>
        Cadastrar outra pessoa
        <ArrowIcon />
      </button>
    </div>
  )
}

function Logo() {
  return (
    <div className="brand-logo" aria-label="Obra Circular">
      <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
        <circle cx="16" cy="16" r="4.4" />
        <ellipse cx="16" cy="16" rx="13" ry="6" transform="rotate(30 16 16)" />
        <ellipse cx="16" cy="16" rx="13" ry="6" transform="rotate(90 16 16)" />
        <ellipse cx="16" cy="16" rx="13" ry="6" transform="rotate(150 16 16)" />
      </svg>
      <span className="logo-type">
        Obra <strong>Circular</strong>
      </span>
    </div>
  )
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 20c1.6-3.4 4.3-5 7.5-5s5.9 1.6 7.5 5" />
    </svg>
  )
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="3" />
      <path d="M4 8l8 5 8-5" />
    </svg>
  )
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6.5" y="2.5" width="11" height="19" rx="3" />
      <path d="M11 18.5h2" />
    </svg>
  )
}

function LeafIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 4.5C12.5 4.5 6 8.1 6 14.1c0 2.9 2.1 5.4 5.4 5.4 5.8 0 8.6-6.4 8.6-15Z" />
      <path d="M4 20c2.5-4.4 6.2-7.5 11.2-9.4" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 4.8 6v5.2c0 4.7 2.9 8.2 7.2 9.8 4.3-1.6 7.2-5.1 7.2-9.8V6L12 3Z" />
      <path d="m8.8 12.1 2.1 2.1 4.5-4.7" />
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

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6.8 12.3 3.3 3.4 7.3-7.5" />
    </svg>
  )
}
