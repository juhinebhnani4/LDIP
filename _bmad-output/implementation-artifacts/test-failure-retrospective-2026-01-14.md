# Test Failure Retrospective: 58 Integration Test Failures + 11 Skipped Tests

**Date**: 2026-01-14
**Context**: After completing Stories 7-1, 7-2, 7-3 with BMAD workflow, code reviews, and git commits, 58 tests failed (reduced to 24 in session, then 0). Additionally, 11 tests were skipped - investigation revealed 6 could be enabled with DI refactoring.

---

## Executive Summary

The test failures were **NOT caused by broken implementations** - all story features worked correctly. The failures stemmed from:

1. **Test infrastructure drift** - Tests weren't updated when underlying infrastructure changed
2. **Mock brittleness** - Tests tightly coupled to implementation details
3. **Missing test maintenance in code reviews** - Reviews focused on new code, not existing test compatibility

---

## Failure Categories and Root Causes

### Category 1: FastAPI Dependency Injection Pattern Change (9 tests)
**Files**: `tests/integration/api/test_entity_aliases_api.py`

**What Failed**:
- Tests used `@patch("app.api.deps.require_matter_role")` to mock authentication
- All 9 tests returned 401 Unauthorized

**Root Cause**:
- At some point, the authentication pattern changed to use FastAPI's native `Depends()` system
- Tests still used the old decorator-patching approach
- **The implementation was correct; the tests were outdated**

**Fix Applied**:
```python
# OLD (broken): Patching decorators
@patch("app.api.deps.require_matter_role")
async def test_something(self, mock_role):
    ...

# NEW (working): FastAPI dependency overrides
app.dependency_overrides[get_settings] = get_test_settings
app.dependency_overrides[get_matter_service] = lambda: mock_service
```

**Prevention**:
- [ ] When changing auth patterns, grep for all tests using the old pattern
- [ ] Add integration test for auth flow itself that fails if pattern changes
- [ ] Document the testing pattern in a `TESTING.md` guide

---

### Category 2: Supabase Mock Chaining Issues (5 tests)
**Files**: `tests/integration/test_job_tracking_integration.py`

**What Failed**:
- Tests with chained `.eq().eq().execute()` calls
- `.range()` pagination calls
- Mock returned wrong data structures

**Root Cause**:
- Supabase client uses builder pattern with chained method calls
- Initial mocks only handled single `.eq()` call, not chained filters
- When implementation added matter isolation (`.eq("matter_id", x).eq("id", y)`), mocks broke

**Fix Applied**:
```python
# OLD (broken): Simple mock
table_mock.update.return_value.eq.return_value.execute.return_value.data = [...]

# NEW (working): Accumulating filter mock
def mock_update(data):
    result = MagicMock()
    result._filters = {}

    def mock_eq(field, value):
        result._filters[field] = value
        return result  # Return self for chaining

    result.eq = mock_eq
    result.execute = lambda: MagicMock(data=[...])
    return result
```

**Prevention**:
- [ ] Create a `MockSupabaseClient` helper class in `tests/conftest.py`
- [ ] Test the mock itself to ensure it handles common patterns
- [ ] When adding new query patterns to implementation, update mock helper

---

### Category 3: Mock Fixture Data Structure Mismatch (3 tests)
**Files**: `tests/integration/test_citation_extraction.py`

**What Failed**:
- `'str' object has no attribute 'get'`
- Mock returned UUID string instead of dict with `id`, `created_at`, `updated_at`

**Root Cause**:
- Implementation evolved to expect full record objects from Supabase
- Test fixtures still returned minimal data (just IDs)
- **Fixture drift** - fixtures weren't updated when model requirements changed

**Fix Applied**:
```python
# OLD (broken): Minimal return
result.execute.return_value.data = str(uuid4())

# NEW (working): Full record return
result.execute.return_value.data = [{
    "id": str(uuid4()),
    "created_at": datetime.utcnow().isoformat(),
    "updated_at": datetime.utcnow().isoformat(),
    **input_data
}]
```

**Prevention**:
- [ ] Create Pydantic models for test fixtures that match DB schema
- [ ] Use factory functions (e.g., `create_citation_record()`) instead of inline dicts
- [ ] Add schema validation to mock return values

