# LDIP Test Cases - Comprehensive Test Suite

## Overview

This document defines test cases for all critical decision points and system components in LDIP. Tests are organized by component and priority.

---

## Test Category 1: Matter Isolation & Conflict Checking

### Test 1.1: Matter Creation with Conflict Detection
**Priority:** Critical  
**Component:** Matter Management, Conflict Checking

**Test Steps:**
1. Create Matter A with parties: ["Client X", "Opposing Party Y"]
2. Create Matter B with parties: ["Client X", "Opposing Party Z"]
3. Attempt to create Matter C with parties: ["Opposing Party Y", "Opposing Party Z"]
4. System should detect conflict (Opposing Party Y appears in Matter A)

**Expected Results:**
- Matter A created successfully
- Matter B created successfully (different opposing party, no conflict)
- Matter C creation BLOCKED with conflict warning
- Conflict check completes in <5 seconds (pre-check)
- Background deep check completes within 10 minutes

**Success Criteria:**
- ✅ Zero false negatives (conflicts always detected)
- ✅ <1% false positives (minimal false conflict warnings)
- ✅ Fast pre-check: <5 seconds
- ✅ Background check: <10 minutes

---

### Test 1.2: Cross-Matter Data Leakage Prevention
**Priority:** Critical  
**Component:** Matter Isolation, RAG System

**Test Steps:**
1. Create Matter A with documents about "Nirav Jobalia"
2. Create Matter B with documents about "Kalpana Jobalia"
3. Query Matter A: "Find all mentions of Jobalia"
4. Query Matter B: "Find all mentions of Jobalia"
5. Attempt cross-matter query without authorization

**Expected Results:**
- Matter A query returns only Matter A documents
- Matter B query returns only Matter B documents
- Cross-matter query rejected with authorization required message
- Zero documents from Matter B appear in Matter A results

**Success Criteria:**
- ✅ 100% isolation (zero cross-matter data in results)
- ✅ Authorization gates enforced
- ✅ Clear error messages for unauthorized requests

---

### Test 1.3: Background Conflict Detection
**Priority:** High  
**Component:** Conflict Checking, Background Jobs

**Test Steps:**
1. Create Matter A
2. Upload 50 documents to Matter A
3. Create Matter B with conflicting parties
4. Upload new document to Matter A that mentions Matter B parties
5. Background job should detect conflict

**Expected Results:**
- Matter A created successfully
- Documents uploaded successfully
- New document upload triggers background check
- Conflict detected within 10 minutes
- Matter A status changes to "FROZEN_CONFLICT"
- Alert sent to MatterLead

**Success Criteria:**
- ✅ Background check detects conflicts: 95%+ accuracy
- ✅ Alert sent within 10 minutes
- ✅ Matter frozen automatically
- ✅ No false freezes

---

## Test Category 2: Pre-Linking Engine

### Test 2.1: Entity Extraction Accuracy
**Priority:** Critical  
**Component:** Pre-Linking Engine

**Test Steps:**
1. Upload document: "Nirav D. Jobalia submitted request. N.D. Jobalia was notified."
2. Pre-linking engine processes document
3. Check MIG for entity nodes

**Expected Results:**
- Entity "Nirav D. Jobalia" extracted
- Entity "N.D. Jobalia" extracted
- ALIAS_OF edge created between entities
- Both entities linked to same document

**Success Criteria:**
- ✅ Entity extraction: 90%+ accuracy for obvious entities
- ✅ Alias detection: 85%+ accuracy for obvious aliases
- ✅ Zero false entity creation

---

### Test 2.2: Event Extraction and Timeline
**Priority:** High  
**Component:** Pre-Linking Engine, Timeline Engine

**Test Steps:**
1. Upload document with dates: "2020-05-01: Request submitted. 2020-06-15: Notification sent."
2. Pre-linking extracts events
3. Timeline engine reconstructs chronology

**Expected Results:**
- Event 1: "request_submitted" on 2020-05-01
- Event 2: "notification_sent" on 2020-06-15
- Timeline shows correct chronological order
- Events linked to entities mentioned

