const UNIDADES: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 31_536_000],
  ['month', 2_592_000],
  ['week', 604_800],
  ['day', 86_400],
  ['hour', 3_600],
  ['minute', 60],
]

const formatadorRelativo = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' })

export function formatarTempoRelativo(dataIso: string): string {
  const segundosDecorridos = Math.round((Date.now() - new Date(dataIso).getTime()) / 1000)
  if (segundosDecorridos < 60) return 'agora há pouco'

  for (const [unidade, segundosDaUnidade] of UNIDADES) {
    const valor = Math.floor(segundosDecorridos / segundosDaUnidade)
    if (valor >= 1) return formatadorRelativo.format(-valor, unidade)
  }
  return 'agora há pouco'
}

const formatadorMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export function formatarMoeda(valor: string | number): string {
  return formatadorMoeda.format(Number(valor))
}

const formatadorMesAno = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' })

export function formatarMesAno(dataIso: string): string {
  return formatadorMesAno.format(new Date(dataIso))
}
