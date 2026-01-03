# MVP Scope Definition v1.0
# LDIP - Legal Document Intelligence Platform
**Version:** 1.0
**Date:** 2026-01-01
**Timeline:** 15-16 months
**Status:** Implementation-Ready

---

## Document Purpose

This MVP Scope Definition provides detailed implementation guidance for building LDIP. It breaks down:
- Each engine's I/O contracts, dependencies, and acceptance criteria
- 3-Layer Memory System implementation details
- Safety features specifications
- Month-by-month timeline
- Team requirements and skill sets
- Risk register with mitigation strategies

**Parent Document:** [Requirements-Baseline-v1.0.md](./Requirements-Baseline-v1.0.md)

---

## Table of Contents

1. [Engine Specifications](#engine-specifications)
2. [Memory System Implementation](#memory-system-implementation)
3. [Safety Features](#safety-features)
4. [Infrastructure Setup](#infrastructure-setup)
5. [Timeline Breakdown](#timeline-breakdown)
6. [Team Requirements](#team-requirements)
7. [Risk Register](#risk-register)
8. [Acceptance Criteria](#acceptance-criteria)

---

## Engine Specifications

### Engine Architecture Overview

**Orchestrator Pattern (MVP - 3 Engines):**
```
User Query
  ↓
Query Router (analyzes intent)
  ↓
Engine Selection (orchestrator)
  ├─ Citation query → Citation Engine
  ├─ Timeline query → Timeline Engine
  └─ Contradiction query → Contradiction Engine
  ↓
Engine Execution (with I/O contract)
  ↓
Result Aggregation
  ↓
Safety Layer (guardrails + language policing)
  ↓
Response to user
```

> **Note:** Documentation Gap Engine and Process Chain Engine are deferred to Phase 2.
> See [Phase-2-Backlog.md](./Phase-2-Backlog.md) for details.

**Common I/O Contract Structure:**
```typescript
interface EngineInput {
  matter_id: string;
  query: string;
  context?: {
    session_memory?: SessionContext;
    matter_memory?: MatterMemory;
    mig_context?: MIGContext;
  };
  parameters?: Record<string, any>;
}

interface EngineOutput {
  engine_id: string;
  execution_id: string;
  status: 'success' | 'error' | 'partial';
  confidence: number; // 0-100
  findings: Finding[];
  metadata: {
    execution_time_ms: number;
    tokens_used: number;
    cost_usd: number;
    engines_invoked: string[];
  };
  audit_trail: AuditEntry[];
}

interface Finding {
  finding_id: string;
  type: string;
  description: string;
  evidence: Evidence[];
  confidence: number;
  requires_verification: boolean;
}

interface Evidence {
  document_id: string;
  page: number;
  bbox_ids: string[];
  text_excerpt: string;
  source: 'mig' | 'rag' | 'both';
}
```

---

### Engine 1: Citation Verification Engine

**Purpose:** Verify Act references, flag misattributions, link citations to visual bounding boxes

**I/O Contract:**
```typescript
interface CitationEngineInput extends EngineInput {
  parameters: {
    acts_to_verify?: string[]; // e.g., ['IPC', 'BNS', 'SARFAESI']
    strict_mode?: boolean; // Fail on any unverified citation
  };
}

interface CitationEngineOutput extends EngineOutput {
  findings: CitationFinding[];
}

interface CitationFinding extends Finding {
  type: 'verified_citation' | 'unverified_citation' | 'misattribution' | 'section_error';
  citation_text: string; // e.g., "Section 138 of NI Act"
  act_name: string;
  section: string;
  verification_status: 'verified' | 'not_found' | 'section_mismatch' | 'act_mismatch';
  correct_citation?: string; // If misattribution detected
}
```

**Implementation Steps:**
1. **Citation Extraction (Gemini ingestion)**
   - Regex patterns for Indian Act citations (Section X of Y Act)
   - Store in `citations` table with document/page/bbox references

2. **Verification Logic (GPT-4 reasoning)**
   - Load Act database (IPC, BNS, BNSS, NI Act, SARFAESI, etc.)
   - Cross-check section exists in cited Act
   - Flag misattributions (e.g., "Section 420 of BNS" - Section 420 is IPC, not BNS)

3. **Bounding Box Linkage**
   - Link verified citations to `bounding_boxes` table
   - Enable click-to-highlight in frontend

**Dependencies:**
- Acts database (JSON or PostgreSQL table with all sections)
- citations table
- bounding_boxes table

**Acceptance Criteria:**
- 95%+ citation extraction recall (find 95%+ of all Act references)
- 95%+ verification accuracy (correctly verify/reject citations)
- <10 seconds to verify all citations in 2000-page document
- Bounding box linkage for 100% of verified citations

**Timeline:** 6 weeks (Months 4-5)

---

### Engine 2: Timeline Construction Engine

**Purpose:** Extract dates/events, build chronological timeline, validate sequences

**I/O Contract:**
```typescript
interface TimelineEngineInput extends EngineInput {
  parameters: {
    date_range?: { start: Date; end: Date };
    event_types?: string[]; // Filter: ['filing', 'notice', 'hearing', 'order']
    entities?: string[]; // Filter timeline by specific entities
  };
}

interface TimelineEngineOutput extends EngineOutput {
  findings: TimelineEvent[];
  timeline_cache_updated: boolean; // Did we update Matter Memory timeline cache?
}

interface TimelineEvent extends Finding {
  type: 'event';
  date: Date;
  date_confidence: number; // OCR confidence for date extraction
  event_type: string; // 'filing', 'notice', 'hearing', 'order', 'transaction', etc.
  description: string;
  entities_involved: EntityReference[];
  sequence_validation: {
    logical_order: boolean; // Does this event make sense chronologically?
    warnings: string[]; // e.g., "Notice dated after filing - unusual"
  };
}

interface EntityReference {
  entity_id: string; // MIG canonical entity ID
  entity_name: string; // Canonical name
  role_in_event: string; // 'initiator', 'recipient', 'witness', etc.
}
```

**Implementation Steps:**
1. **Date + Event Extraction (Gemini ingestion)**
   - Extract all dates with surrounding context (±200 words)
   - Classify event types using Gemini
   - Store in `events` table with entity_ids (from MIG)

2. **Chronological Sorting**
   - Order events by date
   - Flag date ambiguities (e.g., "20/10/2023" - DD/MM or MM/DD?)

3. **Sequence Validation (GPT-4 reasoning)**
   - Check logical order: Notice before filing? Hearing after notice?
   - Flag anomalies: "Notice dated 9 months after borrower default"

4. **Matter Memory Caching**
   - Cache timeline in `/matter-{id}/timeline_cache.jsonb`
   - Enables instant re-queries without re-extraction

**Dependencies:**
- events table
- MIG (identity_nodes for entity linking)
- Matter Memory (PostgreSQL JSONB)

**Acceptance Criteria:**
- 80%+ event extraction recall (find 80%+ of all events in documents)
- 90%+ event extraction accuracy (correctly identify event type)
- 95%+ chronological ordering accuracy
- Sequence validation flags 70%+ of logical anomalies
- Timeline cached in Matter Memory for instant re-queries

**Timeline:** 6 weeks (Months 5-6)

---

### Engine 3: Consistency & Contradiction Engine

**Purpose:** Detect conflicting statements by same entity using MIG entity resolution

**I/O Contract:**
```typescript
interface ContradictionEngineInput extends EngineInput {
  parameters: {
    entities_to_check?: string[]; // Check specific entities only
    statement_types?: string[]; // 'claim', 'denial', 'admission', 'testimony'
    semantic_threshold?: number; // 0-1, contradiction confidence threshold
  };
}

interface ContradictionEngineOutput extends EngineOutput {
  findings: ContradictionFinding[];
}

interface ContradictionFinding extends Finding {
  type: 'semantic_contradiction' | 'factual_contradiction' | 'date_mismatch' | 'amount_mismatch';
  entity_id: string; // MIG canonical entity who made contradictory statements
  entity_name: string;
  statement_1: Statement;
  statement_2: Statement;
  contradiction_explanation: string; // GPT-4 natural language explanation
  severity: 'high' | 'medium' | 'low';
}

interface Statement {
  document_id: string;
  page: number;
  bbox_ids: string[];
  text_excerpt: string;
  date_made?: Date;
  context: string; // Surrounding text
}
```

**Implementation Steps:**
1. **Entity Statement Grouping (MIG)**
   - Query all chunks mentioning a canonical entity_id
   - Example: entity_id=e-nirav groups:
     - "Nirav Jobalia stated..."
     - "N.D. Jobalia claims..."
     - "Mr. Jobalia testified..."

2. **Semantic Comparison (GPT-4 reasoning)**
   - Compare pairs of statements for contradictions
   - Prompt: "Do these two statements by [entity] contradict each other? Explain."
   - Use chain-of-thought reasoning for accuracy

3. **Factual Checks**
   - Date mismatches: "Sale on June 15" vs "Sale on July 20"
   - Amount mismatches: "Loan of ₹50 lakhs" vs "Loan of ₹5 crores"

4. **Confidence Scoring**
   - High: Clear factual contradictions (dates, amounts)
   - Medium: Semantic contradictions requiring interpretation
   - Low: Possible contradictions needing attorney review

**Dependencies:**
- MIG (identity_nodes, identity_edges for entity resolution)
- RAG (chunks with entity mentions)
- GPT-4 reasoning

**Acceptance Criteria:**
- 95%+ entity resolution accuracy (correctly link name variants)
- 70%+ contradiction detection recall (find 70%+ of contradictions)
- 90%+ contradiction detection precision (low false positive rate)
- Confidence scores align with attorney verification (high confidence = 90%+ attorney agreement)

**Timeline:** 6 weeks (Months 6-7)

---

### ❌ Engine 4: Documentation Gap Engine — DEFERRED TO PHASE 2

> **Status:** DEFERRED per Decision 10 (2026-01-03)
> **Reason:** Requires process templates that must be created from real matter experience
> **See:** [Phase-2-Backlog.md](./Phase-2-Backlog.md) for full specification
> **Trigger:** After Juhi creates manual templates from 5+ completed matters

---

### ❌ Engine 5: Process Chain Integrity Engine — DEFERRED TO PHASE 2

> **Status:** DEFERRED per Decision 10 (2026-01-03)
> **Reason:** Requires "typical timeline" templates that must be created from real matter experience
> **See:** [Phase-2-Backlog.md](./Phase-2-Backlog.md) for full specification
> **Trigger:** After Juhi creates manual templates from 5+ completed matters

---

### Engine Orchestrator

**Purpose:** Route queries to appropriate engines, aggregate results, manage execution

**Implementation:**
```typescript
class EngineOrchestrator {
  async executeQuery(input: EngineInput): Promise<OrchestratorOutput> {
    // Step 1: Analyze query intent
    const intent = await this.analyzeIntent(input.query);

    // Step 2: Select engines
    const engines = this.selectEngines(intent);
    // Example: "Find contradictions in custodian statements"
    //   → Timeline Engine (get custodian timeline)
    //   → Contradiction Engine (check for conflicts)

    // Step 3: Execute engines in order (some parallel, some sequential)
    const results = await this.executeEngines(engines, input);

    // Step 4: Aggregate results
    const aggregated = this.aggregateResults(results);

    // Step 5: Apply safety layer
    const safe_output = await this.applySafetyLayer(aggregated);

    // Step 6: Log to audit trail
    await this.logExecution(input, safe_output);

    return safe_output;
  }
}
```

**Timeline:** 2 weeks (Month 8)

---

## Memory System Implementation

### Layer 1: Session Memory (Redis)

**Purpose:** Multi-turn conversation context

**Implementation:**
```typescript
// Redis storage structure
interface SessionContext {
  session_id: string;
  matter_id: string;
  user_id: string;
  created_at: Date;
  last_activity: Date;
  messages: SessionMessage[]; // Sliding window, max 20
  entities_mentioned: Map<string, string>; // Pronoun resolution
}

interface SessionMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  engine_trace?: {
    engines_invoked: string[];
    execution_time_ms: number;
    findings_count: number;
  };
}

// Redis key: session:{session_id}
// TTL: 4 hours (14400 seconds)
```

**Storage Pattern:**
```typescript
// Save session
await redis.setex(
  `session:${sessionId}`,
  14400, // 4 hours
  JSON.stringify(sessionContext)
);

// Load session
const session = JSON.parse(
  await redis.get(`session:${sessionId}`)
);

// Pronoun resolution example
// User: "Who is the custodian?"
// Assistant: "Jitendra Kumar"
// session.entities_mentioned.set('custodian', 'e-jitendra')
// User: "When did they file the affidavit?"
// System resolves "they" → e-jitendra
```

**Timeline:** 2 weeks (Month 9)

---

### Layer 2: Matter Memory (PostgreSQL JSONB)

**Purpose:** Persistent matter-level knowledge, query history, forensic audit

**Database Schema:**
```sql
CREATE TABLE matter_memory (
  memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id),
  file_path VARCHAR NOT NULL, -- e.g., '/query_history.jsonb'
  content JSONB NOT NULL,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  modified_by UUID REFERENCES users(id),
  modified_at TIMESTAMPTZ DEFAULT NOW(),
  archived BOOLEAN DEFAULT FALSE,
  UNIQUE(matter_id, file_path)
);

-- RLS policy: Only attorneys on matter can access
CREATE POLICY matter_memory_isolation ON matter_memory
  USING (matter_id IN (
    SELECT matter_id FROM matter_attorneys WHERE attorney_id = auth.uid()
  ));

-- Index for fast lookups
CREATE INDEX idx_matter_memory_matter ON matter_memory(matter_id, file_path)
WHERE archived = FALSE;
```

**File Structure:**
```typescript
// /matter-{id}/query_history.jsonb
interface QueryHistoryFile {
  queries: QueryHistoryEntry[];
}

interface QueryHistoryEntry {
  query_id: string;
  query_text: string;
  query_intent: string;
  asked_by: string; // attorney_id
  asked_at: Date;
  engines_invoked: string[];
  execution_time_ms: number;
  findings_count: number;
  response_summary: string; // First 500 chars of response
  verified: boolean;
  verified_by?: string;
  verified_at?: Date;
}

// /matter-{id}/timeline_cache.jsonb
interface TimelineCacheFile {
  cached_at: Date;
  events: TimelineEvent[];
  last_document_upload: Date; // Invalidate cache if new docs uploaded
}

// /matter-{id}/entity_graph.jsonb
interface EntityGraphCacheFile {
  cached_at: Date;
  entities: Map<string, EntityNode>;
  relationships: EntityRelationship[];
}

interface EntityNode {
  entity_id: string;
  canonical_name: string;
  aliases: string[];
  entity_type: 'PERSON' | 'ORG' | 'INSTITUTION' | 'ASSET';
  metadata: any;
}

// /matter-{id}/key_findings.jsonb
interface KeyFindingsFile {
  findings: VerifiedFinding[];
}

interface VerifiedFinding {
  finding_id: string;
  finding_type: string;
  description: string;
  evidence: Evidence[];
  verified_by: string; // attorney_id
  verified_at: Date;
  notes?: string; // Attorney annotations
}

// /matter-{id}/research_notes.jsonb
interface ResearchNotesFile {
  notes: ResearchNote[];
}

interface ResearchNote {
  note_id: string;
  created_by: string;
  created_at: Date;
  title: string;
  content: string; // Markdown
  tags: string[];
  linked_findings: string[]; // finding_ids
}
```

**Implementation:**
```typescript
class MatterMemoryService {
  async readFile(matterId: string, filePath: string): Promise<any> {
    const result = await db.query(
      `SELECT content FROM matter_memory
       WHERE matter_id = $1 AND file_path = $2 AND archived = false`,
      [matterId, filePath]
    );
    return result.rows[0]?.content;
  }

  async writeFile(matterId: string, filePath: string, content: any, userId: string): Promise<void> {
    await db.query(
      `INSERT INTO matter_memory (matter_id, file_path, content, created_by, modified_by)
       VALUES ($1, $2, $3, $4, $4)
       ON CONFLICT (matter_id, file_path)
       DO UPDATE SET content = $3, modified_by = $4, modified_at = NOW()`,
      [matterId, filePath, JSON.stringify(content), userId]
    );
  }

  async appendToQueryHistory(matterId: string, entry: QueryHistoryEntry): Promise<void> {
    const history = await this.readFile(matterId, '/query_history.jsonb') || { queries: [] };
    history.queries.push(entry);
    await this.writeFile(matterId, '/query_history.jsonb', history, entry.asked_by);
  }
}
```

**Timeline:** 3 weeks (Months 9-10)

---

### Layer 3: Query Cache (Redis)

**Purpose:** Performance optimization for identical queries

**Implementation:**
```typescript
// Redis key: cache:query:{matter_id}:{query_hash}
// TTL: 1 hour (3600 seconds)

async function getCachedQuery(matterId: string, query: string): Promise<any | null> {
  const queryHash = crypto.createHash('sha256').update(query).digest('hex');
  const key = `cache:query:${matterId}:${queryHash}`;
  const cached = await redis.get(key);
  return cached ? JSON.parse(cached) : null;
}

async function cacheQuery(matterId: string, query: string, result: any): Promise<void> {
  const queryHash = crypto.createHash('sha256').update(query).digest('hex');
  const key = `cache:query:${matterId}:${queryHash}`;
  await redis.setex(key, 3600, JSON.stringify(result)); // 1 hour
}

// Invalidation: Clear cache on document upload
async function clearMatterCache(matterId: string): Promise<void> {
  const keys = await redis.keys(`cache:query:${matterId}:*`);
  if (keys.length > 0) {
    await redis.del(...keys);
  }
}
```

**Timeline:** 1 week (Month 10)

---

## Safety Features

### 1. Query Guardrails (2 weeks)

**Purpose:** Block dangerous legal questions, suggest safe rewrites

**Implementation:**
```typescript
interface GuardrailCheck {
  is_safe: boolean;
  violation_type?: 'legal_conclusion' | 'prediction' | 'advice' | 'personal_opinion';
  explanation?: string;
  suggested_rewrite?: string;
}

async function checkQuerySafety(query: string): Promise<GuardrailCheck> {
  // Pattern matching (fast path)
  const dangerous_patterns = [
    /should (i|we|client) (file|appeal|settle)/i,
    /is (client|defendant|plaintiff) (guilty|innocent|liable)/i,
    /will (judge|court) (rule|decide|hold)/i,
    /what are (my|our) chances/i,
  ];

  for (const pattern of dangerous_patterns) {
    if (pattern.test(query)) {
      return {
        is_safe: false,
        violation_type: 'legal_conclusion',
        explanation: 'This query asks for a legal conclusion or prediction.',
        suggested_rewrite: suggestRewrite(query)
      };
    }
  }

  // LLM-based check (GPT-4o-mini, for subtle violations)
  const llm_check = await gpt4_mini.complete({
    system: "You are a legal AI safety checker. Determine if this query asks for legal advice, predictions, or conclusions. Only factual document analysis queries are allowed.",
    user: query
  });

  return parseLLMResponse(llm_check);
}

function suggestRewrite(unsafe_query: string): string {
  // Example rewrites
  const rewrites = {
    'Should I file an appeal?': 'What are the grounds for appeal in this matter?',
    'Is client guilty?': 'What evidence supports or contradicts the charges?',
    'Will we win?': 'What are the key strengths and weaknesses of this case?',
  };

  // Use GPT-4o-mini to generate contextual rewrite
  return rewriteQuery(unsafe_query);
}
```

**Timeline:** 2 weeks (Month 13)

---

### 2. Language Policing (1 week)

**Purpose:** Sanitize legal conclusions from outputs

**Implementation:**
```typescript
async function policeLanguage(output: string): Promise<string> {
  // Regex-based replacements (fast)
  const replacements = [
    { pattern: /violated (Section \d+)/gi, replacement: 'affected by $1' },
    { pattern: /(defendant|plaintiff|client) is (guilty|innocent|liable)/gi, replacement: '$1\'s liability regarding' },
    { pattern: /the court will (rule|hold|decide)/gi, replacement: 'the court may consider' },
    { pattern: /proves that/gi, replacement: 'suggests that' },
    { pattern: /client should/gi, replacement: 'client may consider' },
  ];

  let policed = output;
  for (const { pattern, replacement } of replacements) {
    policed = policed.replace(pattern, replacement);
  }

  // LLM-based policing (GPT-4o-mini, for subtle conclusions)
  const final_policed = await gpt4_mini.complete({
    system: "Remove any legal conclusions from this text. Replace with neutral, factual language. Examples: 'violated' → 'affected by', 'is guilty' → 'allegations include', 'will rule' → 'may consider'.",
    user: policed
  });

  return final_policed;
}
```

**Timeline:** 1 week (Month 13)

---

### 3. Attorney Verification Workflow (3 weeks)

**Purpose:** Court-defensible audit trail with approve/reject UI

**Database Schema:**
```sql
CREATE TABLE finding_verifications (
  verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id UUID NOT NULL REFERENCES matters(id),
  finding_id UUID NOT NULL,
  finding_type VARCHAR NOT NULL,
  finding_summary TEXT NOT NULL,
  verified_by UUID NOT NULL REFERENCES users(id),
  verified_at TIMESTAMPTZ DEFAULT NOW(),
  decision VARCHAR NOT NULL CHECK (decision IN ('approved', 'rejected', 'flagged')),
  notes TEXT,
  confidence_before INTEGER, -- Engine confidence 0-100
  confidence_after INTEGER, -- Attorney adjustment 0-100
);

CREATE INDEX idx_verifications_matter ON finding_verifications(matter_id);
CREATE INDEX idx_verifications_attorney ON finding_verifications(verified_by);
```

**UI Components (Next.js 16 + React):**
```tsx
// components/VerificationQueue.tsx
'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useFindingsStore } from '@/stores/findings';

export function VerificationQueue() {
  const { getUnverifiedFindings, verifyFinding } = useFindingsStore();
  const [findings, setFindings] = useState<Finding[]>([]);

  useEffect(() => {
    getUnverifiedFindings().then(setFindings);
  }, []);

  async function handleVerify(finding: Finding, decision: 'approved' | 'rejected' | 'flagged') {
    const notes = await promptForNotes(decision);
    await verifyFinding(finding.finding_id, decision, notes);
    setFindings(prev => prev.filter(f => f.finding_id !== finding.finding_id));
  }

  return (
    <div className="verification-queue">
      <h2 className="text-xl font-semibold mb-4">Findings Requiring Verification</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Type</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {findings.map((finding) => (
            <TableRow key={finding.finding_id}>
              <TableCell>{finding.finding_type}</TableCell>
              <TableCell>{finding.description}</TableCell>
              <TableCell><Progress value={finding.confidence} /></TableCell>
              <TableCell className="space-x-2">
                <Button variant="default" onClick={() => handleVerify(finding, 'approved')}>Approve</Button>
                <Button variant="destructive" onClick={() => handleVerify(finding, 'rejected')}>Reject</Button>
                <Button variant="secondary" onClick={() => handleVerify(finding, 'flagged')}>Flag</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

**Timeline:** 3 weeks (Months 13-14)

---

## Infrastructure Setup

### Month 1-3: Foundation

**Week 1-2: Supabase Setup**
- Create Supabase project
- Configure PostgreSQL extensions (pgvector, uuid-ossp)
- Set up Supabase Auth (email/password, Google OAuth)
- Configure Supabase Storage buckets (matter-documents, profile-photos)

**Week 3-4: Database Schema**
- Core tables: matters, users, attorneys, matter_attorneys
- MIG tables: identity_nodes, identity_edges, pre_linked_relationships, events
- RAG tables: documents, bounding_boxes, chunks, citations
- Memory tables: matter_memory, finding_verifications
- RLS policies for all tables

**Week 5-6: Backend Scaffolding**
- FastAPI project setup (Poetry for dependencies)
- SQLAlchemy 2.0 models (async)
- Alembic migrations
- Supabase JWT validation middleware
- CORS configuration

**Week 7-8: Frontend Scaffolding**
- Next.js 16 project setup with App Router
- shadcn/ui installation and theming
- Tailwind CSS configuration
- Next.js routing (file-based)
- Zustand stores (auth, matters, findings)

**Week 9-10: Redis + Celery**
- Redis Cloud setup (or local Redis)
- Celery worker configuration
- Task queue for long-running jobs (OCR, ingestion, timeline extraction)

**Week 11-12: Dev Environment**
- Docker Compose for local development
- Environment variables (.env files)
- Testing framework setup (Pytest for backend, Jest + React Testing Library for frontend)
- CI/CD pipeline (GitHub Actions)

---

## Timeline Breakdown

### Months 1-3: Infrastructure (12 weeks)
See [Infrastructure Setup](#infrastructure-setup) above

### Months 4-7: Core Engines (14 weeks) — REVISED per Decision 10
- **Month 4-5 (6 weeks):** Citation Verification Engine
- **Month 5-6 (6 weeks):** Timeline Construction Engine
- **Month 6-7 (6 weeks):** Consistency & Contradiction Engine
- **Month 7 (2 weeks):** Engine Orchestrator
- ~~**Month 7 (3 weeks):** Documentation Gap Engine~~ → DEFERRED TO PHASE 2
- ~~**Month 7-8 (3 weeks):** Process Chain Integrity Engine~~ → DEFERRED TO PHASE 2

> **Timeline Savings:** 6 weeks saved by deferring 2 engines to Phase 2.
> **See:** [Phase-2-Backlog.md](./Phase-2-Backlog.md)

### Months 9-12: Memory + RAG (16 weeks)
- **Month 9 (4 weeks):** MIG Implementation
  - identity_nodes, identity_edges tables
  - Entity extraction (Gemini)
  - Alias linking logic
  - pre_linked_relationships table
- **Month 10 (4 weeks):** RAG Pipeline
  - Parent-child chunking
  - Embedding generation (OpenAI ada-002)
  - Hybrid search (BM25 + Vector)
  - Cohere reranking integration
- **Month 10-11 (4 weeks):** Memory System
  - Session Memory (Redis) - 2 weeks
  - Matter Memory (PostgreSQL JSONB) - 3 weeks
  - Query Cache (Redis) - 1 week
- **Month 11-12 (4 weeks):** Integration
  - Connect engines to MIG + RAG
  - Test end-to-end flows
  - Performance optimization

### Months 13-14: Safety Features (8 weeks)
- **Month 13 (2 weeks):** Query Guardrails
- **Month 13 (1 week):** Language Policing
- **Month 13-14 (3 weeks):** Attorney Verification Workflow
- **Month 14 (2 weeks):** Integration testing

### Months 14-15: Integration + Testing (8 weeks)
- **Week 1-2:** Frontend-backend integration
- **Week 3-4:** End-to-end testing (happy paths)
- **Week 5-6:** Error handling and edge cases
- **Week 7-8:** Performance optimization (query speed, memory usage)

### Month 16: Deployment + UAT (4 weeks)
- **Week 1:** Production deployment (Vercel frontend, Railway/Render backend)
- **Week 2:** User acceptance testing (UAT) with Juhi
- **Week 3:** Bug fixes from UAT
- **Week 4:** Documentation (user guide, API docs, training materials)

---

## Team Requirements

### Required Roles

**1. Full-Stack Developer (Primary)** - 1 person
- Skills: Python, FastAPI, React/Next.js, PostgreSQL, Redis
- Responsibility: End-to-end feature development, engine implementation

**2. Backend Developer (LLM Integration)** - 1 person
- Skills: Python, LLM APIs (OpenAI, Google), prompt engineering
- Responsibility: Gemini + GPT integration, MIG + RAG pipelines

**3. Frontend Developer** - 1 person
- Skills: Next.js 16, React, TypeScript, shadcn/ui, D3.js (for timeline visualization)
- Responsibility: UI components, verification workflow, visual citations

**4. DevOps Engineer** - 0.5 person (part-time)
- Skills: Docker, CI/CD, Supabase, Redis Cloud, Vercel
- Responsibility: Infrastructure setup, deployment, monitoring

**5. QA Engineer** - 0.5 person (part-time, starting Month 13)
- Skills: Pytest, Jest, React Testing Library, manual testing
- Responsibility: Test coverage, edge case identification, UAT coordination

**6. Product Owner (Juhi)** - UAT, requirements clarification, attorney verification testing

**Total Team Size:** 3.5-4 people

---

## Risk Register

### High-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **OCR quality poor for handwritten docs** | High | High | Gemini validation + human review queue, OCR confidence thresholds |
| **MIG entity resolution <95% accuracy** | Medium | High | Iterative prompt engineering, attorney verification, manual alias override UI |
| **Timeline slippage (15-16 months → 18-20 months)** | Medium | Medium | Buffer built into each phase, ruthless prioritization, monthly progress reviews |
| **LLM API price increases** | Medium | Medium | Hybrid architecture allows swapping models, cost monitoring alerts |
| **Attorney adoption resistance** | Medium | High | Focus on UX, attorney supervision (not autonomous AI), training materials |
| **Court acceptance of AI findings** | Low | High | Attorney verification workflow = court-defensible audit trail, conservative language policing |

### Medium-Risk Items

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **GPT-5.2 not available/affordable** | Low | Low | Start with GPT-4, upgrade when ready, architecture supports swap |
| **Process templates not ready for Phase 2** | High | Medium | MVP ships with basic hardcoded rules, Phase 2 waits for templates |
| **Supabase outages** | Low | Medium | Implement retry logic, fallback to cached data, monitoring |
| **Team skill gaps (LLM expertise)** | Medium | Medium | Training on prompt engineering, pair programming, external consultant if needed |
| **Scope creep (user requests Phase 2 features during MVP)** | High | Medium | Clear MoSCoW prioritization, "Phase 2 Parking Lot" document, stakeholder communication |

---

## Acceptance Criteria

### Engine-Level Criteria

**Citation Verification Engine:**
- [x] 95%+ citation extraction recall
- [x] 95%+ verification accuracy
- [x] <10 seconds to verify all citations in 2000-page document
- [x] Bounding box linkage for 100% of verified citations

**Timeline Construction Engine:**
- [x] 80%+ event extraction recall
- [x] 90%+ event extraction accuracy
- [x] 95%+ chronological ordering accuracy
- [x] 70%+ sequence validation (flag logical anomalies)
- [x] Timeline cached in Matter Memory for instant re-queries

**Consistency & Contradiction Engine:**
- [x] 95%+ entity resolution accuracy
- [x] 70%+ contradiction detection recall
- [x] 90%+ contradiction detection precision
- [x] Confidence scores align with attorney verification (high = 90%+ agreement)

**Documentation Gap Engine:**
- [x] 100% of SARFAESI/DRT critical documents checked
- [x] 80%+ accuracy in detecting missing documents
- [x] Attorney verification for all "missing" findings

**Process Chain Integrity Engine:**
- [x] 100% of critical process steps checked
- [x] 70%+ deviation detection recall
- [x] Attorney verification for all flagged deviations

### System-Level Criteria

**Performance:**
- [x] Query response time <10 seconds (95th percentile)
- [x] Document ingestion <5 minutes per 100 pages
- [x] Timeline generation <2 minutes for 2000-page matter
- [x] UI page load <2 seconds

**Cost:**
- [x] Cost per 2000-page matter <$15 (target: $13-14)
- [x] LLM API costs monitored and optimized

**Memory System:**
- [x] Multi-turn conversations work (pronoun resolution)
- [x] Query history visible in UI (last 50 queries per matter)
- [x] Matter Memory survives session logout/restart
- [x] Timeline cache invalidates on document upload

**Safety:**
- [x] 0 legal conclusions escape language policing (100% sanitized)
- [x] Query guardrails block 95%+ dangerous questions
- [x] Attorney verification UI functional for all finding types
- [x] Audit trail complete (who verified what, when)

**User Acceptance:**
- [x] Juhi (Product Owner) approves UAT
- [x] All critical user flows tested and working
- [x] Training materials complete
- [x] Deployment successful

---

## Next Steps After MVP

**Immediate Post-MVP (Month 17-18):**
1. Collect user feedback (Juhi + 2-3 pilot attorneys)
2. Iterate on UX pain points
3. Performance optimization based on real usage
4. Bug fixes and stability improvements

**Phase 2 Trigger (Month 18-24):**
1. User creates manual process templates (SARFAESI, DRT, IBC)
2. Collect 10-20 real matters for template validation
3. Plan Phase 2 scope (3 advanced engines, full template engine, bounded computation)

---

**END OF MVP SCOPE DEFINITION v1.0**
