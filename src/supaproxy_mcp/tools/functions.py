"""Edge function tools for SupaProxy (Deno runtime)."""

import json
import logging
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
            result = await client.post(
                f"/functions/v1/{name}",
                json=body or {},
                include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
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
            result = await client.get(
                f"/functions/v1/{name}/health", include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in function_health")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def list_functions() -> str:
        """List all deployed edge functions.

        Returns:
            JSON object with a list of edge functions (name, status, version, code).
        """
        try:
            result = await client.get("/admin/functions", include_connection=False)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
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
            result = await client.post(
                "/admin/functions/deploy", json=body, include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
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
            result = await client.get(
                f"/admin/functions/{name}", include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
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
            result = await client.delete(
                f"/admin/functions/{name}", include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
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
            result = await client.get(
                f"/admin/functions/{name}/versions", include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
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
            result = await client.post(
                f"/admin/functions/{name}/rollback",
                json={"version": version},
                include_connection=False,
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in rollback_function")
            return f"Unexpected error: {exc}"
