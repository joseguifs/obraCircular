import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Paginacao } from '../admin/Paginacao'
import { mensagemApiErro, resolverUrlDaApi } from '../../lib/api'
import { formatarTempoRelativo } from '../../lib/formatarTempo'
import { responderPergunta } from '../anuncios/anuncioApi'
import type { AnuncioPergunta } from '../anuncios/types'
import { listarMinhasPerguntas } from './perguntaApi'
import type { PerguntaUsuario, TipoPerguntaUsuario } from './types'

const POR_PAGINA = 10
const RESPOSTA_MAX = 1000

/** O filtro fica na URL (?tipo=recebidas) para sobreviver ao voltar do anúncio. */
const FILTROS: Array<{ valor: TipoPerguntaUsuario; parametro: string; rotulo: string }> = [
  { valor: 'FEITAS', parametro: 'feitas', rotulo: 'Perguntas feitas por mim' },
  { valor: 'RECEBIDAS', parametro: 'recebidas', rotulo: 'Perguntas em meus anúncios' },
]

interface Resultado {
  chave: string
  tipo: TipoPerguntaUsuario
  itens: PerguntaUsuario[]
  total: number
}

interface Falha {
  chave: string
  mensagem: string
}

export function MinhasPerguntasPage() {
  const [parametros, setParametros] = useSearchParams()
  const tipo: TipoPerguntaUsuario =
    parametros.get('tipo') === 'recebidas' ? 'RECEBIDAS' : 'FEITAS'

  const [pagina, setPagina] = useState({ tipo, offset: 0 })
  const offset = pagina.tipo === tipo ? pagina.offset : 0
  const [tentativa, setTentativa] = useState(0)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [falha, setFalha] = useState<Falha | null>(null)

  // Cada busca tem uma chave; enquanto a resposta dela não chega, a tela está carregando.
  const chave = `${tipo}:${offset}:${tentativa}`
  const erro = falha?.chave === chave ? falha.mensagem : ''
  const carregando = resultado?.chave !== chave && !erro

  // Busca apenas o recorte selecionado; o outro só é carregado quando o filtro muda.
  useEffect(() => {
    let ativo = true
    listarMinhasPerguntas(tipo, { offset, limit: POR_PAGINA })
      .then((resposta) => {
        if (!ativo) return
        setResultado({ chave, tipo, itens: resposta.items, total: resposta.total })
        setFalha(null)
      })
      .catch((erroRecebido) => {
        if (!ativo) return
        setFalha({
          chave,
          mensagem: mensagemApiErro(erroRecebido, 'Não foi possível carregar as perguntas.'),
        })
      })
    return () => {
      ativo = false
    }
  }, [chave, tipo, offset])

  function escolherTipo(filtro: (typeof FILTROS)[number]) {
    if (filtro.valor === tipo) return
    setPagina({ tipo: filtro.valor, offset: 0 })
    const proximos = new URLSearchParams(parametros)
    proximos.set('tipo', filtro.parametro)
    setParametros(proximos, { replace: true })
  }

  function atualizarPergunta(atualizada: AnuncioPergunta) {
    setResultado((atual) =>
      atual && {
        ...atual,
        itens: atual.itens.map((item) =>
          item.id === atualizada.id ? { ...item, ...atualizada } : item,
        ),
      },
    )
  }

  // Não mostra a lista do filtro anterior enquanto o novo carrega.
  const itens = resultado?.tipo === tipo ? resultado.itens : []
  const total = resultado?.tipo === tipo ? resultado.total : 0
  const recebidas = tipo === 'RECEBIDAS'

  return (
    <main className="minhas-perguntas-main">
      <div className="meus-anuncios-cabecalho">
        <div>
          <h1>Perguntas</h1>
          <p>
            {carregando && itens.length === 0
              ? 'Carregando perguntas…'
              : recebidas
                ? `${total} ${total === 1 ? 'pergunta recebida' : 'perguntas recebidas'} nos seus anúncios.`
                : `${total} ${total === 1 ? 'pergunta feita' : 'perguntas feitas'} por você.`}
          </p>
        </div>
      </div>

      <div className="meus-anuncios-filtros" role="group" aria-label="Filtrar perguntas">
        {FILTROS.map((filtro) => (
          <button
            key={filtro.valor}
            type="button"
            aria-pressed={tipo === filtro.valor}
            className={tipo === filtro.valor ? 'home-filtro home-filtro--ativo' : 'home-filtro'}
            onClick={() => escolherTipo(filtro)}
          >
            {filtro.rotulo}
          </button>
        ))}
      </div>

      {erro && (
        <div className="minhas-perguntas-erro">
          <div className="home-alert" role="alert">
            {erro}
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setTentativa((atual) => atual + 1)}
          >
            Tentar novamente
          </button>
        </div>
      )}

      {!erro && !carregando && itens.length === 0 && (
        <div className="home-vazio">
          <p className="home-vazio-titulo">
            {recebidas ? 'Nenhuma pergunta nos seus anúncios' : 'Você ainda não fez perguntas'}
          </p>
          <p>
            {recebidas
              ? 'Quando alguém perguntar em um anúncio seu, a pergunta aparece aqui para você responder.'
              : 'Pergunte ao vendedor na página de um anúncio e acompanhe a resposta por aqui.'}
          </p>
        </div>
      )}

      {itens.length > 0 && (
        <ul className="minhas-perguntas-lista" aria-busy={carregando}>
          {itens.map((item) => (
            <ItemPergunta
              key={item.id}
              pergunta={item}
              podeResponder={recebidas}
              aoResponder={atualizarPergunta}
            />
          ))}
        </ul>
      )}

      <Paginacao
        offset={offset}
        porPagina={POR_PAGINA}
        total={total}
        desabilitada={carregando}
        aoMudar={(novoOffset) => setPagina({ tipo, offset: novoOffset })}
      />
    </main>
  )
}

