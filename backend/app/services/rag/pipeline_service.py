"""RAG Pipeline Service — programmatic access to the RAG pipeline.

Provides a clean abstraction for running queries through the full RAG pipeline
(safety → intent → engines → aggregation) WITHOUT requiring SSE streaming or HTTP.

Consumers:
- Batch evaluation (Celery tasks)
- Auto-evaluation hook
- Lawyer verification UI (F2)
- Future: regression tests, CI pipeline, API integrations

This service delegates to QueryOrchestrator — the same pipeline the chat UI uses —
so results are identical to what users see in the chat.
"""

import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.engines.orchestrator.orchestrator import (
    QueryOrchestrator,
    get_query_orchestrator,
)
from app.models.orchestrator import OrchestratorResult
from app.services.rag.embedder import EMBEDDING_MODEL

logger = structlog.get_logger(__name__)


# =============================================================================
# Result Model
# =============================================================================


class RAGPipelineResult(BaseModel):
    """Result of running a query through the RAG pipeline.

    Contains everything needed for evaluation, verification, or display.
    """

    answer: str = Field(description="Generated answer text")
    contexts: list[str] = Field(
        default_factory=list,
        description="Text content of retrieved chunks used to generate the answer",
    )
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Source references (document_name, page_number, chunk_id, etc.)",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Overall confidence score"
    )
    engines_used: list[str] = Field(
        default_factory=list, description="Which engines contributed to the answer"
    )
    execution_time_ms: int = Field(
        default=0, description="Total pipeline execution time in milliseconds"
    )
    pipeline_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Snapshot of pipeline configuration for traceability",
    )
    search_latency_ms: int | None = Field(
        default=None, description="Search+rerank latency in ms (from RAG adapter)",
    )
    blocked: bool = Field(
        default=False, description="True if query was blocked by safety checks"
    )
    blocked_reason: str = Field(
        default="", description="Reason for blocking if blocked"
    )


# =============================================================================
# Service
# =============================================================================


