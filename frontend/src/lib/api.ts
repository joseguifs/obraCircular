import {
  obterSessaoArmazenada,
  removerSessaoArmazenada,
  salvarSessaoArmazenada,
} from '../features/autenticacao/sessaoStorage'

const apiUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1').replace(
  /\/$/,
  '',
)

interface ValidationIssue {
  loc?: Array<string | number>
  msg?: string
}

interface ApiErrorBody {
  detail?: string | ValidationIssue[]
}

interface TokenResponse {
  access_token: string
  refresh_token: string
  expires_in: number
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface ListResponse<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}

export function mensagemApiErro(erro: unknown, padrao: string): string {
  return erro instanceof ApiError ? erro.message : padrao
}

let renovacaoEmAndamento: Promise<string> | null = null

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const rotaAutenticacao = path === '/auth/login' || path === '/auth/refresh'
  let sessao = obterSessaoArmazenada()

  if (!rotaAutenticacao && sessao && sessao.expiraEm <= Date.now() + 30_000) {
    await renovarSessaoAtual()
    sessao = obterSessaoArmazenada()
  }

  let response = await executarRequisicao(path, init, sessao?.accessToken)
  if (response.status === 401 && !rotaAutenticacao && sessao?.refreshToken) {
    const accessToken = await renovarSessaoAtual()
    response = await executarRequisicao(path, init, accessToken)
  }

  if (!response.ok) {
    const body = await lerCorpoDeErro(response)
    throw new ApiError(mensagemDoErro(body, response.status), response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function executarRequisicao(
  path: string,
  init: RequestInit,
  accessToken?: string,
): Promise<Response> {
  let response: Response
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  try {
    response = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers,
    })
  } catch {
    throw new ApiError(
      'Não foi possível conectar ao servidor. Verifique se o backend está em execução.',
      0,
    )
  }
  return response
}

export async function renovarSessaoAtual(): Promise<string> {
  if (renovacaoEmAndamento) return renovacaoEmAndamento

  renovacaoEmAndamento = renovarTokens()
  try {
    return await renovacaoEmAndamento
  } finally {
    renovacaoEmAndamento = null
  }
}

async function renovarTokens(): Promise<string> {
  const sessao = obterSessaoArmazenada()
  if (!sessao) throw new ApiError('Sua sessão expirou. Entre novamente.', 401)

  let response: Response
  try {
    response = await fetch(`${apiUrl}/auth/refresh`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: sessao.refreshToken }),
    })
  } catch {
    throw new ApiError('Não foi possível renovar sua sessão.', 0)
  }

  if (!response.ok) {
    removerSessaoArmazenada()
    throw new ApiError('Sua sessão expirou. Entre novamente.', 401)
  }

  const tokens = (await response.json()) as TokenResponse
  salvarSessaoArmazenada({
    ...sessao,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiraEm: Date.now() + tokens.expires_in * 1000,
  })
  return tokens.access_token
}

async function lerCorpoDeErro(response: Response): Promise<ApiErrorBody | null> {
  try {
    return (await response.json()) as ApiErrorBody
  } catch {
    return null
  }
}

function mensagemDoErro(body: ApiErrorBody | null, status: number): string {
  if (typeof body?.detail === 'string') {
    return body.detail
  }

  if (Array.isArray(body?.detail)) {
    const mensagens = body.detail
      .map((issue) => issue.msg)
      .filter((mensagem): mensagem is string => Boolean(mensagem))
    if (mensagens.length > 0) {
      return mensagens.join(' ')
    }
  }

  if (status >= 500) {
    return 'O servidor encontrou um problema. Tente novamente em instantes.'
  }
  return 'Não foi possível concluir a solicitação. Revise os dados e tente novamente.'
}
