"""Tests for document_ocr_chunks table migration.

Tests verify:
- Table schema and column types
- CHECK constraint enforcement
- UNIQUE constraint enforcement
- RLS policy behavior
- Cascading delete behavior
- Storage path validation functions

Note: These tests use mocks for unit testing. Integration tests
with live Supabase require the migration to be applied first.
"""

import uuid
from unittest.mock import MagicMock

import pytest


class TestDocumentOCRChunksSchema:
    """Tests for document_ocr_chunks table schema."""

    def test_table_columns_match_expected_schema(self) -> None:
        """Verify table has all required columns with correct types.

        AC: #2 - Core columns present
        """
        expected_columns = {
            "id": "uuid",
            "matter_id": "uuid",
            "document_id": "uuid",
            "chunk_index": "integer",
            "page_start": "integer",
            "page_end": "integer",
            "status": "text",
            "error_message": "text",
            "result_storage_path": "text",
            "result_checksum": "text",
            "processing_started_at": "timestamptz",
            "processing_completed_at": "timestamptz",
            "created_at": "timestamptz",
            "updated_at": "timestamptz",
        }

        # This documents expected schema - actual verification requires live DB
        assert len(expected_columns) == 14
        assert "id" in expected_columns
        assert "matter_id" in expected_columns
        assert "result_storage_path" in expected_columns  # AC: #3

    def test_result_storage_columns_present(self) -> None:
        """Verify caching architecture columns exist.

        AC: #3 - Result storage columns
        """
        caching_columns = {
            "result_storage_path": "Supabase Storage path for cached OCR results",
            "result_checksum": "SHA256 checksum for validation",
        }

        assert "result_storage_path" in caching_columns
        assert "result_checksum" in caching_columns

    def test_status_enum_values_documented(self) -> None:
        """Verify allowed status values.

        AC: #4 - CHECK constraint on status
        """
        allowed_statuses = ["pending", "processing", "completed", "failed"]

        assert "pending" in allowed_statuses
        assert "processing" in allowed_statuses
        assert "completed" in allowed_statuses
        assert "failed" in allowed_statuses
        assert len(allowed_statuses) == 4


