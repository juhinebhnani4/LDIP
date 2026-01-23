"""GPT-4 prompts for statement comparison in the Contradiction Engine.

Story 5-2: Statement Pair Comparison

Prompts for chain-of-thought reasoning to detect contradictions between
two statements about the same entity. Uses structured JSON output for
reliable parsing.

CRITICAL: These prompts are used with GPT-4 per LLM routing rules.
Contradiction detection is high-stakes reasoning, requiring GPT-4 quality.
"""

# =============================================================================
# System Prompt - Sets the role and rules
# =============================================================================

STATEMENT_COMPARISON_SYSTEM_PROMPT = """You are a legal analysis assistant specializing in detecting contradictions between statements in legal documents.

Your role is to compare two statements about the same entity and determine if they contradict each other.

IMPORTANT RULES:
1. Only compare the two statements provided - do not infer external context
2. A contradiction requires DIRECT conflict, not just different focus areas
3. Provide step-by-step reasoning BEFORE your verdict
4. Extract specific conflicting values (dates, amounts) when detected
5. If uncertain, classify as "uncertain" rather than forcing a verdict
6. Statements from different documents discussing different aspects are "unrelated", not contradictions

CONTRADICTION TYPES:
- date_mismatch: Same event/fact has different dates
- amount_mismatch: Same transaction/value has different amounts
- factual_conflict: Direct factual disagreement (e.g., "A owns property" vs "B owns property")
- semantic_conflict: Statements mean opposite things when analyzed
- none: No conflict detected

CLASSIFICATION GUIDE:
- contradiction: Statements DIRECTLY conflict about the same fact/event
- consistent: Statements agree or are compatible
- uncertain: Cannot determine with confidence; might conflict, might not
- unrelated: Statements discuss different topics/aspects of the entity

EXAMPLES OF CONTRADICTIONS:
1. "The loan was disbursed on 15/01/2024" vs "The loan was disbursed on 15/06/2024"
   → contradiction (date_mismatch)

2. "The property value is Rs. 50 lakhs" vs "The property was valued at Rs. 80 lakhs"
   → contradiction (amount_mismatch)

3. "Mr. Sharma signed as witness" vs "Mr. Sharma was not present at signing"
   → contradiction (factual_conflict)

EXAMPLES OF NON-CONTRADICTIONS:
1. "The loan was disbursed on 15/01/2024" vs "The first EMI was due on 15/02/2024"
   → consistent (different aspects, no conflict)

2. "Mr. Sharma is the borrower" vs "Mr. Sharma owns a house in Delhi"
   → unrelated (different topics about same entity)

You must respond ONLY with valid JSON matching the required schema."""


# =============================================================================
# User Prompt Template - Statement comparison request
# =============================================================================

STATEMENT_COMPARISON_USER_PROMPT = """Entity being discussed: {entity_name}

Statement A (from "{doc_a}", page {page_a}):
"{content_a}"

Statement B (from "{doc_b}", page {page_b}):
"{content_b}"

Compare these two statements step by step:

1. What specific claims does Statement A make about {entity_name}?
2. What specific claims does Statement B make about {entity_name}?
3. Do these claims conflict with each other? If so, exactly how?
4. What is your confidence level (0.0 to 1.0) in your assessment?

Respond with JSON in this exact format:
{{
  "reasoning": "Your step-by-step analysis explaining how you reached your conclusion...",
  "result": "contradiction|consistent|uncertain|unrelated",
  "confidence": 0.0-1.0,
  "evidence": {{
    "type": "date_mismatch|amount_mismatch|factual_conflict|semantic_conflict|none",
    "value_a": "extracted value from statement A (or null if not applicable)",
    "value_b": "extracted value from statement B (or null if not applicable)"
  }}
}}"""


# =============================================================================
# JSON Schema for Structured Output
# =============================================================================

COMPARISON_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {
            "type": "string",
            "description": "Step-by-step chain-of-thought analysis"
        },
        "result": {
            "type": "string",
            "enum": ["contradiction", "consistent", "uncertain", "unrelated"],
            "description": "Classification result"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence score"
        },
        "evidence": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["date_mismatch", "amount_mismatch", "factual_conflict", "semantic_conflict", "none"],
                    "description": "Type of evidence"
                },
                "value_a": {
                    "type": ["string", "null"],
                    "description": "Extracted value from statement A"
                },
                "value_b": {
                    "type": ["string", "null"],
                    "description": "Extracted value from statement B"
                }
            },
            "required": ["type"],
            "additionalProperties": False
        }
    },
    "required": ["reasoning", "result", "confidence", "evidence"],
    "additionalProperties": False
}


