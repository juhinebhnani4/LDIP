# Story 14.7: Anomaly Detection Auto-Trigger

Status: done

## Story

As a **legal attorney using LDIP**,
I want **timeline anomalies to be automatically detected after entity linking completes during document ingestion**,
So that **I don't have to manually trigger anomaly detection and can immediately see timeline issues when processing completes**.

## Acceptance Criteria

1. **AC1: Auto-trigger after entity linking**
   - When `link_entities_for_matter` task completes successfully, anomaly detection is automatically queued
   - The `detect_timeline_anomalies` task runs with `force_redetect=False` (incremental)
   - No manual API call required to trigger detection

2. **AC2: Pipeline integration**
   - Document processing pipeline extended: extraction → classification → entity linking → **anomaly detection**
   - Anomaly detection runs as final step in timeline pipeline
   - Pipeline order preserved: only triggers after entity linking succeeds

3. **AC3: Incremental detection for single document**
   - When `link_entities_after_extraction` (single document) completes, queue anomaly detection
   - Detection scoped to events from newly processed document where practical
   - Full matter re-detection if incremental not feasible

4. **AC4: Job tracking integration**
   - Anomaly detection job created and tracked via `JobTrackingService`
   - Progress visible in processing status
   - Completion/failure states properly recorded

5. **AC5: Idempotency and error handling**
   - If anomaly detection fails, it does NOT fail the entire pipeline
   - Failed detection logged but document processing marked complete
   - Anomaly detection can be manually re-triggered via existing API

## Tasks / Subtasks