**Success Criteria:**
- ✅ Date extraction: 95%+ accuracy
- ✅ Event type classification: 90%+ accuracy
- ✅ Timeline ordering: 100% accuracy
- ✅ Entity-event linking: 85%+ accuracy

---

### Test 2.3: Citation Extraction
**Priority:** High  
**Component:** Pre-Linking Engine, Citation Engine

**Test Steps:**
1. Upload document: "As per Torts Act Section 15, notification is required."
2. Pre-linking extracts citation
3. Citation engine verifies against Act

**Expected Results:**
- Citation extracted: Act="Torts Act", Section="15"
- Citation linked to document and page
- Citation engine retrieves actual Act text
- Verification: Citation is accurate

**Success Criteria:**
- ✅ Citation extraction: 95%+ accuracy
- ✅ Act text retrieval: 100% accuracy
- ✅ Citation verification: 90%+ accuracy

---

## Test Category 3: Analysis Engines

### Test 3.1: Timeline Engine - Gap Detection
**Priority:** High  
**Component:** Timeline Engine

**Test Steps:**
1. Upload documents with events:
   - 2020-05-01: Request submitted
   - 2020-12-15: Notification sent (7.5 month gap)
2. Timeline engine processes events
3. Check for gap detection

**Expected Results:**
- Timeline shows chronological order
- Gap detected: "7.5 months between request and notification"
- Gap flagged as anomaly (if baseline indicates typical 2-3 months)
- Evidence citations provided

**Success Criteria:**
- ✅ Gap detection: 90%+ accuracy
- ✅ Baseline comparison: 85%+ accuracy (if baselines available)
- ✅ All gaps have evidence citations

---

### Test 3.2: Process Chain Engine - Missing Steps
**Priority:** Critical  
**Component:** Process Chain Engine

**Test Steps:**
1. Upload documents showing dematerialisation process
2. Documents show: Request → Approval → Transfer
3. Act requires: Request → Verification → Approval → Notification → Transfer
4. Process chain engine compares

**Expected Results:**
- Expected chain: 5 steps (from Act)
- Observed chain: 3 steps (from documents)
- Missing steps identified: "Verification" and "Notification"
- Evidence citations for each step

**Success Criteria:**
- ✅ Missing step detection: 85%+ accuracy
- ✅ Step ordering detection: 90%+ accuracy
- ✅ All findings have Act references

---

### Test 3.3: Consistency Engine - Contradiction Detection
**Priority:** High  
**Component:** Consistency Engine, MIG

**Test Steps:**
1. Upload Document A: "Nirav Jobalia owns these shares"
2. Upload Document B: "Mehta family owns these shares"
3. MIG resolves "Nirav Jobalia" and "Mehta family" as different entities
4. Consistency engine detects contradiction

**Expected Results:**
- Contradiction detected: Ownership claim conflict
- Statement A: Document A, page X, "Nirav Jobalia owns..."
- Statement B: Document B, page Y, "Mehta family owns..."
- Conflict type: "factual" (ownership)
- Evidence citations for both statements

**Success Criteria:**
- ✅ Contradiction detection: 80%+ accuracy
- ✅ Entity resolution: 90%+ accuracy (using MIG)
- ✅ All contradictions have evidence citations

---

### Test 3.4: Citation Engine - Misquotation Detection
**Priority:** High  
**Component:** Citation Engine

**Test Steps:**
1. Upload document: "Torts Act Section 15 states: 'Notification must be sent within 30 days'"
2. Actual Act text: "Notification must be sent within 60 days"
3. Citation engine verifies

**Expected Results:**
- Citation extracted: Act="Torts Act", Section="15"
- Actual Act text retrieved
- Misquotation detected: "30 days" vs "60 days"
- Similarity score calculated
- Evidence: Document text vs Act text comparison

**Success Criteria:**
- ✅ Misquotation detection: 95%+ accuracy
- ✅ Omitted proviso detection: 90%+ accuracy
- ✅ All verifications have Act text citations

---

## Test Category 4: Pattern Context (Phase 2)

### Test 4.1: Same-Client Pattern Comparison
**Priority:** High  
**Component:** Pattern Context System, Authorization