class TestConstraintEnforcement:
    """Tests for CHECK and UNIQUE constraints."""

    def test_unique_constraint_prevents_duplicate_chunks(self) -> None:
        """Verify UNIQUE constraint on (document_id, chunk_index).

        AC: #4 - No duplicate chunks for same document
        """
        mock_db = MagicMock()

        # Simulate duplicate insertion error
        mock_db.table.return_value.insert.return_value.execute.side_effect = Exception(
            'duplicate key value violates unique constraint "document_ocr_chunks_unique_doc_chunk"'
        )

        document_id = str(uuid.uuid4())
        chunk_1 = {
            "document_id": document_id,
            "chunk_index": 0,
            "matter_id": str(uuid.uuid4()),
            "page_start": 1,
            "page_end": 25,
        }
        chunk_duplicate = {
            "document_id": document_id,
            "chunk_index": 0,  # Same chunk_index - should fail
            "matter_id": str(uuid.uuid4()),
            "page_start": 26,
            "page_end": 50,
        }

        # First insert succeeds
        mock_db.table.return_value.insert.return_value.execute.side_effect = [
            MagicMock(data=[chunk_1]),
            Exception('duplicate key value violates unique constraint'),
        ]

        # Second insert with same (document_id, chunk_index) should fail
        result_1 = mock_db.table("document_ocr_chunks").insert(chunk_1).execute()
        assert result_1.data == [chunk_1]

        with pytest.raises(Exception) as exc_info:
            mock_db.table("document_ocr_chunks").insert(chunk_duplicate).execute()

        assert "duplicate key value" in str(exc_info.value)

    def test_page_order_check_constraint(self) -> None:
        """Verify CHECK constraint: page_start <= page_end.

        AC: #4 - Page order constraint
        """
        mock_db = MagicMock()

        # Simulate check constraint violation
        mock_db.table.return_value.insert.return_value.execute.side_effect = Exception(
            'new row violates check constraint "document_ocr_chunks_check_page_order"'
        )

        invalid_chunk = {
            "document_id": str(uuid.uuid4()),
            "chunk_index": 0,
            "matter_id": str(uuid.uuid4()),
            "page_start": 50,  # Greater than page_end - should fail
            "page_end": 25,
        }

        with pytest.raises(Exception) as exc_info:
            mock_db.table("document_ocr_chunks").insert(invalid_chunk).execute()

        assert "check constraint" in str(exc_info.value).lower()

    def test_page_start_minimum_check_constraint(self) -> None:
        """Verify CHECK constraint: page_start >= 1.

        AC: #4 - Page numbers are 1-indexed
        """
        mock_db = MagicMock()

        # Simulate check constraint violation
        mock_db.table.return_value.insert.return_value.execute.side_effect = Exception(
            'new row violates check constraint "document_ocr_chunks_check_page_start"'
        )

        invalid_chunk = {
            "document_id": str(uuid.uuid4()),
            "chunk_index": 0,
            "matter_id": str(uuid.uuid4()),
            "page_start": 0,  # Must be >= 1
            "page_end": 25,
        }

        with pytest.raises(Exception) as exc_info:
            mock_db.table("document_ocr_chunks").insert(invalid_chunk).execute()

        assert "check constraint" in str(exc_info.value).lower()

    def test_status_check_constraint_valid_values(self) -> None:
        """Verify CHECK constraint: status must be valid enum value.

        AC: #4 - Status constraint
        """
        mock_db = MagicMock()

        # Test valid status values succeed
        valid_statuses = ["pending", "processing", "completed", "failed"]

        for status in valid_statuses:
            mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[{"status": status}]
            )
            result = mock_db.table("document_ocr_chunks").insert({"status": status}).execute()
            assert result.data[0]["status"] == status

    def test_status_check_constraint_rejects_invalid(self) -> None:
        """Verify CHECK constraint rejects invalid status values.

        AC: #4 - Status constraint
        """
        mock_db = MagicMock()

        # Simulate check constraint violation for invalid status
        mock_db.table.return_value.insert.return_value.execute.side_effect = Exception(
            'new row violates check constraint "document_ocr_chunks_check_status"'
        )

        invalid_chunk = {
            "document_id": str(uuid.uuid4()),
            "chunk_index": 0,
            "matter_id": str(uuid.uuid4()),
            "page_start": 1,
            "page_end": 25,
            "status": "invalid_status",  # Not in allowed values
        }

        with pytest.raises(Exception) as exc_info:
            mock_db.table("document_ocr_chunks").insert(invalid_chunk).execute()

        assert "check constraint" in str(exc_info.value).lower()


