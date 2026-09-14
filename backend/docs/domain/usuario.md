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