**Test Steps:**
1. Create Matter A (Client X vs Party A) - timeline anomaly: 9 months
2. Create Matter B (Client X vs Party B) - timeline anomaly: 8 months
3. Request pattern comparison: Matter A + Matter B
4. System checks authorization
5. Pattern comparison executed

**Expected Results:**
- Authorization check: Both matters for same client ✅
- Adverse check: Matters not adverse ✅
- Pattern comparison: "Similar timeline anomalies detected in 2 matters"
- Evidence: Citations from both matters
- Query logged for audit

**Success Criteria:**
- ✅ Authorization enforced: 100%
- ✅ Adverse check: 100% accuracy
- ✅ Pattern comparison: 85%+ accuracy
- ✅ All queries logged

---

### Test 4.2: Cross-Matter Identity Resolution
**Priority:** Medium  
**Component:** Entity Matching Service

**Test Steps:**
1. Matter A has entity: "Nirav D. Jobalia"
2. Matter B has entity: "N.D. Jobalia"
3. Request pattern comparison: Matter A + Matter B
4. Entity matching service runs
5. Lawyer approves match
6. Match cached

**Expected Results:**
- Query-time matching finds candidate: "Nirav D. Jobalia" ≈ "N.D. Jobalia"
- Confidence score: 0.92
- Lawyer reviews and approves
- Match cached for future queries
- Future queries use cached match (faster)

**Success Criteria:**
- ✅ Matching accuracy: 85%+ for obvious matches
- ✅ Approval workflow: <30 seconds
- ✅ Cache reduces query time: 50%+ improvement
- ✅ All matches logged

---

## Test Category 5: Research Journal

### Test 5.1: Journal Isolation
**Priority:** Critical  
**Component:** Research Journal, RAG System

**Test Steps:**
1. Create journal entry in Matter A
2. Query Matter A: "What did I research last time?"
3. Query Matter B: "What did I research last time?"
4. Attempt RAG query that might retrieve journal entries

**Expected Results:**
- Journal entry visible in Matter A journal
- Journal entry NOT visible in Matter B journal
- Matter A query can reference journal (for UX continuity)
- Matter B query shows no journal entries
- RAG query does NOT retrieve journal entries

**Success Criteria:**
- ✅ 100% journal isolation (zero cross-matter visibility)
- ✅ Zero journal entries in RAG retrieval
- ✅ Journal entries encrypted at rest

---

### Test 5.2: Journal Auto-Save
**Priority:** Medium  
**Component:** Research Journal, Orchestrator

**Test Steps:**
1. Run analysis query in Matter A
2. System offers: "Save to Research Journal?"
3. User accepts
4. Check journal entry created

**Expected Results:**
- Journal entry created with:
  - Question asked
  - Structured answer
  - Citations
  - Engine used
  - Timestamp
- Entry visible in Matter A journal
- Entry NOT used in future RAG queries

**Success Criteria:**
- ✅ Journal entry created: <1 second
- ✅ All required fields populated
- ✅ Zero journal entries in RAG

---

## Test Category 6: Security & Compliance

### Test 6.1: Privilege Detection
**Priority:** Critical  
**Component:** Privilege Detection, Document Processing

**Test Steps:**
1. Upload document with "ATTORNEY-CLIENT PRIVILEGE" header
2. System scans for privilege markers
3. Document classified as HIGH privilege
4. Attempt to analyze document

**Expected Results:**
- Document classified: HIGH privilege
- Document stored but not indexed
- Analysis query blocked: "Document requires privilege override"
- MatterLead can approve override
- Override logged with justification

**Success Criteria:**
- ✅ Privilege detection: 90%+ accuracy
- ✅ HIGH privilege documents blocked: 100%
- ✅ All overrides logged

---

### Test 6.2: Authorization Enforcement
**Priority:** Critical  
**Component:** Authentication, Authorization

**Test Steps:**
1. User A has access to Matter A only
2. User A attempts to query Matter B
3. User A attempts to access User B's journal
4. System enforces authorization

**Expected Results:**
- Matter B query rejected: "Access denied"
- User B's journal access rejected: "Access denied"
- All unauthorized attempts logged
- Clear error messages provided

