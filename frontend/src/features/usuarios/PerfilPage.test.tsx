import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../../App'
import { AuthProvider } from '../autenticacao/AuthProvider'
import {
  obterSessaoArmazenada,
  salvarSessaoArmazenada,
} from '../autenticacao/sessaoStorage'

const usuario = {
  id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70',
  nome: 'Ana Silva',
  email: 'ana@example.com',
  telefone: '+5511987654321',
  status: 'ATIVO',
  criado_em: '2026-09-13T01:00:00Z',
  atualizado_em: '2026-09-13T01:00:00Z',
}
function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}
function renderPagina() {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>,
  )
}
beforeEach(() => {
  window.history.replaceState({}, '', '/perfil')
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario,
    }),
  )
})
afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

it('carrega o perfil autenticado e cancela alterações sem gravar', async () => {
  const fetchMock = vi.fn().mockResolvedValue(resposta(usuario))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Editar dados' }))
  await user.clear(screen.getByLabelText('Nome completo'))
  await user.type(screen.getByLabelText('Nome completo'), 'Outro nome')
  await user.click(screen.getByRole('button', { name: 'Cancelar' }))
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ana Silva')
  await user.click(screen.getByRole('button', { name: 'Editar dados' }))
  expect(screen.getByLabelText('Nome completo')).toHaveValue('Ana Silva')
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe(
    'Bearer access-token',
  )
})

it('salva o próprio perfil, remove telefone e sincroniza a sessão e o cabeçalho', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(resposta(usuario))
    .mockResolvedValueOnce(resposta({ ...usuario, nome: 'Ana Maria', telefone: null }))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Editar dados' }))
  await user.clear(screen.getByLabelText('Nome completo'))
  await user.type(screen.getByLabelText('Nome completo'), ' Ana Maria ')
  await user.clear(screen.getByLabelText('Telefone (opcional)'))
  await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))
  expect(
    await screen.findByText('Seus dados foram atualizados com sucesso.'),
  ).toBeInTheDocument()
  const [url, init] = fetchMock.mock.calls[1]
  expect(url).toContain(`/users/${usuario.id}`)
  expect(init.method).toBe('PATCH')
  expect(JSON.parse(init.body)).toEqual({
    nome: 'Ana Maria',
    email: 'ana@example.com',
    telefone: null,
  })
  expect(obterSessaoArmazenada()?.usuario.nome).toBe('Ana Maria')
  expect(screen.getAllByText('Ana Maria')).toHaveLength(2)
})

it('informa e-mail duplicado, preserva o formulário e não altera a sessão', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(resposta(usuario))
      .mockResolvedValueOnce(
        resposta({ detail: 'Já existe um usuário cadastrado com este e-mail.' }, 409),
      ),
  )
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Editar dados' }))
  await user.clear(screen.getByLabelText('E-mail'))
  await user.type(screen.getByLabelText('E-mail'), 'outra@example.com')
  await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))
  expect(
    await screen.findByText('Já existe um usuário cadastrado com este e-mail.'),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('E-mail')).toHaveValue('outra@example.com')
  expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true')
  expect(obterSessaoArmazenada()?.usuario.email).toBe(usuario.email)
})

it('valida nome, e-mail e telefone antes de enviar', async () => {
  const fetchMock = vi.fn().mockResolvedValue(resposta(usuario))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Editar dados' }))
  await user.clear(screen.getByLabelText('Nome completo'))
  await user.clear(screen.getByLabelText('E-mail'))
  await user.type(screen.getByLabelText('E-mail'), 'invalido')
  await user.clear(screen.getByLabelText('Telefone (opcional)'))
  await user.type(screen.getByLabelText('Telefone (opcional)'), '123')
  await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))
  expect(screen.getByText('Informe seu nome.')).toBeInTheDocument()
  expect(screen.getByText('Informe um e-mail válido.')).toBeInTheDocument()
  expect(
    screen.getByText('Informe DDD e número, com 10 ou 11 dígitos.'),
  ).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('permite tentar novamente quando o carregamento falha', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce(resposta(usuario)),
  )
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Tentar novamente' }))
  expect(await screen.findByRole('heading', { name: usuario.nome })).toBeInTheDocument()
})

it.each(['/perfil', '/perfil/enderecos'])(
  'protege a rota %s sem sessão',
  async (rota) => {
    sessionStorage.clear()
    window.history.replaceState({}, '', rota)
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    expect(await screen.findByText('Bem-vindo de volta')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
    expect(fetchMock).not.toHaveBeenCalled()
  },
)

it('preserva tokens renovados durante o salvamento e bloqueia envio duplo', async () => {
  let concluir!: (valor: unknown) => void
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(resposta(usuario))
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          concluir = resolve
        }),
    )
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Editar dados' }))
  await user.dblClick(screen.getByRole('button', { name: 'Salvar alterações' }))
  expect(screen.getByRole('button', { name: 'Salvando...' })).toBeDisabled()
  expect(fetchMock).toHaveBeenCalledTimes(2)
  salvarSessaoArmazenada({
    ...obterSessaoArmazenada()!,
    accessToken: 'novo-token',
    refreshToken: 'novo-refresh',
  })
  concluir(resposta({ ...usuario, nome: 'Ana Atualizada' }))
  await waitFor(() =>
    expect(obterSessaoArmazenada()?.usuario.nome).toBe('Ana Atualizada'),
  )
  expect(obterSessaoArmazenada()?.accessToken).toBe('novo-token')
})
