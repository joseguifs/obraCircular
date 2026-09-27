export type EnderecoForm = Record<
  'cep' | 'logradouro' | 'numero' | 'complemento' | 'bairro' | 'cidade' | 'estado',
  string
>
export type Endereco = Omit<EnderecoForm, 'complemento'> & {
  id: string
  complemento: string | null
}
export type EnderecoPayload = Omit<EnderecoForm, 'complemento'> & {
  complemento?: string
}
export type EnderecoUpdatePayload = Omit<EnderecoForm, 'complemento'> & {
  complemento: string | null
}
export type ErrosEndereco = Partial<Record<keyof EnderecoForm, string>>