**Success Criteria:**
- ✅ Authorization enforced: 100%
- ✅ Zero unauthorized access
- ✅ All attempts logged

---

### Test 6.3: Audit Trail Completeness
**Priority:** High  
**Component:** Audit Logging

**Test Steps:**
1. Perform various operations:
   - Create matter
   - Upload documents
   - Run analysis
   - Access journal
   - Cross-matter query (authorized)
2. Check audit logs

**Expected Results:**
- All operations logged with:
  - User ID
  - Matter ID
  - Operation type
  - Timestamp
  - Result (success/failure)
- Logs are append-only
- Logs are tamper-evident

**Success Criteria:**
- ✅ 100% operation coverage
- ✅ Logs immutable (append-only)
- ✅ Logs retained per policy (10 years default)

---

## Test Category 7: Performance & Scalability

### Test 7.1: Bulk Upload Performance
**Priority:** High  
**Component:** Document Upload, Pre-Linking

**Test Steps:**
1. Upload 100 documents (5000 pages total) to Matter A
2. Measure upload time
3. Measure pre-linking time
4. Check system responsiveness

**Expected Results:**
- Upload completes: <10 minutes
- Pre-linking completes: <30 minutes
- System remains responsive during processing
- No errors or timeouts

**Success Criteria:**
- ✅ Upload: <10 minutes for 100 documents
- ✅ Pre-linking: <30 minutes for 5000 pages
- ✅ System uptime: 95%+ during processing

---

### Test 7.2: Query Performance
**Priority:** High  
**Component:** RAG System, Engines

**Test Steps:**
1. Matter A has 100 documents processed
2. Run timeline query
3. Run process chain query
4. Run consistency query
5. Measure response times

**Expected Results:**
- Timeline query: <2 minutes
- Process chain query: <3 minutes
- Consistency query: <3 minutes
- Results are accurate and complete

**Success Criteria:**
- ✅ Query response: <5 minutes (MVP target)
- ✅ Results accuracy: 80%+ (MVP target)
- ✅ System handles 50+ concurrent users

---

### Test 7.3: Cache Effectiveness
**Priority:** Medium  
**Component:** Caching System

**Test Steps:**
1. Run timeline query (first time)
2. Run same timeline query (second time)
3. Compare response times
4. Check cache hit rate

**Expected Results:**
- First query: Full computation, <3 minutes
- Second query: Cache hit, <5 seconds
- Cache hit rate: 70%+ for repeated queries
- Cache invalidation works when new documents added

**Success Criteria:**
- ✅ Cache hit: <5 seconds
- ✅ Cache hit rate: 70%+ for common queries
- ✅ Cache invalidation: 100% accuracy

---

## Test Category 8: Bounded Adaptive Computation (Phase 2)

### Test 8.1: Stop Condition Enforcement
**Priority:** Critical  
**Component:** Bounded Loop Executor

**Test Steps:**
1. Request multi-hop connection discovery
2. Set stop conditions: max 5 iterations, 30 seconds
3. Execute loop
4. Verify stop conditions enforced

**Expected Results:**
- Loop stops at iteration 5 (max reached) OR
- Loop stops at 30 seconds (time limit) OR
- Loop stops when no new findings (threshold reached)
- Partial results returned
- Stop reason logged

**Success Criteria:**
- ✅ Stop conditions enforced: 100%
- ✅ No loops exceed limits
- ✅ All stop reasons logged

---

### Test 8.2: Iteration Traceability
**Priority:** High  
**Component:** Bounded Loop Executor, Audit Logging

**Test Steps:**
1. Execute bounded loop (connection discovery)
2. Loop runs 3 iterations before stopping
3. Request iteration log
4. Verify full traceability

**Expected Results:**
- Iteration 1: Actions logged, findings recorded
- Iteration 2: Actions logged, findings recorded
- Iteration 3: Actions logged, findings recorded, stop triggered
- Full log available for replay
- Stop reason: "No new findings"

**Success Criteria:**
- ✅ All iterations logged: 100%
- ✅ Logs are replayable
- ✅ Stop reasons accurate

---

## Test Category 11: Stress Test Scenarios

