# Obra Circular

Marketplace para compra e venda de materiais de construção. O repositório está
preparado como monorepo; nesta primeira etapa contém o backend em FastAPI.

## Requisitos

- Python 3.12+
- PostgreSQL 15+ executando localmente
- Banco de dados `obra_circular_web` criado

## Primeira configuração — Windows/PowerShell

```powershell
git clone -b develop https://github.com/joseguifs/obraCircular.git
cd obraCircular\backend

# Cria e ativa um ambiente isolado para o projeto
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instala dependências de execução, teste e desenvolvimento
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Cria a configuração local
Copy-Item .env.example .env
```

Edite `backend/.env` e substitua `SEU_USUARIO` e `SUA_SENHA` pelas credenciais do
PostgreSQL de cada desenvolvedor. O arquivo `.env` é local e não deve ser commitado.

Se o banco ainda não existir na máquina do desenvolvedor, ele pode ser criado com:

```powershell
psql -U postgres -c "CREATE DATABASE obra_circular_web;"
```

Com o PostgreSQL iniciado e o ambiente virtual ativado:

```powershell
# Cria ou atualiza as tabelas até a migration mais recente
python -m alembic upgrade head

# Inicia a API com recarregamento automático
fastapi dev app/main.py
```

A API ficará disponível em `http://localhost:8000`, a documentação Swagger em
`http://localhost:8000/docs` e o health check em `http://localhost:8000/api/v1/health`.

Nas próximas vezes, basta executar:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m alembic upgrade head
fastapi dev app/main.py
```

No Linux ou macOS, a ativação equivalente é `source .venv/bin/activate` e a cópia
do arquivo de ambiente é `cp .env.example .env`.

## Comandos úteis

```powershell
# Ver a migration atualmente aplicada
python -m alembic current

# Ver o histórico de migrations
python -m alembic history

# Criar uma migration após alterar os models
python -m alembic revision --autogenerate -m "descricao da alteracao"

# Aplicar migrations
python -m alembic upgrade head

# Executar testes e análise estática
python -m pytest
python -m ruff check .
python -m mypy app
```


