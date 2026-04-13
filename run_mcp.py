"""
Entry point explícito para empacotamento com PyInstaller.

Este script garante que o PyInstaller consiga enxergar e empacotar
todos os módulos necessários do servidor MCP.

Uso (após compilação):
    SupaProxyMCP.exe                        # stdio — Claude Desktop / Claude Code
    SupaProxyMCP.exe --transport sse        # SSE / HTTP em 0.0.0.0:8002
    SupaProxyMCP.exe --transport sse --host 127.0.0.1 --port 9000
"""

import multiprocessing
import sys

# --- Importações explícitas: ensinam o PyInstaller a empacotar estes módulos ---

# Pacote principal e todos os módulos de tools
import supaproxy_mcp.server                  # noqa: F401
import supaproxy_mcp.tools.auth              # noqa: F401
import supaproxy_mcp.tools.crud              # noqa: F401
import supaproxy_mcp.tools.functions         # noqa: F401
import supaproxy_mcp.tools.knowledge         # noqa: F401
import supaproxy_mcp.tools.navigation        # noqa: F401
import supaproxy_mcp.tools.query             # noqa: F401
import supaproxy_mcp.tools.schema            # noqa: F401
import supaproxy_mcp.tools.secrets           # noqa: F401
import supaproxy_mcp.tools.storage           # noqa: F401

# MCP transports (carregados dinamicamente — invisíveis ao PyInstaller)
import mcp.server.stdio                      # noqa: F401
import mcp.server.sse                        # noqa: F401
import mcp.server.streamable_http            # noqa: F401

from supaproxy_mcp.server import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # Necessário para PyInstaller no Windows
    main()
