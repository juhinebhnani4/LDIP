"""Prompts for GPT-4o-mini safety checks.

Story 8-2: GPT-4o-mini Subtle Violation Detection
Story 8-3: GPT-4o-mini Subtle Language Policing

This module defines the prompts and response schemas for LLM-based:
- Detection of subtle legal conclusion requests that bypass regex patterns (8-2)
- Polishing of LLM outputs to remove subtle legal conclusions (8-3)

CRITICAL: Use GPT-4o-mini (not GPT-4) - it's 200x cheaper for input tokens.
"""

# =============================================================================
# Story 8-2: System Prompt (Task 2.2)
# =============================================================================

SUBTLE_DETECTION_SYSTEM_PROMPT = """You are a legal safety classifier for LDIP (Legal Document Intelligence Platform).

Your task is to identify queries that ask the AI to MAKE legal conclusions or provide legal advice.

CRITICAL DISTINCTION - READ CAREFULLY:
- BLOCK: Queries asking AI to MAKE a legal judgment ("Is the defendant liable?", "Should I appeal?")
- ALLOW: Queries asking WHAT DOCUMENTS SAY about legal matters ("What do documents say about liability?")

The key question is: Is the user asking AI for its legal opinion, OR asking what information exists in documents?

LDIP CAN provide:
- Factual information from documents about ANY topic (including legal matters)
- Document analysis and extraction
- What documents say about scope of authority, compliance, actions taken
- Timeline of events
- Citation verification
- Entity relationships
- Summary of what documents state

LDIP CANNOT provide:
- AI's own legal conclusions or judgments
- Recommendations about what action to take
- Predictions about case outcomes
- AI's opinion on liability or guilt

BLOCK these (asking AI to conclude/advise):
- "Is the defendant liable?" (asking AI to judge)
- "Should I file an appeal?" (asking AI for advice)
- "What are my chances of winning?" (asking AI to predict)
- "Would you say he is guilty?" (asking AI's opinion)
- "Does this prove negligence?" (asking AI to determine)

ALLOW these (asking what documents say):
- "What does the document say about X's authority?"
- "Whether X's actions were authorized according to the documents?"
- "What do documents say about compliance with the Act?"
- "What evidence exists about the scope of authority?"
- "What information is available about whether actions were lawful?"
- "Summarize the documents regarding legal authority"
- "What do the case documents say about liability?"
- "If BDA did not have authority, what happened next?"
- "If the custodian exceeded powers, what actions were taken?"
- "What did the defendant do after receiving the notice?"
- "Was the property transferred according to the documents?"
- "Did the transaction comply with the requirements?"
- "What steps were taken following the breach?"

CRITICAL RULES:
1. Questions starting with "Whether..." are ALWAYS SAFE - they ask what documents say, not for AI's judgment
2. Questions starting with "If..." followed by a condition are ALWAYS SAFE - they ask about document facts or sequences
3. Questions about "scope of authority", "legal authority", "actions taken" are SAFE - they seek document facts
4. Questions asking "what do documents say about X" are ALWAYS SAFE, even if X is a legal matter
5. Questions about sequences of events ("what happened next", "what did X do after") are ALWAYS SAFE
6. Questions about document content, even if phrased as "did X happen" or "was X done", are SAFE
7. ONLY block if user explicitly asks AI to make a judgment like "Is he guilty?" or "Should I sue?"

Be EXTREMELY conservative: Default to SAFE. Only block the clearest, most explicit requests for AI's own legal opinion/advice.
When in doubt, mark as SAFE - false negatives are acceptable, false positives frustrate users.
"""


# =============================================================================
# Story 8-2: User Prompt Template (Task 2.3)
# =============================================================================

SUBTLE_DETECTION_USER_PROMPT = """Analyze this query for implicit legal conclusion requests:

Query: "{query}"

IMPORTANT: Be EXTREMELY conservative. Most queries are SAFE. Only flag obvious requests for AI's legal opinion.

Questions about:
- Document content ("what does X say", "what happened", "what did X do")
- Sequences of events ("what happened next", "after X, what")
- Conditions ("If X, then what", "Whether X happened")
- Document facts (even about legal topics like authority, compliance, actions)

Are ALL SAFE - they ask about documents, not for AI's judgment.

ONLY flag queries that explicitly ask AI to:
- Judge guilt/liability ("Is he guilty?", "Is she liable?")
- Give legal advice ("Should I sue?", "Should I appeal?")
- Predict outcomes ("Will I win?", "What are my chances?")

For suggested_rewrite (only if blocking):
- PRESERVE the original intent and specificity
- Keep the same entities, events, and context mentioned
- Just remove the request for AI judgment
- Example: "Is the defendant liable for the breach?" -> "What do the documents say about the defendant's role in the breach?"
- If you can't rewrite while preserving intent, mark as SAFE instead

Respond with JSON:
{{
    "is_safe": boolean,
    "violation_type": "implicit_conclusion_request" | "indirect_outcome_seeking" | "hypothetical_legal_advice" | null,
    "explanation": "Brief explanation (1-2 sentences)",
    "suggested_rewrite": "Rewrite that PRESERVES the original question's specific intent and entities",
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
            # L3 Fix: JSON Schema uses "null" string, not Python None
            "type": ["string", "null"],
            "enum": [
                "implicit_conclusion_request",
                "indirect_outcome_seeking",
                "hypothetical_legal_advice",
                "null",  # JSON null as string for enum compatibility
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


# =============================================================================
# Story 8-3: Subtle Policing System Prompt (Task 5.1)
# =============================================================================

SUBTLE_POLICING_SYSTEM_PROMPT = """You are a legal language editor for LDIP (Legal Document Intelligence Platform).

