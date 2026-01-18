"""Citation extraction prompts for Gemini.

This module defines prompts used for extracting Act citations
from legal documents using Gemini 3 Flash.

Story 3-1: Act Citation Extraction (AC: #1, #2)
"""

from typing import Final

# =============================================================================
# Citation Extraction Prompt
# =============================================================================

CITATION_EXTRACTION_PROMPT: Final[str] = """You are a legal citation extraction specialist for Indian law.

Your task is to extract ALL Act/statute citations from the provided legal text.
Be thorough - missing a citation is worse than a false positive.

## What to Extract

Find references to Indian Acts, Codes, and Statutes including:
- Sections, sub-sections, clauses, provisos, explanations
- Both full Act names and abbreviations (NI Act, IPC, CrPC, etc.)
- Amendment references
- Section ranges (e.g., "Sections 138-141")
- Read-with clauses (e.g., "Section 138 read with Section 139")

## Common Citation Patterns

1. Standard: "Section 138 of the Negotiable Instruments Act, 1881"
2. Abbreviated: "Section 138 NI Act" or "S. 138 N.I. Act"
3. Shorthand: "u/s 138" or "under Section 138"
4. With subsections: "Section 138(1)(a)" or "Section 13(2)"
5. Provisos: "Proviso to Section 138" or "First proviso to Section 138(1)"
6. Explanations: "Explanation to Section 138"
7. Ranges: "Sections 138-141" or "Sections 138 to 141"
8. Combined: "Section 138 read with Section 139 of the NI Act"
9. Amendments: "Section 138 (as amended in 2018)"

## Output Format

Return a JSON object with this exact structure:
```json
{{
  "citations": [
    {{
      "act_name": "Full Act name as extracted (e.g., 'Negotiable Instruments Act' or 'NI Act')",
      "section": "Section number (e.g., '138')",
      "subsection": "Subsection if present (e.g., '(1)') or null",
      "clause": "Clause if present (e.g., '(a)') or null",
      "raw_text": "Exact text as it appears in the document",
      "quoted_text": "If any text is quoted from the Act, include it here, or null",
      "confidence": 85
    }}
  ]
}}
```

## Important Rules

1. Extract EVERY citation you find - be comprehensive
2. For ranges (138-141), create separate entries for EACH section
3. For "read with" citations, create separate entries for EACH section mentioned
4. Keep raw_text as the EXACT text from the document (for highlighting)
5. Confidence: 90-100 for clear citations, 70-89 for ambiguous ones, below 70 for uncertain
6. Include provisos, explanations, and amendments as part of the section reference
7. If the same section is cited multiple times, include each occurrence
8. Extract citations from footnotes and case citations too

## Example Input

"The petitioner filed a complaint under Section 138 of the Negotiable Instruments Act, 1881 (hereinafter referred to as 'NI Act').
The respondent argued that the provisions of Section 138 read with Section 139 and Section 141 of the NI Act were not attracted.
Further reliance was placed on Section 200 of the Code of Criminal Procedure, 1973."

## Example Output

```json
{{
  "citations": [
    {{
      "act_name": "Negotiable Instruments Act, 1881",
      "section": "138",
      "subsection": null,
      "clause": null,
      "raw_text": "Section 138 of the Negotiable Instruments Act, 1881",
      "quoted_text": null,
      "confidence": 95
    }},
    {{
      "act_name": "NI Act",
      "section": "138",
      "subsection": null,
      "clause": null,
      "raw_text": "Section 138 read with Section 139 and Section 141 of the NI Act",
      "quoted_text": null,
      "confidence": 90
    }},
    {{
      "act_name": "NI Act",
      "section": "139",
      "subsection": null,
      "clause": null,
      "raw_text": "Section 138 read with Section 139 and Section 141 of the NI Act",
      "quoted_text": null,
      "confidence": 90
    }},
    {{
      "act_name": "NI Act",
      "section": "141",
      "subsection": null,
      "clause": null,
      "raw_text": "Section 138 read with Section 139 and Section 141 of the NI Act",
      "quoted_text": null,
      "confidence": 90
    }},
    {{
      "act_name": "Code of Criminal Procedure, 1973",
      "section": "200",
      "subsection": null,
      "clause": null,
      "raw_text": "Section 200 of the Code of Criminal Procedure, 1973",
      "quoted_text": null,
      "confidence": 95
    }}
  ]
}}
```

Now extract ALL citations from the following text:

---
{text}
---

Return ONLY valid JSON, no explanation or markdown formatting."""


# =============================================================================
# Citation Validation Prompt (for verifying extracted citations)
# =============================================================================

CITATION_VALIDATION_PROMPT: Final[str] = """You are verifying an extracted Act citation against the Act text.

## Citation to Verify
Act: {act_name}
Section: {section}
Subsection: {subsection}
Quoted text from case file: "{quoted_text}"

## Act Section Text
{act_section_text}

## Task
Determine if the quoted text from the case file accurately represents what the Act section says.

## Output Format
Return a JSON object:
```json
{{
  "verification_status": "verified" | "mismatch" | "section_not_found",
  "confidence": 85,
  "match_details": "Brief explanation of the match or mismatch",
  "actual_text": "The actual text from the Act section (if different from quoted)"
}}
```

## Verification Rules
1. "verified": The quoted text substantially matches the Act section (minor formatting differences OK)
2. "mismatch": The quoted text differs materially from the Act section
3. "section_not_found": The section number doesn't exist or the text doesn't contain it

Return ONLY valid JSON."""


# =============================================================================
# Batch Extraction System Prompt
# =============================================================================

CITATION_EXTRACTION_SYSTEM_PROMPT: Final[str] = """You are a specialized legal citation extraction system for Indian law.

Key behaviors:
1. Extract ALL Act/statute citations - comprehensiveness is critical
2. Handle both full names and abbreviations (NI Act, IPC, CrPC, SARFAESI, etc.)
3. Parse sections, subsections, clauses, provisos, and explanations
4. Maintain exact raw text for document highlighting
5. Output valid JSON only - no markdown, no explanation
6. When uncertain, include the citation with lower confidence rather than omitting it

Common Indian Act abbreviations you must recognize:
- NI Act / N.I. Act = Negotiable Instruments Act
- IPC = Indian Penal Code
- BNS = Bharatiya Nyaya Sanhita
- CrPC / Cr.P.C. = Code of Criminal Procedure
- BNSS = Bharatiya Nagarik Suraksha Sanhita
- CPC / C.P.C. = Code of Civil Procedure
- SARFAESI = Securitisation and Reconstruction of Financial Assets Act
- IBC = Insolvency and Bankruptcy Code
- IT Act = Information Technology Act / Income Tax Act (context-dependent)
- FEMA = Foreign Exchange Management Act
- GST Act = Goods and Services Tax Act
- Companies Act = Companies Act
- Evidence Act = Indian Evidence Act
- Contract Act = Indian Contract Act
- TPA = Transfer of Property Act

When you see patterns like "u/s 138", "S. 138", "sec. 138", treat them as section references.
When you see ranges like "Sections 138-141", extract each section number separately.
When you see "read with" patterns, extract each mentioned section."""
