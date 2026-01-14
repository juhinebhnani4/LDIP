# LDIP Backend Testing Guide

> **CRITICAL**: Read this before writing ANY tests. Following these patterns prevents test failures that are hard to debug.

---

## Table of Contents

1. [FastAPI Testing Pattern](#1-fastapi-testing-pattern)
2. [Supabase Mock Pattern](#2-supabase-mock-pattern)
3. [Celery Task Testing](#3-celery-task-testing)
4. [Patch Path Rules](#4-patch-path-rules)
5. [httpx Quirks](#5-httpx-quirks)
6. [Python Property Mocking](#6-python-property-mocking)
7. [Test Data Factories](#7-test-data-factories)
8. [Code Review Checklist](#8-code-review-checklist)
9. [Celery Task Dependency Injection](#9-celery-task-dependency-injection)

---

## 1. FastAPI Testing Pattern

### DO: Use `app.dependency_overrides`

```python
from app.main import app
from app.core.config import get_settings, Settings
from app.services.matter_service import get_matter_service

def get_test_settings() -> Settings:
    """Create test settings with known JWT secret."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = "test-secret-key-for-testing-only"
    settings.environment = "test"
    return settings

def create_test_token(user_id: str = "test-user") -> str:
    """Create valid JWT for testing."""
    payload = {
        "sub": user_id,
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, "test-secret-key-for-testing-only", algorithm="HS256")

@pytest.mark.anyio
async def test_endpoint():
    # Override dependencies
    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_matter_service] = lambda: mock_service

    try:
        token = create_test_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/endpoint",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()  # ALWAYS clean up!
```

### DON'T: Patch decorators

```python
# BROKEN - This won't work!
@patch("app.api.deps.require_matter_role")
async def test_something(self, mock_role):
    ...
```

**Why?** FastAPI's `Depends()` system uses dependency injection, not decorators. Patching the decorator function doesn't affect already-registered routes.

---

## 2. Supabase Mock Pattern

### DO: Handle Method Chaining

Supabase uses a builder pattern: `.select().eq().eq().execute()`. Your mocks must support chaining.

```python
def create_mock_supabase_client():
    """Create a mock Supabase client that handles chained calls."""
    client = MagicMock()
    storage = {}  # Track "database" state

    def create_table_mock(table_name: str):
        table = MagicMock()

        def mock_select(*args):
            query = MagicMock()
            query._filters = {}

            def mock_eq(field, value):
                query._filters[field] = value
                return query  # Return self for chaining!

            def mock_range(start, end):
                query._range = (start, end)
                return query

            def mock_execute():
                # Filter storage based on accumulated filters
                results = [
                    row for row in storage.get(table_name, [])
                    if all(row.get(k) == v for k, v in query._filters.items())
                ]
                return MagicMock(data=results)

            query.eq = mock_eq
            query.range = mock_range
            query.execute = mock_execute
            return query

        def mock_insert(data):
            result = MagicMock()
            if isinstance(data, list):
                for d in data:
                    d["id"] = str(uuid4())
                    d["created_at"] = datetime.utcnow().isoformat()
                    d["updated_at"] = datetime.utcnow().isoformat()
                storage.setdefault(table_name, []).extend(data)
                result.execute.return_value.data = data
            else:
                data["id"] = str(uuid4())
                data["created_at"] = datetime.utcnow().isoformat()
                data["updated_at"] = datetime.utcnow().isoformat()
                storage.setdefault(table_name, []).append(data)
                result.execute.return_value.data = [data]
            return result

        def mock_update(data):
            result = MagicMock()
            result._filters = {}

            def mock_eq(field, value):
                result._filters[field] = value
                return result

            def mock_execute():
                # Update matching rows
                for row in storage.get(table_name, []):
                    if all(row.get(k) == v for k, v in result._filters.items()):
                        row.update(data)
                        row["updated_at"] = datetime.utcnow().isoformat()
                        return MagicMock(data=[row])
                return MagicMock(data=[])

            result.eq = mock_eq
            result.execute = mock_execute
            return result

        table.select = mock_select
        table.insert = mock_insert
        table.update = mock_update
        return table

    client.table = create_table_mock
    client._storage = storage  # Expose for assertions
    return client
```

### DON'T: Use Simple Return Values

```python
# BROKEN - Doesn't handle chained .eq() calls
mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [...]
```

**Why?** When implementation adds `.eq("matter_id", x).eq("id", y)`, the second `.eq()` call returns the wrong thing.

---

## 3. Celery Task Testing

### DO: Use `.run()` for Synchronous Tests

```python
def test_task_handles_missing_document():
    """Test early-exit behavior without needing Celery context."""
    from app.workers.tasks.document_tasks import extract_citations

    # .run() executes synchronously without Celery overhead
    result = extract_citations.run(prev_result=None, document_id=None)

    assert result["status"] == "citation_extraction_failed"
    assert result["error_code"] == "NO_DOCUMENT_ID"
```

### DO: Use `.apply()` for Integration Tests with Context

```python
def test_task_with_celery_context():
    """Test that needs Celery's request context."""
    result = my_task.apply(args=["arg1", "arg2"])
    assert result.get() == expected_value
```

### DON'T: Mock Celery Internals

```python
# BROKEN - self.request is set by Celery at runtime
with patch.object(extract_citations, "request") as mock_request:
    mock_request.id = "fake-task-id"
    extract_citations(...)
```

**Why?** Celery's `request` is a special property that's populated when the task runs in a worker. Mocking it is fragile and breaks easily.

---

## 4. Patch Path Rules

### RULE: Always Patch at the SOURCE Module

```python
# Implementation in app/services/rag/hybrid_search.py:
from app.services.rag.reranker import get_cohere_rerank_service

def search(...):
    reranker = get_cohere_rerank_service()  # Lazy import inside function
    ...
```

```python
# CORRECT: Patch at source
@patch("app.services.rag.reranker.get_cohere_rerank_service")
def test_search(...):
    ...

# BROKEN: Patch at import location (doesn't exist!)
@patch("app.services.rag.hybrid_search.get_cohere_rerank_service")
def test_search(...):
    ...  # AttributeError: module has no attribute 'get_cohere_rerank_service'
```

### When to Use `patch.object`

Use `patch.object` when you have access to the actual module object:

```python
from app.services.rag import reranker

@patch.object(reranker, "get_cohere_rerank_service")
def test_search(mock_get_service):
    ...
```

---

## 5. httpx Quirks

### DELETE with Body

httpx's `delete()` method doesn't accept a `json` parameter. Use `request()` instead:

```python
# BROKEN
response = await client.delete(url, json={"alias": "test"})

# CORRECT
response = await client.request("DELETE", url, json={"alias": "test"})
```

### Helper Function

```python
async def delete_with_body(client: AsyncClient, url: str, json: dict, **kwargs):
    """DELETE request with JSON body (httpx workaround)."""
    return await client.request("DELETE", url, json=json, **kwargs)
```

---

## 6. Python Property Mocking

### The Problem

Python properties are descriptors on the class, not instance attributes. You can't patch them directly:

```python
class MyClass:
    @property
    def model(self):
        return self._model

# BROKEN - properties can't be patched like this
with patch.object(instance, "model") as mock:
    ...  # AttributeError: property 'model' has no setter
```

### The Solution

Set the private attribute directly:

```python
# CORRECT
instance._model = MagicMock()
instance._model.generate.return_value = "mocked result"

# Or use PropertyMock on the class
with patch.object(MyClass, "model", new_callable=PropertyMock) as mock:
    mock.return_value = "mocked value"
    ...
```

---

## 7. Test Data Factories

### DO: Use Factory Functions

```python
# tests/factories.py

def create_document_record(
    document_id: str = None,
    matter_id: str = None,
    status: str = "pending",
    **overrides
) -> dict:
    """Create a document record matching the database schema."""
    return {
        "id": document_id or str(uuid4()),
        "matter_id": matter_id or str(uuid4()),
        "filename": "test.pdf",
        "status": status,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        **overrides
    }

def create_citation_record(
    citation_id: str = None,
    matter_id: str = None,
    **overrides
) -> dict:
    """Create a citation record matching the database schema."""
    return {
        "id": citation_id or str(uuid4()),
        "matter_id": matter_id or str(uuid4()),
        "act_name": "Test Act",
        "section": "123",
        "confidence": 0.95,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        **overrides
    }
```

### DON'T: Use Inline Dicts

```python
# BROKEN - Missing required fields, will break when schema evolves
mock.return_value.data = [{"id": "123"}]
```

---

## 8. Code Review Checklist

Before approving ANY PR, verify:

### Test Compatibility

- [ ] Did you run the FULL test suite (`pytest tests/`)? Not just new tests!
- [ ] If you changed an implementation pattern, did you grep for tests using the old pattern?
- [ ] Are all mocks at the correct patch path (source module, not import location)?

### Mock Quality

- [ ] Do Supabase mocks handle chained `.eq()` calls?
- [ ] Do mock return values include all required fields (`id`, `created_at`, `updated_at`)?
- [ ] Are you using `.run()` for Celery task unit tests?

### Pattern Changes

- [ ] If auth pattern changed, are ALL tests using the new `dependency_overrides` pattern?
- [ ] If task architecture changed (e.g., single task → chain), are tests updated?
- [ ] If model schema changed, are test fixtures updated?

---

## 9. Celery Task Dependency Injection

### DO: Use Task DI Parameters When Available

Many Celery tasks in this codebase support dependency injection via optional parameters. **Always prefer this over patching**.

```python
# Check if task supports DI (look for optional service parameters)
def validate_ocr(
    self,
    prev_result: dict | None = None,
    document_id: str | None = None,
    validation_extractor: ValidationExtractor | None = None,  # DI!
    gemini_validator: GeminiOCRValidator | None = None,       # DI!
    document_service: DocumentService | None = None,          # DI!
) -> dict:
    ...

# CORRECT: Use DI parameters
def test_validation_with_di(mock_extractor, mock_document_service):
    result = validate_ocr.run(
        prev_result={"status": "ocr_complete", "document_id": "doc-123"},
        validation_extractor=mock_extractor,
        document_service=mock_document_service,
    )
    assert result["status"] == "validated"

# WRONG: Patch factory functions (brittle, path-sensitive)
@patch("app.workers.tasks.document_tasks.get_validation_extractor")
@patch("app.workers.tasks.document_tasks.get_document_service")
def test_validation_with_patching(mock_get_doc, mock_get_ext):
    ...
```

### Benefits of DI Over Patching

| DI Approach | Patching Approach |
|-------------|-------------------|
| Clean, explicit mock passing | Hidden mock setup in decorators |
| Works with `spec=ClassName` | Spec often ignored or wrong |
| IDE autocomplete works | No type hints |
| Fails fast if parameter wrong | Silently uses wrong path |
| Easy to understand | Requires import chain knowledge |

---

## Quick Reference

| Situation | DO | DON'T |
|-----------|-----|-------|
| FastAPI auth | `app.dependency_overrides[get_settings] = ...` | `@patch("app.api.deps.require_role")` |
| Supabase chaining | Return `self` from `mock_eq()` | `table.select.return_value.eq.return_value...` |
| Celery testing | `task.run()` or `task.apply()` | `patch.object(task, "request")` |
| **Celery with DI** | `task.run(service=mock_service)` | `@patch("module.get_service")` |
| Patch location | `@patch("source.module.function")` | `@patch("import.location.function")` |
| DELETE with body | `client.request("DELETE", url, json=...)` | `client.delete(url, json=...)` |
| Property mocking | `obj._private_attr = mock` | `patch.object(obj, "property")` |
| Test data | `create_document_record(...)` | `{"id": "123"}` inline dict |
