# Code Review Findings: Timeline Engine (Epic 4)

**Review Status**: 🔴 **CRITICAL FAIL**
**Scope**: Timeline Construction Engine, Date Extraction, Event Classification, Anomaly Detection

## 🚨 Critical Security & Performance Vulnerabilities (Must Fix Immediately)

### 1. Denial of Service (OOM) / Scalability Failure
- **Severity**: **CRITICAL**
- **Affected File**: `backend/app/engines/timeline/timeline_builder.py` (Lines 227-231)
- **Vulnerability**: The `build_timeline` method attempts to load **ALL** entities for a matter into memory to establish relationships:
  ```python
  entities, _ = await self.mig_service.get_entities_by_matter(
      matter_id=matter_id,
      page=1,
      per_page=10000,  # DANGEROUS: Loads essentially entire graph into RAM
  )
  ```
- **Exploit/Impact**: For large matters (e.g., "Nirav Jobalia Share Sale Case" with thousands of entities), this will cause the backend worker to run Out of Memory (OOM) and crash, effectively causing a Denial of Service.
- **Fix**: Use batch processing or fetch entities lazily/by ID subset. Do not fetch `per_page=10000`.

### 2. Silent Logic Failure in Date Parsing
- **Severity**: High
- **Affected File**: `backend/app/engines/timeline/date_extractor.py` (Line 653)
- **Bug**: The manual date parsing relies on unchecked integer conversion:
  ```python
  extracted_date = date(int(date_parts[0]), ...)
  ```
  It catches `ValueError` but logs it as debug and returns `None`.
- **Impact**: If the LLM returns an invalid date (e.g., "2024-02-30"), the system silently drops data without alerting the user or retrying with correction. This leads to **data loss** in the timeline.
- **Fix**: Add explicit validation and potentially a "fixer" step or user alert for invalid dates.

### 3. Audit Logging Gap (Compliance Violation)
- **Severity**: High
- **Affected File**: `backend/app/api/routes/timeline.py`
- **Impact**: The APIs for creating events (manual classification) and triggering extraction (`/extract`, `/classify`) log to `stdout` (structlog) but **DO NOT** write to the `audit_logs` table.
- **Consequence**: This violates the "Layer 4" tracking requirement for legal defensibility. Actions like "Attorney X manually reclassified Event Y" are not durably recorded in the legal audit trail.
- **Fix**: Inject `AuditLogService` dependency and record meaningful events.

### 4. Algorithmic Bottleneck (Duplicate Detection)
- **Severity**: Medium/High
- **Affected File**: `backend/app/engines/timeline/anomaly_detector.py` (Lines 325-341)
- **Bug**: The duplicate detection uses a nested loop ($O(N^2)$) inside a date bucket:
  ```python
  for i in range(len(date_events)):
      for j in range(i + 1, len(date_events)):
          # fuzz.ratio comparison
  ```
- **Impact**: During bulk ingestion, if many events map to the same date (e.g., "January 1st" defaults), this will cause CPU spikes and timeout the analysis job.
- **Fix**: Use Locality Sensitive Hashing (LSH) or simple token-set pre-filtering before running expensive fuzzy matching.

---

## 🟡 Medium Issues

### 5. Context Window Limit Risk
- **Severity**: Medium
- **Affected File**: `backend/app/engines/timeline/date_extractor.py`
- **Impact**: `_split_into_chunks` uses a fixed `MAX_TEXT_LENGTH` (30k chars) with `CHUNK_OVERLAP` (500 chars).
- **Issue**: If a date's relevant context spans across the cut point (unluckily falling inside the non-overlapped region relative to the date), context is lost or the date is fragmented.
- **Fix**: Use a sentence-boundary-aware splitter (e.g., existing NLP library) rather than simple string slicing/rfind.

### 6. Hardcoded Future Outlier Logic
- **Severity**: Low
- **Affected File**: `backend/app/engines/timeline/anomaly_detector.py`
- **Issue**: `OUTLIER_YEARS_FUTURE = 0`. Any event with `date > today` is flagged as an anomaly.
- **Impact**: Legitimate "Scheduled Hearings" for next week will be flagged as errors ("Future date"), causing noise for attorneys.
- **Fix**: Allow a buffer (e.g., +5 years) or check `event_type` (Hearing/Deadline = Future Allowed).

### 7. Missing Transaction Handling
- **Severity**: Medium
- **Affected File**: `backend/app/api/routes/timeline.py`
- **Impact**: The extraction endpoints queue Celery tasks but don't seem to update the `processing_jobs` table atomically or robustly. If the Celery enqueue fails, the job remains "created" but never runs.
