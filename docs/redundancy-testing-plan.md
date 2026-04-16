# Redundancy & Over-Engineering Testing Plan

> Goal: Empirically determine what's redundant in the system after real users start using the product.
> Don't cut based on opinion — cut based on measurement.

---

## 1. Table Activity Monitor

Run this SQL query after 2-4 weeks of real usage to see which tables are actually being used:

```sql
SELECT
  schemaname,
  relname AS table_name,
  n_tup_ins AS total_inserts,
  n_tup_upd AS total_updates,
  n_live_tup AS live_rows,
  last_autoanalyze AS last_activity
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;
```

**Decision rule**: Any table with 0 rows after 4 weeks is dead weight. Any table with rows but 0 updates might be write-once noise.

---

## 2. API Endpoint Hit Counter

Add a lightweight Redis middleware to count endpoint hits per day:

```python
# One counter per endpoint per day
key = f"api_hits:{date}:{request.method}:{request.url.path}"
redis.incr(key)
redis.expire(key, 60 * 60 * 24 * 30)  # 30 day TTL
```

After a few weeks, query which endpoints were never called:

```python
keys = redis.keys("api_hits:*")
# Group by endpoint path, sort by total hits
```

**Expected result**: Out of 180+ endpoints, 40-60% likely get zero hits from real users. Those are deprecation candidates.

---

## 3. Frontend Feature Usage Tracker

Cheapest possible version — a global event logger using localStorage:

```typescript
// lib/analytics/usage.ts
export function trackFeature(feature: string) {
  const key = `feature_usage`;
  const data = JSON.parse(localStorage.getItem(key) || '{}');
  data[feature] = (data[feature] || 0) + 1;
  localStorage.setItem(key, JSON.stringify(data));
}
```

Sprinkle in key places:

```typescript
trackFeature('tab:timeline');
trackFeature('tab:contradictions');
trackFeature('export:pptx');
trackFeature('export:pdf');
trackFeature('ab_testing:started');
trackFeature('verification:approved');
trackFeature('split_view:opened');
trackFeature('orchestrator:multi_engine');
```

When talking to pilot users, pull this from their browser to see which features they actually use.

---

## 4. Specific Hypotheses to Test

| Hypothesis | How to Test | Decision Rule |
|---|---|---|
| `activities` + `notifications` are redundant | Query both tables after 4 weeks | If users only read one and ignore the other, merge into one table |
| Evaluation framework (4 tables) is premature | Track: does anyone besides devs trigger A/B tests or golden dataset evals? | If only devs use it, move out of prod schema |
| Dual embeddings waste storage | `SELECT embedding_model_version, count(*) FROM chunks GROUP BY 1` | If 100% use one provider, delete the other column |
| Safety modules are overkill | Add counter: `redis.incr("safety:blocked")` every time safety guard blocks something | After 4 weeks, if count is 0, not earning its cost (but keep `injection_detector` — uploaded PDFs are a real attack vector) |
| PPTX export is unused | `SELECT format, count(*) FROM exports GROUP BY format` | Zero PPTX rows = cut it |
| Orchestrator is overkill | Track multi-engine queries vs. single-tab queries | If 95% of queries go to one engine, orchestrator/planner/aggregator is overhead |
| `data_residency` is premature | `SELECT data_residency, count(*) FROM matters GROUP BY 1` | If 100% are 'default', the enum is dead code |
| `job_stage_history` is overkill | `SELECT count(*) FROM job_stage_history` + ask: was this table ever queried to debug a prod issue? | If never queried for debugging, it's write-only waste |
| `matter_memory` + `matter_query_history` overlap | Check if `matter_memory` rows with `memory_type = 'query_history'` exist alongside `matter_query_history` rows | If both are populated for the same matter, one is redundant |
| `ocr_validation_log` + `ocr_human_review` overlap | Check if human review results always create validation log entries | If so, human review is just a status on validation log |
| `consistency_issues` vs `statement_comparisons` vs `anomalies` | Check if the UI presents these separately or in a unified "issues" view | If users see them as one list, merge into one table |

---

## 5. Pilot Protocol

| Week | Action |
|---|---|
| Week 0 | Deploy Redis hit counters + frontend `trackFeature` calls (~2 hours) |
| Week 0 | Create saved SQL query for table activity monitor, bookmark it |
| Weeks 1-4 | Let pilot users (even 2-3) use the product naturally, don't guide them |
| Week 4 | Pull all data: table rows, endpoint hits, frontend feature usage |
| Week 5 | Cut everything with zero usage, merge everything with overlapping usage |

---

## Background: Structural Redundancies (Observable Facts)

These are confirmed from the schema — not assumptions:

1. **`activities` + `notifications`** — Both have `user_id`, `matter_id`, `is_read`, `created_at`, type field, description/message field
2. **`matter_memory` (with `memory_type = 'query_history'`) + `matter_query_history`** — Generic store AND specific table for the same data
3. **Dual embedding columns** on `chunks` and `library_chunks` — Two vector columns per row regardless of usage
4. **5 verification/review tables** — `findings`, `finding_verifications`, `summary_verifications`, `summary_notes`, `summary_edits`
5. **3 "problems found" tables** — `consistency_issues`, `statement_comparisons`, `anomalies`

## Background: Potentially Over-Engineered (Needs Usage Data to Confirm)

These depend on actual usage patterns and customer requirements:

- Evaluation framework (4 tables) — justified if team runs A/B tests regularly
- `llm_pricing` with time-windowed pricing — justified if pricing changes frequently
- `llm_quota_limits` table — justified at scale, env vars suffice for small deployments
- 6 safety modules — justified if uploaded PDFs contain adversarial content
- 3 export formats — justified if customers request DOCX/PPTX
- Court certification — justified if it's a regulatory requirement
- `data_residency` enum — justified if multi-region is a contractual requirement
- Full orchestrator engine (8 modules) — justified if multi-engine queries are a differentiator
- `section_index` + `toc_pages` — justified if citation verification needs section-to-page mapping
