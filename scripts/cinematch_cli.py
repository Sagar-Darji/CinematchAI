"""CinematchAI Admin CLI — Rich-powered terminal interface.

Usage:
    python scripts/cinematch_cli.py
    python scripts/cinematch_cli.py --stats
    python scripts/cinematch_cli.py --bulk --language hi en --max-pages 50
    python scripts/cinematch_cli.py --progress
    python scripts/cinematch_cli.py --test-llm
    python scripts/cinematch_cli.py --user USER_ID
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

console = Console()

APP_BANNER = """
[bold yellow]╔══════════════════════════════════════════════════════════╗[/bold yellow]
[bold yellow]║[/bold yellow]  [bold white]🎬  CinematchAI Admin CLI  v2.0.0[/bold white]                        [bold yellow]║[/bold yellow]
[bold yellow]╚══════════════════════════════════════════════════════════╝[/bold yellow]
"""


def _format_size(mb: float) -> str:
    if mb >= 1024:
        return f"{mb/1024:.2f} GB"
    return f"{mb:.1f} MB"


def show_banner(corpus_count: int = 0, llm_provider: str = "?"):
    console.print(APP_BANNER)
    console.print(
        f"  [dim]{corpus_count:,} movies · LLM: {llm_provider}[/dim]\n"
    )


def cmd_stats(args):
    """Show corpus statistics."""
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES

    with console.status("[bold green]Loading corpus stats...", spinner="dots"):
        pipeline = EnrichmentPipeline()
        tracker_count = pipeline.tracker.count()
        dist = pipeline.get_language_distribution()
        reg = pipeline.tracker.get_page_registry_stats()

    show_banner(tracker_count)

    # Summary panel
    est_mb = tracker_count * 16 / 1024
    console.print(Panel(
        f"[bold white]{tracker_count:,}[/bold white] movies indexed  •  "
        f"[bold yellow]{_format_size(est_mb)}[/bold yellow] estimated\n"
        f"[dim]Page registry: {reg['total_cached_pages']} pages cached, "
        f"{reg['pages_with_results']} with results, "
        f"{reg['total_fetches']} total fetches[/dim]",
        title="[bold]Corpus Summary[/bold]",
        border_style="yellow",
    ))

    # Language table
    if dist:
        table = Table(
            title="Language Distribution",
            box=box.ROUNDED,
            border_style="dim",
            header_style="bold yellow",
        )
        table.add_column("Language", style="white", width=14)
        table.add_column("Code", justify="center", width=6)
        table.add_column("Movies", justify="right", width=8)
        table.add_column("Share", justify="right", width=8)
        table.add_column("Bar", width=30)

        total = max(tracker_count, 1)
        for lang, count in sorted(dist.items(), key=lambda x: -x[1]):
            name = LANGUAGE_NAMES.get(lang, lang)
            pct = count / total * 100
            bar_len = int(pct / 2)
            bar = "[yellow]" + "█" * bar_len + "[/yellow]" + "[dim]" + "░" * (50 - bar_len) + "[/dim]"
            table.add_row(name, lang, f"{count:,}", f"{pct:.1f}%", bar)

        console.print(table)


def cmd_bulk(args):
    """Run bulk enrichment with rich progress display."""
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES

    languages = args.language or None
    max_pages = args.max_pages
    target = args.target

    if languages:
        lang_label = ", ".join(LANGUAGE_NAMES.get(l, l) for l in languages)
    else:
        lang_label = "All languages (Hindi-first)"

    show_banner()
    console.print(Panel(
        f"[bold white]Languages:[/bold white] {lang_label}\n"
        f"[bold white]Max pages:[/bold white] {max_pages}  •  "
        f"[bold white]Target:[/bold white] {target} GB",
        title="[bold]Bulk Enrichment[/bold]",
        border_style="yellow",
    ))

    pipeline = EnrichmentPipeline()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold yellow]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("{task.completed}/{task.total} pages"),
        TextColumn("[green]+{task.fields[new_movies]} new[/green]"),
        TextColumn("[dim]skip:{task.fields[skipped]} fetch:{task.fields[fetched]}[/dim]"),
        TimeElapsedColumn(),
        console=console,
    )

    task = progress.add_task(
        "Processing...", total=max_pages, new_movies=0, skipped=0, fetched=0
    )

    def _cb(info):
        job = info.get("current_job", {})
        lang = LANGUAGE_NAMES.get(job.get("language", "?"), "?")
        decade = job.get("decade_start", "")
        genre = job.get("genre_id", "")
        decade_str = f"{decade}s" if decade else "all"
        genre_str = f"g={genre}" if genre else "popular"
        desc = f"{lang} | {genre_str} | {decade_str}"
        progress.update(
            task,
            completed=info["pages_processed"],
            description=desc,
            new_movies=info["total_new"],
            skipped=info.get("pages_skipped", 0),
            fetched=info.get("pages_fetched", 0),
        )

    with progress:
        result = pipeline.run_bulk_local(
            target_gb=target,
            max_pages=max_pages,
            progress_callback=_cb,
            languages=languages,
        )

    console.print()
    console.print(Panel(
        f"[bold green]✓ Done![/bold green]  "
        f"[bold white]{result['total_new']}[/bold white] new movies in "
        f"[bold white]{result['elapsed']:.1f}s[/bold white]\n"
        f"Pages processed: [white]{result['pages_processed']}[/white]  "
        f"(fetched: [white]{result.get('pages_fetched', '?')}[/white], "
        f"skipped: [white]{result.get('pages_skipped', '?')}[/white])\n"
        f"Total corpus: [bold yellow]{result['total_indexed']:,}[/bold yellow] movies  "
        f"([dim]{_format_size(result['total_indexed'] * 16 / 1024)}[/dim])",
        title="[bold]Results[/bold]",
        border_style="green",
    ))


def cmd_progress(args):
    """Show job queue progress."""
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES

    with console.status("[bold green]Fetching progress...", spinner="dots"):
        pipeline = EnrichmentPipeline()
        prog = pipeline.get_bulk_progress()

    show_banner(prog["total_indexed"])

    reg = prog.get("page_registry", {})
    if reg.get("total_cached_pages", 0) > 0:
        console.print(Panel(
            f"[white]{reg['total_cached_pages']}[/white] pages cached  •  "
            f"[white]{reg['pages_with_results']}[/white] with results  •  "
            f"[white]{reg['empty_pages']}[/white] empty  •  "
            f"[white]{reg['total_fetches']}[/white] total fetches",
            title="[bold]Page Registry[/bold]",
            border_style="dim",
        ))

    if prog["total_jobs"] == 0:
        console.print(
            f"[dim]No jobs in queue.[/dim]  "
            f"Corpus: [bold yellow]{prog['total_indexed']:,}[/bold yellow] movies  "
            f"([dim]{_format_size(prog['est_size_mb'])}[/dim])"
        )
        return

    table = Table(
        title=f"Job Queue — {prog['done']}/{prog['total_jobs']} done ({prog['pct_complete']:.1f}%)",
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold yellow",
    )
    table.add_column("Language", width=14)
    table.add_column("P", justify="center", width=4)
    table.add_column("Done", justify="right", width=7)
    table.add_column("Pending", justify="right", width=8)
    table.add_column("Failed", justify="right", width=7)
    table.add_column("Movies", justify="right", width=8)
    table.add_column("Progress", width=24)

    for lp in prog["by_language"]:
        lang = LANGUAGE_NAMES.get(lp["language"], lp["language"])
        pct = (lp["done"] / lp["total"] * 100) if lp["total"] > 0 else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        table.add_row(
            lang,
            str(lp["priority"]),
            str(lp["done"]),
            str(lp["pending"]),
            f"[red]{lp['failed']}[/red]" if lp["failed"] else "0",
            str(lp.get("movies_found", 0)),
            f"[yellow]{bar}[/yellow] {pct:.0f}%",
        )

    console.print(table)
    console.print(
        f"\n  Corpus: [bold yellow]{prog['total_indexed']:,}[/bold yellow] movies  "
        f"([dim]{_format_size(prog['est_size_mb'])}[/dim])"
    )


def cmd_test_llm(args):
    """Test LLM connectivity and latency."""
    import time
    from src.utils.llm_client import get_llm_client

    show_banner()
    console.print("[bold]LLM Health Check[/bold]\n")

    test_prompt = "Reply with exactly: OK"

    for provider_name in ["groq", "ollama"]:
        try:
            from config.settings import get_settings
            s = get_settings()
            if provider_name == "groq" and not s.groq_api_key:
                console.print(f"  [yellow]groq[/yellow]   [dim]SKIP — no API key[/dim]")
                continue

            from src.utils.llm_client import LLMProvider
            provider = LLMProvider.GROQ if provider_name == "groq" else LLMProvider.OLLAMA
            client = get_llm_client(provider=provider, use_fast_model=True)

            t0 = time.time()
            resp = client.generate(test_prompt, max_tokens=10)
            latency = (time.time() - t0) * 1000

            console.print(
                f"  [green]✓[/green] [bold]{provider_name}[/bold]  "
                f"[dim]{client.model}[/dim]  →  "
                f"[white]{resp.strip()[:30]}[/white]  "
                f"[dim]({latency:.0f}ms)[/dim]"
            )
        except Exception as e:
            console.print(f"  [red]✗[/red] [bold]{provider_name}[/bold]  [red]{e}[/red]")


def cmd_user(args):
    """Show user profile and taste summary."""
    from src.services.user_service import get_user_service
    from src.services.enrichment_pipeline import LANGUAGE_NAMES

    user_id = args.user_id
    show_banner()

    with console.status(f"[bold green]Loading profile for {user_id}...", spinner="dots"):
        try:
            svc = get_user_service()
            ratings = svc.get_user_ratings(user_id)
        except Exception as e:
            console.print(f"[red]Error loading user: {e}[/red]")
            return

    if not ratings:
        console.print(f"[yellow]No ratings found for user '{user_id}'[/yellow]")
        return

    total = len(ratings)
    avg = sum(r["rating"] for r in ratings) / total
    top = sorted(ratings, key=lambda r: -r["rating"])[:5]

    console.print(Panel(
        f"[bold white]User:[/bold white] {user_id}\n"
        f"[bold white]Ratings:[/bold white] {total}  •  "
        f"[bold white]Avg:[/bold white] {avg:.2f}/5.0",
        title="[bold]User Profile[/bold]",
        border_style="yellow",
    ))

    table = Table(title="Top Rated Movies", box=box.SIMPLE, header_style="bold yellow")
    table.add_column("Movie ID", width=10)
    table.add_column("Rating", justify="right", width=8)

    for r in top:
        stars = "★" * int(r["rating"])
        table.add_row(str(r.get("movie_id", r.get("movieId", "?"))), f"[yellow]{stars}[/yellow] {r['rating']}")

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="CinematchAI Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stats", action="store_true", help="Show corpus statistics")
    group.add_argument("--bulk", action="store_true", help="Run bulk enrichment")
    group.add_argument("--progress", action="store_true", help="Show job queue progress")
    group.add_argument("--test-llm", action="store_true", help="Test LLM connectivity")
    group.add_argument("--user", dest="user_id", metavar="USER_ID", help="Inspect user profile")

    parser.add_argument("--language", nargs="+", metavar="LANG",
                        help="Language codes for bulk (e.g. hi en ta)")
    parser.add_argument("--max-pages", type=int, default=100,
                        help="Max pages for bulk run (default: 100)")
    parser.add_argument("--target", type=float, default=15.0,
                        help="Target corpus size in GB (default: 15)")

    args = parser.parse_args()

    if args.stats:
        cmd_stats(args)
    elif args.bulk:
        cmd_bulk(args)
    elif args.progress:
        cmd_progress(args)
    elif args.test_llm:
        cmd_test_llm(args)
    elif args.user_id:
        cmd_user(args)
    else:
        # Interactive menu
        show_banner()
        console.print("[bold white]Commands:[/bold white]")
        console.print("  [yellow]--stats[/yellow]          Corpus statistics")
        console.print("  [yellow]--bulk[/yellow]           Run bulk enrichment")
        console.print("  [yellow]--progress[/yellow]       Job queue progress")
        console.print("  [yellow]--test-llm[/yellow]       Test LLM connectivity")
        console.print("  [yellow]--user USER_ID[/yellow]   Inspect user profile")
        console.print()
        console.print("[dim]Run with --help for full options.[/dim]")


if __name__ == "__main__":
    main()
