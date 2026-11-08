# Frontend

Aplicação React + TypeScript do Obra Circular, construída com Vite.

A navegação usa React Router 7, com rotas públicas para autenticação e uma
área protegida para as telas internas do marketplace.

## Configuração local

```powershell
cd frontend
npm.cmd ci
Copy-Item .env.example .env
npm.cmd run dev
```

O frontend fica disponível em `http://localhost:5173`. Por padrão, ele consome a API
em `http://localhost:8000/api/v1`; altere `VITE_API_URL` no `.env` quando necessário.

A porta `5173` é fixa para coincidir com o CORS da API e os retornos do Mercado Pago.
Se ela estiver ocupada, o Vite informa o erro em vez de iniciar em outra porta.
Mantenha o frontend em execução enquanto testa o retorno do checkout no mesmo computador.

## Comandos

```powershell
npm.cmd run dev
npm.cmd run build
npm.cmd run lint
npm.cmd test
```

O uso de `npm.cmd` evita o bloqueio do `npm.ps1` em instalações do Windows cuja
política de execução do PowerShell não permite scripts. Em Linux e macOS, use `npm`.

## Rotas atuais

- `/login`: entrada na plataforma; redireciona usuários autenticados para a home.
- `/cadastro`: criação de conta; redireciona usuários autenticados para a home.
- `/home`: rota protegida, disponível apenas enquanto a sessão estiver válida.
- `/perfil`: consulta e edição de nome, e-mail e telefone do usuário autenticado.
- `/perfil/enderecos`: consulta paginada e edição dos próprios endereços.
- `/anuncios/novo` e `/anuncios/:anuncioId/publicado`: publicação de anúncios (rotas protegidas).
- `/anuncios/:anuncioId`: detalhes, categoria, disponibilidade, preço e galeria do anúncio.
- `/pedidos`: lista dos pedidos do comprador autenticado.
- `/pedidos/:pedidoId`: acompanhamento do pedido, pagamento, reembolso e acesso às contestações.
- `/pedidos/:pedidoId/contestacoes`: abertura e histórico de contestações do pedido, inclusive em produção.
- `/testes/contestacao`: seletor auxiliar de pedidos para testar o mesmo formulário; somente em desenvolvimento.
- `/categorias`: cadastro, listagem e edição de categorias. Pública temporariamente, sem
  autenticação; deve voltar para a área protegida quando houver perfil administrativo.
- Qualquer endereço desconhecido exibe a página de erro 404.

Em hospedagem estática, o servidor deve redirecionar as URLs do frontend para
`index.html`, permitindo que o React Router resolva acessos diretos como `/home`.

## Contestações

Em **Meus pedidos**, abra o detalhe do pedido e selecione **Abrir contestação**.
Informe o motivo e a descrição do problema. A tela apresenta a confirmação, o
protocolo e o histórico atualizado. Nos demais estados do pedido, o acesso aparece
como **Ver contestações**. A sessão é obrigatória e a API limita os dados ao comprador.

A abertura exige entrega confirmada, prazo de sete dias ainda válido e repasse em
estado permitido. Os erros da API são exibidos sem apagar o texto digitado. Pedidos
ainda não entregues ou com contestação ativa não permitem novo envio. Após sucesso
ou falha de comunicação, a tela consulta novamente o pedido e o histórico.

No detalhe de um pedido pago, o comprador pode **Gerar PIN da entrega**. O código
fica somente na memória da página, com validade exibida; gerar outro invalida o
anterior. O comprador deve conferir todo o material antes de informar o PIN.

Em **Minhas vendas** (`/vendas`), o vendedor seleciona **Confirmar entrega/retirada**
e informa os cinco dígitos recebidos. O backend valida o PIN e, na mesma transação,
confirma a entrega, altera o pedido para `ENTREGUE` e inicia o prazo de sete dias
para contestação. Erros, expiração e bloqueio do PIN são apresentados na tela.
As vendas são consultadas por `GET /api/v1/orders/sales`, restrito ao vendedor
autenticado. A consulta não retorna PIN nem hash.

O detalhe da compra acompanha a confirmação automaticamente a cada dez segundos
(por até dez minutos), ao retornar à janela ou pelo botão **Atualizar pedido**.
A tela de contestação mostra o prazo e impede o envio quando ele termina ou quando
o estado do repasse já impede a abertura. O backend repete as validações ao enviar.

O modelo atual recebe na plataforma e faz repasse posterior via Pix. A contestação
impede essa liberação; as contas de teste utilizadas não têm chave Pix, portanto
a transferência financeira é validada apenas com gateways simulados. Detalhes e
comandos de teste: [abertura de contestação](../backend/docs/abertura-contestacao.md).

## Perfil e endereços

Após entrar, acesse **Meu perfil** no cabeçalho. Os dados são carregados da API;
**Editar dados** permite salvar alterações ou cancelar. O telefone pode ser removido.
E-mails duplicados são recusados pelo backend, inclusive sem distinção de maiúsculas,
e a mensagem aparece junto ao campo. Após salvar, a sessão e o cabeçalho recebem os
novos dados sem descartar tokens renovados durante a requisição.

Em **Meus endereços**, escolha **Editar endereço**. CEP, UF e campos obrigatórios
são validados antes do envio. O complemento pode ser removido. A edição usa PATCH
sobre o mesmo registro; não cadastra outro endereço e não altera o endereço histórico
de pedidos existentes. A API limita o acesso aos endereços do próprio usuário.

As telas seguem o layout compartilhado, as cores e os componentes visuais do projeto.
O perfil mantém a referência visual iniciada na branch `feature/tela-home`.
Os testes cobrem proteção de rotas, erros, cancelamento, atualização da sessão,
e-mail duplicado, paginação e edição autenticada.
