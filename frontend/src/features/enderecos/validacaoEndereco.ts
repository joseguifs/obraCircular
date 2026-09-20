import type { EnderecoForm, ErrosEndereco } from './types'

export const UFS =
  'AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split(
    ' ',
  )

export function validarEndereco(dados: EnderecoForm): ErrosEndereco {
  const erros: ErrosEndereco = {}
  if (!/^[\d\s-]+$/.test(dados.cep) || dados.cep.replace(/\D/g, '').length !== 8) {
    erros.cep = 'Informe um CEP com oito dígitos.'
  }
  if (!UFS.includes(dados.estado.trim().toUpperCase()))
    erros.estado = 'Selecione uma UF brasileira.'
  for (const [campo, label, limite] of [
    ['logradouro', 'o logradouro', 150],
    ['numero', 'o número', 20],
    ['bairro', 'o bairro', 100],
    ['cidade', 'a cidade', 100],
  ] as const) {
    if (!dados[campo].trim()) erros[campo] = `Informe ${label}.`
    else if (dados[campo].trim().length > limite)
      erros[campo] = `Use no máximo ${limite} caracteres.`
  }
  if (dados.complemento.trim().length > 100)
    erros.complemento = 'Use no máximo 100 caracteres.'
  return erros
}
