# Obra Circular

Marketplace para compra e venda de materiais de construção. O projeto está organizado
como um monorepo com uma API FastAPI, banco PostgreSQL e frontend React com TypeScript.

## Tecnologias do projeto

### Backend

- Python 3.12+
- FastAPI
- SQLAlchemy assíncrono
- Alembic para migrations
- PostgreSQL 15+
- Pytest, Ruff e mypy para qualidade e testes

### Frontend

- Node.js 20.19+ ou 22.12+
- npm, instalado junto com o Node.js
- React 19
- TypeScript
- Vite
- Vitest e Testing Library para testes
- Oxlint para análise estática

## O que precisa estar instalado

Antes de clonar e executar o projeto, cada integrante da equipe deve instalar:

1. [Git](https://git-scm.com/downloads)
2. [Python 3.12 ou superior](https://www.python.org/downloads/)
3. [PostgreSQL 15 ou superior](https://www.postgresql.org/download/)
4. [Node.js](https://nodejs.org/) em uma versão compatível com o Vite

O Docker não é necessário. O PostgreSQL deve estar em execução na máquina local.

Para conferir as instalações:

```powershell
git --version
python --version
psql --version
node --version
npm.cmd --version
```

## Estrutura principal

```text
obraCircular/
├── backend/
│   ├── alembic/          # Migrations do banco
│   ├── app/              # API, models, schemas, services e repositories
│   ├── docs/domain/      # Regras de negócio
│   └── tests/            # Testes do backend
├── frontend/
│   ├── src/features/     # Funcionalidades e telas por domínio
│   ├── src/lib/          # Infraestrutura compartilhada, como cliente HTTP
│   └── src/test/         # Configuração dos testes do frontend
└── README.md
```

## Primeira configuração

Clone o repositório e entre na pasta do projeto:

```powershell
git clone https://github.com/joseguifs/obraCircular.git
cd obraCircular
```

### 1. Configurar o PostgreSQL

Crie o banco de dados local usado pelo projeto:

```powershell
psql -U postgres -c "CREATE DATABASE obra_circular_web;"
```

Se o banco já existir, não execute esse comando novamente.

### 2. Configurar o backend

Dentro da raiz do projeto:

```powershell
cd backend

# Cria um ambiente virtual exclusivo para o backend
python -m venv .venv

# Ativa o ambiente virtual
.venv\Scripts\Activate.ps1

# Instala todas as dependências do backend dentro da .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Cria o arquivo local de configuração
Copy-Item .env.example .env
```

Abra `backend/.env` e substitua `SEU_USUARIO` e `SUA_SENHA` pelas credenciais do
PostgreSQL local:

```env
OBRA_CIRCULAR_DATABASE_URL=postgresql+asyncpg://SEU_USUARIO:SUA_SENHA@localhost:5432/obra_circular_web
```

Com o PostgreSQL iniciado, aplique as migrations:

```powershell
python -m alembic upgrade head
```

### 3. Configurar o frontend

Volte à raiz e entre no frontend:

```powershell
cd ..\frontend

# Instala exatamente as versões registradas no package-lock.json
npm.cmd ci

# Cria a configuração local do frontend
Copy-Item .env.example .env
```

O arquivo `frontend/.env` aponta, por padrão, para a API local:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

Os arquivos `.env` contêm configurações locais, estão no `.gitignore` e não devem ser
commitados.

## Executar backend e frontend juntos

São necessários dois terminais.

### Terminal 1 — backend

```powershell
cd obraCircular\backend
.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m fastapi dev app/main.py
```

O backend estará disponível em:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

### Terminal 2 — frontend

```powershell
cd obraCircular\frontend
npm.cmd run dev
```

O frontend estará disponível em `http://localhost:5173` e consumirá o endpoint de
cadastro `POST /api/v1/users` do backend.

## Execuções seguintes

Depois da primeira configuração, normalmente basta executar:

```powershell
# Terminal do backend
cd backend
.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m fastapi dev app/main.py
```

```powershell
# Terminal do frontend
cd frontend
npm.cmd run dev
```

Execute `npm.cmd ci` novamente quando o `package-lock.json` mudar e
`python -m pip install -r requirements.txt` quando o `requirements.txt` mudar.

## Testes e verificações

### Backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest
python -m ruff check .
python -m mypy app
python -m alembic check
```

### Frontend

```powershell
cd frontend
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

## Linux e macOS

As principais diferenças são a ativação da `.venv`, a cópia dos arquivos de ambiente
e o comando do npm:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env

cd ../frontend
npm ci
cp .env.example .env
```

## Problemas comuns

### `npm.ps1` não pode ser carregado

Em algumas instalações do Windows, o PowerShell bloqueia o script `npm.ps1`. Use
`npm.cmd` nos comandos, como mostrado neste README.

### `No module named alembic`

Confirme que a `.venv` do backend está ativa e que as dependências foram instaladas:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

### Erro de conexão com o PostgreSQL

Confira se o serviço do PostgreSQL está iniciado, se o banco `obra_circular_web`
existe e se usuário, senha e porta em `backend/.env` estão corretos.

### Frontend não consegue acessar o backend

Confirme que:

- o backend está respondendo em `http://localhost:8000/api/v1/health`;
- `VITE_API_URL` aponta para `http://localhost:8000/api/v1`;
- o frontend está sendo executado em `http://localhost:5173`.
