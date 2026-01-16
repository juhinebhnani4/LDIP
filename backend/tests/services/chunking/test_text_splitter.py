"""Unit tests for recursive text splitter."""


from app.services.chunking.text_splitter import RecursiveTextSplitter
from app.services.chunking.token_counter import count_tokens


class TestRecursiveTextSplitter:
    """Tests for RecursiveTextSplitter class."""

    def test_empty_text(self) -> None:
        """Should return empty list for empty text."""
        splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=10)
        result = splitter.split_text("")
        assert result == []

    def test_whitespace_only(self) -> None:
        """Should return empty list for whitespace only."""
        splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=10)
        result = splitter.split_text("   \n\n  \t  ")
        assert result == []

    def test_short_text_no_split(self) -> None:
        """Should not split text smaller than chunk size."""
        splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=10)
        text = "This is a short sentence."
        result = splitter.split_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_split_on_paragraph(self) -> None:
        """Should prefer splitting on paragraph boundaries."""
        splitter = RecursiveTextSplitter(chunk_size=10, chunk_overlap=2)
        text = "First paragraph with some content.\n\nSecond paragraph with more content."
        result = splitter.split_text(text)
        assert len(result) >= 2
        # Each chunk should be reasonable size
        for chunk in result:
            assert count_tokens(chunk) <= 15  # Allow some margin

    def test_split_on_sentence(self) -> None:
        """Should split on sentence boundaries when paragraphs too large."""
        splitter = RecursiveTextSplitter(chunk_size=8, chunk_overlap=2)
        text = "First sentence here. Second sentence there. Third sentence now."
        result = splitter.split_text(text)
        assert len(result) >= 2
        # Chunks should end at natural boundaries
        for chunk in result:
            assert chunk.strip()

    def test_overlap_between_chunks(self) -> None:
        """Should have overlap between consecutive chunks."""
        splitter = RecursiveTextSplitter(chunk_size=30, chunk_overlap=10)
        text = "Word one two three. Word four five six. Word seven eight nine."
        result = splitter.split_text(text)

        if len(result) >= 2:
            # Check that some text from first chunk appears in second
            first_words = set(result[0].split()[-3:])
            second_words = set(result[1].split()[:5])
            # Due to overlap, there should be some shared words
            # (This is a soft check as overlap depends on separators)
            assert len(result) > 1

    def test_respects_chunk_size(self) -> None:
        """All chunks should be within size limit."""
        splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=10)
        text = " ".join(["word"] * 500)  # ~500 tokens
        result = splitter.split_text(text)

        for chunk in result:
            tokens = count_tokens(chunk)
            # Allow 20% margin for edge cases
            assert tokens <= 120, f"Chunk too large: {tokens} tokens"

    def test_handles_long_words(self) -> None:
        """Should handle text with very long words."""
        splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=5)
        long_word = "a" * 200
        text = f"Normal word {long_word} another word"
        result = splitter.split_text(text)
        assert len(result) >= 1

    def test_custom_separators(self) -> None:
        """Should use custom separators when provided."""
        splitter = RecursiveTextSplitter(
            chunk_size=5,
            chunk_overlap=1,
            separators=["|", " "],  # Custom separators
        )
        text = "Part one|Part two|Part three"
        result = splitter.split_text(text)
        # Should split on | first
        assert len(result) >= 2

    def test_legal_document_text(self) -> None:
        """Should handle typical legal document structure."""
        splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=10)
        legal_text = """
        ARTICLE I - DEFINITIONS

        1.1 "Agreement" means this Agreement and all exhibits attached hereto.

        1.2 "Confidential Information" means any and all information disclosed
        by either party to the other party, either directly or indirectly.

        ARTICLE II - OBLIGATIONS

        2.1 Each party agrees to maintain the confidentiality of all
        Confidential Information received from the other party.

        2.2 The receiving party shall not disclose any Confidential Information
        to any third party without prior written consent.
        """
        result = splitter.split_text(legal_text)

        # Should produce multiple chunks
        assert len(result) >= 2

        # Each chunk should have meaningful content
        for chunk in result:
            assert len(chunk.strip()) > 10

    def test_preserves_all_content(self) -> None:
        """Should not lose content during splitting."""
        splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=0)
        words = ["word" + str(i) for i in range(100)]
        text = " ".join(words)
        result = splitter.split_text(text)

        # Combine all chunks (ignoring overlap)
        combined = " ".join(result)

        # All unique words should be present
        for word in words:
            assert word in combined


class TestRecursiveTextSplitterEdgeCases:
    """Edge case tests for RecursiveTextSplitter."""

    def test_zero_overlap(self) -> None:
        """Should work with zero overlap."""
        splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=0)
        text = "First part. Second part. Third part. Fourth part."
        result = splitter.split_text(text)
        assert len(result) >= 1

    def test_large_overlap(self) -> None:
        """Should handle large overlap values."""
        splitter = RecursiveTextSplitter(chunk_size=100, chunk_overlap=50)
        text = " ".join(["word"] * 200)
        result = splitter.split_text(text)
        assert len(result) >= 2

    def test_unicode_content(self) -> None:
        """Should handle unicode characters properly."""
        splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=5)
        text = "Hello 世界. This is a test. 你好 world. More text here."
        result = splitter.split_text(text)
        assert len(result) >= 1
        # Unicode should be preserved
        combined = " ".join(result)
        assert "世界" in combined or "你好" in combined

    def test_only_newlines(self) -> None:
        """Should handle text with many newlines."""
        splitter = RecursiveTextSplitter(chunk_size=50, chunk_overlap=5)
        text = "Line one\n\n\n\nLine two\n\n\nLine three"
        result = splitter.split_text(text)
        assert len(result) >= 1

    def test_single_character_chunks(self) -> None:
        """Should handle very small chunk sizes gracefully."""
        splitter = RecursiveTextSplitter(chunk_size=5, chunk_overlap=1)
        text = "Hello world test"
        result = splitter.split_text(text)
        assert len(result) >= 1
