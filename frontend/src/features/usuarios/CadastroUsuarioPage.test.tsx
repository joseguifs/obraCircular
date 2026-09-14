import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CadastroUsuarioPage } from './CadastroUsuarioPage'

const usuarioCriado = {
  id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70',
  nome: 'Ana Silva',
  email: 'ana@example.com',
  telefone: '+5511987654321',
  status: 'ATIVO',
  criado_em: '2026-09-13T01:00:00Z',
  atualizado_em: '2026-09-13T01:00:00Z',
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('CadastroUsuarioPage', () => {
  it('valida os campos antes de chamar o backend', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<CadastroUsuarioPage />)

    await user.click(screen.getByRole('button', { name: 'Criar minha conta' }))

    expect(await screen.findByText('Informe seu nome.')).toBeInTheDocument()
    expect(screen.getByText('Informe seu e-mail.')).toBeInTheDocument()
    expect(screen.getByText('A senha deve ter pelo menos 8 caracteres.')).toBeInTheDocument()
    expect(screen.getByText('É preciso aceitar os Termos de Uso.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('envia os dados válidos para o endpoint de usuários', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => usuarioCriado,
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<CadastroUsuarioPage />)

    await preencherFormulario(user)
    await user.click(screen.getByRole('button', { name: 'Criar minha conta' }))

    expect(await screen.findByText('Boas-vindas, Ana!')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/users')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body as string)).toEqual({
      nome: 'Ana Silva',
      email: 'ana@example.com',
      telefone: '(11) 98765-4321',
      senha: 'senha-forte-123',
    })
  })

  it('exibe a mensagem devolvida pelo backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: 'Já existe um usuário cadastrado com este e-mail.' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<CadastroUsuarioPage />)

    await preencherFormulario(user)
    await user.click(screen.getByRole('button', { name: 'Criar minha conta' }))

    expect(
      await screen.findByText('Já existe um usuário cadastrado com este e-mail.'),
    ).toBeInTheDocument()
  })
})

async function preencherFormulario(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Nome completo'), 'Ana Silva')
  await user.type(screen.getByLabelText('E-mail'), 'ANA@example.com')
  await user.type(screen.getByLabelText(/Telefone/), '(11) 98765-4321')
  await user.type(screen.getByLabelText('Senha'), 'senha-forte-123')
  await user.type(screen.getByLabelText('Confirmar senha'), 'senha-forte-123')
  await user.click(screen.getByRole('checkbox', { name: 'Aceitar termos de uso' }))
  await waitFor(() => expect(screen.getByLabelText('Nome completo')).toHaveValue('Ana Silva'))
}
