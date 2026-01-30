#!/usr/bin/env python3
"""Index all known Indian acts into the vector database.

Run this once to build the acts library for citation verification.

Usage:
    python scripts/index_acts.py
    python scripts/index_acts.py --download  # Download missing acts from India Code
    python scripts/index_acts.py --acts-dir ./my_acts  # Use custom acts directory
"""

import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.acts.indexer import ActsIndexer
from src.acts.india_code import KNOWN_ACTS

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Index Indian acts for citation verification")
    parser.add_argument(
        "--acts-dir",
        type=Path,
        default=Path("./data/acts"),
        help="Directory containing act PDFs",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("./vectordb/acts"),
        help="Path to ChromaDB storage",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download missing acts from India Code",
    )

    args = parser.parse_args()

    console.print("\n[bold blue]Jaanch Lite - Acts Indexer[/bold blue]\n")

    # Show known acts
    console.print(f"[dim]Known acts: {len(KNOWN_ACTS)}[/dim]")
    console.print(f"[dim]Acts directory: {args.acts_dir}[/dim]")
    console.print(f"[dim]Database path: {args.db_path}[/dim]")
    console.print(f"[dim]Download missing: {args.download}[/dim]\n")

    # Initialize indexer
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing indexer...", total=None)

        indexer = ActsIndexer(db_path=args.db_path)

        progress.update(task, description="Indexing acts...")

        # Index all acts
        results = indexer.index_all_known_acts(
            acts_dir=args.acts_dir,
            download_missing=args.download,
        )

        progress.update(task, description="Done!")

    # Show results
    table = Table(title="Indexing Results")
    table.add_column("Act Name", style="cyan")
    table.add_column("Sections", justify="right", style="green")
    table.add_column("Status")

    for act_name, count in results.items():
        status = "[green]Indexed[/green]" if count > 0 else "[red]Not Found[/red]"
        table.add_row(act_name, str(count), status)

    console.print(table)

    # Summary
    total_indexed = sum(results.values())
    acts_indexed = sum(1 for c in results.values() if c > 0)

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Acts indexed: {acts_indexed}/{len(results)}")
    console.print(f"  Total sections: {total_indexed}")

    # Stats
    stats = indexer.get_stats()
    console.print(f"\n[dim]Database stats: {stats['total_documents']} total documents[/dim]")


if __name__ == "__main__":
    main()
