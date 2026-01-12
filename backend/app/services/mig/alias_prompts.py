"""Gemini prompts for contextual alias analysis.

Defines prompts for using Gemini Flash to analyze document context
and determine if two name mentions refer to the same entity.

CRITICAL: Uses Gemini for contextual analysis per LLM routing rules -
this is a pattern matching task, NOT user-facing reasoning.
"""

# =============================================================================
# System Prompt for Contextual Alias Analysis
# =============================================================================

ALIAS_CONTEXT_SYSTEM_PROMPT = """You are analyzing whether two name mentions in legal documents refer to the same person or organization.

Your task is to determine if NAME 1 and NAME 2 refer to the same entity based on the surrounding context.

IMPORTANT RULES:
1. Look for consistent roles (both plaintiff, both from same company, etc.)
2. Check for consistent descriptions (both described as "director", etc.)
3. Be cautious with very common names - require stronger evidence
4. If contexts are too limited or ambiguous, set confidence < 0.5
5. Consider if one could be a variant/alias of the other (initials, title variations)
6. Consider Indian naming conventions (patronymics like "Dineshbhai", honorifics like "Shri")

OUTPUT FORMAT (strict JSON):
{
  "same_entity": true | false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation (max 50 words)",
  "indicators": ["list", "of", "evidence"]
}

Do NOT include any text outside the JSON object."""


# =============================================================================
# User Prompt Template for Contextual Alias Analysis
# =============================================================================

ALIAS_CONTEXT_USER_PROMPT = """Analyze if these two names refer to the same entity:

CONTEXT 1:
{context1}

NAME 1: {name1}

---

CONTEXT 2:
{context2}

NAME 2: {name2}

---

Analyze the contexts and determine if these names refer to the same entity. Output ONLY valid JSON."""


# =============================================================================
# Batch Analysis Prompt (for multiple pairs)
# =============================================================================

ALIAS_BATCH_SYSTEM_PROMPT = """You are analyzing multiple name pairs from legal documents to determine which pairs refer to the same entity.

For each pair, analyze the provided context and determine if the two names refer to the same person or organization.

IMPORTANT RULES:
1. Look for consistent roles (both plaintiff, both from same company, etc.)
2. Check for consistent descriptions (both described as "director", etc.)
3. Be cautious with very common names - require stronger evidence
4. If contexts are too limited or ambiguous, set confidence < 0.5
5. Consider name variants (initials, titles, honorifics)
6. Consider Indian naming conventions (patronymics, honorifics like "Shri", "Smt")

OUTPUT FORMAT (strict JSON array):
[
  {
    "pair_id": "pair_0",
    "same_entity": true | false,
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
  },
  ...
]

Do NOT include any text outside the JSON array."""


ALIAS_BATCH_USER_PROMPT = """Analyze these name pairs from legal documents:

{pairs_text}

For each pair, determine if the names refer to the same entity. Output ONLY valid JSON array."""


# =============================================================================
# Pair Text Formatter
# =============================================================================

PAIR_TEXT_TEMPLATE = """--- Pair {pair_id} ---
CONTEXT 1: {context1}
NAME 1: {name1}

CONTEXT 2: {context2}
NAME 2: {name2}
"""


def format_pairs_for_batch(
    pairs: list[dict],
) -> str:
    """Format multiple name pairs for batch analysis.

    Args:
        pairs: List of dicts with keys: pair_id, name1, context1, name2, context2

    Returns:
        Formatted text for batch prompt.
    """
    formatted_pairs = []
    for pair in pairs:
        formatted_pairs.append(
            PAIR_TEXT_TEMPLATE.format(
                pair_id=pair.get("pair_id", "unknown"),
                name1=pair.get("name1", ""),
                context1=pair.get("context1", "(no context available)"),
                name2=pair.get("name2", ""),
                context2=pair.get("context2", "(no context available)"),
            )
        )
    return "\n".join(formatted_pairs)
