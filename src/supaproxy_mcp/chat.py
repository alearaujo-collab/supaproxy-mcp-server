"""
AI Chat endpoint — loop agêntico com chamada direta às tool functions.

Arquitetura:
    POST /ai/chat
        ↓
    Extrai Bearer token, x-api-key, x-connection-name → injeta nos 3 ContextVars
        ↓
    mcp._tool_manager.list_tools() → converte para formato Anthropic
        ↓
    Loop agêntico (máx ai_max_tool_iterations):
        Claude API → tool_use? → mcp._tool_manager.call_tool() → resultado
        │                                     ↑
        └── as tool functions leem os ContextVars via client._headers()
        ↓
    Retorna { reply, model, stop_reason }

Sem protocolo MCP, sem sessão, sem round-trip HTTP — chamada direta às funções.
"""

import asyncio
import json
import logging
import time
from typing import Any

from anthropic import AsyncAnthropic, RateLimitError
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from .header_context import forwarded_api_key, forwarded_connection_name, forwarded_token

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas de request / response
# ---------------------------------------------------------------------------


class ConversationMessage(BaseModel):
    role: str    # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ConversationMessage] = []


class ChatResponse(BaseModel):
    reply: str
    model: str
    stop_reason: str


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _build_tools_for_claude(mcp) -> list[dict]:
    """Lê as tools registradas no FastMCP e converte para o formato Anthropic.

    Aplica cache_control no último tool: a Anthropic faz cache do bloco inteiro
    de tools (TTL 5 min), economizando tokens em iterações subsequentes do loop.
    """
    tools = mcp._tool_manager.list_tools()
    result = []
    for i, t in enumerate(tools):
        tool_def: dict[str, Any] = {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.parameters,
        }
        # Marcar APENAS o último tool — a Anthropic faz cache de tudo até ele.
        if i == len(tools) - 1:
            tool_def["cache_control"] = {"type": "ephemeral"}
        result.append(tool_def)
    return result


