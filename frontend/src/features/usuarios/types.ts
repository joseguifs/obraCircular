export interface CadastroUsuarioForm {
  nome: string
  email: string
  telefone: string
  senha: string
  confirmarSenha: string
}

export interface UsuarioCreatePayload {
  nome: string
  email: string
  senha: string
  telefone?: string
}

export interface Usuario {
  id: string
  nome: string
  email: string
  telefone: string | null
  status: 'ATIVO' | 'INATIVO' | 'BLOQUEADO'
  criado_em: string
  atualizado_em: string
}

export type CampoCadastro = keyof CadastroUsuarioForm
export type ErrosCadastro = Partial<Record<CampoCadastro, string>>