---

### Category 4: Celery Task Testing Pattern (3 tests)
**Files**: `tests/integration/test_citation_extraction.py`

**What Failed**:
- `AttributeError: 'MagicMock' object has no attribute 'id'` for `self.request`
- Tests tried to mock Celery's internal `request` property

**Root Cause**:
- Celery tasks have a `self.request` property that's set at runtime
- Patching this is complex and fragile
- Tests should use `.run()` for synchronous testing of early-exit paths

**Fix Applied**:
```python
# OLD (broken): Trying to patch request
with patch.object(extract_citations, "request") as mock_request:
    extract_citations(prev_result=None, document_id=None)

# NEW (working): Direct run() call for early-exit tests
result = extract_citations.run(prev_result=None, document_id=None)
assert result["status"] == "citation_extraction_failed"
```

**Prevention**:
- [ ] Document Celery testing patterns in `TESTING.md`
- [ ] Use `.run()` for unit-style tests, `.apply()` for integration
- [ ] Never mock Celery internals like `request`, `retry`, etc.

---

### Category 5: Import Path Mismatches (4 tests)
**Files**: `tests/integration/test_search_integration.py`

**What Failed**:
- `get_cohere_rerank_service` not found in `app.services.rag.hybrid_search`
- Patches pointed to wrong module

**Root Cause**:
- Function was imported inside another function (lazy import)
- Patch path `app.services.rag.hybrid_search.get_cohere_rerank_service` didn't exist
- Must patch at source: `app.services.rag.reranker.get_cohere_rerank_service`

**Fix Applied**:
```python
# OLD (broken): Patching at import location
@patch("app.services.rag.hybrid_search.get_cohere_rerank_service")

# NEW (working): Patching at source module
@patch("app.services.rag.reranker.get_cohere_rerank_service")
```

**Prevention**:
- [ ] Always patch at the source module, not where it's imported
- [ ] Use `patch.object(module, "function")` when possible for clarity
- [ ] Add a linting rule or pre-commit hook to detect common patch path errors

---

### Category 6: Python Property Patching Limitation (1 test)
**Files**: `tests/integration/test_mig_integration.py`

**What Failed**:
- `AttributeError: property 'model' of 'CitationExtractor' object has no setter`

**Root Cause**:
- Python properties can't be patched with `patch.object(obj, "property")`
- Properties are descriptors on the class, not instance attributes

**Fix Applied**:
```python
# OLD (broken): Patching property
with patch.object(extractor, "model") as mock_model:
    ...

# NEW (working): Setting private attribute
mock_model = MagicMock()
extractor._model = mock_model  # Bypass property
```

**Prevention**:
- [ ] Avoid properties for things that need testing; use methods or direct attributes
- [ ] If using properties, expose a `_set_model_for_testing()` method
- [ ] Document this Python limitation in `TESTING.md`

---

### Category 7: Implementation Changed Without Test Update (3 tests)
**Files**: `tests/integration/test_ocr_integration.py`

**What Failed**:
- Tests expected `process_document.apply_async(args=["doc-id"], queue="high")`
- Implementation changed to use Celery `chain()` pattern

**Root Cause**:
- `_queue_ocr_task` was refactored from single task to task chain
- Tests weren't updated to reflect the new architecture
- **This is a code review gap** - reviewer should have flagged test incompatibility

**Fix Applied**:
```python
# OLD (broken): Testing single task
with patch.object(process_document, "apply_async") as mock_apply:
    _queue_ocr_task("doc-small", 5 * 1024 * 1024)
    assert mock_apply.call_args.kwargs["args"] == ["doc-small"]

# NEW (working): Testing chain pattern
with patch("celery.chain") as mock_chain:
    mock_task_chain = MagicMock()
    mock_chain.return_value = mock_task_chain
    _queue_ocr_task("doc-small", 5 * 1024 * 1024)
    mock_task_chain.apply_async.assert_called_once_with(queue="high")
```

**Prevention**:
- [ ] Code review checklist item: "Are existing tests still valid?"
- [ ] Run full test suite before merging (not just new tests)
- [ ] Add test coverage check to CI that fails if coverage decreases