### Test 11.1: Legal & Ethical Safety (Language Policing)
**Priority:** Critical  
**Component:** Language Policing Service

**Test Steps:**
1. Generate finding that would naturally use blocked language
2. System should detect and block/rewrite
3. Verify mandatory suffix is added
4. Check that no legal conclusion language appears

**Expected Results:**
- Blocked words ("violates", "illegal", "liable", "guilty") are caught
- Output rewritten to neutral language
- Mandatory suffix: "This is a factual signal requiring attorney review."
- No legal conclusion language in final output

**Success Criteria:**
- ✅ 100% of blocked words caught
- ✅ All outputs include mandatory suffix
- ✅ Zero legal conclusion language in outputs

---

### Test 11.2: Judicial Scrutiny (Explainability)
**Priority:** Critical  
**Component:** Explainability Mode

**Test Steps:**
1. Generate finding with explainability mode enabled
2. Verify all required components present:
   - Exact text
   - Exact location (document, page, paragraph/line)
   - Why flagged
   - What rule/template triggered
3. Test with missing components → should downgrade to low confidence

**Expected Results:**
- Every finding shows complete reasoning chain
- Missing components trigger low confidence downgrade
- All findings are courtroom-defensible

**Success Criteria:**
- ✅ 100% of findings have complete explainability data
- ✅ Missing components trigger appropriate downgrade
- ✅ All findings defensible in court

---

### Test 11.3: Indian Pleading Reality (Boilerplate Tolerance)
**Priority:** High  
**Component:** Admissions Detector, Consistency Engine

**Test Steps:**
1. Upload documents with boilerplate denials
2. Upload copy-paste affidavits
3. Test admissions detection on boilerplate language
4. Verify confidence calibration

**Expected Results:**
- Boilerplate phrases recognized
- Confidence lowered for copied text
- Graceful degradation, not aggressive flagging
- "Possible admission (low confidence – boilerplate denial pattern detected)"

**Success Criteria:**
- ✅ Boilerplate patterns recognized
- ✅ Confidence appropriately lowered
- ✅ No false positives from standard Indian drafting

---

### Test 11.4: Bad Junior Lawyer Misuse (Watermark/Export)
**Priority:** Critical  
**Component:** Junior Case Note Generator, Export System

**Test Steps:**
1. Generate junior case note
2. Attempt to export without acknowledgement
3. Verify watermark appears
4. Test copy-paste restrictions

**Expected Results:**
- Watermark: "NOT FOR FILING. INTERNAL REVIEW ONLY."
- Export requires explicit acknowledgement
- Copy-paste of conclusions disabled
- Disclaimer present: "This is a factual extraction, not legal advice."

**Success Criteria:**
- ✅ 100% of exports have watermark
- ✅ Acknowledgement required for export
- ✅ Copy-paste restrictions enforced

---

### Test 11.5: Overconfident Senior Advocate (Override/Dismiss)
**Priority:** Medium  
**Component:** Attorney Verification Workflow

**Test Steps:**
1. Senior dismisses finding with reason
2. Verify system doesn't learn from override
3. Verify override logged for audit
4. Test that system doesn't argue back

**Expected Results:**
- Override accepted with reason
- No automatic learning from overrides
- Override logged with reviewer identity
- System accepts dismissal without argument

**Success Criteria:**
- ✅ Overrides logged correctly
- ✅ No automatic learning from overrides
- ✅ System accepts dismissals gracefully

---

### Test 11.6: Factual Ambiguity (Three-State Logic)
**Priority:** High  
**Component:** All Engines

**Test Steps:**
1. Test with missing documents
2. Test with ambiguous evidence
3. Verify three-state logic used:
   - Present
   - Explicitly absent
   - Not determinable from record
4. Verify never uses "likely", "must have", "implies intent"

**Expected Results:**
- Only three states used
- Never guesses or infers
- Uncertainty clearly stated
- No implied conclusions

**Success Criteria:**
- ✅ 100% compliance with three-state logic
- ✅ Zero use of forbidden inference language
- ✅ Uncertainty always clearly stated

---

