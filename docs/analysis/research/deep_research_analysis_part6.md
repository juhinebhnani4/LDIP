---
📋 **DOCUMENT STATUS: PHASE 2+ VISION - DEFERRED**
This document is part of the Deep Research vision (8 parts). See [deep_research_analysis_part1.md](./deep_research_analysis_part1.md) for full status information.
**For implementation, use:** [Requirements-Baseline-v1.0.md](../../../_bmad-output/project-planning-artifacts/Requirements-Baseline-v1.0.md)
---

6A — Interaction Principles & Safe Context Model (Contract Layer)

This part defines how users interact with the system, how context is handled, and how memory is safely scoped in a legal environment.

It ensures the tool is intuitive for junior associates, trustworthy for senior attorneys, and safe from confidentiality breaches.

6.1 Guiding Principles for User Interaction
LDIP’s user interaction must:

Never assume or invent legal conclusions

Maintain matter isolation for every query

Provide transparent, reproducible outputs

Tell users why an answer could not be generated

Adapt the level of detail depending on who is asking

Allow follow-up questions while maintaining safety

Keep the experience simple despite complex internal reasoning

LDIP should feel like:

“A highly organized, calm senior researcher assisting you—
never guessing, never overconfident, always showing evidence.”

6.2 Query Intake Pipeline (How Input Becomes Analysis)

Every user question follows a strict pipeline:

Step 1 — Authorization Check

Does the user have permission for this matter?

If not → Explain clearly that access is restricted.

Step 2 — Safety Classification

Using the Question Classifier from Part 3:

Factual Retrieval → allowed

Pattern or Timeline Analysis → allowed

Citation Verification → allowed

Legal Strategy / Legal Conclusion → blocked with alternatives

Privilege-sensitive questions → flagged / rerouted

Step 3 — Context Assembling

LDIP assembles only matter-specific context:

relevant documents

extracted facts

timelines

parties & roles

previously uploaded Acts

previously answered safe questions (within same session)

Step 4 — Retrieval (RAG)

Querying embeddings scoped to the current matter_id only

No cross-matter retrieval allowed unless explicit permission exists

Step 5 — Structured AI Reasoning

Using templates from Part 4:

Evidence extraction

Comparison

Neutral description of differences

Confidence scoring

Limitations report

Step 6 — Response Formatting

Answers are:

neutral

source-linked

explain reasoning

include safety disclaimers

6.3 Conversational Memory Model (Safe Memory)

Legal systems cannot use typical LLM “memory” because it risks leaking information across matters.

LDIP uses three layers of memory, each with strict limits:

A. Session Memory (Temporary)

Remembers follow-up context only within current session & current matter

Discarded when session ends

Cannot include privileged content unless user authorized to view

Used for:

follow-up questions

refining timelines

interacting with analysis results

B. Matter-Scoped Analytical Memory (Persistent but Isolated)

Stored inside that matter only, never visible to other matters or users lacking access.

Contains:

extracted events

chronological timelines

summary of parties & roles

structured citations

previously identified inconsistencies

document metadata

Matter Memory Files (File-Based Structured Storage)

LDIP uses a file-based memory organization inspired by Claude's memory tool architecture, combined with lightweight query summaries inspired by ChatGPT's efficient memory system.

File-Based Organization:

Matter memory stored in `/memories/{matter_id}/` directory structure

Client-side control: Law firms control storage location, encryption, and access policies

Files organized by type:
- `/memories/{matter_id}/recent_queries.xml` - Query summaries
- `/memories/{matter_id}/timeline_summary.xml` - Pre-computed timeline
- `/memories/{matter_id}/entity_mapping.xml` - Party/role summaries
- `/memories/{matter_id}/query_cache/` - Q&A cache entries

