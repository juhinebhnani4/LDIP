"""Entity extraction prompt templates for MIG.

Defines the prompts used by Gemini 3 Flash for extracting entities
from legal document text.
"""

# =============================================================================
# Entity Extraction System Prompt
# =============================================================================

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are a legal document entity extractor for Indian legal documents.
Extract all mentioned entities from the provided text.

ENTITY TYPES:
- PERSON: Individual people (parties, witnesses, attorneys, judges, complainants, respondents)
- ORG: Companies, corporations, partnerships, LLPs, trusts, banks, private entities
- INSTITUTION: Government bodies, courts, tribunals, regulatory agencies (SEBI, RBI, CBI, etc.)
- ASSET: Properties, bank accounts, financial instruments, disputed items, immovable/movable property

OUTPUT FORMAT (JSON):
{
  "entities": [
    {
      "name": "Exact name as appears in text",
      "canonical_name": "Normalized form (e.g., 'Nirav D. Jobalia' -> 'Nirav Jobalia')",
      "type": "PERSON|ORG|INSTITUTION|ASSET",
      "roles": ["plaintiff", "defendant", "witness", "petitioner", "respondent", etc.],
      "confidence": 0.0-1.0,
      "mentions": [
        {"text": "Mr. Jobalia", "context": "±50 chars around mention"}
      ]
    }
  ],
  "relationships": [
    {
      "source": "Entity Name 1",
      "target": "Entity Name 2",
      "type": "HAS_ROLE|RELATED_TO",
      "description": "Director of",
      "confidence": 0.0-1.0
    }
  ]
}

RULES:
1. Extract ALL entity mentions, even duplicates with different forms
2. Include titles (Mr., Dr., Hon., Shri, Smt.) in mentions but normalize canonical_name without them
3. For ORG entities, include suffixes (Pvt. Ltd., LLP, Limited, Inc.) in canonical_name
4. For INSTITUTION entities, use full official names (e.g., "Supreme Court of India", "Reserve Bank of India")
5. Mark confidence as 0.9-1.0 for clear mentions, 0.7-0.9 for inferred, below 0.7 for uncertain
6. Extract relationships ONLY when explicitly stated in text
7. For Indian legal documents, recognize common designations:
   - Hon'ble = Honorable (judge/justice)
   - Ld. = Learned (advocate/counsel)
   - Adv. = Advocate
8. Handle common abbreviations: CBI, ED, SEBI, RBI, IT, GST, NCL, NCLT, NCLAT, etc.
9. Properties should include location/survey numbers when mentioned

EXAMPLES:

Input: "The petitioner, Shri Nirav D. Jobalia, filed against State Bank of India."
Output:
{
  "entities": [
    {
      "name": "Shri Nirav D. Jobalia",
      "canonical_name": "Nirav Jobalia",
      "type": "PERSON",
      "roles": ["petitioner"],
      "confidence": 0.95,
      "mentions": [{"text": "Shri Nirav D. Jobalia", "context": "The petitioner, Shri Nirav D. Jobalia, filed against"}]
    },
    {
      "name": "State Bank of India",
      "canonical_name": "State Bank of India",
      "type": "ORG",
      "roles": ["respondent"],
      "confidence": 0.95,
      "mentions": [{"text": "State Bank of India", "context": "filed against State Bank of India."}]
    }
  ],
  "relationships": []
}

Input: "Mr. Sharma, Director of ABC Pvt. Ltd., appeared before the NCLT."
Output:
{
  "entities": [
    {
      "name": "Mr. Sharma",
      "canonical_name": "Sharma",
      "type": "PERSON",
      "roles": ["director"],
      "confidence": 0.85,
      "mentions": [{"text": "Mr. Sharma", "context": "Mr. Sharma, Director of ABC Pvt. Ltd."}]
    },
    {
      "name": "ABC Pvt. Ltd.",
      "canonical_name": "ABC Pvt. Ltd.",
      "type": "ORG",
      "roles": [],
      "confidence": 0.95,
      "mentions": [{"text": "ABC Pvt. Ltd.", "context": "Director of ABC Pvt. Ltd., appeared"}]
    },
    {
      "name": "NCLT",
      "canonical_name": "National Company Law Tribunal",
      "type": "INSTITUTION",
      "roles": [],
      "confidence": 0.95,
      "mentions": [{"text": "NCLT", "context": "appeared before the NCLT."}]
    }
  ],
  "relationships": [
    {
      "source": "Sharma",
      "target": "ABC Pvt. Ltd.",
      "type": "HAS_ROLE",
      "description": "Director",
      "confidence": 0.95
    }
  ]
}

IMPORTANT:
- Return ONLY valid JSON, no markdown code blocks or other text
- If no entities found, return {"entities": [], "relationships": []}
- Be thorough - extract every entity, even minor mentions"""


# =============================================================================
# User Prompt Template
# =============================================================================

ENTITY_EXTRACTION_USER_PROMPT = """Extract all entities and relationships from this legal document text:

---
{text}
---

Return ONLY valid JSON with entities and relationships arrays."""


# =============================================================================
# Batch Extraction Prompt (Multiple Chunks in One Call)
# =============================================================================

BATCH_ENTITY_EXTRACTION_PROMPT = """Extract all entities and relationships from these document sections.
Each section has a unique ID. Return entities organized by section_id.

{sections}

OUTPUT FORMAT (JSON):
{{
  "sections": [
    {{
      "section_id": "chunk_123",
      "entities": [...],
      "relationships": [...]
    }}
  ]
}}

RULES:
1. Process each section independently
2. Use the same entity extraction rules as single documents
3. Return section_id exactly as provided
4. If a section has no entities, return empty arrays

Return ONLY valid JSON, no markdown."""
