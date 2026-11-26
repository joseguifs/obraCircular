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

## Cadastro

- `POST /users` é público e cria o usuário já como `ATIVO`; o status não pode ser escolhido.
- O cadastro não inicia sessão: a resposta (`201`) traz apenas os dados públicos do
  usuário, sem tokens. Para entrar, o usuário se autentica em `POST /auth/login`.
- Logo após o cadastro, o frontend leva o usuário à tela de login (`/login`) com o
  e-mail da conta já preenchido; a conta recém-criada deve conseguir autenticar
  imediatamente.

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
