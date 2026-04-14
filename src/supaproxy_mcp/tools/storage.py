"""File storage tools for SupaProxy."""

import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register storage tools on the given FastMCP instance."""

    @mcp.tool()
    async def list_files(
        page: int = 1,
        page_size: int = 20,
        bucket: Optional[str] = None,
        search: Optional[str] = None,
        order_by: Optional[str] = None,
        order_dir: Optional[str] = None,
    ) -> str:
        """List files stored in SupaProxy storage with pagination and filtering.

        Args:
            page: Page number (1-based, default 1).
            page_size: Number of files per page (default 20).
            bucket: Filter by bucket name (e.g. "documentos", "imagens").
                    Available buckets: default, documentos, imagens, anexos, temp.
            search: Search files by name (partial match).
            order_by: Column to sort by (e.g. "createdAt", "fileName").
            order_dir: Sort direction ("asc" or "desc").

        Returns:
            JSON object with file list and pagination metadata.
        """
        try:
            params: dict = {"page": page, "pageSize": page_size}
            if bucket:
                params["bucket"] = bucket
            if search:
                params["search"] = search
            if order_by:
                params["orderBy"] = order_by
            if order_dir:
                params["orderDir"] = order_dir
            t0 = time.perf_counter()
            logger.info("[PERF >>>] list_files: bucket=%s, page=%d, page_size=%d", bucket, page, page_size)
            result = await client.get("/api/storage/list", params=params, include_connection=False)
            total = result.get("totalRecords", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] list_files: %dms | totalRecords=%s", int((time.perf_counter() - t0) * 1000), total)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] list_files: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] list_files: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in list_files")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def get_file_info(file_id: str) -> str:
        """Get metadata for a specific file.

        Args:
            file_id: The GUID of the file.

        Returns:
            JSON object with file metadata (id, fileName, bucket, contentType,
            fileSize, title, caption, tags, knowledgeBaseIds, createdAt, etc.).
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] get_file_info: file_id=%s", file_id)
            result = await client.get(f"/api/storage/files/{file_id}/info", include_connection=False)
            logger.info("[PERF <<<] get_file_info: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] get_file_info: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] get_file_info: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in get_file_info")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def update_file_metadata(
        file_id: str,
        title: Optional[str] = None,
        caption: Optional[str] = None,
        tags: Optional[list[str]] = None,
        knowledge_base_ids: Optional[list[str]] = None,
    ) -> str:
        """Update metadata for a stored file.

        Args:
            file_id: The GUID of the file.
            title: New display title.
            caption: New caption/description.
            tags: New list of tags.
            knowledge_base_ids: New list of knowledge base IDs to associate.

        Returns:
            JSON object with updated file metadata, or an error message.
        """
        try:
            body: dict = {}
            if title is not None:
                body["title"] = title
            if caption is not None:
                body["caption"] = caption
            if tags is not None:
                body["tags"] = tags
            if knowledge_base_ids is not None:
                body["knowledgeBaseIds"] = knowledge_base_ids
            t0 = time.perf_counter()
            logger.info("[PERF >>>] update_file_metadata: file_id=%s, fields=%s", file_id, list(body.keys()))
            result = await client.patch(
                f"/api/storage/files/{file_id}/metadata",
                json=body,
                include_connection=False,
            )
            logger.info("[PERF <<<] update_file_metadata: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] update_file_metadata: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] update_file_metadata: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in update_file_metadata")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def delete_file(file_id: str, permanent: bool = False) -> str:
        """Delete a file from storage.

        Args:
            file_id: The GUID of the file to delete.
            permanent: If True, permanently removes the file.  If False
                       (default), performs a soft delete (sets DeletedAt).

        Returns:
            JSON confirmation, or an error message.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] delete_file: file_id=%s, permanent=%s", file_id, permanent)
            result = await client.delete(
                f"/api/storage/files/{file_id}?permanent={'true' if permanent else 'false'}",
                include_connection=False,
            )
            logger.info("[PERF <<<] delete_file: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] delete_file: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] delete_file: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in delete_file")
            return f"Unexpected error: {exc}"
