# Story gap-5.3: Implement Cross-Engine Correlation Links

Status: ready-for-dev

## Story

As an **associate attorney**,
I want **timeline events linked to related contradictions and entities**,
So that **I can see the full context of each event and understand relationships across engine outputs**.

## Acceptance Criteria

1. **Given** a timeline event involves "John Smith" on "Jan 15, 2024"
   **When** I view the event detail panel
   **Then** I see links to all contradictions involving John Smith
   **And** I see the entity's journey (all timeline events for that entity)
   **And** clicking a link navigates to the related finding

2. **Given** a timeline event is displayed in any timeline view (list, horizontal, multi-track)
   **When** the event has associated contradictions
   **Then** a contradiction indicator badge shows on the event card
   **And** the badge shows the count and highest severity level

3. **Given** I'm viewing an entity's detail panel
   **When** the entity has timeline events and contradictions
   **Then** I see a "Journey" section showing chronological events involving this entity
   **And** I see a "Contradictions" section showing all contradictions about this entity

4. **Given** I click a cross-engine link (e.g., contradiction link from timeline)
   **When** the link is clicked
   **Then** I navigate to the appropriate tab (Contradictions/Entities/Timeline)
   **And** the linked item is highlighted/scrolled into view
   **And** a breadcrumb shows where I came from

5. **Given** I'm viewing a contradiction detail
   **When** the contradiction involves dates mentioned in timeline events
   **Then** I see links to related timeline events where those dates appear
   **And** clicking navigates to the timeline tab with event highlighted

## Tasks / Subtasks

