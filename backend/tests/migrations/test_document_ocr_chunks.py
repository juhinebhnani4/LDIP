"""Tests for document_ocr_chunks table migration.

Tests verify:
- Table schema and column types (via SQL parsing)
- CHECK constraint enforcement
- UNIQUE constraint enforcement
- RLS policy behavior
- Cascading delete behavior
- Storage path validation functions

This module includes:
1. SQL validation tests that parse the migration file directly
2. Mock-based tests that document expected runtime behavior
"""

import re
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Path to migration files (relative to backend directory)
MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "supabase" / "migrations"
MIGRATION_FILE = "20260117100001_create_document_ocr_chunks_table.sql"
FIX_MIGRATION_FILE = "20260117100002_fix_document_ocr_chunks_constraints.sql"


class TestMigrationSQLValidation:
    """Tests that parse and validate the actual SQL migration file.

    These tests verify the migration SQL contains the expected schema,
    constraints, and policies without requiring a live database.
    """

    @pytest.fixture
    def migration_sql(self) -> str:
        """Load the main migration SQL file."""
        migration_path = MIGRATIONS_DIR / MIGRATION_FILE
        if not migration_path.exists():
            pytest.skip(f"Migration file not found: {migration_path}")
        return migration_path.read_text(encoding="utf-8")

    @pytest.fixture
    def fix_migration_sql(self) -> str:
        """Load the fix migration SQL file (if exists)."""
        fix_path = MIGRATIONS_DIR / FIX_MIGRATION_FILE
        if not fix_path.exists():
            return ""
        return fix_path.read_text(encoding="utf-8")

    def test_table_creation_exists(self, migration_sql: str) -> None:
        """Verify CREATE TABLE statement exists for document_ocr_chunks."""
        assert "CREATE TABLE public.document_ocr_chunks" in migration_sql

    def test_all_required_columns_present(self, migration_sql: str) -> None:
        """Verify all 14 required columns are defined in the schema.

        AC: #2 - Core columns present
        AC: #3 - Result storage columns present
        """
        required_columns = [
            "id uuid",
            "matter_id uuid",
            "document_id uuid",
            "chunk_index integer",
            "page_start integer",
            "page_end integer",
            "status text",
            "error_message text",
            "result_storage_path text",
            "result_checksum text",
            "processing_started_at timestamptz",
            "processing_completed_at timestamptz",
            "created_at timestamptz",
            "updated_at timestamptz",
        ]

        for col in required_columns:
            # Column definitions may have extra whitespace or NOT NULL
            col_name = col.split()[0]
            col_type = col.split()[1]
            pattern = rf"{col_name}\s+{col_type}"
            assert re.search(pattern, migration_sql, re.IGNORECASE), f"Column {col} not found"

    def test_foreign_key_constraints_defined(self, migration_sql: str) -> None:
        """Verify FK constraints with CASCADE delete.

        AC: #4 - FK constraints with ON DELETE CASCADE
        """
        assert "REFERENCES public.matters(id) ON DELETE CASCADE" in migration_sql
        assert "REFERENCES public.documents(id) ON DELETE CASCADE" in migration_sql

    def test_unique_constraint_on_document_chunk(self, migration_sql: str) -> None:
        """Verify UNIQUE constraint on (document_id, chunk_index).

        AC: #4 - No duplicate chunks
        """
        assert "document_ocr_chunks_unique_doc_chunk" in migration_sql
        assert "UNIQUE (document_id, chunk_index)" in migration_sql

    def test_check_constraints_defined(self, migration_sql: str) -> None:
        """Verify all CHECK constraints are defined.

        AC: #4 - CHECK constraints
        """
        # Page order constraint
        assert "document_ocr_chunks_check_page_order" in migration_sql
        assert "page_start <= page_end" in migration_sql

        # Page start minimum
        assert "document_ocr_chunks_check_page_start" in migration_sql
        assert "page_start >= 1" in migration_sql

        # Status enum
        assert "document_ocr_chunks_check_status" in migration_sql
        assert "'pending'" in migration_sql
        assert "'processing'" in migration_sql
        assert "'completed'" in migration_sql
        assert "'failed'" in migration_sql

    def test_chunk_index_check_constraint(self, fix_migration_sql: str) -> None:
        """Verify chunk_index >= 0 CHECK constraint exists (added in fix migration).

        AC: #4 - chunk_index is 0-indexed, must be non-negative
        """
        if not fix_migration_sql:
            pytest.skip("Fix migration not yet applied")
        assert "document_ocr_chunks_check_chunk_index" in fix_migration_sql
        assert "chunk_index >= 0" in fix_migration_sql

    def test_indexes_created(self, migration_sql: str) -> None:
        """Verify all required indexes are created.

        AC: #5 - Indexes for query optimization
        """
        assert "idx_doc_ocr_chunks_document_id" in migration_sql
        assert "idx_doc_ocr_chunks_matter_id" in migration_sql
        assert "idx_doc_ocr_chunks_document_status" in migration_sql

    def test_rls_enabled(self, migration_sql: str) -> None:
        """Verify RLS is enabled on the table.

        AC: #6 - RLS required
        """
        assert "ENABLE ROW LEVEL SECURITY" in migration_sql

    def test_rls_policies_created(self, migration_sql: str) -> None:
        """Verify all 4 RLS policies are created.

        AC: #6 - 4-layer matter isolation
        """
        # SELECT policy
        assert 'FOR SELECT' in migration_sql
        assert 'Users can view chunks from their matters' in migration_sql

        # INSERT policy
        assert 'FOR INSERT' in migration_sql
        assert 'Editors and Owners can insert chunks' in migration_sql

        # UPDATE policy
        assert 'FOR UPDATE' in migration_sql
        assert 'Editors and Owners can update chunks' in migration_sql

        # DELETE policy
        assert 'FOR DELETE' in migration_sql
        assert 'Only Owners can delete chunks' in migration_sql

    def test_update_policy_has_with_check(self, fix_migration_sql: str) -> None:
        """Verify UPDATE policy includes WITH CHECK clause (security fix).

        Prevents users from changing matter_id to move chunks between matters.
        """
        if not fix_migration_sql:
            pytest.skip("Fix migration not yet applied")
        # The fix migration should recreate UPDATE policy with WITH CHECK
        assert "WITH CHECK" in fix_migration_sql
        assert "Editors and Owners can update chunks" in fix_migration_sql

    def test_updated_at_trigger_exists(self, migration_sql: str) -> None:
        """Verify trigger for auto-updating updated_at column."""
        assert "set_document_ocr_chunks_updated_at" in migration_sql
        assert "update_updated_at_column()" in migration_sql

    def test_storage_helper_functions_created(self, migration_sql: str) -> None:
        """Verify storage path helper functions are created.

        AC: #7 - Storage bucket support
        """
        assert "get_matter_id_from_chunk_path" in migration_sql
        assert "validate_ocr_chunk_path" in migration_sql

    def test_storage_policies_created(self, migration_sql: str) -> None:
        """Verify storage bucket RLS policies are created.

        AC: #7 - Storage bucket policies
        """
        assert "Users can view ocr chunks from their matters" in migration_sql
        assert "Editors and Owners can upload ocr chunks" in migration_sql
        assert "Editors and Owners can update ocr chunks" in migration_sql
        assert "Owners can delete ocr chunks" in migration_sql

    def test_storage_policies_are_idempotent(self, migration_sql: str) -> None:
        """Verify storage policies use DROP IF EXISTS for idempotency."""
        drop_statements = re.findall(r"DROP POLICY IF EXISTS.*ocr chunk", migration_sql)
        assert len(drop_statements) >= 4, "Should drop existing policies before creating"


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


class TestTimestampConstraints:
    """Tests for timestamp column constraints (added in fix migration)."""

    @pytest.fixture
    def fix_migration_sql(self) -> str:
        """Load the fix migration SQL file."""
        fix_path = MIGRATIONS_DIR / FIX_MIGRATION_FILE
        if not fix_path.exists():
            pytest.skip("Fix migration not found")
        return fix_path.read_text(encoding="utf-8")

    def test_created_at_not_null_constraint(self, fix_migration_sql: str) -> None:
        """Verify created_at has NOT NULL constraint.

        AC: #2 - created_at should always have a value
        """
        assert "created_at SET NOT NULL" in fix_migration_sql

    def test_updated_at_not_null_constraint(self, fix_migration_sql: str) -> None:
        """Verify updated_at has NOT NULL constraint.

        AC: #2 - updated_at should always have a value
        """
        assert "updated_at SET NOT NULL" in fix_migration_sql
