import type { Categoria, CategoriaAtualizacao, ErrosCategoria } from './types'

export const NOME_MAXIMO = 100
export const DESCRICAO_MAXIMA = 255

/** Remove espaços nas pontas e colapsa espaços internos, como o backend faz. */
export function normalizarNome(nome: string): string {
  return nome.split(/\s+/).filter(Boolean).join(' ')
}

export function validarCategoria(nome: string, descricao: string): ErrosCategoria {
  const erros: ErrosCategoria = {}
  const nomeNormalizado = normalizarNome(nome)

  if (!nomeNormalizado) erros.nome = 'Informe o nome da categoria.'
  else if (nomeNormalizado.length > NOME_MAXIMO) {
    erros.nome = `O nome deve ter no máximo ${NOME_MAXIMO} caracteres.`
  }

  if (descricao.trim().length > DESCRICAO_MAXIMA) {
    erros.descricao = `A descrição deve ter no máximo ${DESCRICAO_MAXIMA} caracteres.`
  }

  return erros
}

/** Monta o PATCH apenas com os campos que mudaram em relação à categoria original. */
export function camposAlterados(
  original: Categoria,
  nome: string,
  descricao: string,
  status: Categoria['status'],
): CategoriaAtualizacao {
  const alteracoes: CategoriaAtualizacao = {}
  const nomeNormalizado = normalizarNome(nome)
  const descricaoNormalizada = descricao.trim() || null

  if (nomeNormalizado !== original.nome) alteracoes.nome = nomeNormalizado
  if (descricaoNormalizada !== (original.descricao?.trim() || null)) {
    alteracoes.descricao = descricaoNormalizada
  }
  if (status !== original.status) alteracoes.status = status
  return alteracoes
}