Automatic memory directory checking: System checks matter memory files before processing queries (similar to Claude's automatic memory directory checking)

Path traversal protection: All paths must be within `/memories/{matter_id}/` - strict validation prevents cross-matter access

Recent Queries Summary (Lightweight, Pre-Computed):

Format: Timestamp + query snippet + engine(s) used + key finding (one-line summary)

Storage: Last 15-20 queries per matter, stored in `/memories/{matter_id}/recent_queries.xml`

Retrieval: Injected into context alongside other matter data, not RAG-searched

Benefits over RAG:
- Token efficiency: Pre-computed summaries vs. embedding/search operations
- Speed: No embedding or similarity search overhead
- Continuity: Provides context across sessions within a matter
- Organization: File-based structure easier to manage and audit

Invalidation: When new documents added, privilege status changed, or matter identity graph updated

Isolation guarantees: Matter-scoped only, never cross-matter, never visible to unauthorized users

Example format:
```
<recent_queries>
  <query timestamp="2025-01-15T14:30:00Z">
    <question>What events relate to dematerialisation?</question>
    <engines>Timeline, Process Chain</engines>
    <key_finding>9-month delay detected vs typical 2-3 months</key_finding>
  </query>
  <query timestamp="2025-01-15T15:45:00Z">
    <question>Any contradictions in custodian statements?</question>
    <engines>Consistency</engines>
    <key_finding>Ownership claim inconsistency across documents</key_finding>
  </query>
</recent_queries>
```

This dramatically reduces cost because repeated questions reuse structured outputs, and the lightweight query summaries provide continuity without the computational overhead of full RAG retrieval across conversation history.

C. System-Wide Memory (Non-content, Safe-to-share)

Only stores general tools and reasoning strategies, NOT legal content.

Examples:

“if a timeline is missing dates, ask user whether to fill approximate ranges”

“citation verification requires both document text and official Act text”

“contradiction detection outputs are neutral, not interpretive”

This helps the system behave consistently without risking confidentiality.

6.3.1 Matter Memory Files: Implementation Details

The file-based memory system combines the organizational benefits of Claude's memory tool with the efficiency of ChatGPT's lightweight summaries.

Storage Architecture:

Directory structure: `/memories/{matter_id}/`
- Each matter has its own isolated directory
- All file operations restricted to matter directory
- Path validation prevents directory traversal attacks

File organization:
- `recent_queries.xml` - Lightweight query summaries (last 15-20)
- `timeline_summary.xml` - Pre-computed chronological timeline
- `entity_mapping.xml` - Party and role summaries
- `query_cache/` - Subdirectory for Q&A cache entries

Client-Side Control:

Storage location: Controlled by law firm infrastructure
- Can be local filesystem, encrypted storage, cloud storage, or database
- Firm controls encryption, access policies, and backup strategies
- No server-side storage of matter memory (unless firm chooses)

Security benefits:
- Path traversal protection: All paths validated to stay within matter directory
- File size limits: Prevent memory files from growing too large
- Memory expiration: Can implement policies to clear old memory files
- Access control: Firm controls who can read/write matter memory files

Query Summary Format:

Each query summary contains:
- Timestamp (ISO 8601 format)
- Query snippet (user's question, truncated if needed)
- Engine(s) used (comma-separated list)
- Key finding (one-line summary of result)

Storage limits:
- Maximum 15-20 queries per matter
- Oldest queries removed when limit reached (FIFO)
- Lightweight format keeps file size small

Retrieval Method:

Automatic memory directory checking: Before processing any query, LDIP automatically checks the matter's memory directory (similar to Claude's memory tool behavior). This ensures continuity is maintained without requiring explicit user action.

Automatic injection: Query summaries automatically included in context when:
- User starts new session within same matter (system checks memory directory first)
- User asks follow-up questions
- System needs continuity context
- Context editing clears tool results (memory files preserved as extension of context)

Not used for:
- RAG retrieval (never embedded or searched)
- Cross-matter access (strictly matter-scoped)
- Engine reasoning (only context, not evidence)

Invalidation Rules:

Memory files invalidated when:
- New documents added to matter
- Privilege classification of any document changes
- Matter Identity Graph updated
- Matter metadata modified

Cache entries MUST NOT be reused across matters or across privilege states.

Integration with Context Editing:

For long-running conversations, matter memory files work with context editing:
- System can preserve important information to memory files before clearing context
- Memory files act as extension of working context
- Enables complex, multi-step workflows without losing critical information

This approach trades detailed historical context for speed and efficiency, which is the right balance for most legal document analysis tasks. The system remembers what matters (recent queries, key findings, continuity) while staying fast and responsive.

Design Philosophy:

LDIP's Matter Memory Files combine the best of both ChatGPT's and Claude's memory approaches:

- **From ChatGPT**: Lightweight, pre-computed query summaries that provide continuity without RAG overhead. Token-efficient, fast, sufficient for most continuity needs.

- **From Claude**: File-based organization with client-side control. Structured storage, path validation, automatic directory checking. Better security and organization than flat summaries.

- **LDIP Enhancement**: Matter-scoped isolation ensures legal confidentiality. Each matter has its own memory directory, strict path validation prevents cross-matter access, and client-side control gives law firms complete control over storage and security.

The result is a memory system that is efficient (like ChatGPT), organized (like Claude), and secure (legal-grade isolation). This pragmatic approach prioritizes speed and security over detailed historical context, which is exactly what legal document analysis requires.

6.4 Limitations & Transparency Prompts

LDIP continually communicates limits:

When context is insufficient:

“I cannot determine Event X because no document in this matter references it.
If you have another document, please upload it.”

When access is not permitted:

“You do not have authorization to view the matter where this information exists.”

When documents are likely missing:

“Absence in uploaded documents does not mean the document does not exist.”

When a question is strategic:

“This requires legal judgment and cannot be answered.
Here are safe alternative factual questions…”

6.5 User Feedback & Correction Loop

Every answer can be rated:

Accurate

Incomplete

Incorrect extraction

Incorrect interpretation

Missing supporting documents

When a user provides corrections:

LDIP updates matter-scoped memory

Flags extraction logic for improvement

Does not update model-level memory (no risk of contamination)

6.6 UX Requirements for MVP
The MVP must support:
1. Simple Upload → Ask → Answer Flow

Upload documents

Run privilege scan

Assign to matter

Ask factual questions

View results with citations

2. Clean, reliable interface

Clear "Matter: X" indicator

Clear “Document Sources” section

“Show evidence” button

“Explain reasoning” section

Filter answers by Act, party, or timeline

3. Reproducible Reports

Every answer must include:

query ID

timestamp

sources

confidence score

limitations

reproducibility instructions

4. Guided Questioning

LDIP should gently guide users away from unsafe questions and toward structured factual prompts.

6.7 Multi-User, Multi-Matter Interaction

The system must support:

junior associates working on multiple matters

partners reviewing output

paralegals uploading and tagging documents

With strict guarantees:

users only see matters they’re assigned

session memory resets when switching matters

search and retrieval automatically scoped

6.8 How Part 6 Enables Bounded Adaptive Computation (Part 8)

This part lays the foundation for bounded adaptive computation:

Matter-scoped memory → enables state continuity across bounded loops

Session context → enables deterministic multi-step query planning

Structured pipeline → enables deterministic tool orchestration

Query classification → prevents unsafe queries

Reproducible output → enables supervisory review of bounded loop execution

Nothing here will break when you later add:

bounded iterative workflows

automated timeline construction

cross-case analytics (on public judgments)

background monitors (e.g., detect new contradictions)

6B — Applied User Experience & Workflow Design (Implementation Layer)

6.1 Goals of the Interaction Model

The LDIP interface must enable lawyers to:

Ask questions freely without risk of hallucinations

Navigate large volumes of documents effectively

Build understanding over time

Maintain continuity across days or weeks

Capture personal insights without contaminating the system

Always know what evidence supports an answer

Keep privileged, strategic, or personal notes safely separated

The design must feel natural for:

junior associates doing research

senior partners verifying findings

clients consuming high-level summaries

paralegals preparing files

6.2 Core User Actions

Users must be able to:

1. Ask a Question

Freeform natural language

System classifies into timeline, consistency, process chain, pattern analysis, etc.

Evidence-bound answer returned

Citations mandatory

2. Explore Documents

Document list

Page-level viewer

OCR text

Highlighted citations where relevant

3. Review Structured Outputs

Timelines

Contradictions

Process chain comparisons

Citation accuracy reports

4. Save Insights to Personal Research Journal (New)

System automatically offers to save every analysis

User can attach private notes

These notes do NOT enter retrieval or reasoning

Notes never visible to other team members unless explicitly shared

5. Track Progress

View “what analyses have been run so far”

Re-run engines when new documents are uploaded

See superseded or stale results

6. Export Reports

Generate:

evidence packs

contradiction summaries

issue lists

case synopsis

Reports are safe, evidence-bound, and compliant with privilege rules.

6.3 The Interaction Loop (End-to-End UX)

Below is the actual experience a junior lawyer will have.

STEP 1 — Begin in a Matter Workspace

When the user selects Matter X, LDIP loads:

all documents

all precomputed summaries

act sections

existing analyses

the user’s private Research Journal for this matter

UI elements:

Left: document tree

Center: chat/analysis panel

Right: timeline, entities, journal

Everything shown is strictly scoped to Matter X.

STEP 2 — Ask a Question

Examples:

“Show me all contradictions between custodian statements.”
“What events relate to dematerialisation requests?”
“Was Nirav’s sale of shares before or after he was notified as benami?”
“Build the process chain for physical-to-demat conversion and compare it to the Act.”

User does NOT need to specify the engine.

LDIP does:

Safety classification

Authorization check

Reasoning mode selection

If unsafe or cross-matter → gives Part 4.9 fallback template.

STEP 3 — LDIP Performs the Analysis

LDIP executes the pipeline defined in Part 4:

retrieval

evidence pack construction

engine reasoning

safety filtering

post-processing

Output appears with:

Facts found

Citations

Missing information

Confidence score

Limitations

Documents considered

UI automatically highlights cited text inside documents.

STEP 4 — User Accepts or Rejects Journal Logging

Each result appears with:

“Save to Research Journal?”

If accepted:

system stores:

the question

the factual answer

citations

engine used

timestamps

notes (optional)

Journal entries become:

a chronological research log

a map of what the lawyer has explored

a detachable asset for future reasoning steps (but NOT training data)

If rejected:

no journal entry created

question stays ephemeral

STEP 5 — Add Personal Notes (Optional)

The user can write:

“This contradiction might help us in the appeal.”
“Mehta’s affidavit conflicts with Order dated 2003.”
“Ask senior if this timeline gap is relevant.”

These notes:

are private

are NOT used in RAG

are NOT visible to seniors unless shared

do NOT count as evidence

are stored encrypted

This solves the “I need my own thought process saved” problem with zero risk.

STEP 6 — Returning Tomorrow / Next Week

When the same user comes back:

They do NOT rely on LLM session memory

LDIP reconstructs context from:

their Research Journal

previous outputs

cached timelines/analyses per matter

This gives perfect continuity with zero cross-session leakage.

LDIP can say:

“Last time you worked on this matter, you were investigating dematerialisation timelines. Would you like to continue?”

This is based on journal entries, not LLM memory.

STEP 7 — Senior Review

Senior lawyers may:

See structured outputs

Run their own queries

View any journal entries marked “shared with team”

Leave comments (optional)

Export evidence reports

They cannot:

view private notes

access personal logs of other lawyers

access unauthorized matters

6.4 Research Journal Design (Critical UX Component)
Purpose

To give lawyers continuity, personal workspace, and progressive understanding without polluting model reasoning.

What Gets Stored

questions asked

factual outputs

citations

engine used

timestamps

optional personal notes

What NEVER Gets Stored

hallucinations

privileged content the user types manually

legal judgments or strategies

data from other matters

content from blocked/privileged files

What the AI Can Use

ONLY the factual outputs saved (timelines, contradictions, etc.)

NOT personal notes

NOT strategic thinking

This keeps the AI neutral and clean.

6.5 Multi-User Collaboration Rules
MatterLead

can view all system outputs

cannot access personal journals

may access shared journal entries

Team Sharing

Users may explicitly share a journal entry:

with team

with MatterLead

with FirmAdmin

Shares must be logged.

Defaults

All journal entries are private unless shared.

6.6 Avoiding Hallucinations & Unsafe Behavior in UX

The UI MUST enforce:

Evidence snippets visible inline

Warnings when evidence is missing

Model disclaimers always visible

No summaries without citations

Buttons to “Open in Source Document”

Clear error messages for cross-matter attempts

Examples:

⚠️ “This answer is based on low-confidence OCR for pages 17–20.”

⛔ “Cross-matter comparison requires authorization.”

6.7 Interaction with Bounded Adaptive Computation (Future Proofing)

When Option 3 (bounded adaptive computation) is added:

UX remains the same

Under the hood, multiple engines are orchestrated via bounded loops and deterministic planning

User still sees ONE unified output

Journal captures which engines were used

Example UI metadata:

Engines Used: Timeline + ProcessChain + Citation + Pattern
Evidence Sources: Docs 12, 13, 25, 41

Nothing becomes more complex for the user.

6.8 What the System Must Prevent

The UX must make it impossible to:

add privileged content into the model by accident

leak matter info into another matter

reveal journal entries to the wrong users

store final opinions as facts

accidentally reuse another lawyer’s private notes

see stale results without warnings

view sensitive outputs with missing citations

6.9 Summary of UX Philosophy
🔹 Transparent

Users always see how an answer was produced.

🔹 Evidence-first

Citations are the default view, not hidden.

🔹 Safe-by-design

Hard stops on unsafe queries.

🔹 Personal continuity

Research Journal provides long-term memory without using model memory.

🔹 Collaborative

Team sharing built on explicit user control.

🔹 Future-proof

Seamless path from Option 2 to Option 3 without changing UX.

### MIG Update Rules (MVP)

- MIG updates occur only via explicit Orchestrator-approved actions.
- Automatic entity merges are disabled for MVP.
- Each MIG update records:
  - previous state reference
  - new state
  - actor (user or system)
  - timestamp

6.10 Attorney Training & Usage Guidelines

6.10.1 Training Modules

**Content:**
1. **System Overview:** What LDIP does and doesn't do
   - LDIP provides factual patterns, not legal conclusions
   - Evidence-first architecture (all claims tied to document, page, line)
   - Neutral fact extraction (no legal advice)
   - Attorney remains the decision-maker

2. **Matter Management:** Creating matters, uploading documents
   - Matter creation workflow
   - Document upload process
   - Conflict checking explained
   - Privilege detection and handling

3. **Query Techniques:** How to ask effective questions
   - Factual retrieval queries
   - Pattern analysis queries
   - Timeline construction queries
   - What questions are blocked and why

4. **Interpreting Results:** Understanding confidence scores, citations
   - Confidence levels (High/Medium/Low)
   - How to verify citations
   - Understanding evidence links
   - When to trust findings vs. when to verify

5. **Safety Guidelines:** Privilege protection, conflict checking
   - Matter isolation principles
   - Privilege detection and override
   - Conflict checking workflow
   - Ethical wall enforcement

6. **Common Mistakes:** What to avoid
   - Over-relying on AI findings without verification
   - Ignoring confidence scores
   - Not verifying citations
   - Misinterpreting neutral language as legal conclusions

**Delivery:**
- **Interactive Tutorial:** Step-by-step walkthrough in system
- **Video Guides:** Short videos for each feature
- **Documentation:** Comprehensive user guide
- **Practice Matters:** Sample matters for training

6.10.2 Usage Guidelines

**For Junior Associates:**
- **Supervised Mode:** Require senior attorney approval for certain queries
- **Clear Limitations:** Emphasize system is assistant, not replacement
- **Citation Requirements:** Always verify citations before using findings
- **Confidence Thresholds:** Only use high-confidence findings without review
- **Evidence Verification:** Always verify critical findings before using in legal work

**For All Users:**
- **Neutral Language Reminder:** System provides facts, attorney makes conclusions
- **Evidence Verification:** Always verify critical findings
- **Privilege Awareness:** Understand privilege detection and manual review
- **Conflict Checking:** Understand matter isolation and conflict prevention
- **Trust Building:** Start with low-risk use cases, build confidence over time

6.10.3 Building Trust in AI Outputs

**Key Trust-Building Features:**
1. **Evidence-Bound Design:** Every finding has citations (document, page, line)
2. **Confidence Scoring:** Clear confidence levels with attorney-configurable thresholds
3. **Neutral Language:** System doesn't make legal conclusions
4. **Explainability:** Show reasoning chains, visualize evidence links
5. **Gradual Adoption:** Start with low-risk use cases, allow verification

**Metrics to Track:**
- Accuracy rate vs senior lawyer review (target: 80%+)
- False positive rate (target: <5%)
- False negative rate (target: <10%)
- Citation accuracy (target: 100%)

6.10.4 Ensuring Critical Findings Aren't Overlooked

**Prioritization:**
- Findings ranked by severity (Critical/High/Medium/Low)
- Critical findings highlighted at top of report
- Visual indicators (red flags, icons)

**Summary Dashboard:**
- Executive summary of all critical findings
- One-page overview before detailed report
- Quick access to critical items

**Notification System:**
- Email/SMS alerts for critical findings
- In-app notifications
- Escalation to senior attorney if junior associate doesn't acknowledge

**Review Workflow:**
- Require attorney acknowledgment for critical findings
- Track which findings have been reviewed
- Remind attorneys of unacknowledged critical findings

**Implementation Priority:** MVP (Basic training) → Phase 2 (Comprehensive)

✔️ End of PART 6