"""Voyage AI embeddings and reranking for legal documents.

Voyage AI provides:
- voyage-law-2: Legal-specific embeddings (better than generic models)
- rerank-2.5: Instruction-following reranker
"""

from typing import Optional

import structlog
import voyageai

from src.core.config import settings

logger = structlog.get_logger(__name__)


class VoyageEmbedder:
    """Generate embeddings using Voyage AI's legal-specific model.

    voyage-law-2 is trained on legal documents and understands:
    - Legal terminology
    - Citation formats
    - Statutory language
    - Case law references
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "voyage-law-2",
    ):
        """Initialize Voyage embedder.

        Args:
            api_key: Voyage AI API key. Uses VOYAGE_API_KEY env var if not provided.
            model: Embedding model. Options:
                - voyage-law-2: Legal-specific (recommended)
                - voyage-3-large: General purpose, highest quality
                - voyage-3: General purpose, balanced
                - voyage-3-lite: Fast, lower quality
        """
        self.api_key = api_key or settings.voyage_api_key
        self.model = model
        self.client = voyageai.Client(api_key=self.api_key)

        logger.info("voyage_embedder_initialized", model=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for documents.

        Args:
            texts: List of document texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.debug("embedding_documents", count=len(texts))

        result = self.client.embed(
            texts,
            model=self.model,
            input_type="document",  # Optimized for documents
        )

        return result.embeddings

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Embedding vector
        """
        logger.debug("embedding_query", query=query[:50])

        result = self.client.embed(
            [query],
            model=self.model,
            input_type="query",  # Optimized for queries
        )

        return result.embeddings[0]

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 128,
        input_type: str = "document",
    ) -> list[list[float]]:
        """Embed texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            input_type: "document" or "query"

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            logger.debug(
                "embedding_batch",
                batch_num=i // batch_size + 1,
                batch_size=len(batch),
            )

            result = self.client.embed(
                batch,
                model=self.model,
                input_type=input_type,
            )

            all_embeddings.extend(result.embeddings)

        return all_embeddings


class VoyageReranker:
    """Rerank search results using Voyage AI's instruction-following model.

    rerank-2.5 supports instructions like:
    - "Retrieve statutory provisions, not case commentary"
    - "Prioritize Central Acts over State Acts"
    - "Find procedural requirements, not penalties"
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "rerank-2.5",
    ):
        """Initialize Voyage reranker.

        Args:
            api_key: Voyage AI API key
            model: Reranking model. Options:
                - rerank-2.5: Instruction-following (recommended)
                - rerank-2.5-lite: Faster, slightly lower quality
                - rerank-2: Previous version, no instructions
        """
        self.api_key = api_key or settings.voyage_api_key
        self.model = model
        self.client = voyageai.Client(api_key=self.api_key)

        logger.info("voyage_reranker_initialized", model=model)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: Optional[int] = None,
        instruction: Optional[str] = None,
    ) -> list[dict]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Number of top results to return (default: all)
            instruction: Optional instruction for legal document retrieval, e.g.:
                - "Retrieve statutory provisions from Central Acts"
                - "Find case law discussing Section 138 of NI Act"
                - "Prioritize recent judgments over older ones"

        Returns:
            List of dicts with keys: index, document, relevance_score
        """
        if not documents:
            return []

        logger.debug(
            "reranking",
            query=query[:50],
            doc_count=len(documents),
            instruction=instruction[:50] if instruction else None,
        )

        # Build rerank parameters
        kwargs = {
            "query": query,
            "documents": documents,
            "model": self.model,
        }

        if top_k:
            kwargs["top_k"] = top_k

        # Add instruction for rerank-2.5+
        if instruction and "2.5" in self.model:
            # Voyage rerank-2.5 supports query instruction
            kwargs["query"] = f"{instruction}\n\nQuery: {query}"

        result = self.client.rerank(**kwargs)

        # Convert to list of dicts
        reranked = []
        for r in result.results:
            reranked.append({
                "index": r.index,
                "document": documents[r.index],
                "relevance_score": r.relevance_score,
            })

        return reranked


# =============================================================================
# Legal-specific reranking instructions
# =============================================================================

LEGAL_RERANK_INSTRUCTIONS = {
    "statutes": "Retrieve statutory provisions and act sections. Prioritize primary legislation (Central Acts) over case commentary, legal articles, or secondary sources.",

    "case_law": "Retrieve case law and judicial decisions. Prioritize Supreme Court and High Court judgments over tribunal orders.",

    "procedural": "Retrieve procedural requirements, timelines, and compliance steps. Focus on how-to information rather than penalties or exceptions.",

    "penalties": "Retrieve penalty provisions, punishments, and consequences. Focus on sentencing guidelines and fine amounts.",

    "definitions": "Retrieve legal definitions and interpretations. Prioritize statutory definitions over judicial interpretations.",

    "recent": "Retrieve the most recent and current legal provisions. Prioritize amendments and new acts (post-2020) over older legislation.",
}


def get_rerank_instruction(category: str) -> Optional[str]:
    """Get pre-defined reranking instruction for a category.

    Args:
        category: One of: statutes, case_law, procedural, penalties, definitions, recent

    Returns:
        Instruction string or None if category not found
    """
    return LEGAL_RERANK_INSTRUCTIONS.get(category)
