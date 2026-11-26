import { describe, expect, it } from 'vitest'
import { abaixoDoMinimo, avisoDaFoto } from './fotosAnuncio'

describe('padrão de fotos do anúncio', () => {
  it('aplica o mínimo de 640 × 480 px em qualquer orientação', () => {
    expect(abaixoDoMinimo({ largura: 640, altura: 480 })).toBe(false)
    expect(abaixoDoMinimo({ largura: 480, altura: 640 })).toBe(false)
    expect(abaixoDoMinimo({ largura: 639, altura: 480 })).toBe(true)
    expect(abaixoDoMinimo({ largura: 1920, altura: 400 })).toBe(true)
  })

  it('só avisa quando a foto foge do formato ou da resolução recomendada', () => {
    expect(avisoDaFoto({ largura: 1600, altura: 1200 })).toBeUndefined()
    expect(avisoDaFoto({ largura: 1920, altura: 1080 })).toBeUndefined()
    expect(avisoDaFoto({ largura: 900, altura: 1600 })).toMatch(/vertical/)
    expect(avisoDaFoto({ largura: 2400, altura: 1000 })).toMatch(/muito larga/)
    expect(avisoDaFoto({ largura: 800, altura: 600 })).toMatch(/1200 × 900/)
    expect(avisoDaFoto({ largura: 500, altura: 300 })).toMatch(/Abaixo do mínimo de 640 × 480/)
  })
})