async def _call_tool_direct(mcp, name: str, arguments: dict) -> str:
    """Chama uma tool registrada no FastMCP diretamente, sem protocolo MCP.

    Os ContextVars (forwarded_token, forwarded_api_key, forwarded_connection_name)
    DEVEM estar definidos antes desta chamada. As tool functions os leem
    automaticamente através de client._headers().

    Retorna str com o resultado, ou "Tool error: ..." em caso de falha.
    Nunca lança exceção — o loop agêntico sempre continua.
    """
    try:
        result = await mcp._tool_manager.call_tool(name, arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Tool '%s' failed: %s", name, exc)
        return f"Tool error: {exc}"


def _is_retryable_error(exc: Exception) -> bool:
    """Identifica erros da Anthropic que devem ser retentados (429/529)."""
    msg = str(exc).lower()
    return (
        isinstance(exc, RateLimitError)
        or "429" in msg
        or "529" in msg
        or "rate" in msg
        or "overloaded" in msg
    )


def _log_cache_usage(response: Any) -> None:
    """Loga métricas de prompt caching se disponíveis."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    if read or write:
        logger.debug(
            "Prompt cache — read: %d tokens, write: %d tokens (input: %d, output: %d)",
            read, write, usage.input_tokens, usage.output_tokens,
        )


# ---------------------------------------------------------------------------
# Loop agêntico
# ---------------------------------------------------------------------------


async def _run_agentic_loop(
    client: AsyncAnthropic,
    mcp,
    messages: list[dict],
    tools: list[dict],
    settings,
) -> dict:
    """Executa o loop agêntico completo: Claude ↔ tools diretas.

    Retorna dict com { text, model, stop_reason }.
    Lança RuntimeError se o provider falhar após todos os retries.
    """
    t_loop_start = time.perf_counter()
    final: dict = {"text": "", "model": settings.ai_model, "stop_reason": "end_turn"}

    for iteration in range(settings.ai_max_tool_iterations):

        # ── 1. Chamar o LLM ─────────────────────────────────────────────
        t0 = time.perf_counter()
        response = None
        last_exc = None

        for attempt in range(settings.anthropic_max_retries + 1):
            try:
                response = await client.messages.create(
                    model=settings.ai_model,
                    max_tokens=settings.ai_max_tokens,
                    system=[
                        {
                            "type": "text",
                            "text": mcp.instructions or "You are a helpful AI assistant.",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=tools,
                    messages=messages,
                )
                break
            except Exception as exc:
                last_exc = exc
                if _is_retryable_error(exc) and attempt < settings.anthropic_max_retries:
                    delay = 2 ** (attempt + 1)  # 2, 4, 8, 16... segundos
                    logger.warning(
                        "Anthropic retry %d/%d after %ds: %s",
                        attempt + 1, settings.anthropic_max_retries, delay, exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError(f"Anthropic API error: {exc}") from exc

        if response is None:
            raise RuntimeError(f"Anthropic API: all retries exhausted. Last error: {last_exc}")

        llm_ms = (time.perf_counter() - t0) * 1000
        _log_cache_usage(response)

        # ── 2. Extrair texto e tool_use blocks ───────────────────────────
        text = ""
        tool_use_blocks = []

        for block in response.content:
            if hasattr(block, "text") and block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_use_blocks.append(block)

        logger.info(
            "[loop iter=%d] LLM call: %.0f ms | stop_reason=%s | tool_calls=%d",
            iteration + 1, llm_ms, response.stop_reason, len(tool_use_blocks),
        )

        # ── 3. Sem tool calls → resposta final ──────────────────────────
        if not tool_use_blocks:
            logger.info(
                "[loop] finished after %d iteration(s) | total: %.0f ms",
                iteration + 1, (time.perf_counter() - t_loop_start) * 1000,
            )
            return {
                "text": text,
                "model": response.model,
                "stop_reason": response.stop_reason or "end_turn",
            }

        # ── 4. Executar cada tool diretamente ───────────────────────────
        tool_results = []

        for tc in tool_use_blocks:
            t1 = time.perf_counter()
            content = await _call_tool_direct(mcp, tc.name, tc.input or {})
            tool_ms = (time.perf_counter() - t1) * 1000

            logger.info(
                "[loop iter=%d] tool '%s' args=%s: %.0f ms | result_len=%d chars",
                iteration + 1, tc.name,
                json.dumps(tc.input or {}),
                tool_ms, len(content),
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": content,
            })

        # ── 5. Atualizar histórico de mensagens ──────────────────────────
        # ORDEM CRÍTICA:
        #   a) assistant turn com o content block RAW (não texto plano).
        #   b) user turn com os tool_result blocks.
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        final = {"text": text, "model": response.model, "stop_reason": response.stop_reason or ""}

    # ── Limite de iterações atingido ─────────────────────────────────────
    logger.warning(
        "[loop] hit max iterations (%d) | total: %.0f ms",
        settings.ai_max_tool_iterations,
        (time.perf_counter() - t_loop_start) * 1000,
    )
    return final


# ---------------------------------------------------------------------------
# Factory do handler (evita importação circular com server.py)
# ---------------------------------------------------------------------------


def make_chat_handler(mcp, settings):
    """Retorna o handler async do POST /ai/chat com mcp e settings injetados.

    Uso em server.py:
        from .chat import make_chat_handler
        app.routes.append(Route("/ai/chat", make_chat_handler(mcp, settings), methods=["POST"]))
    """
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY não configurado. "
            "Adicione ao .env antes de usar o endpoint /ai/chat."
        )

    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Pré-computa a lista de tools uma vez — é estática após o registro inicial.
    tools = _build_tools_for_claude(mcp)
    logger.info("[chat] pre-built %d tools for Anthropic", len(tools))

    async def handler(request: Request) -> JSONResponse:
        """Handler do POST /ai/chat.

        Headers obrigatórios:
            Authorization: Bearer <jwt_token>
            x-api-key: <chave_da_api>
            x-connection-name: <nome_da_conexao>
        """
        t_request = time.perf_counter()

        # ── 1. Extrair e validar os três headers obrigatórios ────────────
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                {"detail": "Authorization: Bearer <token> is required."},
                status_code=401,
            )
        token = auth_header[7:].strip()
        if not token:
            return JSONResponse({"detail": "Bearer token is empty."}, status_code=401)

        api_key = request.headers.get("x-api-key", "").strip()
        if not api_key:
            return JSONResponse({"detail": "x-api-key header is required."}, status_code=401)

        connection_name = request.headers.get("x-connection-name", "").strip()
        if not connection_name:
            return JSONResponse(
                {"detail": "x-connection-name header is required."}, status_code=401
            )

        # ── 2. Injetar os três valores nos ContextVars ───────────────────
        # ContextVar é async-safe: cada coroutine tem seu próprio ramo de
        # contexto — requests concorrentes nunca interferem.
        tok = forwarded_token.set(token)
        tok_api_key = forwarded_api_key.set(api_key)
        tok_conn = forwarded_connection_name.set(connection_name)

        try:
            # ── 3. Parsear body ──────────────────────────────────────────
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"detail": "Invalid JSON body."}, status_code=400)

            chat_req = ChatRequest.model_validate(body)

            # ── 4. Montar lista inicial de mensagens ─────────────────────
            messages: list[dict] = [
                {"role": m.role, "content": m.content}
                for m in (chat_req.conversation_history or [])
            ]
            messages.append({"role": "user", "content": chat_req.message})

            # ── 5. Executar loop agêntico ────────────────────────────────
            try:
                result = await _run_agentic_loop(
                    anthropic_client, mcp, messages, tools, settings
                )
            except RuntimeError as exc:
                logger.error("LLM provider error: %s", exc)
                return JSONResponse({"detail": str(exc)}, status_code=502)

            logger.info(
                "[chat] request completed in %.0f ms",
                (time.perf_counter() - t_request) * 1000,
            )

            return JSONResponse(
                ChatResponse(
                    reply=result["text"],
                    model=result["model"],
                    stop_reason=result["stop_reason"],
                ).model_dump()
            )

        except Exception as exc:
            logger.exception("Unexpected error in /ai/chat: %s", exc)
            return JSONResponse({"detail": f"Internal error: {exc}"}, status_code=500)

        finally:
            # SEMPRE resetar os três ContextVars — mesmo em caso de erro.
            forwarded_token.reset(tok)
            forwarded_api_key.reset(tok_api_key)
            forwarded_connection_name.reset(tok_conn)

    return handler


def make_health_handler(mcp, settings):
    """Handler do GET /ai/health — verifica configuração do endpoint."""

    async def handler(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "model": settings.ai_model,
            "tools_count": len(mcp._tool_manager.list_tools()),
            "anthropic_configured": bool(settings.anthropic_api_key),
        })

    return handler