- [x] **Task 1: Modify `link_entities_for_matter` to auto-trigger anomaly detection** (AC: #1, #2)
  - [x] 1.1 In `backend/app/workers/tasks/engine_tasks.py`, locate `link_entities_for_matter` task (line ~875)
  - [x] 1.2 After successful completion (before `return`), add auto-trigger code
  - [x] 1.3 Add import at top if not present: ensure `detect_timeline_anomalies` is available
  - [x] 1.4 Add structured log for pipeline continuation

- [x] **Task 2: Modify `link_entities_after_extraction` to auto-trigger for single document** (AC: #3)
  - [x] 2.1 In `backend/app/workers/tasks/engine_tasks.py`, locate `link_entities_after_extraction` task (line ~1114)
  - [x] 2.2 After successful completion, add anomaly detection trigger

- [x] **Task 3: Add job tracking to auto-triggered anomaly detection** (AC: #4)
  - [x] 3.1 In `detect_timeline_anomalies` task, ensure job is created if `job_id=None`
  - [x] 3.2 Verify `JobType.ANOMALY_DETECTION` exists in `backend/app/models/job.py`

- [x] **Task 4: Implement graceful failure handling** (AC: #5)
  - [x] 4.1 Wrap anomaly detection trigger in try/except in both tasks
  - [x] 4.2 Ensure entity linking result is returned even if anomaly trigger fails

- [x] **Task 5: Write unit tests for auto-trigger** (AC: #1, #2, #3)
  - [x] 5.1 Create `backend/tests/workers/test_engine_tasks_anomaly_trigger.py`:
    - Test `link_entities_for_matter` calls `detect_timeline_anomalies.delay` on success
    - Test `link_entities_after_extraction` calls `detect_timeline_anomalies.delay` on success
    - Test no trigger when `events_with_links == 0`
    - Test trigger uses `force_redetect=False`
  - [x] 5.2 Use `unittest.mock.patch` to mock `detect_timeline_anomalies.delay`

- [x] **Task 6: Write integration test for full pipeline** (AC: #2, #4)
  - [x] 6.1 Create `backend/tests/integration/test_timeline_pipeline_with_anomalies.py`:
    - Test full flow: entity linking → anomaly detection auto-triggered
    - Verify job tracking records both stages
    - Verify anomalies are created in database
  - [x] 6.2 Test with mock events that should produce anomalies (sequence violations, gaps)

- [x] **Task 7: Write error handling tests** (AC: #5)
  - [x] 7.1 Test that entity linking succeeds even if anomaly trigger raises exception
  - [x] 7.2 Test that warning is logged when trigger fails
  - [x] 7.3 Test manual re-trigger via API still works after failed auto-trigger

## Dev Notes

### FR Reference (from MVP Gap Analysis)

> **FR2: Timeline Construction Engine** - ...flag anomalies with warnings (e.g., "Notice dated 9 months after borrower default")...

### Gap Reference

**GAP-ORCH-1: Anomaly Detection Auto-Trigger (MEDIUM)**
- Story 4.4 (line 133): "Task 4 - Integrate with timeline pipeline (DEFERRED - requires orchestration work). After entity linking completes, queue anomaly detection. Pipeline: extraction → classification → entity linking → anomaly detection. NOTE: Currently anomaly detection is triggered manually via POST /api/matters/{matter_id}/anomalies/detect"

### Architecture Compliance

**Pipeline Flow (Target State):**
```
DATE EXTRACTION (Story 4-1) ✓
  ↓
EVENT CLASSIFICATION (Story 4-2) ✓
  ↓
ENTITY LINKING (Story 4-3) ✓
  ↓
ANOMALY DETECTION (Story 4-4) ✓ → AUTO-TRIGGERED (THIS STORY)
```

**Celery Task Chaining:**
- Do NOT use Celery `chain()` - tasks are already designed with `prev_result` pattern
- Use `.delay()` to queue anomaly detection as independent task
- This allows entity linking to complete successfully regardless of anomaly detection outcome

**LLM Usage:** None required - this is pure orchestration/plumbing work.

### Existing Code to Modify

**File: `backend/app/workers/tasks/engine_tasks.py`**

1. **`link_entities_for_matter`** (line ~875-1112):
   - Currently returns result without triggering next pipeline step
   - Add anomaly detection trigger before final return

2. **`link_entities_after_extraction`** (line ~1114-1247):
   - Currently returns result for single document linking
   - Add anomaly detection trigger for incremental processing

3. **`detect_timeline_anomalies`** (line ~1254-1469):
   - Already fully implemented with job tracking
   - May need minor update to create job when `job_id=None`

### Existing Code to Reuse

**From Story 4-4 (Anomaly Detection):**
- `detect_timeline_anomalies` task is complete and tested (68 tests)
- `TimelineAnomalyDetector` class with sequence/gap/duplicate/outlier detection
- `AnomalyService` for database operations
- All API endpoints exist for manual trigger and retrieval

**From Story 4-3 (Entity Linking):**
- `link_entities_for_matter` task structure
- `link_entities_after_extraction` task structure
- Job tracking integration pattern

### Code Pattern Reference

**Auto-classification trigger pattern (existing in `extract_dates_from_document`):**
```python
# Auto-classify events if requested (Story 4-2)
if auto_classify and event_ids:
    logger.info(
        "auto_classification_triggered",
        document_id=document_id,
        events_to_classify=len(event_ids),
    )
    classify_events_for_document.delay(
        document_id=document_id,
        matter_id=matter_id,
        job_id=None,
    )
    result["classification_queued"] = True
```

**Apply same pattern for anomaly detection trigger.**

### Job Types

Verify `JobType.ANOMALY_DETECTION` exists in `backend/app/models/job.py`:
```python
class JobType(str, Enum):
    # ... existing types ...
    ANOMALY_DETECTION = "anomaly_detection"
```

### Testing Strategy

**Unit Tests (mock Celery tasks):**
```python
@patch("app.workers.tasks.engine_tasks.detect_timeline_anomalies.delay")
def test_link_entities_triggers_anomaly_detection(mock_detect):
    # Arrange
    matter_id = "test-matter-id"

    # Act
    result = link_entities_for_matter(matter_id=matter_id)

    # Assert
    mock_detect.assert_called_once_with(
        matter_id=matter_id,
        force_redetect=False,
        job_id=None,
    )
```

**Integration Tests (real task execution):**
```python
@pytest.mark.asyncio
async def test_full_pipeline_triggers_anomaly_detection():
    # Create matter with timeline events
    # Run entity linking
    # Verify anomaly detection job created
    # Verify anomalies detected and stored
```

### Pipeline Stages Update

The `PIPELINE_STAGES` constant may need updating if anomaly detection should be visible in job tracking stages:

```python
PIPELINE_STAGES = [
    "ocr",
    "validation",
    "confidence",
    "chunking",
    "embedding",
    "entity_extraction",
    "alias_resolution",
    "citation_extraction",
    "citation_verification",
    "anomaly_detection",  # Add if needed for visibility
]
```

**Note:** This is optional - anomaly detection creates its own job, so it may not need to be in the document processing pipeline stages.

### Error Handling Pattern

**Graceful degradation:**
```python
# In link_entities_for_matter, after successful completion:
try:
    if result["events_with_links"] > 0:
        detect_timeline_anomalies.delay(
            matter_id=matter_id,
            force_redetect=False,
            job_id=None,
        )
        result["anomaly_detection_queued"] = True
except Exception as e:
    logger.warning(
        "anomaly_detection_trigger_failed",
        matter_id=matter_id,
        error=str(e),
    )
    result["anomaly_detection_queued"] = False
    # Don't re-raise - entity linking succeeded

return result
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - no database changes needed

#### Environment Variables
- [ ] None - uses existing configuration

#### Dashboard Configuration
- [ ] None - no dashboard changes needed

#### Manual Tests
- [ ] Upload a document to a matter with existing timeline events
- [ ] Verify entity linking completes
- [ ] Check `processing_jobs` table for `anomaly_detection` job
- [ ] Verify anomalies appear in `GET /api/matters/{matter_id}/anomalies`
- [ ] Test that upload succeeds even if anomaly detection is slow/fails

### File Structure

```
backend/app/workers/tasks/
├── engine_tasks.py          # MODIFY - add auto-triggers
└── __init__.py

backend/tests/workers/tasks/
├── test_engine_tasks.py     # CREATE/UPDATE - unit tests

backend/tests/integration/
└── test_timeline_pipeline_with_anomalies.py  # CREATE - integration test
```

### References

- [Source: _bmad-output/implementation-artifacts/mvp-gap-analysis-2026-01-16.md#GAP-ORCH-1]
- [Source: _bmad-output/implementation-artifacts/4-4-timeline-anomaly-detection.md] - Anomaly detection implementation
- [Source: backend/app/workers/tasks/engine_tasks.py] - Current task implementations
- [Source: project-context.md] - Celery patterns, error handling conventions

## Dev Agent Record

### Agent Model Used

claude-opus-4-5-20251101

### Debug Log References

N/A

### Completion Notes List

1. **Implementation Complete (2026-01-16)**
   - Modified `link_entities_for_matter` to auto-trigger anomaly detection after successful entity linking
   - Modified `link_entities_after_extraction` to auto-trigger for single document processing
   - Added job creation when `job_id=None` in `detect_timeline_anomalies` for pipeline-triggered detection
   - Implemented graceful failure handling - entity linking succeeds even if anomaly trigger fails
   - All 18 tests passing (11 unit tests + 7 integration tests)

2. **Key Implementation Details**
   - Auto-trigger uses `force_redetect=False` for incremental detection (doesn't delete existing anomalies)
   - Job metadata includes `triggered_by: "pipeline"` to distinguish from manual triggers
   - Result dict includes `anomaly_detection_queued: true/false` flag for visibility

3. **Test Coverage**
   - Unit tests: TestLinkEntitiesForMatterAnomalyTrigger (4 tests), TestLinkEntitiesAfterExtractionAnomalyTrigger (2 tests), TestDetectTimelineAnomaliesJobCreation (2 tests), TestAnomalyTriggerGracefulFailure (2 tests), TestManualRetriggerAfterAutoTriggerFailure (1 test)
   - Integration tests: Full pipeline flow, job creation, anomaly storage, sequence/gap detection, idempotency

4. **Code Review Fixes (2026-01-16)**
   - **Issue #1 FIXED**: Added missing `_cleanup_task_loop()` to `link_entities_after_extraction` finally block
   - **Issue #2 FIXED**: Aligned trigger conditions - both tasks now trigger when `events > 0` (not just when links made)
   - **Issue #3 FIXED**: Added anomaly detection trigger to `no_mig_entities` early return path
   - **Issue #4 NOTED**: AC#3 scoped detection is at matter level (per "where practical" qualifier) - full scoped detection would require significant anomaly detector changes
   - **Issue #5 FIXED**: Added 2 new tests for `no_mig_entities` and `events_exist_but_no_links` cases
   - **Issue #6 FIXED**: Aligned log messages to include `events_processed` and `events_linked` consistently
   - **Issue #7 NOTED**: Line numbers in Dev Notes are approximate references
   - All 20 tests passing after fixes (13 unit tests + 7 integration tests)

### File List

**Modified:**
- [backend/app/workers/tasks/engine_tasks.py](backend/app/workers/tasks/engine_tasks.py) - Auto-trigger logic in `link_entities_for_matter` (lines ~1091-1115), `link_entities_after_extraction` (lines ~1206-1311 including no_mig_entities path), job creation in `detect_timeline_anomalies` (lines ~1349-1366)

**Created:**
- [backend/tests/workers/test_engine_tasks_anomaly_trigger.py](backend/tests/workers/test_engine_tasks_anomaly_trigger.py) - 13 unit tests for auto-trigger functionality (including 2 new edge case tests)
- [backend/tests/integration/test_timeline_pipeline_with_anomalies.py](backend/tests/integration/test_timeline_pipeline_with_anomalies.py) - 7 integration tests for full pipeline

