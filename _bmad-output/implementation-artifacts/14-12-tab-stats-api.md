# Story 14.12: Tab Stats API

Status: completed

## Story

As an **attorney**,
I want **the workspace tab bar to display real counts and processing status from the backend**,
so that **I can see accurate numbers of items in each tab (timeline events, entities, citations, etc.) and know when processing is still in progress**.

## Acceptance Criteria

1. **Tab Stats API Endpoint Created**
   - GET /api/matters/{matter_id}/tab-stats returns aggregated counts for all tabs
   - Response includes count and issueCount for each tab (summary, timeline, entities, citations, contradictions, verification, documents)
   - Response includes processing status for each tab ('ready' | 'processing')
   - Requires authentication and matter access (any role: OWNER, EDITOR, VIEWER)

2. **Tab Counts Are Accurate**
   - timeline: Count of events from events table for this matter
   - entities: Count of identity_nodes for this matter, issueCount = count with unresolved aliases
   - citations: Count of citations for this matter, issueCount = count where verification_status NOT IN ('verified')
   - contradictions: Count from contradictions for this matter, issueCount = same (all contradictions need attention)
   - verification: Count of finding_verifications pending, issueCount = count where decision = 'flagged' OR confidence < 70
   - documents: Count of documents for this matter
   - summary: count = 1, issueCount = 0 (static for now)

3. **Processing Status Is Derived**
   - Check background_jobs table for any active jobs for this matter
   - If job_type matches tab (e.g., 'entity_extraction' -> entities tab), mark that tab as 'processing'
   - If no active jobs, all tabs are 'ready'

4. **Frontend workspaceStore Wired to Real API**
   - Update `fetchTabStats` in workspaceStore.ts to call GET /api/matters/{matterId}/tab-stats
   - Remove mock data and simulated delay
   - Handle errors gracefully (show tabs without counts on failure)

5. **API Response Matches Frontend Types**
   - Response uses camelCase aliases matching frontend TabStats interface
   - Response format: `{ data: { tabCounts: {...}, tabProcessingStatus: {...} } }`

6. **Tests Added**
   - Backend: pytest tests for /api/matters/{matter_id}/tab-stats endpoint
   - Frontend: Update workspaceStore.test.ts to mock API calls instead of mock data

## Tasks / Subtasks

