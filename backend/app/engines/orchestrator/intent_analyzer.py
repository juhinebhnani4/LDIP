"""Intent Analyzer Engine for query routing.

Story 6-1: Query Intent Analysis
Story 13-2: Circuit breaker protection for OpenAI calls

Classifies user queries and routes them to appropriate engines using:
1. Fast-path regex patterns for obvious keywords
2. GPT-3.5 LLM classification for complex queries
3. Multi-engine fallback for low-confidence classifications
4. Circuit breaker protection for resilience

CRITICAL: Uses GPT-3.5 per LLM routing rules (ADR-002).
Query normalization = simple task, cost-sensitive.
DO NOT use GPT-4 - it's 30x more expensive for a simple task.

Fallback: When circuit is open, defaults to RAG engine with warning.
"""

import json
import re
import time
from functools import lru_cache

import structlog

from app.core.circuit_breaker import (
    CircuitOpenError,
    CircuitService,
    with_circuit_breaker,
)
from app.core.config import get_settings
from app.engines.orchestrator.models import (
    HIGH_CONFIDENCE_THRESHOLD,
    INCLUSION_THRESHOLD,
    CompoundIntent,
    IntentSignal,
    IntentSource,
    MultiIntentClassification,
)
from app.engines.orchestrator.prompts import (
    INTENT_CLASSIFICATION_SYSTEM_PROMPT,
    format_intent_prompt,
    validate_intent_response,
)
from app.models.orchestrator import (
    LOW_CONFIDENCE_THRESHOLD,
    EngineType,
    IntentAnalysisCost,
    IntentAnalysisResult,
    IntentClassification,
    QueryIntent,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# High-confidence threshold for fast-path (bypass LLM)
FAST_PATH_CONFIDENCE = 0.95

# Low confidence fallback used when circuit is open
FALLBACK_CONFIDENCE = 0.3


# =============================================================================
# Regex Patterns for Fast-Path Classification (Task 4.1, 4.2)
# =============================================================================

# Citation patterns - detect Act/Section references
CITATION_PATTERNS = [
    re.compile(r"\bcitations?\b", re.IGNORECASE),  # citation, citations
    re.compile(r"\b(cite|cited|citing)\b", re.IGNORECASE),
    re.compile(r"\bacts?\s+(of\s+)?\d{4}\b", re.IGNORECASE),  # "Act 1956", "Acts of 2013"
    re.compile(r"\bsection\s+\d+", re.IGNORECASE),  # "Section 138"
    re.compile(r"\b(statute|statutory|provisions?)\b", re.IGNORECASE),
    re.compile(r"\breferences?\b.*\b(act|law|statute)\b", re.IGNORECASE),
    re.compile(r"\blegal\s+reference", re.IGNORECASE),
    re.compile(r"\bact\s+references?\b", re.IGNORECASE),  # "Act references"
]

# Timeline patterns - detect chronological/date queries
TIMELINE_PATTERNS = [
    re.compile(r"\btimeline\b", re.IGNORECASE),
    re.compile(r"\bchronolog(y|ical|ically)?\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+did\b", re.IGNORECASE),
    re.compile(r"\bsequence\s+(of\s+)?events?\b", re.IGNORECASE),  # "sequence of events"
    re.compile(r"\bwhat\s+happened\b.*\b(order|first|then|before|after)\b", re.IGNORECASE),
    re.compile(r"\b(date|dates|dated)\b.*\b(event|occur|happen)\b", re.IGNORECASE),
    re.compile(r"\b(before|after|between)\b.*\d{4}", re.IGNORECASE),  # date references
    re.compile(r"\bchronological\s+order\b", re.IGNORECASE),
    re.compile(r"\bwhen\s+was\b", re.IGNORECASE),  # "when was"
]

# Contradiction patterns - detect inconsistency queries
CONTRADICTION_PATTERNS = [
    re.compile(r"\bcontradictions?\b", re.IGNORECASE),  # contradiction, contradictions
    re.compile(r"\b(contradict|contradicts|contradictory|contradicting)\b", re.IGNORECASE),
    re.compile(r"\binconsisten(t|cy|cies)\b", re.IGNORECASE),  # inconsistent, inconsistency
    re.compile(r"\bconflicts?\b", re.IGNORECASE),  # conflict, conflicts
    re.compile(r"\b(conflicting)\b", re.IGNORECASE),
    re.compile(r"\bdisagrees?\b", re.IGNORECASE),  # disagree, disagrees
    re.compile(r"\bdisagreement\b", re.IGNORECASE),
    re.compile(r"\bmismatche?s?\b", re.IGNORECASE),  # mismatch, mismatches
    re.compile(r"\bdifferent\s+(amount|date|claim|statement|version)\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+match\b", re.IGNORECASE),
]

# Document discovery patterns - detect document listing/metadata queries
DOCUMENT_DISCOVERY_PATTERNS = [
    re.compile(r"\bwhat\s+(documents?|files?)\b", re.IGNORECASE),  # what documents
    re.compile(r"\blist\s*(of\s*)?(all\s*)?(the\s*)?(documents?|files?)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+(documents?|files?)\b", re.IGNORECASE),  # which documents
    re.compile(r"\bhow\s+many\s+(documents?|files?|pages?)\b", re.IGNORECASE),
    re.compile(r"\b(show|display)\s*(me\s*)?(all\s*)?(the\s*)?(documents?|files?)\b", re.IGNORECASE),
    re.compile(r"\bdocuments?\s+(are|were)\s+(in|uploaded|available)\b", re.IGNORECASE),
    re.compile(r"\b(all|total)\s+(documents?|files?|pages?)\b", re.IGNORECASE),
    re.compile(r"\bexhibits?\b", re.IGNORECASE),  # legal document reference
]

# Entity lookup patterns - detect person/party queries
ENTITY_LOOKUP_PATTERNS = [
    re.compile(r"\bwho\s+is\b", re.IGNORECASE),  # who is X
    re.compile(r"\bwho\s+are\s+(the\s+)?(parties?|respondents?|applicants?|petitioners?|defendants?|plaintiffs?)\b", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+about\s+\w+", re.IGNORECASE),  # tell me about [name]
    re.compile(r"\b(parties?|respondents?|applicants?|petitioners?)\s+(involved|in\s+this)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+is\s+the\s+role\s+of\b", re.IGNORECASE),
    re.compile(r"\b(information|details?)\s+(about|on|regarding)\s+\w+", re.IGNORECASE),
    re.compile(r"\bwho\s+(filed|initiated|brought)\b", re.IGNORECASE),
    re.compile(r"\brelationship\s+(between|of)\b", re.IGNORECASE),
]


# =============================================================================
# Exceptions
# =============================================================================


class IntentAnalyzerError(Exception):
    """Base exception for intent analyzer operations."""

    def __init__(
        self,
        message: str,
        code: str = "INTENT_ANALYZER_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class OpenAIConfigurationError(IntentAnalyzerError):
    """Raised when OpenAI is not properly configured."""

    def __init__(self, message: str):
        super().__init__(message, code="OPENAI_NOT_CONFIGURED", is_retryable=False)


class IntentParseError(IntentAnalyzerError):
    """Raised when GPT-3.5 response cannot be parsed."""

    def __init__(self, message: str):
        super().__init__(message, code="PARSE_ERROR", is_retryable=True)


# =============================================================================
# Intent Analyzer Engine (Task 3)
# =============================================================================


class IntentAnalyzer:
    """Engine for classifying query intent and routing to appropriate engines.

    Story 6-1: Implements semantic routing via LLM classification.

    Pipeline:
    1. Check fast-path regex patterns (skip LLM if obvious keywords)
    2. If no fast-path match, use GPT-3.5 for classification
    3. If confidence < 0.7, add RAG fallback engine

    CRITICAL: Uses GPT-3.5 for cost-sensitive classification.

    Example:
        >>> analyzer = IntentAnalyzer()
        >>> result = await analyzer.analyze_intent(
        ...     matter_id="matter-123",
        ...     query="What does Section 138 of the NI Act say?",
        ... )
        >>> result.classification.intent
        QueryIntent.CITATION
    """

    def __init__(self) -> None:
        """Initialize intent analyzer."""
        self._client = None
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_intent_model

    @property
    def client(self):
        """Get or create OpenAI client.

        Returns:
            OpenAI client instance.

        Raises:
            OpenAIConfigurationError: If API key is not configured.
        """
        if self._client is None:
            if not self.api_key:
                raise OpenAIConfigurationError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                )

            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(
                    "intent_analyzer_initialized",
                    model=self.model_name,
                )
            except Exception as e:
                logger.error("intent_analyzer_init_failed", error=str(e))
                raise OpenAIConfigurationError(
                    f"Failed to initialize OpenAI client: {e}"
                ) from e

        return self._client

    async def analyze_intent(
        self,
        matter_id: str,
        query: str,
    ) -> IntentAnalysisResult:
        """Analyze query intent and determine routing.

        Implements AC #1-5:
        - AC #1: Route citation queries to Citation Engine
        - AC #2: Route timeline queries to Timeline Engine
        - AC #3: Route contradiction queries to Contradiction Engine
        - AC #4: Route general queries to RAG search
        - AC #5: Multi-engine fallback for low confidence

        Args:
            matter_id: Matter UUID for context and isolation.
            query: User's natural language query.

        Returns:
            IntentAnalysisResult with classification and metadata.

        Raises:
            IntentAnalyzerError: If analysis fails after retries.
        """
        # Normalize query - strip whitespace to avoid regex false negatives
        query = query.strip()

        logger.info(
            "analyze_intent_request",
            matter_id=matter_id,
            query_length=len(query),
        )

        start_time = time.time()

        # Step 1: Try fast-path regex classification
        fast_path_result = self._fast_path_classification(query)
        if fast_path_result is not None:
            processing_time = int((time.time() - start_time) * 1000)

            # Apply RAG fallback even for fast-path (always want document context)
            fast_path_result = self._apply_multi_engine_fallback(fast_path_result)

            logger.info(
                "analyze_intent_fast_path",
                matter_id=matter_id,
                intent=fast_path_result.intent.value,
                confidence=fast_path_result.confidence,
                required_engines=[e.value for e in fast_path_result.required_engines],
                processing_time_ms=processing_time,
            )

            return IntentAnalysisResult(
                matter_id=matter_id,
                query=query,
                classification=fast_path_result,
                fast_path_used=True,
                cost=IntentAnalysisCost(llm_call_made=False),
            )

        # Step 2: Use LLM classification
        classification, cost = await self._llm_classification(query)

        # Step 3: Apply confidence-based multi-engine fallback
        classification = self._apply_multi_engine_fallback(classification)

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "analyze_intent_complete",
            matter_id=matter_id,
            intent=classification.intent.value,
            confidence=classification.confidence,
            required_engines=[e.value for e in classification.required_engines],
            cost_usd=cost.total_cost_usd,
            processing_time_ms=processing_time,
        )

        return IntentAnalysisResult(
            matter_id=matter_id,
            query=query,
            classification=classification,
            fast_path_used=False,
            cost=cost,
        )

    def _fast_path_classification(self, query: str) -> IntentClassification | None:
        """Attempt fast-path classification using regex patterns.

        Task 4.2: Check obvious keywords BEFORE calling LLM to save cost.

        Args:
            query: User's query.

        Returns:
            IntentClassification if fast-path matches, None otherwise.
        """
        # Check document discovery patterns FIRST (most specific)
        doc_discovery_matches = sum(
            1 for pattern in DOCUMENT_DISCOVERY_PATTERNS if pattern.search(query)
        )
        if doc_discovery_matches >= 1:
            return IntentClassification(
                intent=QueryIntent.DOCUMENT_DISCOVERY,
                confidence=FAST_PATH_CONFIDENCE,
                required_engines=[EngineType.DOCUMENT_DISCOVERY],
                reasoning=f"Fast-path: Detected {doc_discovery_matches} document discovery keyword(s)",
            )

        # Check entity lookup patterns
        entity_matches = sum(
            1 for pattern in ENTITY_LOOKUP_PATTERNS if pattern.search(query)
        )
        if entity_matches >= 1:
            # Entity lookup also uses RAG for context
            return IntentClassification(
                intent=QueryIntent.ENTITY_LOOKUP,
                confidence=FAST_PATH_CONFIDENCE,
                required_engines=[EngineType.ENTITY_LOOKUP, EngineType.RAG],
                reasoning=f"Fast-path: Detected {entity_matches} entity lookup keyword(s)",
            )

        # Check citation patterns
        citation_matches = sum(
            1 for pattern in CITATION_PATTERNS if pattern.search(query)
        )
        if citation_matches >= 1:
            # Strong citation signal
            return IntentClassification(
                intent=QueryIntent.CITATION,
                confidence=FAST_PATH_CONFIDENCE,
                required_engines=[EngineType.CITATION],
                reasoning=f"Fast-path: Detected {citation_matches} citation keyword(s)",
            )

        # Check timeline patterns
        timeline_matches = sum(
            1 for pattern in TIMELINE_PATTERNS if pattern.search(query)
        )
        if timeline_matches >= 1:
            return IntentClassification(
                intent=QueryIntent.TIMELINE,
                confidence=FAST_PATH_CONFIDENCE,
                required_engines=[EngineType.TIMELINE],
                reasoning=f"Fast-path: Detected {timeline_matches} timeline keyword(s)",
            )

        # Check contradiction patterns
        contradiction_matches = sum(
            1 for pattern in CONTRADICTION_PATTERNS if pattern.search(query)
        )
        if contradiction_matches >= 1:
            return IntentClassification(
                intent=QueryIntent.CONTRADICTION,
                confidence=FAST_PATH_CONFIDENCE,
                required_engines=[EngineType.CONTRADICTION],
                reasoning=f"Fast-path: Detected {contradiction_matches} contradiction keyword(s)",
            )

        # No fast-path match - need LLM
        return None

    async def _llm_classification(
        self, query: str
    ) -> tuple[IntentClassification, IntentAnalysisCost]:
        """Classify query intent using GPT-3.5 with circuit breaker.

        Task 4.3: Use LLM for complex queries that don't match fast-path.
        Story 13.2: Circuit breaker protection with RAG fallback.

        Args:
            query: User's query.

        Returns:
            Tuple of (classification, cost).
            Falls back to RAG with low confidence if circuit is open.

        Raises:
            IntentAnalyzerError: If classification fails after retries.
        """
        user_prompt = format_intent_prompt(query)

        try:
            # Call OpenAI with circuit breaker protection
            response_text, input_tokens, output_tokens = await self._call_openai_chat(
                user_prompt
            )

            # Track cost
            cost = IntentAnalysisCost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                llm_call_made=True,
            )
            cost.calculate_cost()

            # Parse response
            classification = self._parse_classification_response(response_text)

            logger.debug(
                "llm_classification_success",
                intent=classification.intent.value,
                confidence=classification.confidence,
            )

            return classification, cost

        except CircuitOpenError as e:
            # Fallback: default to RAG engine with warning
            logger.warning(
                "intent_circuit_open_fallback",
                circuit_name=e.circuit_name,
                cooldown_remaining=e.cooldown_remaining,
                fallback="RAG engine",
            )
            return (
                IntentClassification(
                    intent=QueryIntent.RAG_SEARCH,
                    confidence=FALLBACK_CONFIDENCE,
                    required_engines=[EngineType.RAG],
                    reasoning="Circuit open - defaulting to RAG search (degraded mode)",
                ),
                IntentAnalysisCost(llm_call_made=False),
            )

        except OpenAIConfigurationError:
            raise

        except Exception as e:
            logger.error(
                "llm_classification_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise IntentAnalyzerError(
                f"Intent classification failed: {e}",
                code="CLASSIFICATION_FAILED",
            ) from e

    @with_circuit_breaker(CircuitService.OPENAI_CHAT)
    async def _call_openai_chat(
        self, user_prompt: str
    ) -> tuple[str, int, int]:
        """Call OpenAI Chat API with circuit breaker protection.

        Args:
            user_prompt: Formatted user prompt.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens).
        """
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": INTENT_CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistent classification
        )

        response_text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return response_text, input_tokens, output_tokens

    def _parse_classification_response(self, response_text: str) -> IntentClassification:
        """Parse GPT-3.5 response into IntentClassification.

        Args:
            response_text: Raw JSON response from GPT-3.5.

        Returns:
            Parsed IntentClassification.

        Raises:
            IntentParseError: If response cannot be parsed.
        """
        try:
            parsed = json.loads(response_text)

            # Validate response
            validation_errors = validate_intent_response(parsed)
            if validation_errors:
                logger.warning(
                    "classification_response_validation_failed",
                    errors=validation_errors,
                    response_preview=response_text[:200] if response_text else "",
                )
                # Continue with defaults for graceful degradation

            # Parse intent
            intent_str = parsed.get("intent", "rag_search").lower()
            intent = QueryIntent(intent_str)

            # Parse engines
            engine_strs = parsed.get("required_engines", ["rag"])
            engines = []
            for e in engine_strs:
                # Normalize engine names
                e_normalized = e.lower().replace("rag_search", "rag")
                try:
                    engines.append(EngineType(e_normalized))
                except ValueError:
                    # Default to RAG if unknown engine
                    engines.append(EngineType.RAG)

            if not engines:
                engines = [EngineType.RAG]

            return IntentClassification(
                intent=intent,
                confidence=float(parsed.get("confidence", 0.5)),
                required_engines=engines,
                reasoning=parsed.get("reasoning", ""),
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "classification_response_json_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else "",
            )
            raise IntentParseError(f"Invalid JSON response: {e}") from e

        except (KeyError, ValueError) as e:
            logger.warning(
                "classification_response_parse_error",
                error=str(e),
            )
            raise IntentParseError(f"Failed to parse classification: {e}") from e

    def _apply_multi_engine_fallback(
        self, classification: IntentClassification
    ) -> IntentClassification:
        """Apply multi-engine fallback to ensure RAG context for all queries.

        Task 4.4: ALWAYS add RAG for document-grounded answers.

        All queries benefit from RAG context, regardless of confidence:
        - Entity lookup: RAG provides document context about the entity
        - Timeline: RAG provides narrative around events
        - Citation: RAG provides context for legal references
        - Contradiction: RAG provides surrounding text for analysis

        Args:
            classification: Original classification.

        Returns:
            Updated classification with RAG always included.
        """
        engines = list(classification.required_engines)

        # ALWAYS add RAG for document-grounded answers
        # This ensures all responses include context from the actual documents
        if EngineType.RAG not in engines:
            engines.append(EngineType.RAG)

            logger.debug(
                "rag_always_added",
                original_intent=classification.intent.value,
                confidence=classification.confidence,
                engines=[e.value for e in engines],
            )

        # Update reasoning based on confidence
        if classification.confidence < LOW_CONFIDENCE_THRESHOLD:
            reasoning = f"{classification.reasoning} (Low confidence + RAG context)"
        else:
            reasoning = f"{classification.reasoning} (+ RAG context for document grounding)"

        return IntentClassification(
            intent=QueryIntent.MULTI_ENGINE if len(engines) > 1 else classification.intent,
            confidence=classification.confidence,
            required_engines=engines,
            reasoning=reasoning,
        )