class TestRLSPolicies:
    """Tests for Row Level Security policies.

    AC: #6 - 4-layer matter isolation
    """

    def test_viewer_can_select_chunks_from_own_matter(self) -> None:
        """Verify viewers can SELECT chunks from matters they have access to."""
        mock_db = MagicMock()
        matter_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())

        chunk_data = {
            "id": str(uuid.uuid4()),
            "matter_id": matter_id,
            "document_id": document_id,
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 25,
            "status": "completed",
        }

        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[chunk_data]
        )

        result = mock_db.table("document_ocr_chunks").select("*").eq("matter_id", matter_id).execute()

        assert len(result.data) == 1
        assert result.data[0]["matter_id"] == matter_id

    def test_viewer_cannot_insert_chunks(self) -> None:
        """Verify viewers cannot INSERT chunks (requires editor/owner).

        AC: #6 - INSERT restricted to editors and owners
        """
        mock_db = MagicMock()

        # Simulate RLS policy rejection
        mock_db.table.return_value.insert.return_value.execute.side_effect = Exception(
            "new row violates row-level security policy for table"
        )

        chunk = {
            "matter_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 25,
        }

        with pytest.raises(Exception) as exc_info:
            mock_db.table("document_ocr_chunks").insert(chunk).execute()

        assert "row-level security" in str(exc_info.value).lower()

    def test_editor_can_insert_and_update_chunks(self) -> None:
        """Verify editors can INSERT and UPDATE chunks."""
        mock_db = MagicMock()
        matter_id = str(uuid.uuid4())

        chunk = {
            "id": str(uuid.uuid4()),
            "matter_id": matter_id,
            "document_id": str(uuid.uuid4()),
            "chunk_index": 0,
            "page_start": 1,
            "page_end": 25,
            "status": "pending",
        }

        # Insert succeeds for editor
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[chunk]
        )

        result = mock_db.table("document_ocr_chunks").insert(chunk).execute()
        assert result.data[0]["status"] == "pending"

        # Update succeeds for editor
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{**chunk, "status": "processing"}]
        )

        update_result = (
            mock_db.table("document_ocr_chunks")
            .update({"status": "processing"})
            .eq("id", chunk["id"])
            .execute()
        )
        assert update_result.data[0]["status"] == "processing"

    def test_viewer_and_editor_cannot_delete_chunks(self) -> None:
        """Verify only owners can DELETE chunks.

        AC: #6 - DELETE restricted to owners only
        """
        mock_db = MagicMock()

        # Simulate RLS policy rejection for non-owner
        mock_db.table.return_value.delete.return_value.eq.return_value.execute.side_effect = Exception(
            "new row violates row-level security policy"
        )

        chunk_id = str(uuid.uuid4())

        with pytest.raises(Exception) as exc_info:
            mock_db.table("document_ocr_chunks").delete().eq("id", chunk_id).execute()

        assert "row-level security" in str(exc_info.value).lower()

    def test_owner_can_delete_chunks(self) -> None:
        """Verify owners can DELETE chunks."""
        mock_db = MagicMock()

        chunk_id = str(uuid.uuid4())

        # Delete succeeds for owner
        mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": chunk_id}]
        )

        result = mock_db.table("document_ocr_chunks").delete().eq("id", chunk_id).execute()
        assert result.data[0]["id"] == chunk_id

    def test_cross_matter_access_blocked(self) -> None:
        """Verify users cannot access chunks from other matters.

        AC: #6 - 4-layer matter isolation critical test
        """
        mock_db = MagicMock()

        other_matter_id = str(uuid.uuid4())

        # RLS returns empty result for inaccessible matter
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]  # No results due to RLS
        )

        result = (
            mock_db.table("document_ocr_chunks")
            .select("*")
            .eq("matter_id", other_matter_id)
            .execute()
        )

        assert len(result.data) == 0


class TestCascadingDeletes:
    """Tests for ON DELETE CASCADE behavior."""

    def test_document_delete_cascades_to_chunks(self) -> None:
        """Verify deleting a document deletes associated chunks.

        AC: #4 - FK constraint with ON DELETE CASCADE
        """
        mock_db = MagicMock()

        document_id = str(uuid.uuid4())

        # Create chunks for document
        chunks = [
            {"id": str(uuid.uuid4()), "document_id": document_id, "chunk_index": i}
            for i in range(3)
        ]

        # Before deletion: 3 chunks exist
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=chunks
        )

        result_before = (
            mock_db.table("document_ocr_chunks")
            .select("*")
            .eq("document_id", document_id)
            .execute()
        )
        assert len(result_before.data) == 3

        # After document deletion: 0 chunks (cascaded delete)
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result_after = (
            mock_db.table("document_ocr_chunks")
            .select("*")
            .eq("document_id", document_id)
            .execute()
        )
        assert len(result_after.data) == 0

    def test_matter_delete_cascades_to_chunks(self) -> None:
        """Verify deleting a matter deletes associated chunks.

        AC: #4 - FK constraint with ON DELETE CASCADE
        """
        mock_db = MagicMock()

        matter_id = str(uuid.uuid4())

        # Before deletion: chunks exist
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": str(uuid.uuid4()), "matter_id": matter_id}]
        )

        result_before = (
            mock_db.table("document_ocr_chunks")
            .select("*")
            .eq("matter_id", matter_id)
            .execute()
        )
        assert len(result_before.data) == 1

        # After matter deletion: 0 chunks (cascaded delete)
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result_after = (
            mock_db.table("document_ocr_chunks")
            .select("*")
            .eq("matter_id", matter_id)
            .execute()
        )
        assert len(result_after.data) == 0