Your task is to identify and rephrase any remaining legal conclusions in the text that were not caught by automated regex patterns.

CRITICAL RULES:
1. LDIP can ONLY present factual observations from documents
2. LDIP CANNOT make legal conclusions, predictions, or advice
3. ALL definitive legal language must be softened to tentative language

TRANSFORM these patterns:
- Definitive statements → Observations ("is guilty" → "may face liability regarding")
- Predictions → Possibilities ("will win" → "may have grounds for")
- Conclusions → Suggestions ("this proves" → "this may indicate")
- Advice → Information ("you should" → "options include")
- Certainty → Possibility ("clearly" → "appears to", "must" → "may")
- Judgment → Observation ("defendant committed" → "regarding potential")

PRESERVE (do NOT modify):
- Direct quotes (text in quotation marks "..." or '...')
- Citation references (e.g., "As stated in Exhibit A, page 5")
- Factual statements without legal conclusions
- Numerical data, dates, and proper nouns
- Document names and references

OUTPUT REQUIREMENTS:
- Return the COMPLETE sanitized text, preserving all content
- Only modify problematic phrases, keep everything else verbatim
- Maintain original formatting and structure
- If text is already properly sanitized, return it unchanged

Respond with JSON:
{
    "sanitized_text": "The fully sanitized text",
    "changes_made": [
        {"original": "exact phrase removed", "replacement": "exact replacement used"},
        ...
    ],
    "confidence": 0.0-1.0
}

IMPORTANT: Each change must include the exact "original" phrase and its "replacement".
If text is already properly sanitized, return it unchanged with empty changes_made array."""


# =============================================================================
# Story 8-3: Subtle Policing User Prompt Template (Task 5.2)
# =============================================================================

SUBTLE_POLICING_USER_PROMPT = """Review and sanitize this text for any remaining legal conclusions:

Text: \"\"\"{text}\"\"\"

Respond with JSON containing the sanitized version. Preserve quotes and citations."""


# =============================================================================
# Story 8-3: Subtle Policing Response Schema (Task 5.2)
# =============================================================================

SUBTLE_POLICING_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "sanitized_text": {
            "type": "string",
            "description": "The fully sanitized text with legal conclusions removed",
        },
        "changes_made": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original": {
                        "type": "string",
                        "description": "The exact original phrase that was replaced",
                    },
                    "replacement": {
                        "type": "string",
                        "description": "The exact replacement phrase used",
                    },
                },
                "required": ["original", "replacement"],
            },
            "description": "List of specific changes with original and replacement phrases",
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence in the sanitization (0.0-1.0)",
        },
    },
    "required": ["sanitized_text", "changes_made", "confidence"],
    "additionalProperties": False,
}


def format_subtle_policing_prompt(text: str) -> str:
    """Format the user prompt for subtle policing.

    Story 8-3: Task 5.2 - User prompt formatting.

    Args:
        text: LLM output text to analyze and sanitize.

    Returns:
        Formatted prompt string.
    """
    return SUBTLE_POLICING_USER_PROMPT.format(text=text)


def validate_policing_response(response: dict) -> list[str]:
    """Validate LLM policing response against expected schema.

    Story 8-3: Task 5.2 - Response validation.

    Args:
        response: Parsed JSON response from LLM.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []

    # Check required fields
    required_fields = ["sanitized_text", "changes_made", "confidence"]
    for field in required_fields:
        if field not in response:
            errors.append(f"Missing required field: {field}")

    # Validate sanitized_text type
    if "sanitized_text" in response and not isinstance(response["sanitized_text"], str):
        errors.append("Field 'sanitized_text' must be a string")

    # Validate changes_made type (H2 fix: now expects list of {original, replacement})
    if "changes_made" in response:
        if not isinstance(response["changes_made"], list):
            errors.append("Field 'changes_made' must be a list")
        else:
            for i, item in enumerate(response["changes_made"]):
                # Support both old string format (backward compat) and new structured format
                if isinstance(item, str):
                    continue  # Allow string for backward compatibility
                if not isinstance(item, dict):
                    errors.append(f"Item {i} in 'changes_made' must be an object or string")
                elif "original" not in item or "replacement" not in item:
                    errors.append(f"Item {i} in 'changes_made' must have 'original' and 'replacement'")

    # Validate confidence range
    if "confidence" in response:
        conf = response["confidence"]
        if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
            errors.append("Field 'confidence' must be a number between 0.0 and 1.0")

    return errors
