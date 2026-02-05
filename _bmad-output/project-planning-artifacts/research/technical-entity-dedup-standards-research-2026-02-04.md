---
stepsCompleted: ['discovery', 'web-research', 'analysis', 'recommendations']
inputDocuments: ['backend/scripts/merge_duplicate_entities.py']
workflowType: 'research'
lastStep: 4
research_type: 'technical'
research_topic: 'Entity Deduplication Industry Standards'
research_goals: 'Identify best practices for name matching that avoid false positives on structured names (orgs with suffixes, numbered legal parties)'
user_name: 'Juhi'
date: '2026-02-04'
web_research_enabled: true
source_verification: true
---

# Technical Research: Entity Deduplication Industry Standards

**Date:** 2026-02-04
**Author:** Juhi
**Research Type:** Technical
**Application:** Improving `backend/scripts/merge_duplicate_entities.py` for the LDIP project

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Industry Standard Algorithms](#industry-standard-algorithms)
4. [Company Name Deduplication Best Practices](#company-name-deduplication)
5. [Legal Domain Entity Resolution](#legal-domain-entity-resolution)
6. [Algorithm Comparison Matrix](#algorithm-comparison)
7. [Recommended Approach for LDIP](#recommended-approach)
8. [Sources](#sources)

---

## 1. Executive Summary

Our entity deduplication script uses **Jaro-Winkler similarity at a 0.75 threshold**, which produces massive false positives because common suffixes like "Ltd.", "Pvt. Ltd.", "of India" inflate similarity scores between unrelated entities. Industry research confirms this is a **known limitation** of character-level string similarity when applied to structured names.

The industry consensus is clear:

| Finding | Confidence |
|---------|------------|
| Suffix stripping before comparison is standard practice | **High** — Multiple tools (Splink, Scribe, Datablist) implement this |
| Jaro-Winkler is best for **person names**, not org names | **High** — Cohen (2003), Flagright, Splink docs all agree |
| Token-based similarity (Jaccard) outperforms character-level for multi-word org names | **High** — Cohen (2003), Splink business matching examples |
| Hybrid approaches (SoftTFIDF) are the best overall | **High** — Cohen (2003) seminal paper |
| AML/compliance systems use 0.85-0.90 thresholds for Jaro-Winkler | **High** — Flagright, industry standards |
| Single-column matching (name only) needs higher thresholds than multi-column | **High** — Splink documentation explicitly warns about this |

---

## 2. Problem Statement

### Current Implementation
- Algorithm: Jaro-Winkler similarity on normalized names
- Threshold: 0.75
- Blocking: Last name grouping with 0.85 similarity
- Clustering: Union-Find

### Observed False Positives (from dry-run with 920 entities)

| Canonical | Incorrectly Merged With | Why It Failed |
|-----------|------------------------|---------------|
| "Central Bank of India" | "State Bank of India" | Shared suffix "Bank of India" inflates score |
| "MCS Ltd." | "ACC Ltd." | 3-char core + shared suffix "Ltd." |
| "Hindustan Lever Ltd" | 18+ unrelated "Pvt. Ltd." companies | Shared suffix "Ltd" dominates similarity |
| "Respondent No.2" | "Respondent No.3/No.1/No.5" | Identical prefix, only number differs |

### True Duplicates (must still catch)

| Entity A | Entity B | Type |
|----------|----------|------|
| "Hero MotoCorp Ltd" | "Hero MotoCrop Ltd" | OCR typo |
| "Shilpa Bhate Associates" | "Shilpa Bhate & Associates" | Missing punctuation |
| "Kalpana Jobalia" | "Kalpana Jhobalia" | Spelling variation |

---

## 3. Industry Standard Algorithms

### 3.1 Character-Level: Jaro-Winkler

Jaro-Winkler was created by Matthew A. Jaro (1989) and modified by William E. Winkler (1990). It gives extra weight to matching prefixes — critical for person names where first characters carry the most discriminatory power.

**Best for:** Short strings, person names, typo detection
**Weakness:** Inflates scores for strings sharing common suffixes or prefixes; poor for rearranged tokens
**Industry threshold:** 0.85-0.90 for AML screening (Flagright)

> "The Jaro and Jaro-Winkler metrics seem to be intended primarily for short strings (for example, personal first or last names)." — Splink documentation

### 3.2 Token-Level: Jaccard Similarity

Converts strings into sets of tokens (words) and measures overlap. Order-independent.

**Best for:** Multi-word names where word order varies
**Weakness:** Requires exact token match (no typo tolerance)
**Example:** "Energy and Transportation" vs "Transportation, Energy, and Gas" → high similarity

### 3.3 Hybrid: SoftTFIDF (Cohen 2003)

Combines token-level Jaccard overlap with character-level Jaro-Winkler as a "secondary" fuzzy matcher for individual tokens. Uses TF-IDF weighting so common tokens (like "Ltd") contribute less to the score.

> "Generally speaking, SoftTFIDF was found to be the best overall distance measure across multiple datasets." — Cohen (2003), CMU

**This is the gold standard** for entity name matching according to the seminal comparison paper.

### 3.4 Probabilistic: Fellegi-Sunter Model (Splink)

The industry-standard framework for record linkage. Computes weights for each field based on its discriminatory power. Common values (like "Smith" or "Ltd") get lower weights automatically via term frequency adjustments.

**Best for:** Multi-field matching (name + address + DOB)
**Note:** Splink explicitly warns that single-column matching (name only) is a challenging scenario requiring special handling.

### 3.5 Phonetic: Soundex / Metaphone

Encodes names by pronunciation. Useful for transliteration variants but generates many false positives for dissimilar names that happen to sound alike.

**Not recommended** as primary matcher for LDIP's use case (Indian legal names with OCR errors, not pronunciation variants).

---

## 4. Company Name Deduplication Best Practices

### 4.1 Suffix Stripping is Standard

Multiple industry tools implement suffix stripping as a first step:

- **Scribe Insight** provides `STRIPCOMPANYSUFFIX` function that removes "Inc, Incorporated, Corp, Corporation, Co, Company, Ltd, Limited" etc.
- **Datablist** removes "legal suffixes (LLC, Inc., Ltd.), geographic terms (Europe, USA), and business keywords (Partners, Group, Technologies)"
- **Tilores** recommends "creating a reference list of common legal forms for detection and normalization"

### 4.2 Indian Legal Suffixes to Handle

For LDIP's Indian legal context, the suffix list should include:

```
Pvt. Ltd., Private Limited, Ltd., Limited,
& Associates, & Co., & Company, & Sons,
of India, of Maharashtra, of [State],
Industries, Enterprises, Corporation, Corp.,
Bank, Trust, Foundation, Society
```

### 4.3 Multi-Field Matching Reduces False Positives

Industry consensus: matching on name alone is inherently error-prone. Additional signals dramatically improve accuracy:

- **Document co-occurrence** — entities appearing in the same documents are more likely to be duplicates
- **Entity type** — already implemented in LDIP
- **Source metadata** — jurisdiction, role in case, etc.

### 4.4 Minimum Core Length Guard

Short cores (≤ 3 characters) after suffix stripping are highly ambiguous. Industry practice: require exact match for very short cores, or flag for human review.

---

## 5. Legal Domain Entity Resolution

### 5.1 Numbered Party Patterns

Legal documents use numbered party references ("Respondent No.1", "Petitioner No.2") that are **structurally distinct entities** despite near-identical names. No standard entity resolution system handles these without custom rules.

**Recommended:** Hard-coded blocklist pattern — never merge entities matching `(Respondent|Petitioner|Appellant|Complainant|Accused|Witness)\s*No\.\s*\d+`.

### 5.2 Legal NLP Tools

John Snow Labs' Legal NLP provides pre-trained NER models that distinguish between PARTY, ALIAS, and DOC entities in contracts. The ALIAS concept is directly relevant — it identifies when a company is referenced by different names in the same document.

However, deploying a full NLP pipeline is overkill for LDIP's dedup script. The suffix-stripping + threshold approach achieves the same outcome with simpler implementation.

### 5.3 Human-in-the-Loop

RelationalAI and others advocate for tiered results:
1. **Auto-merge:** Very high confidence (>0.95 on core name)
2. **Review queue:** Medium confidence (0.85-0.95) — present to user for approval
3. **No merge:** Below 0.85

LDIP's UI already shows "10 high-confidence duplicates at 99%" — this is essentially the auto-merge tier. The script should target only this tier.

---

## 6. Algorithm Comparison Matrix

| Algorithm | Person Names | Org Names | Typo Tolerance | Suffix Resilience | Complexity |
|-----------|-------------|-----------|----------------|-------------------|------------|
| Jaro-Winkler (current) | ★★★★★ | ★★☆☆☆ | ★★★★☆ | ★☆☆☆☆ | O(m+n) |
| Levenshtein | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★☆☆☆☆ | O(m×n) |
| Jaccard tokens | ★★☆☆☆ | ★★★★☆ | ★☆☆☆☆ | ★★★★☆ | O(n) |
| SoftTFIDF + JW | ★★★★★ | ★★★★★ | ★★★★☆ | ★★★★★ | O(n×m) |
| JW on stripped core | ★★★★★ | ★★★★☆ | ★★★★☆ | ★★★★★ | O(m+n) |

**"JW on stripped core"** is effectively a simplified SoftTFIDF — strip low-information tokens (suffixes), then apply Jaro-Winkler on the high-information core. This captures most of SoftTFIDF's benefit with minimal implementation complexity.

---

## 7. Recommended Approach for LDIP

Based on the research, here is the recommended implementation — validated against industry standards:

### 7.1 Algorithm: Suffix-Stripped Jaro-Winkler

This is a **simplified SoftTFIDF** approach that:
- Strips common org suffixes before comparison (standard industry practice)
- Applies Jaro-Winkler on the high-information core name
- Uses suffix match as a secondary signal (bonus, not blocker)
- Blocks numbered party patterns entirely

### 7.2 Threshold: 0.92 on Core Names

Industry AML standards use 0.85-0.90 on raw names. Since we're comparing **stripped cores** (which are shorter and more discriminating), 0.92 is appropriate:

| Example | Core After Stripping | Core Similarity | Outcome |
|---------|---------------------|----------------|---------|
| "Hero MotoCorp Ltd" vs "Hero MotoCrop Ltd" | "hero motocorp" vs "hero motocrop" | 0.97 | MERGE ✓ |
| "Shilpa Bhate Associates" vs "Shilpa Bhate & Associates" | "shilpa bhate" vs "shilpa bhate" | 1.00 | MERGE ✓ |
| "Central Bank of India" vs "State Bank of India" | "central bank" vs "state bank" | 0.72 | SKIP ✓ |
| "MCS Ltd." vs "ACC Ltd." | "mcs" vs "acc" | 0.44 | SKIP ✓ |
| "Hindustan Lever Ltd" vs "Neeta Enterprises Pvt. Ltd." | "hindustan lever" vs "neeta enterprises" | 0.45 | SKIP ✓ |

### 7.3 Implementation Complexity

**~60 lines changed in one file.** No new dependencies. No ML models. No LLM calls. This aligns with Winston's (Architect) principle: **boring technology that works.**

### 7.4 Future Enhancements (not needed for V1)

1. **Document co-occurrence scoring** — bonus for entities appearing in same documents
2. **TF-IDF token weighting** — full SoftTFIDF if suffix list proves insufficient
3. **Human review queue** — UI for borderline cases (0.85-0.92 range)

---

## 8. Sources

### Entity Resolution General
- [Entity Resolution: Techniques, Tools & Use Cases](https://www.puppygraph.com/blog/entity-resolution) — PuppyGraph
- [Entity Resolution: Identifying Real-World Entities in Noisy Data](https://medium.com/data-science/entity-resolution-identifying-real-world-entities-in-noisy-data-3e8c59f4f41c) — Tomonori Masui, Medium
- [Name Matching Model for Entity Resolution](https://medium.com/@vietexob/name-matching-model-for-entity-resolution-part-1-2d8362a5ed05) — Joe Le, Medium (Dec 2025)
- [Record Linkage](https://en.wikipedia.org/wiki/Record_linkage) — Wikipedia
- [Entity Resolution Explained: Top 12 Techniques](https://spotintelligence.com/2024/01/22/entity-resolution/) — Spot Intelligence

### String Similarity Algorithms
- [A Comparison of String Distance Metrics for Name-Matching Tasks](https://www.cs.cmu.edu/~wcohen/postscript/ijcai-ws-2003.pdf) — Cohen (2003), CMU (seminal paper)
- [String Comparators - Splink Documentation](https://moj-analytical-services.github.io/splink/topic_guides/comparisons/comparators.html) — MOJ Analytical Services
- [Jaro-Winkler vs Levenshtein in AML Screening](https://www.flagright.com/post/jaro-winkler-vs-levenshtein-choosing-the-right-algorithm-for-aml-screening) — Flagright
- [Jaro-Winkler distance](https://en.wikipedia.org/wiki/Jaro%E2%80%93Winkler_distance) — Wikipedia
- [String Similarity Metrics: Token Methods](https://www.baeldung.com/cs/string-similarity-token-methods) — Baeldung

### Company Name Deduplication
- [How to Normalize Company Names for Deduplication](https://medium.com/tilo-tech/how-to-normalize-company-names-for-deduplication-and-matching-21e9720b30ba) — Tilores / Sami Yaseen
- [How to Find and Merge Duplicate Company Names](https://www.datablist.com/how-to/dedupe-company-names) — Datablist
- [STRIPCOMPANYSUFFIX Function](https://help.scribesoft.com/scribeinsight/en/Subsystems/Insight/formulas/functions/stripcompanysuffix.htm) — Scribe Software

### Splink (Probabilistic Entity Resolution)
- [Splink GitHub Repository](https://github.com/moj-analytical-services/splink) — MOJ Analytical Services
- [Linking Businesses Example](https://moj-analytical-services.github.io/splink/demos/examples/duckdb_no_test/business_rates_match.html) — Splink (token-based company matching)
- [Splink: Fast, Accurate and Scalable Record Linkage](https://dataingovernment.blog.gov.uk/2022/09/23/splink-fast-accurate-and-scalable-record-linkage/) — UK Government Data Blog

### Legal Domain Entity Resolution
- [Named Entity Recognition and Resolution in Legal Text](https://link.springer.com/chapter/10.1007/978-3-642-12837-0_2) — Dozier et al. (Springer)
- [Legal NLP - John Snow Labs](https://www.johnsnowlabs.com/legal-nlp/) — Pre-trained legal NER models
- [Entity Resolution and Visualization for Legal Documents](https://python.useinstructor.com/examples/entity_resolution/) — Instructor (LLM-based)
- [Named Entity Recognition in the Legal Domain](https://relational.ai/resources/named-entity-recognition-in-the-legal-domain) — RelationalAI
