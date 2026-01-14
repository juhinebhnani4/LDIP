# Senior Developer Review - Validation Checklist

## Story Context
- [ ] Story file loaded from `{{story_path}}`
- [ ] Story Status verified as reviewable (review)
- [ ] Epic and Story IDs resolved ({{epic_num}}.{{story_num}})
- [ ] Story Context located or warning recorded
- [ ] Epic Tech Spec located or warning recorded
- [ ] Architecture/standards docs loaded (as available)
- [ ] Tech stack detected and documented
- [ ] MCP doc search performed (or web fallback) and references captured

## Implementation Review
- [ ] Acceptance Criteria cross-checked against implementation
- [ ] File List reviewed and validated for completeness
- [ ] Code quality review performed on changed files
- [ ] Security review performed on changed files and dependencies

## Test Compatibility Review (CRITICAL)
> Reference: `backend/docs/TESTING.md` for patterns
- [ ] **Full test suite run** - Did `pytest tests/` pass (not just new tests)?
- [ ] **Skipped tests count** - Did skipped tests increase? If so, why?
- [ ] **Pattern changes verified** - If implementation pattern changed, were existing tests updated?
- [ ] **Mock paths correct** - Are patches at SOURCE module, not import location?
- [ ] **FastAPI auth pattern** - Tests using `app.dependency_overrides`, NOT `@patch` decorators?
- [ ] **Supabase mocks** - Handle chained `.eq()` calls properly?
- [ ] **Celery tasks** - Using `.run()` for unit tests, not patching internals?
- [ ] **Prefer DI over patching** - If task/route supports DI, use it instead of patching factory functions?
- [ ] **Test fixtures** - Return full objects with `id`, `created_at`, `updated_at`?

## Test Coverage
- [ ] Tests identified and mapped to ACs; gaps noted
- [ ] New implementation has corresponding tests
- [ ] Test coverage did not decrease

## Final Steps
- [ ] Outcome decided (Approve/Changes Requested/Blocked)
- [ ] Review notes appended under "Senior Developer Review (AI)"
- [ ] Change Log updated with review entry
- [ ] Status updated according to settings (if enabled)
- [ ] Sprint status synced (if sprint tracking enabled)
- [ ] Story saved successfully

_Reviewer: {{user_name}} on {{date}}_
