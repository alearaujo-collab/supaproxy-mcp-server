"""SupaProxy MCP Server — entry point."""

import argparse
import logging

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .chat import make_chat_handler, make_health_handler
from .docs import docs_handler, openapi_handler
from .client import SupaProxyClient
from .config import Settings
from .header_context import forwarded_api_key, forwarded_connection_name, forwarded_token
from .tools import auth, crud, functions, knowledge, query, schema, secrets, storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Silence verbose MCP internals — only show WARNING and above from the MCP library
logging.getLogger("mcp.server.lowlevel.server").setLevel(logging.WARNING)
logging.getLogger("mcp.server.streamable_http").setLevel(logging.WARNING)

# Suppress httpx SSL warnings for self-signed certificates during dev
logging.getLogger("httpx").setLevel(logging.WARNING)


class _ForwardedHeadersMiddleware:
    """Pure-ASGI middleware that extracts authentication and context headers
    from requests to /mcp and stores them in ContextVars for the duration
    of the request.

    Forwarded headers:
      - Authorization (Bearer JWT) → forwarded_token
      - X-API-KEY                  → forwarded_api_key
      - X-Connection-Name          → forwarded_connection_name

    Only active on /mcp (Streamable HTTP); /sse requests are untouched
    and continue to use .env-based defaults.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http" and scope.get("path", "").startswith("/mcp"):
            raw_headers = dict(scope.get("headers", []))
            tokens = []

            # Extract Authorization header
            auth_bytes = raw_headers.get(b"authorization", b"")
            auth_val = auth_bytes.decode("utf-8", errors="ignore")
            if auth_val.lower().startswith("bearer "):
                token = auth_val[7:].strip()
                tokens.append(forwarded_token.set(token))

            # Extract X-API-KEY header
            api_key_bytes = raw_headers.get(b"x-api-key", b"")
            api_key_val = api_key_bytes.decode("utf-8", errors="ignore").strip()
            if api_key_val:
                tokens.append(forwarded_api_key.set(api_key_val))

            # Extract X-Connection-Name header
            conn_bytes = raw_headers.get(b"x-connection-name", b"")
            conn_val = conn_bytes.decode("utf-8", errors="ignore").strip()
            if conn_val:
                tokens.append(forwarded_connection_name.set(conn_val))

            if tokens:
                try:
                    await self.app(scope, receive, send)
                finally:
                    for tok in tokens:
                        # Reset each ContextVar using its own token
                        tok.var.reset(tok)
                return

        await self.app(scope, receive, send)


class _SuppressWinError10054(logging.Filter):
    """Suppress the spurious WinError 10054 asyncio noise on Windows.

    Occurs when the HTTP client closes the connection after receiving the
    response — expected behaviour for short-lived Streamable HTTP requests.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if "_ProactorBasePipeTransport._call_connection_lost" in record.getMessage():
            return False
        if record.exc_info:
            exc = record.exc_info[1]
            if isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", None) == 10054:
                return False
        return True


logging.getLogger("asyncio").addFilter(_SuppressWinError10054())

# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------

settings = Settings()
client = SupaProxyClient(settings)

mcp = FastMCP(
    "SupaProxy",
    instructions=(
        "MCP Server para interagir com o SupaProxy — proxy compatível com "
        "Supabase que usa SQL Server como banco de dados.\n"
        "Permite executar consultas SQL (T-SQL), operações CRUD, "
        "introspecção de schema, gerenciar autenticação de usuários, "
        "armazenamento de arquivos, base de conhecimento (RAG), "
        "edge functions e secrets.\n"
        "\n"
        "## Estratégia de consulta\n"
        "Quando o usuário fizer uma pergunta sobre os dados (ex: 'quantos "
        "clientes ativos existem?', 'qual o faturamento do mês?'), siga:\n"
        "1. Chame `list_tables` para descobrir as tabelas disponíveis.\n"
        "2. Chame `describe_table` nas tabelas relevantes para entender "
        "colunas, tipos e relacionamentos (FKs).\n"
        "3. Formule a query T-SQL apropriada e execute com `query` ou "
        "`query_paginated`.\n"
        "4. Apresente os resultados de forma clara ao usuário.\n"
        "\n"
        "## Regras de segurança\n"
        "- NUNCA execute DROP, TRUNCATE ou ALTER via `execute_sql`. "
        "Essa tool é para INSERT/UPDATE/DELETE apenas.\n"
        "- SEMPRE use parâmetros (@param) em vez de concatenar valores "
        "nas queries para evitar SQL injection.\n"
        "- Para DELETE e UPDATE, o SupaProxy exige uma cláusula WHERE "
        "obrigatória — nunca tente operações em massa sem filtro.\n"
        "\n"
        "## Identificação do usuário atual\n"
        "A identidade do usuário é extraída automaticamente do token JWT "
        "enviado na requisição — não é necessário login adicional.\n"
        "Sempre que o usuário se referir a si mesmo ('quem sou eu', "
        "'meu perfil', etc.), chame `get_current_user` primeiro.\n"
        "NUNCA peça ao usuário seu ID, e-mail ou senha.\n"
        "Se `get_current_user` retornar erro de autenticação, informe o "
        "usuário que a sessão expirou e ele deve recarregar a aplicação.\n"
    ),
)

# ---------------------------------------------------------------------------
# Register all tool modules
# ---------------------------------------------------------------------------

schema.register(mcp, client)
query.register(mcp, client)
crud.register(mcp, client)
auth.register(mcp, client)
storage.register(mcp, client)
knowledge.register(mcp, client)
functions.register(mcp, client)
secrets.register(mcp, client)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio or SSE.

    Usage:
        supaproxy-mcp                        # stdio (default — Claude Desktop/Code)
        supaproxy-mcp --transport sse        # SSE on 0.0.0.0:8002
        supaproxy-mcp --transport sse --host 127.0.0.1 --port 9000
    """
    parser = argparse.ArgumentParser(description="SupaProxy MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind when using SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port to bind when using SSE transport (default: 8002)",
    )
    args = parser.parse_args()

    logger.info(
        "Starting SupaProxy MCP Server — transport: %s | base URL: %s",
        args.transport,
        settings.supaproxy_base_url,
    )

    if args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        logger.info("SSE endpoint available at http://%s:%d/sse", args.host, args.port)
        logger.info("Streamable HTTP endpoint available at http://%s:%d/mcp", args.host, args.port)

        async def health(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok", "server": "SupaProxy MCP Server"})

        # Use streamable_http_app as the base (preserves its lifespan/session_manager)
        # and inject SSE routes + health into it so both transports run in one process.
        sse_app = mcp.sse_app()
        app = mcp.streamable_http_app()

        for route in sse_app.routes:  # adds /sse and /messages
            app.routes.append(route)
        app.routes.append(Route("/health", health, methods=["GET"]))
        app.routes.append(Route("/openapi.json", openapi_handler, methods=["GET"]))
        app.routes.append(Route("/docs", docs_handler, methods=["GET"]))
        try:
            app.routes.append(
                Route("/ai/chat", make_chat_handler(mcp, settings), methods=["POST"])
            )
            app.routes.append(
                Route("/ai/health", make_health_handler(mcp, settings), methods=["GET"])
            )
            logger.info("AI Chat endpoint enabled at /ai/chat (model: %s)", settings.ai_model)
        except ValueError as exc:
            logger.warning("AI Chat endpoint disabled: %s", exc)

        app.add_middleware(_ForwardedHeadersMiddleware)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        uvicorn.run(app, host=args.host, port=args.port, timeout_graceful_shutdown=3)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
