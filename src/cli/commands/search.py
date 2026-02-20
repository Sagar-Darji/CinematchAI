"""Search command - search indexed movies."""

import sys
from pathlib import Path
import sqlite3

import rich_click as click
from rich.console import Console
from rich.table import Table
from rich import box

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


@click.command()
@click.argument("query")
@click.option("--limit", default=20, help="Maximum results to show", type=int)
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
def search(query, limit, format):
    """🔍 Search indexed movies by title or TMDB ID.
    
    Search the enrichment index for movies.
    
    [dim]Examples:[/]
        cinematch search "dune"
        cinematch search --id 155
        cinematch search "inception" --limit 5 --format json
    """
    from src.services.enrichment_pipeline import _IndexedTracker
    
    with console.status(f"[bold green]Searching for '{query}'..."):
        tracker = _IndexedTracker()
        conn = sqlite3.connect(str(tracker.db_path))
        conn.row_factory = sqlite3.Row
        
        # Try exact TMDB ID match first
        rows = conn.execute(
            "SELECT * FROM enrichment_log WHERE tmdb_id = ?",
            (query,)
        ).fetchall()
        
        # If no exact match, search by title
        if not rows:
            rows = conn.execute(
                "SELECT * FROM enrichment_log WHERE source LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        
        conn.close()
    
    if not rows:
        console.print(f"[dim]No results for '{query}'[/]")
        return
    
    # JSON output
    if format == "json":
        results = [
            {
                "tmdb_id": row["tmdb_id"],
                "language": row["original_language"],
                "source": row["source"],
                "usage_count": row["usage_count"],
                "last_used_at": row["last_used_at"],
            }
            for row in rows
        ]
        console.print_json(data={"total": len(results), "results": results})
        return
    
    # Table output
    tbl = Table(
        "TMDB ID", "Language", "Title", "Usage", "Last Used",
        border_style="bright_black",
        box=box.ROUNDED,
        header_style="bold yellow"
    )
    
    for r in rows:
        rd = dict(r)
        tbl.add_row(
            str(rd.get("tmdb_id", "?")),
            rd.get("original_language", "?"),
            (rd.get("source") or "")[:50],
            str(rd.get("usage_count", 0) or 0),
            (rd.get("last_used_at") or "never")[:10],
        )
    
    console.print(tbl)
    console.print(f"\n[dim]Found {len(rows)} results[/]")
