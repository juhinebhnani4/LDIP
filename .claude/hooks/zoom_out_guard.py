#!/usr/bin/env python3
"""
Claude Code hook — Zoom Out Guard for LDIP.

Two responsibilities:

1. UserPromptSubmit: every time the user submits a prompt, inject a brief
   reminder that Claude must zoom out (answer 4 questions in writing) before
   proposing or writing code. This is the universal habit.

2. PreToolUse on Edit/Write/NotebookEdit: if the file being edited sits inside
   the high-risk pipeline/worker/state surface, inject a much stronger reminder
   pointing at the architecture-guard skill and the four forbidden patterns.

This hook NEVER blocks. It only injects context. Blocking would be hostile and
would break legitimate work; the goal is to make the right choice the easy
choice by ensuring the rules are always loaded into context at the exact
moment they matter.

Reads JSON from stdin per the Claude Code hook protocol. Writes JSON to stdout
when context injection is needed; otherwise exits silently with code 0.

Cross-platform: pure stdlib, works on Windows/macOS/Linux. Requires `python`
on PATH.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Configuration: which files trigger the architecture-guard reminder
# --------------------------------------------------------------------------- #

# The hook covers TWO architectural surfaces with distinct forbidden-pattern
# catalogs:
#   - BACKEND_* tuples cover the Celery pipeline / worker fleet / state
#     machine (source of ARCH-001..007 in BUGS.md §0).
#   - FRONTEND_* tuples cover the matter workspace shell, responsive layout
#     system, skeleton layer, and presentation/format layer (source of
#     FE-ARCH-01..04 in BUGS.md §0).
# Both halves fire their own reminder text (BACKEND_ vs FRONTEND_
# ARCHITECTURE_GUARD_REMINDER). main() emits both when both apply.

# Substring matches against the absolute file_path (lowercased, forward slashes).
# A file is "backend high-risk" if any of these substrings appears in its path.
BACKEND_HIGH_RISK_PATH_FRAGMENTS = (
    # Document pipeline + worker tasks
    "backend/app/workers/tasks/document_tasks.py",
    "backend/app/workers/tasks/chunked_document_tasks.py",
    "backend/app/workers/tasks/pipeline_chains.py",
    "backend/app/workers/tasks/engine_tasks.py",
    "backend/app/workers/tasks/maintenance_tasks.py",
    "backend/app/workers/celery.py",
    # Admin retry / recovery / pipeline endpoints
    "backend/app/api/routes/admin/pipeline.py",
    "backend/app/api/routes/admin/operations.py",
    "backend/app/api/routes/documents.py",
    # Deployment topology
    "backend/railway.toml",
    "backend/start-worker.sh",
    # LLM client area (Gemini quota partitioning lives or should live here)
    "backend/app/services/llm/",
    "backend/app/engines/citation/",
    "backend/app/engines/contradiction/",
)

# Substring matches against the file content / proposed edit. Even outside the
# backend path set, an edit that mentions any of these symbols is touching the
# dangerous backend state machine and gets the backend architecture-guard reminder.
BACKEND_HIGH_RISK_SYMBOLS = (
    "_mark_job_completed",
    "create_post_ocr_chain",
    "_dispatch_post_entity_tasks",
    "_trigger_parallel_processing",
    "_release_pipeline_lock",
    "finalize_chunked_document",
    "process_document_chunked",
    "documents.status",
    "processing_jobs",
    "job_stage_history",
)

# Frontend high-risk path fragments — touching these means a change to one
# of the four FE-ARCH-NN debt surfaces. Mirrors BACKEND_HIGH_RISK_PATH_FRAGMENTS.
# Fragments are lowercased to match normalize()'s output.
FRONTEND_HIGH_RISK_PATH_FRAGMENTS = (
    # FE-ARCH-01 — matter workspace convergence
    "frontend/src/stores/matterstore.ts",
    "frontend/src/types/matter.ts",
    "frontend/src/app/matter/",                                  # all matter/[matterId]/* routes
    "frontend/src/components/features/matter/",
    "frontend/src/components/ui/api-error-boundary.tsx",
    # FE-ARCH-02 — responsive/layout system
    "frontend/src/stores/qapanelstore.ts",
    "frontend/src/app/globals.css",
    "frontend/tailwind.config.ts",
    "frontend/src/components/features/pdf/pdfsplitview.tsx",
    "frontend/src/components/features/export/exportbuilder.tsx",
    # FE-ARCH-03 — skeletons
    "frontend/src/components/ui/skeleton.tsx",
    "frontend/src/components/features/processing/processingskeleton.tsx",
    # FE-ARCH-04 — presentation/format layer
    "frontend/src/lib/utils.ts",
    "frontend/src/lib/format/",
    "frontend/src/utils/formatrelativetime.ts",
)

# Frontend high-risk symbols. Edits mentioning these — even outside the
# frontend path set — get the frontend architecture-guard reminder.
# Symbol matches are case-sensitive substring matches against edit content.
FRONTEND_HIGH_RISK_SYMBOLS = (
    # FE-ARCH-01
    "MatterProcessingStatus",
    "ApiErrorBoundary",
    "Untitled Matter",
    "fetchMatter",
    # FE-ARCH-02
    "ResizablePanelGroup",
    "scrollbar-gutter",
    # FE-ARCH-04
    "toLocaleDateString",
    "toLocaleTimeString",
    "Intl.DateTimeFormat",
)

# File suffixes whose content legitimately discusses high-risk symbols as
# prose (BUGS.md, ARCH-PATTERNS.md, GUARDRAIL-BACKLOG.md, FRONTEND-AUDIT-*.md,
# READMEs, docs). B1.8 fix: suppress the symbol-mention check on these so
# the hook does not cry wolf on documentation edits. The path-based check
# in is_high_risk_path() still fires correctly on actual code files, so
# the architecture-guard reminder still triggers when dangerous code is
# being edited.
DOC_FILE_SUFFIXES = (".md", ".markdown", ".mdx", ".rst", ".txt")

# --------------------------------------------------------------------------- #
# Reminder text
# --------------------------------------------------------------------------- #

ZOOM_OUT_REMINDER = """\
[ZOOM-OUT GUARD — every request, no exceptions]

