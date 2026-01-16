# Code Review Findings: Consistency & Contradiction Engine (Epic 5)

**Review Status**: 🔴 **CRITICAL FAIL**
**Scope**: Full Epic 5 (Story 5-1 to 5-4) - Implementation & Security Review

## 🚨 Critical Security Vulnerabilities (Must Fix Immediately)

### 1. Data Integrity & RLS Gap: Orphaned/Cross-Matter Comparisons
- **Severity**: **CRITICAL**
- **Affected File**: `supabase/migrations/20260114000004_create_statement_comparisons_table.sql`
- **Vulnerability**: The `statement_comparisons` table lacks Foreign Key constraints for `statement_a_id` and `statement_b_id` referencing `chunks.id`.
  - **Risk 1 (Orphans)**: If chunks are deleted, comparisons remain as corrupt data.
  - **Risk 2 (Cross-Matter Pollution)**: There is no SQL-level enforcement that `statement_a_id` and `statement_b_id` belong to the same `matter_id` as the comparison record. A compromised user account (or SQL injection) could insert comparisons linking statements from Matter A into Matter B, creating data leaks or false contradictions.
- **Fix**: Add FK constraints to `chunks(id)` and a trigger or check constraint ensuring `(statement_a_id -> matter_id) == comparison.matter_id`.

### 2. Verification Gap: Mocked Security & Logic Tests
- **Severity**: **CRITICAL**
- **Affected Files**: `backend/tests/api/routes/test_contradiction.py`
- **Impact**: Tests rely entirely on `AsyncMock` for service layer interactions.
  - **RLS Untested**: The `get_entity_statements` and `compare` endpoints are NOT tested against a real database. The RLS policies implemented in SQL are effectively untested.
  - **Logic Untested**: The `ValueExtractor` (regex patterns) and `StatementComparator` (suspicion scoring) logic is never exercised in the API tests. The tests only verify that "If the service returns X, the API returns X".
- **Fix**: Add integration tests using the local Supabase instance to verify RLS enforcement and actual data retrieval/comparison flows.

## 🟡 Medium Issues

### 3. Untyped JSONB Evidence
- **Severity**: Medium
- **Affected File**: `supabase/migrations/20260114000004_create_statement_comparisons_table.sql`
- **Impact**: The `evidence` column is `JSONB` without a schema validator. While `pydantic` models exist in the app, the database allows any arbitrary JSON. This makes direct SQL querying/reporting fragile if data format evolves.
- **Fix**: Consider promoting critical evidence fields (e.g., `evidence_type`) to proper columns or adding a JSON schema constraint check.

### 4. Hard-Coded Scalability Limit
- **Severity**: Low/Medium
- **Affected File**: `backend/app/engines/contradiction/comparator.py`
- **Impact**: The `ASYNC_THRESHOLD` is hardcoded to 100 statements. For entities with >100 statements (common in large legal matters), the synchronous API rejects the request (`422 Unprocessable Entity`). Without a corresponding Async Job implementation (which seems referenced but not fully visible/tested here), this feature breaks for heavy users.

### 5. Missing Test Coverage for Regex Logic
- **Severity**: Medium
- **Affected File**: `backend/app/engines/contradiction/statement_query.py`
- **Impact**: The `ValueExtractor` contains complex regex for Indian date/amount formats. There are no dedicated unit tests visible for `ValueExtractor` to ensure it handles edge cases (e.g., "Rs. 5,00.00", "5 lakhs", different date separators) correctly.
