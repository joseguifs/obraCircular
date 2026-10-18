import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { formatarTempoRelativo } from '../../lib/formatarTempo'
import { useAuth } from '../autenticacao/useAuth'
import { criarPergunta, listarPerguntas, responderPergunta } from './anuncioApi'
import type { Anuncio, AnuncioPergunta } from './types'

const POR_PAGINA = 10
const PERGUNTA_MIN = 3
const PERGUNTA_MAX = 500
const RESPOSTA_MAX = 1000

interface PerguntasAnuncioProps {
  anuncio: Anuncio
}

export function PerguntasAnuncio({ anuncio }: PerguntasAnuncioProps) {
  const { sessao } = useAuth()
  const usuarioId = sessao?.usuario.id
  const ehVendedor = usuarioId === anuncio.vendedor_id
  const podePerguntar = !ehVendedor && anuncio.status !== 'ENCERRADO'

  const [perguntas, setPerguntas] = useState<AnuncioPergunta[]>([])
  const [total, setTotal] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [carregandoMais, setCarregandoMais] = useState(false)
  const [erroLista, setErroLista] = useState('')
  const [tentativa, setTentativa] = useState(0)

  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erroEnvio, setErroEnvio] = useState('')
  const [enviada, setEnviada] = useState(false)

  useEffect(() => {
    let ativo = true
    listarPerguntas(anuncio.id, { offset: 0, limit: POR_PAGINA })
      .then((resposta) => {
        if (!ativo) return
        setPerguntas(resposta.items)
        setTotal(resposta.total)
      })
      .catch((erro) => {
        if (ativo) setErroLista(mensagemApiErro(erro, 'Não foi possível carregar as perguntas.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [anuncio.id, tentativa])

  async function carregarMais() {
    setCarregandoMais(true)
    try {
      const resposta = await listarPerguntas(anuncio.id, {
        offset: perguntas.length,
        limit: POR_PAGINA,
      })
      setPerguntas((atuais) => {
        const ids = new Set(atuais.map((item) => item.id))
        return [...atuais, ...resposta.items.filter((item) => !ids.has(item.id))]
      })
      setTotal(resposta.total)
    } catch (erro) {
      setErroLista(mensagemApiErro(erro, 'Não foi possível carregar mais perguntas.'))
    } finally {
      setCarregandoMais(false)
    }
  }

  async function enviarPergunta(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    const pergunta = texto.trim()
    if (pergunta.length < PERGUNTA_MIN) {
      setErroEnvio(`Escreva uma pergunta com pelo menos ${PERGUNTA_MIN} caracteres.`)
      return
    }
    setEnviando(true)
    setErroEnvio('')
    setEnviada(false)
    try {
      const criada = await criarPergunta(anuncio.id, pergunta)
      setPerguntas((atuais) => [criada, ...atuais])
      setTotal((atual) => atual + 1)
      setTexto('')
      setEnviada(true)
    } catch (erro) {
      setErroEnvio(mensagemApiErro(erro, 'Não foi possível enviar sua pergunta.'))
    } finally {
      setEnviando(false)
    }
  }

  function atualizarPergunta(atualizada: AnuncioPergunta) {
    setPerguntas((atuais) =>
      atuais.map((item) => (item.id === atualizada.id ? atualizada : item)),
    )
  }

  const pendentes = perguntas.filter((item) => item.resposta === null).length

  return (
    <section className="ad-perguntas" aria-labelledby="ad-perguntas-titulo">
      <h2 id="ad-perguntas-titulo">Perguntas e respostas</h2>

      {ehVendedor && (
        <p className="ad-perguntas-aviso">
          Este anúncio é seu.{' '}
          {pendentes > 0
            ? `Você tem ${pendentes} ${pendentes === 1 ? 'pergunta' : 'perguntas'} aguardando resposta.`
            : 'As perguntas dos interessados aparecem aqui para você responder.'}
        </p>
      )}

      {podePerguntar && sessao && (
        <form className="ad-perguntas-form" onSubmit={enviarPergunta} noValidate>
          <label htmlFor="ad-pergunta-texto">Pergunte ao vendedor</label>
          <div className="ad-perguntas-form-linha">
            <textarea
              id="ad-pergunta-texto"
              value={texto}
              rows={2}
              maxLength={PERGUNTA_MAX}
              placeholder="Escreva sua pergunta…"
              onChange={(evento) => {
                setTexto(evento.target.value)
                setEnviada(false)
                if (erroEnvio) setErroEnvio('')
              }}
              aria-invalid={Boolean(erroEnvio)}
              aria-describedby="ad-pergunta-ajuda"
            />
            <button type="submit" className="publish-button" disabled={enviando}>
              {enviando ? 'Enviando…' : 'Perguntar'}
            </button>
          </div>
          <div id="ad-pergunta-ajuda" className="ad-perguntas-form-rodape">
            <span>
              Sua pergunta ficará visível para todos. Não compartilhe telefone, e-mail ou dados
              pessoais.
            </span>
            <span className="ad-perguntas-contador">
              {texto.length}/{PERGUNTA_MAX}
            </span>
          </div>
          {erroEnvio && (
            <p className="ad-perguntas-erro" role="alert">
              {erroEnvio}
            </p>
          )}
          {enviada && (
            <p className="ad-perguntas-sucesso" role="status">
              Pergunta enviada! Você verá a resposta aqui assim que o vendedor responder.
            </p>
          )}
        </form>
      )}

      {podePerguntar && !sessao && (
        <p className="ad-perguntas-aviso">
          <Link to="/login">Entre na sua conta</Link> para fazer uma pergunta ao vendedor.
        </p>
      )}

      {anuncio.status === 'ENCERRADO' && !ehVendedor && (
        <p className="ad-perguntas-aviso">Este anúncio foi encerrado e não recebe novas perguntas.</p>
      )}

      {carregando && <p className="ad-perguntas-vazio">Carregando perguntas…</p>}

      {!carregando && erroLista && (
        <div className="ad-perguntas-erro-lista">
          <p className="ad-perguntas-erro" role="alert">
            {erroLista}
          </p>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setCarregando(true)
              setErroLista('')
              setTentativa((atual) => atual + 1)
            }}
          >
            Recarregar perguntas
          </button>
        </div>
      )}

      {!carregando && !erroLista && perguntas.length === 0 && (
        <p className="ad-perguntas-vazio">
          {ehVendedor
            ? 'Ninguém perguntou nada ainda.'
            : 'Ninguém perguntou nada ainda. Seja o primeiro!'}
        </p>
      )}

      {perguntas.length > 0 && (
        <>
          <h3 className="ad-perguntas-subtitulo">
            {total} {total === 1 ? 'pergunta' : 'perguntas'}
          </h3>
          <ul className="ad-perguntas-lista">
            {perguntas.map((item) => (
              <ItemPergunta
                key={item.id}
                anuncioId={anuncio.id}
                pergunta={item}
                ehMinha={item.autor_id === usuarioId}
                podeResponder={ehVendedor}
                aoResponder={atualizarPergunta}
              />
            ))}
          </ul>
          {perguntas.length < total && (
            <button
              type="button"
              className="ad-perguntas-mais"
              onClick={carregarMais}
              disabled={carregandoMais}
            >
              {carregandoMais ? 'Carregando…' : 'Ver mais perguntas'}
            </button>
          )}
        </>
      )}
    </section>
  )
}

interface ItemPerguntaProps {
  anuncioId: string
  pergunta: AnuncioPergunta
  ehMinha: boolean
  podeResponder: boolean
  aoResponder: (pergunta: AnuncioPergunta) => void
}

function ItemPergunta({
  anuncioId,
  pergunta,
  ehMinha,
  podeResponder,
  aoResponder,
}: ItemPerguntaProps) {
  const [resposta, setResposta] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')
  const idCampo = `ad-resposta-${pergunta.id}`

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
      aoResponder(await responderPergunta(anuncioId, pergunta.id, texto))
    } catch (erroRecebido) {
      setErro(mensagemApiErro(erroRecebido, 'Não foi possível enviar a resposta.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <li className="ad-pergunta">
      <p className="ad-pergunta-texto">
        {pergunta.pergunta}
        {ehMinha && <span className="ad-pergunta-selo">Sua pergunta</span>}
      </p>
      <p className="ad-pergunta-data">{formatarTempoRelativo(pergunta.criado_em)}</p>

      {pergunta.resposta !== null ? (
        <div className="ad-pergunta-resposta">
          <p>{pergunta.resposta}</p>
          {pergunta.respondido_em && (
            <p className="ad-pergunta-data">
              Vendedor · {formatarTempoRelativo(pergunta.respondido_em)}
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
    </li>
  )
}