Before proposing or writing any code in response to this request, answer these
four questions IN WRITING in your reply:

  1. What is the user actually trying to achieve? (the underlying goal, not the
     literal request)
  2. What is the bigger system this change sits inside? (module, data flow,
     call chain, architectural layer)
  3. Does the obvious local fix make the bigger system better, worse, or
     unchanged? If worse: name what it makes worse (duplication? a new
     "must remember to..." rule? a new special case in the orchestrator?
     a new shared-state hazard? extending an unhealthy pattern?).
  4. Is there a different change at a different level that solves the
     underlying goal without the local damage? Name it even if bigger.

The deliberate pause is the point, not the length of the answer. If the
honest answer to Q3 is "unchanged, this is a one-line copy edit" — say
exactly that sentence and proceed. But say it. Don't skip.

Skipping the zoom-out is the single biggest way past Claude sessions have
hurt this project (see ARCH-001/002/003 in BUGS.md section 0). Don't.

If you are about to spawn research agents (Agent tool) to investigate a
problem or verify a change: use the two-phase Deep Research Protocol at
`.claude/skills/blast-radius-research/SKILL.md`. Phase 1 (explore the
system) must complete before Phase 2 (verify a specific change). Never
skip Phase 1 — that's how generic advice that conflicts with existing
architecture gets proposed (see Railway cost analysis, 2026-04-22).
"""

BACKEND_ARCHITECTURE_GUARD_REMINDER = """\
[ARCHITECTURE GUARD — HIGH-RISK FILE DETECTED]

The file you are about to edit sits inside the LDIP document pipeline / worker
fleet / job state machine surface. This is the surface that produced ARCH-001,
ARCH-002, and ARCH-003 — every P0 architectural debt in this project.

STOP. Before this Edit/Write proceeds, you must:

1. Have already done the universal zoom-out (4 questions) for this request.
2. Invoke the `architecture-guard` skill (or read
   `.claude/skills/architecture-guard/SKILL.md` directly) and fill in its
   8-section checklist IN WRITING in your reply.
