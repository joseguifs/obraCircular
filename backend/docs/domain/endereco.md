# Regras de Domínio — Endereço

- Todo endereço pertence a um usuário.
- `cep` contém exatamente oito dígitos e `estado` usa duas letras maiúsculas.
- O endereço de um anúncio deve pertencer ao vendedor do anúncio.
- O endereço de entrega deve pertencer ao comprador do pedido.
- Pedidos com modalidade `ENTREGA` guardam uma cópia imutável do endereço em
  `endereco_entrega_snapshot`.
- Alterar ou excluir o endereço cadastrado não modifica o snapshot de pedidos
  existentes.
- Pedidos com modalidade `RETIRADA` não possuem endereço de entrega nem snapshot.
