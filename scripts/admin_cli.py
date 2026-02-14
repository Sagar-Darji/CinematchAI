"""CineMatch AI — Interactive Admin Console.

Usage:
    python -m scripts.admin_cli

Provides a menu-driven interface for managing the enrichment pipeline,
viewing corpus stats, starting bulk enrichment, and running rotation.
"""

import sys
import time
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def _format_size(mb: float) -> str:
    if mb >= 1024:
        return f"{mb/1024:.2f} GB"
    return f"{mb:.1f} MB"


def _progress_bar(current: int, total: int, width: int = 30) -> str:
    if total == 0:
        return "[" + " " * width + "]   0%"
    pct = current / total
    filled = int(width * pct)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {pct*100:5.1f}%"


def _get_pipeline():
    from src.services.enrichment_pipeline import EnrichmentPipeline
    return EnrichmentPipeline()


def _get_language_names():
    from src.services.enrichment_pipeline import LANGUAGE_NAMES
    return LANGUAGE_NAMES


def show_menu():
    print()
    print("=" * 50)
    print("     CineMatch AI -- Admin Console")
    print("=" * 50)
    print("  1. Corpus Stats")
    print("  2. Start Bulk Enrichment")
    print("  3. View Job Progress")
    print("  4. Run Overnight Rotation")
    print("  5. Search Indexed Movies")
    print("  6. Clear Job Queue")
    print("  7. Exit")
    print("=" * 50)


def corpus_stats():
    """Show detailed corpus statistics."""
    pipeline = _get_pipeline()
    lang_names = _get_language_names()

    counts = pipeline.cloud_db.count()
    tracker_count = pipeline.tracker.count()
    est_mb = tracker_count * 16 / 1024

    print(f"\n--- Corpus Statistics ---")
    print(f"  Total movies tracked: {tracker_count}")
    print(f"  Estimated size: {_format_size(est_mb)}")
    print()

    print(f"  Backend Counts:")
    for backend, count in counts.items():
        print(f"    {backend}: {count} vectors")
    print()

    availability = pipeline.cloud_db.is_available()
    print(f"  Backend Availability:")
    for backend, available in availability.items():
        status = "UP" if available else "DOWN"
        print(f"    {backend}: {status}")
    print()

    dist = pipeline.get_language_distribution()
    if dist:
        print(f"  Language Distribution:")
        for lang, count in sorted(dist.items(), key=lambda x: -x[1]):
            name = lang_names.get(lang, lang)
            pct = (count / tracker_count * 100) if tracker_count > 0 else 0
            bar = _progress_bar(count, tracker_count, width=20)
            print(f"    {name:>12} ({lang:>2}): {count:>6} movies ({pct:5.1f}%) {bar}")
    else:
        print("  No language data available.")


def start_bulk_enrichment():
    """Start bulk enrichment with interactive config."""
    pipeline = _get_pipeline()
    lang_names = _get_language_names()

    print(f"\n--- Start Bulk Enrichment ---")

    try:
        max_pages_str = input("  Max pages this run [500]: ").strip()
        max_pages = int(max_pages_str) if max_pages_str else 500
    except ValueError:
        max_pages = 500

    try:
        target_str = input("  Target corpus size in GB [15]: ").strip()
        target = float(target_str) if target_str else 15.0
    except ValueError:
        target = 15.0

    confirm = input(f"\n  Start bulk enrichment (max_pages={max_pages}, target={target}GB)? [y/N]: ").strip()
    if confirm.lower() != "y":
        print("  Cancelled.")
        return

    print(f"\n  Running bulk enrichment...")
    print(f"  Target: {target} GB | Max pages: {max_pages}")
    print("  " + "-" * 50)

    def progress_cb(info):
        job = info.get("current_job", {})
        lang = job.get("language", "??")
        lang_name = lang_names.get(lang, lang)
        pages_done = info["pages_processed"]
        total_new = info["total_new"]
        rate = info.get("rate", 0)
        total_indexed = info.get("total_indexed", 0)
        est_mb = total_indexed * 16 / 1024

        bar = _progress_bar(pages_done, max_pages, width=25)
        eta_sec = (max_pages - pages_done) / rate if rate > 0 else 0
        eta_str = f"{eta_sec/60:.1f}m" if eta_sec > 60 else f"{eta_sec:.0f}s"

        print(
            f"\r  {bar} | {lang_name:>8} | +{total_new} new | "
            f"{total_indexed} total ({_format_size(est_mb)}) | ETA: {eta_str}   ",
            end="", flush=True,
        )

    result = pipeline.run_bulk_local(
        target_gb=target,
        max_pages=max_pages,
        progress_callback=progress_cb,
    )

    print()
    print("  " + "-" * 50)
    print(f"  Done! {result['total_new']} new movies in {result['elapsed']:.1f}s")
    print(f"  Total corpus: {result['total_indexed']} movies "
          f"(~{_format_size(result['total_indexed'] * 16 / 1024)})")

    dist = pipeline.get_language_distribution()
    if dist:
        print(f"\n  Language Breakdown:")
        for lang, count in sorted(dist.items(), key=lambda x: -x[1])[:10]:
            name = lang_names.get(lang, lang)
            print(f"    {name:>12}: {count:>6} movies")


