# SupaProxy MCP Server

MCP (Model Context Protocol) server that exposes the [SupaProxy](https://github.com/your-org/SupaProxy) REST API as tools for Claude.

SupaProxy is a Supabase-compatible API proxy backed by SQL Server. This MCP server allows Claude to interact with any SQL Server database through SupaProxy, including schema introspection, CRUD operations, user management, file storage, knowledge base (RAG), edge functions, and encrypted secrets.

## Features

| Module | Tools | Description |
|--------|-------|-------------|
| **Schema** | `list_tables`, `describe_table`, `health_check` | Database introspection and connectivity |
| **Query** | `query`, `query_paginated` | Parameterized T-SQL SELECT queries |
| **CRUD** | `insert_record`, `update_record`, `upsert_record`, `delete_record`, `bulk_insert`, `execute_sql`, `export_data` | Data manipulation with safety guards |
| **Auth** | `get_current_user`, `update_current_user`, `admin_list_users`, `admin_create_user`, `admin_update_user`, `admin_delete_user`, `list_roles`, `create_role`, `update_role`, `delete_role`, `set_user_roles` | User & role management |
| **Storage** | `list_files`, `get_file_info`, `update_file_metadata`, `delete_file` | File storage management |
| **Knowledge** | `ask_knowledge_base`, `kb_document_status`, `kb_retry_document`, `kb_update_metadata`, `kb_delete_metadata` | RAG-powered Q&A |
| **Functions** | `invoke_function`, `function_health`, `list_functions`, `deploy_function`, `get_function`, `delete_function`, `list_function_versions`, `rollback_function` | Deno edge functions |
| **Secrets** | `list_secrets`, `get_secret`, `create_secret`, `update_secret`, `delete_secret` | AES-encrypted secret management |

**Total: 42 tools**

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/your-org/supaproxy-mcp-server.git
cd supaproxy-mcp-server

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your SupaProxy URL and API key
```

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPAPROXY_BASE_URL` | SupaProxy API base URL | `https://localhost:7001` |
| `SUPAPROXY_API_KEY` | Default API key (stdio mode) | *(empty)* |
| `SUPAPROXY_CONNECTION_NAME` | Default SQL Server connection name | `DefaultConnection` |

### 3. Run

```bash
# stdio transport (default — Claude Desktop / Claude Code)
supaproxy-mcp

# SSE + Streamable HTTP transport (web clients)
supaproxy-mcp --transport sse
supaproxy-mcp --transport sse --host 127.0.0.1 --port 9001

supaproxy-mcp --transport sse --host 127.0.0.1 --port 9001 2>&1 | Select-String "PERF" #PERF logs filter
supaproxy-mcp --transport sse --host 127.0.0.1 --port 9001 2>&1 | grep PERF #PERF logs filter

# Health Check
http://127.0.0.1:9001/health
```


## Architecture

```
┌──────────────────────────────────────────────────┐
│           Claude (Desktop / Web / IDE)            │
└───────────────────────┬──────────────────────────┘
                        │
             STDIO / SSE / HTTP
          (forwards x-api-key, JWT,
           x-connection-name headers)
                        │
┌───────────────────────▼──────────────────────────┐
│          supaproxy-mcp-server (Python)            │
│          FastMCP + Uvicorn                        │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │ 8 Tool Modules (42 tools)                   │  │
│  │  schema · query · crud · auth               │  │
│  │  storage · knowledge · functions · secrets   │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │ SupaProxyClient (httpx)                     │  │
│  │  · Forwards x-api-key, JWT, connection name │  │
│  │  · Falls back to .env defaults (stdio)      │  │
│  └─────────────────────────────────────────────┘  │
└───────────────────────┬──────────────────────────┘
                        │
                   HTTP (httpx)
                        │
┌───────────────────────▼──────────────────────────┐
│            SupaProxy (.NET Core)                  │
│  /api/sql-server/* · /auth/* · /api/storage/*     │
│  /functions/v1/*   · /secrets/*                    │
└───────────────────────┬──────────────────────────┘
                        │
                   ADO.NET / EF Core
                        │
┌───────────────────────▼──────────────────────────┐
│             SQL Server (any database)             │
└──────────────────────────────────────────────────┘
```

## Header Forwarding

When running in SSE/HTTP mode, the MCP server transparently forwards three headers from the incoming HTTP request to all SupaProxy API calls:

| Header | Purpose | Fallback (stdio) |
|--------|---------|-------------------|
| `Authorization` | Bearer JWT token for user identity | *(none)* |
| `X-API-KEY` | API key for SupaProxy authentication | `SUPAPROXY_API_KEY` from .env |
| `X-Connection-Name` | SQL Server connection to use | `SUPAPROXY_CONNECTION_NAME` from .env |

This means:
- **SSE/HTTP mode**: The calling application (React, etc.) sends its own credentials, and the MCP server passes them through. User identity (JWT) and database connection are determined by the caller.
- **stdio mode**: Uses the default API key and connection name from `.env`. Useful for Claude Desktop/Code where headers aren't available.

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "supaproxy": {
      "command": "supaproxy-mcp",
      "args": []
    }
  }
}
```

Or with the SSE transport:

```json
{
  "mcpServers": {
    "supaproxy": {
      "url": "http://localhost:8002/sse"
    }
  }
}
```

## How Claude Uses This

When a user asks a business question (e.g., "Quantos clientes ativos existem?"), Claude will:

1. Call `list_tables` to discover available tables
2. Call `describe_table` on relevant tables to understand the schema
3. Formulate and execute a T-SQL query via `query` or `query_paginated`
4. Present the results in a clear, formatted answer

For data modifications, Claude uses the structured CRUD tools (`insert_record`, `update_record`, etc.) which provide built-in safety guards (required WHERE clauses, parameterized queries).

## Development

```bash
# Run directly (without installing)
python -m supaproxy_mcp.server
```


## 🚀 Parte 1: Empacotando (Máquina do Desenvolvedor)

### Passo 1.1: Instalar o PyInstaller

No terminal, com o ambiente virtual (`venv`) ativado, instale o empacotador:

```cmd
cd "C:\DEV\REPS\supaproxy-mcp-server"

