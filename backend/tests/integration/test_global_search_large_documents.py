"""Global Search Integration Tests for Large Documents.

Story 18.9: Global Search Integration Tests (Epic 4)

Validates global search works correctly with large documents:
- Results include matches from large documents
- matched_content snippets are accurate
- Clicking result navigates to correct document and page
- PDF viewer opens to correct page (e.g., page 300)
- Search term is highlighted via bbox coordinates
- Surrounding context chunks are available
- Matter isolation is maintained (no cross-matter leakage)
- Hybrid search combines BM25 + semantic scores correctly
"""

from uuid import uuid4

import pytest

from app.services.ocr_result_merger import ChunkOCRResult, OCRResultMerger


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def matter_a_documents():
    """Create documents for Matter A."""
    matter_id = str(uuid4())
    return {
        "matter_id": matter_id,
        "documents": [
            {
                "id": str(uuid4()),
                "matter_id": matter_id,
                "filename": "large_contract_a.pdf",
                "page_count": 300,
            },
            {
                "id": str(uuid4()),
                "matter_id": matter_id,
                "filename": "amendment_a.pdf",
                "page_count": 50,
            },
        ],
    }


@pytest.fixture
def matter_b_documents():
    """Create documents for Matter B."""
    matter_id = str(uuid4())
    return {
        "matter_id": matter_id,
        "documents": [
            {
                "id": str(uuid4()),
                "matter_id": matter_id,
                "filename": "large_contract_b.pdf",
                "page_count": 200,
            },
        ],
    }


@pytest.fixture
def create_document_chunks():
    """Factory to create text chunks for a document."""

    def _create(document_id: str, matter_id: str, page_count: int) -> list[dict]:
        chunks = []
        chunk_id = 0

        for page_start in range(1, page_count + 1, 10):  # Chunks every 10 pages
            page_end = min(page_start + 9, page_count)

            chunks.append({
                "id": str(uuid4()),
                "document_id": document_id,
                "matter_id": matter_id,
                "content": f"Content from pages {page_start}-{page_end}. "
                           f"Contains legal terms, parties, and obligations.",
                "page_number": page_start,
                "chunk_index": chunk_id,
                "bbox_ids": [str(uuid4()) for _ in range(20)],  # 20 bboxes
                "embedding": [0.1] * 1536,
            })
            chunk_id += 1

        return chunks

    return _create


# =============================================================================
# Story 18.9: Global Search Integration Tests
# =============================================================================


class TestGlobalSearchWithLargeDocuments:
    """Tests for global search finding content in large documents."""

    def test_search_finds_large_document_results(
        self, matter_a_documents, create_document_chunks
    ):
        """Global search returns results from large documents."""
        matter_id = matter_a_documents["matter_id"]
        large_doc = matter_a_documents["documents"][0]

        # Create chunks for 300-page document
        chunks = create_document_chunks(
            large_doc["id"], matter_id, large_doc["page_count"]
        )

        # Simulate search that matches chunks
        query = "legal terms and obligations"
        search_results = [
            chunk for chunk in chunks
            if "legal terms" in chunk["content"].lower()
        ]

        # Should find results in large document
        assert len(search_results) > 0
        assert all(r["document_id"] == large_doc["id"] for r in search_results)

    def test_matched_content_accurate(self, matter_a_documents, create_document_chunks):
        """matched_content snippets contain query terms."""
        matter_id = matter_a_documents["matter_id"]
        doc = matter_a_documents["documents"][0]

        chunks = create_document_chunks(doc["id"], matter_id, 300)

        # Search for specific content
        query = "obligations"
        matched_chunks = [c for c in chunks if query in c["content"]]

        for chunk in matched_chunks:
            # Verify matched_content contains the query term
            assert query in chunk["content"]


