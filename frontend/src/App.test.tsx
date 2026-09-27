import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'
import { AuthProvider } from './features/autenticacao/AuthProvider'

const usuario = {
  id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70',
  nome: 'Ana Silva',
  email: 'ana@example.com',
  telefone: null,
  status: 'ATIVO',
  criado_em: '2026-09-13T01:00:00Z',
  atualizado_em: '2026-09-13T01:00:00Z',
}

beforeEach(() => {
  window.history.replaceState({}, '', '/login')
  sessionStorage.clear()
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

function renderAplicacao() {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>,
  )
}

function respostaJson(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function respostaListaVazia() {
  return respostaJson({ items: [], total: 0, offset: 0, limit: 100 })
}

it('redireciona para a home após o login e permite encerrar a sessão', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(
      respostaJson({
        access_token: 'access-token',
        refresh_token: 'refresh-token',
        token_type: 'bearer',
        expires_in: 900,
      }),
    )
    .mockResolvedValueOnce(respostaJson(usuario))
    // HomePage: categorias, total de anúncios do vendedor, listagem de anúncios
    .mockResolvedValueOnce(respostaListaVazia())
    .mockResolvedValueOnce(respostaListaVazia())
    .mockResolvedValueOnce(respostaListaVazia())
    // PerfilPage: dados atuais do usuário
    .mockResolvedValueOnce(respostaJson(usuario))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()

  renderAplicacao()
  await user.type(screen.getByLabelText('E-mail'), 'ana@example.com')
  await user.type(screen.getByLabelText('Senha'), 'senha-forte-123')
  await user.click(screen.getByRole('button', { name: 'Entrar na plataforma' }))

  expect(await screen.findByText('Olá, Ana')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/home')

  await user.click(screen.getByRole('link', { name: 'Ver meu perfil' }))
  await user.click(await screen.findByRole('button', { name: 'Sair da conta' }))

  expect(await screen.findByText('Bem-vindo de volta')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/login')
  expect(sessionStorage.getItem('obra-circular:sessao')).toBeNull()
})

it('protege a home de visitantes sem sessão', async () => {
  window.history.replaceState({}, '', '/home')

  renderAplicacao()

  expect(await screen.findByText('Bem-vindo de volta')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/login')
})

it('exibe o cadastro em sua própria rota', () => {
  window.history.replaceState({}, '', '/cadastro')

  renderAplicacao()

  expect(screen.getByText('Crie sua conta')).toBeInTheDocument()
})

it('redireciona usuário autenticado para fora das rotas públicas', async () => {
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario,
    }),
  )
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respostaListaVazia()))

  renderAplicacao()

  expect(await screen.findByText('Olá, Ana')).toBeInTheDocument()
  expect(window.location.pathname).toBe('/home')
})

it('exibe uma página para endereços inexistentes', () => {
  window.history.replaceState({}, '', '/rota-inexistente')

  renderAplicacao()

  expect(screen.getByText('Página não encontrada')).toBeInTheDocument()
})
