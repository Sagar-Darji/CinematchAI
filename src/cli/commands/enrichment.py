"""Enrichment command - manage corpus enrichment jobs."""

import sys
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
)
from rich.table import Table
from rich import box

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

console = Console()


@click.group()
def enrichment():
    """🌍 Manage corpus enrichment and movie discovery.
    
    Add movies from TMDB to your corpus with bulk enrichment jobs.
    """
    pass


@enrichment.command()
@click.option("--lang", "-l", multiple=True, help="Language codes (e.g., hi, es). Repeat for multiple.")
@click.option("--pages", "-p", default=500, help="Maximum pages to process", type=int)
@click.option("--target", "-t", default=15.0, help="Target corpus size in GB", type=float)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def start(lang, pages, target, yes):
    """Start bulk enrichment job.
    
    Discover and enrich movies from TMDB by language.
    
    [dim]Examples:[/]
        cinematch enrichment start --lang hi --pages 100
        cinematch enrichment start --lang hi --lang es --target 20
        cinematch enrichment start --pages 1000 --yes
    """
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
    
    # Convert language tuple to list
    selected_langs = list(lang) if lang else None
    
    # Validate language codes
    if selected_langs:
        for code in selected_langs:
            if code not in LANGUAGE_NAMES:
                console.print(f"[red]Error:[/] Unknown language code '{code}'")
                console.print(f"[dim]Available: {', '.join(sorted(LANGUAGE_NAMES.keys()))}[/]")
                sys.exit(1)
    
    # Show summary
    lang_label = ", ".join(LANGUAGE_NAMES.get(c, c) for c in selected_langs) if selected_langs else "ALL"
    console.print(Panel(
        f"Languages: [yellow]{lang_label}[/]\n"
        f"Max pages: [yellow]{pages}[/]\n"
        f"Target size: [yellow]{target} GB[/]",
        title="[bold]Enrichment Configuration[/]",
        border_style="yellow"
    ))
    
    # Confirm
    if not yes:
        confirm = console.input("\n[bold]Start enrichment? (yes/no):[/] ")
        if confirm.lower() not in ["yes", "y"]:
            console.print("[dim]Cancelled[/]")
            return
    
    # Run enrichment
    pipeline = EnrichmentPipeline()
    
    prog = Progress(
        SpinnerColumn(),
        TextColumn("[bold yellow]{task.description}"),
        BarColumn(bar_width=36),
        TextColumn("{task.completed}/{task.total} pages"),
        TextColumn("[green]+{task.fields[new]} new[/]"),
        TimeElapsedColumn(),
        console=console,
    )
    task = prog.add_task("Starting…", total=pages, new=0)
    
    def _progress_callback(info):
        job = info.get("current_job", {})
        lang_code = job.get("language", "?")
        lang_name = LANGUAGE_NAMES.get(lang_code, lang_code)
        prog.update(
            task,
            completed=info["pages_processed"],
            description=lang_name,
            new=info["total_new"]
        )
    
    console.print()
    with prog:
        result = pipeline.run_bulk_local(
            target_gb=target,
            max_pages=pages,
            progress_callback=_progress_callback,
            languages=selected_langs,
        )
    
    # Show results
    console.print(Panel(
        f"[bold green]✓ Enrichment complete![/]\n\n"
        f"New movies: [yellow]{result['total_new']:,}[/]\n"
        f"Total corpus: [yellow]{result['total_indexed']:,}[/] movies\n"
        f"Elapsed: [dim]{result['elapsed']:.1f}s[/]",
        border_style="green",
    ))


@enrichment.command()
@click.option("--format", type=click.Choice(["table", "json"]), default="table")
def status(format):
    """Show enrichment job progress.
    
    Display current job queue status and language-wise progress.
    
    [dim]Examples:[/]
        cinematch enrichment status
        cinematch enrichment status --format json
    """
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
    
    with console.status("[bold green]Loading progress..."):
        pipeline = EnrichmentPipeline()
        progress = pipeline.get_bulk_progress()
    
    # JSON output
    if format == "json":
        output = {
            "total_jobs": progress["total_jobs"],
            "done": progress["done"],
            "total_indexed": progress["total_indexed"],
            "estimated_size_mb": round(progress["est_size_mb"], 2),
            "by_language": progress["by_language"]
        }
        console.print_json(data=output)
        return
    
    # Table output
    if progress["total_jobs"] == 0:
        console.print(
            f"[dim]No jobs in queue[/]\n"
            f"Corpus: [yellow]{progress['total_indexed']:,}[/] movies"
        )
        return
    
    done = progress["done"]
    total = progress["total_jobs"]
    console.print(Panel(
        f"Progress: [yellow]{done}/{total}[/] jobs ({done/total*100:.1f}%)\n"
        f"Corpus: [yellow]{progress['total_indexed']:,}[/] movies "
        f"([dim]{_fmt_mb(progress['est_size_mb'])}[/])",
        border_style="yellow"
    ))
    
    # Language breakdown
    tbl = Table(
        "Language", "Priority", "Done", "Pending", "Failed", "Movies", "Progress",
        border_style="bright_black",
        box=box.ROUNDED,
        header_style="bold yellow"
    )
    
    for lp in progress["by_language"]:
        name = LANGUAGE_NAMES.get(lp["language"], lp["language"])
        pct = (lp["done"] / lp["total"] * 100) if lp["total"] > 0 else 0
        bar = "[yellow]" + "█" * int(pct / 5) + "[/][dim]" + "░" * (20 - int(pct / 5)) + "[/]"
        tbl.add_row(
            name,
            str(lp["priority"]),
            str(lp["done"]),
            str(lp["pending"]),
            f"[red]{lp['failed']}[/]" if lp["failed"] else "0",
            str(lp.get("movies_found", 0)),
            f"{bar} {pct:.0f}%",
        )
    
    console.print(tbl)


@enrichment.command()
@click.option("--show", type=click.Choice(["all", "candidates"]), default="candidates")
def rotation(show):
    """Show overnight rotation candidates.
    
    List movies that haven't been used recently and could be removed.
    
    [dim]Examples:[/]
        cinematch enrichment rotation
        cinematch enrichment rotation --show all
    """
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
    
    with console.status("[bold green]Loading candidates..."):
        pipeline = EnrichmentPipeline()
        tracker_count = pipeline.tracker.count()
        candidates = pipeline.tracker.get_rotation_candidates(keep_days=30)
    
    console.print(f"Total corpus: [yellow]{tracker_count:,}[/] movies")
    console.print(f"Rotation candidates (>30 days unused): [yellow]{len(candidates)}[/]\n")
    
    if not candidates:
        console.print("[dim]No rotation candidates[/]")
        return
    
    # Group by language
    by_lang = {}
    for c in candidates:
        lang = c.get("original_language", "?")
        by_lang[lang] = by_lang.get(lang, 0) + 1
    
    tbl = Table("Language", "Candidates", box=box.SIMPLE, border_style="bright_black")
    for lang, cnt in sorted(by_lang.items(), key=lambda x: -x[1]):
        tbl.add_row(LANGUAGE_NAMES.get(lang, lang), str(cnt))
    console.print(tbl)


def _fmt_mb(mb: float) -> str:
    """Format megabytes for display."""
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb/1024:.1f} GB"