### Test 11.7: Cross-Matter Contamination (Matter Isolation)
**Priority:** Critical  
**Component:** Matter Isolation, Process Templates

**Test Steps:**
1. Create Matter A and Matter B
2. Use process templates in Matter A
3. Verify Matter B doesn't see Matter A data
4. Verify comparison labels say "Based on statutory expectation" not "Based on other matters"

**Expected Results:**
- Strict matter isolation maintained
- Templates labeled as statutory, not cross-matter
- No data leakage between matters

**Success Criteria:**
- ✅ Zero cross-matter data leakage
- ✅ All comparisons properly labeled
- ✅ Matter isolation enforced

---

### Test 11.8: Document Fabrication Claims (Neutral Language)
**Priority:** High  
**Component:** Document Authenticity Checks

**Test Steps:**
1. Flag document with inconsistent formatting
2. Verify language is neutral
3. Verify "No conclusion drawn" suffix
4. Test that no intent is assigned

**Expected Results:**
- "Inconsistent formatting" not "forged"
- "Signature style differs" not "fake signature"
- Always ends with "No conclusion drawn."
- No intent or motive assigned

**Success Criteria:**
- ✅ 100% neutral language
- ✅ No intent/motive language
- ✅ "No conclusion drawn" always present

---

### Test 11.9: Regulatory/Bar Council Review (Defensibility)
**Priority:** Critical  
**Component:** All Systems

**Test Steps:**
1. Generate comprehensive system report
2. Verify no legal advice
3. Verify no strategy suggestions
4. Verify no outcome predictions
5. Verify evidence-only approach
6. Verify attorney-in-loop workflow

**Expected Results:**
- System report shows evidence-only approach
- No legal advice anywhere
- Attorney verification workflow documented
- Full audit trail available

**Success Criteria:**
- ✅ Defensible as forensic reading assistant
- ✅ Zero legal advice
- ✅ Complete audit trail

---

### Test 11.10: Product Trust & Adoption (Signal-to-Noise)
**Priority:** Medium  
**Component:** Risk Register, Signal Ranking

**Test Steps:**
1. Generate findings with various severity levels
2. Verify signal ranking (Critical/Review/Informational)
3. Test default view shows only Critical
4. Verify collapsible views for Review/Informational

**Expected Results:**
- Signals properly ranked
- Default view not overwhelming
- Collapsible sections for less critical items
- Signal-to-noise ratio controlled

**Success Criteria:**
- ✅ Signal ranking working correctly
- ✅ Default view shows only Critical
- ✅ User experience not overwhelming

---

## Test Category 12: New Engine Functionality

### Test 12.1: Admissions & Non-Denial Detector
**Priority:** High  
**Component:** Engine 7

**Test Steps:**
1. Upload documents with explicit admissions
2. Upload documents with partial admissions
3. Upload documents with "para denied for want of knowledge"
4. Upload documents with silent non-denials
5. Verify detection and confidence calibration

**Expected Results:**
- Explicit admissions detected (high confidence)
- Partial admissions detected (medium confidence)
- Boilerplate denials recognized (low confidence)
- Silent non-denials flagged

**Success Criteria:**
- ✅ 85%+ accuracy in admissions detection
- ✅ Confidence calibration appropriate
- ✅ Boilerplate patterns recognized

---

### Test 12.2: Pleading-vs-Document Mismatch Engine
**Priority:** High  
**Component:** Engine 8

**Test Steps:**
1. Upload pleading claiming X
2. Upload supporting document showing Y
3. Verify mismatch detected
4. Verify side-by-side comparison shown
5. Verify evidence binding complete

**Expected Results:**
- Mismatches detected
- Side-by-side comparison provided
- Exact text from both sources shown
- Evidence binding complete

**Success Criteria:**
- ✅ 80%+ accuracy in mismatch detection
- ✅ Complete evidence binding
- ✅ Clear side-by-side comparisons

---

### Test 12.3: Case Orientation Layer
**Priority:** High  
**Component:** Case Orientation System

**Test Steps:**
1. Upload order documents
2. Verify automatic extraction of:
   - Court & jurisdiction
   - Case type
   - Current stage
   - Last order
   - Next date
3. Test manual override

