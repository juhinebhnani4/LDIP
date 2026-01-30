"""Acts library indexer - builds vector DB from act PDFs.

One-time setup to index all acts for citation verification.
"""

import re
from pathlib import Path
from typing import Optional

import structlog
import chromadb
from chromadb.config import Settings as ChromaSettings

from src.core.config import settings
from src.core.models import ActSection, KnownAct
from src.core.utils import normalize_act_name
from src.parsers.ade_parser import ADEParser
from src.embeddings.voyage import VoyageEmbedder
from .india_code import KNOWN_ACTS, IndiaCodeClient

logger = structlog.get_logger(__name__)


# Section extraction patterns
SECTION_PATTERNS = [
    # "Section 138." at start of line/paragraph
    re.compile(r"^(?:Section|Sec\.?)\s+(\d+[A-Za-z]?)\.?\s", re.MULTILINE | re.IGNORECASE),
    # "138. " at paragraph start
    re.compile(r"^\s*(\d+[A-Za-z]?)\.\s+[A-Z]", re.MULTILINE),
    # "[Section 138]" in brackets
    re.compile(r"\[(?:Section|Sec\.?)\s+(\d+[A-Za-z]?)\]", re.IGNORECASE),
    # "§ 138" symbol notation
    re.compile(r"§\s*(\d+[A-Za-z]?)"),
]


class ActsIndexer:
    """Index acts into ChromaDB for citation verification.

    Creates a searchable index of all act sections.
    Each section is stored with:
    - Act name
    - Section number
    - Full text
    - Embedding (voyage-law-2)
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        collection_name: str = "indian_acts",
    ):
        """Initialize acts indexer.

        Args:
            db_path: Path to ChromaDB storage
            collection_name: Name of the collection
        """
        self.db_path = Path(db_path or settings.acts_db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Indian Central Acts for citation verification"},
        )

        # Initialize embedder
        self.embedder = VoyageEmbedder()

        # Initialize parser
        self.parser = ADEParser()

        logger.info(
            "acts_indexer_initialized",
            db_path=str(self.db_path),
            collection=collection_name,
        )

    def index_act_pdf(
        self,
        pdf_path: Path,
        act_name: str,
        overwrite: bool = False,
    ) -> int:
        """Index a single act PDF.

        Args:
            pdf_path: Path to act PDF
            act_name: Canonical act name
            overwrite: Whether to overwrite existing entries

        Returns:
            Number of sections indexed
        """
        normalized_name = normalize_act_name(act_name)

        # Check if already indexed
        if not overwrite:
            existing = self.collection.get(
                where={"act_name": act_name},
                limit=1,
            )
            if existing["ids"]:
                logger.info("act_already_indexed", act=act_name)
                return 0

        logger.info("indexing_act", act=act_name, path=str(pdf_path))

        # Parse PDF with ADE
        chunks = self.parser.parse(pdf_path)

        if not chunks:
            logger.warning("no_chunks_from_pdf", act=act_name)
            return 0

        # Extract sections from chunks
        sections = self._extract_sections(chunks, act_name)

        if not sections:
            # If no sections found, index as general chunks
            sections = [
                ActSection(
                    act_name=act_name,
                    section_number="general",
                    text=chunk.text,
                    page=chunk.page,
                    chunk_id=chunk.chunk_id,
                )
                for chunk in chunks
            ]

        # Generate embeddings
        texts = [s.text for s in sections]
        embeddings = self.embedder.embed_batch(texts, input_type="document")

        # Store in ChromaDB
        ids = [f"{normalized_name}_{s.section_number}_{i}" for i, s in enumerate(sections)]
        metadatas = [
            {
                "act_name": act_name,
                "act_normalized": normalized_name,
                "section_number": s.section_number,
                "page": s.page or 0,
            }
            for s in sections
        ]

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            "act_indexed",
            act=act_name,
            sections=len(sections),
        )

        return len(sections)

    def _extract_sections(self, chunks: list, act_name: str) -> list[ActSection]:
        """Extract sections from parsed chunks.

        Args:
            chunks: Parsed document chunks
            act_name: Act name

        Returns:
            List of ActSection objects
        """
        sections = []
        current_section = None
        current_text = []

        for chunk in chunks:
            text = chunk.text

            # Try to find section number
            section_num = self._find_section_number(text)

            if section_num:
                # Save previous section if exists
                if current_section and current_text:
                    sections.append(ActSection(
                        act_name=act_name,
                        section_number=current_section,
                        text="\n".join(current_text),
                        page=chunk.page,
                        chunk_id=chunk.chunk_id,
                    ))

                current_section = section_num
                current_text = [text]
            elif current_section:
                current_text.append(text)

        # Don't forget the last section
        if current_section and current_text:
            sections.append(ActSection(
                act_name=act_name,
                section_number=current_section,
                text="\n".join(current_text),
                page=chunks[-1].page if chunks else 0,
                chunk_id=chunks[-1].chunk_id if chunks else "",
            ))

        return sections

    def _find_section_number(self, text: str) -> Optional[str]:
        """Find section number in text.

        Args:
            text: Text to search

        Returns:
            Section number or None
        """
        for pattern in SECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None

    def index_all_known_acts(
        self,
        acts_dir: Optional[Path] = None,
        download_missing: bool = True,
    ) -> dict[str, int]:
        """Index all known acts.

        Args:
            acts_dir: Directory containing act PDFs
            download_missing: Whether to download missing acts

        Returns:
            Dict mapping act names to number of sections indexed
        """
        acts_dir = Path(acts_dir or settings.data_path / "acts")
        acts_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        client = IndiaCodeClient(download_dir=acts_dir) if download_missing else None

        for act in KNOWN_ACTS:
            act_name = act["canonical_name"]
            normalized = normalize_act_name(act_name)
            pdf_path = acts_dir / f"{normalized}.pdf"

            # Download if missing
            if not pdf_path.exists() and download_missing and client:
                doc_id = act.get("india_code_doc_id")
                filename = act.get("india_code_filename")

                if doc_id and filename:
                    downloaded = client.download_act(doc_id, filename, act_name)
                    if downloaded:
                        pdf_path = downloaded

            # Index if PDF exists
            if pdf_path.exists():
                count = self.index_act_pdf(pdf_path, act_name)
                results[act_name] = count
            else:
                logger.warning("act_pdf_not_found", act=act_name)
                results[act_name] = 0

        if client:
            client.close()

        return results

    def search(
        self,
        query: str,
        act_name: Optional[str] = None,
        section: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Search the acts index.

        Args:
            query: Search query
            act_name: Optional filter by act name
            section: Optional filter by section number
            top_k: Number of results

        Returns:
            List of search results
        """
        # Build where clause
        where = {}
        if act_name:
            where["act_name"] = act_name
        if section:
            where["section_number"] = section

        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where if where else None,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []
        for i, doc_id in enumerate(results["ids"][0]):
            formatted.append({
                "id": doc_id,
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1 - results["distances"][0][i],
            })

        return formatted

    def get_stats(self) -> dict:
        """Get index statistics."""
        return {
            "total_documents": self.collection.count(),
            "collection_name": self.collection_name,
            "db_path": str(self.db_path),
        }


def index_acts(
    acts_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    download_missing: bool = True,
) -> dict[str, int]:
    """Convenience function to index all acts.

    Args:
        acts_dir: Directory containing act PDFs
        db_path: Path to ChromaDB storage
        download_missing: Whether to download missing acts

    Returns:
        Dict mapping act names to sections indexed
    """
    indexer = ActsIndexer(db_path=db_path)
    return indexer.index_all_known_acts(acts_dir, download_missing)
