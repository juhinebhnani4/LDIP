# Epic 6 Error Report: Engine Orchestrator

This document outlines the errors, vulnerabilities, and improvement areas identified during the code review of Epic 6 (Engine Orchestrator).

## 1. Critical Security Vulnerabilities

### [CRITICAL] Audit Trail Bypass (NFR24 Violation)
**Location**: `backend/app/engines/orchestrator/orchestrator.py`

**Issue**:
The `process_query` method treats `user_id` as optional (`str | None = None`). The audit logging logic wraps its execution in a conditional check:
```python
if user_id:
    task = asyncio.create_task(self._log_query_audit(...))
```
If `user_id` is not provided (e.g., during internal system calls, testing, or if an API endpoint fails to pass it), **no audit record is created**. This violates **NFR24 (Complete Audit Trail)**, which requires forensic logging of *all* queries.

**Impact**:
Queries executed without a user context are invisible to the audit logs, creating a security blind spot.

**Recommended Fix**:
1.  Make `user_id` a **required** argument in `process_query`.
2.  If system-level queries are permitted, enforce a specific system user ID (e.g., `"system"`) rather than `None`.
3.  Remove the `if user_id:` check and ensure `log_query` handles system users correctly.

---

## 2. Logic Conflict / Runtime Crash

### [MEDIUM] Potential Audit Failure on Missing User
**Location**: `backend/app/models/orchestrator.py`

**Issue**:
The `QueryAuditEntry` model defines `asked_by` as a required field:
```python
class QueryAuditEntry(BaseModel):
    # ...
    asked_by: str = Field(description="User ID who asked the query")
    # ...
```
If the orchestrator logic were modified to log audits even when `user_id` is `None` (to fix the bypass above), it would crash with a Pydantic validation error because `asked_by` cannot be None.

**Recommended Fix**:
Ensure the fix for the Audit Trail Bypass passes a valid string for `asked_by`, or update the model to allow for a "SYSTEM" or "UNKNOWN" sentinel value, but do *not* make the field optional.

---

## 3. Verification Gaps

### [LOW] Hardcoded Confidence Weights
**Location**: `backend/app/engines/orchestrator/aggregator.py`

**Issue**:
Engine confidence weights are hardcoded in the module:
```python
ENGINE_CONFIDENCE_WEIGHTS: dict[EngineType, float] = {
    EngineType.CITATION: 1.0,
    EngineType.TIMELINE: 1.0,
    EngineType.CONTRADICTION: 1.2,
    EngineType.RAG: 0.8,
}
```
This makes tuning the orchestration logic difficult without code deployment.

**Recommended Fix**:
Move these weights to `app/core/config.py` or a database configuration to allow for runtime adjustments.

---

## 4. Code Quality & Cleanup

### [LOW] Magic Numbers in RAG Adapter
**Location**: `backend/app/engines/orchestrator/adapters.py`

**Issue**:
`RAG_SEARCH_LIMIT = 20` and `RAG_RERANK_TOP_N = 5` are defined as constants at the top of the file. These should ideally be configurable via environment variables or the `settings` module to allow for performance tuning.

### [LOW] "H3 Fix" Comment References
**Location**: `backend/app/engines/orchestrator/orchestrator.py`

**Issue**:
Comments like `# H3 Fix: Create audit entry and persist to database` refer to specific hotfixes or tickets. While helpful for context, ensure the "H3" reference is documented in the project's issue tracker or changelog, otherwise it becomes obscure legacy knowledge.

---

## 5. Summary of Review

| Category | Count | Status |
| :--- | :--- | :--- |
| **Critical Security** | 1 | 🔴 **Requires Immediate Fix** |
| **Logic/Runtime** | 1 | 🟡 **Needs Attention** |
| **Verification Gaps** | 1 | 🟢 **Low Priority** |
| **Code Cleanup** | 2 | 🟢 **Low Priority** |

**Reviewer Verdict**:
**FAIL**. The Audit Trail Bypass is a critical violation of NFR24. The orchestrator must enforce audit logging for *every* execution, regardless of the source. Logic is otherwise sound, with good use of concurrency and error handling.