**Expected Results:**
- All orientation data extracted automatically
- Manual override available
- Always visible in UI
- Updates when new orders uploaded

**Success Criteria:**
- ✅ 90%+ accuracy in automatic extraction
- ✅ Manual override working
- ✅ UI always shows orientation

---

### Test 12.4: Operative Directions Extractor
**Priority:** High  
**Component:** Operative Directions System

**Test Steps:**
1. Upload latest order with directions
2. Verify directions extracted
3. Verify deadlines identified
4. Verify compliance tracking
5. Verify neutral language

**Expected Results:**
- Directions extracted correctly
- Deadlines identified
- Compliance status tracked
- Neutral language only

**Success Criteria:**
- ✅ 85%+ accuracy in direction extraction
- ✅ Compliance tracking working
- ✅ Neutral language enforced

---

### Test 12.5: Silence/Delay Intelligence
**Priority:** Medium  
**Component:** Engine 2 (Enhanced)

**Test Steps:**
1. Upload documents with unexplained delays
2. Upload documents with long gaps
3. Upload documents with missing responses
4. Verify three-state logic used
5. Verify no inference language

**Expected Results:**
- Delays detected
- Gaps identified
- Missing responses flagged
- Three-state logic used
- No "likely" or "must have" language

**Success Criteria:**
- ✅ Delays and gaps detected
- ✅ Three-state logic compliance
- ✅ No inference language

---

## Test Category 13: Query Guardrails

### Test 13.1: Query Blocking (Unsafe Queries)
**Priority:** Critical  
**Component:** Query Guardrails System

**Test Steps:**
1. Submit unsafe queries:
   - "Who is at fault?"
   - "Who is liable?"
   - "What should we argue?"
   - "Will we win this case?"
2. Verify queries are blocked
3. Verify appropriate error message

**Expected Results:**
- Unsafe queries blocked
- Clear error message explaining why
- Suggested safe alternatives provided

**Success Criteria:**
- ✅ 100% of unsafe queries blocked
- ✅ Clear error messages
- ✅ Safe alternatives suggested

---

### Test 13.2: Query Rewriting
**Priority:** High  
**Component:** Query Rewriting Service

**Test Steps:**
1. Submit queries needing rewriting:
   - "Who did wrong?" → "What actions were taken by each party?"
   - "Is this fraud?" → "What inconsistencies exist?"
2. Verify automatic rewriting
3. Verify explanation provided

**Expected Results:**
- Queries automatically rewritten
- Explanation of why rewritten
- Safe alternative provided

**Success Criteria:**
- ✅ 90%+ of rewrites appropriate
- ✅ Explanations clear
- ✅ Safe alternatives provided

---

### Test 13.3: Language Policing
**Priority:** Critical  
**Component:** Language Policing Service

**Test Steps:**
1. Generate outputs that would contain blocked words
2. Verify real-time blocking
3. Verify automatic rewrite
4. Verify mandatory suffix added

**Expected Results:**
- Blocked words caught in real-time
- Automatic rewrite triggered
- Mandatory suffix always present

**Success Criteria:**
- ✅ 100% of blocked words caught
- ✅ Automatic rewrite working
- ✅ Mandatory suffix always present

---

### Test 13.4: Soft Warnings
**Priority:** Medium  
**Component:** Query Guardrails System

**Test Steps:**
1. Submit borderline queries
2. Verify soft warnings provided
3. Verify query still processed
4. Verify warning logged

**Expected Results:**
- Soft warnings for borderline queries
- Queries still processed
- Warnings logged for audit

**Success Criteria:**
- ✅ Appropriate warnings provided
- ✅ Queries still processed
- ✅ Warnings logged

---

## Test Category 14: Junior Lawyer Workflows

### Test 14.1: Junior Case Note Generation
**Priority:** High  
**Component:** Junior Case Note Generator

**Test Steps:**
1. Generate case note for matter
2. Verify content: facts timeline, key documents, red flags, missing items
3. Verify disclaimer present
4. Verify watermark on export

**Expected Results:**
- Case note generated with all required sections
- Disclaimer: "This is a factual extraction, not legal advice."
- Watermark on export: "NOT FOR FILING. INTERNAL REVIEW ONLY."

