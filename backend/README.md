# Backend — Obra Circular

API assíncrona em FastAPI do marketplace Obra Circular. Este documento descreve a
configuração do backend e, em especial, o fluxo completo de publicação de anúncios com
endereços, categorias e imagens armazenadas localmente.

Para a configuração inicial do monorepo, consulte também o [README principal](../README.md).

## Tecnologias

- Python 3.12+
- FastAPI
- SQLAlchemy assíncrono
- PostgreSQL 15+
- Alembic
- Pydantic
- Pytest, Ruff e mypy

## Executar localmente

Dentro de `backend/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure no `.env` as credenciais do PostgreSQL e uma chave JWT com pelo menos 32
caracteres. Depois, aplique todas as migrations e inicie a API:

```powershell
python -m alembic upgrade head
python -m fastapi dev app/main.py
```

Serviços locais:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`
- Arquivos enviados: `http://localhost:8000/uploads/...`

## Configuração das imagens

O arquivo `.env.example` contém as configurações do armazenamento local:

```env
OBRA_CIRCULAR_STORAGE_PATH=storage
OBRA_CIRCULAR_MAX_AD_IMAGES=5
OBRA_CIRCULAR_MAX_IMAGE_SIZE_BYTES=5242880
```

Com a configuração padrão, os arquivos ficam em:

```text
backend/storage/anuncios/{anuncio_id}/{uuid}.{extensao}
```

O diretório `backend/storage/` está no `.gitignore` e não deve ser versionado. O nome do
arquivo é sempre gerado pelo backend; o nome original é guardado somente como metadado.

O banco não armazena o conteúdo binário nem uma URL de `localhost`. Ele armazena uma
chave relativa, por exemplo:

```text
anuncios/550e8400-e29b-41d4-a716-446655440000/0f77cda1-57af-4a92-a1be-foto.webp
```

Essa separação permite trocar o armazenamento local por S3, Cloudflare R2 ou outro
serviço sem modificar a estrutura da tabela. Basta implementar outro adaptador que use
a mesma chave de objeto.

O armazenamento local é adequado para desenvolvimento. Em produção com múltiplas
instâncias ou filesystem efêmero, deve ser substituído por armazenamento de objetos.

## Migration de imagens

A migration `20260919_0004_anuncio_imagens.py` cria a tabela `anuncio_imagens`.

```powershell
python -m alembic upgrade head
python -m alembic current
```

O resultado esperado do segundo comando é:

```text
20260919_0004 (head)
```

Para verificar se os models e o banco continuam sincronizados:

```powershell
python -m alembic check
```

### Estrutura de `anuncio_imagens`

| Campo | Descrição |
|---|---|
| `id` | UUID da imagem |
| `anuncio_id` | Anúncio proprietário da imagem |
| `chave_objeto` | Caminho relativo no serviço de armazenamento |
| `nome_original` | Nome recebido no upload, apenas para metadados |
| `mime_type` | `image/jpeg`, `image/png` ou `image/webp` |
| `tamanho_bytes` | Tamanho validado do arquivo |
| `ordem` | Posição da imagem; `0` representa a capa |
| `criado_em` | Data de criação em UTC |
| `atualizado_em` | Data da última atualização em UTC |

Restrições importantes:

- `chave_objeto` é única;
- o par `(anuncio_id, ordem)` é único;
- `tamanho_bytes` deve ser maior que zero;
- `ordem` não pode ser negativa;
- a chave estrangeira usa `ON DELETE CASCADE` para uma eventual remoção física do anúncio;
- atualizações recebem `atualizado_em` pelo mesmo trigger utilizado pelas demais tabelas.

A coluna legada `anuncios.imagem_url` foi mantida temporariamente para preservar a
compatibilidade da API existente. Os novos uploads utilizam `anuncio_imagens`.

## Categorias para desenvolvimento

A feature não cria categorias automaticamente e não inclui uma tela administrativa.
Antes de testar a publicação, insira categorias ativas manualmente:

```sql
INSERT INTO categorias (id, nome, descricao, status)
VALUES
    (gen_random_uuid(), 'Cimento e argamassa', 'Cimentos, argamassas e agregados.', 'ATIVA'),
    (gen_random_uuid(), 'Tijolos e blocos', 'Tijolos, blocos e materiais de alvenaria.', 'ATIVA'),
    (gen_random_uuid(), 'Madeira', 'Madeiras e derivados.', 'ATIVA'),
    (gen_random_uuid(), 'Pisos e revestimentos', 'Pisos, azulejos e revestimentos.', 'ATIVA'),
    (gen_random_uuid(), 'Outros', 'Outros materiais de construção.', 'ATIVA')
ON CONFLICT (nome) DO NOTHING;
```

