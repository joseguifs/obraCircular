# Regras de Domínio — Usuário

O mesmo usuário pode atuar como comprador e vendedor.

## Status

- `ATIVO`: pode comprar, anunciar e operar pedidos próprios.
- `INATIVO`: não inicia novas operações, mas seus registros históricos permanecem.
- `BLOQUEADO`: não pode autenticar nem executar ações protegidas.

## Regras

- O e-mail é único sem diferenciação entre maiúsculas e minúsculas.
- A senha nunca é armazenada diretamente, apenas seu hash seguro.
- A exclusão é lógica por meio de `deletado_em`.
- Desativação, bloqueio ou exclusão não removem pedidos e registros financeiros.

## Recuperação de senha

- O usuário informa o e-mail em `POST /auth/forgot-password` e recebe um link
  `FRONTEND_URL/redefinir-senha?token=...` por e-mail (SMTP).
- A resposta é sempre a mesma (`202`), exista ou não o e-mail, para não revelar quais
  contas estão cadastradas. Usuários `INATIVO`, `BLOQUEADO` ou excluídos não recebem o link.
- O token é aleatório (256 bits), de uso único e expira em
  `OBRA_CIRCULAR_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (padrão: 30 minutos).
- Apenas o hash SHA-256 do token é armazenado em `tokens_recuperacao_senha`.
- Um novo pedido invalida os links anteriores ainda não usados.
- `POST /auth/reset-password/validate` confere o link antes de exibir o formulário, e
  `POST /auth/reset-password` grava a nova senha (8 a 72 caracteres) e consome o token.
- Link inválido, expirado ou já usado retorna `400` com o código
  `PASSWORD_RESET_TOKEN_INVALID`.
