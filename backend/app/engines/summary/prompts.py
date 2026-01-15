"""GPT-4 prompts for executive summary generation.

Story 14.1: Summary API Endpoint (Task 4)

Prompts for generating matter summaries using GPT-4.
CRITICAL: Uses GPT-4 per LLM routing rules (ADR-002).
Summary generation = user-facing, accuracy critical, reasoning task.

LANGUAGE POLICING:
All prompts include instructions to avoid legal conclusions.
Output is additionally sanitized by language_policing_service.
"""

# =============================================================================
# Configuration Constants
# =============================================================================

# Maximum chunks to include in GPT-4 prompt context
MAX_PROMPT_CHUNKS = 10

# Maximum events to include for current status context
MAX_PROMPT_EVENTS = 5

# =============================================================================
# Story 14.1: Subject Matter Prompt (Task 4.1)
# =============================================================================

SUBJECT_MATTER_SYSTEM_PROMPT = """You are a legal document analyst generating objective case summaries for attorneys.

Your task is to summarize the SUBJECT MATTER of a legal case based on document excerpts.

CRITICAL GUIDELINES:
1. Be OBJECTIVE - describe only what is stated in the documents
2. NEVER make legal conclusions or judgments
3. NEVER use words like "clearly", "obviously", "proves", "establishes"
4. Use neutral language: "concerns", "relates to", "involves"
5. Include specific details: names, dates, amounts if mentioned
6. Keep summary to 2-3 sentences maximum
7. Always cite source documents for factual claims

LANGUAGE POLICING RULES (MANDATORY):
- Replace "proves" → "suggests"
- Replace "clearly shows" → "indicates"
- Replace "establishes" → "relates to"
- Replace "the evidence shows" → "the documents contain"
- Replace "guilty/liable" → "alleged"
- NEVER use definitive legal language

Respond with JSON in this exact format:
{
  "description": "2-3 sentence summary of what the matter concerns",
  "sources": [{"documentName": "filename.pdf", "pageRange": "1-3"}]
}"""


SUBJECT_MATTER_USER_PROMPT = """Based on these document excerpts from the matter, summarize the SUBJECT MATTER:

DOCUMENT EXCERPTS:
{chunks}

Generate a brief, objective summary of what this legal matter concerns.
Include source citations for each claim.

Respond ONLY with valid JSON matching the schema."""


# =============================================================================
# Story 14.1: Key Issues Prompt (Task 4.1)
# =============================================================================

KEY_ISSUES_SYSTEM_PROMPT = """You are a legal document analyst identifying key legal issues in a case.

Your task is to extract 3-5 KEY ISSUES from legal documents for attorney review.

CRITICAL GUIDELINES:
1. Frame issues as QUESTIONS, not conclusions
2. Use phrases like "Whether...", "If...", "What..."
3. Focus on LEGAL ISSUES, not procedural details
4. Order issues by apparent significance
5. NEVER suggest answers to the questions
6. NEVER make determinations about liability, guilt, or fault

LANGUAGE POLICING RULES (MANDATORY):
- Frame as open questions: "Whether X occurred" not "X clearly occurred"
- Avoid certainty: "appears to be disputed" not "is clearly disputed"
- No judgments: "alleged misconduct" not "obvious misconduct"

Respond with JSON in this exact format:
{
  "issues": [
    {"id": "issue-1", "number": 1, "title": "Whether [issue framed as question]?"},
    {"id": "issue-2", "number": 2, "title": "If [issue framed as question]?"}
  ]
}"""


KEY_ISSUES_USER_PROMPT = """Based on these document excerpts, identify 3-5 KEY LEGAL ISSUES:

DOCUMENT EXCERPTS:
{chunks}

Extract the main legal questions that need to be addressed in this matter.
Frame each as a neutral question without suggesting answers.

Respond ONLY with valid JSON matching the schema."""


# =============================================================================
# Story 14.1: Current Status Prompt (Task 4.1)
# =============================================================================