.venv\Scripts\activate

pip install pyinstaller
```

### Passo 1.2: O Ponto de Entrada

O arquivo `run_mcp.py` (já presente na raiz do projeto) é o script de entrada do PyInstaller. Ele:

- Chama `multiprocessing.freeze_support()` — obrigatório no Windows com PyInstaller.
- Importa explicitamente todos os módulos de tools e os transportes MCP que o PyInstaller não consegue detectar automaticamente (são carregados de forma dinâmica em runtime).
- Delega a execução para `supaproxy_mcp.server.main()`, que já lida com os argumentos `--transport`, `--host` e `--port`.

Você não precisa criar este arquivo — ele já existe no projeto.

### Passo 1.3: Realizando o Build

No terminal (raiz do projeto, com venv ativado), execute o comando:

```cmd
pyinstaller --name "SupaProxyMCP" --onedir --clean run_mcp.py
```

> **Por que sem `--hidden-import`?** O `run_mcp.py` já importa estaticamente todos os módulos que o PyInstaller não conseguiria detectar sozinho (transportes MCP, tools, pydantic_settings). Com os imports explícitos no entry point, os flags `--hidden-import` se tornam redundantes.

> **`--onedir`** gera uma pasta `dist\SupaProxyMCP\` com o executável e uma subpasta `_internal\` contendo o runtime Python e todas as bibliotecas. Esta é a abordagem preferida (mais fácil de depurar que `--onefile`).

> **(⚠️ ModuleNotFoundError ao iniciar o `.exe`?)** Se ocorrer, adicione o import do módulo diretamente em `run_mcp.py` (ex: `import nome_do_modulo  # noqa: F401`) e recompile. Não é necessário usar `--hidden-import`.

Ao terminar a compilação, a pasta `dist\SupaProxyMCP\` estará pronta.

### Passo 1.4: Testando o Binário Localmente

Antes de enviar ao servidor, teste o executável na própria máquina de desenvolvimento.

**1. Copie o `.env`** para a pasta `dist\SupaProxyMCP\`:
```cmd
copy .env dist\SupaProxyMCP\.env
```

**2. Run**

```bash
cd dist\SupaProxyMCP

# stdio transport (default — Claude Desktop / Claude Code)
.\SupaProxyMCP.exe

# SSE + Streamable HTTP transport (web clients)
.\SupaProxyMCP.exe --transport sse
.\SupaProxyMCP.exe --transport sse --host 127.0.0.1 --port 9001


# Swagger
http://127.0.0.1:9001/docs

```

## Cloudflare - Expose Public HTTP
Cloudflare Tunnel é a solução correta aqui — é gratuito, estável com SSE e sem as limitações do ngrok free:

-Instalar no Powershell:
winget install Cloudflare.cloudflared

-Usar:
cloudflared tunnel --url http://localhost:9001
 Vai aparecer o endereço na áre "Your quick Tunnel has been created!". Acesse o {endereço}/docs:  
  {endereço}/docs


## License

MIT
