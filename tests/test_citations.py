"""Tests for citation extraction."""

import pytest
from src.citations.patterns import extract_citations_regex
from src.citations.abbreviations import resolve_abbreviation, ACT_ABBREVIATIONS


class TestCitationPatterns:
    """Test citation regex patterns."""

    def test_section_of_pattern(self):
        """Test 'Section X of Act' pattern."""
        text = "Section 138 of the Negotiable Instruments Act, 1881"
        matches = extract_citations_regex(text)

        assert len(matches) == 1
        assert matches[0].section == "138"
        assert "Negotiable Instruments Act" in matches[0].act_name

    def test_under_section_pattern(self):
        """Test 'u/s X Act' pattern."""
        text = "The accused was charged u/s 302 IPC"
        matches = extract_citations_regex(text)

        assert len(matches) == 1
        assert matches[0].section == "302"
        assert "IPC" in matches[0].act_name

    def test_abbreviated_section(self):
        """Test 'S. X Act' pattern."""
        text = "S. 420 Indian Penal Code, 1860"
        matches = extract_citations_regex(text)

        assert len(matches) == 1
        assert matches[0].section == "420"

    def test_article_pattern(self):
        """Test 'Article X Constitution' pattern."""
        text = "Article 21 of the Constitution of India"
        matches = extract_citations_regex(text)

        assert len(matches) == 1
        assert matches[0].section == "21"
        assert "Constitution" in matches[0].act_name

    def test_multiple_citations(self):
        """Test extracting multiple citations."""
        text = """
        The accused was charged under Section 302 IPC for murder.
        The court also considered Section 138 of the NI Act.
        Article 21 guarantees right to life.
        """
        matches = extract_citations_regex(text)

        assert len(matches) >= 2  # At least 2 citations


class TestAbbreviations:
    """Test act abbreviation resolution."""

    def test_ipc_abbreviation(self):
        """Test IPC resolves to Indian Penal Code."""
        result = resolve_abbreviation("IPC")
        assert result == "Indian Penal Code, 1860"

    def test_ni_act_abbreviation(self):
        """Test NI Act resolves correctly."""
        result = resolve_abbreviation("NI Act")
        assert result == "Negotiable Instruments Act, 1881"

    def test_bns_abbreviation(self):
        """Test new Bharatiya Nyaya Sanhita."""
        result = resolve_abbreviation("BNS")
        assert result == "Bharatiya Nyaya Sanhita, 2023"

    def test_unknown_returns_original(self):
        """Test unknown abbreviation returns original."""
        result = resolve_abbreviation("Unknown Act XYZ")
        assert result == "Unknown Act XYZ"

    def test_case_insensitive(self):
        """Test case insensitive lookup."""
        result = resolve_abbreviation("ipc")
        assert result == "Indian Penal Code, 1860"
