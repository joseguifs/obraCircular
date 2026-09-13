# Frontend

Aplicação React + TypeScript do Obra Circular, construída com Vite.

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
