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
- Qualquer endereço desconhecido exibe a página de erro 404.

Em hospedagem estática, o servidor deve redirecionar as URLs do frontend para
`index.html`, permitindo que o React Router resolva acessos diretos como `/home`.

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
