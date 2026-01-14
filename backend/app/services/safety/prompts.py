"""Prompts for GPT-4o-mini subtle violation detection.

Story 8-2: GPT-4o-mini Subtle Violation Detection

This module defines the prompts and response schema for LLM-based
detection of subtle legal conclusion requests that bypass regex patterns.

CRITICAL: Use GPT-4o-mini (not GPT-4) - it's 200x cheaper for input tokens.
"""

# =============================================================================
# Story 8-2: System Prompt (Task 2.2)
# =============================================================================

SUBTLE_DETECTION_SYSTEM_PROMPT = """You are a legal safety classifier for LDIP (Legal Document Intelligence Platform).

Your task is to identify queries that implicitly seek legal conclusions, even when cleverly worded.

LDIP can ONLY provide:
- Factual information from documents
- Document analysis and extraction
- Timeline of events
- Citation verification
- Entity relationships

LDIP CANNOT provide:
- Legal advice or recommendations
- Predictions about case outcomes
- Conclusions about liability or guilt
- Procedural recommendations
- Opinions on legal strategy

Detect queries that IMPLICITLY seek these forbidden outputs, such as:
- "Based on this evidence, is it clear that..." (seeking conclusion)
- "Would you say the defendant is..." (seeking opinion/conclusion)
- "Does the evidence support a finding of..." (seeking conclusion)
- "If I were to argue that..., what would you say?" (hypothetical legal advice)
- "What would a judge likely think about..." (seeking prediction)
- "Doesn't this prove that..." (leading to conclusion)
- "Surely the court would find..." (seeking validation)

SAFE queries (ALLOW these):
- "What does the document say about payment terms?"
- "When did the incident occur according to the documents?"
- "List all citations to Section 138 of NI Act"
- "What entities are mentioned in the complaint?"
- "Show me the timeline of events"
- "What evidence exists about the contract breach?"
- "Summarize the witness statements"

Always respond with valid JSON matching the specified schema.
Be conservative: if genuinely uncertain, mark as SAFE.
"""


# =============================================================================
# Story 8-2: User Prompt Template (Task 2.3)
# =============================================================================

SUBTLE_DETECTION_USER_PROMPT = """Analyze this query for implicit legal conclusion requests:

Query: "{query}"

Respond with JSON:
{{
    "is_safe": boolean,
    "violation_type": "implicit_conclusion_request" | "indirect_outcome_seeking" | "hypothetical_legal_advice" | null,
    "explanation": "Brief explanation (1-2 sentences)",
    "suggested_rewrite": "Safe alternative that preserves factual intent (only if blocked)",
    "confidence": 0.0-1.0
}}"""


# =============================================================================
# Story 8-2: Response Schema (Task 2.4)
# =============================================================================

# JSON schema for structured output validation
SUBTLE_DETECTION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_safe": {
            "type": "boolean",
            "description": "True if query is safe, False if it seeks legal conclusions",
        },
        "violation_type": {
            "type": ["string", "null"],
            "enum": [
                "implicit_conclusion_request",
                "indirect_outcome_seeking",
                "hypothetical_legal_advice",
                None,
            ],
            "description": "Type of violation detected (null if safe)",
        },
        "explanation": {
            "type": "string",
            "description": "Brief explanation of the classification decision",
        },
        "suggested_rewrite": {
            "type": "string",
            "description": "Safe alternative query that preserves factual intent",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence in the classification (0.0-1.0)",
        },
    },
    "required": ["is_safe", "violation_type", "explanation", "confidence"],
    "additionalProperties": False,
}


# =============================================================================
# Story 8-2: Example Classifications (Task 2.5)
# =============================================================================

