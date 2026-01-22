"""Data loader utility for external JSON configuration files.

This module provides functions to load and cache JSON data files
for act validation, known acts, and garbage detection patterns.

Supports hot-reloading in development mode via cache clearing.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Data directory path
DATA_DIR = Path(__file__).parent.parent / "data"


class DataLoadError(Exception):
    """Exception raised when data file loading fails."""

    def __init__(self, filename: str, message: str):
        self.filename = filename
        self.message = message
        super().__init__(f"Failed to load {filename}: {message}")


@lru_cache(maxsize=10)
def load_json_data(filename: str) -> dict[str, Any]:
    """Load and cache a JSON data file.

    Args:
        filename: Name of the JSON file in the data directory.

    Returns:
        Parsed JSON data as a dictionary.

    Raises:
        DataLoadError: If file cannot be loaded or parsed.
    """
    path = DATA_DIR / filename

    if not path.exists():
        logger.warning(f"Data file not found: {filename}, using defaults")
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Loaded data file: {filename}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in {filename}: {e}")
        raise DataLoadError(filename, f"Invalid JSON: {e}") from e
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        raise DataLoadError(filename, str(e)) from e


def clear_data_cache() -> None:
    """Clear all cached data files.

    Useful for development when data files are modified.
    """
    load_json_data.cache_clear()
    _get_known_acts_mapping.cache_clear()
    _get_garbage_patterns_compiled.cache_clear()
    logger.info("Data cache cleared")


# =============================================================================
# Known Acts Data
# =============================================================================


@lru_cache(maxsize=1)
def _get_known_acts_mapping() -> dict[str, tuple[str, str]]:
    """Internal cached loader for known acts mapping."""
    data = load_json_data("known_acts.json")

    if not data or "acts" not in data:
        logger.warning("known_acts.json not found or empty, using empty mapping")
        return {}

    mapping: dict[str, tuple[str, str]] = {}
    for act in data.get("acts", []):
        if not act.get("is_active", True):
            continue
        normalized = act.get("normalized_name")
        doc_id = act.get("india_code_doc_id")
        filename = act.get("india_code_filename")
        if normalized and doc_id and filename:
            mapping[normalized] = (doc_id, filename)

    logger.info(f"Loaded {len(mapping)} known acts from JSON")
    return mapping


def get_known_acts() -> dict[str, tuple[str, str]]:
    """Get known acts mapping from JSON.

    Returns:
        Dict mapping normalized_name -> (doc_id, filename).
    """
    return _get_known_acts_mapping()


def get_known_act_info(normalized_name: str) -> tuple[str, str] | None:
    """Get India Code info for a specific act.

    Args:
        normalized_name: Normalized act name (e.g., "negotiable_instruments_act_1881")

    Returns:
        Tuple of (doc_id, filename) if found, None otherwise.
    """
    return get_known_acts().get(normalized_name)


# =============================================================================
# Garbage Patterns Data
# =============================================================================


@lru_cache(maxsize=1)
def _get_garbage_patterns_compiled() -> list[tuple[re.Pattern, str]]:
    """Internal cached loader for compiled garbage patterns."""
    data = load_json_data("garbage_patterns.json")

    if not data or "patterns" not in data:
        logger.warning("garbage_patterns.json not found or empty, using defaults")
        return []

    patterns: list[tuple[re.Pattern, str]] = []
    for p in data.get("patterns", []):
        pattern_str = p.get("pattern")
        description = p.get("description", pattern_str)
        flags_list = p.get("flags", [])

        if not pattern_str:
            continue

        # Build regex flags
        flags = 0
        if "IGNORECASE" in flags_list:
            flags |= re.IGNORECASE
        if "MULTILINE" in flags_list:
            flags |= re.MULTILINE

        try:
            compiled = re.compile(pattern_str, flags)
            patterns.append((compiled, description))
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern_str}': {e}")

    logger.info(f"Loaded {len(patterns)} garbage patterns from JSON")
    return patterns


def get_garbage_patterns() -> list[tuple[re.Pattern, str]]:
    """Get compiled garbage detection patterns from JSON.

    Returns:
        List of (compiled_pattern, description) tuples.
    """
    return _get_garbage_patterns_compiled()


# =============================================================================
# Validation Rules Data
# =============================================================================


def get_validation_rules() -> dict[str, Any]:
    """Get validation rules from JSON.

    Returns:
        Dict with validation rules and thresholds.
    """
    data = load_json_data("validation_rules.json")

    # Return defaults if file not found
    if not data:
        return {
            "valid_suffixes": ["act", "code", "rules", "regulations", "ordinance", "order", "bill", "amendment", "notification"],
            "valid_keywords": ["act", "code", "rules", "regulations", "ordinance", "amendment", "indian", "central", "state", "prevention", "protection", "enforcement", "regulation", "development", "welfare", "management", "control"],
        }

    return data


def get_valid_act_suffixes() -> tuple[str, ...]:
    """Get valid act name suffixes.

    Returns:
        Tuple of valid suffix strings.
    """
    rules = get_validation_rules()
    return tuple(rules.get("valid_suffixes", []))


def get_valid_act_keywords() -> set[str]:
    """Get valid act name keywords.

    Returns:
        Set of valid keyword strings.
    """
    rules = get_validation_rules()
    return set(rules.get("valid_keywords", []))


def get_generic_terms() -> set[str]:
    """Get generic terms that should always be considered invalid.

    These are terms that are too vague to be useful act names,
    like "the Act" or "Ordinance" alone.

    Returns:
        Set of generic term strings (lowercase).
    """
    rules = get_validation_rules()
    terms = rules.get("generic_terms", [])

    if not terms:
        # Fallback defaults
        return {
            "act", "the act", "code", "the code", "ordinance", "the ordinance",
            "rules", "the rules", "regulations", "the regulations",
            "bill", "the bill", "amendment", "the amendment",
        }

    return set(t.lower() for t in terms)


# =============================================================================
# Act Abbreviations Data
# =============================================================================


def get_act_abbreviations() -> dict[str, tuple[str, int | None]]:
    """Get act abbreviations from JSON.

    Falls back to built-in abbreviations if JSON not available.

    Returns:
        Dict mapping abbreviation -> (canonical_name, year).
    """
    data = load_json_data("act_abbreviations.json")

    if not data or "abbreviations" not in data:
        # Fall back to built-in abbreviations
        return {}

    mapping: dict[str, tuple[str, int | None]] = {}
    for abbr in data.get("abbreviations", []):
        key = abbr.get("key", "").lower()
        canonical = abbr.get("canonical_name")
        year = abbr.get("year")

        if key and canonical:
            mapping[key] = (canonical, year)

            # Also add aliases
            for alias in abbr.get("aliases", []):
                alias_key = alias.lower()
                if alias_key not in mapping:
                    mapping[alias_key] = (canonical, year)

    logger.info(f"Loaded {len(mapping)} act abbreviations from JSON")
    return mapping
