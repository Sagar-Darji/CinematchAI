"""Stats command - show corpus statistics."""

import json
import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


@click.command()
@click.option(
    "--format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format",
)
@click.option(
    "--language",
    "-l",
    help="Filter by specific language code (e.g., en, hi, es)",
)
def stats(format, language):
    """📊 Show corpus statistics and language distribution.
    
    Display indexed movie count, vector database status, and language breakdown.
    
    [dim]Examples:[/]
        cinematch stats
        cinematch stats --format json
        cinematch stats --language hi
    """
    with console.status("[bold green]Loading statistics..."):
        from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
        
        pipeline = EnrichmentPipeline()
        tracker_count = pipeline.tracker.count()
        est_mb = tracker_count * 16 / 1024
        counts = pipeline.cloud_db.count()
        availability = pipeline.cloud_db.is_available()
        dist = pipeline.get_language_distribution()
    
    # Filter by language if specified
    if language:
        if language not in dist:
            console.print(f"[red]Error:[/] Language '{language}' not found in corpus")
            sys.exit(1)
        dist = {language: dist[language]}
    
    # JSON output
    if format == "json":
        output = {
            "total_movies": tracker_count,
            "estimated_size_mb": round(est_mb, 2),
            "backends": [
                {
                    "name": backend,
                    "vectors": cnt,
                    "status": "up" if availability.get(backend, False) else "down"
                }
                for backend, cnt in counts.items()
            ],
            "languages": [
                {
                    "code": lang,
                    "name": LANGUAGE_NAMES.get(lang, lang),
                    "count": cnt,
                    "percentage": round(cnt / max(tracker_count, 1) * 100, 2)
                }
                for lang, cnt in sorted(dist.items(), key=lambda x: -x[1])
            ]
        }
        console.print_json(data=output)
        return
    
    # Table output (default)
    # Summary panel
    console.print(Panel(
        f"[bold white]{tracker_count:,}[/] movies indexed  ·  "
        f"[bold yellow]{_fmt_mb(est_mb)}[/] estimated",
        border_style="yellow",
        title="[bold]Corpus Overview[/]",
    ))
    
    # Backends table
    b = Table("Backend", "Vectors", "Status", border_style="bright_black", box=box.SIMPLE)
    for backend, cnt in counts.items():
        up = availability.get(backend, False)
        b.add_row(backend, f"{cnt:,}", "[green]● UP[/]" if up else "[red]● DOWN[/]")
    console.print(b)
    console.print()
    
    # Languages table
    if dist:
        total = max(tracker_count, 1)
        l_tbl = Table(
            "Language", "Count", "Share", "Distribution",
            border_style="bright_black",
            box=box.ROUNDED,
            header_style="bold yellow"
        )
        for lang, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            name = LANGUAGE_NAMES.get(lang, lang)
            pct = cnt / total * 100
            bar_len = int(pct / 2)
            bar = "[yellow]" + "█" * bar_len + "[/][dim]" + "░" * (50 - bar_len) + "[/]"
            l_tbl.add_row(name, f"{cnt:,}", f"{pct:.1f}%", bar)
        console.print(l_tbl)


def _fmt_mb(mb: float) -> str:
    """Format megabytes for display."""
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb/1024:.1f} GB"
