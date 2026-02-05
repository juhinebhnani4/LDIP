# LDIP Playwright Latency Testing Plan

## Objective
Measure end-to-end latency across all user flows, identify bottlenecks, and generate actionable UX improvement recommendations.

---

## 1. Test Infrastructure Setup

### Files to Create
```
frontend/e2e/
├── playwright.config.ts          # Main config with projects, timeouts, reporters
├── fixtures/
│   ├── auth.fixture.ts           # Authentication setup
│   ├── matter.fixture.ts         # Matter creation/cleanup
│   └── metrics.fixture.ts        # Latency measurement utilities
├── utils/
│   ├── metrics-collector.ts      # Performance metrics collection
│   ├── websocket-listener.ts     # WebSocket message capture
│   ├── sse-listener.ts           # SSE stream timing
│   └── report-generator.ts       # HTML/JSON report generation
├── test-data/
│   ├── small-doc.pdf             # <10 pages
│   ├── medium-doc.pdf            # 10-50 pages
│   └── large-doc.pdf             # 50+ pages
└── tests/
    ├── upload.spec.ts
    ├── pipeline.spec.ts
    ├── ask-jaanch.spec.ts
    ├── timeline.spec.ts
    ├── contradictions.spec.ts
    ├── documents.spec.ts
    ├── summary.spec.ts
    ├── entities.spec.ts
    ├── citations.spec.ts
    ├── verification.spec.ts
    └── navigation.spec.ts
```

### Metrics Collection Strategy
```typescript
interface LatencyMetrics {
  operation: string;
  startTime: number;
  endTime: number;
  duration: number;
  networkRequests: NetworkTiming[];
  webVitals: { LCP: number; FID: number; CLS: number };
  customMarks: Record<string, number>;
}
```

---

## 2. Test Scenarios by Feature

### A. Upload Flow (`upload.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Single file upload | File selection → Upload complete |
| Bulk upload (5 files) | All files queued → All uploads complete |
| Large file upload (50+ pages) | Upload start → Processing started |
| Upload with ZIP | Extraction time + individual file processing |

**Key Metrics:**
- Time to upload acknowledgment
- Progress bar accuracy vs actual progress
- WebSocket connection establishment time

### B. Document Processing Pipeline (`pipeline.spec.ts`)
| Stage | Measurement Points |
|-------|-------------------|
| OCR | Upload complete → OCR done (WebSocket event) |
| Validation | OCR done → Validation complete |
| Chunking | Validation → Chunks created |
| Embedding | Chunking → Embeddings generated |
| Entity Extraction | Embedding → Entities available |
| Citation Discovery | Entity extraction → Citations ready |

**Key Metrics:**
- Per-stage latency
- Total pipeline time by document size
- WebSocket message delivery latency

### C. Ask Jaanch - Q&A (`ask-jaanch.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Simple question | Submit → First token (TTFT) |
| Complex question | TTFT + Total response time |
| Multi-turn conversation | Context loading + response time |
| Source citation click | Click → PDF highlight visible |

**Key Metrics:**
- Time to First Token (TTFT)
- Tokens per second (streaming rate)
- Engine trace timings (search, entity, citation engines)
- Source reference load time

### D. Timeline (`timeline.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Initial load | Navigation → Events rendered |
| View mode switch | Toggle → New view rendered |
| Filter application | Filter change → Results updated |
| Add manual event | Dialog open → Event appears in list |
| Anomaly click | Click → Detail panel rendered |

**Key Metrics:**
- Initial load with 50+ events
- Filter debounce + API response
- Anomaly detection latency

### E. Contradictions (`contradictions.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Initial load | Navigation → Cards rendered |
| Filter by severity | Filter → Results updated |
| Evidence click | Click → Split view with highlighted bbox |
| Pagination | Page change → New page rendered |

**Key Metrics:**
- Time to render contradiction cards
- Split-view PDF load + bbox highlight time
- Filter response time

