import type { Endereco } from '../anuncios/types'

export type { Endereco }
export type EnderecoForm = Record<
  'cep' | 'logradouro' | 'numero' | 'complemento' | 'bairro' | 'cidade' | 'estado',
  string
>
export type EnderecoUpdatePayload = Omit<EnderecoForm, 'complemento'> & {
  complemento: string | null
}
export type ErrosEndereco = Partial<Record<keyof EnderecoForm, string>>
