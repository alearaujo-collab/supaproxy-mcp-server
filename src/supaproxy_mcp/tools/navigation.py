"""Navigation deep-link tools for SupaProxy MCP Server.

Allows the AI to discover which pages/forms exist in the calling
React application so it can embed clickable navigation links in
its responses.

Each application database must contain a table ``dbo.AppNavigation``
with the following schema:

    CREATE TABLE dbo.AppNavigation (
        Id          INT IDENTITY PRIMARY KEY,
        Entity      NVARCHAR(100) NOT NULL,   -- e.g. "cliente", "pedido"
        Action      NVARCHAR(50)  NOT NULL,   -- "list", "detail", "create", "edit"
        Route       NVARCHAR(500) NOT NULL,   -- "/clientes", "/clientes/{id}"
        Label       NVARCHAR(200) NOT NULL,   -- "Ver clientes"
        Description NVARCHAR(500) NULL        -- When to suggest this link
    );

The tool reads from this table via the existing SupaProxy query
endpoint, inheriting the caller's connection automatically.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register navigation deep-link tools on the given FastMCP instance."""

    @mcp.tool()
    async def get_app_routes(
        entity: Optional[str] = None,
        action: Optional[str] = None,
    ) -> str:
        """Retrieve navigation routes available in the calling application.

        Each React application that connects to this MCP has its own
        ``dbo.AppNavigation`` table listing the pages and forms it
        supports.  Call this tool to discover which links you can embed
        in your answer so the user can navigate directly to the
        relevant page.

        **When to call this tool:**
        - Your answer mentions a specific entity (e.g. clients,
          orders, products) and the user might want to open that page.
        - The user explicitly asks for a link or to "go to" something.
        - You are about to suggest an action (create, edit, view)
          that could correspond to a page in the application.

        **How to use the results:**
        Include links in the response using the format
        ``[[nav:<route>|<label>]]``.  Replace ``{id}`` or similar
        placeholders with actual values when available.
        Example: ``[[nav:/clientes/42|Ver cliente Maria]]``

        Args:
            entity: Optional filter by entity name (case-insensitive).
                    Example: "cliente", "pedido", "produto".
                    When omitted, all routes are returned.
            action: Optional filter by action type (case-insensitive).
                    Example: "list", "detail", "create", "edit".
                    When omitted, all actions are returned.

        Returns:
            JSON array of route objects with Entity, Action, Route,
            Label, and Description.  Returns an empty array if the
            table does not exist or has no matching rows.
        """
        try:
            # Build a filtered SELECT against AppNavigation.
            conditions = []
            parameters: dict = {}

            if entity:
                conditions.append("LOWER(Entity) = LOWER(@Entity)")
                parameters["Entity"] = entity
            if action:
                conditions.append("LOWER(Action) = LOWER(@Action)")
                parameters["Action"] = action

            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            sql = (
                "SELECT Entity, Action, Route, Label, Description "
                f"FROM dbo.AppNavigation{where} "
                "ORDER BY Entity, Action"
            )

            body: dict = {"sql": sql}
            if parameters:
                body["parameters"] = parameters

            result = await client.post("/api/sql-server/query", json=body)

            # Normalise: return just the data rows for the LLM.
            if isinstance(result, dict) and "data" in result:
                return json.dumps(result["data"], indent=2, ensure_ascii=False)
            return json.dumps(result, indent=2, ensure_ascii=False)

        except httpx.HTTPStatusError as exc:
            # Table might not exist — return empty list gracefully.
            if exc.response.status_code in (400, 404):
                logger.info(
                    "AppNavigation table not available (HTTP %d) — "
                    "returning empty routes.",
                    exc.response.status_code,
                )
                return "[]"
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in get_app_routes")
            return f"Unexpected error: {exc}"