- [x] Task 1: Create Tab Stats Pydantic models (AC: #5)
  - [x] 1.1: Create `backend/app/models/tab_stats.py`
  - [x] 1.2: Define `TabStats` model with count: int, issueCount: int (with camelCase alias)
  - [x] 1.3: Define `TabProcessingStatus` as Literal['ready', 'processing']
  - [x] 1.4: Define `TabStatsData` with tabCounts and tabProcessingStatus
  - [x] 1.5: Define `TabStatsResponse` with data: TabStatsData

- [x] Task 2: Create Tab Stats service (AC: #2, #3)
  - [x] 2.1: Create `backend/app/services/tab_stats_service.py`
  - [x] 2.2: Implement `get_tab_stats(matter_id: str) -> TabStatsData`
  - [x] 2.3: Query events table for timeline count
  - [x] 2.4: Query identity_nodes table for entities count
  - [x] 2.5: Query citations table with status breakdown
  - [x] 2.6: Query contradictions for count
  - [x] 2.7: Query finding_verifications for verification tab stats
  - [x] 2.8: Query documents table for document count
  - [x] 2.9: Query processing_jobs for processing status by job_type
  - [x] 2.10: Map job_type to tab

- [x] Task 3: Create Tab Stats API endpoint (AC: #1, #5)
  - [x] 3.1: Add endpoint to `backend/app/api/routes/matters.py`
  - [x] 3.2: Implement `GET /api/matters/{matter_id}/tab-stats`
  - [x] 3.3: Use `require_matter_role` for auth
  - [x] 3.4: Inject TabStatsService via Depends
  - [x] 3.5: Return TabStatsResponse

- [x] Task 4: Wire frontend to real API (AC: #4)
  - [x] 4.1: Create `frontend/src/lib/api/tabStats.ts`
  - [x] 4.2: Update `workspaceStore.ts` fetchTabStats to call API
  - [x] 4.3: Remove mock data implementation
  - [x] 4.4: Add error handling

- [x] Task 5: Write backend tests (AC: #6)
  - [x] 5.1: Create `backend/tests/api/test_tab_stats.py`
  - [x] 5.2: Test endpoint returns correct counts
  - [x] 5.3: Test processing status detection
  - [x] 5.4: Test unauthorized access returns 401
  - [x] 5.5: Test non-member access returns 404

- [x] Task 6: Update frontend tests (AC: #6)
  - [x] 6.1: Update `workspaceStore.test.ts` to mock API call
  - [x] 6.2: Test successful API response populates store
  - [x] 6.3: Test API error is handled gracefully

## Dev Notes

### Critical Architecture Patterns

**API Response Format (MANDATORY from project-context.md):**
```python
{
    "data": {
        "tabCounts": {
            "summary": { "count": 1, "issueCount": 0 },
            "timeline": { "count": 24, "issueCount": 0 },
            "entities": { "count": 18, "issueCount": 2 },
            "citations": { "count": 45, "issueCount": 3 },
            "contradictions": { "count": 7, "issueCount": 7 },
            "verification": { "count": 12, "issueCount": 5 },
            "documents": { "count": 8, "issueCount": 0 }
        },
        "tabProcessingStatus": {
            "summary": "ready",
            "timeline": "ready",
            "entities": "ready",
            "citations": "ready",
            "contradictions": "ready",
            "verification": "ready",
            "documents": "ready"
        }
    }
}
```

**Matter Isolation (4-Layer Security - MANDATORY):**
- All queries MUST filter by matter_id
- Use require_matter_role dependency for auth check
- RLS policies already enforce at database level

**Zustand Selector Pattern (MANDATORY):**
```typescript
// CORRECT
const tabCounts = useWorkspaceStore((state) => state.tabCounts);

// WRONG
const { tabCounts } = useWorkspaceStore();
```

### Existing Tables for Counts

| Tab | Table | Count Query | IssueCount Logic |
|-----|-------|-------------|------------------|
| timeline | events | COUNT(*) WHERE matter_id = ? | 0 |
| entities | identity_nodes | COUNT(*) WHERE matter_id = ? | COUNT(*) WHERE has_unresolved_alias |
| citations | citations | COUNT(*) WHERE matter_id = ? | COUNT(*) WHERE verification_status != 'verified' |
| contradictions | contradictions | COUNT(*) WHERE matter_id = ? | Same as count |
| verification | finding_verifications | COUNT(*) WHERE matter_id = ? AND decision IS NULL | COUNT(*) WHERE decision = 'flagged' |
| documents | documents | COUNT(*) WHERE matter_id = ? | 0 |
| summary | N/A | 1 (hardcoded) | 0 |

### Processing Status Mapping

```python
JOB_TYPE_TO_TAB = {
    "entity_extraction": "entities",
    "date_extraction": "timeline",
    "citation_extraction": "citations",
    "contradiction_detection": "contradictions",
    "ocr_processing": "documents",
    "summary_generation": "summary",
}
```

**Query for active jobs:**
```sql
SELECT job_type FROM background_jobs
WHERE matter_id = :matter_id
AND status IN ('pending', 'running', 'queued')
```

### Service Layer Pattern

**Reference:** [dashboard_stats_service.py](backend/app/services/dashboard_stats_service.py)

```python
# backend/app/services/tab_stats_service.py
import structlog
from app.core.supabase import get_supabase_client

logger = structlog.get_logger(__name__)

class TabStatsService:
    def __init__(self, supabase=None):
        self.supabase = supabase or get_supabase_client()

    def get_tab_stats(self, matter_id: str) -> TabStatsData:
        """Get aggregated tab statistics for a matter."""
        # Query each table and aggregate counts
        ...
```

### API Endpoint Pattern

**Add to backend/app/api/routes/matters.py:**

```python
@router.get("/{matter_id}/tab-stats", response_model=TabStatsResponse)
async def get_tab_stats(
    matter_id: str,
    membership: MatterMembership = Depends(
        require_matter_role([MatterRole.OWNER, MatterRole.EDITOR, MatterRole.VIEWER])
    ),
    tab_stats_service: TabStatsService = Depends(get_tab_stats_service),
) -> TabStatsResponse:
    """Get tab statistics for workspace tab bar."""
    data = tab_stats_service.get_tab_stats(matter_id)
    return TabStatsResponse(data=data)
```

### Frontend API Call

```typescript
// frontend/src/lib/api/tabStats.ts
export async function fetchTabStats(matterId: string): Promise<TabStatsResponse> {
  const response = await fetch(`${API_BASE_URL}/matters/${matterId}/tab-stats`, {
    headers: {
      'Authorization': `Bearer ${getAccessToken()}`,
      'Content-Type': 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch tab stats: ${response.statusText}`);
  }
  return response.json();
}
```

### workspaceStore Update

**Location:** [workspaceStore.ts:124-170](frontend/src/stores/workspaceStore.ts#L124)

Replace mock implementation with:
```typescript
fetchTabStats: async (matterId: string) => {
  // ... existing guard logic ...
  set({ isLoadingTabStats: true, tabStatsError: null, currentMatterId: matterId });

  try {
    const response = await fetchTabStats(matterId);
    set({
      tabCounts: response.data.tabCounts,
      tabProcessingStatus: response.data.tabProcessingStatus,
      isLoadingTabStats: false,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to fetch tab stats';
    console.error('Tab stats fetch failed:', message);
    set({ tabStatsError: message, isLoadingTabStats: false });
  }
},
```

### File Structure

**New Files:**
- backend/app/models/tab_stats.py
- backend/app/services/tab_stats_service.py
- backend/tests/api/test_tab_stats.py
- frontend/src/lib/api/tabStats.ts

**Modified Files:**
- backend/app/api/routes/matters.py (add endpoint)
- backend/app/api/deps.py (add get_tab_stats_service)
- frontend/src/stores/workspaceStore.ts (wire to API)
- frontend/src/stores/workspaceStore.test.ts (mock API)

### References

- [Source: Story 10A.2 - workspaceStore TODO](10a-2-tab-bar-navigation.md#workspace-store-pattern)
- [Source: sprint-status.yaml line 238](sprint-status.yaml)
- [Source: project-context.md - API patterns](project-context.md)
- [Source: Story 14-11 - API wiring patterns](14-11-global-search-rag.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Backend: Table is `processing_jobs` not `background_jobs` as originally documented
- Backend: Service uses parallel async queries for efficiency
- Frontend: Added dedicated tabStats.ts API module with transform function
- Tests: Both backend (pytest) and frontend (vitest) tests added

### File List

**New Files:**
- backend/app/models/tab_stats.py
- backend/app/services/tab_stats_service.py
- backend/tests/api/test_tab_stats.py
- frontend/src/lib/api/tabStats.ts
- frontend/src/lib/api/tabStats.test.ts

**Modified Files:**
- backend/app/api/deps.py (added get_tab_stats_service_dep, TabStatsService import)
- backend/app/api/routes/matters.py (added GET /{matter_id}/tab-stats endpoint)
- frontend/src/stores/workspaceStore.ts (wired to real API)
- frontend/src/stores/workspaceStore.test.ts (mocked API calls)