O `ON CONFLICT` torna o comando seguro para repetição. Apenas categorias com status
`ATIVA` podem ser utilizadas em novos anúncios.

## Fluxo de publicação

A publicação é realizada em etapas para manter o endpoint JSON existente compatível.

```text
Usuário autenticado
      │
      ├── GET /categories?status=ATIVA
      ├── GET /users/me/addresses
      │       └── POST /users/me/addresses, se necessário
      │
      ├── POST /ads
      │       └── retorna anuncio_id
      │
      └── POST /ads/{anuncio_id}/images
              └── multipart/form-data com um ou mais campos "files"
```

Se o upload falhar no frontend depois da criação, ele solicita `DELETE /ads/{id}` como
compensação para não deixar um anúncio incompleto visível.

### 1. Autenticação

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "vendedor@example.com",
  "senha": "senha-forte-123"
}
```

As rotas de criação, upload, alteração e exclusão usam:

```http
Authorization: Bearer {access_token}
```

O frontend renova automaticamente o token em `POST /api/v1/auth/refresh` quando ele está
próximo da expiração ou quando uma rota protegida devolve `401`.

### 2. Listar categorias ativas

```http
GET /api/v1/categories?status=ATIVA&limit=100
```

### 3. Listar endereços do usuário

```http
GET /api/v1/users/me/addresses?limit=100
Authorization: Bearer {access_token}
```

Caso o usuário ainda não tenha endereço:

```http
POST /api/v1/users/me/addresses
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "cep": "01310100",
  "logradouro": "Avenida Paulista",
  "numero": "1000",
  "complemento": "Conjunto 10",
  "bairro": "Bela Vista",
  "cidade": "São Paulo",
  "estado": "SP"
}
```

Endereços excluídos logicamente não aparecem na listagem e não podem ser vinculados a
novos anúncios. O serviço também confirma que o endereço pertence ao vendedor.

### 4. Criar o anúncio

```http
POST /api/v1/ads
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "titulo": "50 blocos de concreto",
  "descricao": "Blocos novos que sobraram da obra.",
  "categoria_id": "0cdf91cd-132f-4e64-bfd9-aac74442f1fd",
  "endereco_id": "6e2d754a-71fc-490f-b98c-66140c9a32ac",
  "preco": "12.50",
  "quantidade": 50
}
```

O `vendedor_id` nunca vem do corpo da requisição. Ele é extraído do access token.

Regras aplicadas pelo serviço:

- o vendedor deve existir e estar `ATIVO`;
- a categoria deve existir e estar `ATIVA`;
- o endereço deve estar ativo e pertencer ao vendedor;
- preço e quantidade não podem ser negativos;
- quantidade zero cria um anúncio `ESGOTADO`;
- quantidade positiva cria um anúncio `ATIVO`;
- o frontend exige quantidade mínima de 1 no fluxo de publicação;
- a criação e suas validações de banco ocorrem em uma transação.

### 5. Enviar imagens

O upload usa `multipart/form-data`. Todos os arquivos devem utilizar o nome de campo
`files`.

Exemplo com `curl.exe` no PowerShell:

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/ads/SEU_ANUNCIO_ID/images" `
  -H "Authorization: Bearer SEU_ACCESS_TOKEN" `
  -F "files=@C:\imagens\material-frente.jpg" `
  -F "files=@C:\imagens\material-detalhe.webp"
