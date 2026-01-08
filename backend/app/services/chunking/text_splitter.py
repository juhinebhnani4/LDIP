"""Recursive text splitter for semantic chunking.

Implements a LangChain-inspired recursive text splitter that preserves
semantic boundaries (paragraphs, sentences) when splitting text into chunks.
"""

from collections.abc import Callable

import structlog

from app.services.chunking.token_counter import count_tokens

logger = structlog.get_logger(__name__)

# Separator hierarchy: prefer semantic boundaries over arbitrary splits
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


class RecursiveTextSplitter:
    """Recursively splits text by trying separators in order.

    Preserves sentence/paragraph boundaries when possible by trying
    semantic separators before falling back to character-level splits.

    Attributes:
        chunk_size: Target size for each chunk (in tokens).
        chunk_overlap: Number of tokens to overlap between chunks.
        length_function: Function to measure text length (defaults to token count).
        separators: List of separators to try in order.
    """

    def __init__(
        self,
        chunk_size: int,
        chunk_overlap: int,
        length_function: Callable[[str], int] | None = None,
        separators: list[str] | None = None,
    ):
        """Initialize the text splitter.

        Args:
            chunk_size: Target chunk size in tokens.
            chunk_overlap: Token overlap between consecutive chunks.
            length_function: Function to measure text length. Defaults to count_tokens.
            separators: Ordered list of separators to try. Defaults to semantic hierarchy.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function or count_tokens
        self.separators = separators or DEFAULT_SEPARATORS

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks respecting size limits and separators.

        Args:
            text: Text to split into chunks.

        Returns:
            List of text chunks, each within the chunk_size limit.
        """
        if not text or not text.strip():
            return []

        return self._split_text(text, self.separators)

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursive splitting with separator hierarchy.

        Args:
            text: Text to split.
            separators: Remaining separators to try.

        Returns:
            List of chunks.
        """
        final_chunks: list[str] = []

        # Find the best separator for this text
        separator = separators[-1] if separators else ""
        new_separators: list[str] = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1 :]
                break

        # Split by separator
        if separator:
            splits = text.split(separator)
        else:
            # Character-level split
            splits = list(text)

        # Merge splits into chunks
        good_splits: list[str] = []
        _separator = "" if separator == "" else separator

        for split in splits:
            if not split:
                continue

            split_len = self.length_function(split)

            # If single split exceeds chunk size, recursively split it
            if split_len > self.chunk_size:
                if good_splits:
                    merged = self._merge_splits(good_splits, _separator)
                    final_chunks.extend(merged)
                    good_splits = []

                # Recurse with remaining separators
                if new_separators:
                    sub_chunks = self._split_text(split, new_separators)
                    final_chunks.extend(sub_chunks)
                else:
                    # No more separators - force split at chunk_size
                    forced = self._force_split(split)
                    final_chunks.extend(forced)
            else:
                good_splits.append(split)

        # Process remaining good splits
        if good_splits:
            merged = self._merge_splits(good_splits, _separator)
            final_chunks.extend(merged)

        return [chunk for chunk in final_chunks if chunk.strip()]

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """Merge splits into chunks with proper overlap.

        Args:
            splits: List of text segments to merge.
            separator: Separator to use when joining segments.

        Returns:
            List of merged chunks.
        """
        if not splits:
            return []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for split in splits:
            split_len = self.length_function(split)

            # Calculate potential length if we add this split
            sep_len = self.length_function(separator) if current_chunk else 0
            potential_length = current_length + split_len + sep_len

            if potential_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = separator.join(current_chunk)
                chunks.append(chunk_text)

                # Apply overlap: keep last segments that fit within overlap
                overlap_splits = self._get_overlap_splits(current_chunk, separator)
                current_chunk = overlap_splits
                current_length = self.length_function(separator.join(current_chunk)) if current_chunk else 0

            current_chunk.append(split)
            current_length = self.length_function(separator.join(current_chunk))

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = separator.join(current_chunk)
            chunks.append(chunk_text)

        return chunks

    def _get_overlap_splits(self, splits: list[str], separator: str) -> list[str]:
        """Get splits to include in overlap with next chunk.

        Args:
            splits: Segments from the current chunk.
            separator: Separator used to join segments.

        Returns:
            List of segments to carry over for overlap.
        """
        if not splits or self.chunk_overlap <= 0:
            return []

        overlap_splits: list[str] = []
        overlap_length = 0

        # Work backwards through splits
        for split in reversed(splits):
            test_length = overlap_length + self.length_function(split)
            if overlap_splits:
                test_length += self.length_function(separator)

            if test_length <= self.chunk_overlap:
                overlap_splits.insert(0, split)
                overlap_length = test_length
            else:
                break

        return overlap_splits

    def _force_split(self, text: str) -> list[str]:
        """Force split text at exact chunk_size when no separators work.

        This is a fallback for very long text without natural break points.

        Args:
            text: Text that exceeds chunk_size with no separators.

        Returns:
            List of forced chunks.
        """
        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            # Binary search for the right cut point
            end = min(start + self.chunk_size * 4, text_len)  # Characters estimate

            # Refine using token count
            while end > start:
                chunk = text[start:end]
                if self.length_function(chunk) <= self.chunk_size:
                    break
                end -= max(1, (end - start) // 10)

            if end <= start:
                # Fallback: take at least one character
                end = start + 1

            chunks.append(text[start:end])

            # Calculate overlap in characters (approximate)
            overlap_chars = max(0, int(self.chunk_overlap * 4))  # 4 chars per token estimate
            start = max(start + 1, end - overlap_chars)

        return chunks
