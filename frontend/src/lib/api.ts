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

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(
      'Não foi possível conectar ao servidor. Verifique se o backend está em execução.',
      0,
    )
  }

  if (!response.ok) {
    const body = await lerCorpoDeErro(response)
    throw new ApiError(mensagemDoErro(body, response.status), response.status)
  }

  return (await response.json()) as T
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
