#!/usr/bin/env python3
"""Full pipeline demo for Jaanch Lite.

Demonstrates:
1. Document parsing with ADE (visual grounding)
2. Citation extraction (hybrid regex + LLM)
3. Citation verification against acts library
4. RAG search with reranking

Usage:
    python scripts/demo.py path/to/document.pdf
    python scripts/demo.py path/to/document.pdf --matter-id case123
"""

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown

from src.parsers.ade_parser import parse_document
from src.citations.extractor import CitationExtractor
from src.acts.verifier import ActsVerifier
from src.search.rag import RAGSearch, DocumentStore

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Jaanch Lite Demo")
    parser.add_argument("document", type=Path, help="Path to legal document (PDF)")
    parser.add_argument("--matter-id", default="demo", help="Matter/case identifier")
    parser.add_argument("--query", default=None, help="Optional search query")

    args = parser.parse_args()

    if not args.document.exists():
        console.print(f"[red]Error: File not found: {args.document}[/red]")
        return

    console.print(Panel.fit(
        "[bold blue]Jaanch Lite - Legal Document Intelligence[/bold blue]\n"
        "Simplified POC with Landing AI ADE + Voyage AI + Instructor",
        border_style="blue",
    ))

    # =========================================================================
    # Step 1: Parse Document with ADE
    # =========================================================================
    console.print("\n[bold]Step 1: Parsing Document with Landing AI ADE[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing document...", total=None)

        chunks = parse_document(
            args.document,
            document_id=args.document.stem,
            matter_id=args.matter_id,
        )

        progress.update(task, description=f"Parsed {len(chunks)} chunks")

    # Show sample chunks with grounding
    console.print(f"\n[green]Parsed {len(chunks)} chunks with visual grounding[/green]")

    if chunks:
        table = Table(title="Sample Chunks (First 3)")
        table.add_column("Page")
        table.add_column("Type")
        table.add_column("BBox")
        table.add_column("Text Preview", max_width=50)

        for chunk in chunks[:3]:
            bbox_str = f"[{chunk.bbox.x0:.2f}, {chunk.bbox.y0:.2f}]" if chunk.bbox else "N/A"
            table.add_row(
                str(chunk.page),
                chunk.chunk_type.value,
                bbox_str,
                chunk.text[:50] + "...",
            )

        console.print(table)

    # =========================================================================
    # Step 2: Extract Citations
    # =========================================================================
    console.print("\n[bold]Step 2: Extracting Citations (Hybrid Regex + LLM)[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Extracting citations...", total=None)

        extractor = CitationExtractor(use_llm=False)  # Regex-only, no OpenAI needed
        citation_result = extractor.extract_from_chunks(chunks)

        progress.update(task, description=f"Found {len(citation_result.citations)} citations")

    console.print(f"\n[green]Found {len(citation_result.citations)} citations[/green]")

    if citation_result.citations:
        table = Table(title="Extracted Citations")
        table.add_column("Act")
        table.add_column("Section")
        table.add_column("Page")
        table.add_column("Confidence")
        table.add_column("Method")

        for cit in citation_result.citations[:10]:
            table.add_row(
                cit.act_name[:40],
                cit.section,
                str(cit.source_page or "?"),
                f"{cit.confidence:.2f}",
                cit.extraction_method,
            )

        console.print(table)

    # =========================================================================
    # Step 3: Verify Citations
    # =========================================================================
    console.print("\n[bold]Step 3: Verifying Citations Against Acts Library[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Verifying citations...", total=None)

        verifier = ActsVerifier()
        verifications = verifier.verify_batch(citation_result.citations[:5])  # First 5

        progress.update(task, description="Verification complete")

    if verifications:
        table = Table(title="Verification Results")
        table.add_column("Citation")
        table.add_column("Status")
        table.add_column("Similarity")

        for v in verifications:
            status_color = {
                "verified": "green",
                "mismatch": "yellow",
                "not_found": "red",
                "act_missing": "red",
            }.get(v.status.value, "white")

            table.add_row(
                f"S. {v.citation.section} {v.citation.act_name[:30]}",
                f"[{status_color}]{v.status.value}[/{status_color}]",
                f"{v.similarity_score:.2f}" if v.similarity_score else "N/A",
            )

        console.print(table)

    # =========================================================================
    # Step 4: Add to Document Store & Search
    # =========================================================================
    console.print("\n[bold]Step 4: RAG Search with Voyage AI Reranking[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing document...", total=None)

        rag = RAGSearch()
        rag.add_document(chunks)

        progress.update(task, description="Document indexed")

    # Search
    query = args.query or "What are the key legal issues in this case?"
    console.print(f"\n[dim]Search query: {query}[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Searching with reranking...", total=None)

        results = rag.search(
            query=query,
            matter_id=args.matter_id,
            top_k=3,
            rerank=True,
            legal_category="statutes",
        )

        progress.update(task, description=f"Found {len(results.results)} results")

    if results.results:
        console.print(f"\n[green]Top {len(results.results)} results (reranked):[/green]")

        for r in results.results:
            console.print(Panel(
                f"[dim]Page {r.page} | Score: {r.score:.3f} | "
                f"Rerank: {r.rerank_score:.3f if r.rerank_score else 'N/A'}[/dim]\n\n"
                f"{r.chunk.text[:300]}...",
                title=f"Result #{r.rank}",
                border_style="cyan",
            ))

    # =========================================================================
    # Summary
    # =========================================================================
    console.print(Panel.fit(
        f"[bold green]Pipeline Complete![/bold green]\n\n"
        f"Document: {args.document.name}\n"
        f"Chunks: {len(chunks)}\n"
        f"Citations: {len(citation_result.citations)}\n"
        f"Reranked: {results.reranked}",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
