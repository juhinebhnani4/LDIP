"""Tests for processing complete email template.

Gap #19: Email Notification on Processing Completion - Task 8

Tests cover:
- Template rendering with success/failure scenarios
- Subject line generation
- HTML and plain text content
"""

import pytest

from app.services.email.templates.processing_complete import (
    render_processing_complete_email,
)


# =============================================================================
# Template Rendering Tests
# =============================================================================


class TestRenderProcessingCompleteEmail:
    """Tests for render_processing_complete_email function."""

    def test_all_successful_subject(self):
        """Test subject line when all documents succeed."""
        subject, _, _ = render_processing_complete_email(
            matter_name="Smith vs Jones",
            doc_count=10,
            success_count=10,
            failed_count=0,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        assert "Smith vs Jones" in subject
        assert "ready" in subject.lower()

    def test_partial_failure_subject(self):
        """Test subject line when some documents fail."""
        subject, _, _ = render_processing_complete_email(
            matter_name="Test Matter",
            doc_count=10,
            success_count=8,
            failed_count=2,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        assert "Test Matter" in subject

    def test_html_contains_matter_name(self):
        """Test HTML content contains matter name."""
        _, html_content, _ = render_processing_complete_email(
            matter_name="Important Case",
            doc_count=5,
            success_count=5,
            failed_count=0,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        assert "Important Case" in html_content

    def test_html_contains_document_counts(self):
        """Test HTML content contains document counts."""
        _, html_content, _ = render_processing_complete_email(
            matter_name="Test",
            doc_count=10,
            success_count=8,
            failed_count=2,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        assert "10" in html_content  # Total
        assert "8" in html_content  # Success

    def test_html_contains_workspace_url(self):
        """Test HTML content contains workspace URL."""
        workspace_url = "https://app.ldip.com/matters/abc-123/documents"
        _, html_content, _ = render_processing_complete_email(
            matter_name="Test",
            doc_count=5,
            success_count=5,
            failed_count=0,
            workspace_url=workspace_url,
        )

        assert workspace_url in html_content

    def test_text_contains_matter_name(self):
        """Test plain text content contains matter name."""
        _, _, text_content = render_processing_complete_email(
            matter_name="Text Test Matter",
            doc_count=5,
            success_count=5,
            failed_count=0,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        assert "Text Test Matter" in text_content

    def test_text_contains_document_counts(self):
        """Test plain text content contains document counts."""
        _, _, text_content = render_processing_complete_email(
            matter_name="Test",
            doc_count=15,
            success_count=12,
            failed_count=3,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        assert "15" in text_content  # Total
        assert "12" in text_content  # Success

    def test_text_contains_workspace_url(self):
        """Test plain text content contains workspace URL."""
        workspace_url = "https://app.ldip.com/matters/xyz-789/documents"
        _, _, text_content = render_processing_complete_email(
            matter_name="Test",
            doc_count=5,
            success_count=5,
            failed_count=0,
            workspace_url=workspace_url,
        )

        assert workspace_url in text_content

    def test_success_message_no_failures(self):
        """Test success message when no documents fail."""
        _, html_content, text_content = render_processing_complete_email(
            matter_name="Test",
            doc_count=5,
            success_count=5,
            failed_count=0,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        # Should show success message
        assert "processed successfully" in text_content.lower()

    def test_partial_failure_message(self):
        """Test message when some documents fail."""
        _, html_content, text_content = render_processing_complete_email(
            matter_name="Test",
            doc_count=10,
            success_count=7,
            failed_count=3,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        # Should mention attention needed
        assert "attention" in text_content.lower() or "7 document" in text_content

    def test_single_document_grammar(self):
        """Test correct grammar for single document."""
        _, html_content, text_content = render_processing_complete_email(
            matter_name="Test",
            doc_count=1,
            success_count=1,
            failed_count=0,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        # Should use singular "document" not "documents"
        assert "1 document" in text_content or "document processed" in text_content.lower()

    def test_html_is_valid_structure(self):
        """Test HTML has proper structure."""
        _, html_content, _ = render_processing_complete_email(
            matter_name="Test",
            doc_count=5,
            success_count=5,
            failed_count=0,
            workspace_url="https://app.ldip.com/matters/123/documents",
        )

        # Basic HTML structure checks
        assert html_content.startswith("<!DOCTYPE html>")
        assert "<html" in html_content
        assert "</html>" in html_content
        assert "<body" in html_content
        assert "</body>" in html_content
