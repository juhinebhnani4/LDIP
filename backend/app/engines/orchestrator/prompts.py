"""GPT-3.5 prompts for query intent classification in the Orchestrator Engine.

Story 6-1: Query Intent Analysis

Prompts for classifying user queries and routing them to appropriate engines.
Uses structured JSON output for reliable parsing.

CRITICAL: These prompts are used with GPT-3.5 per LLM routing rules.
Query normalization = simple task, cost-sensitive.
"""

# =============================================================================
# System Prompt - Sets the role and rules (Subtask 2.1)
# =============================================================================

INTENT_CLASSIFICATION_SYSTEM_PROMPT = """You are a query router for a legal document analysis system.

Your task is to classify user queries to determine which analysis engine(s) should handle them.

AVAILABLE ENGINES:
1. citation - Handles queries about Act citations, sections, legal references
2. timeline - Handles queries about chronological events, dates, sequences
3. contradiction - Handles queries specifically asking to compare statements across documents to find inconsistencies
4. rag_search - Handles general questions requiring document search

CLASSIFICATION RULES:
1. Match query intent to the most specific engine
2. "citation" for: Act references, Section numbers, statutory provisions, legal citations
3. "timeline" for: chronological order, when events happened, sequences of events, dates
4. "contradiction" for: explicitly comparing statements to find discrepancies or inconsistencies BETWEEN different documents/parties
5. "rag_search" for: general questions that don't fit above categories

IMPORTANT - RAG_SEARCH (not contradiction) for:
- General questions about the case/matter/dispute (e.g., "What is the dispute about?", "What happened?")
- Summary or overview requests (e.g., "Summarize the case", "What are the main issues?")
- Questions about facts, parties, allegations, claims
- Any question asking WHAT the content is (not comparing for inconsistencies)

IMPORTANT - CONTRADICTION only for:
- Explicit requests to find inconsistencies/contradictions between statements
- Comparing what different parties said about the same topic
- Finding where documents/witnesses disagree with each other

KEYWORD INDICATORS:
- citation: "citation", "cite", "Act", "Section", "statute", "provision", "referenced"
- timeline: "timeline", "chronological", "when", "date", "sequence", "order", "happened"
- contradiction: "contradict", "inconsistent", "conflict between", "disagree", "mismatch", "compare statements"
- rag_search: "what is", "summarize", "explain", "describe", "dispute", "case", "matter", "facts", "parties"

CONFIDENCE SCORING:
- 0.9-1.0: Query clearly matches single engine (explicit keywords)
- 0.7-0.9: Query likely matches engine (strong context clues)
- 0.5-0.7: Uncertain, might need multiple engines
- <0.5: Very uncertain, default to rag_search

Respond ONLY with valid JSON matching the required schema."""


# =============================================================================
# User Prompt Template (Subtask 2.2)
# =============================================================================

INTENT_CLASSIFICATION_USER_PROMPT = """Classify this legal query:

Query: "{query}"

Respond with JSON in this exact format:
{{
  "intent": "citation|timeline|contradiction|rag_search",
  "confidence": 0.0-1.0,
  "required_engines": ["engine_name"],
  "reasoning": "Brief explanation of classification"
}}"""


# =============================================================================
# JSON Schema for Structured Output (Subtask 2.3)
# =============================================================================

INTENT_CLASSIFICATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["citation", "timeline", "contradiction", "rag_search"],
            "description": "Primary intent detected in the query",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence score for classification",
        },
        "required_engines": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Engine(s) to invoke",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of classification decision",
        },
    },
    "required": ["intent", "confidence", "required_engines", "reasoning"],
    "additionalProperties": False,
}


# =============================================================================
# Helper Functions (Subtasks 2.4, 2.5)
# =============================================================================


def format_intent_prompt(query: str) -> str:
    """Format the user prompt for intent classification.

    Args:
        query: User's natural language query.

    Returns:
        Formatted prompt string.
    """
    return INTENT_CLASSIFICATION_USER_PROMPT.format(query=query)


def validate_intent_response(parsed: dict) -> list[str]:
    """Validate parsed GPT-3.5 response against expected schema.

    Args:
        parsed: Parsed JSON response from GPT-3.5.

    Returns:
        List of validation errors (empty if valid).
    """
    errors: list[str] = []

    # Check required fields
    required_fields = ["intent", "confidence", "required_engines", "reasoning"]
    for field in required_fields:
        if field not in parsed:
            errors.append(f"Missing required field: {field}")

    # Validate intent enum
    valid_intents = {"citation", "timeline", "contradiction", "rag_search"}
    intent = parsed.get("intent", "").lower()
    if intent and intent not in valid_intents:
        errors.append(f"Invalid intent '{intent}'. Must be one of: {valid_intents}")

    # Validate confidence range
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            conf_val = float(confidence)
            if conf_val < 0.0 or conf_val > 1.0:
                errors.append(f"Confidence {conf_val} out of range [0.0, 1.0]")
        except (TypeError, ValueError):
            errors.append(f"Invalid confidence value: {confidence}")

    # Validate required_engines is a list
    required_engines = parsed.get("required_engines")
    if required_engines is not None:
        if not isinstance(required_engines, list):
            errors.append("required_engines must be a list")
        else:
            valid_engines = {"citation", "timeline", "contradiction", "rag"}
            for engine in required_engines:
                # Normalize rag_search to rag for validation
                engine_normalized = engine.lower().replace("rag_search", "rag")
                if engine_normalized not in valid_engines:
                    errors.append(
                        f"Invalid engine '{engine}'. Must be one of: {valid_engines}"
                    )

    # Validate reasoning is a string
    reasoning = parsed.get("reasoning")
    if reasoning is not None and not isinstance(reasoning, str):
        errors.append("reasoning must be a string")

    return errors
