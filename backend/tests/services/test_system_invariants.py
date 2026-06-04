"""Tests for the silent-failure invariant catalog (app.services.system_invariants).

This is the guard that proves the watchman itself is not a dead battery: the
flagship GAP-24 invariant must FLAG a fully-embedded resolved Act whose citations
are stuck pending at 0% verified, and must NOT flag the carved known-good shapes
(act_unavailable citations like doc a65f4b17, not-yet-embedded Acts, recent
pending within the verification grace window, or Acts that already have a verified
citation).
"""

from unittest.mock import patch

from app.engines.citation.abbreviations import normalize_act_name
from app.services import act_verification_state, system_invariants
from app.services.system_invariants import (
    INVARIANTS,
    Invariant,
    _check_acts_resolved_embedded_zero_verified,
    _check_completed_docs_zero_chunks,
    run_all_invariants,
)

# A timestamp safely older than the 60-minute pending grace window.
OLD = "2020-01-01T00:00:00+00:00"
# A timestamp safely inside the grace window (far future => never older than cutoff).
RECENT = "2999-01-01T00:00:00+00:00"

ACT_DISPLAY = "Companies Act, 2013"
ACT_NORM = normalize_act_name(ACT_DISPLAY)
MATTER = "11111111-1111-1111-1111-111111111111"
ACT_DOC = "22222222-2222-2222-2222-222222222222"


class _Resp:
    def __init__(self, data):
        self.data = list(data)
        self.count = len(data)


