"""Run the movie enrichment pipeline manually or on schedule.

Usage:
    python -m scripts.run_enrichment --full     # Full enrichment cycle (~4 min)
    python -m scripts.run_enrichment --light    # Light cycle (trending only, ~30s)
    python -m scripts.run_enrichment --user USER_ID  # Index a user's rated movies
    python -m scripts.run_enrichment --migrate  # Migrate ChromaDB -> cloud
    python -m scripts.run_enrichment --stats    # Show corpus stats
    python -m scripts.run_enrichment --bulk     # Bulk local enrichment (Hindi-first)
    python -m scripts.run_enrichment --bulk --max-pages 10   # Test with 10 pages
    python -m scripts.run_enrichment --progress # Show bulk job progress
    python -m scripts.run_enrichment --rotate   # Run overnight rotation
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _print_progress_bar(current: int, total: int, width: int = 40) -> str:
    """Simple ASCII progress bar."""
    if total == 0:
        return "[" + " " * width + "]  0%"
    pct = current / total
    filled = int(width * pct)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {pct*100:5.1f}%"


def _format_size(mb: float) -> str:
    if mb >= 1024:
        return f"{mb/1024:.2f} GB"
    return f"{mb:.1f} MB"


def run_bulk(args):
    """Run bulk local enrichment with live progress."""
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES

    pipeline = EnrichmentPipeline()
    max_pages = args.max_pages
    target = args.target
    languages = args.language or None  # None = all languages

    if languages:
        lang_label = ", ".join(LANGUAGE_NAMES.get(l, l) for l in languages)
        print(f"\nBulk Enrichment -- Languages: {lang_label}")
    else:
        print(f"\nBulk Enrichment -- All Languages (Hindi-first)")
    print(f"Target: {target} GB | Max pages this run: {max_pages}")
    print("=" * 60)

    last_lang = [None]

    def progress_cb(info):
        job = info.get("current_job", {})
        lang = job.get("language", "??")
        lang_name = LANGUAGE_NAMES.get(lang, lang)
        genre_id = job.get("genre_id", "")
        decade = job.get("decade_start", "")
        pages_done = info["pages_processed"]
        total_new = info["total_new"]
        skipped = info.get("pages_skipped", 0)
        fetched = info.get("pages_fetched", 0)
        cache_st = info.get("cache_status", "")
        rate = info.get("rate", 0)
        total_indexed = info.get("total_indexed", 0)
        est_mb = total_indexed * 16 / 1024

        bar = _print_progress_bar(pages_done, max_pages)

        # Clear line and print
        decade_str = f"{decade}s" if decade else "all"
        genre_str = f"genre={genre_id}" if genre_id else "popular"
        eta_sec = (max_pages - pages_done) / rate if rate > 0 else 0
        eta_str = f"{eta_sec/60:.1f} min" if eta_sec > 60 else f"{eta_sec:.0f}s"
        cache_indicator = "SKIP" if cache_st.startswith("skip") else "FETCH"

        print(
            f"\r{bar} | {lang_name:>10} | {genre_str:>12} | {decade_str:>5} | "
            f"{cache_indicator:>5} | +{total_new} new | skip:{skipped} fetch:{fetched} | "
            f"{total_indexed} total ({_format_size(est_mb)}) | "
            f"{rate:.1f} pg/s | ETA: {eta_str}   ",
            end="", flush=True,
        )

    result = pipeline.run_bulk_local(
        target_gb=target,
        max_pages=max_pages,
        progress_callback=progress_cb,
        languages=languages,
    )

    print()  # newline after progress
    print("=" * 60)
    print(f"Done! {result['total_new']} new movies indexed in {result['elapsed']:.1f}s")
    print(f"  Pages processed: {result['pages_processed']} "
          f"(fetched: {result.get('pages_fetched', '?')}, "
          f"skipped: {result.get('pages_skipped', '?')})")
    print(f"Total corpus: {result['total_indexed']} movies "
          f"(~{_format_size(result['total_indexed'] * 16 / 1024)})")

    # Show language breakdown
    dist = pipeline.get_language_distribution()
    if dist:
        print(f"\nLanguage Breakdown:")
        for lang, count in sorted(dist.items(), key=lambda x: -x[1]):
            name = LANGUAGE_NAMES.get(lang, lang)
            print(f"  {name:>12} ({lang:>2}): {count:>6} movies")


def show_progress(args):
    """Show current bulk job progress."""
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES

    pipeline = EnrichmentPipeline()
    progress = pipeline.get_bulk_progress()

    if progress["total_jobs"] == 0:
        print("\nNo bulk jobs in queue. Run --bulk to start.")

    print(f"\nBulk Job Progress")
    print("=" * 70)

    # Page registry stats (always show even if no jobs in queue)
    reg = progress.get("page_registry", {})
    if reg.get("total_cached_pages", 0) > 0:
        print(f"  Page Registry: {reg['total_cached_pages']} pages cached "
              f"({reg['pages_with_results']} with results, {reg['empty_pages']} empty), "
              f"{reg['total_fetches']} total fetches")

    if progress["total_jobs"] == 0:
        print(f"  Corpus: {progress['total_indexed']} movies (~{_format_size(progress['est_size_mb'])})")
        return

    print(f"Overall: {_print_progress_bar(progress['done'], progress['total_jobs'])}")
    print(f"  Done: {progress['done']} | Pending: {progress['pending']} | "
          f"Failed: {progress['failed']} | Total: {progress['total_jobs']}")
    print(f"  Corpus: {progress['total_indexed']} movies (~{_format_size(progress['est_size_mb'])})")
    print()

    # Per-language table
    print(f"{'Language':<15} {'Priority':<9} {'Done':<8} {'Pending':<9} "
          f"{'Failed':<8} {'Movies':<10} {'Progress'}")
    print("-" * 80)
    for lp in progress["by_language"]:
        lang = lp["language"]
        name = LANGUAGE_NAMES.get(lang, lang)
        pct = (lp["done"] / lp["total"] * 100) if lp["total"] > 0 else 0
        bar = _print_progress_bar(lp["done"], lp["total"], width=20)
        print(f"  {name:<13} P{lp['priority']:<7} {lp['done']:<8} {lp['pending']:<9} "
              f"{lp['failed']:<8} {lp['movies_found']:<10} {bar}")


def show_stats(args):
    """Show corpus statistics."""
    from src.services.enrichment_pipeline import EnrichmentPipeline, LANGUAGE_NAMES

    pipeline = EnrichmentPipeline()

    counts = pipeline.cloud_db.count()
    tracker_count = pipeline.tracker.count()
    est_mb = tracker_count * 16 / 1024

    print(f"\nCorpus Statistics:")
    print(f"  Enrichment tracker: {tracker_count} movies (~{_format_size(est_mb)})")
    for backend, count in counts.items():
        print(f"  {backend}: {count} vectors")

    availability = pipeline.cloud_db.is_available()
    print(f"\nBackend Availability:")
    for backend, available in availability.items():
        status = "UP" if available else "DOWN"
        print(f"  {backend}: {status}")

    # Language distribution
    dist = pipeline.get_language_distribution()
    if dist:
        print(f"\nLanguage Distribution:")
        for lang, count in sorted(dist.items(), key=lambda x: -x[1]):
            name = LANGUAGE_NAMES.get(lang, lang)
            pct = (count / tracker_count * 100) if tracker_count > 0 else 0
            bar_len = int(pct / 2)
            bar = "#" * bar_len
            print(f"  {name:>12} ({lang:>2}): {count:>6} movies ({pct:5.1f}%) {bar}")


def run_rotation(args):
    """Run overnight rotation."""
    from src.services.enrichment_pipeline import EnrichmentPipeline

    pipeline = EnrichmentPipeline()
    target = args.target

    print(f"\nOvernight Rotation (target: {target} GB)")
    print("=" * 50)

    result = pipeline.rotate_unused(keep_gb=target)

    print(f"  Candidates: {result.get('candidates', 0)}")
    print(f"  Removed: {result['removed']}")
    if "size_gb" in result:
        print(f"  Corpus size: {result['size_gb']:.3f} GB")


def main():
    parser = argparse.ArgumentParser(description="CineMatch AI Movie Enrichment Pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true",
                       help="Full enrichment cycle (all strategies x all languages)")
    group.add_argument("--light", action="store_true",
                       help="Light cycle (trending only)")
    group.add_argument("--user", type=str,
                       help="Enrich movies for a specific user ID")
    group.add_argument("--migrate", action="store_true",
                       help="Migrate local ChromaDB to cloud vector DBs")
    group.add_argument("--stats", action="store_true",
                       help="Show corpus statistics")
    group.add_argument("--bulk", action="store_true",
                       help="Run bulk local enrichment (Hindi -> English -> Other Indian)")
    group.add_argument("--progress", action="store_true",
                       help="Show current bulk job progress")
    group.add_argument("--rotate", action="store_true",
                       help="Run overnight rotation (remove least-used movies)")

    parser.add_argument("--max-pages", type=int, default=500,
                        help="Max pages per bulk run (default: 500)")
    parser.add_argument("--target", type=float, default=15.0,
                        help="Target corpus size in GB (default: 15)")
    parser.add_argument(
        "--language", nargs="+", metavar="LANG",
        help="Language codes to process (e.g. hi en ta). Omit for all languages."
    )

    args = parser.parse_args()

    if args.bulk:
        run_bulk(args)
    elif args.progress:
        show_progress(args)
    elif args.stats:
        show_stats(args)
    elif args.rotate:
        run_rotation(args)
    elif args.migrate:
        from src.services.enrichment_pipeline import EnrichmentPipeline
        pipeline = EnrichmentPipeline()
        count = pipeline.migrate_from_chromadb()
        print(f"\nMigrated {count} movies from ChromaDB to cloud vector DBs")
    elif args.user:
        from src.services.enrichment_pipeline import EnrichmentPipeline
        pipeline = EnrichmentPipeline()
        count = pipeline.enrich_user_movies(args.user)
        print(f"\nEnriched {count} movies for user '{args.user}'")
    elif args.light:
        from src.services.enrichment_pipeline import EnrichmentPipeline
        pipeline = EnrichmentPipeline()
        count = pipeline.run_light_cycle()
        print(f"\nLight enrichment complete: {count} new movies indexed")
    else:  # --full
        from src.services.enrichment_pipeline import EnrichmentPipeline
        pipeline = EnrichmentPipeline()
        count = pipeline.run_full_cycle()
        print(f"\nFull enrichment complete: {count} new movies indexed")


if __name__ == "__main__":
    main()
