"""Encrypted secrets management tools for SupaProxy."""

import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register secrets management tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_secrets() -> str:
        """List all secrets stored in SupaProxy (admin only).

        Returns secret names only — values are encrypted at rest and
        returned only when requested individually via `get_secret`.

        Returns:
            JSON object with a list of secret entries.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] list_secrets")
            result = await client.get("/secrets", include_connection=False)
            count = len(result) if isinstance(result, list) else "?"
            logger.info("[PERF <<<] list_secrets: %dms | count=%s", int((time.perf_counter() - t0) * 1000), count)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] list_secrets: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] list_secrets: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in list_secrets")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def get_secret(name: str) -> str:
        """Retrieve the decrypted value of a specific secret.

        Args:
            name: The name of the secret to retrieve.

        Returns:
            JSON object with the secret's name and decrypted value.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] get_secret: name=%s", name)
            result = await client.get(f"/secrets/{name}", include_connection=False)
            logger.info("[PERF <<<] get_secret: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] get_secret: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] get_secret: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in get_secret")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def create_secret(name: str, value: str) -> str:
        """Create a new encrypted secret (admin only).

        The value is encrypted with AES before being stored in the database.

        Args:
            name: Unique name for the secret (e.g. "STRIPE_API_KEY").
            value: The secret value to store (will be encrypted at rest).

        Returns:
            JSON object confirming creation, or an error if name already exists.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] create_secret: name=%s", name)
            result = await client.post(
                "/secrets",
                json={"name": name, "value": value},
                include_connection=False,
            )
            logger.info("[PERF <<<] create_secret: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] create_secret: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] create_secret: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in create_secret")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def update_secret(name: str, value: str) -> str:
        """Update the value of an existing secret (admin only).

        Args:
            name: The name of the secret to update.
            value: The new value (will be re-encrypted).

        Returns:
            JSON object confirming update, or an error message.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] update_secret: name=%s", name)
            result = await client.put(
                f"/secrets/{name}",
                json={"value": value},
                include_connection=False,
            )
            logger.info("[PERF <<<] update_secret: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] update_secret: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] update_secret: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in update_secret")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def delete_secret(name: str) -> str:
        """Delete a secret permanently (admin only).

        Args:
            name: The name of the secret to delete.

        Returns:
            JSON confirmation, or an error message.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] delete_secret: name=%s", name)
            result = await client.delete(f"/secrets/{name}", include_connection=False)
            logger.info("[PERF <<<] delete_secret: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] delete_secret: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] delete_secret: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in delete_secret")
            return f"Unexpected error: {exc}"
