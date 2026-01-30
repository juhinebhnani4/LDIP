"""RAG (Retrieval-Augmented Generation) search with visual grounding.

Combines:
- ChromaDB vector store
- Voyage AI embeddings (voyage-law-2)
- Voyage AI reranking (rerank-2.5)
- Visual grounding from ADE chunks
"""

from pathlib import Path
from typing import Optional

import structlog
import chromadb
from chromadb.config import Settings as ChromaSettings

from src.core.config import settings
from src.core.models import Chunk, SearchResult, SearchResponse, BoundingBox
from src.embeddings.voyage import VoyageEmbedder, VoyageReranker, get_rerank_instruction

logger = structlog.get_logger(__name__)


class DocumentStore:
    """Store and retrieve document chunks with embeddings.

    Uses ChromaDB for vector storage and Voyage AI for embeddings.
    All chunks retain their visual grounding (bounding boxes).
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        collection_name: str = "documents",
    ):
        """Initialize document store.

        Args:
            db_path: Path to ChromaDB storage
            collection_name: Collection name
        """
        self.db_path = Path(db_path or settings.docs_db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Legal document chunks with grounding"},
        )

        # Initialize embedder
        self.embedder = VoyageEmbedder()

        logger.info(
            "document_store_initialized",
            db_path=str(self.db_path),
            collection=collection_name,
        )

    def add_chunks(
        self,
        chunks: list[Chunk],
        batch_size: int = 100,
    ) -> int:
        """Add chunks to the store.

        Args:
            chunks: List of Chunk objects
            batch_size: Batch size for embedding

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        logger.info("adding_chunks", count=len(chunks))

        # Generate embeddings
        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_batch(texts, batch_size=batch_size)

        # Prepare metadata (flatten bbox for ChromaDB)
        ids = [c.chunk_id for c in chunks]
        metadatas = []

        for chunk in chunks:
            meta = {
                "page": chunk.page,
                "chunk_type": chunk.chunk_type.value,
                "document_id": chunk.document_id or "",
                "matter_id": chunk.matter_id or "",
                "token_count": chunk.token_count or 0,
            }

            # Flatten bbox
            if chunk.bbox:
                meta["bbox_x0"] = chunk.bbox.x0
                meta["bbox_y0"] = chunk.bbox.y0
                meta["bbox_x1"] = chunk.bbox.x1
                meta["bbox_y1"] = chunk.bbox.y1

            metadatas.append(meta)

        # Add to ChromaDB
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info("chunks_added", count=len(chunks))
        return len(chunks)

    def search(
        self,
        query: str,
        matter_id: Optional[str] = None,
        document_id: Optional[str] = None,
        top_k: int = 20,
    ) -> list[dict]:
        """Search for relevant chunks.

        Args:
            query: Search query
            matter_id: Optional filter by matter
            document_id: Optional filter by document
            top_k: Number of results

        Returns:
            List of search results with metadata
        """
        # Build where clause
        where = {}
        if matter_id:
            where["matter_id"] = matter_id
        if document_id:
            where["document_id"] = document_id

        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where if where else None,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]

            # Reconstruct bbox
            bbox = None
            if all(f"bbox_{k}" in meta for k in ["x0", "y0", "x1", "y1"]):
                bbox = BoundingBox(
                    x0=meta["bbox_x0"],
                    y0=meta["bbox_y0"],
                    x1=meta["bbox_x1"],
                    y1=meta["bbox_y1"],
                )

            formatted.append({
                "chunk_id": doc_id,
                "text": results["documents"][0][i],
                "page": meta.get("page", 0),
                "chunk_type": meta.get("chunk_type", "text"),
                "document_id": meta.get("document_id"),
                "matter_id": meta.get("matter_id"),
                "bbox": bbox,
                "distance": results["distances"][0][i],
                "similarity": 1 - results["distances"][0][i],
            })

        return formatted

    def delete_document(self, document_id: str) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: Document ID

        Returns:
            Number of chunks deleted
        """
        # Get all chunk IDs for this document
        results = self.collection.get(
            where={"document_id": document_id},
            include=[],
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info("document_deleted", document_id=document_id, chunks=len(results["ids"]))
            return len(results["ids"])

        return 0

    def get_stats(self) -> dict:
        """Get store statistics."""
        return {
            "total_chunks": self.collection.count(),
            "collection_name": self.collection_name,
            "db_path": str(self.db_path),
        }


class RAGSearch:
    """RAG search with reranking and visual grounding.

    Pipeline:
    1. Vector search (Voyage voyage-law-2)
    2. Rerank (Voyage rerank-2.5 with instructions)
    3. Return results with visual grounding
    """

    def __init__(
        self,
        store: Optional[DocumentStore] = None,
        db_path: Optional[Path] = None,
    ):
        """Initialize RAG search.

        Args:
            store: Optional existing DocumentStore
            db_path: Path to ChromaDB (if creating new store)
        """
        self.store = store or DocumentStore(db_path=db_path)
        self.reranker = VoyageReranker()

        logger.info("rag_search_initialized")

    def search(
        self,
        query: str,
        matter_id: Optional[str] = None,
        document_id: Optional[str] = None,
        top_k: int = 5,
        rerank: bool = True,
        rerank_instruction: Optional[str] = None,
        legal_category: Optional[str] = None,
    ) -> SearchResponse:
        """Search with optional reranking.

        Args:
            query: Search query
            matter_id: Optional filter by matter
            document_id: Optional filter by document
            top_k: Number of final results
            rerank: Whether to apply reranking
            rerank_instruction: Custom reranking instruction
            legal_category: Use pre-defined instruction (statutes, case_law, etc.)

        Returns:
            SearchResponse with grounded results
        """
        logger.info(
            "searching",
            query=query[:50],
            matter_id=matter_id,
            rerank=rerank,
        )

        # Stage 1: Vector search (retrieve more for reranking)
        initial_k = top_k * 4 if rerank else top_k
        raw_results = self.store.search(
            query=query,
            matter_id=matter_id,
            document_id=document_id,
            top_k=initial_k,
        )

        if not raw_results:
            return SearchResponse(
                query=query,
                results=[],
                search_type="semantic",
                reranked=False,
            )

        # Stage 2: Rerank (optional)
        if rerank and len(raw_results) > 1:
            # Get instruction
            instruction = rerank_instruction
            if not instruction and legal_category:
                instruction = get_rerank_instruction(legal_category)

            # Rerank
            documents = [r["text"] for r in raw_results]
            reranked = self.reranker.rerank(
                query=query,
                documents=documents,
                top_k=top_k,
                instruction=instruction,
            )

            # Map back to original results
            final_results = []
            for rank, item in enumerate(reranked, 1):
                original = raw_results[item["index"]]
                final_results.append(
                    SearchResult(
                        chunk=Chunk(
                            chunk_id=original["chunk_id"],
                            text=original["text"],
                            page=original["page"],
                            chunk_type=original["chunk_type"],
                            bbox=original["bbox"],
                            document_id=original["document_id"],
                            matter_id=original["matter_id"],
                        ),
                        score=item["relevance_score"],
                        rank=rank,
                        page=original["page"],
                        bbox=original["bbox"],
                        rerank_score=item["relevance_score"],
                        original_rank=item["index"] + 1,
                    )
                )
        else:
            # No reranking, use vector search results directly
            final_results = [
                SearchResult(
                    chunk=Chunk(
                        chunk_id=r["chunk_id"],
                        text=r["text"],
                        page=r["page"],
                        chunk_type=r["chunk_type"],
                        bbox=r["bbox"],
                        document_id=r["document_id"],
                        matter_id=r["matter_id"],
                    ),
                    score=r["similarity"],
                    rank=i + 1,
                    page=r["page"],
                    bbox=r["bbox"],
                )
                for i, r in enumerate(raw_results[:top_k])
            ]

        return SearchResponse(
            query=query,
            results=final_results,
            search_type="semantic",
            reranked=rerank,
        )

    def search_for_statutes(
        self,
        query: str,
        matter_id: Optional[str] = None,
        top_k: int = 5,
    ) -> SearchResponse:
        """Search specifically for statutory provisions.

        Args:
            query: Search query
            matter_id: Optional filter
            top_k: Number of results

        Returns:
            SearchResponse focused on statutes
        """
        return self.search(
            query=query,
            matter_id=matter_id,
            top_k=top_k,
            rerank=True,
            legal_category="statutes",
        )

    def search_for_case_law(
        self,
        query: str,
        matter_id: Optional[str] = None,
        top_k: int = 5,
    ) -> SearchResponse:
        """Search specifically for case law.

        Args:
            query: Search query
            matter_id: Optional filter
            top_k: Number of results

        Returns:
            SearchResponse focused on case law
        """
        return self.search(
            query=query,
            matter_id=matter_id,
            top_k=top_k,
            rerank=True,
            legal_category="case_law",
        )

    def add_document(
        self,
        chunks: list[Chunk],
    ) -> int:
        """Add a document's chunks to the store.

        Args:
            chunks: Parsed document chunks

        Returns:
            Number of chunks added
        """
        return self.store.add_chunks(chunks)

    def get_stats(self) -> dict:
        """Get search statistics."""
        return self.store.get_stats()
