"""Chunk service for database operations.

Handles chunk record creation, retrieval, and management in the chunks table.
Works with the parent-child chunking system for RAG pipelines.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

import structlog
from supabase import Client

from app.models.chunk import (
    Chunk,
    ChunkListItem,
    ChunkType,
    ChunkWithContent,
)
from app.services.chunking.parent_child_chunker import ChunkData
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


class ChunkServiceError(Exception):
    """Base exception for chunk service operations."""

    def __init__(self, message: str, code: str = "CHUNK_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ChunkNotFoundError(ChunkServiceError):
    """Raised when a chunk is not found."""

    def __init__(self, chunk_id: str):
        super().__init__(
            message=f"Chunk not found: {chunk_id}",
            code="CHUNK_NOT_FOUND",
            status_code=404,
        )


class ChunkService:
    """Service for chunk database operations.

    Uses the service client to bypass RLS since the backend
    has already validated access via the document's matter.
    """

    def __init__(self, client: Client | None = None):
        """Initialize chunk service.

        Args:
            client: Optional Supabase client. Uses service client if not provided.
        """
        self.client = client or get_service_client()

    async def save_chunks(
        self,
        document_id: str,
        matter_id: str,
        parent_chunks: list[ChunkData],
        child_chunks: list[ChunkData],
        batch_size: int = 100,
    ) -> int:
        """Save chunks to the database.

        Inserts parent chunks first to ensure foreign key integrity,
        then inserts child chunks with parent references.

        Args:
            document_id: Document UUID.
            matter_id: Matter UUID for RLS.
            parent_chunks: List of parent ChunkData.
            child_chunks: List of child ChunkData.
            batch_size: Number of rows per insert batch.

        Returns:
            Total number of chunks saved.

        Raises:
            ChunkServiceError: If save fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        all_chunks = parent_chunks + child_chunks

        if not all_chunks:
            logger.info(
                "chunks_save_skipped",
                document_id=document_id,
                reason="empty_list",
            )
            return 0

        logger.info(
            "chunks_save_starting",
            document_id=document_id,
            matter_id=matter_id,
            parent_count=len(parent_chunks),
            child_count=len(child_chunks),
        )

        try:
            # Delete any existing chunks for this document (in case of reprocessing)
            await self.delete_chunks_for_document(document_id)

            # Convert to database records - parents first
            parent_records = [
                {
                    "id": str(chunk.id),
                    "matter_id": matter_id,
                    "document_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    "parent_chunk_id": None,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "bbox_ids": [str(bid) for bid in chunk.bbox_ids] if chunk.bbox_ids else None,
                    "token_count": chunk.token_count,
                    "chunk_type": chunk.chunk_type,
                }
                for chunk in parent_chunks
            ]

            # Insert parents in batches
            total_saved = 0
            for i in range(0, len(parent_records), batch_size):
                batch = parent_records[i : i + batch_size]
                result = self.client.table("chunks").insert(batch).execute()
                total_saved += len(result.data) if result.data else 0

            # Now insert children with parent references
            child_records = [
                {
                    "id": str(chunk.id),
                    "matter_id": matter_id,
                    "document_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    "parent_chunk_id": str(chunk.parent_id) if chunk.parent_id else None,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "bbox_ids": [str(bid) for bid in chunk.bbox_ids] if chunk.bbox_ids else None,
                    "token_count": chunk.token_count,
                    "chunk_type": chunk.chunk_type,
                }
                for chunk in child_chunks
            ]

            for i in range(0, len(child_records), batch_size):
                batch = child_records[i : i + batch_size]
                result = self.client.table("chunks").insert(batch).execute()
                total_saved += len(result.data) if result.data else 0

            logger.info(
                "chunks_save_complete",
                document_id=document_id,
                total_saved=total_saved,
            )

            return total_saved

        except ChunkServiceError:
            raise
        except Exception as e:
            logger.error(
                "chunks_save_failed",
                document_id=document_id,
                matter_id=matter_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to save chunks: {e!s}",
                code="SAVE_FAILED",
            ) from e

    async def delete_chunks_for_document(self, document_id: str) -> int:
        """Delete all chunks for a document.

        Used when re-processing a document.

        Args:
            document_id: Document UUID.

        Returns:
            Number of chunks deleted.

        Raises:
            ChunkServiceError: If deletion fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            # Delete children first (foreign key constraint)
            self.client.table("chunks").delete().eq(
                "document_id", document_id
            ).eq("chunk_type", "child").execute()

            # Then delete parents
            result = self.client.table("chunks").delete().eq(
                "document_id", document_id
            ).execute()

            deleted_count = len(result.data) if result.data else 0

            logger.info(
                "chunks_deleted",
                document_id=document_id,
                deleted_count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            logger.error(
                "chunks_delete_failed",
                document_id=document_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to delete chunks: {e!s}",
                code="DELETE_FAILED",
            ) from e

    def get_chunks_for_document(
        self,
        document_id: str,
        chunk_type: ChunkType | None = None,
    ) -> tuple[list[ChunkWithContent], int, int]:
        """Get all chunks for a document.

        Args:
            document_id: Document UUID.
            chunk_type: Optional filter by chunk type.

        Returns:
            Tuple of (chunks list, parent count, child count).

        Raises:
            ChunkServiceError: If query fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            query = (
                self.client.table("chunks")
                .select("*")
                .eq("document_id", document_id)
                .order("chunk_type", desc=True)  # Parents first
                .order("chunk_index", desc=False)
            )

            if chunk_type:
                query = query.eq("chunk_type", chunk_type.value)

            result = query.execute()

            chunks = [self._parse_chunk_with_content(row) for row in (result.data or [])]

            # Count parents and children
            parent_count = sum(1 for c in chunks if c.chunk_type == ChunkType.PARENT)
            child_count = sum(1 for c in chunks if c.chunk_type == ChunkType.CHILD)

            return chunks, parent_count, child_count

        except Exception as e:
            logger.error(
                "chunks_get_for_document_failed",
                document_id=document_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to get chunks: {e!s}",
                code="GET_FAILED",
            ) from e

    def get_chunk(self, chunk_id: str) -> Chunk:
        """Get a single chunk by ID.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            Chunk record.

        Raises:
            ChunkNotFoundError: If chunk doesn't exist.
            ChunkServiceError: If query fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            result = (
                self.client.table("chunks")
                .select("*")
                .eq("id", chunk_id)
                .execute()
            )

            if not result.data:
                raise ChunkNotFoundError(chunk_id)

            return self._parse_chunk(result.data[0])

        except ChunkNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "chunk_get_failed",
                chunk_id=chunk_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to get chunk: {e!s}",
                code="GET_FAILED",
            ) from e

    def get_parent_chunk(self, chunk_id: str) -> Chunk | None:
        """Get the parent chunk of a child chunk.

        Args:
            chunk_id: Child chunk UUID.

        Returns:
            Parent Chunk or None if no parent.

        Raises:
            ChunkServiceError: If query fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            # First get the chunk to find its parent_chunk_id
            result = (
                self.client.table("chunks")
                .select("parent_chunk_id")
                .eq("id", chunk_id)
                .execute()
            )

            if not result.data:
                raise ChunkNotFoundError(chunk_id)

            parent_id = result.data[0].get("parent_chunk_id")

            if not parent_id:
                return None

            # Get the parent chunk
            return self.get_chunk(parent_id)

        except (ChunkNotFoundError, ChunkServiceError):
            raise
        except Exception as e:
            logger.error(
                "chunk_get_parent_failed",
                chunk_id=chunk_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to get parent chunk: {e!s}",
                code="GET_PARENT_FAILED",
            ) from e

    def get_child_chunks(self, parent_id: str) -> list[Chunk]:
        """Get all child chunks of a parent chunk.

        Args:
            parent_id: Parent chunk UUID.

        Returns:
            List of child Chunks.

        Raises:
            ChunkServiceError: If query fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            result = (
                self.client.table("chunks")
                .select("*")
                .eq("parent_chunk_id", parent_id)
                .order("chunk_index", desc=False)
                .execute()
            )

            return [self._parse_chunk(row) for row in (result.data or [])]

        except Exception as e:
            logger.error(
                "chunks_get_children_failed",
                parent_id=parent_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to get child chunks: {e!s}",
                code="GET_CHILDREN_FAILED",
            ) from e

    def get_chunk_with_context(self, chunk_id: str) -> dict[str, Any]:
        """Get a chunk with its parent and sibling context.

        Args:
            chunk_id: Chunk UUID.

        Returns:
            Dictionary with chunk, parent (if applicable), and siblings.

        Raises:
            ChunkNotFoundError: If chunk doesn't exist.
            ChunkServiceError: If query fails.
        """
        if self.client is None:
            raise ChunkServiceError(
                message="Database client not configured",
                code="DATABASE_NOT_CONFIGURED",
            )

        try:
            # Get the chunk
            chunk = self.get_chunk(chunk_id)

            # Build context response
            context: dict[str, Any] = {"chunk": chunk}

            # If it's a child chunk, get parent and siblings
            if chunk.chunk_type == ChunkType.CHILD and chunk.parent_chunk_id:
                parent = self.get_chunk(chunk.parent_chunk_id)
                context["parent"] = parent

                # Get sibling children (other children of same parent)
                siblings = self.get_child_chunks(chunk.parent_chunk_id)
                context["siblings"] = [s for s in siblings if s.id != chunk_id]

            # If it's a parent chunk, get its children
            elif chunk.chunk_type == ChunkType.PARENT:
                children = self.get_child_chunks(chunk_id)
                context["children"] = children

            return context

        except (ChunkNotFoundError, ChunkServiceError):
            raise
        except Exception as e:
            logger.error(
                "chunk_get_with_context_failed",
                chunk_id=chunk_id,
                error=str(e),
            )
            raise ChunkServiceError(
                message=f"Failed to get chunk with context: {e!s}",
                code="GET_CONTEXT_FAILED",
            ) from e

    def _parse_chunk(self, row: dict[str, Any]) -> Chunk:
        """Parse a database row into a Chunk model.

        Args:
            row: Database row dictionary.

        Returns:
            Chunk model instance.
        """
        return Chunk(
            id=row["id"],
            matter_id=row["matter_id"],
            document_id=row["document_id"],
            content=row["content"],
            chunk_type=ChunkType(row["chunk_type"]),
            chunk_index=row["chunk_index"],
            token_count=row.get("token_count") or 0,
            parent_chunk_id=row.get("parent_chunk_id"),
            page_number=row.get("page_number"),
            bbox_ids=row.get("bbox_ids"),
            entity_ids=row.get("entity_ids"),
            created_at=datetime.fromisoformat(
                row["created_at"].replace("Z", "+00:00")
            ),
        )

    def _parse_chunk_with_content(self, row: dict[str, Any]) -> ChunkWithContent:
        """Parse a database row into a ChunkWithContent model.

        Args:
            row: Database row dictionary.

        Returns:
            ChunkWithContent model instance.
        """
        return ChunkWithContent(
            id=row["id"],
            document_id=row["document_id"],
            content=row["content"],
            chunk_type=ChunkType(row["chunk_type"]),
            chunk_index=row["chunk_index"],
            token_count=row.get("token_count") or 0,
            parent_chunk_id=row.get("parent_chunk_id"),
            page_number=row.get("page_number"),
        )


@lru_cache(maxsize=1)
def get_chunk_service() -> ChunkService:
    """Get singleton chunk service instance.

    Returns:
        ChunkService instance.
    """
    return ChunkService()