def view_job_progress():
    """View current bulk job progress."""
    pipeline = _get_pipeline()
    lang_names = _get_language_names()

    progress = pipeline.get_bulk_progress()

    if progress["total_jobs"] == 0:
        print("\n  No bulk jobs in queue. Use option 2 to start.")
        return

    print(f"\n--- Bulk Job Progress ---")
    print(f"  Overall: {_progress_bar(progress['done'], progress['total_jobs'])}")
    print(f"  Done: {progress['done']} | Pending: {progress['pending']} | "
          f"Failed: {progress['failed']} | Total: {progress['total_jobs']}")
    print(f"  Corpus: {progress['total_indexed']} movies (~{_format_size(progress['est_size_mb'])})")
    print()

    print(f"  {'Language':<14} {'Pri':<5} {'Done':<7} {'Pend':<7} {'Fail':<6} "
          f"{'Movies':<8} {'Progress'}")
    print("  " + "-" * 72)
    for lp in progress["by_language"]:
        lang = lp["language"]
        name = lang_names.get(lang, lang)
        bar = _progress_bar(lp["done"], lp["total"], width=15)
        print(f"  {name:<14} P{lp['priority']:<4} {lp['done']:<7} {lp['pending']:<7} "
              f"{lp['failed']:<6} {lp['movies_found']:<8} {bar}")


def run_rotation():
    """Run overnight rotation with confirmation."""
    pipeline = _get_pipeline()

    tracker_count = pipeline.tracker.count()
    est_mb = tracker_count * 16 / 1024

    print(f"\n--- Overnight Rotation ---")
    print(f"  Current corpus: {tracker_count} movies (~{_format_size(est_mb)})")

    candidates = pipeline.tracker.get_rotation_candidates(keep_days=30)
    print(f"  Rotation candidates (unused, >30 days old): {len(candidates)}")

    if not candidates:
        print("  No candidates for removal.")
        return

    # Show breakdown by language
    lang_names = _get_language_names()
    by_lang = {}
    for c in candidates:
        lang = c.get("original_language", "unknown")
        by_lang[lang] = by_lang.get(lang, 0) + 1
    print(f"\n  Candidates by language:")
    for lang, count in sorted(by_lang.items(), key=lambda x: -x[1]):
        name = lang_names.get(lang, lang)
        print(f"    {name:>12}: {count}")

    try:
        target_str = input("\n  Target corpus size in GB [15]: ").strip()
        target = float(target_str) if target_str else 15.0
    except ValueError:
        target = 15.0

    confirm = input(f"  Proceed with rotation (keep={target}GB)? [y/N]: ").strip()
    if confirm.lower() != "y":
        print("  Cancelled.")
        return

    result = pipeline.rotate_unused(keep_gb=target)
    print(f"\n  Removed: {result['removed']} movies")
    if "size_gb" in result:
        print(f"  Corpus size after: {result['size_gb']:.3f} GB")


def search_indexed():
    """Search for movies in the index."""
    import sqlite3
    from src.services.enrichment_pipeline import _IndexedTracker

    tracker = _IndexedTracker()

    query = input("\n  Search title or TMDB ID: ").strip()
    if not query:
        return

    with sqlite3.connect(str(tracker.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        # Search by tmdb_id exact match first
        rows = conn.execute(
            "SELECT * FROM enrichment_log WHERE tmdb_id = ?", (query,)
        ).fetchall()

        if not rows:
            # Search by source containing the query (rough text match)
            rows = conn.execute(
                "SELECT * FROM enrichment_log WHERE source LIKE ? LIMIT 20",
                (f"%{query}%",)
            ).fetchall()

    if not rows:
        print(f"  No results for '{query}'")
        return

    print(f"\n  Found {len(rows)} result(s):")
    for r in rows:
        r = dict(r)
        usage = r.get("usage_count", 0) or 0
        last_used = r.get("last_used_at", "never") or "never"
        lang = r.get("original_language", "?") or "?"
        print(f"    TMDB {r['tmdb_id']:>10} | lang={lang:>2} | source={r['source']:<30} | "
              f"usage={usage} | last_used={last_used}")


def clear_job_queue():
    """Clear the bulk job queue."""
    pipeline = _get_pipeline()
    job_counts = pipeline.tracker.count_jobs()
    total = sum(job_counts.values())

    if total == 0:
        print("\n  Job queue is already empty.")
        return

    print(f"\n--- Clear Job Queue ---")
    print(f"  Current jobs: {job_counts}")

    print("  Options:")
    print("    1. Clear ALL jobs")
    print("    2. Clear only FAILED jobs")
    print("    3. Clear only PENDING jobs")
    print("    4. Cancel")

    choice = input("  Choice [4]: ").strip()

    if choice == "1":
        confirm = input("  Clear ALL jobs? [y/N]: ").strip()
        if confirm.lower() == "y":
            pipeline.tracker.clear_jobs()
            print("  All jobs cleared.")
    elif choice == "2":
        pipeline.tracker.clear_jobs(status="failed")
        print("  Failed jobs cleared.")
    elif choice == "3":
        pipeline.tracker.clear_jobs(status="pending")
        print("  Pending jobs cleared.")
    else:
        print("  Cancelled.")


def main():
    print("\nInitializing CineMatch AI Admin Console...")

    while True:
        show_menu()
        choice = input("  Select option [1-7]: ").strip()

        try:
            if choice == "1":
                corpus_stats()
            elif choice == "2":
                start_bulk_enrichment()
            elif choice == "3":
                view_job_progress()
            elif choice == "4":
                run_rotation()
            elif choice == "5":
                search_indexed()
            elif choice == "6":
                clear_job_queue()
            elif choice == "7":
                print("\nGoodbye!")
                break
            else:
                print("  Invalid option. Please enter 1-7.")
        except KeyboardInterrupt:
            print("\n\n  Interrupted. Returning to menu...")
        except Exception as e:
            print(f"\n  Error: {e}")

        input("\n  Press Enter to continue...")


if __name__ == "__main__":
    main()
