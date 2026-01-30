"""Citation verification against indexed acts.

Verifies that citations reference real sections in actual acts.
"""

from pathlib import Path
from typing import Optional

import structlog

from src.core.config import settings
from src.core.models import (
    Citation,
    VerificationResult,
    VerificationStatus,
)
from src.core.utils import normalize_act_name
from .indexer import ActsIndexer

logger = structlog.get_logger(__name__)


class ActsVerifier:
    """Verify citations against the indexed acts library.

    Checks:
    1. Does the act exist in our library?
    2. Does the section exist in the act?
    3. Does the citation text match the actual section?
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        similarity_threshold: float = 0.6,
    ):
        """Initialize verifier.

        Args:
            db_path: Path to ChromaDB acts index
            similarity_threshold: Minimum similarity for a match
        """
        self.indexer = ActsIndexer(db_path=db_path)
        self.similarity_threshold = similarity_threshold

        logger.info(
            "acts_verifier_initialized",
            threshold=similarity_threshold,
        )

    def verify(self, citation: Citation) -> VerificationResult:
        """Verify a single citation.

        Args:
            citation: Citation to verify

        Returns:
            VerificationResult with status and matched text
        """
        logger.debug(
            "verifying_citation",
            act=citation.act_name,
            section=citation.section,
        )

        normalized_act = normalize_act_name(citation.act_name)

        # Search for the section in the acts index
        results = self.indexer.search(
            query=f"Section {citation.section}",
            act_name=citation.act_name,
            section=citation.section,
            top_k=3,
        )

        # No results - act or section not found
        if not results:
            # Check if act exists at all
            act_results = self.indexer.search(
                query=citation.act_name,
                top_k=1,
            )

            if not act_results:
                return VerificationResult(
                    citation=citation,
                    status=VerificationStatus.ACT_MISSING,
                    message=f"Act '{citation.act_name}' not found in library",
                )
            else:
                return VerificationResult(
                    citation=citation,
                    status=VerificationStatus.NOT_FOUND,
                    message=f"Section {citation.section} not found in {citation.act_name}",
                )

        # Check best match
        best_match = results[0]
        similarity = best_match["similarity"]

        if similarity >= self.similarity_threshold:
            # Good match - verified
            return VerificationResult(
                citation=citation,
                status=VerificationStatus.VERIFIED,
                matched_text=best_match["text"][:500],  # Truncate for response
                similarity_score=similarity,
                act_chunk_id=best_match["id"],
                message=f"Verified: Section {citation.section} found in {citation.act_name}",
            )
        else:
            # Low similarity - possible mismatch
            return VerificationResult(
                citation=citation,
                status=VerificationStatus.MISMATCH,
                matched_text=best_match["text"][:500],
                similarity_score=similarity,
                act_chunk_id=best_match["id"],
                message=f"Low confidence match (similarity: {similarity:.2f})",
            )

    def verify_batch(self, citations: list[Citation]) -> list[VerificationResult]:
        """Verify multiple citations.

        Args:
            citations: List of citations to verify

        Returns:
            List of VerificationResult objects
        """
        results = []
        for citation in citations:
            result = self.verify(citation)
            results.append(result)
        return results

    def get_section_text(
        self,
        act_name: str,
        section: str,
    ) -> Optional[str]:
        """Get the actual text of a section from an act.

        Args:
            act_name: Act name
            section: Section number

        Returns:
            Section text or None if not found
        """
        results = self.indexer.search(
            query=f"Section {section}",
            act_name=act_name,
            section=section,
            top_k=1,
        )

        if results:
            return results[0]["text"]
        return None


def verify_citation(
    citation: Citation,
    db_path: Optional[Path] = None,
) -> VerificationResult:
    """Convenience function to verify a citation.

    Args:
        citation: Citation to verify
        db_path: Path to acts database

    Returns:
        VerificationResult
    """
    verifier = ActsVerifier(db_path=db_path)
    return verifier.verify(citation)