---

### Category 8: httpx AsyncClient API Limitation (2 tests)
**Files**: `tests/integration/api/test_entity_aliases_api.py`

**What Failed**:
- `TypeError: AsyncClient.delete() got unexpected keyword argument 'json'`

**Root Cause**:
- httpx's `delete()` method doesn't accept `json` parameter
- Must use `request("DELETE", url, json=...)` for DELETE with body

**Fix Applied**:
```python
# OLD (broken): Using delete() with json
response = await client.delete(url, json={"alias": "test"})

# NEW (working): Using request() method
response = await client.request("DELETE", url, json={"alias": "test"})
```

**Prevention**:
- [ ] Document httpx quirks in `TESTING.md`
- [ ] Create helper function `async_delete_with_body(client, url, json)`
- [ ] Consider switching to `aiohttp` which has consistent API

---

## Summary Table

| Category | Tests | Root Cause | Prevention |
|----------|-------|------------|------------|
| FastAPI DI Pattern | 9 | Auth pattern changed, tests not updated | Document pattern, grep on change |
| Supabase Mock Chaining | 5 | Builder pattern not fully mocked | Create `MockSupabaseClient` helper |
| Mock Data Structure | 3 | Fixtures didn't match evolved schema | Use factory functions |
| Celery Testing | 3 | Patching internals instead of using `.run()` | Document Celery patterns |
| Import Path Mismatch | 4 | Patched wrong module (import vs source) | Always patch at source |
| Property Patching | 1 | Python limitation with descriptors | Avoid properties or use workaround |
| Implementation Drift | 3 | Refactored impl without updating tests | Code review checklist |
| httpx API | 2 | delete() doesn't accept json | Document, use helper |
| **Total** | **30** | (24 unique, some overlap) | |

---

## Process Improvements

### 1. Pre-Merge Test Validation
**Current**: Code review checks new code only
**Improved**: CI must run full test suite; code review verifies test compatibility

### 2. Test Infrastructure Documentation
Create `docs/TESTING.md` with:
- FastAPI dependency override pattern
- Supabase mock helper usage
- Celery task testing patterns
- httpx quirks
- Patch path rules

### 3. Mock Helper Library
Create `tests/helpers/` with:
- `mock_supabase.py` - Full Supabase client mock with chaining
- `mock_auth.py` - Auth dependency overrides
- `factories.py` - Test data factories

### 4. Code Review Checklist Addition
Add to BMAD code review workflow:
- [ ] Do existing tests still pass with this change?
- [ ] If implementation pattern changed, are related tests updated?
- [ ] Are mocks at the correct patch path (source, not import)?

### 5. CI Pipeline Enhancement
- Run `pytest tests/` (all tests, not just new)
- Fail on coverage decrease
- Fail on test duration increase > 20%

---

## Why BMAD/Code Review Didn't Catch This

1. **Focus on New Code**: Reviews checked new implementation, not existing test compatibility
2. **Tests Ran in Isolation**: Each story's tests passed individually; cross-story integration wasn't validated
3. **No "Test the Tests" Culture**: Mocks weren't validated against real Supabase behavior
4. **Missing CI Gate**: No requirement to run full test suite before merge

---

## Action Items

- [x] Create `docs/TESTING.md` with patterns documented above *(Completed 2026-01-14)*
- [ ] Create `tests/helpers/mock_supabase.py` with proper chaining support *(Deferred - patterns documented in TESTING.md)*
- [x] Add code review checklist item for test compatibility *(Completed 2026-01-14)*
- [ ] Configure CI to run full test suite on every PR *(Requires CI infrastructure setup)*
- [ ] Add pre-commit hook to detect common patch path errors *(Nice-to-have)*
- [ ] Schedule monthly "test health" review to catch fixture drift *(Process improvement)*

---

## Completed Prevention Actions

### 1. Created `backend/docs/TESTING.md` (2026-01-14)

Comprehensive testing guide covering all 8 failure categories:
- FastAPI dependency override pattern (with code examples)
- Supabase mock with proper chaining support
- Celery task testing (`.run()` vs patching internals)
- Patch path rules (source vs import location)
- httpx quirks (DELETE with body workaround)
- Python property mocking workarounds
- Test data factory patterns
- Quick reference table for all patterns

