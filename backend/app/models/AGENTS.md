# Regras para os modelos de domínio

Antes de alterar um model, uma migration ou registros de uma entidade, leia a regra
geral e os documentos dos domínios envolvidos:

`docs/regras-de-negocio.md`
`docs/domain/anuncio.md`
`docs/domain/categoria.md`
`docs/domain/conta_pagamento.md`
`docs/domain/contestacao.md`
`docs/domain/endereco.md`
`docs/domain/entrega.md`
`docs/domain/evento_provedor.md`
`docs/domain/pagamento.md`
`docs/domain/pedido.md`
`docs/domain/reembolso.md`
`docs/domain/repasse.md`
`docs/domain/usuario.md`
`docs/domain/fluxo_pedido.md`

Regras que envolvam mais de uma entidade devem ser implementadas na camada de
serviços, em uma única transação e com comportamento idempotente.
