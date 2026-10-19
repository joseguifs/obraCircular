interface PaginacaoProps {
  offset: number
  porPagina: number
  total: number
  desabilitada: boolean
  aoMudar: (offset: number) => void
}

export function Paginacao({ offset, porPagina, total, desabilitada, aoMudar }: PaginacaoProps) {
  if (total === 0) return null
  const ultimo = Math.min(offset + porPagina, total)

  return (
    <nav className="cat-pagination" aria-label="Paginação">
      <span>
        {offset + 1}–{ultimo} de {total}
      </span>
      <div>
        <button
          type="button"
          className="secondary-button"
          disabled={offset === 0 || desabilitada}
          onClick={() => aoMudar(Math.max(0, offset - porPagina))}
        >
          Anterior
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={offset + porPagina >= total || desabilitada}
          onClick={() => aoMudar(offset + porPagina)}
        >
          Próxima
        </button>
      </div>
    </nav>
  )
}
