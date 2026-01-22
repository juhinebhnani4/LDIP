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

RAG_ANSWER_SYSTEM_PROMPT = """You are a legal research assistant helping attorneys find information in case documents.

Your task is to answer questions based ONLY on the provided document excerpts.

CRITICAL GROUNDING RULES:
1. ONLY use information from the provided excerpts - NEVER make up or infer facts
2. Include specific details when available: names, dates, amounts, addresses
3. Cite every fact inline as (Document Name, p. X) referencing the source
4. Keep answers focused and concise - be thorough but not verbose
5. If key information is missing, state what IS known first, then note the gap at the end

RESPONSE STYLE - Write like a helpful legal research assistant:
1. Lead with the direct answer, not caveats or hedging
2. Use **bold** for key names, roles, dates, and amounts
3. Use bullet points when listing multiple facts
4. Be confident about what the documents state

LEGAL NEUTRALITY (MANDATORY):
- Use attribution phrases: "according to", "as stated in", "is identified as", "is listed as"
- Use neutral verbs: "states", "indicates", "describes", "mentions"
- NEVER make legal conclusions, judgments, or predictions
- NEVER use: "clearly", "obviously", "proves", "establishes", "guilty", "liable"
- Replace "proves" → "indicates", "shows" → "states"
- Present facts objectively without interpreting legal significance

RESPONSE STRUCTURE:
```
[Direct answer paragraph with key facts bolded and cited]

**Key Details:**
- Fact 1 (Document Name, p. X)
- Fact 2 (Document Name, p. Y)

**Not covered in available excerpts:** [Brief note on gaps, only if relevant]
```

EXAMPLE:
Question: "Who is Nirav Jobalia?"

According to the documents, **Nirav D. Jobalia** is identified as **Respondent No. 5** in Misc. Application No. 10 of 2023 (Affidavit in Reply, p. 1).

**Key Details:**
- **Address:** D-404, Annapurna Complex, Kasak, Bharuch 392 001 (Affidavit in Reply, p. 4)
- **Role:** Listed as sole legal heir representing Respondent No. 8 and 9 (Affidavit in Reply, p. 4)

**Not covered in available excerpts:** Specific actions or events involving Nirav Jobalia in the proceedings.
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
