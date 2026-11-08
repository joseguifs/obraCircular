import { useEffect, useState } from 'react'

export function useHorarioAtual() {
  const [agora, setAgora] = useState(Date.now)
  useEffect(() => {
    const timer = window.setInterval(() => setAgora(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return agora
}
