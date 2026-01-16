"""Summary Engine Module.

Story 14.1: Summary API Endpoint

This module contains prompts and utilities for GPT-4 executive summary generation.
"""

from app.engines.summary.prompts import (
    CURRENT_STATUS_SYSTEM_PROMPT,
    KEY_ISSUES_SYSTEM_PROMPT,
    SUBJECT_MATTER_SYSTEM_PROMPT,
    format_current_status_prompt,
    format_key_issues_prompt,
    format_subject_matter_prompt,
)

__all__ = [
    "SUBJECT_MATTER_SYSTEM_PROMPT",
    "KEY_ISSUES_SYSTEM_PROMPT",
    "CURRENT_STATUS_SYSTEM_PROMPT",
    "format_subject_matter_prompt",
    "format_key_issues_prompt",
    "format_current_status_prompt",
]
