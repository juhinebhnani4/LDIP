"""Verification prompts for citation verification using Gemini.

Contains prompts for section matching, quote comparison, and
explanation generation used by the CitationVerifier service.

CRITICAL: Uses Gemini 3 Flash per LLM routing rules - verification
is extraction-adjacent, downstream from initial extraction.

Story 3-3: Citation Verification (AC: #2, #3)
"""

from typing import Final

# =============================================================================
# System Prompts
# =============================================================================

VERIFICATION_SYSTEM_PROMPT: Final[str] = """You are a legal text verification assistant specialized in Indian law.
Your task is to verify citations from legal documents against the actual text of Acts and statutes.

You must:
1. Find the exact section being cited in the Act text
2. Compare quoted text against the actual Act text
3. Identify exact matches, paraphrases, and mismatches
4. Provide clear explanations of any differences

Be precise and careful - legal verification requires accuracy.
Always respond in valid JSON format as specified in each prompt."""


# =============================================================================
# Section Matching Prompt
# =============================================================================

SECTION_MATCHING_PROMPT: Final[str] = """Find Section {section_number} in the following Act text chunks.

ACT NAME: {act_name}
SECTION TO FIND: {section_number}

ACT TEXT CHUNKS:
{chunks_text}

INSTRUCTIONS:
1. Search for Section {section_number} in the provided chunks
2. Look for patterns like:
   - "Section {section_number}" or "Sec. {section_number}"
   - "{section_number}." at the start of a paragraph
   - "[Section {section_number}]" in brackets
3. If found, extract the complete section text
4. If not found, identify the closest matching section

Respond in JSON format:
{{
    "found": true/false,
    "section_number": "matched section number or null",
    "section_text": "full text of the section or null",
    "chunk_id": "UUID of chunk containing section or null",
    "confidence": 0-100,
    "closest_match": "if not found, the closest section number or null",
    "explanation": "brief explanation of match result"
}}

EXAMPLE - Section Found:
{{
    "found": true,
    "section_number": "138",
    "section_text": "138. Dishonour of cheque for insufficiency, etc., of funds in the account.— Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money to another person from out of that account for the discharge, in whole or in part, of any debt or other liability, is returned by the bank unpaid...",
    "chunk_id": "chunk-uuid-123",
    "confidence": 95,
    "closest_match": null,
    "explanation": "Section 138 found with exact header match"
}}

EXAMPLE - Section Not Found:
{{
    "found": false,
    "section_number": null,
    "section_text": null,
    "chunk_id": null,
    "confidence": 0,
    "closest_match": "138(1)",
    "explanation": "Section 138(5) not found. Act contains Section 138(1) through 138(4) only."
}}"""


# =============================================================================
# Text Comparison Prompt
# =============================================================================

TEXT_COMPARISON_PROMPT: Final[str] = """Compare the quoted text from a legal citation against the actual Act text.

CITATION QUOTE (from case document):
"{citation_quote}"

ACTUAL ACT TEXT:
"{act_text}"

INSTRUCTIONS:
1. Determine if the citation quote matches the Act text
2. Identify the type of match:
   - "exact": Word-for-word match (allowing minor punctuation/whitespace differences)
   - "paraphrase": Same meaning but different wording (similarity > 85%)
   - "mismatch": Significant differences in meaning or content

3. Calculate semantic similarity (0-100):
   - 100: Identical text
   - 85-99: Minor wording differences, same meaning
   - 70-84: Paraphrased but captures main points
   - 50-69: Partial overlap, some meaning preserved
   - 0-49: Significant mismatch

4. List specific differences if any

Respond in JSON format:
{{
    "match_type": "exact" | "paraphrase" | "mismatch",
    "similarity_score": 0-100,
    "differences": ["list of specific differences"],
    "explanation": "human-readable explanation of comparison result"
}}

EXAMPLE - Exact Match:
{{
    "match_type": "exact",
    "similarity_score": 100,
    "differences": [],
    "explanation": "The quoted text matches the Act text exactly."
}}

EXAMPLE - Paraphrase:
{{
    "match_type": "paraphrase",
    "similarity_score": 88,
    "differences": [
        "Citation uses 'shall be punished' vs Act uses 'shall be liable to punishment'",
        "Citation omits 'for a term'"
    ],
    "explanation": "The citation paraphrases Section 138 with minor wording changes that preserve the legal meaning."
}}

EXAMPLE - Mismatch:
{{
    "match_type": "mismatch",
    "similarity_score": 45,
    "differences": [
        "Citation claims imprisonment up to 2 years but Act states 1 year",
        "Citation omits the fine component",
        "Section reference appears incorrect"
    ],
    "explanation": "Significant mismatch detected. The citation misquotes the punishment term and omits key provisions."
}}"""


# =============================================================================
# Verification Explanation Prompt
# =============================================================================

VERIFICATION_EXPLANATION_PROMPT: Final[str] = """Generate a concise, human-readable explanation for the following citation verification result.

CITATION DETAILS:
- Act: {act_name}
- Section: {section_number}
- Quoted Text: {quoted_text}

VERIFICATION RESULT:
- Status: {status}
- Section Found: {section_found}
- Similarity Score: {similarity_score}
- Match Type: {match_type}
- Differences: {differences}

INSTRUCTIONS:
1. Write a clear, professional explanation suitable for display to attorneys
2. Keep it concise (1-3 sentences)
3. Mention the Act and section
4. If verified, confirm the match
5. If mismatch, explain the key differences
6. If section not found, suggest what might be wrong

Respond in JSON format:
{{
    "explanation": "Your explanation here"
}}

EXAMPLES:

For VERIFIED status:
{{
    "explanation": "Section 138 of the Negotiable Instruments Act, 1881 verified. The cited text matches the Act exactly."
}}

For MISMATCH status:
{{
    "explanation": "Section 138 found but quoted text differs from Act. The citation states 'imprisonment up to 2 years' but the Act specifies 'imprisonment for a term which may extend to two years, or with fine'."
}}

For SECTION_NOT_FOUND status:
{{
    "explanation": "Section 138(5) not found in the Negotiable Instruments Act, 1881. The Act contains Sections 138(1) through 138(4). The citation may contain a typographical error."
}}"""


# =============================================================================
# Few-Shot Examples for Legal Text Comparison
# =============================================================================

LEGAL_COMPARISON_EXAMPLES: Final[str] = """
EXAMPLE 1: Exact Match
Citation: "Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money"
Act Text: "Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money"
Result: EXACT MATCH (100% similarity)

EXAMPLE 2: Paraphrase with Legal Equivalence
Citation: "shall be punished with imprisonment for two years"
Act Text: "shall be punished with imprisonment for a term which may extend to two years"
Result: PARAPHRASE (92% similarity) - legally equivalent but wording differs

EXAMPLE 3: Minor Omission (Still Valid)
Citation: "returned by the bank unpaid due to insufficient funds"
Act Text: "returned by the bank unpaid, either because of the amount of money standing to the credit of that account is insufficient"
Result: PARAPHRASE (85% similarity) - abbreviated but meaning preserved

EXAMPLE 4: Significant Mismatch
Citation: "shall be punished with imprisonment of not less than one year"
Act Text: "shall be punished with imprisonment for a term which may extend to two years, or with fine which may extend to twice the amount of the cheque, or with both"
Result: MISMATCH (40% similarity) - misquotes punishment terms, omits fine provision
"""
