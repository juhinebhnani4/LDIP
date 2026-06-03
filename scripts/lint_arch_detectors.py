#!/usr/bin/env python3
"""
B4.4 — Architectural-debt entry detector discipline lint.

Scans `BUGS.md` and asserts that every architectural-debt entry — any header
matching `### (ARCH|FE-ARCH)-NN:` — carries a `**Detector:**` field in its
body before the next entry / separator / top-level heading.

Why this exists
---------------
The four FE-ARCH-01..04 entries authored on 2026-05-25 carry runnable
detector commands so their instance counts are regenerable, not hand-typed.
Without this lint, the next architectural-debt entry (FE-ARCH-05, ARCH-008,
…) would silently drop the detector field — and the census would rot back
into a hand-list, the exact ARCH-003 shape that `FRONTEND-ARCH-DEBT.md` was
deleted to escape.

This is the wall version of "remember to include a Detector field."
See `GUARDRAIL-BACKLOG.md` B4.4 for context.

Usage
-----
    python scripts/lint_arch_detectors.py [path/to/BUGS.md]

Exits 0 on pass, 1 on missing detectors, 2 on file-not-found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ----- patterns ------------------------------------------------------------ #

# Matches `### ARCH-001: ...` or `### FE-ARCH-04: ...`
ENTRY_HEADER = re.compile(r"^### ((?:FE-)?ARCH-\w+):", re.MULTILINE)

# The detector field — accept `**Detector:**` or `**Detector**:` (either style).
DETECTOR_FIELD = re.compile(r"\*\*Detector(?::?\*\*|\*\*:)", re.IGNORECASE)

# An entry body ends at the next `### ` (any subheader), `## ` (top-level), or
# horizontal rule `---`. We use the EARLIEST of these as the body terminus so
# the lint cannot be fooled by a detector field that belongs to a sibling.
BODY_TERMINUS = re.compile(r"^(?:### |## |---+\s*$)", re.MULTILINE)


def find_entries(text: str):
    """Yield (name, body_text) for each architectural-debt entry."""
    headers = list(ENTRY_HEADER.finditer(text))
    for i, h in enumerate(headers):
        name = h.group(1)
        body_start = h.end()
        # Next entry header (if any) or end-of-file as the absolute ceiling.
        ceiling = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        # Earliest of: next ### / ## / --- after body_start, but capped at ceiling.
        terminus = BODY_TERMINUS.search(text, body_start, ceiling)
        body_end = terminus.start() if terminus else ceiling
        yield name, text[body_start:body_end]


# ----- main ---------------------------------------------------------------- #


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path("BUGS.md")
    if not path.exists():
        print(f"lint_arch_detectors: ERROR: {path} not found", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    missing: list[str] = []
    total = 0
    for name, body in find_entries(text):
        total += 1
        if not DETECTOR_FIELD.search(body):
            missing.append(name)

    if missing:
        print(
            f"lint_arch_detectors: FAIL — {len(missing)} of {total} "
            f"architectural-debt entries in {path} are missing **Detector:**",
            file=sys.stderr,
        )
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        print(
            "\nEvery `### (FE-)ARCH-NN:` entry MUST carry a runnable `**Detector:**` field\n"
            "(an `rg` / `find` / `wc` command that re-derives the instance count).\n"
            "See GUARDRAIL-BACKLOG.md B4.4 and ARCH-PATTERNS.md.",
            file=sys.stderr,
        )
        return 1

    print(f"lint_arch_detectors: OK — all {total} entries in {path} carry **Detector:**")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