### 2. Updated BMAD Code Review Checklist (2026-01-14)

Added **"Test Compatibility Review (CRITICAL)"** section to:
`_bmad/bmm/workflows/4-implementation/code-review/checklist.md`

New checklist items:
- [ ] Full test suite run (`pytest tests/` not just new tests)
- [ ] Pattern changes verified (existing tests updated if impl changed)
- [ ] Mock paths correct (patches at SOURCE module)
- [ ] FastAPI auth pattern (`dependency_overrides` not `@patch`)
- [ ] Supabase mocks (handle chained `.eq()` calls)
- [ ] Celery tasks (using `.run()` for unit tests)
- [ ] Test fixtures (return full objects with timestamps)
- [ ] Skipped tests reviewed (using DI injection where available)

---

## Skipped Tests Analysis (Category 9)

### What Was Skipped
**File**: `tests/integration/test_ocr_validation_integration.py`
**Original Count**: 11 skipped tests across 4 test classes

### Root Cause Analysis

The tests were marked with `@pytest.mark.skip(reason="Integration tests require proper database mocking")`. Investigation revealed:

1. **Tests used wrong mocking approach** - Patching non-existent module-level functions like `app.services.document_service.get_service_client`
2. **Task supports dependency injection** - The `validate_ocr` task has built-in DI parameters for all services
3. **Outdated skip reasons** - The skip message claimed "requires proper database mocking" but DI was already available

### Tests Enabled (6 tests)

#### TestValidationPipelineIntegration (3 tests)
**Fix**: Refactored to use `validate_ocr` task's DI parameters instead of patching

```python
# OLD (broken): Patching non-existent functions
@patch("app.services.document_service.get_service_client")
@patch("app.services.ocr.validation_extractor.get_validation_extractor")
def test_something(self, mock_get_extractor, mock_get_client):
    ...

# NEW (working): Using task's built-in DI
def test_something(
    self,
    mock_validation_extractor: MagicMock,
    mock_document_service: MagicMock,
    mock_bounding_box_service: MagicMock,
) -> None:
    result = validate_ocr.run(
        prev_result=prev_result,
        validation_extractor=mock_validation_extractor,
        document_service=mock_document_service,
        bounding_box_service=mock_bounding_box_service,
    )
```

#### TestValidationErrorHandling (3 tests)
**Fix**: Same DI approach - test error handling for extraction failures, Gemini failures, and missing input fields

### Tests Remaining Skipped (5 tests)

#### TestValidationTaskChaining (2 tests)
**Reason**: `process_document` task doesn't support DI, requires complex patching
**Skip justification**: Chaining logic already covered by enabled pipeline tests

#### TestValidationDatabaseUpdates (3 tests)
**Reason**: Test internal database update implementation details
**Skip justification**: Covered by service-level unit tests in `tests/services/ocr/`

### Prevention: New Code Review Checklist Item

Added to `_bmad/bmm/workflows/4-implementation/code-review/checklist.md`:

```markdown
- [ ] **Skipped tests reviewed** - If tests are skipped, verify:
  - Can they be enabled using dependency injection?
  - Is the skip reason still valid?
  - Are they providing unique coverage or duplicating other tests?
```

### Results

| Status | Before | After | Change |
|--------|--------|-------|--------|
| Passed | 98 | 104 | +6 |
| Skipped | 11 | 5 | -6 |

### Key Lesson: Prefer DI Over Patching

When Celery tasks or FastAPI routes support dependency injection parameters, **always use DI** instead of patching:

| Approach | Pros | Cons |
|----------|------|------|
| **Dependency Injection** | Clean, explicit, type-safe, works with `spec=` | Requires task/route to support it |
| **Patching Factory Functions** | Works without code changes | Brittle, path-sensitive, breaks easily |
| **Patching Module Attributes** | Sometimes necessary | Often targets wrong module, requires understanding import chains |

**Rule**: Before skipping a test due to "mocking complexity", check if the code under test supports dependency injection.
