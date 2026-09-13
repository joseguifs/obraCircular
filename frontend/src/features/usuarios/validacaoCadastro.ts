import type { CadastroUsuarioForm, ErrosCadastro } from './types'

const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function validarCadastro(dados: CadastroUsuarioForm): ErrosCadastro {
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

  return erros
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
