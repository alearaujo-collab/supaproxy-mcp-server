"""Edge function tools for SupaProxy (Deno runtime)."""

import json
import logging
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register edge function tools on the given FastMCP instance."""

    @mcp.tool()
    async def invoke_function(name: str, body: Optional[dict] = None) -> str:
        """Invoke a deployed edge function by name.

        Edge functions run in a Deno runtime and can contain arbitrary
        JavaScript/TypeScript logic.

        Args:
            name: The name of the function to invoke.
            body: Optional JSON payload to send to the function.

        Returns:
            The function's JSON response, or stdout/stderr if not JSON.
            Returns HTTP 504 if the function times out (30s limit).
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] invoke_function: name=%s", name)
            result = await client.post(
                f"/functions/v1/{name}",
                json=body or {},
                include_connection=False,
            )
            logger.info("[PERF <<<] invoke_function: %dms | name=%s", int((time.perf_counter() - t0) * 1000), name)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] invoke_function: HTTP %d apos %dms | name=%s", exc.response.status_code, int((time.perf_counter() - t0) * 1000), name)
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] invoke_function: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in invoke_function")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def function_health(name: str) -> str:
        """Check the health/status of a deployed edge function.

        Args:
            name: The name of the function.

        Returns:
            JSON object with name, status (active/inactive/deleted), and version.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] function_health: name=%s", name)
            result = await client.get(
                f"/functions/v1/{name}/health", include_connection=False,
            )
            logger.info("[PERF <<<] function_health: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] function_health: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] function_health: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in function_health")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def list_functions() -> str:
        """List all deployed edge functions.

        Returns:
            JSON object with a list of edge functions (name, status, version, code).
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] list_functions")
            result = await client.get("/admin/functions", include_connection=False)
            count = len(result) if isinstance(result, list) else "?"
            logger.info("[PERF <<<] list_functions: %dms | count=%s", int((time.perf_counter() - t0) * 1000), count)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] list_functions: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] list_functions: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in list_functions")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def deploy_function(
        name: str,
        code: str,
        config: Optional[dict] = None,
    ) -> str:
        """Deploy a new edge function or update an existing one.

        If a function with the same name already exists, it is updated
        to a new version.

        Args:
            name: Function name (used as the endpoint: /functions/v1/{name}).
            code: The JavaScript/TypeScript source code for the function.
                  Example: 'export default (req) => { return new Response("ok"); }'
            config: Optional configuration object.
                    Can include import_map for dependency resolution.

        Returns:
            JSON object with function details (name, status, version,
            deployed_at, endpoint).
        """
        try:
            body: dict = {"name": name, "code": code}
            if config is not None:
                body["config"] = config
            t0 = time.perf_counter()
            logger.info("[PERF >>>] deploy_function: name=%s, code_len=%d", name, len(code))
            result = await client.post(
                "/admin/functions/deploy", json=body, include_connection=False,
            )
            version = result.get("version", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] deploy_function: %dms | version=%s", int((time.perf_counter() - t0) * 1000), version)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] deploy_function: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] deploy_function: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in deploy_function")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def get_function(name: str) -> str:
        """Get details of a specific edge function including its code.

        Args:
            name: The name of the function.

        Returns:
            JSON object with full function details (id, name, code, version, etc.).
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] get_function: name=%s", name)
            result = await client.get(
                f"/admin/functions/{name}", include_connection=False,
            )
            logger.info("[PERF <<<] get_function: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] get_function: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] get_function: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in get_function")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def delete_function(name: str) -> str:
        """Delete (soft-delete) an edge function.

        Sets the function status to "deleted" so it can no longer be invoked.

        Args:
            name: The name of the function to delete.

        Returns:
            JSON confirmation, or an error message.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] delete_function: name=%s", name)
            result = await client.delete(
                f"/admin/functions/{name}", include_connection=False,
            )
            logger.info("[PERF <<<] delete_function: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] delete_function: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] delete_function: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in delete_function")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def list_function_versions(name: str) -> str:
        """List all deployed versions of an edge function.

        Args:
            name: The name of the function.

        Returns:
            JSON object with version history (version number, code, created_at, etc.).
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] list_function_versions: name=%s", name)
            result = await client.get(
                f"/admin/functions/{name}/versions", include_connection=False,
            )
            count = len(result) if isinstance(result, list) else "?"
            logger.info("[PERF <<<] list_function_versions: %dms | versions=%s", int((time.perf_counter() - t0) * 1000), count)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] list_function_versions: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] list_function_versions: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in list_function_versions")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def rollback_function(name: str, version: int) -> str:
        """Rollback an edge function to a previous version.

        Creates a new deployment version with the code from the specified
        historical version.

        Args:
            name: The name of the function.
            version: The version number to rollback to.

        Returns:
            JSON object with the new version number, or an error message.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] rollback_function: name=%s, version=%d", name, version)
            result = await client.post(
                f"/admin/functions/{name}/rollback",
                json={"version": version},
                include_connection=False,
            )
            logger.info("[PERF <<<] rollback_function: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] rollback_function: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] rollback_function: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in rollback_function")
            return f"Unexpected error: {exc}"
