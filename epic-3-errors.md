# Code Review Findings: Citation Verification Engine (Epic 3)

**Review Status**: 🔴 **CRITICAL FAIL**
**Scope**: Epic 3 (Stories 3-1 to 3-4) - Citation Extraction, Verification, and Split-View UI

## 🚨 Critical Performance & Stability Issues

### 1. The Event Loop Storm (Resource Exhaustion)
- **Severity**: **CRITICAL (Server Crash Risk)**
- **Affected Files**:
  - `backend/app/workers/tasks/verification_tasks.py`
  - `backend/app/engines/citation/verifier.py`
- **Vulnerability**: The code creates and destroys a **new AsyncIO Event Loop** for *every single citation* processed in a batch.
  - `verify_citations_for_act` loops through citations.
  - Inside the loop, it calls `verifier.verify_citation_sync`, which creates a loop.
  - Then it calls `_run_async(storage.update...)`, which creates *another* loop.
- **Impact**: For an Act with 100 citations, this creates **200+ event loops** sequentially. This adds massive overhead, context switching latency, and will likely trigger "Too Many Open Files" or memory exhaustion errors under load, crashing the Celery worker.
- **Fix**: Use `asgiref.sync.async_to_sync` with a shared loop, or rewrite the Celery task to use `asyncio.run` *once* for the entire batch.

### 2. Silent Data Loss (Truncation)
- **Severity**: **CRITICAL (Correctness)**
- **Affected File**: `backend/app/engines/citation/extractor.py` (Line 225)
- **Bug**: The extractor hard-truncates text at 30,000 characters:
  ```python
  if len(text) > MAX_TEXT_LENGTH:
      text = text[:MAX_TEXT_LENGTH]
  ```
- **Impact**: Any legal document longer than ~10-15 pages will have its latter half **completely ignored**. Citations in the second half will be **silently lost** with no warning to the user. This undermines the core value proposition of the "Citation Verification" feature.
- **Fix**: Implement chunk-based processing (already available in `Chunker` service) and aggregate results, rather than truncating.

---

## 🔴 High Severity Issues

### 3. Pagination Performance Killer (Memory Bomb)
- **Severity**: High
- **Affected File**: `backend/app/api/routes/citations.py` (Line 189) & `backend/app/engines/citation/storage.py` (Line 211)
- **Bug**: The `list_citations` endpoint fetches **ALL** citations for a document/matter from the database and performs pagination **in memory** (Python slicing).
  ```python
  # storage.py
  return query.order("source_page").execute() # No limit/offset!
  
  # routes.py
  citations = citations[offset : offset + per_page]
  ```
- **Impact**: As the dataset grows (e.g., 50k citations), this API call will become ensuringly slow and eventually cause the API server to run out of memory (OOM Kill).
- **Fix**: Push `limit` and `offset` down to the Supabase SQL query in `storage.py`.

---

## 🟡 Medium Issues

### 4. Logic Race Condition (Act Resolution)
- **Severity**: Medium
- **Affected File**: `backend/app/engines/citation/storage.py` (Line 383)
- **Bug**: The `create_or_update_act_resolution` method has a fallback manual upsert (Check -> Insert/Update) if the RPC fails. This is not atomic.
- **Impact**: Concurrency (e.g., multiple batch inserts) will cause "Duplicate Key" errors if two threads try to insert the same Act Resolution simultaneously.
- **Fix**: Ensure the `upsert_act_resolution` RPC is present and reliable, or use `INSERT ... ON CONFLICT` if Supabase client supports it (it does).

### 5. Security Signature Risk (IDOR Potential)
- **Severity**: Medium
- **Affected File**: `backend/app/engines/citation/storage.py` (Line 214)
- **Bug**: `get_citations_by_document` makes `matter_id` optional.
  ```python
  async def get_citations_by_document(self, document_id: str, matter_id: str | None = None)
  ```
- **Impact**: While current usage is safe, this signature invites future developers to omit `matter_id`, potentially returning citations for a document belonging to a restricted matter (breaking Layer 4 isolation).
- **Fix**: Make `matter_id` a **required** argument to enforce isolation context at the interface level.

### 6. Verification Logic Gap
- **Severity**: Medium
- **Affected File**: `backend/app/workers/tasks/verification_tasks.py`
- **Bug**: If a single citation verification raises an unhandled exception, it is caught/logged, but that citation is left in a `PENDING` state forever (or whatever state it was). The code catches exception and increments `error` count, but does not mark the citation as `ERROR` or `FAILED` in the DB.
- **Impact**: Stuck citations that never resolve.
- **Fix**: Add a `VerificationStatus.ERROR` or `FAILED` and update the citation status in the `except` block.