### F. Documents Tab (`documents.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Document list load | Navigation → Table rendered |
| OCR quality display | Document row → Quality badge visible |
| Rename document | Dialog → Name updated in list |
| Delete document | Confirm → Document removed |
| Processing status poll | Status change → UI update |

**Key Metrics:**
- List render time with 20+ documents
- Polling latency for status updates
- Action completion feedback time

### G. Summary Page (`summary.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| First load (uncached) | Navigation → All sections rendered |
| Cached load | Navigation → Sections rendered |
| Section edit | Edit click → Save confirmation |
| Force refresh | Refresh click → New content |

**Key Metrics:**
- Cold vs warm summary generation
- Section-by-section render timing
- Attention items load time

### H. Entities/MIG (`entities.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Graph initial render | Navigation → Graph interactive |
| Node click | Click → Detail panel populated |
| Entity merge | Select 2 → Merge complete |
| View mode switch | Toggle → New view rendered |
| Search/filter | Type → Results filtered |

**Key Metrics:**
- React Flow graph render time (with 50+ nodes)
- Relationship edge calculation time
- Detail panel API fetch time

### I. Citations (`citations.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| List load | Navigation → Citations table rendered |
| Split view open | Citation click → PDF + highlights visible |
| Mark verified | Button click → Status updated |
| Bulk selection | Select all → Count updated |
| Missing Acts display | Load → Missing Acts card rendered |
| Upload missing Act | File select → Act processing started |

**Key Metrics:**
- Citation list pagination time
- Split-view PDF render + bbox overlay time
- Bulk action processing time

### J. Verification Queue (`verification.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Queue load | Navigation → Table rendered |
| Filter by tier | Filter → Results updated |
| Approve single | Click → Status updated |
| Bulk approve | Select + approve → All updated |
| Notes dialog | Open → Submit → Closed |

**Key Metrics:**
- Queue render time with 100+ items
- Bulk operation latency
- Optimistic update perceived speed

### K. Navigation & Transitions (`navigation.spec.ts`)
| Scenario | What to Measure |
|----------|-----------------|
| Tab switch | Tab click → Content rendered |
| Matter switch | Select matter → Workspace loaded |
| Deep link | Direct URL → Page ready |
| Back navigation | Browser back → Previous state restored |

**Key Metrics:**
- Tab transition time
- Route change latency
- State restoration time

---

## 3. Measurement Utilities

### WebSocket Listener
```typescript
// Capture WebSocket messages with timestamps
class WSListener {
  captureMessages(matterId: string): Promise<WSMessage[]>
  waitForEvent(type: string, timeout: number): Promise<WSMessage>
  measureLatency(sendTime: number, receiveTime: number): number
}
```

### SSE Stream Timer
```typescript
// Measure streaming response metrics
class SSETimer {
  measureTTFT(): Promise<number>           // Time to first token
  measureTokenRate(): Promise<number>      // Tokens/second
  measureTotalTime(): Promise<number>      // Full response time
  captureEngineTraces(): Promise<Trace[]>  // Engine execution times
}
```

### Performance Observer
```typescript
// Capture Web Vitals and custom metrics
class PerfObserver {
  captureLCP(): Promise<number>
  captureFID(): Promise<number>
  captureCLS(): Promise<number>
  captureResourceTimings(): Promise<ResourceTiming[]>
  captureNetworkRequests(): Promise<NetworkRequest[]>
}
```

---

## 4. Reporting

### Metrics Report Structure
```
reports/
├── latency-report.html          # Visual dashboard
├── latency-data.json            # Raw metrics data
├── comparison-baseline.json     # Previous run for comparison
└── ux-recommendations.md        # Generated improvement suggestions
```

### Report Sections
1. **Executive Summary** - Overall latency scores, pass/fail thresholds
2. **Per-Feature Breakdown** - Latency by feature with percentiles
3. **Bottleneck Analysis** - Slowest operations identified
4. **Network Analysis** - API call timings, payload sizes
5. **UX Recommendations** - Specific improvement suggestions

