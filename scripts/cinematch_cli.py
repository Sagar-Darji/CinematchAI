"""CinematchAI — Interactive Terminal Console (Rich UI).

Run:
    python -m scripts.cinematch_cli
    python scripts/cinematch_cli.py

Fully interactive — press a number key, no commands to type.
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from rich import box
    from rich.align import Align
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.prompt import Confirm, IntPrompt, Prompt
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Install rich first:  pip install rich")
    sys.exit(1)

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_mb(mb: float) -> str:
    return f"{mb/1024:.2f} GB" if mb >= 1024 else f"{mb:.1f} MB"


def _pause():
    console.print()
    Prompt.ask("[dim]  Press Enter to return to menu[/]", default="")


def _banner():
    console.clear()
    console.print(Panel(
        Align.center(
            Text.from_markup(
                "[bold yellow]🎬  CineMatch AI  v2.0.0[/]\n"
                "[dim]Interactive Admin Console — press a number, no commands needed[/]"
            )
        ),
        border_style="yellow",
        padding=(0, 6),
    ))


def _main_menu() -> str:
    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column(style="bold yellow", min_width=4)
    table.add_column(style="white", min_width=28)
    table.add_column(style="dim")

    items = [
        ("1", "📊  Corpus Stats",         "counts, language distribution, backend health"),
        ("2", "🌍  Bulk Enrichment",       "interactive language + page config, then runs"),
        ("3", "📈  Job Progress",          "live view of pending / done / failed jobs"),
        ("4", "🔄  Overnight Rotation",    "prune stale movies, refresh corpus"),
        ("5", "🔍  Search Index",          "look up any movie by title or TMDB ID"),
        ("6", "🗑️   Clear Job Queue",       "choose pending, failed, or all"),
        ("7", "🧪  Test Recommendation",   "run full AI pipeline for any user_id"),
        ("8", "🔌  LLM Health Check",      "test Groq + Ollama latency"),
        ("0", "🚪  Exit",                  ""),
    ]
    for key, label, hint in items:
        table.add_row(f"[{key}]", label, hint)

    console.print(Panel(table, title="[bold]Main Menu[/]", border_style="bright_black"))
    return Prompt.ask("[bold yellow]  Choose[/]", choices=[str(i) for i in range(9)], default="0")


# ── Action: Corpus Stats ──────────────────────────────────────────────────────

def action_stats():
    console.rule("[yellow]Corpus Stats[/]")
    with console.status("[bold green]Loading…"):
        from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
        pipeline = EnrichmentPipeline()
        tracker_count = pipeline.tracker.count()
        est_mb = tracker_count * 16 / 1024
        counts = pipeline.cloud_db.count()
        availability = pipeline.cloud_db.is_available()
        dist = pipeline.get_language_distribution()

    # Summary
    console.print(Panel(
        f"[bold white]{tracker_count:,}[/] movies indexed  ·  "
        f"[bold yellow]{_fmt_mb(est_mb)}[/] estimated",
        border_style="yellow",
    ))

    # Backends
    b = Table("Backend", "Vectors", "Status", border_style="bright_black", box=box.SIMPLE)
    for backend, cnt in counts.items():
        up = availability.get(backend, False)
        b.add_row(backend, f"{cnt:,}", "[green]● UP[/]" if up else "[red]● DOWN[/]")
    console.print(b)

    # Languages
    if dist:
        total = max(tracker_count, 1)
        l_tbl = Table("Language", "Count", "Share", "Distribution",
                      border_style="bright_black", box=box.ROUNDED, header_style="bold yellow")
        for lang, cnt in sorted(dist.items(), key=lambda x: -x[1]):
            name = LANGUAGE_NAMES.get(lang, lang)
            pct = cnt / total * 100
            bar_len = int(pct / 2)
            bar = "[yellow]" + "█" * bar_len + "[/][dim]" + "░" * (50 - bar_len) + "[/]"
            l_tbl.add_row(name, f"{cnt:,}", f"{pct:.1f}%", bar)
        console.print(l_tbl)

    _pause()


# ── Action: Bulk Enrichment ───────────────────────────────────────────────────

def action_bulk():
    console.rule("[yellow]Bulk Enrichment[/]")
    from src.services.enrichment_pipeline import LANGUAGE_NAMES

    # Show language picker table
    lang_items = sorted(LANGUAGE_NAMES.items(), key=lambda x: x[1])
    l_tbl = Table("Key", "Code", "Language", box=box.SIMPLE, border_style="bright_black")
    l_tbl.add_row("[bold yellow]0[/]", "—", "ALL languages")
    for i, (code, name) in enumerate(lang_items):
        l_tbl.add_row(f"[yellow]{i+1}[/]", code, name)
    console.print(l_tbl)

    raw = Prompt.ask(
        "\n  Language key(s) [0=all, or space-separated numbers like '1 3 7']",
        default="0",
    ).strip()

    selected_langs: list[str] | None = None
    if raw != "0":
        selected_langs = []
        for part in raw.split():
            try:
                idx = int(part) - 1
                selected_langs.append(lang_items[idx][0])
            except (ValueError, IndexError):
                console.print(f"  [red]Invalid key: {part}[/]")

    max_pages = IntPrompt.ask("  Max pages this run", default=500)
    target = float(Prompt.ask("  Target corpus size (GB)", default="15"))

    lang_label = ", ".join(LANGUAGE_NAMES.get(c, c) for c in selected_langs) if selected_langs else "ALL"
    console.print(f"\n  Languages: [yellow]{lang_label}[/]  ·  Pages: [yellow]{max_pages}[/]  ·  Target: [yellow]{target} GB[/]\n")

    if not Confirm.ask("  Start bulk enrichment?", default=False):
        console.print("[dim]  Cancelled.[/]")
        _pause()
        return

    from src.services.enrichment_pipeline import EnrichmentPipeline
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
    task = prog.add_task("Starting…", total=max_pages, new=0)

    def _cb(info):
        job = info.get("current_job", {})
        lang = LANGUAGE_NAMES.get(job.get("language", "?"), "?")
        prog.update(task, completed=info["pages_processed"],
                    description=lang, new=info["total_new"])

    with prog:
        result = pipeline.run_bulk_local(
            target_gb=target, max_pages=max_pages,
            progress_callback=_cb, languages=selected_langs,
        )

    console.print(Panel(
        f"[bold green]✓ Done![/]  {result['total_new']:,} new movies in {result['elapsed']:.1f}s\n"
        f"Total corpus: [yellow]{result['total_indexed']:,}[/] movies  "
        f"([dim]{_fmt_mb(result['total_indexed'] * 16 / 1024)}[/])",
        border_style="green",
    ))
    _pause()


# ── Action: Job Progress ──────────────────────────────────────────────────────

def action_progress():
    console.rule("[yellow]Job Progress[/]")
    with console.status("[bold green]Loading…"):
        from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
        pipeline = EnrichmentPipeline()
        progress = pipeline.get_bulk_progress()

    if progress["total_jobs"] == 0:
        console.print(
            f"  [dim]No jobs in queue.[/]  Corpus: [yellow]{progress['total_indexed']:,}[/] movies"
        )
        _pause()
        return

    done = progress["done"]
    total = progress["total_jobs"]
    console.print(f"  Overall: [yellow]{done}/{total}[/] ({done/total*100:.1f}%)  ·  "
                  f"Corpus: [yellow]{progress['total_indexed']:,}[/] movies "
                  f"([dim]{_fmt_mb(progress['est_size_mb'])}[/])\n")

    tbl = Table("Language", "Pri", "Done", "Pending", "Failed", "Movies", "Progress",
                border_style="bright_black", box=box.ROUNDED, header_style="bold yellow")
    for lp in progress["by_language"]:
        name = LANGUAGE_NAMES.get(lp["language"], lp["language"])
        pct = (lp["done"] / lp["total"] * 100) if lp["total"] > 0 else 0
        bar = "[yellow]" + "█" * int(pct / 5) + "[/][dim]" + "░" * (20 - int(pct / 5)) + "[/]"
        tbl.add_row(
            name, str(lp["priority"]),
            str(lp["done"]), str(lp["pending"]),
            f"[red]{lp['failed']}[/]" if lp["failed"] else "0",
            str(lp.get("movies_found", 0)),
            f"{bar} {pct:.0f}%",
        )
    console.print(tbl)
    _pause()


# ── Action: Rotation ──────────────────────────────────────────────────────────

def action_rotation():
    console.rule("[yellow]Overnight Rotation[/]")
    with console.status("[bold green]Loading candidates…"):
        from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES
        pipeline = EnrichmentPipeline()
        tracker_count = pipeline.tracker.count()
        candidates = pipeline.tracker.get_rotation_candidates(keep_days=30)

    console.print(f"  Corpus: [yellow]{tracker_count:,}[/] movies")
    console.print(f"  Rotation candidates (unused >30 days): [yellow]{len(candidates)}[/]")

    if not candidates:
        console.print("[dim]  Nothing to remove.[/]")
        _pause()
        return

    by_lang: dict[str, int] = {}
    for c in candidates:
        lang = c.get("original_language", "?")
        by_lang[lang] = by_lang.get(lang, 0) + 1

    tbl = Table("Language", "Candidates", box=box.SIMPLE, border_style="bright_black")
    for lang, cnt in sorted(by_lang.items(), key=lambda x: -x[1]):
        tbl.add_row(LANGUAGE_NAMES.get(lang, lang), str(cnt))
    console.print(tbl)

    target = float(Prompt.ask("\n  Target corpus size to keep (GB)", default="15"))
    if not Confirm.ask(f"  Proceed with rotation (keep ≈{target} GB)?", default=False):
        console.print("[dim]  Cancelled.[/]")
        _pause()
        return

    with console.status("[bold green]Running rotation…"):
        result = pipeline.rotate_unused(keep_gb=target)
    console.print(f"[green]  ✓ Removed {result['removed']:,} movies[/]")
    _pause()


# ── Action: Search Index ──────────────────────────────────────────────────────

def action_search():
    console.rule("[yellow]Search Index[/]")
    query = Prompt.ask("  Title or TMDB ID").strip()
    if not query:
        _pause()
        return

    import sqlite3
    from src.services.enrichment_pipeline import _IndexedTracker
    tracker = _IndexedTracker()

    with sqlite3.connect(str(tracker.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM enrichment_log WHERE tmdb_id = ?", (query,)).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT * FROM enrichment_log WHERE source LIKE ? LIMIT 20",
                (f"%{query}%",),
            ).fetchall()

    if not rows:
        console.print(f"  [dim]No results for '{query}'[/]")
        _pause()
        return

    tbl = Table("TMDB ID", "Language", "Source", "Usage", "Last Used",
                border_style="bright_black", box=box.SIMPLE)
    for r in rows:
        rd = dict(r)
        tbl.add_row(
            str(rd.get("tmdb_id", "?")),
            rd.get("original_language", "?"),
            (rd.get("source") or "")[:40],
            str(rd.get("usage_count", 0) or 0),
            rd.get("last_used_at") or "never",
        )
    console.print(tbl)
    _pause()


# ── Action: Clear Queue ───────────────────────────────────────────────────────

def action_clear_queue():
    console.rule("[yellow]Clear Job Queue[/]")
    from src.services.enrichment_pipeline import EnrichmentPipeline
    pipeline = EnrichmentPipeline()
    job_counts = pipeline.tracker.count_jobs()
    total = sum(job_counts.values())

    if total == 0:
        console.print("  [dim]Queue is already empty.[/]")
        _pause()
        return

    console.print(f"  Current queue: {job_counts}")
    console.print()

    tbl = Table(box=None, show_header=False, padding=(0, 2))
    tbl.add_column(style="bold yellow", min_width=4)
    tbl.add_column(style="white")
    for key, label in [("1","Clear ALL jobs"),("2","Clear only FAILED jobs"),
                       ("3","Clear only PENDING jobs"),("0","Cancel")]:
        tbl.add_row(f"[{key}]", label)
    console.print(tbl)

    choice = Prompt.ask("  Choose", choices=["0","1","2","3"], default="0")

    if choice == "1":
        if Confirm.ask("  Clear [bold red]ALL[/] jobs?", default=False):
            pipeline.tracker.clear_jobs()
            console.print("[green]  ✓ All jobs cleared.[/]")
    elif choice == "2":
        pipeline.tracker.clear_jobs(status="failed")
        console.print("[green]  ✓ Failed jobs cleared.[/]")
    elif choice == "3":
        pipeline.tracker.clear_jobs(status="pending")
        console.print("[green]  ✓ Pending jobs cleared.[/]")
    else:
        console.print("[dim]  Cancelled.[/]")
    _pause()


# ── Action: Test Recommendation ───────────────────────────────────────────────

def action_test_rec():
    console.rule("[yellow]Test Recommendation Pipeline[/]")
    import requests as _http

    user_id = Prompt.ask("  User ID to test").strip()
    if not user_id:
        _pause()
        return
    k = IntPrompt.ask("  Number of recommendations", default=5)

    api = "http://localhost:8000/api/v1"
    console.print(f"\n  Submitting job for [yellow]{user_id}[/]…")
    try:
        resp = _http.post(f"{api}/recommendations/async",
                          json={"user_id": user_id, "k": k}, timeout=15)
        if resp.status_code not in (200, 202):
            console.print(f"[red]  API error: {resp.text}[/]")
            _pause()
            return
        job_id = resp.json()["job_id"]
    except Exception as e:
        console.print(f"[red]  Cannot reach API at port 8000: {e}[/]")
        _pause()
        return

    ALL_AGENTS = ["Profile Analyzer","Context-Aware","Retrieval",
                  "Content Intelligence","Serendipity","Explanation","Aggregation"]
    data: dict = {}
    deadline = time.time() + 90

    with Live(console=console, refresh_per_second=4) as live:
        while time.time() < deadline:
            try:
                poll = _http.get(f"{api}/recommendations/result/{job_id}", timeout=10)
                data = poll.json()
                steps = data.get("steps", [])
                done_set = {s["step"] for s in steps}

                lines = ["[bold yellow]🎬 CineMatch pipeline:[/]\n"]
                for i, agent in enumerate(ALL_AGENTS):
                    if agent in done_set:
                        detail = next((s["detail"] for s in steps if s["step"] == agent), "done")
                        lines.append(f"  [green]✓[/] [yellow]{agent}[/] [dim]— {detail}[/]")
                    elif i == len(done_set):
                        lines.append(f"  [blink]⚙[/] [bold]{agent}[/] [dim]— processing…[/]")
                    else:
                        lines.append(f"  [dim]○ {agent}[/]")
                live.update(Panel("\n".join(lines), border_style="bright_black"))

                if data["status"] == "complete":
                    break
                if data["status"] == "failed":
                    console.print(f"[red]  Pipeline failed: {data.get('error')}[/]")
                    _pause()
                    return
                time.sleep(0.6)
            except Exception:
                time.sleep(1)

    recs = data.get("result", {}).get("recommendations", [])
    if not recs:
        console.print("[dim]  No recommendations returned.[/]")
        _pause()
        return

    tbl = Table("#", "Title", "Year", "Genres", "Score",
                border_style="bright_black", box=box.ROUNDED, header_style="bold yellow", min_width=65)
    for rec in recs:
        m = rec["movie"]
        genres = ", ".join((m.get("genres") or [])[:3])
        pct = int(rec.get("score", 0) * 100)
        color = "yellow" if pct >= 70 else ("red" if pct >= 40 else "dim")
        tbl.add_row(str(rec.get("rank","?")), m.get("title","?"), str(m.get("year","")),
                    genres, f"[{color}]{pct}%[/]")
    console.print(tbl)
    _pause()


# ── Action: LLM Health Check ──────────────────────────────────────────────────

def action_llm_check():
    console.rule("[yellow]LLM Health Check[/]")
    test_prompt = "Reply with exactly: OK"

    for provider_name in ["groq", "ollama"]:
        try:
            from config.settings import get_settings
            s = get_settings()
            if provider_name == "groq" and not getattr(s, "groq_api_key", None):
                console.print(f"  [yellow]groq[/]   [dim]SKIP — no API key[/]")
                continue

            from src.utils.llm_client import get_llm_client, LLMProvider
            provider = LLMProvider.GROQ if provider_name == "groq" else LLMProvider.OLLAMA
            client = get_llm_client(provider=provider, use_fast_model=True)

            t0 = time.time()
            resp = client.generate(test_prompt, max_tokens=10)
            latency = (time.time() - t0) * 1000
            console.print(
                f"  [green]✓[/] [bold]{provider_name}[/]  [dim]{client.model}[/]  →  "
                f"[white]{resp.strip()[:30]}[/]  [dim]({latency:.0f}ms)[/]"
            )
        except Exception as e:
            console.print(f"  [red]✗[/] [bold]{provider_name}[/]  [red]{e}[/]")

    _pause()


# ── Main loop ─────────────────────────────────────────────────────────────────

ACTIONS = {
    "1": action_stats,
    "2": action_bulk,
    "3": action_progress,
    "4": action_rotation,
    "5": action_search,
    "6": action_clear_queue,
    "7": action_test_rec,
    "8": action_llm_check,
}


def main():
    _banner()

    while True:
        choice = _main_menu()
        if choice == "0":
            console.print("\n[yellow]  Goodbye! 🎬[/]\n")
            break
        action = ACTIONS.get(choice)
        if action:
            try:
                console.print()
                action()
            except KeyboardInterrupt:
                console.print("\n[dim]  Interrupted — returning to menu.[/]")
            except Exception as e:
                console.print(f"\n[red]  Error:[/] {e}")
                _pause()


if __name__ == "__main__":
    main()
