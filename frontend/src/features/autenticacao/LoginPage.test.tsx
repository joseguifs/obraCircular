import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'

const tokens = {
  access_token: 'access-token',
  refresh_token: 'refresh-token',
  token_type: 'bearer',
  expires_in: 900,
}

const usuario = {
  id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70',
  nome: 'Ana Silva',
  email: 'ana@example.com',
  telefone: null,
  status: 'ATIVO',
  criado_em: '2026-09-13T01:00:00Z',
  atualizado_em: '2026-09-13T01:00:00Z',
}

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe('LoginPage', () => {
  it('valida os campos antes de chamar o backend', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))

    expect(await screen.findByText('Informe seu e-mail.')).toBeInTheDocument()
    expect(screen.getByText('Informe sua senha.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('autentica, consulta o usuário e entrega a sessão', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => tokens })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => usuario })
    vi.stubGlobal('fetch', fetchMock)
    const aoAutenticar = vi.fn()
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={aoAutenticar} aoCadastrar={vi.fn()} />)
    await user.type(screen.getByLabelText('E-mail'), 'ANA@EXAMPLE.COM')
    await user.type(screen.getByLabelText('Senha'), 'senha-forte-123')
    await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))

    expect(aoAutenticar).toHaveBeenCalledWith(
      expect.objectContaining({
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
        expiraEm: expect.any(Number),
        usuario,
      }),
    )
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/api/v1/auth/login')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      email: 'ana@example.com',
      senha: 'senha-forte-123',
    })
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe('Bearer access-token')
    expect(sessionStorage.getItem('obra-circular:sessao')).toContain('access-token')
  })

  it('exibe a mensagem de credenciais inválidas devolvida pela API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'E-mail ou senha inválidos.' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} />)
    await user.type(screen.getByLabelText('E-mail'), 'ana@example.com')
    await user.type(screen.getByLabelText('Senha'), 'senha-errada')
    await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos.')
  })
})
