# Regras de Domínio — Perguntas do Anúncio

Perguntas públicas feitas por usuários ao vendedor de um anúncio, no estilo
"Perguntas e respostas" de marketplaces. Ficam na tabela `anuncio_perguntas`.

## Regras

- Qualquer pessoa pode listar as perguntas de um anúncio não excluído; a listagem
  não exige autenticação.
- Apenas usuários autenticados e com status `ATIVO` podem perguntar.
- O vendedor não pode fazer perguntas no próprio anúncio.
- Anúncios `ATIVO` e `ESGOTADO` recebem perguntas; anúncios `ENCERRADO` ou excluídos
  não recebem.
- A pergunta tem de 3 a 500 caracteres e a resposta de 1 a 1000, sem contar espaços
  nas pontas.
- Somente o vendedor do anúncio, com status `ATIVO`, pode responder.
- Cada pergunta recebe no máximo uma resposta. A pergunta é bloqueada com
  `SELECT ... FOR UPDATE` antes de responder, e uma segunda resposta retorna 409.
- `resposta` e `respondido_em` são preenchidos juntos (garantido por constraint).
- A identidade de quem perguntou não é exibida: a API devolve apenas `autor_id`.
- A exclusão física do anúncio remove as perguntas em cascata. A exclusão lógica
  esconde o anúncio e, com ele, as perguntas.
- A listagem é ordenada da pergunta mais recente para a mais antiga.

## Endpoints

| Método | Rota | Autenticação |
| --- | --- | --- |
| `GET` | `/api/v1/ads/{anuncio_id}/questions?offset=0&limit=20` | Não |
| `POST` | `/api/v1/ads/{anuncio_id}/questions` | Sim |
| `POST` | `/api/v1/ads/{anuncio_id}/questions/{pergunta_id}/answer` | Sim (vendedor) |

## Códigos de erro

| Código | Status | Situação |
| --- | --- | --- |
| `AD_NOT_FOUND` | 404 | Anúncio inexistente ou excluído |
| `QUESTION_OWN_AD` | 403 | Vendedor tentando perguntar no próprio anúncio |
| `AD_CLOSED` | 400 | Pergunta em anúncio encerrado |
| `USER_NOT_ACTIVE` | 403 | Usuário inativo ou bloqueado |
| `QUESTION_ANSWER_FORBIDDEN` | 403 | Quem respondeu não é o vendedor |
| `QUESTION_NOT_FOUND` | 404 | Pergunta inexistente ou de outro anúncio |
| `QUESTION_ALREADY_ANSWERED` | 409 | Pergunta já respondida |