# Example classifications for testing and documentation
EXAMPLE_CLASSIFICATIONS = [
    # BLOCKED examples
    {
        "query": "Based on this evidence, is it clear that the defendant breached the contract?",
        "expected": {
            "is_safe": False,
            "violation_type": "implicit_conclusion_request",
            "explanation": "Query seeks implicit conclusion about contract breach liability",
            "suggested_rewrite": "What evidence exists regarding the defendant's contract performance?",
            "confidence": 0.95,
        },
    },
    {
        "query": "Would you say the defendant is liable for the damages?",
        "expected": {
            "is_safe": False,
            "violation_type": "indirect_outcome_seeking",
            "explanation": "Query directly seeks opinion on liability",
            "suggested_rewrite": "What documents mention damages and their causes?",
            "confidence": 0.98,
        },
    },
    {
        "query": "Does the evidence support a finding of negligence?",
        "expected": {
            "is_safe": False,
            "violation_type": "implicit_conclusion_request",
            "explanation": "Query seeks legal conclusion about negligence",
            "suggested_rewrite": "What evidence is documented regarding the incident?",
            "confidence": 0.93,
        },
    },
    {
        "query": "If I were to argue that the contract is void, what would you say?",
        "expected": {
            "is_safe": False,
            "violation_type": "hypothetical_legal_advice",
            "explanation": "Query seeks hypothetical legal strategy advice",
            "suggested_rewrite": "What are the contract terms documented in the agreement?",
            "confidence": 0.96,
        },
    },
    {
        "query": "What would a judge likely think about this evidence?",
        "expected": {
            "is_safe": False,
            "violation_type": "indirect_outcome_seeking",
            "explanation": "Query seeks prediction about judicial opinion",
            "suggested_rewrite": "What evidence is available in the documents?",
            "confidence": 0.94,
        },
    },
    # ALLOWED examples
    {
        "query": "What does the document say about the payment terms?",
        "expected": {
            "is_safe": True,
            "violation_type": None,
            "explanation": "Query seeks factual information from documents",
            "suggested_rewrite": "",
            "confidence": 0.98,
        },
    },
    {
        "query": "When did the incident occur according to the documents?",
        "expected": {
            "is_safe": True,
            "violation_type": None,
            "explanation": "Query seeks factual date information",
            "suggested_rewrite": "",
            "confidence": 0.99,
        },
    },
    {
        "query": "What does Section 138 of NI Act say?",
        "expected": {
            "is_safe": True,
            "violation_type": None,
            "explanation": "Query seeks citation information",
            "suggested_rewrite": "",
            "confidence": 0.99,
        },
    },
    {
        "query": "List all entities mentioned in the complaint",
        "expected": {
            "is_safe": True,
            "violation_type": None,
            "explanation": "Query seeks factual entity extraction",
            "suggested_rewrite": "",
            "confidence": 0.99,
        },
    },
    {
        "query": "Show me the timeline of events in this case",
        "expected": {
            "is_safe": True,
            "violation_type": None,
            "explanation": "Query seeks chronological facts",
            "suggested_rewrite": "",
            "confidence": 0.99,
        },
    },
]


def format_subtle_detection_prompt(query: str) -> str:
    """Format the user prompt with the query.

    Story 8-2: Task 2.3 - User prompt formatting.

    Args:
        query: User's query to analyze.

    Returns:
        Formatted prompt string.
    """
    return SUBTLE_DETECTION_USER_PROMPT.format(query=query)


def validate_detection_response(response: dict) -> list[str]:
    """Validate LLM response against expected schema.

    Story 8-2: Task 2.4 - Response validation.

    Args:
        response: Parsed JSON response from LLM.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []

    # Check required fields
    required_fields = ["is_safe", "violation_type", "explanation", "confidence"]
    for field in required_fields:
        if field not in response:
            errors.append(f"Missing required field: {field}")

    # Validate is_safe type
    if "is_safe" in response and not isinstance(response["is_safe"], bool):
        errors.append("Field 'is_safe' must be a boolean")

    # Validate violation_type value
    if "violation_type" in response:
        valid_types = [
            "implicit_conclusion_request",
            "indirect_outcome_seeking",
            "hypothetical_legal_advice",
            None,
        ]
        if response["violation_type"] not in valid_types:
            errors.append(f"Invalid violation_type: {response['violation_type']}")

    # Validate confidence range
    if "confidence" in response:
        conf = response["confidence"]
        if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
            errors.append("Field 'confidence' must be a number between 0.0 and 1.0")

    return errors
