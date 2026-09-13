import type { CadastroUsuarioForm, ErrosCadastro } from './types'

const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validarCadastro(dados: CadastroUsuarioForm, termosAceitos: boolean): ErrosCadastro {
  const erros: ErrosCadastro = {}
  const nome = dados.nome.trim()
  const email = dados.email.trim()

  if (!nome) {
    erros.nome = 'Informe seu nome.'
  } else if (nome.length > 150) {
    erros.nome = 'O nome deve ter no máximo 150 caracteres.'
  }

  if (!email) {
    erros.email = 'Informe seu e-mail.'
  } else if (!EMAIL_VALIDO.test(email)) {
    erros.email = 'Informe um e-mail válido.'
  }

  const erroTelefone = validarTelefone(dados.telefone)
  if (erroTelefone) {
    erros.telefone = erroTelefone
  }

  if (dados.senha.length < 8) {
    erros.senha = 'A senha deve ter pelo menos 8 caracteres.'
  } else if (dados.senha.length > 72) {
    erros.senha = 'A senha deve ter no máximo 72 caracteres.'
  }

  if (!dados.confirmarSenha) {
    erros.confirmarSenha = 'Confirme sua senha.'
  } else if (dados.confirmarSenha !== dados.senha) {
    erros.confirmarSenha = 'As senhas não coincidem.'
  }

  if (!termosAceitos) {
    erros.termos = 'É preciso aceitar os Termos de Uso.'
  }

  return erros
}

/** Feedback visual imediato (ex.: ícone de "e-mail válido"), independente do
 * envio do formulário — não deve ser usado para decidir se pode submeter. */
export function emailEhValido(valor: string): boolean {
  return EMAIL_VALIDO.test(valor.trim())
}

export type ForcaSenha = 0 | 1 | 2 | 3

/** 0 = vazia, 1 = fraca, 2 = média, 3 = forte — soma um ponto por critério
 * atendido (tamanho mínimo, maiúsculas e minúsculas, dígito ou símbolo). */
export function forcaDaSenha(senha: string): ForcaSenha {
  if (!senha) return 0
  let pontos = 0
  if (senha.length >= 8) pontos++
  if (/[A-Z]/.test(senha) && /[a-z]/.test(senha)) pontos++
  if (/[0-9\W]/.test(senha)) pontos++
  return Math.max(1, pontos) as ForcaSenha
}

function validarTelefone(valor: string): string | undefined {
  if (!valor.trim()) {
    return undefined
  }

  let digitos = valor.replace(/\D/g, '')
  if (digitos.startsWith('55') && (digitos.length === 12 || digitos.length === 13)) {
    digitos = digitos.slice(2)
  }

  if (digitos.length !== 10 && digitos.length !== 11) {
    return 'Informe DDD e número, com 10 ou 11 dígitos.'
  }

  const ddd = digitos.slice(0, 2)
  const numero = digitos.slice(2)
  if (ddd.includes('0')) {
    return 'Informe um DDD válido.'
  }
  if (numero.length === 9 && !numero.startsWith('9')) {
    return 'Celulares com 9 dígitos devem começar com 9.'
  }
  if (numero.length === 8 && ['0', '1'].includes(numero[0])) {
    return 'Informe um número de telefone válido.'
  }

  return undefined
}
