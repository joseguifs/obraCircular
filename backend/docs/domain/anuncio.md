# Regras de Domínio — Anúncio

## Status

- `ATIVO`
- `ESGOTADO`
- `ENCERRADO`

## Regras

- Não existe um papel fixo de vendedor: qualquer usuário `ATIVO` pode anunciar.
- Antes de publicar o primeiro anúncio, o usuário deve conectar uma conta Mercado Pago
  com status `ATIVA`.
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
- Um anúncio pode ter até cinco imagens JPEG, PNG ou WebP; a imagem de ordem zero é a capa.
- Cada imagem precisa ser um arquivo JPEG, PNG ou WebP íntegro (lido pela biblioteca
  Pillow); arquivos corrompidos são recusados com `AD_IMAGE_INVALID_TYPE`.
- As fotos são exibidas no formato 4:3 na horizontal. O recomendado é 1200 × 900 px ou
  mais, e o mínimo é 640 × 480 px (lado maior × lado menor, em qualquer orientação),
  considerando a rotação gravada no EXIF pelo celular.
- Fotos fora do padrão **são aceitas**, porque o vendedor pode não ter outra melhor. O
  envio devolve, em `avisos`, uma orientação por foto com o código:
  - `AD_IMAGE_BELOW_MINIMUM`: abaixo de 640 × 480 px; pode aparecer borrada.
  - `AD_IMAGE_PORTRAIT`: foto na vertical; a página inicial mostra só a parte central.
  - `AD_IMAGE_TOO_WIDE`: proporção acima de 1,9:1; as laterais ficam cortadas.
  - `AD_IMAGE_BELOW_RECOMMENDED`: abaixo de 1200 × 900 px; pode perder nitidez ao ampliar.
- As dimensões não são gravadas no banco; os avisos existem só na resposta do envio.
- O banco armazena apenas a chave e os metadados da imagem. O arquivo fica no serviço de
  armazenamento configurado pela aplicação.
- O vendedor pode pagar um destaque para o anúncio aparecer primeiro nas listagens.
  As regras estão em `docs/domain/destaque_anuncio.md`.
