"""Knowledge base (RAG) tools for SupaProxy."""

import json
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def register(mcp, client):  # noqa: ANN001
    """Register knowledge base tools on the given FastMCP instance."""

    @mcp.tool()
    async def ask_knowledge_base(
        question: str,
        source_application: Optional[str] = None,
        external_document_ids: Optional[list[str]] = None,
        metadata_filters: Optional[dict] = None,
        top_k: Optional[int] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> str:
        """Ask a question to the knowledge base using RAG (Retrieval Augmented Generation).

        Queries the KnowledgeBaseService through SupaProxy.  The system
        retrieves relevant document chunks, builds context, and generates
        an answer using an LLM.

        Args:
            question: The question to ask in natural language.
                      Example: "Qual é a política de devolução?"
            source_application: Optional filter by source application name.
            external_document_ids: Optional list of specific document GUIDs
                                   to restrict the search to.
            metadata_filters: Optional dictionary of metadata key-value
                              pairs to filter documents.
            top_k: Number of top relevant chunks to retrieve (1-50).
            conversation_history: Optional list of previous messages for
                                  multi-turn conversations.
                                  Format: [{"role": "user", "content": "..."},
                                           {"role": "assistant", "content": "..."}]

        Returns:
            JSON with answer, sources, retrieval_info, and token usage.
            May return HTTP 202 if documents are still being processed.
        """
        try:
            body: dict = {"question": question}
            filters: dict = {}
            if source_application:
                filters["source_application"] = source_application
            if external_document_ids:
                filters["external_document_ids"] = external_document_ids
            if metadata_filters:
                filters["metadata_filters"] = metadata_filters
            if filters:
                body["filters"] = filters
            if top_k is not None:
                body["top_k"] = top_k
            if conversation_history:
                body["conversation_history"] = conversation_history
            t0 = time.perf_counter()
            logger.info("[PERF >>>] ask_knowledge_base: question=%.60s, top_k=%s, filters=%s",
                question, top_k, list(filters.keys()) if filters else [])
            result = await client.post(
                "/api/storage/knowledge/ask", json=body, include_connection=False,
            )
            retrieval = result.get("retrieval_info", {}) if isinstance(result, dict) else {}
            chunks = retrieval.get("chunks_retrieved", "?")
            logger.info("[PERF <<<] ask_knowledge_base: %dms | chunks_retrieved=%s",
                int((time.perf_counter() - t0) * 1000), chunks)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] ask_knowledge_base: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] ask_knowledge_base: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in ask_knowledge_base")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def kb_document_status(document_id: str) -> str:
        """Check the knowledge base sync status for a document.

        Args:
            document_id: The GUID of the storage document.

        Returns:
            JSON object with document_id, source_application, kb_status
            (pending/sent/indexed/failed), last_sent_at, and last_error.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] kb_document_status: document_id=%s", document_id)
            result = await client.get(
                f"/api/storage/knowledge/{document_id}/status",
                include_connection=False,
            )
            status = result.get("kb_status", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] kb_document_status: %dms | kb_status=%s", int((time.perf_counter() - t0) * 1000), status)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] kb_document_status: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] kb_document_status: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in kb_document_status")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def kb_retry_document(document_id: str) -> str:
        """Retry sending a failed document to the knowledge base.

        Use this when a document has kb_status "failed" or "pending" and
        you want to re-trigger the ingestion pipeline.

        Args:
            document_id: The GUID of the storage document.

        Returns:
            JSON object with document_id, kb_status, and last_error.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] kb_retry_document: document_id=%s", document_id)
            result = await client.post(
                f"/api/storage/knowledge/{document_id}/retry",
                include_connection=False,
            )
            status = result.get("kb_status", "?") if isinstance(result, dict) else "?"
            logger.info("[PERF <<<] kb_retry_document: %dms | kb_status=%s", int((time.perf_counter() - t0) * 1000), status)
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] kb_retry_document: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] kb_retry_document: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in kb_retry_document")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def kb_update_metadata(
        document_id: str,
        metadata_json: str,
        reindex: bool = True,
    ) -> str:
        """Update the domain metadata associated with a document in the knowledge base.

        Args:
            document_id: The GUID of the storage document.
            metadata_json: New domain metadata as a JSON string.
                           Replaces the previous metadata entirely.
            reindex: If True (default), the KnowledgeBaseService reprocesses
                     the document (recalculates embeddings).
                     If False, only updates search filters (faster).

        Returns:
            JSON object with document_id, metadata_updated, and kb_status.
        """
        try:
            body = {"metadataJson": metadata_json, "reindex": reindex}
            t0 = time.perf_counter()
            logger.info("[PERF >>>] kb_update_metadata: document_id=%s, reindex=%s", document_id, reindex)
            result = await client.put(
                f"/api/storage/knowledge/{document_id}/metadata",
                json=body,
                include_connection=False,
            )
            logger.info("[PERF <<<] kb_update_metadata: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] kb_update_metadata: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] kb_update_metadata: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in kb_update_metadata")
            return f"Unexpected error: {exc}"

    @mcp.tool()
    async def kb_delete_metadata(document_id: str) -> str:
        """Remove the knowledge base metadata record for a document.

        This does NOT delete the file — only the KB sync metadata.

        Args:
            document_id: The GUID of the storage document.

        Returns:
            JSON object with document_id and deleted status.
        """
        try:
            t0 = time.perf_counter()
            logger.info("[PERF >>>] kb_delete_metadata: document_id=%s", document_id)
            result = await client.delete(
                f"/api/storage/knowledge/{document_id}/status",
                include_connection=False,
            )
            logger.info("[PERF <<<] kb_delete_metadata: %dms", int((time.perf_counter() - t0) * 1000))
            return json.dumps(result, indent=2, ensure_ascii=False)
        except httpx.HTTPStatusError as exc:
            logger.warning("[PERF !!!] kb_delete_metadata: HTTP %d apos %dms", exc.response.status_code, int((time.perf_counter() - t0) * 1000))
            return f"Error {exc.response.status_code}: {exc.response.text}"
        except Exception as exc:
            logger.warning("[PERF !!!] kb_delete_metadata: falha apos %dms — %s", int((time.perf_counter() - t0) * 1000), exc)
            logger.exception("Unexpected error in kb_delete_metadata")
            return f"Unexpected error: {exc}"
