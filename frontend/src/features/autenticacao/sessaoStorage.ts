import type { Sessao } from './types'

const CHAVE_SESSAO = 'obra-circular:sessao'
const EVENTO_SESSAO = 'obra-circular:sessao-atualizada'

export function obterSessaoArmazenada(): Sessao | null {
  try {
    const valor = sessionStorage.getItem(CHAVE_SESSAO)
    if (!valor) return null

    const sessao = JSON.parse(valor) as Partial<Sessao>
    if (
      !sessao.accessToken ||
      !sessao.refreshToken ||
      !sessao.expiraEm ||
      !sessao.usuario?.id
    ) {
      removerSessaoArmazenada()
      return null
    }
    return sessao as Sessao
  } catch {
    return null
  }
}

export function salvarSessaoArmazenada(sessao: Sessao) {
  try {
    sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao))
  } catch {
    // A sessão continua disponível em memória durante esta navegação.
  }
  window.dispatchEvent(new CustomEvent<Sessao | null>(EVENTO_SESSAO, { detail: sessao }))
}

export function removerSessaoArmazenada() {
  try {
    sessionStorage.removeItem(CHAVE_SESSAO)
  } catch {
    // O encerramento local continua válido mesmo sem acesso ao armazenamento.
  }
  window.dispatchEvent(new CustomEvent<Sessao | null>(EVENTO_SESSAO, { detail: null }))
}

export function observarSessao(callback: (sessao: Sessao | null) => void) {
  function atualizar(evento: Event) {
    callback((evento as CustomEvent<Sessao | null>).detail)
  }
  window.addEventListener(EVENTO_SESSAO, atualizar)
  return () => window.removeEventListener(EVENTO_SESSAO, atualizar)
}
