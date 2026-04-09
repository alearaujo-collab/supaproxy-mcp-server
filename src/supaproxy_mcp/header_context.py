"""Per-request context variables for forwarded HTTP headers.

When the MCP server is called via /mcp (Streamable HTTP), the incoming
request headers are extracted by _ForwardedHeadersMiddleware (server.py)
and stored here.  SupaProxyClient reads them in _headers() so the
SupaProxy backend receives the original caller's credentials and
connection context.

Three headers are forwarded:
  - Authorization (Bearer JWT) → forwarded_token
  - X-API-KEY               → forwarded_api_key
  - X-Connection-Name       → forwarded_connection_name
"""

from contextvars import ContextVar

forwarded_token: ContextVar[str | None] = ContextVar("forwarded_token", default=None)
forwarded_api_key: ContextVar[str | None] = ContextVar("forwarded_api_key", default=None)
forwarded_connection_name: ContextVar[str | None] = ContextVar("forwarded_connection_name", default=None)
