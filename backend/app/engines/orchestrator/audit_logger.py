"""Query Audit Logger for forensic compliance.

Story 6-3: Audit Trail Logging (AC: #1-3)

Creates comprehensive audit records for every query processed,
enabling forensic analysis and compliance with NFR24.

CRITICAL: Audit logging must be non-blocking - failures should
not affect query processing.
"""

import uuid
from datetime import datetime, timezone
from functools import lru_cache

import structlog

from app.models.orchestrator import (
    EngineType,
    FindingAuditEntry,
    IntentAnalysisResult,
    LLMCostEntry,
    OrchestratorResult,
    QueryAuditEntry,
    QueryIntent,
    SourceReference,
)

logger = structlog.get_logger(__name__)


class QueryAuditLogger:
    """Creates comprehensive audit records for queries.

    Story 6-3: Extracts all relevant data from orchestrator results
    and creates forensically complete audit records.

    Example:
        >>> logger = get_query_audit_logger()
        >>> entry = logger.log_query(
        ...     matter_id="matter-123",
        ...     user_id="user-456",
        ...     result=orchestrator_result,
        ...     intent_result=intent_result,
        ... )
        >>> entry.query_id
        'abc-123-...'
    """

    def log_query(
        self,
        matter_id: str,
        user_id: str,
        result: OrchestratorResult,
        intent_result: IntentAnalysisResult | None = None,
    ) -> QueryAuditEntry:
        """Create complete audit record for a query (AC: #1-3).

        Args:
            matter_id: Matter UUID.
            user_id: User who asked the query.
            result: OrchestratorResult from query processing.
            intent_result: Optional IntentAnalysisResult for cost tracking.

        Returns:
            QueryAuditEntry ready for persistence.
        """
        query_id = str(uuid.uuid4())
        asked_at = datetime.now(timezone.utc).isoformat()

        # Extract findings from engine results (AC: #2)
        findings = self._extract_findings(result)

        # Collect LLM costs (AC: #3)
        llm_costs = self._collect_llm_costs(intent_result, result)
        total_cost = self._calculate_total_cost(llm_costs)

        # Generate response summary
        response_summary = self._generate_response_summary(result)

        # Determine intent (from result or default)
        query_intent = QueryIntent.RAG_SEARCH
        intent_confidence = 0.0
        if intent_result:
            query_intent = intent_result.classification.intent
            intent_confidence = intent_result.classification.confidence

        entry = QueryAuditEntry(
            query_id=query_id,
            matter_id=matter_id,
            query_text=result.query,
            query_intent=query_intent,
            intent_confidence=intent_confidence,
            asked_by=user_id,
            asked_at=asked_at,
            engines_invoked=result.successful_engines + result.failed_engines,
            successful_engines=result.successful_engines,
            failed_engines=result.failed_engines,
            execution_time_ms=result.total_execution_time_ms,
            wall_clock_time_ms=result.wall_clock_time_ms,
            findings_count=len(findings),
            response_summary=response_summary,
            overall_confidence=result.confidence,
            llm_costs=llm_costs,
            total_cost_usd=total_cost,
            findings=findings,
        )

        logger.info(
            "query_audit_created",
            query_id=query_id,
            matter_id=matter_id,
            user_id=user_id,
            engines=len(entry.engines_invoked),
            findings=entry.findings_count,
            cost_usd=entry.total_cost_usd,
        )

        return entry

    def _extract_findings(
        self,
        result: OrchestratorResult,
    ) -> list[FindingAuditEntry]:
        """Extract finding details from engine results (AC: #2).

        Args:
            result: OrchestratorResult with engine outputs.

        Returns:
            List of FindingAuditEntry for each finding.
        """
        findings: list[FindingAuditEntry] = []

        for engine_result in result.engine_results:
            if not engine_result.success or not engine_result.data:
                continue

            # Extract findings based on engine type
            engine_findings = self._extract_engine_findings(
                engine=engine_result.engine,
                data=engine_result.data,
                confidence=engine_result.confidence or 0.0,
            )
            findings.extend(engine_findings)

        return findings

    def _extract_engine_findings(
        self,
        engine: EngineType,
        data: dict,
        confidence: float,
    ) -> list[FindingAuditEntry]:
        """Extract findings from a specific engine's output.

        Args:
            engine: Engine type.
            data: Engine output data.
            confidence: Engine confidence score.

        Returns:
            List of FindingAuditEntry.
        """
        findings: list[FindingAuditEntry] = []

        match engine:
            case EngineType.CITATION:
                # Citation engine outputs citations list
                for citation in data.get("citations", []):
                    findings.append(
                        FindingAuditEntry(
                            finding_id=str(uuid.uuid4()),
                            engine=engine,
                            finding_type="citation",
                            confidence=citation.get("confidence", confidence),
                            summary=f"{citation.get('act', 'Unknown')} Section {citation.get('section', '?')}",
                            source_references=self._extract_source_refs(
                                citation, engine
                            ),
                        )
                    )

            case EngineType.TIMELINE:
                # Timeline engine outputs events list
                for event in data.get("events", []):
                    findings.append(
                        FindingAuditEntry(
                            finding_id=str(uuid.uuid4()),
                            engine=engine,
                            finding_type="timeline_event",
                            confidence=event.get("confidence", confidence),
                            summary=f"{event.get('date', '?')}: {event.get('description', 'Event')[:50]}",
                            source_references=self._extract_source_refs(event, engine),
                        )
                    )

            case EngineType.CONTRADICTION:
                # Contradiction engine outputs contradictions list
                for contradiction in data.get("contradictions", []):
                    findings.append(
                        FindingAuditEntry(
                            finding_id=str(uuid.uuid4()),
                            engine=engine,
                            finding_type="contradiction",
                            confidence=contradiction.get("confidence", confidence),
                            summary=contradiction.get(
                                "explanation", "Contradiction detected"
                            )[:100],
                            source_references=self._extract_source_refs(
                                contradiction, engine
                            ),
                        )
                    )

            case EngineType.RAG:
                # RAG engine outputs search results - limit to top 5
                for i, rag_result in enumerate(data.get("results", [])[:5]):
                    findings.append(
                        FindingAuditEntry(
                            finding_id=str(uuid.uuid4()),
                            engine=engine,
                            finding_type="search_result",
                            confidence=rag_result.get("score", confidence),
                            summary=rag_result.get("text", "")[:100],
                            source_references=self._extract_source_refs(
                                rag_result, engine
                            ),
                        )
                    )

        return findings

    def _extract_source_refs(
        self,
        data: dict,
        engine: EngineType,
    ) -> list[SourceReference]:
        """Extract source references from finding data.

        Args:
            data: Finding data dict.
            engine: Engine that produced the finding.

        Returns:
            List of SourceReference.
        """
        refs: list[SourceReference] = []

        # Check common source reference patterns
        if "document_id" in data:
            refs.append(
                SourceReference(
                    document_id=data["document_id"],
                    document_name=data.get("document_name"),
                    chunk_id=data.get("chunk_id"),
                    page_number=data.get("page_number"),
                    text_preview=data.get("text", "")[:200] if data.get("text") else None,
                    engine=engine,
                )
            )
        elif "sources" in data and isinstance(data["sources"], list):
            for source in data["sources"][:3]:  # Limit to 3 sources
                if isinstance(source, dict) and "document_id" in source:
                    refs.append(
                        SourceReference(
                            document_id=source["document_id"],
                            document_name=source.get("document_name"),
                            chunk_id=source.get("chunk_id"),
                            page_number=source.get("page_number"),
                            engine=engine,
                        )
                    )

        return refs

    def _collect_llm_costs(
        self,
        intent_result: IntentAnalysisResult | None,
        result: OrchestratorResult,
    ) -> list[LLMCostEntry]:
        """Collect LLM costs from all sources (AC: #3).

        Args:
            intent_result: Intent analysis result with cost.
            result: Orchestrator result (engines may have costs).

        Returns:
            List of LLMCostEntry for all LLM calls.
        """
        costs: list[LLMCostEntry] = []

        # Intent analysis cost (GPT-3.5)
        if intent_result and intent_result.cost.llm_call_made:
            costs.append(
                LLMCostEntry(
                    model_name="gpt-3.5-turbo",
                    purpose="intent_analysis",
                    input_tokens=intent_result.cost.input_tokens,
                    output_tokens=intent_result.cost.output_tokens,
                    cost_usd=intent_result.cost.total_cost_usd,
                )
            )

        # Engine-level costs (from engine results if tracked)
        for engine_result in result.engine_results:
            if engine_result.success and engine_result.data:
                # Check if engine tracked LLM cost
                llm_data = engine_result.data.get("llm_cost")
                if llm_data:
                    costs.append(
                        LLMCostEntry(
                            model_name=llm_data.get("model", "unknown"),
                            purpose=f"{engine_result.engine.value}_engine",
                            input_tokens=llm_data.get("input_tokens", 0),
                            output_tokens=llm_data.get("output_tokens", 0),
                            cost_usd=llm_data.get("cost_usd", 0.0),
                        )
                    )

        return costs

    def _calculate_total_cost(
        self,
        llm_costs: list[LLMCostEntry],
    ) -> float:
        """Calculate total cost from all LLM entries (AC: #3).

        Args:
            llm_costs: List of LLM cost entries.

        Returns:
            Total cost in USD.
        """
        return sum(c.cost_usd for c in llm_costs)

    def _generate_response_summary(
        self,
        result: OrchestratorResult,
    ) -> str:
        """Generate concise summary of the response.

        Args:
            result: OrchestratorResult.

        Returns:
            Concise summary string (max 500 chars).
        """
        # Use unified_response but truncate
        summary = result.unified_response
        if len(summary) > 500:
            summary = summary[:497] + "..."
        return summary


@lru_cache(maxsize=1)
def get_query_audit_logger() -> QueryAuditLogger:
    """Get singleton QueryAuditLogger instance.

    Returns:
        QueryAuditLogger instance.
    """
    return QueryAuditLogger()