**Success Criteria:**
- ✅ Case notes contain all required sections
- ✅ Disclaimer always present
- ✅ Watermark on all exports

---

### Test 14.2: Risk Register Population
**Priority:** High  
**Component:** Risk & Weakness Register

**Test Steps:**
1. Generate findings across all engines
2. Verify risk register populated
3. Verify signal ranking (Critical/Review/Informational)
4. Verify default view shows only Critical

**Expected Results:**
- Risk register populated from all engines
- Signals properly ranked
- Default view shows only Critical
- Review/Informational collapsible

**Success Criteria:**
- ✅ Risk register populated correctly
- ✅ Signal ranking working
- ✅ Default view appropriate

---

### Test 14.3: Watermark/Export Restrictions
**Priority:** Critical  
**Component:** Export System

**Test Steps:**
1. Attempt to export case note
2. Verify acknowledgement required
3. Verify watermark appears
4. Test copy-paste restrictions

**Expected Results:**
- Acknowledgement required before export
- Watermark on all exports
- Copy-paste of conclusions disabled

**Success Criteria:**
- ✅ Acknowledgement enforced
- ✅ Watermark always present
- ✅ Copy-paste restrictions working

---

### Test 14.4: Attorney Verification Workflow
**Priority:** High  
**Component:** Attorney Verification System

**Test Steps:**
1. Generate findings
2. Verify all marked as "Pending Verification"
3. Attorney marks as Accepted/Rejected/Needs follow-up/Dismissed
4. Verify logging with reviewer identity
5. Test bulk verification

**Expected Results:**
- All findings require verification
- Status tracking working
- Reviewer identity logged
- Bulk verification available

**Success Criteria:**
- ✅ All findings require verification
- ✅ Status tracking accurate
- ✅ Reviewer identity logged
- ✅ Bulk verification working

---

## Test Execution Strategy

### Test Phases

**Phase 1: Unit Tests (Continuous)**
- Run on every code commit
- Cover individual components
- Target: 80%+ code coverage

**Phase 2: Integration Tests (Daily)**
- Run end-to-end workflows
- Test component interactions
- Target: All critical paths covered

**Phase 3: Security Tests (Weekly)**
- Test matter isolation
- Test authorization
- Test privilege protection
- Target: Zero security breaches

**Phase 4: Performance Tests (Monthly)**
- Load testing
- Stress testing
- Scalability testing
- Target: Meet performance criteria

**Phase 5: User Acceptance Tests (Per Phase)**
- Real lawyers using system
- Real cases analyzed
- Feedback collected
- Target: 80%+ satisfaction

---

## Test Data Requirements

### Test Matter Sets
1. **Simple Matter:** 10 documents, 1 opposing party, clear timeline
2. **Complex Matter:** 100 documents, multiple parties, complex relationships
3. **Multi-Matter Set:** 5 matters, same client, different opposing parties
4. **Conflict Matter Set:** Matters with conflicting parties (for conflict testing)

### Test Documents
- Real court filings (anonymized)
- Documents with privilege markers
- Documents with various entity name formats
- Documents with timeline gaps
- Documents with process chain deviations
- Documents with contradictions

---

## Success Criteria Summary

### Critical Tests (Must Pass 100%)
- Matter isolation
- Conflict detection
- Privilege protection
- Authorization enforcement
- Stop condition enforcement

### High Priority Tests (Must Pass 95%+)
- Entity extraction
- Timeline accuracy
- Process chain detection
- Citation verification
- Pattern context accuracy

### Medium Priority Tests (Must Pass 85%+)
- Performance targets
- Cache effectiveness
- Journal functionality
- Identity resolution

---

## Conclusion

This comprehensive test suite ensures:
- ✅ All critical decision points validated
- ✅ Safety requirements met
- ✅ Performance targets achieved
- ✅ Real-world usability confirmed

Tests are designed to be:
- **Automated:** Where possible
- **Repeatable:** Consistent results
- **Comprehensive:** Cover all scenarios
- **Realistic:** Use real-world data

Regular test execution ensures system quality and safety throughout development and deployment.