class RAGPipelineService:
    """Runs queries through the full RAG pipeline programmatically.

    Uses the same QueryOrchestrator as the chat UI, ensuring identical results.

    Example:
        >>> service = get_rag_pipeline_service()
        >>> result = await service.query(
        ...     matter_id="matter-123",
        ...     question="Who are the parties in this case?",
        ... )
        >>> print(result.answer)
        'The parties include Jyoti H. Mehta as applicant...'
        >>> print(result.contexts)
        ['Section 138 of NI Act provides for...', ...]
    """

    def __init__(self, orchestrator: QueryOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator or get_query_orchestrator()
        self._settings = get_settings()

    async def query(
        self,
        matter_id: str,
        question: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        skip_cache: bool = False,
    ) -> RAGPipelineResult:
        """Run a question through the full RAG pipeline.

        Args:
            matter_id: Matter UUID (for document isolation).
            question: The question to answer.
            user_id: Optional user ID for audit trail.
            context: Optional conversation context.

        Returns:
            RAGPipelineResult with answer, contexts, sources, and metadata.
        """
        start_time = time.time()

        # Use a system user ID for programmatic access (batch eval, etc.)
        effective_user_id = user_id or "system-evaluation"

        logger.info(
            "rag_pipeline_query_start",
            matter_id=matter_id,
            question_length=len(question),
            user_id=effective_user_id,
        )

        try:
            # Run through the full orchestrator pipeline
            result: OrchestratorResult = await self._orchestrator.process_query(
                matter_id=matter_id,
                query=question,
                user_id=effective_user_id,
                context=context,
                skip_cache=skip_cache,
            )

            # Handle blocked queries
            if result.blocked:
                return RAGPipelineResult(
                    answer="",
                    blocked=True,
                    blocked_reason=result.blocked_reason,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    pipeline_config=self._get_pipeline_config(),
                )

            # Extract contexts from engine results (chunk text content)
            contexts = self._extract_contexts(result)

            # Extract sources as dicts
            sources = [
                {
                    "document_id": s.document_id,
                    "document_name": s.document_name,
                    "chunk_id": s.chunk_id,
                    "page_number": s.page_number,
                    "confidence": s.confidence,
                    "engine": s.engine.value if s.engine else None,
                }
                for s in result.sources
            ]

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "rag_pipeline_query_complete",
                matter_id=matter_id,
                answer_length=len(result.unified_response),
                contexts_count=len(contexts),
                sources_count=len(sources),
                engines_used=[e.value for e in result.successful_engines],
                execution_time_ms=execution_time_ms,
            )

            # Gap 10: Extract search latency and actual provider from RAG engine result data
            search_latency_ms = None
            actual_embedding_provider = None
            actual_rerank_provider = None
            for er in result.engine_results:
                if er.data:
                    if "search_latency_ms" in er.data:
                        search_latency_ms = er.data["search_latency_ms"]
                    if "embedding_provider" in er.data:
                        actual_embedding_provider = er.data["embedding_provider"]
                    if "rerank_provider" in er.data:
                        actual_rerank_provider = er.data["rerank_provider"]

            # Use actual providers from engine results, then context, then defaults
            embed_prov = (
                actual_embedding_provider
                or (context or {}).get("embedding_provider")
            )
            rerank_prov = (
                actual_rerank_provider
                or (context or {}).get("rerank_provider")
            )

            return RAGPipelineResult(
                answer=result.unified_response,
                contexts=contexts,
                sources=sources,
                confidence=result.confidence,
                engines_used=[e.value for e in result.successful_engines],
                execution_time_ms=execution_time_ms,
                search_latency_ms=search_latency_ms,
                pipeline_config=self._get_pipeline_config(
                    embedding_provider=embed_prov,
                    rerank_provider=rerank_prov,
                ),
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "rag_pipeline_query_failed",
                matter_id=matter_id,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=execution_time_ms,
            )
            raise

    def _extract_contexts(self, result: OrchestratorResult) -> list[str]:
        """Extract text content of retrieved chunks from engine results.

        Walks through all engine results and pulls out chunk content strings.
        These are the actual text passages the LLM used to generate the answer.
        """
        contexts: list[str] = []
        for engine_result in result.engine_results:
            if not engine_result.data:
                continue
            chunks = engine_result.data.get("chunks", []) or engine_result.data.get("results", [])
            for chunk in chunks:
                if isinstance(chunk, dict) and "content" in chunk:
                    contexts.append(chunk["content"])
                elif isinstance(chunk, str):
                    contexts.append(chunk)
        return contexts

    def _get_pipeline_config(
        self,
        embedding_provider: str | None = None,
        rerank_provider: str | None = None,
    ) -> dict[str, Any]:
        """Snapshot current pipeline configuration for traceability.

        Stored with each evaluation result so you can compare
        'how did the same question perform under different configs?'

        Args:
            embedding_provider: Override embedding provider name for A/B testing.
            rerank_provider: Override reranker provider name for A/B testing.
        """
        embed_provider = embedding_provider or "openai"
        rerank = rerank_provider or "cohere"

        embed_model_map = {
            "openai": EMBEDDING_MODEL,
            "voyage": "voyage-law-2",
        }
        rerank_model_map = {
            "cohere": "cohere-rerank-v3.5",
            "voyage": "voyage-rerank-2.5",
        }

        return {
            "generator_model": self._settings.gemini_model,
            "embedding_model": embed_model_map.get(embed_provider, EMBEDDING_MODEL),
            "embedding_provider": embed_provider,
            "reranker": rerank_model_map.get(rerank, "cohere-rerank-v3.5"),
            "rerank_provider": rerank,
            "rag_search_limit": self._settings.rag_search_limit,
            "rag_rerank_top_n": self._settings.rag_rerank_top_n,
        }


# =============================================================================
# Factory
# =============================================================================

_instance: RAGPipelineService | None = None


def get_rag_pipeline_service() -> RAGPipelineService:
    """Get RAG pipeline service instance.

    Returns:
        RAGPipelineService instance.
    """
    global _instance
    if _instance is None:
        _instance = RAGPipelineService()
    return _instance
