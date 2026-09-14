# Regras de Domínio — Endereço

- Todo endereço pertence a um usuário.
- `cep` contém exatamente oito dígitos e `estado` usa duas letras maiúsculas.
- O endereço de um anúncio deve pertencer ao vendedor do anúncio.
- O endereço de entrega deve pertencer ao comprador do pedido.
- Pedidos com modalidade `ENTREGA` guardam uma cópia imutável do endereço em
  `endereco_entrega_snapshot`.
- Alterar ou excluir o endereço cadastrado não modifica o snapshot de pedidos
  existentes.
- A exclusão do endereço é lógica (`deletado_em`): a linha permanece no banco
  para preservar as referências de `anuncios` e `pedidos`, e endereços
  excluídos não aparecem nas consultas do usuário.
- O usuário acessa apenas os próprios endereços; um endereço de outro usuário
  responde 404, igual a um endereço inexistente.
- Pedidos com modalidade `RETIRADA` não possuem endereço de entrega nem snapshot.
