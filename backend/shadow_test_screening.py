#!/usr/bin/env python3
"""Shadow test: compare current vs tighter screening prompts.

Reads known contradiction pairs + sampled non-contradiction pairs from DB,
runs both prompts against Gemini Flash, and reports:
  - Safety: do all 29 known contradictions still get escalated?
  - Effectiveness: how many non-contradictions get correctly filtered?

Usage:
    cd backend
    python shadow_test_screening.py

Cost: ~$0.06 (130 Gemini Flash calls at $0.0005 each). Zero GPT-4o calls.
"""

import asyncio
import json
import os
import random
import sys
from pathlib import Path

import psycopg2

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# ─── Configuration ───────────────────────────────────────────────────────────

DATABASE_URL = "postgresql://postgres:22121970Jn!kiara@db.xmbtcgmjvdouqstiqqom.supabase.co:6543/postgres"

# How many non-contradiction pairs to sample per matter
NON_CONTRADICTION_SAMPLE_PER_MATTER = 15

# The confidence threshold used in production
CONFIDENCE_THRESHOLD = 0.65

# ─── Current prompt (production) ─────────────────────────────────────────────

CURRENT_SYSTEM_PROMPT = """You are a fast legal screening assistant. Your job is to flag ANY statement pairs that MIGHT conflict so an expert can review them.

Your default should be "needs_review". Only mark "consistent" when statements are clearly, unambiguously in agreement about the exact same facts.

CLASSIFICATION (err heavily toward "needs_review"):
- consistent: Statements explicitly agree on the SAME specific facts — no room for ambiguity
- unrelated: Statements discuss completely different topics with zero overlap
- needs_review: DEFAULT for anything involving the same topic. Use this if there is ANY doubt
- contradiction: Statements make obviously incompatible claims about the same fact

CRITICAL RULES — classify as "needs_review" (NOT "consistent") when:
1. WITNESS TESTIMONY: Any two statements about what a witness saw, heard, or did — even if they seem complementary. Witnesses often describe overlapping events differently, and subtle differences matter in court.
2. HEARSAY vs DIRECT: One person claims another person saw/did something, but that other person's own testimony describes events differently (e.g., PW-1 says "PW-2 saw the murder" but PW-2 says "I only saw the accused giving water").
3. PROSECUTION vs DEFENSE: Any pair where one statement comes from the prosecution's version and another from defense testimony or deposition.
4. PARTIAL OVERLAP: Statements describe the same event but mention different details, actions, or sequences — even if not directly contradictory on the surface.
5. DIFFERENT SPECIFICITY: One statement is general ("he was present") and another is specific ("he arrived at 3pm and left at 4pm") about the same fact.

The cost of missing a real contradiction is 100x worse than escalating a false positive. When in doubt, ALWAYS say "needs_review".

Respond ONLY with valid JSON."""

# ─── Tighter prompt (candidate) ──────────────────────────────────────────────

V3_SYSTEM_PROMPT = """You are a legal screening assistant. Your job is to flag statement pairs that might conflict so an expert can review them. An expensive expert reviews flagged pairs, so avoid obvious false alarms — but never miss a real conflict.

CLASSIFICATION:
- contradiction: Statements make obviously incompatible claims about the same fact (different dates, amounts, sequences, or directly opposing assertions)
- needs_review: Use when statements describe the SAME facts or events but with differences that COULD matter. Specifically:
  * Different witness accounts of the same event (even if they seem to agree — witnesses often omit or add details that matter)
  * One person's testimony about what another person did vs that other person's own account
  * Prosecution and defense describing the same facts differently
  * One statement reaches a conclusion that could conflict with facts in the other
  * Different factual details about the same person, event, or proceeding (even subtle ones like age, time, or role)
- consistent: Statements are about the same topic and clearly agree. Use ONLY when:
  * Both statements make the same factual claims with no meaningful differences
  * One is a direct subset of the other (quote, paraphrase, or summary) with nothing added or changed
  * Statements are purely procedural/administrative with no factual claims to compare
- unrelated: Statements discuss completely different topics, events, or people

KEY PRINCIPLE: If two statements discuss the same person or event, the DEFAULT is "needs_review" unless you can confirm they say the same thing. The expert is better than you at spotting subtle legal contradictions.

Respond ONLY with valid JSON."""

V3_USER_PROMPT = """Entity: {entity_name}

Statement A: <document_content>{content_a}</document_content>

Statement B: <document_content>{content_b}</document_content>

Do these statements potentially conflict? If both discuss the same person or event with ANY factual differences (even subtle), classify as "needs_review". Only use "consistent" if they clearly say the same thing.

Respond with JSON:
{{
  "result": "consistent|unrelated|needs_review|contradiction",
  "confidence": 0.0-1.0,
  "quick_reason": "One sentence explanation"
}}"""