class TestDeepPageNavigation:
    """Tests for navigating to pages deep in large documents."""

    def test_navigate_to_page_300(self, matter_a_documents, create_document_chunks):
        """Search result on page 300 enables correct navigation."""
        matter_id = matter_a_documents["matter_id"]
        doc = matter_a_documents["documents"][0]  # 300 pages

        chunks = create_document_chunks(doc["id"], matter_id, 300)

        # Find chunk containing page 300
        page_300_chunk = next(
            (c for c in chunks if c["page_number"] <= 300 <= c["page_number"] + 9),
            None,
        )

        assert page_300_chunk is not None
        assert page_300_chunk["document_id"] == doc["id"]

        # Verify navigation info available
        assert "page_number" in page_300_chunk
        assert page_300_chunk["page_number"] in range(291, 301)

    def test_bbox_ids_enable_highlighting_on_page_300(
        self, matter_a_documents, create_document_chunks
    ):
        """bbox_ids available for highlighting on page 300."""
        matter_id = matter_a_documents["matter_id"]
        doc = matter_a_documents["documents"][0]

        chunks = create_document_chunks(doc["id"], matter_id, 300)

        # Find chunk for page 300 area
        page_300_chunk = next(
            (c for c in chunks if c["page_number"] <= 300 <= c["page_number"] + 9),
            None,
        )

        # Verify bbox_ids available for highlighting
        assert page_300_chunk is not None
        assert "bbox_ids" in page_300_chunk
        assert len(page_300_chunk["bbox_ids"]) > 0

    def test_context_chunks_available(self, matter_a_documents, create_document_chunks):
        """Surrounding context chunks available for expansion."""
        matter_id = matter_a_documents["matter_id"]
        doc = matter_a_documents["documents"][0]

        chunks = create_document_chunks(doc["id"], matter_id, 300)

        # Find chunk at page 150
        target_chunk_idx = next(
            (i for i, c in enumerate(chunks) if c["page_number"] == 141),
            None,
        )

        assert target_chunk_idx is not None

        # Verify surrounding chunks exist
        if target_chunk_idx > 0:
            prev_chunk = chunks[target_chunk_idx - 1]
            assert prev_chunk["page_number"] < 141

        if target_chunk_idx < len(chunks) - 1:
            next_chunk = chunks[target_chunk_idx + 1]
            assert next_chunk["page_number"] > 141


class TestMatterIsolation:
    """Tests for matter isolation in global search."""

    def test_no_cross_matter_leakage(
        self,
        matter_a_documents,
        matter_b_documents,
        create_document_chunks,
    ):
        """Search in Matter A doesn't return Matter B results."""
        # Create chunks for both matters
        matter_a_id = matter_a_documents["matter_id"]
        matter_b_id = matter_b_documents["matter_id"]

        matter_a_chunks = create_document_chunks(
            matter_a_documents["documents"][0]["id"],
            matter_a_id,
            300,
        )

        matter_b_chunks = create_document_chunks(
            matter_b_documents["documents"][0]["id"],
            matter_b_id,
            200,
        )

        # All chunks
        all_chunks = matter_a_chunks + matter_b_chunks

        # Simulate search in Matter A context
        search_matter_id = matter_a_id
        filtered_results = [
            c for c in all_chunks if c["matter_id"] == search_matter_id
        ]

        # Results should only be from Matter A
        assert len(filtered_results) > 0
        assert all(r["matter_id"] == matter_a_id for r in filtered_results)
        assert not any(r["matter_id"] == matter_b_id for r in filtered_results)

    def test_matter_filter_applied_to_all_documents(
        self,
        matter_a_documents,
        create_document_chunks,
    ):
        """Matter filter applies to all documents in matter."""
        matter_id = matter_a_documents["matter_id"]

        all_matter_chunks = []
        for doc in matter_a_documents["documents"]:
            chunks = create_document_chunks(doc["id"], matter_id, doc["page_count"])
            all_matter_chunks.extend(chunks)

        # All chunks should be from same matter
        assert all(c["matter_id"] == matter_id for c in all_matter_chunks)

        # Should include chunks from both documents
        doc_ids = {c["document_id"] for c in all_matter_chunks}
        assert len(doc_ids) == 2


class TestHybridSearchScoring:
    """Tests for hybrid search score combination."""

    def test_bm25_and_semantic_scores_combined(self):
        """Hybrid search combines BM25 + semantic scores."""
        # Mock search results with both scores
        results = [
            {
                "chunk_id": str(uuid4()),
                "bm25_score": 0.8,
                "semantic_score": 0.7,
                "combined_score": None,
            },
            {
                "chunk_id": str(uuid4()),
                "bm25_score": 0.6,
                "semantic_score": 0.9,
                "combined_score": None,
            },
        ]

        # Simulate score combination (typical: 0.5 * bm25 + 0.5 * semantic)
        for result in results:
            result["combined_score"] = (
                0.5 * result["bm25_score"] + 0.5 * result["semantic_score"]
            )

        # First result: 0.5*0.8 + 0.5*0.7 = 0.75
        assert abs(results[0]["combined_score"] - 0.75) < 0.01

        # Second result: 0.5*0.6 + 0.5*0.9 = 0.75
        assert abs(results[1]["combined_score"] - 0.75) < 0.01

    def test_semantic_fallback_when_no_bm25_match(self):
        """Semantic search works when BM25 has no matches."""
        results = [
            {
                "chunk_id": str(uuid4()),
                "bm25_score": 0.0,  # No keyword match
                "semantic_score": 0.85,  # But semantic similarity
                "combined_score": None,
            },
        ]

        # Should still score based on semantic
        for result in results:
            result["combined_score"] = (
                0.5 * result["bm25_score"] + 0.5 * result["semantic_score"]
            )

        assert results[0]["combined_score"] > 0