class _FakeQuery:
    """Records nothing; filters are ignored. Tests use single-matter / single-doc
    fixtures so filter-ignorance does not change the asserted logic. ``execute``
    returns the table's full row list; the production pagination loop terminates
    because each batch is < the 1000-row page size."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def neq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def is_(self, *a, **k):
        return self

    def lt(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    @property
    def not_(self):
        return self

    def execute(self):
        return _Resp(self._rows)


class _FakeClient:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def _resolution(status="available"):
    return {
        "matter_id": MATTER,
        "act_name_normalized": ACT_NORM,
        "act_name_display": ACT_DISPLAY,
        "act_document_id": ACT_DOC,
        "resolution_status": status,
    }


def _citation(status, updated_at=OLD, act_name=ACT_DISPLAY):
    return {
        "act_name": act_name,
        "verification_status": status,
        "updated_at": updated_at,
    }


# ---------------------------------------------------------------------------
# Flagship (GAP-24) — the invariant this whole effort exists for
# ---------------------------------------------------------------------------


def test_flagship_flags_embedded_resolved_act_with_zero_verified():
    """The exact GAP-24 shape: resolved + fully embedded Act, stale-pending
    citations, ZERO verified => must be flagged."""
    client = _FakeClient(
        {
            "act_resolutions": [_resolution()],
            "citations": [_citation("pending"), _citation("pending")],
        }
    )
    with patch.object(
        act_verification_state, "act_doc_fully_embedded", return_value=True
    ):
        result = _check_acts_resolved_embedded_zero_verified(client)
    assert result.violating_count == 1
    assert result.sample[0]["act_document_id"] == ACT_DOC


def test_flagship_does_not_flag_act_unavailable_only():
    """Carved known-good (a65f4b17): citations are act_unavailable, not pending.
    Even though the Act is resolved + embedded, act_unavailable means the Act is
    legitimately absent for those citations => must NOT be flagged."""
    client = _FakeClient(
        {
            "act_resolutions": [_resolution()],
            "citations": [_citation("act_unavailable"), _citation("act_unavailable")],
        }
    )
    with patch.object(
        act_verification_state, "act_doc_fully_embedded", return_value=True
    ):
        result = _check_acts_resolved_embedded_zero_verified(client)
    assert result.violating_count == 0


def test_flagship_does_not_flag_when_a_citation_is_verified():
    """If even one citation for the Act is verified, verification is converging =>
    not the 0%-verified silent failure."""
    client = _FakeClient(
        {
            "act_resolutions": [_resolution()],
            "citations": [_citation("pending"), _citation("verified")],
        }
    )
    with patch.object(
        act_verification_state, "act_doc_fully_embedded", return_value=True
    ):
        result = _check_acts_resolved_embedded_zero_verified(client)
    assert result.violating_count == 0


def test_flagship_does_not_flag_not_yet_embedded_act():
    """An Act still embedding legitimately has 0 verified => must NOT be flagged."""
    client = _FakeClient(
        {
            "act_resolutions": [_resolution()],
            "citations": [_citation("pending")],
        }
    )
    with patch.object(
        act_verification_state, "act_doc_fully_embedded", return_value=False
    ):
        result = _check_acts_resolved_embedded_zero_verified(client)
    assert result.violating_count == 0


def test_flagship_does_not_flag_recent_pending_within_grace():
    """Pending citations newer than the grace window are normal verification
    latency => must NOT be flagged."""
    client = _FakeClient(
        {
            "act_resolutions": [_resolution()],
            "citations": [_citation("pending", updated_at=RECENT)],
        }
    )
    with patch.object(
        act_verification_state, "act_doc_fully_embedded", return_value=True
    ):
        result = _check_acts_resolved_embedded_zero_verified(client)
    assert result.violating_count == 0


# ---------------------------------------------------------------------------
# GAP-2 — completed document with zero chunks
# ---------------------------------------------------------------------------


def test_completed_doc_zero_chunks_flags_when_no_chunks():
    client = _FakeClient(
        {
            "documents": [
                {"id": "doc-1", "filename": "a.pdf", "document_type": "case_file"}
            ],
            "chunks": [],
        }
    )
    result = _check_completed_docs_zero_chunks(client)
    assert result.violating_count == 1
    assert result.sample[0]["document_id"] == "doc-1"


def test_completed_doc_zero_chunks_ok_when_chunks_exist():
    client = _FakeClient(
        {
            "documents": [
                {"id": "doc-1", "filename": "a.pdf", "document_type": "case_file"}
            ],
            "chunks": [{"id": "chunk-1"}],
        }
    )
    result = _check_completed_docs_zero_chunks(client)
    assert result.violating_count == 0


# ---------------------------------------------------------------------------
# Structural guard — the catalog cannot host a "dead" invariant
# ---------------------------------------------------------------------------


def test_catalog_entries_are_well_formed():
    """Every invariant must have a unique name, a severity in the allowed set,
    and a callable check. This is the structural guard that a future invariant
    cannot be added as a no-op (a dead guard) — the failure mode this whole
    system exists to prevent."""
    names = [inv.name for inv in INVARIANTS]
    assert len(names) == len(set(names)), "invariant names must be unique"
    for inv in INVARIANTS:
        assert isinstance(inv, Invariant)
        assert inv.severity in {"critical", "warning", "info"}
        assert callable(inv.check), f"{inv.name} has no callable check"


def test_run_all_invariants_returns_one_row_per_invariant_and_never_raises():
    """run_invariant must swallow check errors into a not-ok row (an invariant
    that errors is itself a signal, never a silent disappearance)."""
    boom = _FakeClient({})  # empty tables; checks run but find nothing

    # Inject a deliberately-failing invariant to prove errors are captured.
    def _explode(_client):
        raise RuntimeError("kaboom")

    original = list(system_invariants.INVARIANTS)
    try:
        system_invariants.INVARIANTS.append(
            Invariant(
                name="explodes", severity="critical", description="x", check=_explode
            )
        )
        rows = run_all_invariants(boom)
    finally:
        system_invariants.INVARIANTS[:] = original

    assert len(rows) == len(original) + 1
    exploded = next(r for r in rows if r["name"] == "explodes")
    assert exploded["ok"] is False
    assert exploded["violating_count"] == -1
    assert "kaboom" in exploded["message"]
