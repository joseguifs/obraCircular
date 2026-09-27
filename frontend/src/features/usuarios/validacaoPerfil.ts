import { emailEhValido, validarTelefone } from './validacaoCadastro'

export interface PerfilForm {
  nome: string
  email: string
  telefone: string
}

export function validarPerfil(
  dados: PerfilForm,
): Partial<Record<keyof PerfilForm, string>> {
  const erros: Partial<Record<keyof PerfilForm, string>> = {}
  if (!dados.nome.trim()) erros.nome = 'Informe seu nome.'
  else if (dados.nome.trim().length > 150)
    erros.nome = 'O nome deve ter no máximo 150 caracteres.'
  if (!emailEhValido(dados.email)) erros.email = 'Informe um e-mail válido.'
  const telefone = validarTelefone(dados.telefone)
  if (telefone) erros.telefone = telefone
  return erros
}