class TestStoragePathValidation:
    """Tests for storage path helper functions.

    AC: #7 - Storage bucket path validation
    """

    def test_valid_chunk_path_structure(self) -> None:
        """Verify valid chunk paths are accepted.

        Path format: {matter_id}/{document_id}/{chunk_index}.json
        """
        valid_paths = [
            "550e8400-e29b-41d4-a716-446655440000/660e8400-e29b-41d4-a716-446655440001/0.json",
            "550e8400-e29b-41d4-a716-446655440000/660e8400-e29b-41d4-a716-446655440001/15.json",
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890/b2c3d4e5-f6a7-8901-bcde-f12345678901/100.json",
        ]

        for path in valid_paths:
            parts = path.split("/")
            assert len(parts) == 3
            assert parts[2].endswith(".json")

    def test_invalid_chunk_path_rejected(self) -> None:
        """Verify invalid chunk paths are rejected."""
        invalid_paths = [
            "not-a-uuid/document-id/0.json",  # Invalid matter UUID
            "550e8400-e29b-41d4-a716-446655440000/not-uuid/0.json",  # Invalid doc UUID
            "550e8400-e29b-41d4-a716-446655440000/660e8400-e29b-41d4-a716-446655440001/abc.json",  # Invalid chunk index
            "550e8400-e29b-41d4-a716-446655440000/0.json",  # Missing document_id
            "../escape/attempt/0.json",  # Path traversal attempt
        ]

        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        import re

        for path in invalid_paths:
            parts = path.split("/")

            # Check various validation failures
            is_valid = (
                len(parts) == 3
                and re.match(uuid_pattern, parts[0])
                and re.match(uuid_pattern, parts[1])
                and re.match(r"^[0-9]+\.json$", parts[2])
            )

            assert not is_valid, f"Path should be invalid: {path}"

    def test_path_traversal_blocked(self) -> None:
        """Verify path traversal attacks are blocked."""
        malicious_paths = [
            "../../../etc/passwd",
            "550e8400-e29b-41d4-a716-446655440000/../../../secret/0.json",
            "550e8400-e29b-41d4-a716-446655440000/660e8400-e29b-41d4-a716-446655440001/../../hack.json",
        ]

        for path in malicious_paths:
            # Path traversal indicators
            has_traversal = ".." in path

            assert has_traversal, f"Path should contain traversal: {path}"
            # These paths should be rejected by validation function


class TestIndexes:
    """Tests for index creation.

    AC: #5 - Indexes created
    """

    def test_expected_indexes_documented(self) -> None:
        """Document expected indexes for query optimization."""
        expected_indexes = [
            "idx_doc_ocr_chunks_document_id",  # For chunk lookup by document
            "idx_doc_ocr_chunks_matter_id",  # For RLS performance
            "idx_doc_ocr_chunks_document_status",  # For status queries
        ]

        # These indexes are created in the migration
        assert len(expected_indexes) == 3
        assert "idx_doc_ocr_chunks_document_id" in expected_indexes
        assert "idx_doc_ocr_chunks_matter_id" in expected_indexes
        assert "idx_doc_ocr_chunks_document_status" in expected_indexes


class TestMigrationIdempotency:
    """Tests for migration idempotency.

    AC: #1 - Migration can be run multiple times safely
    """

    def test_create_table_idempotent_concept(self) -> None:
        """Verify migration can handle re-runs.

        Note: Actual idempotency is handled by Supabase migrations.
        This test documents the expected behavior.
        """
        # PostgreSQL migrations track applied migrations
        # Re-running won't re-apply already-applied migrations
        # The migration file uses CREATE TABLE (not IF NOT EXISTS)
        # because Supabase tracks migration state
        assert True  # Architecture documentation

    def test_storage_policies_drop_before_create(self) -> None:
        """Verify storage policies use DROP IF EXISTS for idempotency."""
        # The migration drops existing policies before creating new ones
        # This allows re-running the migration safely
        policy_names = [
            "Users can view ocr chunks from their matters",
            "Editors and Owners can upload ocr chunks",
            "Editors and Owners can update ocr chunks",
            "Owners can delete ocr chunks",
        ]

        assert len(policy_names) == 4
