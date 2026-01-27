"""Fuzzy matching utilities for entity name resolution.

Provides hybrid matching: exact substring first, fuzzy fallback.
Uses rapidfuzz for high-performance fuzzy string matching.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz


@dataclass
class FuzzyMatchResult:
    """Result of a fuzzy match operation."""

    matched: bool
    matched_name: str  # The name that was matched (canonical or alias)
    score: float  # 0-100, higher is better
    is_exact: bool  # True if exact substring match, False if fuzzy


# Default threshold for fuzzy matching (0-100)
# 85 is conservative - requires high similarity to avoid false positives
DEFAULT_FUZZY_THRESHOLD = 85


def extract_name_tokens(text: str) -> list[str]:
    """Extract potential name tokens from text.

    Splits on common delimiters and filters short tokens.
    Returns lowercase tokens for matching.
    """
    # Split on whitespace and common punctuation
    import re

    tokens = re.split(r"[\s,;:\-\"'()]+", text.lower())
    # Filter out very short tokens (likely not names)
    return [t for t in tokens if len(t) >= 2]


def fuzzy_match_name(
    query: str,
    canonical_name: str,
    aliases: list[str] | None = None,
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> FuzzyMatchResult:
    """Match a name against query using hybrid exact+fuzzy approach.

    Strategy:
    1. Try exact substring match (case-insensitive) - fast, no false positives
    2. If no exact match, try fuzzy matching with threshold

    Args:
        query: The user's search query
        canonical_name: The primary/canonical entity name
        aliases: Optional list of known aliases
        threshold: Minimum fuzzy score (0-100) to consider a match

    Returns:
        FuzzyMatchResult with match details
    """
    query_lower = query.lower()
    all_names = [canonical_name] + (aliases or [])

    # Phase 1: Try exact substring match (fast path)
    for name in all_names:
        if name.lower() in query_lower:
            return FuzzyMatchResult(
                matched=True,
                matched_name=name,
                score=100.0,
                is_exact=True,
            )

    # Phase 2: Fuzzy matching fallback
    # Extract potential name phrases from query for comparison
    best_match: FuzzyMatchResult | None = None
    best_score = 0.0

    for name in all_names:
        name_lower = name.lower()

        # Use token_set_ratio - handles word order differences and partial matches
        # "nirav jobalia" vs "Nirav D. Jobalia" -> high score
        # "nirav mehta" vs "Nirav D. Jobalia" -> low score
        score = fuzz.token_set_ratio(name_lower, query_lower)

        # Also try partial_ratio for substring-like fuzzy matching
        partial_score = fuzz.partial_ratio(name_lower, query_lower)

        # Take the better of the two scores
        final_score = max(score, partial_score)

        if final_score >= threshold and final_score > best_score:
            best_score = final_score
            best_match = FuzzyMatchResult(
                matched=True,
                matched_name=name,
                score=final_score,
                is_exact=False,
            )

    if best_match:
        return best_match

    # No match found
    return FuzzyMatchResult(
        matched=False,
        matched_name="",
        score=0.0,
        is_exact=False,
    )


def fuzzy_match_entities(
    query: str,
    entities: list[tuple[str, str, list[str] | None]],  # (entity_id, canonical_name, aliases)
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> list[tuple[str, FuzzyMatchResult]]:
    """Match query against multiple entities, returning all matches.

    Args:
        query: The user's search query
        entities: List of (entity_id, canonical_name, aliases) tuples
        threshold: Minimum fuzzy score to consider a match

    Returns:
        List of (entity_id, FuzzyMatchResult) for all matches, sorted by score descending
    """
    matches: list[tuple[str, FuzzyMatchResult]] = []

    for entity_id, canonical_name, aliases in entities:
        result = fuzzy_match_name(query, canonical_name, aliases, threshold)
        if result.matched:
            matches.append((entity_id, result))

    # Sort by score descending (best matches first)
    matches.sort(key=lambda x: x[1].score, reverse=True)

    return matches
