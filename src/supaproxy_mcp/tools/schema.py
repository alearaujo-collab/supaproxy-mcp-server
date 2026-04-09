"""Schema introspection tools for SupaProxy SQL Server databases."""

import json
import logging

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register schema introspection tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_tables() -> str:
        """List all tables and views in the connected SQL Server database.

        Returns schema, name, type (USER_TABLE or VIEW), creation date, and
        approximate row count for each object.

        This is typically the FIRST tool you should call when exploring a
        database you haven't seen before.  Use the results to decide which
        tables to inspect with `describe_table`.

        Returns:
            JSON object with a list of tables/views, or an error message.
        """
        try:
            result = await client.get("/api/sql-server/schema/tables")
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in list_tables")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def describe_table(table: str, column_name: str | None = None) -> str:
        """Describe the columns of a table or view, including types, PKs, FKs, and constraints.

        Use this tool to understand the structure of a specific table before
        writing queries.  The results include:
        - Column name, ordinal position, data type
        - Max length, precision, scale
        - Whether the column is nullable, a primary key, a foreign key
        - Whether it's an identity or computed column
        - Default value and extended property descriptions

        Supports "schema.table" notation (e.g. "dbo.Customers").

        Args:
            table: Table or view name to describe.  Supports "schema.table"
                   format (e.g. "dbo.Orders").  If schema is omitted, all
                   schemas are searched.
            column_name: Optional column name to filter.  If provided, only
                         that column's metadata is returned.

        Returns:
            JSON object with column metadata, or an error message.
        """
        try:
            params: dict = {"table": table}
            if column_name:
                params["columnName"] = column_name
            result = await client.get("/api/sql-server/schema/columns", params=params)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in describe_table")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def health_check() -> str:
        """Check database connectivity and retrieve server information.

        Returns the database name, server address, SQL Server version, and
        connection status.  Useful for verifying that the SupaProxy is
        reachable and the SQL Server connection is healthy.

        Returns:
            JSON object with health status, or an error message.
        """
        try:
            result = await client.get("/api/sql-server/health")
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.exception("Unexpected error in health_check")
            return f"Unexpected error: {exc}"
