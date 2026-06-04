"""Tests for data loader utility.

Tests the loading of known_acts.json including aliases support.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.data_loader import (
    clear_data_cache,
    get_known_act_info,
    get_known_acts,
)


class TestKnownActsLoading:
    """Tests for known_acts.json loading with aliases."""

    @pytest.fixture(autouse=True)
    def clear_cache(self) -> None:
        """Clear cache before each test."""
        clear_data_cache()

    def test_loads_known_acts_with_aliases(self, tmp_path: Path) -> None:
        """Should load known acts and include aliases in mapping."""
        # Create a test known_acts.json
        test_data = {
            "acts": [
                {
                    "normalized_name": "companies_act_1956",
                    "canonical_name": "Companies Act, 1956",
                    "india_code_doc_id": "1428",
                    "india_code_filename": "19561.pdf",
                    "is_active": True,
                    "aliases": ["indian_companies_act_1956"],
                },
                {
                    "normalized_name": "negotiable_instruments_act_1881",
                    "canonical_name": "Negotiable Instruments Act, 1881",
                    "india_code_doc_id": "2189",
                    "india_code_filename": "1/a1881-26.pdf",
                    "is_active": True,
                    # No aliases
                },
            ]
        }

        test_file = tmp_path / "known_acts.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        # Patch DATA_DIR to use our test directory
        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            known_acts = get_known_acts()

            # Should have both main entries and alias
            assert "companies_act_1956" in known_acts
            assert "indian_companies_act_1956" in known_acts  # Alias
            assert "negotiable_instruments_act_1881" in known_acts

            # Main entry and alias should point to same doc_id
            assert known_acts["companies_act_1956"] == ("1428", "19561.pdf")
            assert known_acts["indian_companies_act_1956"] == ("1428", "19561.pdf")

    def test_skips_inactive_acts(self, tmp_path: Path) -> None:
        """Should not load inactive acts."""
        test_data = {
            "acts": [
                {
                    "normalized_name": "active_act",
                    "canonical_name": "Active Act",
                    "india_code_doc_id": "123",
                    "india_code_filename": "active.pdf",
                    "is_active": True,
                },
                {
                    "normalized_name": "inactive_act",
                    "canonical_name": "Inactive Act",
                    "india_code_doc_id": "456",
                    "india_code_filename": "inactive.pdf",
                    "is_active": False,
                },
            ]
        }

        test_file = tmp_path / "known_acts.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            known_acts = get_known_acts()

            assert "active_act" in known_acts
            assert "inactive_act" not in known_acts

    def test_alias_does_not_override_existing_entry(self, tmp_path: Path) -> None:
        """Alias should not override an existing entry."""
        test_data = {
            "acts": [
                {
                    "normalized_name": "companies_act_2013",
                    "canonical_name": "Companies Act, 2013",
                    "india_code_doc_id": "2114",
                    "india_code_filename": "2013.pdf",
                    "is_active": True,
                    # Alias is same as another act's normalized name
                    "aliases": ["companies_act_1956"],
                },
                {
                    "normalized_name": "companies_act_1956",
                    "canonical_name": "Companies Act, 1956",
                    "india_code_doc_id": "1428",
                    "india_code_filename": "1956.pdf",
                    "is_active": True,
                },
            ]
        }

        test_file = tmp_path / "known_acts.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            known_acts = get_known_acts()

            # The main entry should take precedence over the alias
            # companies_act_1956 should point to 1428, not 2114
            assert known_acts["companies_act_1956"] == ("1428", "1956.pdf")

    def test_get_known_act_info_returns_tuple(self, tmp_path: Path) -> None:
        """get_known_act_info should return (doc_id, filename) tuple."""
        test_data = {
            "acts": [
                {
                    "normalized_name": "test_act_2023",
                    "canonical_name": "Test Act, 2023",
                    "india_code_doc_id": "999",
                    "india_code_filename": "test.pdf",
                    "is_active": True,
                },
            ]
        }

        test_file = tmp_path / "known_acts.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            info = get_known_act_info("test_act_2023")

            assert info == ("999", "test.pdf")

    def test_get_known_act_info_returns_none_for_unknown(self, tmp_path: Path) -> None:
        """get_known_act_info should return None for unknown act."""
        test_data = {"acts": []}

        test_file = tmp_path / "known_acts.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            info = get_known_act_info("nonexistent_act")

            assert info is None

    def test_handles_missing_file_gracefully(self, tmp_path: Path) -> None:
        """Should return empty dict when file is missing."""
        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            known_acts = get_known_acts()

            assert known_acts == {}

    def test_handles_invalid_json_gracefully(self, tmp_path: Path) -> None:
        """Should raise DataLoadError for invalid JSON."""
        test_file = tmp_path / "known_acts.json"
        with open(test_file, "w") as f:
            f.write("{ invalid json }")

        with patch("app.core.data_loader.DATA_DIR", tmp_path):
            clear_data_cache()
            from app.core.data_loader import DataLoadError

            with pytest.raises(DataLoadError):
                get_known_acts()
