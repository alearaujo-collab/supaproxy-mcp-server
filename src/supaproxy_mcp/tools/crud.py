"""CRUD and data manipulation tools for SupaProxy SQL Server databases."""

import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register CRUD tools on the given FastMCP instance."""

    @mcp.tool()
    async def insert_record(
        table: str,
        data: dict,
        return_identity: bool = False,
        timeout: Optional[int] = None,
    ) -> str:
        """Insert a single record into a SQL Server table.

        The SupaProxy builds a parameterized INSERT statement from the
        provided column-value pairs — no raw SQL is needed.

        Args:
            table: Target table name (e.g. "dbo.Customers" or "Customers").
            data: Dictionary of column-value pairs to insert.
                  Example: {"Name": "João", "Email": "joao@example.com", "Age": 30}
            return_identity: If True, returns the auto-generated ID
                             (SCOPE_IDENTITY or OUTPUT for GUID PKs).
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with success status, insertedId (if requested),
            rowsAffected, and executionTime.
        """
        try:
            body: dict = {"table": table, "data": data, "returnIdentity": return_identity}
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] insert_record: table=%s, cols=%d", table, len(data))
            result = await client.post("/api/sql-server/data/insert", json=body)
            rows = result.get("rowsAffected", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] insert_record: %dms | rowsAffected=%s", int((time.perf_counter() - t0) * 1000), rows)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] insert_record: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] insert_record: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in insert_record")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def update_record(
        table: str,
        data: dict,
        where: dict,
        timeout: Optional[int] = None,
    ) -> str:
        """Update records in a SQL Server table using structured column-value pairs.

        The SupaProxy builds a parameterized UPDATE with SET and WHERE clauses
        from the provided dictionaries — no raw SQL needed.

        IMPORTANT: The `where` clause is REQUIRED.  The SupaProxy rejects
        updates without a WHERE clause to prevent accidental mass updates.

        Supports RowVersion/Timestamp concurrency tokens.  If `where`
        contains a "RowVersion" key, the new RowVersion is returned.

        Args:
            table: Target table name (e.g. "dbo.Customers").
            data: Dictionary of column-value pairs to SET.
                  Example: {"Name": "João Silva", "Age": 31}
            where: Dictionary of column-value pairs for the WHERE clause.
                   Example: {"Id": 42}
                   All conditions are ANDed together.
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with success, message, rowsAffected.
            If RowVersion was in where, also returns newRowVersion.
        """
        try:
            body: dict = {"table": table, "data": data, "where": where}
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] update_record: table=%s, set_cols=%d, where_cols=%d", table, len(data), len(where))
            result = await client.put("/api/sql-server/data/update", json=body)
            rows = result.get("rowsAffected", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] update_record: %dms | rowsAffected=%s", int((time.perf_counter() - t0) * 1000), rows)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] update_record: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] update_record: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in update_record")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def upsert_record(
        table: str,
        data: dict,
        conflict_keys: list[str],
        timeout: Optional[int] = None,
    ) -> str:
        """Insert or update a record using MERGE (upsert) semantics.

        If a record matching the `conflict_keys` already exists, it is
        updated.  Otherwise, a new record is inserted.

        Internally uses T-SQL MERGE statement.

        Args:
            table: Target table name (e.g. "dbo.Products").
            data: Dictionary of ALL column-value pairs (both key and non-key).
                  Example: {"ProductCode": "ABC123", "Name": "Widget", "Price": 9.99}
            conflict_keys: List of column names that identify uniqueness.
                           These MUST also be present in `data`.
                           Example: ["ProductCode"]
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with success, message, and rowsAffected.
        """
        try:
            body: dict = {"table": table, "data": data, "conflictKeys": conflict_keys}
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] upsert_record: table=%s, conflict_keys=%s", table, conflict_keys)
            result = await client.post("/api/sql-server/data/upsert", json=body)
            rows = result.get("rowsAffected", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] upsert_record: %dms | rowsAffected=%s", int((time.perf_counter() - t0) * 1000), rows)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] upsert_record: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] upsert_record: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in upsert_record")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def delete_record(
        table: str,
        where: dict,
        timeout: Optional[int] = None,
    ) -> str:
        """Delete records from a SQL Server table.

        IMPORTANT: The `where` clause is REQUIRED.  The SupaProxy rejects
        deletes without a WHERE clause to prevent accidental mass deletion.

        Args:
            table: Target table name (e.g. "dbo.Customers").
            where: Dictionary of column-value pairs for the WHERE clause.
                   Example: {"Id": 42}
                   All conditions are ANDed together.
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with success, message, and rowsAffected.
        """
        try:
            body: dict = {"table": table, "where": where}
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] delete_record: table=%s, where_cols=%d", table, len(where))
            result = await client.delete("/api/sql-server/data/delete", json=body)
            rows = result.get("rowsAffected", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] delete_record: %dms | rowsAffected=%s", int((time.perf_counter() - t0) * 1000), rows)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] delete_record: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] delete_record: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in delete_record")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def bulk_insert(
        table: str,
        rows: list[dict],
        timeout: Optional[int] = None,
    ) -> str:
        """Insert multiple records at once using SQL Server Bulk Copy.

        Significantly faster than individual inserts for large datasets.
        All rows must have the same column structure.

        Args:
            table: Target table name (e.g. "dbo.LogEntries").
            rows: List of dictionaries, each representing a row.
                  Example: [
                      {"Name": "Alice", "Age": 25},
                      {"Name": "Bob", "Age": 30}
                  ]
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with success, message, and rowsAffected.
        """
        try:
            body: dict = {"table": table, "rows": rows}
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] bulk_insert: table=%s, rows=%d", table, len(rows))
            result = await client.post("/api/sql-server/data/bulk-insert", json=body)
            affected = result.get("rowsAffected", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] bulk_insert: %dms | rowsAffected=%s", int((time.perf_counter() - t0) * 1000), affected)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] bulk_insert: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] bulk_insert: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in bulk_insert")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def execute_sql(
        sql: str,
        transaction: bool = False,
        timeout: Optional[int] = None,
    ) -> str:
        """Execute an INSERT, UPDATE, or DELETE SQL statement.

        Use this tool for arbitrary DML that doesn't fit the structured CRUD
        tools (e.g. multi-table updates, complex WHERE clauses).

        WARNING:
        - Do NOT use this for DDL (CREATE, ALTER, DROP, TRUNCATE).
        - Always include a WHERE clause for UPDATE/DELETE.
        - Use parameterized queries when possible.

        Args:
            sql: The T-SQL DML statement to execute.
                 Example: "UPDATE dbo.Orders SET Status = 'Shipped' WHERE OrderId = 123"
            transaction: If True, wraps the execution in a transaction
                         (auto-committed on success, rolled back on error).
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with success, message, rowsAffected, and executionTime.
        """
        try:
            body: dict = {"sql": sql, "transaction": transaction}
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] execute_sql: sql=%.60s, transaction=%s", sql.replace("\n", " "), transaction)
            result = await client.post("/api/sql-server/execute", json=body)
            rows = result.get("rowsAffected", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] execute_sql: %dms | rowsAffected=%s", int((time.perf_counter() - t0) * 1000), rows)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] execute_sql: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] execute_sql: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in execute_sql")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def export_data(
        table: Optional[str] = None,
        sql: Optional[str] = None,
        limit: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> str:
        """Export data from a table or custom query.

        Provide either `table` (for a simple SELECT * with optional LIMIT)
        or `sql` (for a custom query).

        Args:
            table: Table name to export (e.g. "dbo.Customers").
                   If provided without sql, executes
                   SELECT TOP(limit) * FROM table.
            sql: Custom SQL query to export.  Takes precedence over table.
            limit: Maximum number of rows (default 1000, only for table mode).
            timeout: Optional timeout in milliseconds.

        Returns:
            JSON object with the exported data rows.
        """
        try:
            body: dict = {}
            if sql:
                body["sql"] = sql
            if table:
                body["table"] = table
            if limit is not None:
                body["limit"] = limit
            if timeout is not None:
                body["timeout"] = timeout
            t0 = time.perf_counter()
            logger.info("[PERF >>>] export_data: table=%s, limit=%s", table or "(sql)", limit)
            result = await client.post("/api/sql-server/data/export", json=body)
            row_count = len(result) if isinstance(result, list) else (result.get("rowCount", "?") if isinstance(result, dict) else "?")
            logger.info("[PERF <<<] export_data: %dms | rows=%s", int((time.perf_counter() - t0) * 1000), row_count)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] export_data: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] export_data: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in export_data")
            return f"Unexpected error: {exc}"
