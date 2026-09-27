import { describe, expect, it } from 'vitest'
import type { Categoria } from './types'
import { camposAlterados, normalizarNome, validarCategoria } from './validacaoCategoria'

const original: Categoria = {
  id: '1',
  nome: 'Tijolos e blocos',
  descricao: 'Alvenaria',
  status: 'ATIVA',
  criado_em: '2026-09-13T00:00:00Z',
  atualizado_em: '2026-09-13T00:00:00Z',
}

describe('validarCategoria', () => {
  it('exige o nome', () => {
    expect(validarCategoria('   ', '').nome).toBe('Informe o nome da categoria.')
  })

  it('limita nome e descrição', () => {
    const erros = validarCategoria('a'.repeat(101), 'b'.repeat(256))
    expect(erros.nome).toContain('100')
    expect(erros.descricao).toContain('255')
  })

  it('aceita descrição vazia', () => {
    expect(validarCategoria('Ferramentas', '')).toEqual({})
  })
})

describe('normalizarNome', () => {
  it('colapsa espaços repetidos', () => {
    expect(normalizarNome('  Tintas   e   vernizes ')).toBe('Tintas e vernizes')
  })
})

describe('camposAlterados', () => {
  it('não retorna nada quando nada mudou', () => {
    expect(camposAlterados(original, ' Tijolos  e blocos ', 'Alvenaria ', 'ATIVA')).toEqual({})
  })

  it('retorna somente os campos alterados', () => {
    expect(camposAlterados(original, 'Blocos', 'Alvenaria', 'INATIVA')).toEqual({
      nome: 'Blocos',
      status: 'INATIVA',
    })
  })

  it('envia null ao limpar a descrição', () => {
    expect(camposAlterados(original, original.nome, '  ', 'ATIVA')).toEqual({ descricao: null })
  })
})
