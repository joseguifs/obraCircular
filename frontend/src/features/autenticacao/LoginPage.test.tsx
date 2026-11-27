import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'
import { chamadasAlemDaVitrine } from '../../test/chamadasApi'

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

const semAnuncios = { items: [], total: 0, offset: 0, limit: 8 }

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

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))

    expect(await screen.findByText('Informe seu e-mail.')).toBeInTheDocument()
    expect(screen.getByText('Informe sua senha.')).toBeInTheDocument()
    expect(chamadasAlemDaVitrine(fetchMock)).toHaveLength(0)
  })

  it('autentica, consulta o usuário e entrega a sessão', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes('/ads?')) return { ok: true, status: 200, json: async () => semAnuncios }
      if (url.endsWith('/auth/login')) return { ok: true, status: 200, json: async () => tokens }
      return { ok: true, status: 200, json: async () => usuario }
    })
    vi.stubGlobal('fetch', fetchMock)
    const aoAutenticar = vi.fn()
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={aoAutenticar} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)
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
    const chamadas = chamadasAlemDaVitrine(fetchMock) as [string, RequestInit][]
    expect(chamadas).toHaveLength(2)
    expect(chamadas[0][0]).toBe('http://localhost:8000/api/v1/auth/login')
    expect(JSON.parse(String(chamadas[0][1].body))).toEqual({
      email: 'ana@example.com',
      senha: 'senha-forte-123',
    })
    expect((chamadas[1][1].headers as Headers).get('Authorization')).toBe(
      'Bearer access-token',
    )
    expect(sessionStorage.getItem('obra-circular:sessao')).toContain('access-token')
  })

  it('exibe o aviso e o e-mail recebidos, como após criar a conta', () => {
    render(
      <LoginPage
        aoAutenticar={vi.fn()}
        aoCadastrar={vi.fn()}
        aoRecuperarSenha={vi.fn()}
        emailInicial="ana@example.com"
        aviso="Conta criada com sucesso!"
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Conta criada com sucesso!')
    expect(screen.getByLabelText('E-mail')).toHaveValue('ana@example.com')
    expect(screen.getByLabelText('Senha')).toHaveFocus()
  })

  it('não exibe aviso quando nenhum é informado', () => {
    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveValue('')
  })

  it('exibe a mensagem de credenciais inválidas devolvida pela API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'E-mail ou senha inválidos.' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)
    await user.type(screen.getByLabelText('E-mail'), 'ana@example.com')
    await user.type(screen.getByLabelText('Senha'), 'senha-errada')
    await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos.')
  })

  it('mostra e oculta a senha pelo ícone do campo', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sem rede')))
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)
    const senha = screen.getByLabelText('Senha')
    expect(senha).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: 'Mostrar senha' }))
    expect(senha).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Ocultar senha' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: 'Ocultar senha' }))
    expect(senha).toHaveAttribute('type', 'password')
  })

  it('leva ao cadastro pelo cabeçalho e pelo fim do formulário', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('sem rede')))
    const aoCadastrar = vi.fn()
    const user = userEvent.setup()

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={aoCadastrar} aoRecuperarSenha={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    await user.click(screen.getByRole('button', { name: 'Criar uma conta' }))

    expect(aoCadastrar).toHaveBeenCalledTimes(2)
  })

  it('exibe só os anúncios pagos na vitrine e some sem destaques', async () => {
    const anuncio = (id: string, titulo: string, emDestaque: boolean) => ({
      id,
      titulo,
      preco: '89.90',
      imagem_url: null,
      imagem_capa_url: null,
      em_destaque: emDestaque,
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          items: [
            anuncio('a1', 'Porcelanato 60x60 acetinado', true),
            anuncio('a2', 'Tubos PVC 100 mm', false),
          ],
          total: 2,
          offset: 0,
          limit: 8,
        }),
      })),
    )

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)

    const vitrine = await screen.findByRole('region', { name: 'Em destaque agora' })
    expect(within(vitrine).getByText('Porcelanato 60x60 acetinado')).toBeInTheDocument()
    expect(within(vitrine).queryByText('Tubos PVC 100 mm')).not.toBeInTheDocument()
  })

  it('não mostra a vitrine quando a listagem falha', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error('sem rede'))
    vi.stubGlobal('fetch', fetchMock)

    render(<LoginPage aoAutenticar={vi.fn()} aoCadastrar={vi.fn()} aoRecuperarSenha={vi.fn()} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(screen.queryByRole('region', { name: 'Em destaque agora' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entrar na plataforma' })).toBeEnabled()
  })
})
