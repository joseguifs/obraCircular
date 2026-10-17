import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRouter } from '../../app/router'
import { AuthProvider } from '../autenticacao/AuthProvider'
import type { AnuncioAdmin, UsuarioAdmin } from './types'

const adminId = 'b1f7f0c6-7a43-4c3e-9b1f-1f0a5b6f0e01'

const usuarioComum: UsuarioAdmin = {
  id: 'c2a8e1d7-8b54-4d4f-8c2a-2a1b6c7a1f02',
  nome: 'Carlos Vendedor',
  email: 'carlos@example.com',
  telefone: null,
  status: 'ATIVO',
  administrador: false,
  criado_em: '2026-10-01T12:00:00Z',
  atualizado_em: '2026-10-01T12:00:00Z',
  deletado_em: null,
}

const anuncio: AnuncioAdmin = {
  id: 'd3b9f2e8-9c65-4e5a-9d3b-3b2c7d8b2a03',
  titulo: 'Tijolos baianos',
  preco: '120.00',
  quantidade: 10,
  status: 'ATIVO',
  categoria_id: 'e4cafaf9-ad76-4f6b-ae4c-4c3d8e9c3b04',
  categoria_nome: 'Alvenaria',
  vendedor_id: usuarioComum.id,
  vendedor_nome: usuarioComum.nome,
  vendedor_email: usuarioComum.email,
  imagem_capa_url: null,
  postado_em: '2026-10-10T12:00:00Z',
  atualizado_em: '2026-10-10T12:00:00Z',
  encerrado_em: null,
  deletado_em: null,
}

function resposta(body: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function lista<T>(items: T[]) {
  return resposta({ items, total: items.length, offset: 0, limit: 10 })
}

function salvarSessao(usuario: Record<string, unknown>) {
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      expiraEm: Date.now() + 900_000,
      usuario,
    }),
  )
}

function renderEm(caminho: string) {
  window.history.replaceState({}, '', caminho)
  return render(
    <BrowserRouter>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>,
  )
}

beforeEach(() => {
  salvarSessao({ id: adminId, nome: 'Ana Admin', administrador: true })
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

describe('Administração', () => {
  it('nega o acesso a quem não é administrador', async () => {
    salvarSessao({ id: usuarioComum.id, nome: 'Carlos Vendedor' })
    const fetchMock = vi.fn().mockResolvedValue(resposta({ ...usuarioComum }))
    vi.stubGlobal('fetch', fetchMock)

    renderEm('/admin')

    expect(await screen.findByRole('heading', { name: 'Acesso restrito' })).toBeInTheDocument()
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/auth\/me$/)
    expect(screen.queryByRole('link', { name: 'Administração' })).not.toBeInTheDocument()
  })

  it('libera o acesso quando /auth/me confirma o perfil', async () => {
    salvarSessao({ id: adminId, nome: 'Ana Admin' })
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(
        url.endsWith('/auth/me')
          ? resposta({ ...usuarioComum, id: adminId, nome: 'Ana Admin', administrador: true })
          : resposta({
              usuarios: { total: 2, por_status: { ATIVO: 2 } },
              anuncios: { total: 1, por_status: { ATIVO: 1 } },
              categorias: { total: 3, por_status: { ATIVA: 2, INATIVA: 1 } },
              administradores: 1,
            }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    renderEm('/admin')

    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeInTheDocument()
    const categorias = await screen.findByRole('region', { name: 'Categorias' })
    expect(within(categorias).getByText('3')).toBeInTheDocument()
    expect(screen.getByText('1 administrador(es)')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Administração' })).toBeInTheDocument()
  })

  it('lista anúncios e exclui após confirmação', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(lista([anuncio]))
      .mockResolvedValueOnce(resposta(null, 204))
      .mockResolvedValueOnce(lista([]))
    vi.stubGlobal('fetch', fetchMock)
    const usuario = userEvent.setup()

    renderEm('/admin/anuncios')

    expect(await screen.findByText('Tijolos baianos')).toBeInTheDocument()
    expect(screen.getByText(/Carlos Vendedor \(carlos@example.com\)/)).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Excluir Tijolos baianos' }))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await usuario.click(screen.getByRole('button', { name: 'Confirmar exclusão' }))

    expect(await screen.findByRole('status')).toHaveTextContent('Anúncio excluído.')
    const [url, init] = fetchMock.mock.calls[1]
    expect(String(url)).toMatch(`/admin/ads/${anuncio.id}`)
    expect(init.method).toBe('DELETE')
    expect(await screen.findByText('Nenhum anúncio encontrado.')).toBeInTheDocument()
  })

  it('envia a busca de anúncios como filtro', async () => {
    const fetchMock = vi.fn().mockResolvedValue(lista([anuncio]))
    vi.stubGlobal('fetch', fetchMock)
    const usuario = userEvent.setup()

    renderEm('/admin/anuncios')
    await screen.findByText('Tijolos baianos')

    await usuario.type(screen.getByPlaceholderText('Título, vendedor ou e-mail'), 'tijolo')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(String(fetchMock.mock.calls[1][0])).toContain('search=tijolo')
  })

  it('bloqueia usuário e protege a própria conta', async () => {
    const proprio: UsuarioAdmin = {
      ...usuarioComum,
      id: adminId,
      nome: 'Ana Admin',
      email: 'ana@example.com',
      administrador: true,
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(lista([proprio, usuarioComum]))
      .mockResolvedValueOnce(resposta({ ...usuarioComum, status: 'BLOQUEADO' }))
      .mockResolvedValueOnce(lista([proprio, { ...usuarioComum, status: 'BLOQUEADO' }]))
    vi.stubGlobal('fetch', fetchMock)
    const usuario = userEvent.setup()

    renderEm('/admin/usuarios')

    expect(await screen.findByLabelText('Status de Ana Admin')).toBeDisabled()
    await usuario.selectOptions(screen.getByLabelText('Status de Carlos Vendedor'), 'BLOQUEADO')

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Status de Carlos Vendedor alterado para bloqueado.',
    )
    const [url, init] = fetchMock.mock.calls[1]
    expect(String(url)).toMatch(`/admin/users/${usuarioComum.id}/status`)
    expect(JSON.parse(init.body)).toEqual({ status: 'BLOQUEADO' })
  })
})
