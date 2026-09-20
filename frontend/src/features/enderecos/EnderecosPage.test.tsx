import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { EnderecosPage } from './EnderecosPage'

const endereco = {
  id: 'endereco-1',
  cep: '01310100',
  logradouro: 'Avenida Paulista',
  numero: '1000',
  complemento: 'Sala 2',
  bairro: 'Bela Vista',
  cidade: 'São Paulo',
  estado: 'SP',
}
function resposta(body: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => body }
}
function lista(items = [endereco], total = items.length) {
  return resposta({ items, total, limit: 10, offset: 0 })
}
function renderPagina() {
  render(
    <BrowserRouter>
      <EnderecosPage />
    </BrowserRouter>,
  )
}
beforeEach(() => {
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'token',
      refreshToken: 'refresh',
      expiraEm: Date.now() + 900_000,
      usuario: { id: 'usuario-1' },
    }),
  )
})
afterEach(() => {
  cleanup()
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

it('edita o endereço existente com PATCH autenticado e permite remover complemento', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(lista())
    .mockResolvedValueOnce(resposta({ ...endereco, numero: '2000', complemento: null }))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: /Editar endereço:/ }))
  expect(screen.getByLabelText('Logradouro')).toHaveValue(endereco.logradouro)
  await user.clear(screen.getByLabelText('Número'))
  await user.type(screen.getByLabelText('Número'), '2000')
  await user.clear(screen.getByLabelText('Complemento (opcional)'))
  await user.click(screen.getByRole('button', { name: 'Salvar endereço' }))
  expect(await screen.findByText('Endereço atualizado com sucesso.')).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Avenida Paulista, 2000' }),
  ).toBeInTheDocument()
  const [url, init] = fetchMock.mock.calls[1]
  expect(url).toContain('/users/me/addresses/endereco-1')
  expect(init.method).toBe('PATCH')
  expect(init.headers.get('Authorization')).toBe('Bearer token')
  expect(JSON.parse(init.body)).toEqual({
    cep: '01310100',
    logradouro: 'Avenida Paulista',
    numero: '2000',
    complemento: null,
    bairro: 'Bela Vista',
    cidade: 'São Paulo',
    estado: 'SP',
  })
})

it('impede dados inválidos e cancela sem salvar', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce(lista())
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: /Editar endereço:/ }))
  await user.clear(screen.getByLabelText('CEP'))
  await user.type(screen.getByLabelText('CEP'), '123')
  await user.clear(screen.getByLabelText('Cidade'))
  await user.selectOptions(screen.getByLabelText('Estado'), '')
  await user.click(screen.getByRole('button', { name: 'Salvar endereço' }))
  expect(screen.getByText('Informe um CEP com oito dígitos.')).toBeInTheDocument()
  expect(screen.getByText('Informe a cidade.')).toBeInTheDocument()
  expect(screen.getByText('Selecione uma UF brasileira.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Cancelar' }))
  expect(screen.getByText('CEP 01310-100')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

it('exibe falha ao salvar sem perder a edição', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(lista())
      .mockResolvedValueOnce(resposta({ detail: 'Endereço não encontrado.' }, 404)),
  )
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: /Editar endereço:/ }))
  await user.click(screen.getByRole('button', { name: 'Salvar endereço' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Endereço não encontrado.')
  expect(screen.getByLabelText('Logradouro')).toHaveValue(endereco.logradouro)
})

it('distingue lista vazia de erro de carregamento e permite repetir', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(resposta({ detail: 'Falha temporária.' }, 500))
      .mockResolvedValueOnce(lista([])),
  )
  const user = userEvent.setup()
  renderPagina()
  expect(await screen.findByRole('alert')).toHaveTextContent('Falha temporária.')
  expect(screen.queryByText('Nenhum endereço cadastrado')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))
  expect(await screen.findByText('Nenhum endereço cadastrado')).toBeInTheDocument()
})

it('acessa os endereços além da primeira página', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(lista([endereco], 11))
    .mockResolvedValueOnce(lista([{ ...endereco, id: 'endereco-11', numero: '11' }], 11))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderPagina()
  await user.click(await screen.findByRole('button', { name: 'Próxima' }))
  expect(
    await screen.findByRole('heading', { name: 'Avenida Paulista, 11' }),
  ).toBeInTheDocument()
  expect(fetchMock.mock.calls[1][0]).toContain('offset=10')
  expect(screen.getByRole('button', { name: 'Próxima' })).toBeDisabled()
})