CURRENT_STATUS_SYSTEM_PROMPT = """You are a legal document analyst identifying the current procedural status of a case.

Your task is to identify the MOST RECENT order or decision in the matter.

CRITICAL GUIDELINES:
1. Identify the most recent order, judgment, or procedural action
2. Include the DATE if mentioned
3. Describe WHAT was ordered/decided objectively
4. Include source document and page
5. NEVER interpret implications of the order
6. NEVER suggest what should happen next

LANGUAGE POLICING RULES (MANDATORY):
- Use factual language: "The order directs..." not "The court found..."
- Avoid interpretation: "states that" not "clearly means"
- No speculation: describe only what is explicitly stated

If no clear order/status is found, indicate that the status is unclear.

Respond with JSON in this exact format:
{
  "lastOrderDate": "ISO date string or 'Unknown'",
  "description": "Brief description of current status",
  "sourceDocument": "filename.pdf",
  "sourcePage": 1
}"""


CURRENT_STATUS_USER_PROMPT = """Based on these document excerpts, identify the CURRENT STATUS of this matter:

DOCUMENT EXCERPTS:
{chunks}

EVENT TIMELINE (most recent first):
{events}

Find the most recent order, judgment, or procedural status.
Include the date, description, and source.

Respond ONLY with valid JSON matching the schema."""


# =============================================================================
# Story 14.1: Helper Functions (Task 4.2, 4.3)
# =============================================================================


def format_subject_matter_prompt(chunks: list[dict]) -> str:
    """Format the user prompt for subject matter generation.

    Args:
        chunks: List of document chunks with content and metadata.

    Returns:
        Formatted prompt string.
    """
    chunks_text = _format_chunks(chunks)
    return SUBJECT_MATTER_USER_PROMPT.format(chunks=chunks_text)


def format_key_issues_prompt(chunks: list[dict]) -> str:
    """Format the user prompt for key issues extraction.

    Args:
        chunks: List of document chunks with content and metadata.

    Returns:
        Formatted prompt string.
    """
    chunks_text = _format_chunks(chunks)
    return KEY_ISSUES_USER_PROMPT.format(chunks=chunks_text)


def format_current_status_prompt(
    chunks: list[dict],
    events: list[dict] | None = None,
) -> str:
    """Format the user prompt for current status summarization.

    Args:
        chunks: List of document chunks with content and metadata.
        events: Optional list of timeline events (most recent first).

    Returns:
        Formatted prompt string.
    """
    chunks_text = _format_chunks(chunks)
    events_text = _format_events(events) if events else "No events available."
    return CURRENT_STATUS_USER_PROMPT.format(
        chunks=chunks_text,
        events=events_text,
    )


def _format_chunks(chunks: list[dict]) -> str:
    """Format chunks for prompt insertion.

    Args:
        chunks: List of chunks with content, document_name, page_number.

    Returns:
        Formatted string of chunks.
    """
    if not chunks:
        return "No document excerpts available."

    formatted = []
    for i, chunk in enumerate(chunks[:MAX_PROMPT_CHUNKS], 1):
        doc_name = chunk.get("document_name", "Unknown")
        page = chunk.get("page_number", "?")
        content = chunk.get("content", "")[:1000]  # Limit content length

        formatted.append(
            f"[Excerpt {i}] Source: {doc_name}, Page {page}\n{content}\n"
        )

    return "\n---\n".join(formatted)


def _format_events(events: list[dict]) -> str:
    """Format timeline events for prompt insertion.

    Args:
        events: List of events with date, description, document_name.

    Returns:
        Formatted string of events.
    """
    if not events:
        return "No timeline events available."

    formatted = []
    for event in events[:MAX_PROMPT_EVENTS]:
        date = event.get("event_date", "Unknown date")
        desc = event.get("description", "")[:200]
        doc = event.get("document_name", "")

        formatted.append(f"- [{date}] {desc} (Source: {doc})")

    return "\n".join(formatted)
