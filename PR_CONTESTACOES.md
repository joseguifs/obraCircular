# Contestações no painel administrativo

Repositório: `joseguifs/obraCircular`

Branch: `feature/gerenciamento-contestacoes-admin`, criada após atualizar a `develop`.

## Alterações

- Aba Contestações no painel, com informações do pedido, comprador, vendedor, motivo e descrição.
- Filtro por status e paginação para consultar todas as contestações.
- Aprovação ou recusa com justificativa, administrador e data registrados.
- Aprovação cria o reembolso integral e reutiliza o fluxo existente do Mercado Pago.
- O pedido fica em contestação e o repasse contábil bloqueado até o reembolso ser confirmado.
- Confirmação direta ou por webhook resolve a contestação e devolve o estoque uma única vez.
- Recusa devolve o pedido para entregue e ajusta o repasse conforme o prazo e as regras do Split 1:1.
- Decisões repetidas preservam a primeira análise. Falhas de reembolso permitem nova tentativa com a mesma chave de idempotência.
- Botão Anunciar removido das páginas administrativas. Ele permanece na área do marketplace.

Não foi necessário criar migration: a tabela de contestações já existe na develop. O fluxo de abertura pelo comprador é uma feature separada, que deve preencher essa tabela seguindo o domínio existente.

## Rodar no terminal do VS Code

Abra a pasta correta:

```powershell
cd C:\Users\viken\Documents\ChatGPT\Outros\obraCircular
git branch --show-current
```

O ambiente Python e as dependências do frontend estão instalados. O arquivo local `backend/.env` foi preparado a partir do exemplo, com chave JWT local gerada. Configure o PostgreSQL em `OBRA_CIRCULAR_DATABASE_URL` antes de iniciar. Use um banco local de desenvolvimento.

No primeiro terminal:

```powershell
cd backend
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

No segundo terminal:

```powershell
cd C:\Users\viken\Documents\ChatGPT\Outros\obraCircular\frontend
npm run dev
```

Abra `http://localhost:5173`. Cadastre um usuário pelo aplicativo e, para conceder acesso ao painel, execute em outro terminal:

```powershell
cd C:\Users\viken\Documents\ChatGPT\Outros\obraCircular\backend
.\venv\Scripts\python.exe -m app.cli.promover_administrador seu-email@example.com
```

Entre novamente na conta e acesse Administração → Contestações. Sem registros no banco, será exibido o estado vazio. Para solicitar reembolsos reais, é necessária a configuração existente do Mercado Pago e a conta OAuth do vendedor; os testes usam respostas simuladas.

## Verificações

```powershell
cd C:\Users\viken\Documents\ChatGPT\Outros\obraCircular\backend
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m mypy app
cd ../frontend
npm run build
npm run lint
npm test
```

A suíte completa do backend precisa do PostgreSQL em execução e das migrations aplicadas. Os testes isolados de contestações podem ser executados com:

```powershell
cd ../backend
.\venv\Scripts\python.exe -m pytest tests/test_contestacao_service.py tests/test_contestacao_api.py -q
```

## Commit e PR

Revise as alterações antes do commit. Na raiz do repositório:

```powershell
git status
git diff
git add backend/app/api/routes/admin.py backend/app/schemas/admin.py backend/app/repositories/contestacao.py backend/app/services/contestacao.py backend/app/services/reembolso.py backend/app/services/webhook_mercado_pago.py backend/docs/domain/contestacao.md backend/tests/test_contestacao_api.py backend/tests/test_contestacao_service.py frontend/src/app/router.tsx frontend/src/features/admin frontend/src/layouts/MarketplaceLayout.tsx PR_CONTESTACOES.md
git commit -m "feat: adiciona gerenciamento de contestacoes no painel admin"
git push -u origin feature/gerenciamento-contestacoes-admin
```

No GitHub, compare `develop` (base) com `feature/gerenciamento-contestacoes-admin` (compare).

Título sugerido: `feat: gerenciamento de contestações no painel admin`.

Descrição sugerida:

```text
Adiciona listagem paginada e filtros de contestações no painel administrativo.
Permite aprovar ou recusar com justificativa e registro do administrador.

A aprovação solicita reembolso integral pelo fluxo existente do Mercado Pago.
A contestação só fica resolvida após confirmação do provedor. Falhas permitem
nova tentativa com a mesma chave de idempotência. A recusa preserva a entrega.

Remove o botão Anunciar das páginas administrativas.
Reutiliza a tabela existente, sem nova migration.

Validação: testes isolados de serviço/API e testes do frontend, build,
lint dos arquivos alterados e mypy. Integração com PostgreSQL pendente
de ambiente local configurado.
```

Atualize a descrição caso execute a suíte com PostgreSQL antes de abrir o PR. Não inclua `.env`, ambiente virtual ou arquivos locais.