# =============================================================================
# Helper Functions
# =============================================================================


def format_comparison_prompt(
    entity_name: str,
    content_a: str,
    content_b: str,
    doc_a: str = "Document A",
    doc_b: str = "Document B",
    page_a: int | None = None,
    page_b: int | None = None,
) -> str:
    """Format the user prompt for statement comparison.

    Args:
        entity_name: Name of the entity being discussed.
        content_a: Content of statement A.
        content_b: Content of statement B.
        doc_a: Document name for statement A.
        doc_b: Document name for statement B.
        page_a: Page number for statement A.
        page_b: Page number for statement B.

    Returns:
        Formatted prompt string.
    """
    return STATEMENT_COMPARISON_USER_PROMPT.format(
        entity_name=entity_name,
        content_a=content_a,
        content_b=content_b,
        doc_a=doc_a,
        doc_b=doc_b,
        page_a=page_a if page_a is not None else "unknown",
        page_b=page_b if page_b is not None else "unknown",
    )


def validate_comparison_response(parsed: dict) -> list[str]:
    """Validate parsed GPT-4 response against expected schema.

    Args:
        parsed: Parsed JSON response from GPT-4.

    Returns:
        List of validation errors (empty if valid).
    """
    errors: list[str] = []

    # Check required fields
    required_fields = ["reasoning", "result", "confidence", "evidence"]
    for field in required_fields:
        if field not in parsed:
            errors.append(f"Missing required field: {field}")

    # Validate result enum
    valid_results = {"contradiction", "consistent", "uncertain", "unrelated"}
    result = parsed.get("result", "").lower()
    if result and result not in valid_results:
        errors.append(f"Invalid result '{result}'. Must be one of: {valid_results}")

    # Validate confidence range
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            conf_val = float(confidence)
            if conf_val < 0.0 or conf_val > 1.0:
                errors.append(f"Confidence {conf_val} out of range [0.0, 1.0]")
        except (TypeError, ValueError):
            errors.append(f"Invalid confidence value: {confidence}")

    # Validate evidence
    evidence = parsed.get("evidence", {})
    if isinstance(evidence, dict):
        evidence_type = evidence.get("type", "").lower()
        valid_types = {"date_mismatch", "amount_mismatch", "factual_conflict", "semantic_conflict", "none"}
        if evidence_type and evidence_type not in valid_types:
            errors.append(f"Invalid evidence type '{evidence_type}'. Must be one of: {valid_types}")
    else:
        errors.append("Evidence must be an object")

    return errors


# =============================================================================
# Classification Enhancement Prompts (Story 5-3)
# =============================================================================

CLASSIFICATION_ENHANCEMENT_SYSTEM_PROMPT = """You are a legal analysis assistant specializing in classifying contradictions between statements.

Your task is to analyze a detected contradiction and determine its classification type.

CLASSIFICATION TYPES (in priority order):
1. date_mismatch - Statements disagree on when something occurred
2. amount_mismatch - Statements disagree on monetary values, quantities, or measurements
3. factual_contradiction - Direct factual disagreement about a verifiable fact
4. semantic_contradiction - Statements mean opposite things semantically, but not about specific facts

RULES:
1. Prioritize specific classifications (date, amount) over general ones (factual, semantic)
2. If dates or amounts are mentioned but are the SAME, it's NOT a date/amount mismatch
3. semantic_contradiction is used when statements conflict in meaning but not on specific verifiable facts
4. Provide a clear, attorney-friendly explanation of the conflict

You must respond ONLY with valid JSON matching the required schema."""

CLASSIFICATION_ENHANCEMENT_USER_PROMPT = """Analyze this contradiction and classify it:

Statement A:
"{content_a}"

Statement B:
"{content_b}"

Original reasoning (from comparison):
"{reasoning}"

Please classify this contradiction and provide:
1. The most specific contradiction type that applies
2. A clear explanation suitable for attorney review
3. Your confidence in this classification

Respond with JSON in this exact format:
{{
  "contradiction_type": "date_mismatch|amount_mismatch|factual_contradiction|semantic_contradiction",
  "explanation": "Clear explanation of the conflict for attorney review...",
  "confidence": 0.0-1.0
}}"""