# =============================================================================
# Service Factory (Task 3.5)
# =============================================================================


@lru_cache(maxsize=1)
def get_intent_analyzer() -> IntentAnalyzer:
    """Get singleton intent analyzer instance.

    Returns:
        IntentAnalyzer instance.
    """
    return IntentAnalyzer()


# =============================================================================
# Multi-Intent Pattern Registry (Extracts ALL matches)
# =============================================================================

# Intent patterns with confidence weights - extracts ALL matches, not first match
INTENT_PATTERNS: dict[EngineType, list[tuple[re.Pattern, float]]] = {
    EngineType.DOCUMENT_DISCOVERY: [
        (re.compile(r"\bwhat\s+(documents?|files?)\b", re.IGNORECASE), 0.95),
        (re.compile(r"\blist\s*(of\s*)?(all\s*)?(the\s*)?(documents?|files?)\b", re.IGNORECASE), 0.95),
        (re.compile(r"\bwhich\s+(documents?|files?)\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bhow\s+many\s+(documents?|files?|pages?)\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bexhibits?\b", re.IGNORECASE), 0.8),
    ],
    EngineType.ENTITY_LOOKUP: [
        (re.compile(r"\bwho\s+is\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bwho\s+are\s+(the\s+)?(parties?|respondents?|applicants?)\b", re.IGNORECASE), 0.95),
        (re.compile(r"\b(parties?|respondents?|applicants?|petitioners?)\s+(involved|in\s+this)\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bwho\s+(filed|initiated|brought)\b", re.IGNORECASE), 0.85),
        (re.compile(r"\brelationship\s+(between|of)\b", re.IGNORECASE), 0.8),
    ],
    EngineType.CITATION: [
        (re.compile(r"\b(cite|citation|citations?)\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bsection\s+\d+", re.IGNORECASE), 0.9),
        (re.compile(r"\bacts?\s+(of\s+)?\d{4}\b", re.IGNORECASE), 0.85),
        (re.compile(r"\b(statute|statutory|provisions?)\b", re.IGNORECASE), 0.8),
        (re.compile(r"\blegal\s+reference", re.IGNORECASE), 0.7),
    ],
    EngineType.TIMELINE: [
        (re.compile(r"\btimeline\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bchronolog(y|ical|ically)?\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bsequence\s+(of\s+)?events?\b", re.IGNORECASE), 0.85),
        (re.compile(r"\bwhen\s+(did|was)\b", re.IGNORECASE), 0.7),
        (re.compile(r"\b(dates?|order\s+of)\b", re.IGNORECASE), 0.6),
    ],
    EngineType.CONTRADICTION: [
        (re.compile(r"\bcontradictions?\b", re.IGNORECASE), 0.9),
        (re.compile(r"\binconsisten(t|cy|cies)\b", re.IGNORECASE), 0.9),
        (re.compile(r"\bconflicts?\b", re.IGNORECASE), 0.8),
        (re.compile(r"\b(differ|dispute|discrepanc)", re.IGNORECASE), 0.7),
        (re.compile(r"\bdisagree", re.IGNORECASE), 0.7),
    ],
    EngineType.RAG: [
        (re.compile(r"\b(summarize|summary)\b", re.IGNORECASE), 0.8),
        (re.compile(r"\bwhat\s+(is|are|was|were)\b", re.IGNORECASE), 0.7),
        (re.compile(r"\bexplain\b", re.IGNORECASE), 0.7),
        (re.compile(r"\btell\s+me\s+about\b", re.IGNORECASE), 0.7),
        (re.compile(r"\b(search|find|look\s+for)\b", re.IGNORECASE), 0.6),
    ],
}