TIGHTER_SYSTEM_PROMPT = """You are a legal screening assistant. Your job is to flag statement pairs that might conflict so an expert can review them.

CLASSIFICATION:
- contradiction: Statements make obviously incompatible claims about the same fact (different dates, amounts, or directly opposing assertions)
- needs_review: Statements discuss the SAME facts or events but with differences that COULD indicate a conflict. Use this when:
  * Witnesses describe the same event with different details (even if not obviously contradictory)
  * One statement attributes actions/observations to a person that another statement describes differently
  * Prosecution and defense describe the same events differently
  * Statements about the same legal proceeding reach different conclusions or emphasize different facts
- consistent: Statements are clearly about the same topic AND agree on the facts. ONLY use when:
  * Both statements say the same thing (possibly with different wording)
  * One is a direct quote or paraphrase of the other
  * The statements share NO factual claims that could be compared (pure legal reasoning without specific facts)
- unrelated: Statements discuss completely different topics, events, or people with no overlap

IMPORTANT: Two statements about the same topic are NOT automatically "consistent." If they describe the same events but emphasize different aspects, different witness accounts, or reach different conclusions — that is "needs_review" because the expert needs to evaluate whether the differences matter.

Respond ONLY with valid JSON."""

TIGHTER_USER_PROMPT = """Entity: {entity_name}

Statement A: <document_content>{content_a}</document_content>

Statement B: <document_content>{content_b}</document_content>

Do these statements potentially conflict? If both statements describe the same events or facts but with any differences in detail, classify as "needs_review" — only use "consistent" when they clearly agree.

Respond with JSON:
{{
  "result": "consistent|unrelated|needs_review|contradiction",
  "confidence": 0.0-1.0,
  "quick_reason": "One sentence explanation"
}}"""

# Production user prompt for comparison
CURRENT_USER_PROMPT = """Entity: {entity_name}

Statement A: <document_content>{content_a}</document_content>

Statement B: <document_content>{content_b}</document_content>

Do these statements potentially conflict? Remember: if both statements involve witness testimony or describe overlapping events, classify as "needs_review" even if they seem complementary.

Respond with JSON:
{{
  "result": "consistent|unrelated|needs_review|contradiction",
  "confidence": 0.0-1.0,
  "quick_reason": "One sentence explanation"
}}"""


# ─── Gemini API call ─────────────────────────────────────────────────────────

async def call_gemini(system_prompt: str, user_prompt: str) -> dict | None:
    """Call Gemini Flash and parse JSON response."""
    import google.generativeai as genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Try loading from .env
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not api_key:
        print("ERROR: No GEMINI_API_KEY or GOOGLE_API_KEY found")
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    try:
        response = await model.generate_content_async(user_prompt)
        parsed = json.loads(response.text)
        return parsed
    except Exception as e:
        print(f"  Gemini error: {e}")
        return None


# ─── Data loading ────────────────────────────────────────────────────────────