def format_classification_prompt(
    content_a: str,
    content_b: str,
    reasoning: str,
) -> str:
    """Format the user prompt for classification enhancement.

    Story 5-3: Used when rule-based classification fails and LLM fallback is needed.

    Args:
        content_a: Content of statement A.
        content_b: Content of statement B.
        reasoning: Original reasoning from comparison.

    Returns:
        Formatted prompt string.
    """
    return CLASSIFICATION_ENHANCEMENT_USER_PROMPT.format(
        content_a=content_a,
        content_b=content_b,
        reasoning=reasoning,
    )


def validate_classification_response(parsed: dict) -> list[str]:
    """Validate parsed GPT-4 classification response.

    Args:
        parsed: Parsed JSON response from GPT-4.

    Returns:
        List of validation errors (empty if valid).
    """
    errors: list[str] = []

    # Check required fields
    required_fields = ["contradiction_type", "explanation", "confidence"]
    for field in required_fields:
        if field not in parsed:
            errors.append(f"Missing required field: {field}")

    # Validate contradiction_type enum
    valid_types = {
        "date_mismatch",
        "amount_mismatch",
        "factual_contradiction",
        "semantic_contradiction",
    }
    contradiction_type = parsed.get("contradiction_type", "").lower()
    if contradiction_type and contradiction_type not in valid_types:
        errors.append(
            f"Invalid contradiction_type '{contradiction_type}'. Must be one of: {valid_types}"
        )

    # Validate confidence range
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            conf_val = float(confidence)
            if conf_val < 0.0 or conf_val > 1.0:
                errors.append(f"Confidence {conf_val} out of range [0.0, 1.0]")
        except (TypeError, ValueError):
            errors.append(f"Invalid confidence value: {confidence}")

    return errors


# =============================================================================
# Gemini Screening Prompts (Cost Optimization - Two-Tier Routing)
# =============================================================================

GEMINI_SCREENING_SYSTEM_PROMPT = """You are a fast legal screening assistant. Your job is to QUICKLY determine if two statements potentially conflict.

You do NOT need detailed analysis. Just quickly check:
1. Do the statements discuss the SAME topic/fact about the entity?
2. If yes, do they appear to conflict or agree?

CLASSIFICATION (be conservative - when unsure, say "needs_review"):
- consistent: Statements clearly agree or complement each other
- unrelated: Statements discuss completely different topics
- needs_review: Statements MIGHT conflict OR you're not sure - requires expert review

IMPORTANT: It's better to flag something for review than to miss a potential contradiction.

Respond ONLY with valid JSON."""

GEMINI_SCREENING_USER_PROMPT = """Entity: {entity_name}

Statement A: "{content_a}"

Statement B: "{content_b}"

Quick assessment - do these statements conflict?

Respond with JSON:
{{
  "result": "consistent|unrelated|needs_review",
  "confidence": 0.0-1.0,
  "quick_reason": "One sentence explanation"
}}"""


def format_screening_prompt(
    entity_name: str,
    content_a: str,
    content_b: str,
) -> str:
    """Format the user prompt for Gemini screening.

    Cost optimization: Quick screening before full GPT-4 analysis.

    Args:
        entity_name: Name of the entity being discussed.
        content_a: Content of statement A.
        content_b: Content of statement B.

    Returns:
        Formatted prompt string.
    """
    return GEMINI_SCREENING_USER_PROMPT.format(
        entity_name=entity_name,
        content_a=content_a,
        content_b=content_b,
    )


def validate_screening_response(parsed: dict) -> list[str]:
    """Validate parsed Gemini screening response.

    Args:
        parsed: Parsed JSON response from Gemini.

    Returns:
        List of validation errors (empty if valid).
    """
    errors: list[str] = []

    # Check required fields
    required_fields = ["result", "confidence"]
    for field in required_fields:
        if field not in parsed:
            errors.append(f"Missing required field: {field}")

    # Validate result enum
    valid_results = {"consistent", "unrelated", "needs_review"}
    result = parsed.get("result", "").lower()
    if result and result not in valid_results:
        errors.append(f"Invalid result '{result}'. Must be one of: {valid_results}")

    # Validate confidence range
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            conf_val = float(confidence)
            if conf_val < 0.0 or conf_val > 1.0:
                errors.append(f"Confidence {conf_val} out of range [0.0, 1.0]")
        except (TypeError, ValueError):
            errors.append(f"Invalid confidence value: {confidence}")

    return errors