# Comprehensive analysis patterns - triggers ALL engines
COMPREHENSIVE_PATTERNS = [
    re.compile(r"\b(complete|full|comprehensive)\s+(analysis|review|report)", re.IGNORECASE),
    re.compile(r"\b(all|everything)\s+(about|regarding)", re.IGNORECASE),
    re.compile(r"(summarize|summary).+(citation|timeline|contradiction)", re.IGNORECASE),
    re.compile(r"\band\b.+\band\b.+\band\b", re.IGNORECASE),  # Multiple "and" conjunctions
]


# =============================================================================
# Compound Intent Definitions
# =============================================================================

# Compound intent definitions - semantic relationships between intents
COMPOUND_INTENTS: dict[frozenset[EngineType], CompoundIntent] = {
    frozenset({EngineType.CONTRADICTION, EngineType.TIMELINE}): CompoundIntent(
        name="temporal_contradictions",
        primary_engine=EngineType.CONTRADICTION,
        supporting_engines=[EngineType.TIMELINE],
        aggregation_strategy="weave",
    ),
    frozenset({EngineType.CITATION, EngineType.RAG}): CompoundIntent(
        name="cited_search",
        primary_engine=EngineType.RAG,
        supporting_engines=[EngineType.CITATION],
        aggregation_strategy="weave",
    ),
    frozenset({EngineType.TIMELINE, EngineType.RAG}): CompoundIntent(
        name="chronological_summary",
        primary_engine=EngineType.RAG,
        supporting_engines=[EngineType.TIMELINE],
        aggregation_strategy="sequential",
    ),
    frozenset({EngineType.CONTRADICTION, EngineType.RAG}): CompoundIntent(
        name="contradiction_summary",
        primary_engine=EngineType.CONTRADICTION,
        supporting_engines=[EngineType.RAG],
        aggregation_strategy="weave",
    ),
    # Entity lookup should use ENTITY_LOOKUP as primary, not RAG
    frozenset({EngineType.ENTITY_LOOKUP, EngineType.RAG}): CompoundIntent(
        name="entity_details",
        primary_engine=EngineType.ENTITY_LOOKUP,
        supporting_engines=[EngineType.RAG],
        aggregation_strategy="weave",
    ),
}


