# Regras de Domínio — Anúncio

## Status

- `ATIVO`
- `ESGOTADO`
- `ENCERRADO`

## Regras

- O endereço do anúncio deve pertencer ao vendedor.
- O vendedor não pode comprar o próprio anúncio.
- Preço e quantidade não podem ser negativos.
- Apenas anúncio `ATIVO`, não excluído e com estoque suficiente pode ser comprado.
- Na aprovação do pagamento, o anúncio é bloqueado com `SELECT ... FOR UPDATE` e a
  quantidade comprada é reduzida na mesma transação.
- Quando a quantidade chegar a zero, o anúncio passa para `ESGOTADO`.
- Ao devolver estoque, a aplicação bloqueia o anúncio e soma a quantidade exatamente
  uma vez. Se estava `ESGOTADO` e não está encerrado ou excluído, retorna para
  `ATIVO`.
- `ENCERRADO` representa encerramento deliberado pelo vendedor e não é reativado
  automaticamente pela reposição de estoque.
- A exclusão é lógica por meio de `deletado_em`.