3. Verify the proposed change does NOT match any of the four forbidden
   patterns:
     - Forbidden #1: parallel duplicate paths for the same logical work
       (e.g. branching the orchestrator on document properties)
     - Forbidden #2: logical isolation without physical isolation
       (e.g. new queue without a dedicated worker)
     - Forbidden #2b: shared upstream API quota with no partitioning
       (e.g. new Gemini calls without naming a budget bucket)
     - Forbidden #3: "remember to signal" coordination
       (e.g. "all exit paths of task X must dispatch task Y";
        adding the Nth call site of a state mutation)

If the change matches any forbidden pattern, propose the allowed alternative
instead of writing the forbidden version — even if the user asked for "just
a quick fix." Use the explicit waiver escape hatch only if the user says
out loud that they accept the debt.

This reminder is injected automatically by .claude/hooks/zoom_out_guard.py.
It is not optional and not a formality. Past Claude sessions silenced this
voice and we paid for it three times.
"""

FRONTEND_ARCHITECTURE_GUARD_REMINDER = """\
[ARCHITECTURE GUARD — FRONTEND HIGH-RISK FILE DETECTED]

The file you are about to edit sits inside the LDIP frontend's high-risk
surface — the matter workspace shell, the responsive/layout system, the
skeleton layer, or the presentation/format layer. This is the surface that
produced FE-ARCH-01..04 in BUGS.md section 0.

STOP. Walk through whichever of the four debts the touched file belongs to,
and answer the relevant questions IN WRITING in your reply.

FE-ARCH-01 (matter workspace convergence):
  - Adding a new feature panel? Every panel today fetches its own data with
    no shared existence/auth gate; the shell fabricates a placeholder on
    404 instead of propagating the error. Are you routing through a single
    existence gate, or extending the per-panel-handles-its-own pattern that
    produced FE-003?
  - Touching matterStore on the fetch-catch path? Preserving the placeholder
    fabrication is preserving the bug.
  - Touching the matter status type? Does it have a 'failed' state yet?
    (Today it has only processing | ready | unused 'needs_attention' — that
    is why FE-007 misreports failed matters as 'Ready'.)
  - Touching api-error-boundary.tsx? It is currently built but zero usages —
    wiring it around the panel region is part of the fix; do not weaken it.

FE-ARCH-02 (responsive/layout):
  - Adding a fixed two-pane / multi-column / resizable-panel layout? Where
    does it auto-collapse by viewport? There is currently no useBreakpoint
    / useMediaQuery primitive in the codebase — if you need one, that
    primitive is what you should build first.
  - Adding raw sm:/md:/lg: Tailwind classes? Acknowledged — but the goal is
    to reduce reliance on per-component breakpoint convention. Don't extend
    that path without a plan to retire it.

FE-ARCH-03 (skeletons):
  - Authoring a new Skeleton? Why is it not the real component in a
    skeleton-mode? List the hardcoded h-/w- dimensions you are introducing
    and explain why they cannot drift from the real component as the real
    component evolves.

FE-ARCH-04 (presentation/format layer):
  - Calling toLocaleDateString / toLocaleTimeString / Intl.DateTimeFormat in
    a component? frontend/src/lib/format/ is the intended single source
    (build it if it does not exist yet). Do not add a 9th formatDate impl.
  - Building a count-string template? Use a pluralize() helper (build it in
    lib/format/ if it does not exist) — not an inline ternary. Four
    currently-shipping bugs in FE-015 ("1 documents", "1 pages") come from
    skipping this check.

If the change extends any of these debt shapes without closing them,
propose the structural alternative. Full SKILL at
`.claude/skills/architecture-guard/SKILL.md`.

This reminder is injected automatically by .claude/hooks/zoom_out_guard.py.
The frontend was unobserved by this hook until 2026-05-25. Don't let the
next debt accrete unobserved.
"""

DEPLOY_REVIEW_REMINDER = """\
[DEPLOY GUARD — hostile review required before deploy]

You are about to deploy to production. Before this deploy proceeds:

1. Have you run the hostile-review skill (`/hostile-review`) on the
   changes being deployed?

2. If YES — state which BUG FOUND items were fixed and which RISK items
   were accepted. Confirm all BUG FOUND items are resolved.

3. If NO — you MUST run it now. Invoke the `hostile-review` skill at
   `.claude/skills/hostile-review/SKILL.md`. Spawn an Agent with the
   checklist applied to all changed files. Fix any BUG FOUND items
   before deploying.

