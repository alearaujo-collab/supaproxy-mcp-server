"""SQL query tools for SupaProxy SQL Server databases."""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register SQL query tools on the given FastMCP instance."""

    @mcp.tool()
    async def query(
        sql: str,
        parameters: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """Execute a SELECT query against the SQL Server database.

        Use this tool for reading data.  The query is executed with parameter
        binding to prevent SQL injection.

        IMPORTANT:
        - Use @ParamName syntax for parameters (e.g. "WHERE id = @Id").
        - Pass parameter values in the `parameters` dict (e.g. {"Id": 42}).
        - This tool is for SELECT queries only.  For INSERT/UPDATE/DELETE,
          use `execute_sql` or the structured CRUD tools.

        Args:
            sql: The T-SQL SELECT query to execute.
                 Example: "SELECT TOP 10 * FROM dbo.Customers WHERE City = @City"
            parameters: Optional dictionary of parameter name-value pairs.
                        Each key should match a @param in the SQL.
                        Example: {"City": "São Paulo"}
                        For typed parameters, use {"Type": "int", "Value": 42}.
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with:
            - success: boolean
            - data: array of row objects
            - rowCount: number of rows returned
            - executionTime: query time in ms
            - columns: array of {name, type} for each column
        """
        try:
            body: dict = {"sql": sql}
            if parameters:
                body["parameters"] = parameters
            if timeout is not None:
                body["timeout"] = timeout
            result = await client.post("/api/sql-server/query", json=body)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in query")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def query_paginated(
        sql: str,
        page: int = 1,
        page_size: int = 50,
        params: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """Execute a paginated SELECT query against the SQL Server database.

        Automatically handles COUNT and OFFSET/FETCH pagination.  The query
        should include an ORDER BY clause (one will be added automatically
        if missing).

        IMPORTANT:
        - Use @ParamName syntax for parameters.
        - Maximum page_size is 1000.
        - The count query is derived automatically from your SQL.

        Args:
            sql: The T-SQL SELECT query to paginate.  Should include ORDER BY.
                 Example: "SELECT * FROM dbo.Orders WHERE Status = @Status ORDER BY CreatedAt DESC"
            page: Page number (1-based, default 1).
            page_size: Number of records per page (default 50, max 1000).
            params: Optional dictionary of parameter name-value pairs.
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with:
            - success: boolean
            - data: array of row objects for the requested page
            - pagination: {page, pageSize, totalRecords, totalPages, hasNextPage, hasPreviousPage}
            - executionTime: query time in ms
        """
        try:
            body: dict = {
                "sql": sql,
                "pagination": {"page": page, "pageSize": page_size},
            }
            if params:
                body["params"] = params
            if timeout is not None:
                body["timeout"] = timeout
            result = await client.post("/api/sql-server/query/paginated", json=body)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in query_paginated")
            return f"Unexpected error: {exc}"
