import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { limparCachesMemoria } from '../lib/cacheMemoria'

// Cada teste simula a API do seu jeito; nenhum pode herdar dados guardados pelo anterior.
afterEach(() => {
  limparCachesMemoria()
})