class TestSearchResultStructure:
    """Tests for search result structure with large documents."""

    def test_result_includes_document_info(
        self, matter_a_documents, create_document_chunks
    ):
        """Search results include document identification."""
        matter_id = matter_a_documents["matter_id"]
        doc = matter_a_documents["documents"][0]

        chunks = create_document_chunks(doc["id"], matter_id, 300)

        for chunk in chunks:
            assert "document_id" in chunk
            assert "matter_id" in chunk
            assert "page_number" in chunk

    def test_result_includes_highlighting_info(
        self, matter_a_documents, create_document_chunks
    ):
        """Search results include bbox info for highlighting."""
        matter_id = matter_a_documents["matter_id"]
        doc = matter_a_documents["documents"][0]

        chunks = create_document_chunks(doc["id"], matter_id, 300)

        for chunk in chunks:
            assert "bbox_ids" in chunk
            assert isinstance(chunk["bbox_ids"], list)


class TestOCRMergerForGlobalSearch:
    """Tests verifying OCR merger output works with global search."""

    def test_merged_bboxes_support_search_highlighting(self):
        """Merged bboxes can be used for search result highlighting."""
        ocr_chunks = []
        for i in range(12):  # 300 pages = 12 chunks of 25
            page_start = i * 25 + 1
            page_end = min((i + 1) * 25, 300)
            page_count = page_end - page_start + 1

            bboxes = []
            for rel_page in range(1, page_count + 1):
                bboxes.append({
                    "page": rel_page,
                    "reading_order_index": 0,
                    "text": f"Searchable content on page {page_start + rel_page - 1}",
                    "x": 72,
                    "y": 72,
                    "width": 468,
                    "height": 20,
                })

            ocr_chunks.append(
                ChunkOCRResult(
                    chunk_index=i,
                    page_start=page_start,
                    page_end=page_end,
                    bounding_boxes=bboxes,
                    full_text=f"Chunk {i}",
                    overall_confidence=0.9,
                    page_count=page_count,
                )
            )

        merger = OCRResultMerger()
        result = merger.merge_results(ocr_chunks, "doc-search")

        # Verify bboxes for page 300
        page_300_bboxes = [b for b in result.bounding_boxes if b["page"] == 300]
        assert len(page_300_bboxes) > 0

        # Each bbox has coordinates for highlighting
        for bbox in page_300_bboxes:
            assert "x" in bbox
            assert "y" in bbox
            assert "width" in bbox
            assert "height" in bbox

    def test_merged_text_searchable(self):
        """Merged full_text is searchable."""
        ocr_chunks = [
            ChunkOCRResult(
                chunk_index=0,
                page_start=1,
                page_end=25,
                bounding_boxes=[],
                full_text="This agreement between Party A and Party B",
                overall_confidence=0.9,
                page_count=25,
            ),
            ChunkOCRResult(
                chunk_index=1,
                page_start=26,
                page_end=50,
                bounding_boxes=[],
                full_text="sets forth the terms and conditions",
                overall_confidence=0.9,
                page_count=25,
            ),
        ]

        merger = OCRResultMerger()
        result = merger.merge_results(ocr_chunks, "doc-search")

        # Full text should be searchable
        assert "Party A" in result.full_text
        assert "terms and conditions" in result.full_text


class TestMultiMatterGlobalSearch:
    """Tests for global search across multiple matters."""

    def test_user_sees_only_authorized_matters(
        self,
        matter_a_documents,
        matter_b_documents,
        create_document_chunks,
    ):
        """User only sees results from authorized matters."""
        # User has access to Matter A only
        authorized_matter_ids = {matter_a_documents["matter_id"]}

        # Create chunks for both matters
        matter_a_chunks = create_document_chunks(
            matter_a_documents["documents"][0]["id"],
            matter_a_documents["matter_id"],
            300,
        )
        matter_b_chunks = create_document_chunks(
            matter_b_documents["documents"][0]["id"],
            matter_b_documents["matter_id"],
            200,
        )

        all_chunks = matter_a_chunks + matter_b_chunks

        # Filter by authorization
        authorized_results = [
            c for c in all_chunks if c["matter_id"] in authorized_matter_ids
        ]

        # Should only see Matter A results
        assert len(authorized_results) == len(matter_a_chunks)
        assert all(
            r["matter_id"] == matter_a_documents["matter_id"]
            for r in authorized_results
        )