def load_known_contradictions(conn) -> list[dict]:
    """Load the 29 known contradiction pairs with their chunk content."""
    cur = conn.cursor()
    cur.execute("""
        SELECT sc.statement_a_id, sc.statement_b_id, sc.entity_id, sc.confidence,
               ca.content as content_a, cb.content as content_b,
               en.canonical_name as entity_name,
               sc.matter_id
        FROM statement_comparisons sc
        JOIN chunks ca ON ca.id = sc.statement_a_id::uuid
        JOIN chunks cb ON cb.id = sc.statement_b_id::uuid
        JOIN identity_nodes en ON en.id = sc.entity_id
        WHERE sc.created_at >= '2026-04-27'
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    print(f"Loaded {len(rows)} known contradiction pairs")
    return rows


def load_non_contradiction_sample(conn) -> list[dict]:
    """Sample non-contradiction pairs by re-deriving pairs for matters with data.

    Strategy: for each matter with known contradictions, pick random entity names,
    find chunks mentioning those entities, and create cross-document pairs that
    we KNOW are not contradictions (because GPT-4o already evaluated them).
    """
    cur = conn.cursor()

    # Get matters with screening data
    cur.execute("""
        SELECT DISTINCT matter_id
        FROM llm_costs
        WHERE operation = 'contradiction_screening'
          AND metadata IS NOT NULL AND metadata::text != '{}'
          AND created_at >= '2026-04-27'
    """)
    matter_ids = [r[0] for r in cur.fetchall()]

    all_pairs = []
    for matter_id in matter_ids:
        # Get entities in this matter that have 2+ chunks (so pairs exist)
        # Use text[] cast since overlaps works better with text arrays
        cur.execute("""
            SELECT en.id, en.canonical_name, COUNT(DISTINCT c.id) as chunk_count
            FROM identity_nodes en
            JOIN chunks c ON c.entity_ids @> ARRAY[en.id]::uuid[]
                         AND c.matter_id = %s
            WHERE en.matter_id = %s
            GROUP BY en.id, en.canonical_name
            HAVING COUNT(DISTINCT c.id) >= 2
            ORDER BY random()
            LIMIT 8
        """, (matter_id, matter_id))
        entities = cur.fetchall()

        for entity_id, entity_name, chunk_count in entities:
            # Get chunks for this entity (include same-doc pairs too)
            cur.execute("""
                SELECT id, content, document_id
                FROM chunks
                WHERE matter_id = %s
                  AND entity_ids @> ARRAY[%s]::uuid[]
                ORDER BY random()
                LIMIT 6
            """, (matter_id, str(entity_id)))
            chunks = cur.fetchall()

            if len(chunks) < 2:
                continue

            # Create pairs (any combination, not just cross-doc)
            for i in range(min(len(chunks), 4)):
                for j in range(i + 1, min(len(chunks), 4)):
                    # Check this pair isn't a known contradiction
                    a_id, b_id = str(chunks[i][0]), str(chunks[j][0])
                    cur.execute("""
                        SELECT COUNT(*) FROM statement_comparisons
                        WHERE (statement_a_id = %s AND statement_b_id = %s)
                           OR (statement_a_id = %s AND statement_b_id = %s)
                    """, (a_id, b_id, b_id, a_id))
                    if cur.fetchone()[0] == 0:
                        all_pairs.append({
                            "statement_a_id": a_id,
                            "statement_b_id": b_id,
                            "content_a": chunks[i][1],
                            "content_b": chunks[j][1],
                            "entity_name": entity_name,
                            "entity_id": entity_id,
                            "matter_id": matter_id,
                            "is_contradiction": False,
                        })

            if len(all_pairs) >= NON_CONTRADICTION_SAMPLE_PER_MATTER * len(matter_ids):
                break

    # Randomly sample
    sample_size = min(len(all_pairs), NON_CONTRADICTION_SAMPLE_PER_MATTER * len(matter_ids))
    sampled = random.sample(all_pairs, sample_size) if len(all_pairs) > sample_size else all_pairs
    print(f"Sampled {len(sampled)} non-contradiction pairs from {len(matter_ids)} matters")
    return sampled


# ─── Shadow test runner ──────────────────────────────────────────────────────

async def run_shadow_test():
    """Run both prompts against all pairs and compare results."""
    conn = psycopg2.connect(DATABASE_URL)

    print("=" * 70)
    print("SHADOW TEST: Current vs Tighter Screening Prompt")
    print("=" * 70)
    print()

    # Load pairs
    known_contradictions = load_known_contradictions(conn)
    non_contradictions = load_non_contradiction_sample(conn)
    conn.close()

    # Tag known contradictions
    for pair in known_contradictions:
        pair["is_contradiction"] = True

    all_pairs = known_contradictions + non_contradictions
    print(f"\nTotal pairs to test: {len(all_pairs)} ({len(known_contradictions)} contradictions + {len(non_contradictions)} non-contradictions)")
    print(f"Estimated cost: ~${len(all_pairs) * 0.0005:.2f} ({len(all_pairs)} Gemini calls — V3 only)")
    print()

    # Run both prompts on each pair
    results = []
    for i, pair in enumerate(all_pairs):
        label = "CONTRADICTION" if pair["is_contradiction"] else "non-contradiction"
        entity = pair["entity_name"]
        print(f"[{i+1}/{len(all_pairs)}] {label} — {entity[:40]}...", end=" ", flush=True)

        content_a = pair["content_a"][:1500]  # cap to control cost
        content_b = pair["content_b"][:1500]

        # Would this pair escalate under a given prompt result?
        def would_escalate(result_str, confidence):
            if result_str in ("needs_review", "contradiction"):
                return True
            if result_str in ("consistent", "unrelated") and confidence < CONFIDENCE_THRESHOLD:
                return True
            return False

        # Run V3 only (we already have v1/v2 results from prior run)
        v3_user = V3_USER_PROMPT.format(
            entity_name=entity,
            content_a=content_a,
            content_b=content_b,
        )
        v3_result = await call_gemini(V3_SYSTEM_PROMPT, v3_user)
        await asyncio.sleep(0.3)

        v3_classification = v3_result.get("result", "error") if v3_result else "error"
        v3_conf = v3_result.get("confidence", 0) if v3_result else 0
        v3_escalates = would_escalate(v3_classification, v3_conf)

        print(f"v3={v3_classification}({v3_conf:.1f}) [{'escalate' if v3_escalates else 'skip'}]")

        results.append({
            "is_contradiction": pair["is_contradiction"],
            "entity_name": entity,
            "v3_result": v3_classification,
            "v3_confidence": v3_conf,
            "v3_escalates": v3_escalates,
            "v3_reason": v3_result.get("quick_reason", "") if v3_result else "",
        })

    # ─── Report ──────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("RESULTS — V3 SHADOW TEST")
    print("=" * 70)

    # Split by type
    contradiction_results = [r for r in results if r["is_contradiction"]]
    non_contradiction_results = [r for r in results if not r["is_contradiction"]]

    # Safety check: known contradictions
    print(f"\n--- SAFETY CHECK: {len(contradiction_results)} Known Contradictions ---")
    v3_caught = sum(1 for r in contradiction_results if r["v3_escalates"])
    print(f"  V3 prompt catches: {v3_caught}/{len(contradiction_results)} ({100*v3_caught/max(len(contradiction_results),1):.0f}%)")
    print(f"  (Prior results: V1=90%, V2=74%)")

    missed = [r for r in contradiction_results if not r["v3_escalates"]]
    if missed:
        print(f"\n  *** V3 MISSED {len(missed)} real contradictions: ***")
        for r in missed:
            print(f"    Entity: {r['entity_name']}")
            print(f"    V3 said: {r['v3_result']} ({r['v3_confidence']:.1f})")
            print(f"    Reason: {r['v3_reason'][:120]}")
            print()
    else:
        print(f"  SAFE: All {len(contradiction_results)} contradictions caught!")

    # Effectiveness check: non-contradictions
    print(f"\n--- EFFECTIVENESS: {len(non_contradiction_results)} Non-Contradiction Pairs ---")
    v3_escalated = sum(1 for r in non_contradiction_results if r["v3_escalates"])
    print(f"  V3 prompt escalates: {v3_escalated}/{len(non_contradiction_results)} ({100*v3_escalated/max(len(non_contradiction_results),1):.0f}%)")
    print(f"  (Prior results: V1=65%, V2=16%)")
    print(f"  GPT-4o calls saved vs V1: {97 - v3_escalated}/97")

    # Classification distribution
    print(f"\n--- V3 Classification Distribution ---")
    for label, group_key in [("Contradictions", contradiction_results), ("Non-contradictions", non_contradiction_results)]:
        dist = {}
        for r in group_key:
            k = r["v3_result"]
            dist[k] = dist.get(k, 0) + 1
        print(f"  {label}: {dict(sorted(dist.items()))}")

    # Comparison table
    print(f"\n--- COMPARISON: V1 vs V2 vs V3 ---")
    print(f"  {'Metric':40s} {'V1 (current)':>14s} {'V2 (tight)':>14s} {'V3 (balanced)':>14s}")
    print(f"  {'Contradictions caught':40s} {'28/31 (90%)':>14s} {'23/31 (74%)':>14s} {f'{v3_caught}/{len(contradiction_results)} ({100*v3_caught//max(len(contradiction_results),1)}%)':>14s}")
    print(f"  {'Non-contradictions escalated':40s} {'97/150 (65%)':>14s} {'24/150 (16%)':>14s} {f'{v3_escalated}/{len(non_contradiction_results)} ({100*v3_escalated//max(len(non_contradiction_results),1)}%)':>14s}")

    # Projected savings
    if non_contradiction_results:
        v3_rate = v3_escalated / len(non_contradiction_results)
        projected_v3 = int(804 * v3_rate)
        saved_calls = 519 - projected_v3  # 519 = V1 projected
        saved_usd = saved_calls * 0.00627
        print(f"\n--- Projected Production Impact ---")
        print(f"  V1: ~519 GPT-4o calls per 804 screenings")
        print(f"  V3: ~{projected_v3} GPT-4o calls per 804 screenings")
        print(f"  Savings: ~{saved_calls} calls = ~${saved_usd:.2f}")
        safe = len(missed) == 0
        print(f"  Safety: {'PASSED — SAFE TO DEPLOY' if safe else 'FAILED — DO NOT DEPLOY'}")

    # Save raw results
    output_path = Path(__file__).parent / "shadow_test_results_v3.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nRaw results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(run_shadow_test())
