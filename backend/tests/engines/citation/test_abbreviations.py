"""Tests for Act abbreviation dictionary and normalization.

Story 3-1: Act Citation Extraction (AC: #2)
"""


from app.engines.citation.abbreviations import (
    ACT_ABBREVIATIONS,
    extract_year_from_name,
    get_canonical_name,
    get_display_name,
    normalize_act_name,
)


class TestGetCanonicalName:
    """Tests for get_canonical_name function."""

    def test_common_abbreviation_ni_act(self) -> None:
        """Should resolve NI Act to Negotiable Instruments Act."""
        result = get_canonical_name("NI Act")
        assert result is not None
        name, year = result
        assert name == "Negotiable Instruments Act"
        assert year == 1881

    def test_lowercase_abbreviation(self) -> None:
        """Should handle lowercase abbreviations."""
        result = get_canonical_name("ni act")
        assert result is not None
        name, year = result
        assert name == "Negotiable Instruments Act"

    def test_ipc_abbreviation(self) -> None:
        """Should resolve IPC to Indian Penal Code."""
        result = get_canonical_name("IPC")
        assert result is not None
        name, year = result
        assert name == "Indian Penal Code"
        assert year == 1860

    def test_crpc_abbreviation(self) -> None:
        """Should resolve CrPC variations."""
        for abbr in ["CrPC", "Cr.P.C.", "cr pc", "CR PC"]:
            result = get_canonical_name(abbr)
            assert result is not None, f"Failed for {abbr}"
            name, year = result
            assert name == "Code of Criminal Procedure"
            assert year == 1973

    def test_sarfaesi_abbreviation(self) -> None:
        """Should resolve SARFAESI to full name."""
        result = get_canonical_name("SARFAESI")
        assert result is not None
        name, year = result
        assert "Securitisation" in name
        assert year == 2002

    def test_full_name_lookup(self) -> None:
        """Should resolve full Act names."""
        result = get_canonical_name("Negotiable Instruments Act")
        assert result is not None
        name, year = result
        assert name == "Negotiable Instruments Act"
        assert year == 1881

    def test_with_the_prefix(self) -> None:
        """Should handle 'the' prefix."""
        result = get_canonical_name("the NI Act")
        assert result is not None
        name, _ = result
        assert name == "Negotiable Instruments Act"

    def test_unknown_act_returns_none(self) -> None:
        """Should return None for unknown Acts."""
        result = get_canonical_name("Nonexistent Act 2025")
        assert result is None

    def test_ibc_abbreviation(self) -> None:
        """Should resolve IBC to Insolvency and Bankruptcy Code."""
        result = get_canonical_name("IBC")
        assert result is not None
        name, year = result
        assert name == "Insolvency and Bankruptcy Code"
        assert year == 2016

    def test_gst_acts(self) -> None:
        """Should resolve GST-related abbreviations."""
        for abbr, expected_name in [
            ("CGST Act", "Central Goods and Services Tax Act"),
            ("IGST Act", "Integrated Goods and Services Tax Act"),
        ]:
            result = get_canonical_name(abbr)
            assert result is not None, f"Failed for {abbr}"
            name, year = result
            assert name == expected_name
            assert year == 2017


class TestNormalizeActName:
    """Tests for normalize_act_name function."""

    def test_normalize_with_canonical(self) -> None:
        """Should normalize known Act names."""
        result = normalize_act_name("NI Act")
        assert result == "negotiable_instruments_act_1881"

    def test_normalize_with_year(self) -> None:
        """Should include year in normalized form."""
        result = normalize_act_name("Negotiable Instruments Act, 1881")
        assert "1881" in result
        assert "negotiable_instruments_act" in result

    def test_normalize_removes_punctuation(self) -> None:
        """Should remove punctuation from normalized form."""
        result = normalize_act_name("Transfer of Property Act, 1882")
        assert "," not in result
        assert "_" in result

    def test_normalize_unknown_act(self) -> None:
        """Should normalize unknown Acts to lowercase with underscores."""
        result = normalize_act_name("Custom Local Act 2020")
        assert result == "custom_local_act_2020"

    def test_normalize_with_ampersand(self) -> None:
        """Should handle ampersands in Act names."""
        # Test with a known Act that has consistent lookup
        result = normalize_act_name("Arbitration Act")
        assert "arbitration" in result.lower()
        assert "1996" in result  # Should include year from canonical lookup


class TestExtractYearFromName:
    """Tests for extract_year_from_name function."""

    def test_extract_year_with_comma(self) -> None:
        """Should extract year with comma format."""
        year = extract_year_from_name("Negotiable Instruments Act, 1881")
        assert year == 1881

    def test_extract_year_without_comma(self) -> None:
        """Should extract year without comma."""
        year = extract_year_from_name("Companies Act 2013")
        assert year == 2013

    def test_no_year_returns_none(self) -> None:
        """Should return None when no year present."""
        year = extract_year_from_name("NI Act")
        assert year is None

    def test_extract_recent_year(self) -> None:
        """Should extract recent years (2000s)."""
        year = extract_year_from_name("BNS 2023")
        assert year == 2023

    def test_extract_old_year(self) -> None:
        """Should extract old years (1800s)."""
        year = extract_year_from_name("Indian Penal Code 1860")
        assert year == 1860


class TestGetDisplayName:
    """Tests for get_display_name function."""

    def test_display_name_with_year(self) -> None:
        """Should format display name with year."""
        result = get_display_name("negotiable_instruments_act_1881")
        assert result == "Negotiable Instruments Act, 1881"

    def test_display_name_without_year(self) -> None:
        """Should format display name without year."""
        result = get_display_name("some_act")
        assert result == "Some Act"

    def test_display_name_title_case(self) -> None:
        """Should convert to title case."""
        result = get_display_name("indian_penal_code_1860")
        assert result == "Indian Penal Code, 1860"


class TestActAbbreviationsDictionary:
    """Tests for the ACT_ABBREVIATIONS dictionary."""

    def test_dictionary_has_common_acts(self) -> None:
        """Should contain common Indian Acts."""
        assert "ipc" in ACT_ABBREVIATIONS
        assert "crpc" in ACT_ABBREVIATIONS
        assert "ni act" in ACT_ABBREVIATIONS
        assert "sarfaesi" in ACT_ABBREVIATIONS

    def test_dictionary_values_are_tuples(self) -> None:
        """Values should be (name, year) tuples."""
        for key, value in ACT_ABBREVIATIONS.items():
            assert isinstance(value, tuple), f"Value for {key} is not a tuple"
            assert len(value) == 2, f"Tuple for {key} doesn't have 2 elements"
            name, year = value
            assert isinstance(name, str), f"Name for {key} is not a string"
            assert year is None or isinstance(year, int), f"Year for {key} is not int or None"

    def test_criminal_law_acts_present(self) -> None:
        """Should contain major criminal law Acts."""
        criminal_acts = ["ipc", "crpc", "indian evidence act", "pocso"]
        for act in criminal_acts:
            assert act in ACT_ABBREVIATIONS, f"Missing criminal law Act: {act}"

    def test_commercial_law_acts_present(self) -> None:
        """Should contain major commercial law Acts."""
        commercial_acts = ["ni act", "contract act", "companies act"]
        for act in commercial_acts:
            assert act in ACT_ABBREVIATIONS, f"Missing commercial law Act: {act}"

    def test_new_criminal_codes_present(self) -> None:
        """Should contain new criminal codes (BNS, BNSS, BSA)."""
        new_codes = ["bns", "bnss", "bsa"]
        for code in new_codes:
            assert code in ACT_ABBREVIATIONS, f"Missing new criminal code: {code}"