interface ItemPerguntaProps {
  pergunta: PerguntaUsuario
  podeResponder: boolean
  aoResponder: (pergunta: AnuncioPergunta) => void
}

function ItemPergunta({ pergunta, podeResponder, aoResponder }: ItemPerguntaProps) {
  const { anuncio } = pergunta
  const [resposta, setResposta] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')
  const idCampo = `minha-resposta-${pergunta.id}`
  const pendente = pergunta.resposta === null

  async function enviarResposta(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const texto = resposta.trim()
    if (!texto) {
      setErro('Escreva uma resposta antes de enviar.')
      return
    }
    setEnviando(true)
    setErro('')
    try {
      aoResponder(await responderPergunta(anuncio.id, pergunta.id, texto))
    } catch (erroRecebido) {
      setErro(mensagemApiErro(erroRecebido, 'Não foi possível enviar a resposta.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <li className="minhas-perguntas-item">
      <Link
        to={`/anuncios/${anuncio.id}`}
        className="minhas-perguntas-anuncio"
        aria-label={`Ver anúncio ${anuncio.titulo}`}
      >
        <span className="minhas-perguntas-foto">
          {anuncio.imagem_capa_url ? (
            <img src={resolverUrlDaApi(anuncio.imagem_capa_url)} alt="" />
          ) : (
            <span>Sem foto</span>
          )}
        </span>
        <span className="minhas-perguntas-anuncio-titulo">{anuncio.titulo}</span>
        {anuncio.status === 'ESGOTADO' && (
          <span className="meus-anuncios-status meus-anuncios-status--esgotado">Esgotado</span>
        )}
        {podeResponder && pendente && (
          <span className="minhas-perguntas-selo">Aguardando sua resposta</span>
        )}
      </Link>

      <div className="minhas-perguntas-conteudo">
        <p className="ad-pergunta-texto">{pergunta.pergunta}</p>
        <p className="ad-pergunta-data">
          {podeResponder ? 'Um interessado perguntou' : 'Você perguntou'}{' '}
          {formatarTempoRelativo(pergunta.criado_em)}
        </p>

        {!pendente ? (
          <div className="ad-pergunta-resposta">
            <p>{pergunta.resposta}</p>
            {pergunta.respondido_em && (
              <p className="ad-pergunta-data">
                {podeResponder ? 'Você respondeu' : 'Vendedor respondeu'}{' '}
                {formatarTempoRelativo(pergunta.respondido_em)}
              </p>
            )}
          </div>
        ) : podeResponder ? (
          <form className="ad-pergunta-responder" onSubmit={enviarResposta} noValidate>
            <label htmlFor={idCampo} className="ad-perguntas-sr">
              Responder: {pergunta.pergunta}
            </label>
            <textarea
              id={idCampo}
              value={resposta}
              rows={2}
              maxLength={RESPOSTA_MAX}
              placeholder="Escreva sua resposta…"
              onChange={(evento) => {
                setResposta(evento.target.value)
                if (erro) setErro('')
              }}
              aria-invalid={Boolean(erro)}
            />
            <div className="ad-pergunta-responder-acoes">
              <span className="ad-perguntas-contador">
                {resposta.length}/{RESPOSTA_MAX}
              </span>
              <button type="submit" className="secondary-button" disabled={enviando}>
                {enviando ? 'Enviando…' : 'Responder'}
              </button>
            </div>
            {erro && (
              <p className="ad-perguntas-erro" role="alert">
                {erro}
              </p>
            )}
          </form>
        ) : (
          <p className="ad-pergunta-pendente">Aguardando resposta do vendedor</p>
        )}
      </div>
    </li>
  )
}
