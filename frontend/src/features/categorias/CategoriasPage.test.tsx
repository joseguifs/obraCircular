import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../autenticacao/AuthProvider'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CategoriasPage } from './CategoriasPage'
import type { Categoria } from './types'

const tijolos: Categoria = {
  id: '0cdf91cd-132f-4e64-bfd9-aac74442f1fd',
  nome: 'Tijolos e blocos',
  descricao: 'Alvenaria em geral',
  status: 'ATIVA',
  criado_em: '2026-09-13T12:00:00Z',
  atualizado_em: '2026-09-14T12:00:00Z',
}

const tintas: Categoria = {
  id: '5b6d1d0a-0b61-4d1c-9c1c-0f4f4a7d9a11',
  nome: 'Tintas',
  descricao: null,
  status: 'INATIVA',
  criado_em: '2026-09-13T12:00:00Z',
  atualizado_em: '2026-09-14T12:00:00Z',
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function lista(items: Categoria[]) {
  return resposta({ items, total: items.length, offset: 0, limit: 10 })
}

function chamadas(fetchMock: ReturnType<typeof vi.fn>, metodo: string) {
  return fetchMock.mock.calls.filter(([, init]) => (init?.method ?? 'GET') === metodo)
}

function renderPagina() {
  return render(
    <BrowserRouter>
      <CategoriasPage />
    </BrowserRouter>,
  )
}

beforeEach(() => {
  window.history.replaceState({}, '', '/categorias')
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe('CategoriasPage', () => {
  it('lista as categorias sem exigir sessão', async () => {
    const fetchMock = vi.fn().mockResolvedValue(lista([tijolos, tintas]))
    vi.stubGlobal('fetch', fetchMock)

    renderPagina()

    expect(await screen.findByText('Tijolos e blocos')).toBeInTheDocument()
    expect(screen.getByText('Alvenaria em geral')).toBeInTheDocument()
    expect(screen.getByText('Sem descrição.')).toBeInTheDocument()
    expect(screen.getByText('Ativa')).toBeInTheDocument()
    expect(screen.getByText('Inativa')).toBeInTheDocument()
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).has('Authorization')).toBe(false)
  })

  it('filtra por status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(lista([tijolos]))
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    await screen.findByText('Tijolos e blocos')

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'INATIVA')

    await waitFor(() => {
      const ultimaUrl = String(fetchMock.mock.calls.at(-1)?.[0])
      expect(ultimaUrl).toContain('status=INATIVA')
      expect(ultimaUrl).toContain('offset=0')
    })
  })

  it('cadastra uma categoria e recarrega a lista', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(lista([]))
      .mockResolvedValueOnce(resposta(tijolos, 201))
      .mockResolvedValueOnce(lista([tijolos]))
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    await screen.findByText('Nenhuma categoria encontrada.')

    await userEvent.click(screen.getByRole('button', { name: '+ Nova categoria' }))
    await userEvent.type(screen.getByLabelText('Nome'), '  Tijolos   e blocos ')
    await userEvent.type(screen.getByLabelText('Descrição (opcional)'), 'Alvenaria em geral')
    await userEvent.click(screen.getByRole('button', { name: 'Cadastrar categoria' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Categoria cadastrada com sucesso.')
    expect(await screen.findByText('Tijolos e blocos')).toBeInTheDocument()
    const [post] = chamadas(fetchMock, 'POST')
    expect(String(post[0])).toMatch(/\/categories$/)
    expect(JSON.parse(post[1].body)).toEqual({
      nome: 'Tijolos e blocos',
      descricao: 'Alvenaria em geral',
    })
  })

  it('valida o nome antes de enviar', async () => {
    const fetchMock = vi.fn().mockResolvedValue(lista([]))
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    await screen.findByText('Nenhuma categoria encontrada.')

    await userEvent.click(screen.getByRole('button', { name: '+ Nova categoria' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cadastrar categoria' }))

    expect(screen.getByText('Informe o nome da categoria.')).toBeInTheDocument()
    expect(chamadas(fetchMock, 'POST')).toHaveLength(0)
  })

  it('mostra o erro quando o nome já existe', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(lista([]))
      .mockResolvedValueOnce(
        resposta({ detail: 'Já existe uma categoria cadastrada com este nome.' }, 409),
      )
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    await screen.findByText('Nenhuma categoria encontrada.')

    await userEvent.click(screen.getByRole('button', { name: '+ Nova categoria' }))
    await userEvent.type(screen.getByLabelText('Nome'), 'Tijolos e blocos')
    await userEvent.click(screen.getByRole('button', { name: 'Cadastrar categoria' }))

    expect(
      await screen.findByText('Já existe uma categoria cadastrada com este nome.'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Nome')).toHaveValue('Tijolos e blocos')
  })

  it('edita enviando somente os campos alterados', async () => {
    const atualizada = { ...tijolos, nome: 'Blocos', status: 'INATIVA' as const }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(lista([tijolos]))
      .mockResolvedValueOnce(resposta(atualizada))
      .mockResolvedValueOnce(lista([atualizada]))
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    await screen.findByText('Tijolos e blocos')

    await userEvent.click(screen.getByRole('button', { name: 'Editar Tijolos e blocos' }))
    expect(screen.getByLabelText('Nome')).toHaveValue('Tijolos e blocos')
    await userEvent.clear(screen.getByLabelText('Nome'))
    await userEvent.type(screen.getByLabelText('Nome'), 'Blocos')
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'INATIVA')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Categoria atualizada com sucesso.')
    const [patch] = chamadas(fetchMock, 'PATCH')
    expect(String(patch[0])).toContain(`/categories/${tijolos.id}`)
    expect(JSON.parse(patch[1].body)).toEqual({ nome: 'Blocos', status: 'INATIVA' })
    expect(await screen.findByText('Blocos')).toBeInTheDocument()
  })

  it('não envia a edição quando nada mudou', async () => {
    const fetchMock = vi.fn().mockResolvedValue(lista([tijolos]))
    vi.stubGlobal('fetch', fetchMock)
    renderPagina()
    await screen.findByText('Tijolos e blocos')

    await userEvent.click(screen.getByRole('button', { name: 'Editar Tijolos e blocos' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Altere ao menos um campo')
    expect(chamadas(fetchMock, 'PATCH')).toHaveLength(0)
  })

  it('exibe erro quando a listagem falha', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta({ detail: 'Falha interna.' }, 500)))

    renderPagina()

    expect(await screen.findByRole('alert')).toHaveTextContent('Falha interna.')
  })

  it('é acessível sem login pela rota /categorias', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(lista([tijolos])))

    render(
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Categorias' })).toBeInTheDocument()
    expect(await screen.findByText('Tijolos e blocos')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument()
  })
})
