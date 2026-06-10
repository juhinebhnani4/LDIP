"""Self-verification for the INF-014 strict-quarantine mechanism.

Why this exists: the quarantine (tests/inf014_quarantine.txt + the conftest
collection hook) is applied as ``xfail(strict=True)`` so a fixed test's XPASS
fails the required ``test`` job — forcing the fixer to delete the line, which
is what makes the list self-cleaning (the INF-014 ⑤ plan). The one escape hatch
is a per-entry ``# flaky`` tag that reverts THAT entry to strict=False so an
incidental pass on a non-deterministic test can't red the required check and
block unrelated merges.

Both behaviours are pure-string parsing in ``_parse_quarantine``. A wall you
can't prove is a wall you don't have — these tests pin the strict-by-default
rule AND the flaky exemption so a future edit can't silently weaken either.
See BUGS.md INF-014.
"""

from tests.conftest import _parse_quarantine


class TestParseQuarantine:
    def test_plain_nodeid_is_strict_by_default(self):
        """A bare nodeid is strict — that is what makes the list self-cleaning."""
        parsed = _parse_quarantine("tests/foo/test_bar.py::TestX::test_y")
        assert parsed == {"tests/foo/test_bar.py::TestX::test_y": True}

    def test_flaky_tag_reverts_entry_to_non_strict(self):
        """`# flaky` is the escape hatch — only that entry becomes strict=False."""
        text = (
            "tests/foo/test_bar.py::test_deterministic\n"
            "tests/foo/test_bar.py::test_sometimes_passes  # flaky\n"
        )
        parsed = _parse_quarantine(text)
        assert parsed["tests/foo/test_bar.py::test_deterministic"] is True
        assert parsed["tests/foo/test_bar.py::test_sometimes_passes"] is False

    def test_flaky_match_is_case_insensitive_and_position_independent(self):
        parsed = _parse_quarantine("tests/x.py::test_z  #   known FLAKY on CI")
        assert parsed["tests/x.py::test_z"] is False

    def test_non_flaky_inline_comment_stays_strict(self):
        """An inline comment that isn't a flaky tag must NOT weaken the entry."""
        parsed = _parse_quarantine("tests/x.py::test_z  # see BUGS.md INF-014 ③")
        assert parsed["tests/x.py::test_z"] is True

    def test_comment_and_blank_lines_ignored(self):
        text = "\n# a header comment\n\n   \ntests/x.py::test_a\n# trailing\n"
        assert _parse_quarantine(text) == {"tests/x.py::test_a": True}

    def test_empty_text_is_empty_map(self):
        assert _parse_quarantine("") == {}
