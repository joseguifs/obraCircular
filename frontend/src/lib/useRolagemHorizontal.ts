import { useEffect, useRef, useState } from 'react'

interface Bordas {
  /** Há conteúdo escondido à esquerda. */
  antes: boolean
  /** Há conteúdo escondido à direita. */
  depois: boolean
}

/**
 * Acompanha um contêiner com rolagem horizontal e informa se ainda há itens fora da
 * tela de cada lado. Usado para esmaecer a borda e indicar que dá para rolar.
 */
export function useRolagemHorizontal<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [bordas, setBordas] = useState<Bordas>({ antes: false, depois: false })

  useEffect(() => {
    const elemento = ref.current
    if (!elemento) return

    function medir() {
      if (!elemento) return
      const antes = elemento.scrollLeft > 1
      const depois = elemento.scrollLeft + elemento.clientWidth < elemento.scrollWidth - 1
      setBordas((atual) =>
        atual.antes === antes && atual.depois === depois ? atual : { antes, depois },
      )
    }

    const quadro = window.requestAnimationFrame(medir)
    elemento.addEventListener('scroll', medir, { passive: true })
    window.addEventListener('resize', medir)

    // Itens carregados depois (ex.: categorias vindas da API) mudam a largura do conteúdo.
    const mutacoes =
      typeof MutationObserver === 'undefined' ? null : new MutationObserver(medir)
    mutacoes?.observe(elemento, { childList: true, subtree: true, characterData: true })

    return () => {
      window.cancelAnimationFrame(quadro)
      elemento.removeEventListener('scroll', medir)
      window.removeEventListener('resize', medir)
      mutacoes?.disconnect()
    }
  }, [])

  return {
    ref,
    atributos: {
      'data-mais-antes': bordas.antes || undefined,
      'data-mais-depois': bordas.depois || undefined,
    },
  }
}
