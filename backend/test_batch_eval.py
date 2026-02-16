"""Quick test: Insert 4 golden items and run batch evaluation.

This tests the full B1/B2/B3 fix:
1. RAGPipelineService runs questions through the orchestrator
2. RAGAS evaluates the answers
3. Results are stored with correct column names + new JSONB columns

Usage: python test_batch_eval.py
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Fix: RAGAS needs OPENAI_API_KEY as env var, not just in settings
from app.core.config import get_settings

_settings = get_settings()
if _settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _settings.openai_api_key

# Test config
MATTER_ID = "91a4a4db-bc3d-40df-8dcc-49179ac49108"  # Nirav Jobalia matter

# 4 test questions with expected answers (based on what we know about the matter)
TEST_GOLDEN_ITEMS = [
    {
        "question": "What is the case number of this matter?",
        "expected_answer": "MA NO 10 OF 2023",
        "tags": ["lookup"],
    },
    {
        "question": "Who is the applicant in this matter?",
        "expected_answer": "Jyoti H. Mehta (JHM) is the applicant in MA NO 10 OF 2023.",
        "tags": ["entity", "lookup"],
    },
    {
        "question": "Who is Nirav D Jobalia in this case?",
        "expected_answer": "Nirav D Jobalia is one of the respondents in MA NO 10 OF 2023.",
        "tags": ["entity"],
    },
    {
        "question": "What role does the Custodian play in this matter?",
        "expected_answer": "The Custodian is Respondent No. 1 in the matter and has filed an affidavit in reply.",
        "tags": ["entity", "general"],
    },
]


def build_evaluation_row(
    *,
    matter_id: str,
    question: str,
    answer: str,
    contexts: list[str],
    eval_result: Any,
    triggered_by: str,
    pipeline_config: dict[str, Any] | None = None,
    golden_item_id: str | None = None,
    expected_answer: str | None = None,
    job_id: str | None = None,
    chat_message_id: str | None = None,
) -> dict[str, Any]:
    """Build a row matching evaluation_results schema.

    Duplicated from evaluation_tasks._build_evaluation_row to avoid Celery import.
    """
    scores = eval_result.scores

    row: dict[str, Any] = {
        "matter_id": matter_id,
        "question": question,
        "answer": answer,
        "contexts": contexts,
        "context_recall": scores.context_recall,
        "faithfulness": scores.faithfulness,
        "answer_relevancy": scores.answer_relevancy,
        "overall_score": eval_result.overall_score,
        "metric_scores": scores.model_dump(exclude_none=True),
        "pipeline_config": pipeline_config or {},
        "triggered_by": triggered_by,
        "evaluated_at": datetime.now(UTC).isoformat(),
    }

    if golden_item_id is not None:
        row["golden_item_id"] = golden_item_id
    if expected_answer is not None:
        row["expected_answer"] = expected_answer
    if job_id is not None:
        row["job_id"] = job_id
    if chat_message_id is not None:
        row["chat_message_id"] = chat_message_id

    return row


async def main():
    from app.services.supabase.client import get_supabase_client as get_supabase

    sb = get_supabase()

    # Check: skip inserting if golden items already exist from previous run
    existing = sb.table("golden_dataset").select("id, question", count="exact").eq(
        "matter_id", MATTER_ID
    ).execute()

    if existing.count and existing.count > 0:
        print(f"\n=== Step 1: Using {existing.count} existing golden items ===")
        inserted_ids = [item["id"] for item in existing.data]
        for item in existing.data:
            print(f"  Existing: {item['question'][:50]}... (id: {item['id'][:8]})")
    else:
        print("\n=== Step 1: Inserting golden dataset items ===")
        inserted_ids = []
        for item in TEST_GOLDEN_ITEMS:
            result = sb.table("golden_dataset").insert({
                "matter_id": MATTER_ID,
                "question": item["question"],
                "expected_answer": item["expected_answer"],
                "tags": item["tags"],
            }).execute()
            item_id = result.data[0]["id"]
            inserted_ids.append(item_id)
            print(f"  Inserted: {item['question'][:50]}... (id: {item_id[:8]})")

    print(f"  Total: {len(inserted_ids)} golden items")

    # Get the actual questions (either from TEST_GOLDEN_ITEMS or DB)
    golden_items = sb.table("golden_dataset").select("*").eq(
        "matter_id", MATTER_ID
    ).execute()
    items_data = golden_items.data

    # Step 2: Run each through RAG pipeline
    print("\n=== Step 2: Running questions through RAG pipeline ===")
    from app.services.rag.pipeline_service import get_rag_pipeline_service

    pipeline = get_rag_pipeline_service()

    rag_results = []
    for item in items_data:
        print(f"\n  Q: {item['question']}")
        try:
            result = await pipeline.query(
                matter_id=MATTER_ID,
                question=item["question"],
            )
            print(f"  A: {result.answer[:120]}...")
            print(f"  Contexts: {len(result.contexts)}, Sources: {len(result.sources)}, Time: {result.execution_time_ms}ms")
            rag_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            rag_results.append(None)

    # Step 3: Evaluate with RAGAS
    print("\n=== Step 3: Running RAGAS evaluation ===")
    from app.services.evaluation import get_ragas_evaluator

    evaluator = get_ragas_evaluator()

    eval_results = []
    for item, rag_result in zip(items_data, rag_results):
        if rag_result is None:
            eval_results.append(None)
            continue

        print(f"\n  Evaluating: {item['question'][:50]}...")
        try:
            eval_result = await evaluator.evaluate_single(
                question=item["question"],
                answer=rag_result.answer,
                contexts=rag_result.contexts or ["No context"],
                ground_truth=item["expected_answer"],
            )
            print(f"  Faithfulness: {eval_result.scores.faithfulness}")
            print(f"  Relevancy:    {eval_result.scores.answer_relevancy}")
            print(f"  Recall:       {eval_result.scores.context_recall}")
            print(f"  Overall:      {eval_result.overall_score:.3f}")
            eval_results.append(eval_result)
        except Exception as e:
            print(f"  RAGAS ERROR: {e}")
            eval_results.append(None)

    # Step 4: Store results
    print("\n=== Step 4: Storing results in evaluation_results ===")
    stored_count = 0
    for item, rag_result, eval_result in zip(items_data, rag_results, eval_results):
        if rag_result is None or eval_result is None:
            continue

        row = build_evaluation_row(
            matter_id=MATTER_ID,
            question=item["question"],
            answer=rag_result.answer,
            contexts=rag_result.contexts or [],
            eval_result=eval_result,
            triggered_by="test",
            pipeline_config=rag_result.pipeline_config,
            golden_item_id=item["id"],
            expected_answer=item["expected_answer"],
            job_id="test-batch-001",
        )

        try:
            sb.table("evaluation_results").insert(row).execute()
            stored_count += 1
            print(f"  OK: {item['question'][:40]}... (score: {eval_result.overall_score:.2f})")
        except Exception as e:
            print(f"  DB ERROR: {e}")

    # Step 5: Verify
    print(f"\n=== Step 5: Verification ===")
    results = sb.table("evaluation_results").select("*").eq("job_id", "test-batch-001").execute()
    print(f"  Results in DB: {len(results.data)}")

    for r in results.data:
        print(f"\n  Q: {r['question'][:50]}")
        print(f"  A: {r['answer'][:80]}...")
        print(f"  faith={r['faithfulness']}  rel={r['answer_relevancy']}  recall={r['context_recall']}  overall={r['overall_score']}")
        print(f"  metric_scores: {r['metric_scores']}")
        print(f"  pipeline_config: {r['pipeline_config']}")
        print(f"  triggered_by={r['triggered_by']}  job_id={r['job_id']}  golden_item_id={r['golden_item_id'][:8]}...")

    print(f"\n=== DONE: {stored_count}/{len(items_data)} evaluations stored successfully ===")


if __name__ == "__main__":
    asyncio.run(main())
