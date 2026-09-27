import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import { useNavigate } from 'react-router'
import { mensagemApiErro } from '../../lib/api'
import { listarCategoriasAtivas } from '../categorias/categoriaApi'
import { cadastrarEndereco, listarEnderecos } from '../enderecos/enderecoApi'
import type { EnderecoPayload } from '../enderecos/types'
import {
  criarAnuncio,
  enviarImagens,
  excluirAnuncio,
} from './anuncioApi'
import type { ErrosAnuncio } from './types'
import { validarAnuncio, validarImagens } from './validacaoAnuncio'

const enderecoInicial: EnderecoPayload = {
  cep: '',
  logradouro: '',
  numero: '',
  complemento: '',
  bairro: '',
  cidade: '',
  estado: '',
}

export function PublicarAnuncioPage() {
  const navegar = useNavigate()
  const [categorias, setCategorias] = useState<Awaited<ReturnType<typeof listarCategoriasAtivas>>>([])
  const [enderecos, setEnderecos] = useState<Awaited<ReturnType<typeof listarEnderecos>>>([])
  const [carregando, setCarregando] = useState(true)
  const [erroGeral, setErroGeral] = useState('')
  const [erros, setErros] = useState<ErrosAnuncio>({})
  const [enviando, setEnviando] = useState(false)
  const [titulo, setTitulo] = useState('')
  const [descricao, setDescricao] = useState('')
  const [categoriaId, setCategoriaId] = useState('')
  const [enderecoId, setEnderecoId] = useState('')
  const [preco, setPreco] = useState('')
  const [quantidade, setQuantidade] = useState('1')
  const [imagens, setImagens] = useState<File[]>([])
  const [mostrarEndereco, setMostrarEndereco] = useState(false)
  const [novoEndereco, setNovoEndereco] = useState(enderecoInicial)
  const [salvandoEndereco, setSalvandoEndereco] = useState(false)
  const [erroEndereco, setErroEndereco] = useState('')

  const previews = useMemo(
    () => imagens.map((arquivo) => ({ arquivo, url: URL.createObjectURL(arquivo) })),
    [imagens],
  )

  useEffect(() => () => previews.forEach((preview) => URL.revokeObjectURL(preview.url)), [previews])

  useEffect(() => {
    let ativo = true
    Promise.all([listarCategoriasAtivas(), listarEnderecos()])
      .then(([categoriasRecebidas, enderecosRecebidos]) => {
        if (!ativo) return
        setCategorias(categoriasRecebidas)
        setEnderecos(enderecosRecebidos)
        if (enderecosRecebidos.length === 0) setMostrarEndereco(true)
      })
      .catch((erro) => {
        if (ativo) setErroGeral(mensagemApiErro(erro, 'Não foi possível preparar o formulário.'))
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  async function publicar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (enviando) return

    const dados = {
      titulo: titulo.trim(),
      descricao: descricao.trim(),
      categoria_id: categoriaId,
      endereco_id: enderecoId,
      preco,
      quantidade: Number(quantidade),
    }
    const novosErros = validarAnuncio(dados, preco, quantidade, imagens)
    setErros(novosErros)
    setErroGeral('')
    if (Object.keys(novosErros).length > 0) return

    setEnviando(true)
    let anuncioId: string | null = null
    try {
      const anuncio = await criarAnuncio(dados)
      anuncioId = anuncio.id
      if (imagens.length > 0) await enviarImagens(anuncio.id, imagens)
      navegar(`/anuncios/${anuncio.id}/publicado`, {
        replace: true,
        state: { titulo: anuncio.titulo, quantidadeImagens: imagens.length },
      })
    } catch (erro) {
      if (anuncioId) {
        try {
          await excluirAnuncio(anuncioId)
        } catch {
          // A mensagem original é mais útil; a API mantém a exclusão idempotente no fluxo normal.
        }
      }
      setErroGeral(mensagemApiErro(erro, 'Não foi possível publicar o anúncio.'))
    } finally {
      setEnviando(false)
    }
  }

  async function salvarEndereco() {
    setErroEndereco('')
    if (!enderecoValido(novoEndereco)) {
      setErroEndereco('Preencha os campos obrigatórios e informe um CEP com 8 dígitos.')
      return
    }

    setSalvandoEndereco(true)
    try {
      const endereco = await cadastrarEndereco({
        ...novoEndereco,
        cep: novoEndereco.cep.replace(/\D/g, ''),
        estado: novoEndereco.estado.trim().toUpperCase(),
        ...(novoEndereco.complemento?.trim()
          ? { complemento: novoEndereco.complemento.trim() }
          : { complemento: undefined }),
      })
      setEnderecos((atuais) => [endereco, ...atuais])
      setEnderecoId(endereco.id)
      setNovoEndereco(enderecoInicial)
      setMostrarEndereco(false)
      setErros((atuais) => ({ ...atuais, endereco: undefined }))
    } catch (erro) {
      setErroEndereco(mensagemApiErro(erro, 'Não foi possível cadastrar o endereço.'))
    } finally {
      setSalvandoEndereco(false)
    }
  }

  function selecionarImagens(evento: ChangeEvent<HTMLInputElement>) {
    const selecionadas = Array.from(evento.target.files ?? [])
    const erro = validarImagens(selecionadas)
    setImagens(erro ? [] : selecionadas)
    setErros((atuais) => ({ ...atuais, imagens: erro }))
    evento.target.value = ''
  }

  function removerImagem(indice: number) {
    setImagens((atuais) => atuais.filter((_, atual) => atual !== indice))
    setErros((atuais) => ({ ...atuais, imagens: undefined }))
  }

  if (carregando) return <div className="publish-loading">Preparando publicação…</div>

  return (
    <main className="publish-page">
      <header className="publish-heading">
        <button type="button" className="back-button" onClick={() => navegar('/home')}>
          ← Voltar
        </button>
        <span className="step-label">Reaproveitar materiais</span>
        <h1>Publique seu anúncio</h1>
        <p>Conte o que sobrou da sua obra e ajude esse material a encontrar um novo destino.</p>
      </header>

      {erroGeral && <div className="publish-alert" role="alert">{erroGeral}</div>}
      {categorias.length === 0 && (
        <div className="publish-alert" role="alert">
          Nenhuma categoria ativa foi encontrada. Cadastre uma categoria no banco antes de publicar.
        </div>
      )}

      <form className="publish-form" onSubmit={publicar} noValidate aria-busy={enviando}>
        <section className="publish-card">
          <CabecalhoSecao numero="1" titulo="Sobre o material" />
          <Campo label="Título" erro={erros.titulo}>
            <input value={titulo} maxLength={150} onChange={(e) => setTitulo(e.target.value)} placeholder="Ex.: 50 blocos de concreto sem uso" />
          </Campo>
          <Campo label="Descrição" erro={erros.descricao}>
            <textarea value={descricao} onChange={(e) => setDescricao(e.target.value)} placeholder="Informe estado de conservação, medidas e outros detalhes importantes." rows={5} />
          </Campo>
          <div className="publish-grid publish-grid--three">
            <Campo label="Categoria" erro={erros.categoria}>
              <select value={categoriaId} onChange={(e) => setCategoriaId(e.target.value)}>
                <option value="">Selecione</option>
                {categorias.map((categoria) => <option key={categoria.id} value={categoria.id}>{categoria.nome}</option>)}
              </select>
            </Campo>
            <Campo label="Preço unitário" erro={erros.preco}>
              <input type="number" min="0" step="0.01" value={preco} onChange={(e) => setPreco(e.target.value)} placeholder="0,00" />
            </Campo>
            <Campo label="Quantidade" erro={erros.quantidade}>
              <input type="number" min="1" step="1" value={quantidade} onChange={(e) => setQuantidade(e.target.value)} />
            </Campo>
          </div>
        </section>

        <section className="publish-card">
          <CabecalhoSecao numero="2" titulo="Fotos" />
          <p className="section-hint">Adicione até 5 imagens JPEG, PNG ou WebP de no máximo 5 MB. A primeira será a capa.</p>
          <label className="image-picker">
            <input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={selecionarImagens} />
            <span>Selecionar imagens</span>
            <small>{imagens.length}/5 selecionadas</small>
          </label>
          {erros.imagens && <p className="publish-field-error">{erros.imagens}</p>}
          {previews.length > 0 && (
            <div className="image-previews">
              {previews.map((preview, indice) => (
                <figure key={`${preview.arquivo.name}-${indice}`}>
                  <img src={preview.url} alt={`Prévia ${indice + 1}`} />
                  {indice === 0 && <figcaption>Capa</figcaption>}
                  <button type="button" onClick={() => removerImagem(indice)} aria-label={`Remover ${preview.arquivo.name}`}>×</button>
                </figure>
              ))}
            </div>
          )}
        </section>

        <section className="publish-card">
          <CabecalhoSecao numero="3" titulo="Localização do material" />
          {enderecos.length > 0 && (
            <div className="address-options">
              {enderecos.map((endereco) => (
                <label key={endereco.id} className={enderecoId === endereco.id ? 'address-option address-option--selected' : 'address-option'}>
                  <input type="radio" name="endereco" checked={enderecoId === endereco.id} onChange={() => setEnderecoId(endereco.id)} />
                  <span><strong>{endereco.logradouro}, {endereco.numero}</strong>{endereco.bairro} · {endereco.cidade}/{endereco.estado} · CEP {formatarCep(endereco.cep)}</span>
                </label>
              ))}
            </div>
          )}
          {erros.endereco && <p className="publish-field-error">{erros.endereco}</p>}
          <button type="button" className="secondary-button" onClick={() => setMostrarEndereco((atual) => !atual)}>
            {mostrarEndereco ? 'Cancelar novo endereço' : '+ Cadastrar outro endereço'}
          </button>
          {mostrarEndereco && (
            <EnderecoForm dados={novoEndereco} salvando={salvandoEndereco} erro={erroEndereco} aoAlterar={setNovoEndereco} aoEnviar={salvarEndereco} />
          )}
        </section>

        <div className="publish-actions">
          <button type="button" className="secondary-button" onClick={() => navegar('/home')} disabled={enviando}>Cancelar</button>
          <button type="submit" className="publish-button" disabled={enviando || categorias.length === 0}>
            {enviando ? <><span className="spinner" /> Publicando…</> : 'Publicar anúncio'}
          </button>
        </div>
      </form>
    </main>
  )
}

function Campo({ label, erro, children }: { label: string; erro?: string; children: React.ReactNode }) {
  return <label className="publish-field"><span>{label}</span>{children}{erro && <small>{erro}</small>}</label>
}

function CabecalhoSecao({ numero, titulo }: { numero: string; titulo: string }) {
  return <div className="section-heading"><span>{numero}</span><h2>{titulo}</h2></div>
}

function EnderecoForm({ dados, salvando, erro, aoAlterar, aoEnviar }: { dados: EnderecoPayload; salvando: boolean; erro: string; aoAlterar: (dados: EnderecoPayload) => void; aoEnviar: () => void }) {
  function alterar(campo: keyof EnderecoPayload, valor: string) { aoAlterar({ ...dados, [campo]: valor }) }
  return (
    <div className="address-form">
      <h3>Novo endereço</h3>
      <div className="publish-grid">
        <Campo label="CEP">
          <input
            value={dados.cep}
            maxLength={8}
            inputMode="numeric"
            placeholder="Somente números"
            onChange={(e) => alterar('cep', e.target.value.replace(/\D/g, ''))}
          />
        </Campo>
        <Campo label="Estado"><input value={dados.estado} maxLength={2} onChange={(e) => alterar('estado', e.target.value)} /></Campo>
      </div>
      <div className="publish-grid publish-grid--address">
        <Campo label="Logradouro"><input value={dados.logradouro} maxLength={150} onChange={(e) => alterar('logradouro', e.target.value)} /></Campo>
        <Campo label="Número"><input value={dados.numero} maxLength={20} onChange={(e) => alterar('numero', e.target.value)} /></Campo>
      </div>
      <div className="publish-grid">
        <Campo label="Bairro"><input value={dados.bairro} maxLength={100} onChange={(e) => alterar('bairro', e.target.value)} /></Campo>
        <Campo label="Cidade"><input value={dados.cidade} maxLength={100} onChange={(e) => alterar('cidade', e.target.value)} /></Campo>
      </div>
      <Campo label="Complemento"><input value={dados.complemento ?? ''} maxLength={100} onChange={(e) => alterar('complemento', e.target.value)} /></Campo>
      {erro && <p className="publish-field-error" role="alert">{erro}</p>}
      <button type="button" className="secondary-button" disabled={salvando} onClick={aoEnviar}>{salvando ? 'Salvando…' : 'Salvar endereço'}</button>
    </div>
  )
}

function enderecoValido(endereco: EnderecoPayload) {
  return endereco.cep.replace(/\D/g, '').length === 8 && ['logradouro', 'numero', 'bairro', 'cidade', 'estado'].every((campo) => String(endereco[campo as keyof EnderecoPayload] ?? '').trim())
}

function formatarCep(cep: string) { return cep.replace(/(\d{5})(\d{3})/, '$1-$2') }
