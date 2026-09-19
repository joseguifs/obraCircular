import { afterEach, expect, it, vi } from 'vitest'
import { apiRequest } from './api'

afterEach(() => {
  sessionStorage.clear()
  vi.unstubAllGlobals()
})

it('renova a sessão expirada antes de repetir uma chamada protegida', async () => {
  sessionStorage.setItem(
    'obra-circular:sessao',
    JSON.stringify({
      accessToken: 'access-antigo',
      refreshToken: 'refresh-antigo',
      expiraEm: Date.now() - 1,
      usuario: { id: 'd68c0c92-ab56-4f8e-862e-bbc91e31eb70', nome: 'Ana Silva' },
    }),
  )
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        access_token: 'access-novo',
        refresh_token: 'refresh-novo',
        expires_in: 900,
      }),
    })
    .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ id: 'recurso' }) })
  vi.stubGlobal('fetch', fetchMock)

  await apiRequest('/recurso-protegido')

  expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/api/v1/auth/refresh')
  expect(fetchMock.mock.calls[1][0]).toBe(
    'http://localhost:8000/api/v1/recurso-protegido',
  )
  expect((fetchMock.mock.calls[1][1].headers as Headers).get('Authorization')).toBe(
    'Bearer access-novo',
  )
  expect(sessionStorage.getItem('obra-circular:sessao')).toContain('refresh-novo')
})
