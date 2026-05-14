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

# Substring matches against the absolute file_path (lowercased, forward slashes).
# A file is "high-risk" if any of these substrings appears in its path.
HIGH_RISK_PATH_FRAGMENTS = (
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
# high-risk path set, an edit that mentions any of these symbols is touching
# the dangerous state machine and gets the architecture-guard reminder.
HIGH_RISK_SYMBOLS = (
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

ARCHITECTURE_GUARD_REMINDER = """\
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


def is_high_risk_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = normalize(file_path)
    return any(frag in norm for frag in HIGH_RISK_PATH_FRAGMENTS)


def edit_mentions_high_risk_symbol(tool_input: dict) -> bool:
    """Check the proposed edit content for high-risk symbols."""
    blobs = []
    for key in ("content", "new_string", "old_string"):
        val = tool_input.get(key)
        if isinstance(val, str):
            blobs.append(val)
    haystack = "\n".join(blobs)
    return any(sym in haystack for sym in HIGH_RISK_SYMBOLS)


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
        risky = is_high_risk_path(file_path) or edit_mentions_high_risk_symbol(tool_input)
        if risky:
            emit_additional_context("PreToolUse", ARCHITECTURE_GUARD_REMINDER)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
