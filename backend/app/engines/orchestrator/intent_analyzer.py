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

            logger.info(
                "analyze_intent_fast_path",
                matter_id=matter_id,
                intent=fast_path_result.intent.value,
                confidence=fast_path_result.confidence,
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
        """Apply multi-engine fallback for low-confidence classifications.

        Task 4.4: If confidence < 0.7, add RAG fallback.

        Args:
            classification: Original classification.

        Returns:
            Updated classification with potential additional engines.
        """
        if classification.confidence >= LOW_CONFIDENCE_THRESHOLD:
            return classification

        # Low confidence: add RAG fallback if not already present
        engines = list(classification.required_engines)
        if EngineType.RAG not in engines:
            engines.append(EngineType.RAG)

            logger.debug(
                "multi_engine_fallback_applied",
                original_intent=classification.intent.value,
                confidence=classification.confidence,
                engines=[e.value for e in engines],
            )

        return IntentClassification(
            intent=QueryIntent.MULTI_ENGINE if len(engines) > 1 else classification.intent,
            confidence=classification.confidence,
            required_engines=engines,
            reasoning=f"{classification.reasoning} (Low confidence: added RAG fallback)",
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