# =============================================================================
# Multi-Intent Analyzer (Redesigned)
# =============================================================================


class MultiIntentAnalyzer:
    """Redesigned intent analyzer supporting multi-intent classification.

    Story 6-1 Enhancement: Multi-Intent Classification Redesign

    Key differences from IntentAnalyzer:
    1. Extracts ALL matching intent signals (not first-match)
    2. Detects comprehensive analysis requests
    3. Identifies compound intents (semantic relationships)
    4. Uses LLM refinement only when needed (ambiguous cases)
    5. Always includes RAG fallback for low-confidence queries

    Example:
        >>> analyzer = MultiIntentAnalyzer()
        >>> result = await analyzer.classify(
        ...     "Give me a complete analysis: summarize, list citations, timeline"
        ... )
        >>> result.is_multi_intent
        True
        >>> len(result.required_engines)
        4
    """

    def __init__(self, llm_client=None) -> None:
        """Initialize multi-intent analyzer.

        Args:
            llm_client: Optional OpenAI client for LLM refinement.
                        If None, will create when needed.
        """
        self._llm = llm_client
        self._client = None
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_intent_model

    @property
    def client(self):
        """Get or create OpenAI client for LLM refinement."""
        if self._llm is not None:
            return self._llm
        if self._client is None:
            if not self.api_key:
                return None  # LLM refinement unavailable
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except Exception as e:
                logger.warning("multi_intent_llm_init_failed", error=str(e))
                return None
        return self._client

    async def classify(self, query: str) -> MultiIntentClassification:
        """Main entry point for query classification.

        Flow:
        1. Extract all intent signals from patterns
        2. Check for comprehensive analysis request
        3. Determine if LLM refinement needed
        4. Detect compound intents
        5. Apply RAG fallback for ambiguous queries

        Args:
            query: User's natural language query.

        Returns:
            MultiIntentClassification with all detected signals.
        """
        query = query.strip()
        start_time = time.time()

        logger.info(
            "multi_intent_classify_start",
            query_length=len(query),
        )

        # Stage 1: Extract all intent signals from patterns
        signals = self._extract_all_signals(query)

        # Stage 1b: Check for comprehensive analysis request
        if self._is_comprehensive_request(query):
            result = self._build_comprehensive_classification(query)
            processing_time = int((time.time() - start_time) * 1000)
            logger.info(
                "multi_intent_comprehensive_detected",
                engines=[e.value for e in result.required_engines],
                processing_time_ms=processing_time,
            )
            return result

        # Stage 2: Determine if LLM refinement needed
        needs_llm = self._needs_llm_refinement(signals)

        if needs_llm and self.client:
            signals = await self._llm_refine_signals(query, signals)

        # Stage 3: Detect compound intents
        compound = self._detect_compound_intent(signals)

        # Stage 4: Ensure RAG fallback for ambiguous queries
        signals = self._apply_rag_fallback(signals)

        result = MultiIntentClassification(
            signals=signals,
            compound_intent=compound,
            reasoning=self._build_reasoning(signals, compound),
            llm_was_used=needs_llm and self.client is not None,
        )

        processing_time = int((time.time() - start_time) * 1000)
        logger.info(
            "multi_intent_classify_complete",
            is_multi_intent=result.is_multi_intent,
            engines=[e.value for e in result.required_engines],
            compound_intent=compound.name if compound else None,
            aggregation_strategy=result.aggregation_strategy,
            processing_time_ms=processing_time,
        )

        return result

    def _extract_all_signals(self, query: str) -> list[IntentSignal]:
        """Extract ALL matching intent signals, not just first match.

        Args:
            query: User's query.

        Returns:
            List of all detected IntentSignals with confidence scores.
        """
        signals: list[IntentSignal] = []

        for engine, patterns in INTENT_PATTERNS.items():
            best_confidence = 0.0
            best_pattern: str | None = None

            for pattern, confidence in patterns:
                if pattern.search(query) and confidence > best_confidence:
                    best_confidence = confidence
                    best_pattern = pattern.pattern

            if best_confidence > 0:
                signals.append(
                    IntentSignal(
                        engine=engine,
                        confidence=best_confidence,
                        source=IntentSource.PATTERN,
                        pattern_matched=best_pattern,
                    )
                )

        return signals

    def _is_comprehensive_request(self, query: str) -> bool:
        """Check if user wants all engines.

        Args:
            query: User's query.

        Returns:
            True if comprehensive analysis is requested.
        """
        return any(p.search(query) for p in COMPREHENSIVE_PATTERNS)

    def _build_comprehensive_classification(
        self, query: str
    ) -> MultiIntentClassification:
        """Return classification requesting ALL engines.

        Args:
            query: User's query.

        Returns:
            MultiIntentClassification with all four engines activated.
        """
        signals = [
            IntentSignal(EngineType.RAG, 0.9, IntentSource.COMPREHENSIVE),
            IntentSignal(EngineType.CITATION, 0.85, IntentSource.COMPREHENSIVE),
            IntentSignal(EngineType.TIMELINE, 0.85, IntentSource.COMPREHENSIVE),
            IntentSignal(EngineType.CONTRADICTION, 0.85, IntentSource.COMPREHENSIVE),
        ]
        return MultiIntentClassification(
            signals=signals,
            compound_intent=CompoundIntent(
                name="comprehensive_analysis",
                primary_engine=EngineType.RAG,
                supporting_engines=[
                    EngineType.CITATION,
                    EngineType.TIMELINE,
                    EngineType.CONTRADICTION,
                ],
                aggregation_strategy="weave",
            ),
            reasoning="User requested comprehensive analysis - all engines activated",
            llm_was_used=False,
        )

    def _needs_llm_refinement(self, signals: list[IntentSignal]) -> bool:
        """Determine if LLM should refine classification.

        LLM refinement is needed when:
        - No signals detected (uncertain)
        - Multiple high-confidence signals (ambiguous)
        - No high-confidence signals (uncertain)

        Args:
            signals: Detected intent signals.

        Returns:
            True if LLM refinement is recommended.
        """
        if not signals:
            return True

        high_confidence_count = sum(
            1 for s in signals if s.confidence >= HIGH_CONFIDENCE_THRESHOLD
        )

        # LLM needed if: multiple high-confidence OR no high-confidence
        return high_confidence_count > 1 or high_confidence_count == 0

    async def _llm_refine_signals(
        self, query: str, initial_signals: list[IntentSignal]
    ) -> list[IntentSignal]:
        """Use LLM to refine/validate intent signals.

        Args:
            query: User's query.
            initial_signals: Signals from pattern matching.

        Returns:
            Refined list of intent signals.
        """
        if not self.client:
            return initial_signals

        try:
            from app.engines.orchestrator.prompts import (
                MULTI_INTENT_CLASSIFICATION_PROMPT,
            )

            # Format initial signals for context
            signals_str = ", ".join(
                f"{s.engine.value}={s.confidence:.2f}" for s in initial_signals
            )
            if not signals_str:
                signals_str = "None detected"

            prompt = MULTI_INTENT_CLASSIFICATION_PROMPT.format(
                query=query,
                initial_signals=signals_str,
            )

            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            response_text = response.choices[0].message.content or ""
            return self._parse_llm_response(response_text, initial_signals)

        except Exception as e:
            logger.warning(
                "multi_intent_llm_refine_failed",
                error=str(e),
                fallback="using pattern signals",
            )
            return initial_signals

    def _parse_llm_response(
        self, response_text: str, fallback_signals: list[IntentSignal]
    ) -> list[IntentSignal]:
        """Parse LLM response into intent signals.

        Args:
            response_text: JSON response from LLM.
            fallback_signals: Signals to use if parsing fails.

        Returns:
            List of intent signals from LLM or fallback.
        """
        try:
            parsed = json.loads(response_text)
            intents = parsed.get("intents", [])

            signals: list[IntentSignal] = []
            for intent_data in intents:
                engine_str = intent_data.get("engine", "").lower().replace("rag_search", "rag")
                try:
                    engine = EngineType(engine_str)
                    confidence = float(intent_data.get("confidence", 0.5))
                    signals.append(
                        IntentSignal(
                            engine=engine,
                            confidence=confidence,
                            source=IntentSource.LLM,
                        )
                    )
                except (ValueError, KeyError):
                    continue

            return signals if signals else fallback_signals

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "multi_intent_llm_parse_failed",
                error=str(e),
            )
            return fallback_signals

    def _detect_compound_intent(
        self, signals: list[IntentSignal]
    ) -> CompoundIntent | None:
        """Check if signals form a known compound intent.

        Args:
            signals: Detected intent signals.

        Returns:
            CompoundIntent if detected, None otherwise.
        """
        active_engines = frozenset(
            s.engine for s in signals if s.confidence >= INCLUSION_THRESHOLD
        )

        for engine_combo, compound in COMPOUND_INTENTS.items():
            if engine_combo <= active_engines:
                return compound

        return None

    def _apply_rag_fallback(self, signals: list[IntentSignal]) -> list[IntentSignal]:
        """ALWAYS add RAG for document-grounded answers.

        Task 4.4: All queries benefit from RAG context, regardless of confidence.

        Args:
            signals: Current intent signals.

        Returns:
            Signals with RAG always included for document context.
        """
        has_rag = any(s.engine == EngineType.RAG for s in signals)

        # ALWAYS add RAG for document-grounded answers
        if not has_rag:
            max_conf = max((s.confidence for s in signals), default=0)
            signals.append(
                IntentSignal(
                    engine=EngineType.RAG,
                    confidence=0.6 if max_conf < HIGH_CONFIDENCE_THRESHOLD else 0.8,
                    source=IntentSource.FALLBACK,
                )
            )
            logger.debug(
                "rag_always_added_multi_intent",
                existing_engines=[s.engine.value for s in signals if s.engine != EngineType.RAG],
                max_confidence=max_conf,
            )

        return signals

    def _build_reasoning(
        self, signals: list[IntentSignal], compound: CompoundIntent | None
    ) -> str:
        """Build human-readable reasoning for classification.

        Args:
            signals: Detected intent signals.
            compound: Detected compound intent.

        Returns:
            Reasoning string.
        """
        parts = []

        for s in sorted(signals, key=lambda x: -x.confidence):
            parts.append(f"{s.engine.value}: {s.confidence:.0%} ({s.source.value})")

        reasoning = f"Intent signals: {', '.join(parts)}"

        if compound:
            reasoning += f" | Compound intent: {compound.name}"

        return reasoning


# =============================================================================
# Multi-Intent Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_multi_intent_analyzer() -> MultiIntentAnalyzer:
    """Get singleton multi-intent analyzer instance.

    Returns:
        MultiIntentAnalyzer instance.
    """
    return MultiIntentAnalyzer()
