# Regras de Domínio — Conta do vendedor

O único provedor suportado no MVP é `MERCADO_PAGO`.

## Status

- `PENDENTE`
- `ATIVA`
- `BLOQUEADA`
- `DESCONECTADA`

## Transições

```text
PENDENTE -> ATIVA
ATIVA -> BLOQUEADA
ATIVA ou BLOQUEADA -> DESCONECTADA
DESCONECTADA -> PENDENTE
```

- `PENDENTE` aguarda a conclusão do OAuth.
- `ATIVA` permite receber repasses.
- `BLOQUEADA` impede novos repasses até regularização.
- `DESCONECTADA` indica revogação ou encerramento da autorização. Uma nova conexão
  reinicia o fluxo como `PENDENTE`.

## Regras

- A vinculação faz parte do fluxo de publicação: qualquer usuário ativo que queira
  anunciar pode cadastrar sua conta Mercado Pago, sem possuir previamente um papel de
  vendedor.
- Cada vendedor possui no máximo uma conta por provedor.
- `conta_externa_id` identifica o vendedor no Mercado Pago.
- Tokens OAuth nunca são armazenados em texto puro.
- A aplicação criptografa os tokens antes de persistir, utilizando chave externa ao
  banco, mantida em variável de ambiente segura ou gerenciador de segredos.
- Tokens expirados devem ser renovados antes de iniciar uma operação. Falha de
  renovação altera a conta para `BLOQUEADA`; revogação confirmada altera para
  `DESCONECTADA`.
