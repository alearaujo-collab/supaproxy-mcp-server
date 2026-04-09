"""
Swagger UI docs — endpoints /docs e /openapi.json.

Gerado manualmente (sem FastAPI) para o Starlette app do FastMCP.
Documenta os endpoints HTTP públicos: /health, /ai/health e /ai/chat.
"""

import json

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

# ---------------------------------------------------------------------------
# OpenAPI 3.1 schema (estático)
# ---------------------------------------------------------------------------

_OPENAPI_SCHEMA: dict = {
    "openapi": "3.1.0",
    "info": {
        "title": "SupaProxy MCP Server",
        "version": "0.1.0",
        "description": (
            "MCP Server para interagir com o **SupaProxy** — proxy compatível com "
            "Supabase que usa SQL Server como banco de dados.\n\n"
            "O endpoint `/ai/chat` executa um loop agêntico com Claude + as tools "
            "registradas no MCP server, chamadas diretamente no mesmo processo "
            "(sem round-trip HTTP extra)."
        ),
    },
    "tags": [
        {"name": "System", "description": "Health checks do servidor"},
        {
            "name": "AI",
            "description": (
                "Endpoint agêntico. Requer três headers: "
                "`Authorization`, `x-api-key` e `x-connection-name`."
            ),
        },
    ],
    "paths": {
        "/health": {
            "get": {
                "tags": ["System"],
                "summary": "Server health check",
                "operationId": "health",
                "responses": {
                    "200": {
                        "description": "Servidor em execução",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"},
                                        "server": {
                                            "type": "string",
                                            "example": "SupaProxy MCP Server",
                                        },
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/ai/health": {
            "get": {
                "tags": ["AI"],
                "summary": "AI endpoint health check",
                "operationId": "ai_health",
                "responses": {
                    "200": {
                        "description": "Status do endpoint /ai/chat",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"},
                                        "model": {
                                            "type": "string",
                                            "example": "claude-sonnet-4-6",
                                        },
                                        "tools_count": {
                                            "type": "integer",
                                            "example": 45,
                                        },
                                        "anthropic_configured": {"type": "boolean"},
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/ai/chat": {
            "post": {
                "tags": ["AI"],
                "summary": "Agentic AI chat",
                "operationId": "ai_chat",
                "description": (
                    "Executa um loop agêntico: Claude chama as tools do MCP server "
                    "diretamente até formular a resposta final.\n\n"
                    "**Headers obrigatórios:**\n"
                    "- `Authorization: Bearer <jwt>` — token JWT do usuário\n"
                    "- `x-api-key: <key>` — API key do SupaProxy\n"
                    "- `x-connection-name: <name>` — nome da conexão/tenant\n\n"
                    "**Máximo de iterações:** configurável via `AI_MAX_TOOL_ITERATIONS` (padrão 10)."
                ),
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "x-api-key",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "API key do SupaProxy.",
                    },
                    {
                        "name": "x-connection-name",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Nome da conexão configurada no SupaProxy.",
                        "example": "DefaultConnection",
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ChatRequest"},
                            "examples": {
                                "sem_histórico": {
                                    "summary": "Primeira mensagem",
                                    "value": {
                                        "message": "Quem sou eu?",
                                        "conversation_history": [],
                                    },
                                },
                                "com_histórico": {
                                    "summary": "Continuação de conversa",
                                    "value": {
                                        "message": "E minhas tarefas em andamento?",
                                        "conversation_history": [
                                            {"role": "user", "content": "Quem sou eu?"},
                                            {
                                                "role": "assistant",
                                                "content": "Você é João Silva, desenvolvedor sênior.",
                                            },
                                        ],
                                    },
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Resposta final do assistente",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChatResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "JSON inválido no body",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                            }
                        },
                    },
                    "401": {
                        "description": "Header obrigatório ausente ou token vazio",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorDetail"},
                                "examples": {
                                    "sem_token": {
                                        "value": {
                                            "detail": "Authorization: Bearer <token> is required."
                                        }
                                    },
                                    "sem_api_key": {
                                        "value": {"detail": "x-api-key header is required."}
                                    },
                                    "sem_connection": {
                                        "value": {
                                            "detail": "x-connection-name header is required."
                                        }
                                    },
                                },
                            }
                        },
                    },
                    "502": {
                        "description": "Erro na Anthropic API (após retries esgotados)",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                            }
                        },
                    },
                    "500": {
                        "description": "Erro interno inesperado",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorDetail"}
                            }
                        },
                    },
                },
            }
        },
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Token JWT do usuário autenticado.",
            }
        },
        "schemas": {
            "ConversationMessage": {
                "type": "object",
                "required": ["role", "content"],
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["user", "assistant"],
                        "description": "Papel da mensagem na conversa.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo textual da mensagem.",
                    },
                },
            },
            "ChatRequest": {
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Mensagem atual do usuário.",
                        "example": "Quais são minhas tarefas em andamento?",
                    },
                    "conversation_history": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ConversationMessage"},
                        "description": "Histórico anterior da conversa (opcional).",
                        "default": [],
                    },
                },
            },
            "ChatResponse": {
                "type": "object",
                "properties": {
                    "reply": {
                        "type": "string",
                        "description": "Resposta final do assistente.",
                        "example": "Você tem 3 tarefas em andamento: ...",
                    },
                    "model": {
                        "type": "string",
                        "description": "Modelo Claude utilizado.",
                        "example": "claude-sonnet-4-6",
                    },
                    "stop_reason": {
                        "type": "string",
                        "description": "Motivo de encerramento do loop agêntico.",
                        "example": "end_turn",
                    },
                },
            },
            "ErrorDetail": {
                "type": "object",
                "properties": {
                    "detail": {
                        "type": "string",
                        "description": "Descrição do erro.",
                    }
                },
            },
        }
    },
}

# Serializa uma vez para evitar re-serialização a cada request
_OPENAPI_JSON = json.dumps(_OPENAPI_SCHEMA, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Swagger UI HTML (CDN — sem dependências extras)
# ---------------------------------------------------------------------------

_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SupaProxy MCP Server — API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    body { margin: 0; }
    .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = () => {
      SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: "#swagger-ui",
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        layout: "StandaloneLayout",
        deepLinking: true,
        persistAuthorization: true,
      });
    };
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def openapi_handler(request: Request) -> JSONResponse:
    """GET /openapi.json — retorna o schema OpenAPI 3.1."""
    return JSONResponse(content=_OPENAPI_SCHEMA)


async def docs_handler(request: Request) -> HTMLResponse:
    """GET /docs — serve o Swagger UI via CDN."""
    return HTMLResponse(content=_SWAGGER_HTML)
