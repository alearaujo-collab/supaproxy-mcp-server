"""Async HTTP client for the SupaProxy REST API with header forwarding."""

import logging
import time
from typing import Any

import httpx

from .config import Settings
from .header_context import forwarded_api_key, forwarded_connection_name, forwarded_token

logger = logging.getLogger(__name__)


class SupaProxyClient:
    """Async HTTP client that forwards authentication headers to SupaProxy.

    When used via SSE/HTTP transport, the caller's headers (X-API-KEY,
    Authorization, X-Connection-Name) are forwarded transparently.
    When used via stdio, fallback values from the .env configuration are used.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.supaproxy_base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=60.0, verify=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        """Build full URL from a relative path."""
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    def _headers(self, *, include_connection: bool = True) -> dict[str, str]:
        """Build request headers from forwarded context or .env defaults."""
        headers: dict[str, str] = {"Accept": "application/json"}

        # API Key: prefer forwarded, fall back to .env
        api_key = forwarded_api_key.get() or self._settings.supaproxy_api_key
        if api_key:
            headers["X-API-KEY"] = api_key

        # JWT Token: prefer forwarded, no fallback
        token = forwarded_token.get()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Connection Name: prefer forwarded, fall back to .env
        if include_connection:
            conn_name = forwarded_connection_name.get() or self._settings.supaproxy_connection_name
            if conn_name:
                headers["X-Connection-Name"] = conn_name

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        include_connection: bool = True,
    ) -> Any:
        url = self._url(path)
        t0 = time.perf_counter()
        logger.info("[PERF >>>] SupaProxyClient._request: %s %s", method, path)
        try:
            response = await self._http.request(
                method,
                url,
                headers=self._headers(include_connection=include_connection),
                params=params,
                json=json,
                data=data,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.info("[PERF <<<] SupaProxyClient._request: %s %s | %dms | status=%d",
                method, path, elapsed_ms, response.status_code)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            logger.error("[PERF !!!] SupaProxyClient._request: %s %s falha apos %dms — %s",
                method, path, elapsed_ms, exc)
            raise
        response.raise_for_status()
        if response.content:
            return response.json()
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        include_connection: bool = True,
    ) -> Any:
        return await self._request("GET", path, params=params, include_connection=include_connection)

    async def post(
        self,
        path: str,
        json: Any = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        include_connection: bool = True,
    ) -> Any:
        return await self._request(
            "POST", path, json=json, data=data, params=params,
            include_connection=include_connection,
        )

    async def put(
        self,
        path: str,
        json: Any = None,
        *,
        include_connection: bool = True,
    ) -> Any:
        return await self._request("PUT", path, json=json, include_connection=include_connection)

    async def patch(
        self,
        path: str,
        json: Any = None,
        *,
        include_connection: bool = True,
    ) -> Any:
        return await self._request("PATCH", path, json=json, include_connection=include_connection)

    async def delete(
        self,
        path: str,
        json: Any = None,
        *,
        include_connection: bool = True,
    ) -> Any:
        return await self._request("DELETE", path, json=json, include_connection=include_connection)

    async def aclose(self) -> None:
        await self._http.aclose()
