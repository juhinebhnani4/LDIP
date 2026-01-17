# Story 14.16: Anomalies UI Integration

Status: ready-for-dev

## Story

As a **legal attorney using LDIP**,
I want **to see timeline anomalies displayed in the workspace**,
so that **I can identify suspicious date patterns and sequence issues in my case documents**.

## Acceptance Criteria

1. **AC1: Anomalies visible in Timeline tab**
   - Anomaly indicators displayed on timeline events
   - Warning icon with tooltip showing anomaly description
   - Click on anomaly opens detail panel

2. **AC2: Anomalies summary in workspace**
   - Anomaly count shown in tab badge (e.g., "Timeline (3)")
   - Or anomaly banner at top of Timeline tab
   - Quick link to filter timeline to show only anomalous events

3. **AC3: Anomaly detail view**
   - Shows anomaly type (sequence_violation, suspicious_gap, date_pattern)
   - Shows affected events with document links
   - Shows AI-generated explanation
   - Shows severity (high/medium/low)

4. **AC4: Filter timeline by anomalies**
   - Add "Show anomalies only" filter toggle
   - Filter applies to all timeline views (vertical, horizontal, multi-track)
   - Clear filter returns to full timeline

5. **AC5: Wire to existing backend API**
   - Fetch from GET /api/matters/{matter_id}/anomalies
   - Fetch from GET /api/matters/{matter_id}/anomalies/{anomaly_id}
   - Handle loading and error states

## Tasks / Subtasks

- [ ] **Task 1: Create useAnomalies hook** (AC: #5)
  - [ ] 1.1 Create `frontend/src/hooks/useAnomalies.ts`
  - [ ] 1.2 Fetch from GET /api/matters/{matterId}/anomalies
  - [ ] 1.3 Support filtering parameters
  - [ ] 1.4 Export TypeScript interfaces

- [ ] **Task 2: Create AnomalyIndicator component** (AC: #1)
  - [ ] 2.1 Create `frontend/src/components/features/timeline/AnomalyIndicator.tsx`
  - [ ] 2.2 Warning icon with color based on severity
  - [ ] 2.3 Tooltip showing anomaly type and brief description
  - [ ] 2.4 Click handler to open detail panel

- [ ] **Task 3: Integrate anomalies into TimelineEventCard** (AC: #1)
  - [ ] 3.1 Modify TimelineEventCard to accept anomaly prop
  - [ ] 3.2 Display AnomalyIndicator when event has anomaly
  - [ ] 3.3 Add visual styling for anomalous events (border, background)

- [ ] **Task 4: Create AnomalyDetailPanel component** (AC: #3)
  - [ ] 4.1 Create `frontend/src/components/features/timeline/AnomalyDetailPanel.tsx`
  - [ ] 4.2 Slide-over or modal panel design
  - [ ] 4.3 Display anomaly type, severity, explanation
  - [ ] 4.4 Display affected events with document links
  - [ ] 4.5 Close button and keyboard escape

- [ ] **Task 5: Add anomaly count to Timeline tab** (AC: #2)
  - [ ] 5.1 Modify WorkspaceTabBar to show badge on Timeline tab
  - [ ] 5.2 Fetch anomaly count from API or use tab-stats
  - [ ] 5.3 Badge shows count (e.g., "3") or warning icon

- [ ] **Task 6: Create AnomaliesBanner component** (AC: #2)
  - [ ] 6.1 Create `frontend/src/components/features/timeline/AnomaliesBanner.tsx`
  - [ ] 6.2 Alert banner at top of Timeline tab when anomalies exist
  - [ ] 6.3 "X anomalies detected" with "Review" button
  - [ ] 6.4 Dismissible (per session)

- [ ] **Task 7: Add anomaly filter to TimelineFilters** (AC: #4)
  - [ ] 7.1 Add "Show anomalies only" toggle/checkbox
  - [ ] 7.2 Filter events to only those with anomalies
  - [ ] 7.3 Update URL query params
  - [ ] 7.4 Works across all timeline view modes

- [ ] **Task 8: Update timeline data fetching** (AC: #1, #5)
  - [ ] 8.1 Modify useTimeline to include anomaly data
  - [ ] 8.2 Or create separate useEventAnomalies for join
  - [ ] 8.3 Map anomalies to events by event_id

- [ ] **Task 9: Write tests** (AC: all)
  - [ ] 9.1 Test AnomalyIndicator renders with severity colors
  - [ ] 9.2 Test AnomalyDetailPanel displays all fields
  - [ ] 9.3 Test filter toggles correctly
  - [ ] 9.4 Test anomaly count badge updates

## Dev Notes

### Backend API (Already Implemented - Story 4-4)

```
GET /api/matters/{matter_id}/anomalies
Query params: severity, type, page, perPage

GET /api/matters/{matter_id}/anomalies/{anomaly_id}
```

Response structure:
```typescript
interface Anomaly {
  id: string;
  matterId: string;
  anomalyType: 'sequence_violation' | 'suspicious_gap' | 'date_pattern' | 'impossible_date';
  severity: 'high' | 'medium' | 'low';
  description: string;
  explanation: string;
  affectedEventIds: string[];
  metadata: {
    expectedSequence?: string[];
    actualSequence?: string[];
    gapDays?: number;
    pattern?: string;
  };
  createdAt: string;
}

interface AnomaliesListResponse {
  data: Anomaly[];
  meta: {
    total: number;
    page: number;
    perPage: number;
    totalPages: number;
  };
}
```

### Anomaly Types

| Type | Description | Visual |
|------|-------------|--------|
| sequence_violation | Events out of logical order | Red warning |
| suspicious_gap | Unusually long gap between related events | Orange warning |
| date_pattern | Suspicious date patterns (weekends, holidays) | Yellow warning |
| impossible_date | Date that can't be correct (future, before case) | Red error |

### Severity Colors

- **High**: `text-red-600 bg-red-50 border-red-200`
- **Medium**: `text-orange-600 bg-orange-50 border-orange-200`
- **Low**: `text-yellow-600 bg-yellow-50 border-yellow-200`

### Integration Points

The Timeline tab already has:
- TimelineEventCard - needs anomaly indicator
- TimelineFilters - needs anomaly filter
- useTimeline hook - needs anomaly data join

### File Structure

```
frontend/src/
├── components/features/timeline/
│   ├── AnomalyIndicator.tsx (CREATE)
│   ├── AnomalyDetailPanel.tsx (CREATE)
│   ├── AnomaliesBanner.tsx (CREATE)
│   ├── TimelineEventCard.tsx (MODIFY)
│   ├── TimelineFilters.tsx (MODIFY)
│   └── __tests__/
│       └── AnomalyIndicator.test.tsx
└── hooks/
    └── useAnomalies.ts (CREATE)
```

### References

- [Source: backend/app/api/routes/anomalies.py] - Backend API
- [Source: frontend/src/components/features/timeline/TimelineEventCard.tsx]
- [Source: frontend/src/components/features/timeline/TimelineFilters.tsx]
- [Source: _bmad-output/implementation-artifacts/4-4-timeline-anomaly-detection.md]
