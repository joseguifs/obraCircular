import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import { AnuncioPublicadoPage } from './AnuncioPublicadoPage'

afterEach(cleanup)

function renderPagina(state: unknown) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/anuncios/abc/publicado', state }]}>
      <Routes>
        <Route path="/anuncios/:anuncioId/publicado" element={<AnuncioPublicadoPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AnuncioPublicadoPage', () => {
  it('lista as fotos aceitas fora do padrão com a orientação do servidor', () => {
    renderPagina({
      titulo: 'Blocos de concreto',
      quantidadeImagens: 2,
      avisosImagens: [
        {
          imagem_id: '1',
          nome_original: 'pequena.jpg',
          largura: 500,
          altura: 300,
          codigo: 'AD_IMAGE_BELOW_MINIMUM',
          mensagem: 'A foto tem 500 × 300 px, abaixo do mínimo de 640 × 480 px.',
        },
      ],
    })

    expect(screen.getByRole('heading', { name: 'Uma foto está fora do padrão' })).toBeInTheDocument()
    expect(screen.getByText('pequena.jpg')).toBeInTheDocument()
    expect(screen.getByText(/abaixo do mínimo de 640 × 480 px/)).toBeInTheDocument()
  })

  it('não mostra o bloco de avisos quando as fotos seguem o padrão', () => {
    renderPagina({ titulo: 'Blocos de concreto', quantidadeImagens: 1, avisosImagens: [] })

    expect(screen.queryByText(/fora do padrão/)).not.toBeInTheDocument()
  })
})
