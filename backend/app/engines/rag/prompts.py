"""Prompts for RAG answer generation.

Story 6-2: Engine Orchestrator - RAG Answer Synthesis

Prompts for generating grounded answers from retrieved document chunks.
Uses Gemini Flash for cost-effective generation (per LLM routing rules).

CRITICAL: Answers must be grounded in provided context only.
CRITICAL: Include inline citations [1], [2] referencing source chunks.
"""

# =============================================================================
# Configuration Constants
# =============================================================================

# Maximum chunks to include in context
MAX_CONTEXT_CHUNKS = 5

# Maximum content length per chunk (characters)
MAX_CHUNK_CONTENT = 1500

# =============================================================================
# RAG Answer Generation Prompt
# =============================================================================

RAG_ANSWER_SYSTEM_PROMPT = """You are a legal document assistant helping attorneys find information in case documents.

Your task is to answer the user's question based ONLY on the provided document excerpts.

CRITICAL GROUNDING RULES:
1. ONLY use information from the provided excerpts - never make up facts
2. If the excerpts don't contain enough information, say "Based on the available documents, I cannot fully answer this question"
3. Include inline citations like [1], [2] after each fact, referencing the source excerpt
4. Be specific - include names, dates, amounts, and details when available
5. Keep answers concise but complete (2-4 sentences typical)

LANGUAGE POLICING (MANDATORY):
- Use neutral language: "states", "indicates", "describes"
- NEVER make legal conclusions or judgments
- NEVER use words like "clearly", "obviously", "proves", "establishes"
- Replace "proves" → "indicates"
- Replace "shows" → "states"
- Always qualify with "according to" or "as stated in"

RESPONSE FORMAT:
- Answer the question directly and concisely
- Include inline citations [1], [2] after facts
- End with a brief source summary if helpful

Example:
Question: "Who are the parties in this case?"
Answer: "According to the documents, the applicant is Jyoti H. Mehta [1] and the respondents include The Custodian and others [1][2]. Nirav D. Jobalia is identified as Respondent No. 2 [2]."
"""

RAG_ANSWER_USER_PROMPT = """Based on these document excerpts, answer the following question:

QUESTION: {query}

DOCUMENT EXCERPTS:
{context}

Provide a concise, grounded answer with inline citations. If the excerpts don't contain sufficient information to answer, indicate that clearly."""


# =============================================================================
# Helper Functions
# =============================================================================


def format_rag_answer_prompt(
    query: str,
    chunks: list[dict],
) -> str:
    """Format the user prompt for RAG answer generation.

    Args:
        query: User's question.
        chunks: List of retrieved chunks with content and metadata.

    Returns:
        Formatted prompt string.
    """
    context = _format_context(chunks)
    return RAG_ANSWER_USER_PROMPT.format(query=query, context=context)


def _format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks as numbered context.

    Args:
        chunks: List of chunks with content, document_name/id, page_number.

    Returns:
        Formatted context string with numbered excerpts.
    """
    if not chunks:
        return "No document excerpts available."

    formatted = []
    for i, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS], 1):
        # Support both snake_case (from DB) and camelCase (from API)
        doc_name = chunk.get("document_name") or chunk.get("documentName") or "Unknown Document"
        page = chunk.get("page_number") or chunk.get("pageNumber") or "?"
        content = chunk.get("content", "")[:MAX_CHUNK_CONTENT]

        formatted.append(
            f"[{i}] Source: {doc_name}, Page {page}\n{content}"
        )

    return "\n\n---\n\n".join(formatted)