Why: On 2026-05-14, a deploy shipped code that hit Upstash's 100MB Redis
record limit — a failure mode invisible in code but caught by hostile
review. The blast-radius skill missed it because it runs pre-implementation.
The hostile review catches post-implementation bugs that only exist in
actual code: runtime decorator behavior, serialization limits, concurrent
execution races, missing wiring.

Skipping this step is how infrastructure bugs reach production.
"""

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def normalize(path: str) -> str:
    return path.replace("\\", "/").lower()


def _content_blobs(tool_input: dict) -> str:
    """Join all content fields of a tool_input into one searchable string."""
    blobs = []
    for key in ("content", "new_string", "old_string"):
        val = tool_input.get(key)
        if isinstance(val, str):
            blobs.append(val)
    return "\n".join(blobs)


def _is_doc_file(file_path: str) -> bool:
    """B1.8: documentation files legitimately discuss high-risk symbols as prose."""
    return bool(file_path) and normalize(file_path).endswith(DOC_FILE_SUFFIXES)


def is_backend_high_risk_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = normalize(file_path)
    return any(frag in norm for frag in BACKEND_HIGH_RISK_PATH_FRAGMENTS)


def edit_mentions_backend_high_risk_symbol(tool_input: dict) -> bool:
    """Check the proposed edit content for backend high-risk symbols.

    Skips documentation files (B1.8): a file ending in any DOC_FILE_SUFFIXES
    can legitimately reference backend high-risk symbols as prose (BUGS.md,
    ARCH-PATTERNS.md, GUARDRAIL-BACKLOG.md, FRONTEND-AUDIT-*.md) without
    calling them. The path-based check in is_backend_high_risk_path() still
    fires correctly on actual code files, so protection on the real
    dangerous surface is intact.
    """
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if _is_doc_file(file_path):
        return False
    haystack = _content_blobs(tool_input)
    return any(sym in haystack for sym in BACKEND_HIGH_RISK_SYMBOLS)


def is_frontend_high_risk_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = normalize(file_path)
    return any(frag in norm for frag in FRONTEND_HIGH_RISK_PATH_FRAGMENTS)


def edit_mentions_frontend_high_risk_symbol(tool_input: dict) -> bool:
    """Check the proposed edit content for frontend high-risk symbols.

    Mirrors edit_mentions_backend_high_risk_symbol — same B1.8 doc-file
    exclusion. Fires on FE-ARCH-01..04-relevant symbol mentions in code files.
    """
    file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if _is_doc_file(file_path):
        return False
    haystack = _content_blobs(tool_input)
    return any(sym in haystack for sym in FRONTEND_HIGH_RISK_SYMBOLS)


def emit_additional_context(event_name: str, text: str) -> None:
    """Emit a hookSpecificOutput JSON payload that injects context into Claude."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        event = json.loads(raw)
    except Exception:
        # Never crash the user's session because of a hook parse error.
        return 0

    event_name = event.get("hook_event_name") or event.get("hookEventName") or ""

    if event_name == "UserPromptSubmit":
        emit_additional_context("UserPromptSubmit", ZOOM_OUT_REMINDER)
        return 0

    if event_name == "PreToolUse":
        tool_name = event.get("tool_name", "")
        tool_input = event.get("tool_input") or {}

        # Deploy guard: detect `railway up` commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if "railway up" in command:
                emit_additional_context("PreToolUse", DEPLOY_REVIEW_REMINDER)
                return 0

        if tool_name not in ("Edit", "Write", "NotebookEdit"):
            return 0
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        backend_risky = (
            is_backend_high_risk_path(file_path)
            or edit_mentions_backend_high_risk_symbol(tool_input)
        )
        frontend_risky = (
            is_frontend_high_risk_path(file_path)
            or edit_mentions_frontend_high_risk_symbol(tool_input)
        )
        reminders = []
        if backend_risky:
            reminders.append(BACKEND_ARCHITECTURE_GUARD_REMINDER)
        if frontend_risky:
            reminders.append(FRONTEND_ARCHITECTURE_GUARD_REMINDER)
        if reminders:
            emit_additional_context("PreToolUse", "\n\n".join(reminders))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