- [ ] Task 1: Backend - Create Cross-Engine Link Resolution Service (AC: #1, #2, #5)
  - [ ] 1.1: Create `backend/app/services/cross_engine_service.py` for link resolution
  - [ ] 1.2: Implement `get_entity_journey(matter_id, entity_id)` - returns all timeline events for entity
  - [ ] 1.3: Implement `get_entity_contradictions(matter_id, entity_id)` - returns all contradictions for entity
  - [ ] 1.4: Implement `get_timeline_event_context(matter_id, event_id)` - returns related contradictions and entities
  - [ ] 1.5: Implement `get_contradiction_context(matter_id, contradiction_id)` - returns related timeline events
  - [ ] 1.6: Add efficient queries using existing indexes on `entities_involved` and `entity_id`
  - [ ] 1.7: Add unit tests in `tests/services/test_cross_engine_service.py`

- [ ] Task 2: Backend - API Endpoints for Cross-Engine Data (AC: #1, #3, #5)
  - [ ] 2.1: Add `GET /api/matters/{matter_id}/entities/{entity_id}/journey` endpoint
  - [ ] 2.2: Add `GET /api/matters/{matter_id}/timeline/events/{event_id}/context` endpoint
  - [ ] 2.3: Add `GET /api/matters/{matter_id}/contradictions/{contradiction_id}/context` endpoint
  - [ ] 2.4: Create Pydantic response models: `EntityJourneyResponse`, `EventContextResponse`, `ContradictionContextResponse`
  - [ ] 2.5: Add API tests in `tests/api/routes/test_cross_engine.py`

- [ ] Task 3: Backend - Extend Existing Endpoints with Cross-Links (AC: #1, #2)
  - [ ] 3.1: Extend `GET /api/matters/{matter_id}/timeline/events` to include `hasContradiction` flag
  - [ ] 3.2: Extend `GET /api/matters/{matter_id}/timeline/events/{event_id}` to include contradiction summaries
  - [ ] 3.3: Extend contradiction list response to include `hasTimelineEvents` flag
  - [ ] 3.4: Add `contradictionCount` and `maxSeverity` to timeline event responses
  - [ ] 3.5: Update existing API tests for extended responses

- [ ] Task 4: Frontend - Cross-Engine Link Types and Store (AC: #4)
  - [ ] 4.1: Create `frontend/src/types/crossEngine.ts` with link types: `CrossEngineLink`, `EntityJourney`, `EventContext`, `ContradictionContext`
  - [ ] 4.2: Create `frontend/src/lib/api/cross-engine.ts` API client
  - [ ] 4.3: Create `frontend/src/hooks/useCrossEngineLinks.ts` hook for data fetching
  - [ ] 4.4: Extend `workspaceStore.ts` with `highlightedItemId` and `sourceTab` for navigation state

- [ ] Task 5: Frontend - Timeline Event Card Enhancement (AC: #1, #2)
  - [ ] 5.1: Add `ContradictionIndicator` component showing count and max severity badge
  - [ ] 5.2: Add indicator to `TimelineEventCard.tsx` when `hasContradiction` is true
  - [ ] 5.3: Make entities in TimelineEventCard clickable to navigate to Entities tab
  - [ ] 5.4: Add unit tests for ContradictionIndicator

- [ ] Task 6: Frontend - Timeline Event Detail Enhancement (AC: #1)
  - [ ] 6.1: Add "Related Contradictions" section to `TimelineEventDetail.tsx`
  - [ ] 6.2: Fetch and display contradictions involving event's entities
  - [ ] 6.3: Show contradiction cards with type, severity, and "View" link
  - [ ] 6.4: Clicking contradiction navigates to Contradictions tab with highlight

- [ ] Task 7: Frontend - Entity Detail Panel Enhancement (AC: #3)
  - [ ] 7.1: Add "Timeline Journey" section to `EntitiesDetailPanel.tsx`
  - [ ] 7.2: Fetch and display chronological timeline events for entity
  - [ ] 7.3: Show event cards with date, type, description
  - [ ] 7.4: Clicking event navigates to Timeline tab with highlight
  - [ ] 7.5: Add "Entity Contradictions" section showing all contradictions for this entity
  - [ ] 7.6: Add unit tests for new sections

- [ ] Task 8: Frontend - Contradiction Card Enhancement (AC: #5)
  - [ ] 8.1: Add "Related Timeline Events" section to contradiction detail view
  - [ ] 8.2: Parse dates from contradiction statements and match to timeline events
  - [ ] 8.3: Show event cards for matching dates with "View in Timeline" link
  - [ ] 8.4: Add unit tests for date matching and event linking

- [ ] Task 9: Frontend - Cross-Tab Navigation System (AC: #4)
  - [ ] 9.1: Implement `navigateToItem(tab, itemId, sourceTab)` function in workspaceStore
  - [ ] 9.2: Update tab navigation to detect highlighted items on mount
  - [ ] 9.3: Add scroll-into-view and highlight animation for linked items
  - [ ] 9.4: Add "Back to [source]" breadcrumb when navigating via cross-link
  - [ ] 9.5: Clear highlight after 3 seconds or user interaction
  - [ ] 9.6: Add e2e test for cross-tab navigation flow

## Dev Notes

### CRITICAL: Use Existing Relationships

The codebase already has the foundation for cross-engine links. **DO NOT** create new tables:

**Existing Data Relationships:**
1. **Timeline Events → Entities**: `events.entities_involved uuid[]` already links to `identity_nodes.id`
2. **Contradictions → Entities**: `statement_comparisons.entity_id uuid` already links to entity being contradicted
3. **Entity Mentions**: `entity_mentions` table tracks all document mentions

**Query Strategy (Use Existing Indexes):**
```sql
-- Get contradictions for an entity (existing index: idx_statement_comparisons_entity)
SELECT * FROM statement_comparisons
WHERE matter_id = $1 AND entity_id = $2;

-- Get timeline events for an entity (existing index: idx_events_entities)
SELECT * FROM events
WHERE matter_id = $1 AND $2 = ANY(entities_involved);

-- Get contradiction context for timeline event
SELECT sc.* FROM statement_comparisons sc
WHERE sc.matter_id = $1
AND sc.entity_id = ANY(
  SELECT unnest(entities_involved) FROM events WHERE id = $2
);
```

### Architecture Context

**Backend Service Layer:**
```
app/services/cross_engine_service.py  # NEW - Cross-engine link resolution
  ├── get_entity_journey()            # Timeline events for entity
  ├── get_entity_contradictions()     # Contradictions for entity
  ├── get_timeline_event_context()    # Contradictions related to event
  └── get_contradiction_context()     # Timeline events related to contradiction
```

**Frontend Navigation Flow:**
```
Timeline Tab → Event Detail → "View Contradiction" → Contradictions Tab (highlighted)
                          ↘ "View Entity" → Entities Tab (highlighted)

Entities Tab → Entity Detail → "Timeline Journey" → Timeline Tab (highlighted)
                           ↘ "View Contradiction" → Contradictions Tab (highlighted)

Contradictions Tab → Contradiction Detail → "Related Events" → Timeline Tab (highlighted)
```

### Source Tree References

**Backend (READ for patterns):**
- [backend/app/services/timeline_service.py](backend/app/services/timeline_service.py) - Timeline CRUD operations
- [backend/app/services/contradiction/contradiction_list_service.py](backend/app/services/contradiction/contradiction_list_service.py) - Contradiction fetching
- [backend/app/services/mig/graph.py](backend/app/services/mig/graph.py) - Entity graph operations
- [backend/app/models/timeline.py](backend/app/models/timeline.py) - Timeline models with EntityReference

**Frontend (READ for patterns):**
- [frontend/src/components/features/timeline/TimelineEventCard.tsx](frontend/src/components/features/timeline/TimelineEventCard.tsx) - Event card component
- [frontend/src/components/features/entities/EntitiesDetailPanel.tsx](frontend/src/components/features/entities/EntitiesDetailPanel.tsx) - Entity detail panel
- [frontend/src/components/features/contradiction/ContradictionCard.tsx](frontend/src/components/features/contradiction/ContradictionCard.tsx) - Contradiction card
- [frontend/src/stores/workspaceStore.ts](frontend/src/stores/workspaceStore.ts) - Workspace state management

**Database Schema:**
```sql
-- events table (existing)
entities_involved uuid[]  -- Array of entity IDs

-- statement_comparisons table (existing)
entity_id uuid NOT NULL   -- Single entity being contradicted

-- identity_nodes table (existing)
id, canonical_name, entity_type, aliases, metadata
```

### Data Models

**New Response Models (`backend/app/models/cross_engine.py`):**
```python
class EntityJourneyResponse(BaseModel):
    """Complete entity journey with timeline and contradictions"""
    entity_id: str
    entity_name: str
    entity_type: str
    timeline_events: list[TimelineEventSummary]  # Chronological events
    contradictions: list[ContradictionSummary]   # All contradictions
    total_events: int
    total_contradictions: int

class EventContextResponse(BaseModel):
    """Timeline event with cross-engine context"""
    event: TimelineEvent
    related_contradictions: list[ContradictionSummary]
    entities: list[EntitySummary]

class ContradictionContextResponse(BaseModel):
    """Contradiction with cross-engine context"""
    contradiction: Contradiction
    related_timeline_events: list[TimelineEventSummary]  # Events mentioning same dates
    entity: EntitySummary

class TimelineEventSummary(BaseModel):
    id: str
    event_date: str
    event_type: str
    description: str
    entity_count: int

class ContradictionSummary(BaseModel):
    id: str
    contradiction_type: str
    severity: str
    entity_name: str
    statement_a_preview: str
    statement_b_preview: str
```

**Frontend Types (`frontend/src/types/crossEngine.ts`):**
```typescript
interface CrossEngineLink {
  targetType: 'timeline' | 'contradiction' | 'entity';
  targetId: string;
  targetLabel: string;
  sourceType: 'timeline' | 'contradiction' | 'entity';
  sourceId: string;
}

interface EntityJourney {
  entityId: string;
  entityName: string;
  entityType: string;
  timelineEvents: TimelineEventSummary[];
  contradictions: ContradictionSummary[];
}

interface EventContext {
  event: TimelineEvent;
  relatedContradictions: ContradictionSummary[];
  entities: EntitySummary[];
}
```

### UI Component Patterns

**ContradictionIndicator Badge:**
```typescript
// Small badge showing contradiction presence on timeline cards
interface ContradictionIndicatorProps {
  count: number;
  maxSeverity: 'HIGH' | 'MEDIUM' | 'LOW';
  onClick: () => void;
}

// Colors: HIGH=red, MEDIUM=amber, LOW=blue
// Format: "3 contradictions" or just icon if space constrained
```

**Cross-Link Navigation:**
```typescript
// Workspace store extension
interface WorkspaceNavigationState {
  highlightedItemId: string | null;
  highlightedItemType: 'event' | 'contradiction' | 'entity' | null;
  sourceTab: string | null;  // Where the user came from
  clearHighlight: () => void;
  navigateToItem: (
    tab: WorkspaceTab,
    itemId: string,
    itemType: string,
    sourceTab: string
  ) => void;
}
```

### Testing Strategy

**Backend Tests:**
1. Unit tests for cross-engine service queries
2. API tests for new endpoints
3. Integration tests for entity journey aggregation
4. Performance tests for large matters (100+ entities)

**Frontend Tests:**
1. Component tests for ContradictionIndicator
2. Component tests for new detail panel sections
3. Integration tests for cross-tab navigation
4. E2E tests for full navigation flow

### Performance Considerations

- **Lazy loading**: Don't fetch cross-engine data until detail view opens
- **Pagination**: Limit timeline events and contradictions to 20 per page
- **Caching**: Cache entity journey in workspaceStore for 5 minutes
- **Batch queries**: Fetch contradiction counts in bulk when loading timeline

### Project Structure Notes

**New Files:**
- `backend/app/services/cross_engine_service.py` - Link resolution service
- `backend/app/models/cross_engine.py` - Response models
- `backend/app/api/routes/cross_engine.py` - API endpoints
- `frontend/src/types/crossEngine.ts` - TypeScript types
- `frontend/src/lib/api/cross-engine.ts` - API client
- `frontend/src/hooks/useCrossEngineLinks.ts` - Data fetching hook
- `frontend/src/components/features/timeline/ContradictionIndicator.tsx` - Badge component

**Modified Files:**
- `backend/app/api/routes/timeline.py` - Extend event responses
- `backend/app/main.py` - Register new routes
- `frontend/src/components/features/timeline/TimelineEventCard.tsx` - Add indicator
- `frontend/src/components/features/timeline/TimelineEventDetail.tsx` - Add contradictions section
- `frontend/src/components/features/entities/EntitiesDetailPanel.tsx` - Add journey section
- `frontend/src/stores/workspaceStore.ts` - Add navigation state

### References

- [backend/app/services/timeline_service.py](backend/app/services/timeline_service.py) - Timeline CRUD patterns
- [backend/app/services/mig/graph.py](backend/app/services/mig/graph.py) - Entity query patterns
- [frontend/src/components/features/timeline/TimelineEventCard.tsx](frontend/src/components/features/timeline/TimelineEventCard.tsx) - Card component pattern
- [frontend/src/stores/workspaceStore.ts](frontend/src/stores/workspaceStore.ts) - Store pattern
- [_bmad-output/project-context.md](project-context.md) - API response format, Zustand selector pattern

### Gap Traceability

- **Gap #15:** Cross-engine correlation
- **FR:** FR4.3 - Cross-engine correlation - timeline to contradiction links; entity journey visualization
- **Phase:** 4 (Operational Excellence)
- **Epic:** Gap Epic 5

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### Change Log
- 2026-01-27: Story created with comprehensive context analysis

### File List

