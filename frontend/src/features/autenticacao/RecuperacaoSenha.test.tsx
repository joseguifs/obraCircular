import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { EsqueciSenhaPage } from './EsqueciSenhaPage'
import { LoginPage } from './LoginPage'
import { RedefinirSenhaPage } from './RedefinirSenhaPage'

const LINK_INVALIDO = 'Este link de redefinição é inválido ou expirou. Solicite um novo link.'

function respostaOk(status = 204, corpo: unknown = undefined) {
  return { ok: true, status, json: async () => corpo }
}

function respostaErro(status: number, detail: string) {
  return { ok: false, status, json: async () => ({ detail }) }
}

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe('LoginPage', () => {
  it('leva para a recuperação de senha', async () => {
    const aoRecuperarSenha = vi.fn()
    const user = userEvent.setup()

    render(
      <LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={aoRecuperarSenha} />,
    )
    await user.click(screen.getByRole('button', { name: 'Esqueci minha senha' }))

    expect(aoRecuperarSenha).toHaveBeenCalled()
  })
})

describe('EsqueciSenhaPage', () => {
  it('valida o e-mail antes de chamar o backend', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<EsqueciSenhaPage aoVoltarParaLogin={vi.fn()} />)
    await user.type(screen.getByLabelText('E-mail'), 'email-invalido')
    await user.click(screen.getByRole('button', { name: 'Enviar link de recuperação' }))

    expect(await screen.findByText('Informe um e-mail válido.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('solicita o link e mostra a confirmação', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respostaOk(202, { detail: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<EsqueciSenhaPage aoVoltarParaLogin={vi.fn()} />)
    await user.type(screen.getByLabelText('E-mail'), 'ANA@EXAMPLE.COM')
    await user.click(screen.getByRole('button', { name: 'Enviar link de recuperação' }))

    expect(await screen.findByRole('heading', { name: 'Link enviado' })).toBeInTheDocument()
    expect(screen.getByText('ana@example.com')).toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/api/v1/auth/forgot-password')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: 'ana@example.com' })

    await user.click(screen.getByRole('button', { name: 'Enviar novamente' }))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

describe('RedefinirSenhaPage', () => {
  it('sem token na URL mostra o link como inválido', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(
      <RedefinirSenhaPage token={null} aoIrParaLogin={vi.fn()} aoSolicitarNovoLink={vi.fn()} />,
    )

    expect(screen.getByRole('heading', { name: 'Não foi possível usar este link' })).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('mostra o erro quando o token expirou', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respostaErro(400, LINK_INVALIDO)))
    const aoSolicitarNovoLink = vi.fn()
    const user = userEvent.setup()

    render(
      <RedefinirSenhaPage
        token="token-expirado"
        aoIrParaLogin={vi.fn()}
        aoSolicitarNovoLink={aoSolicitarNovoLink}
      />,
    )

    expect(await screen.findByText(LINK_INVALIDO)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Solicitar novo link' }))
    expect(aoSolicitarNovoLink).toHaveBeenCalled()
  })

  it('valida o token, confere as senhas e redefine', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respostaOk())
    vi.stubGlobal('fetch', fetchMock)
    const aoIrParaLogin = vi.fn()
    const user = userEvent.setup()

    render(
      <RedefinirSenhaPage
        token="token-valido"
        aoIrParaLogin={aoIrParaLogin}
        aoSolicitarNovoLink={vi.fn()}
      />,
    )

    const novaSenha = await screen.findByLabelText('Nova senha')
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://localhost:8000/api/v1/auth/reset-password/validate',
    )

    await user.type(novaSenha, 'NovaSenha123')
    await user.type(screen.getByLabelText('Confirmar nova senha'), 'OutraSenha123')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(await screen.findByText('As senhas não coincidem.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await user.clear(screen.getByLabelText('Confirmar nova senha'))
    await user.type(screen.getByLabelText('Confirmar nova senha'), 'NovaSenha123')
    await user.click(screen.getByRole('button', { name: 'Salvar nova senha' }))

    expect(await screen.findByRole('heading', { name: 'Senha redefinida' })).toBeInTheDocument()
    expect(fetchMock.mock.calls[1][0]).toBe('http://localhost:8000/api/v1/auth/reset-password')
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      token: 'token-valido',
      nova_senha: 'NovaSenha123',
    })

    await user.click(screen.getByRole('button', { name: 'Ir para o login' }))
    expect(aoIrParaLogin).toHaveBeenCalled()
  })
})
