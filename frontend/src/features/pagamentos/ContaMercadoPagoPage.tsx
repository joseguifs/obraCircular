import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import {
  conectarContaMercadoPago,
  consultarContaMercadoPago,
} from './pagamentoApi'
import type { ContaMercadoPago } from './types'

export function ContaMercadoPagoPage() {
  const [parametros] = useSearchParams()
  const [conta, setConta] = useState<ContaMercadoPago | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [conectando, setConectando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    consultarContaMercadoPago()
      .then(setConta)
      .catch((falha) => setErro(mensagemApiErro(falha, 'Não foi possível consultar a conta.')))
      .finally(() => setCarregando(false))
  }, [])

  async function conectar() {
    setConectando(true)
    setErro('')
    try {
      await conectarContaMercadoPago()
    } catch (falha) {
      setErro(mensagemApiErro(falha, 'Não foi possível iniciar a conexão.'))
      setConectando(false)
    }
  }

  return (
    <main className="payment-page">
      <Link to="/perfil" className="back-button">
        ← Voltar ao perfil
      </Link>
      <section className="payment-card">
        <span className="step-label">Recebimentos</span>
        <h1>Conta Mercado Pago</h1>
        <p>
          Conecte sua conta para que seus anúncios possam receber pagamentos. O Mercado Pago
          solicitará sua autorização em uma página segura.
        </p>
        {parametros.get('mercado_pago') === 'conectado' && (
          <p className="account-success" role="status">
            Conta conectada com sucesso.
          </p>
        )}
        {erro && <p className="form-alert" role="alert">{erro}</p>}
        {carregando ? (
          <p>Consultando conexão...</p>
        ) : (
          <>
            <p className="payment-status">
              Status: <strong>{conta?.status ?? 'PENDENTE'}</strong>
            </p>
            <button
              type="button"
              className="submit-button"
              disabled={conectando || conta?.status === 'ATIVA'}
              onClick={conectar}
            >
              {conta?.status === 'ATIVA'
                ? 'Conta conectada'
                : conectando
                  ? 'Redirecionando...'
                  : 'Conectar Mercado Pago'}
            </button>
          </>
        )}
      </section>
    </main>
  )
}