```

Resposta resumida:

```json
{
  "items": [
    {
      "id": "uuid-da-imagem",
      "anuncio_id": "uuid-do-anuncio",
      "url": "/uploads/anuncios/uuid-do-anuncio/uuid-da-imagem.jpg",
      "nome_original": "material-frente.jpg",
      "mime_type": "image/jpeg",
      "tamanho_bytes": 245810,
      "ordem": 0,
      "criado_em": "2026-09-19T13:00:00Z"
    }
  ]
}
```

Validações do upload:

- no mínimo um arquivo por requisição;
- no máximo cinco imagens por anúncio na configuração padrão;
- até 5 MB por imagem na configuração padrão;
- somente JPEG, PNG e WebP;
- o tipo real é verificado pela assinatura binária, não apenas pelo cabeçalho enviado;
- somente o vendedor proprietário pode adicionar imagens;
- anúncios encerrados não recebem novas imagens;
- o anúncio é bloqueado com `SELECT ... FOR UPDATE` durante a definição da ordem;
- arquivos já gravados são removidos se a transação falhar;
- a primeira imagem, de ordem `0`, é considerada a capa.

Principais códigos de erro do upload:

| Código | Situação |
|---|---|
| `AD_NOT_FOUND` | Anúncio inexistente ou excluído |
| `AD_FORBIDDEN` | Usuário não é o vendedor |
| `AD_CLOSED` | Anúncio encerrado |
| `AD_IMAGE_REQUIRED` | Nenhum arquivo enviado |
| `AD_IMAGE_LIMIT` | Limite de imagens excedido |
| `AD_IMAGE_TOO_LARGE` | Arquivo maior que o limite |
| `AD_IMAGE_INVALID_TYPE` | Conteúdo não é JPEG, PNG ou WebP válido |

## Outros endpoints de anúncios

| Método | Endpoint | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/api/v1/ads` | Não | Lista e filtra anúncios |
| `GET` | `/api/v1/ads/{id}` | Não | Consulta um anúncio |
| `GET` | `/api/v1/ads/{id}/images` | Não | Lista as imagens de um anúncio |
| `POST` | `/api/v1/ads` | Sim | Cria um anúncio |
| `POST` | `/api/v1/ads/{id}/images` | Sim | Adiciona imagens |
| `PATCH` | `/api/v1/ads/{id}` | Sim | Atualiza um anúncio do vendedor |
| `DELETE` | `/api/v1/ads/{id}` | Sim | Exclui logicamente um anúncio |
| `GET` | `/api/v1/users/{vendedor_id}/ads` | Não | Lista anúncios de um vendedor |

Os filtros disponíveis para `GET /ads` são `category_id`, `status`, `search`,
`min_price`, `max_price`, `offset` e `limit`.

## Organização da implementação

```text
app/
├── api/routes/anuncios.py             # Rotas de anúncios e upload
├── core/config.py                     # Limites e diretório de armazenamento
├── models/anuncio.py                  # Anúncio
├── models/anuncio_imagem.py           # Metadados das imagens
├── repositories/anuncio.py            # Consultas e validação do endereço ativo
├── repositories/anuncio_imagem.py     # Ordem e persistência das imagens
├── schemas/anuncio.py                 # Contratos JSON de anúncios
├── schemas/anuncio_imagem.py          # Resposta do upload
├── services/anuncio.py                # Regras de anúncio
├── services/anuncio_imagem.py         # Regras e transação do upload
└── services/armazenamento.py          # Adaptador de filesystem local

alembic/versions/
└── 20260919_0004_anuncio_imagens.py   # Migration da nova tabela
```

O diretório de arquivos é servido em `/uploads` pelo `StaticFiles` configurado em
`app/main.py`.

## Testes e qualidade

Executar toda a suíte e as verificações:

```powershell
python -m pytest
python -m ruff check .
python -m mypy app
python -m alembic check
```

Os testes específicos da feature cobrem:

- regras e schemas de anúncios;
- criação com categoria, vendedor e endereço;
- rejeição de endereço inválido ou excluído;
- autenticação das rotas;
- upload de imagem válida;
- detecção de arquivo inválido;
- bloqueio de upload por outro vendedor;
- ordem sequencial das imagens.

O frontend possui testes adicionais para validação do formulário, publicação, cadastro
inline de endereço e renovação automática da sessão.

## Migração futura para armazenamento em nuvem

Para migrar sem alterar `anuncio_imagens`:

1. implementar um adaptador com as operações `salvar_imagem`, `excluir` e `url_publica`;
2. copiar `backend/storage/anuncios/` para o bucket preservando as chaves relativas;
3. selecionar o novo adaptador pela configuração da aplicação;
4. configurar URLs públicas ou assinadas no método `url_publica`;
5. remover o mount local de `/uploads` quando ele não for mais necessário.

As URLs assinadas não devem ser persistidas no banco, pois expiram. A
`chave_objeto` permanece como identificador estável do arquivo.

## Limitações atuais e próximos passos

- as categorias são inseridas manualmente; uma futura feature deve administrar o catálogo;
- ainda não há endpoint para remover ou reordenar imagens individualmente;
- a coluna legada `imagem_url` ainda existe;
- o armazenamento local não é compartilhado entre múltiplas instâncias;
- a listagem de anúncios retorna a capa em `imagem_capa_url`; a galeria completa está
  disponível no endpoint específico de imagens;
- jobs futuros podem remover uploads órfãos e aplicar políticas de retenção.