### Latency Thresholds (Target)
| Operation | Good | Acceptable | Poor |
|-----------|------|------------|------|
| Page load | <1s | <2s | >3s |
| API response | <200ms | <500ms | >1s |
| TTFT (chat) | <500ms | <1s | >2s |
| Filter update | <300ms | <500ms | >1s |
| PDF render | <1s | <2s | >3s |
| WebSocket message | <100ms | <300ms | >500ms |

---

## 5. UX Improvement Identification

### Automated Analysis
1. **Perceived Performance** - Compare actual vs perceived latency
2. **Loading State Quality** - Check skeleton/spinner presence
3. **Optimistic Updates** - Verify immediate feedback on actions
4. **Progressive Loading** - Check if critical content loads first
5. **Error Recovery** - Measure time to recover from failures

### Manual Review Points
1. **Feedback Gaps** - Operations without loading indicators
2. **Unnecessary Waits** - Sequential operations that could be parallel
3. **Over-fetching** - Large payloads that could be paginated
4. **Missing Caching** - Repeated fetches for same data
5. **Blocking Operations** - UI freezes during heavy computation

---

## 6. Implementation Order

### Phase 1: Infrastructure
- [ ] Set up Playwright config with custom reporters
- [ ] Create auth fixture with session persistence
- [ ] Build metrics collection utilities
- [ ] Create test data (sample PDFs)

### Phase 2: Core Flow Tests
- [ ] Upload flow tests
- [ ] Pipeline monitoring tests
- [ ] Ask Jaanch streaming tests

### Phase 3: Feature Tests
- [ ] Timeline tests
- [ ] Contradictions tests
- [ ] Documents tab tests
- [ ] Summary page tests
- [ ] Entities/MIG tests
- [ ] Citations tests
- [ ] Verification queue tests

### Phase 4: Analysis & Reporting
- [ ] Navigation/transition tests
- [ ] Generate baseline report
- [ ] Document UX recommendations

---

## 7. Configuration

### Decisions Made
| Question | Decision |
|----------|----------|
| **Environment** | Both (configurable) - Support local dev + staging via `TEST_BASE_URL` env var |
| **Authentication** | Session persistence - Authenticate once, reuse across tests for speed |
| **Test Data** | Create fresh each run - Upload real PDFs for realistic latency measurement |
| **CI/CD** | Both - Manual for development, GitHub Actions for regression detection |

### Environment Configuration
```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    baseURL: process.env.TEST_BASE_URL || 'http://localhost:3000',
    storageState: 'playwright/.auth/session.json', // Persist auth
  },
  projects: [
    { name: 'setup', testMatch: /global-setup\.ts/ },
    { name: 'chromium', dependencies: ['setup'] },
  ],
});
```

### GitHub Actions Workflow
```yaml
# .github/workflows/playwright-latency.yml
name: Latency Tests
on:
  pull_request:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test
        env:
          TEST_BASE_URL: ${{ secrets.STAGING_URL }}
          TEST_USER_EMAIL: ${{ secrets.TEST_USER_EMAIL }}
          TEST_USER_PASSWORD: ${{ secrets.TEST_USER_PASSWORD }}
      - uses: actions/upload-artifact@v4
        with:
          name: latency-report
          path: reports/
```

### Test Data Strategy
Each test run will:
1. Create a fresh matter with unique name
2. Upload test PDFs from `e2e/test-data/`
3. Wait for pipeline completion (with timeout)
4. Run latency measurements
5. Clean up matter after test (optional, configurable)

---

## 8. Key Files to Modify

| File | Purpose |
|------|---------|
| `frontend/package.json` | Add Playwright dependencies |
| `frontend/playwright.config.ts` | Main configuration |
| `frontend/.env.test` | Test environment variables |

---

## 9. Verification

After implementation:
1. Run full test suite: `npx playwright test`
2. Generate report: `npx playwright show-report`
3. Review latency data in `reports/latency-data.json`
4. Compare against thresholds
5. Document UX improvement opportunities
