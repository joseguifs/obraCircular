# Regras de negócio da modelagem inicial

Estas regras vieram com a modelagem do banco e devem ser implementadas na camada
de serviços, dentro de transações quando necessário:

1. A unicidade do e-mail não diferencia maiúsculas de minúsculas.
2. Um comprador não pode adquirir o próprio anúncio.
3. Ao confirmar pagamento, bloquear o anúncio com `SELECT ... FOR UPDATE`, validar
   a quantidade e reduzir o estoque na mesma transação.
4. Quando o estoque chegar a zero, alterar o anúncio para `ESGOTADO`.
5. Confirmar pagamentos e reembolsos consultando o Mercado Pago; não confiar apenas
   no frontend ou no corpo de um webhook.
6. Gerar o PIN de entrega com um gerador criptograficamente seguro e guardar somente
   o hash.
7. Para entrega e retirada, calcular o prazo interno de contestação como sete dias
   corridos após a confirmação pelo PIN. Armazenar as datas em UTC.
8. Bloquear imediatamente o repasse quando uma contestação for aberta.
9. Permitir apenas um reembolso integral por pagamento. Seu valor deve ser igual ao
   valor do pagamento aprovado.
10. Criptografar tokens do provedor fora do banco com chave mantida em secret manager
    ou variável de ambiente.
11. Preservar no pedido o snapshot do endereço usado na compra.
12. Manter o repasse como controle contábil e de estado mesmo quando o split 1:1 do
    Mercado Pago ocorrer automaticamente.
13. Ao validar o PIN, confirmar que `confirmado_por` é o vendedor do anúncio ligado
    ao pedido.
14. Não permitir contestação depois do prazo interno ou depois que o repasse começar
    a ser processado.
15. Cancelamentos posteriores à redução do estoque e reembolsos devem devolver a
    quantidade ao anúncio exatamente uma vez.
16. Atualizações originadas por webhooks e jobs devem ser idempotentes.

## Responsabilidades

- O comprador pode cancelar ou contestar apenas os próprios pedidos.
- O vendedor pode alterar apenas seus anúncios e entregas relacionadas às suas
  vendas.
- Pagamentos, reembolsos e webhooks têm seus estados confirmados pelo backend junto
  ao provedor.
- Resolução de contestação, reprocessamentos manuais e ações excepcionais exigem um
  operador administrativo autenticado. A forma de autenticação e autorização será
  definida na camada de segurança, sem alterar estas regras de domínio.
