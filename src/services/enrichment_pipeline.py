"""Background Enrichment Pipeline — grows the movie corpus automatically.

Fetches movies across multiple languages and strategies from TMDB,
generates embeddings, and upserts them into all cloud vector DB backends.

Includes bulk local enrichment (Hindi-first pipeline) with SQLite job queue,
streaming processor, overnight rotation, and usage tracking.
"""

import gc
import hashlib
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

ENRICHMENT_LANGUAGES = settings.enrichment_languages

ENRICHMENT_STRATEGIES = [
    ("trending_weekly", {"time_window": "week"}),
    ("popular_by_language", {"sort_by": "popularity.desc"}),
    ("top_rated", {"sort_by": "vote_average.desc", "vote_count.gte": 200}),
    ("recent_releases", {"days": 180}),
]

# ----------------------------------------------------------------
# TMDB genre IDs (same as smart_query, duplicated to avoid circular imports)
# ----------------------------------------------------------------
_GENRE_IDS = {
    "Action": 28, "Adventure": 12, "Animation": 16, "Comedy": 35,
    "Crime": 80, "Documentary": 99, "Drama": 18, "Family": 10751,
    "Fantasy": 14, "History": 36, "Horror": 27, "Music": 10402,
    "Mystery": 9648, "Romance": 10749, "Science Fiction": 878,
    "TV Movie": 10770, "Thriller": 53, "War": 10752, "Western": 37,
}
ALL_GENRE_IDS = list(_GENRE_IDS.values())

# ----------------------------------------------------------------
# Bulk enrichment job distribution config
# ----------------------------------------------------------------
BULK_LANGUAGE_CONFIG: List[Dict[str, Any]] = [
    # Priority 1 — Hindi (most coverage)
    {
        "language": "hi", "priority": 1,
        "genre_ids": ALL_GENRE_IDS[:15],
        "decades": list(range(1950, 2030, 10)),  # 1950s-2020s = 8
        "pages_per_combo": 3,
        "explore_depth": 20,       # explore up to 20 pages per genre+decade combo
        "popular_pages": 25,
        "popular_explore_depth": 50,
        "top_rated_decades": list(range(1950, 2030, 10)),
        "top_rated_pages": 5,
        "top_rated_explore_depth": 15,
    },
    # Priority 2 — English
    {
        "language": "en", "priority": 2,
        "genre_ids": ALL_GENRE_IDS[:15],
        "decades": list(range(1960, 2030, 10)),  # 1960s-2020s = 7
        "pages_per_combo": 2,
        "explore_depth": 15,
        "popular_pages": 15,
        "popular_explore_depth": 40,
        "top_rated_decades": list(range(1960, 2030, 10)),
        "top_rated_pages": 3,
        "top_rated_explore_depth": 10,
    },
    # Priority 3 — Other Indian languages
    {"language": "ta", "priority": 3, "genre_ids": ALL_GENRE_IDS[:10],
     "decades": list(range(1980, 2030, 10)), "pages_per_combo": 2,
     "explore_depth": 10},
    {"language": "te", "priority": 3, "genre_ids": ALL_GENRE_IDS[:10],
     "decades": list(range(1980, 2030, 10)), "pages_per_combo": 2,
     "explore_depth": 10},
    {"language": "ml", "priority": 3, "genre_ids": ALL_GENRE_IDS[:8],
     "decades": list(range(1990, 2030, 10)), "pages_per_combo": 2,
     "explore_depth": 8},
    {"language": "kn", "priority": 3, "genre_ids": ALL_GENRE_IDS[:6],
     "decades": list(range(2000, 2030, 10)), "pages_per_combo": 1,
     "explore_depth": 5},
    {"language": "bn", "priority": 3, "genre_ids": ALL_GENRE_IDS[:6],
     "decades": list(range(2000, 2030, 10)), "pages_per_combo": 1,
     "explore_depth": 5},
    {"language": "mr", "priority": 3, "genre_ids": ALL_GENRE_IDS[:5],
     "decades": list(range(2000, 2030, 10)), "pages_per_combo": 1,
     "explore_depth": 5},
    {"language": "gu", "priority": 3, "genre_ids": ALL_GENRE_IDS[:4],
     "decades": list(range(2010, 2030, 10)), "pages_per_combo": 1,
     "explore_depth": 3},
    {"language": "pa", "priority": 3, "genre_ids": ALL_GENRE_IDS[:4],
     "decades": list(range(2010, 2030, 10)), "pages_per_combo": 1,
     "explore_depth": 3},
]

# Language display names
LANGUAGE_NAMES = {
    "hi": "Hindi", "en": "English", "ta": "Tamil", "te": "Telugu",
    "ml": "Malayalam", "kn": "Kannada", "bn": "Bengali", "mr": "Marathi",
    "gu": "Gujarati", "pa": "Punjabi",
}

# Staleness TTL by sort strategy (days before a cached page is re-fetched)
STALE_TTL_DAYS = {
    "popularity.desc": 3,       # Popularity shifts frequently
    "vote_average.desc": 14,    # Ratings are stable
    "revenue.desc": 7,
}
DEFAULT_TTL = 7


class _IndexedTracker:
    """SQLite tracker for already-indexed movie IDs to avoid re-processing."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(settings.data_dir) / "enrichment_log.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            # Core enrichment log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enrichment_log (
                    tmdb_id TEXT PRIMARY KEY,
                    indexed_at TEXT NOT NULL,
                    source TEXT NOT NULL
                )
            """)
            # Add usage tracking columns (safe if they already exist)
            for col, typedef in [
                ("usage_count", "INTEGER DEFAULT 0"),
                ("last_used_at", "TEXT"),
                ("original_language", "TEXT DEFAULT ''"),
                ("priority", "INTEGER DEFAULT 2"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE enrichment_log ADD COLUMN {col} {typedef}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Bulk jobs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bulk_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    language TEXT NOT NULL,
                    genre_id INTEGER,
                    decade_start INTEGER,
                    sort_by TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 2,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    movies_found INTEGER DEFAULT 0,
                    error_msg TEXT,
                    wave INTEGER DEFAULT 1
                )
            """)
            # Add wave column if missing (for existing DBs)
            try:
                conn.execute("ALTER TABLE bulk_jobs ADD COLUMN wave INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass

            # Persistent metadata (survives queue clears)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS enrichment_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_bulk_jobs_status
                ON bulk_jobs(status, priority, id)
            """)

            # Page registry — tracks fingerprints and staleness per TMDB page
            conn.execute("""
                CREATE TABLE IF NOT EXISTS page_registry (
                    combo_key TEXT NOT NULL,
                    page INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    tmdb_ids TEXT NOT NULL,
                    total_pages INTEGER,
                    total_results INTEGER,
                    result_count INTEGER DEFAULT 0,
                    last_fetched_at TEXT NOT NULL,
                    fetch_count INTEGER DEFAULT 1,
                    PRIMARY KEY (combo_key, page)
                )
            """)
            conn.commit()

    # ---- core tracker methods ----
    def is_indexed(self, tmdb_id: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM enrichment_log WHERE tmdb_id = ?", (tmdb_id,)
            ).fetchone()
            return row is not None

    def get_indexed_ids(self) -> Set[str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute("SELECT tmdb_id FROM enrichment_log").fetchall()
            return {r[0] for r in rows}

    def mark_indexed(self, tmdb_ids: List[str], source: str,
                     language: str = "", priority: int = 2):
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO enrichment_log
                   (tmdb_id, indexed_at, source, original_language, priority)
                   VALUES (?, ?, ?, ?, ?)""",
                [(tid, now, source, language, priority) for tid in tmdb_ids],
            )
            conn.commit()

    def count(self) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM enrichment_log").fetchone()
            return row[0] if row else 0

    # ---- usage tracking ----
    def increment_usage(self, tmdb_ids: List[str]):
        """Increment usage_count and update last_used_at for given movie IDs."""
        if not tmdb_ids:
            return
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                """UPDATE enrichment_log
                   SET usage_count = usage_count + 1, last_used_at = ?
                   WHERE tmdb_id = ?""",
                [(now, tid) for tid in tmdb_ids],
            )
            conn.commit()

    def get_language_distribution(self) -> Dict[str, int]:
        """Count movies per original_language."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """SELECT original_language, COUNT(*)
                   FROM enrichment_log
                   GROUP BY original_language
                   ORDER BY COUNT(*) DESC"""
            ).fetchall()
            return {r[0] or "unknown": r[1] for r in rows}

    def get_rotation_candidates(self, keep_days: int = 30) -> List[Dict]:
        """Get movies eligible for rotation (unused, old, low priority first)."""
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT tmdb_id, original_language, priority, indexed_at, usage_count
                   FROM enrichment_log
                   WHERE usage_count = 0 AND indexed_at < ?
                   ORDER BY priority DESC, indexed_at ASC""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def remove_movies(self, tmdb_ids: List[str]):
        """Remove movies from the tracker."""
        if not tmdb_ids:
            return
        with sqlite3.connect(str(self.db_path)) as conn:
            placeholders = ",".join("?" * len(tmdb_ids))
            conn.execute(
                f"DELETE FROM enrichment_log WHERE tmdb_id IN ({placeholders})",
                tmdb_ids,
            )
            conn.commit()

    # ---- page registry methods ----
    def get_page_cache(self, combo_key: str, page: int) -> Optional[Dict]:
        """Look up a cached page entry. Returns dict or None."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM page_registry WHERE combo_key = ? AND page = ?",
                (combo_key, page),
            ).fetchone()
            return dict(row) if row else None

    def upsert_page_cache(
        self, combo_key: str, page: int, fingerprint: str, tmdb_ids: str,
        total_pages: Optional[int], total_results: Optional[int], result_count: int,
    ):
        """Insert or update a page registry entry."""
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO page_registry
                       (combo_key, page, fingerprint, tmdb_ids, total_pages,
                        total_results, result_count, last_fetched_at, fetch_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                   ON CONFLICT(combo_key, page) DO UPDATE SET
                       fingerprint = excluded.fingerprint,
                       tmdb_ids = excluded.tmdb_ids,
                       total_pages = excluded.total_pages,
                       total_results = excluded.total_results,
                       result_count = excluded.result_count,
                       last_fetched_at = excluded.last_fetched_at,
                       fetch_count = fetch_count + 1""",
                (combo_key, page, fingerprint, tmdb_ids,
                 total_pages, total_results, result_count, now),
            )
            conn.commit()

    def get_max_explored_page(self, combo_key: str) -> int:
        """Return the highest page number in the registry for this combo."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT MAX(page) FROM page_registry WHERE combo_key = ?",
                (combo_key,),
            ).fetchone()
            return row[0] if row and row[0] is not None else 0

    def get_total_pages_for_combo(self, combo_key: str) -> int:
        """Return TMDB's reported total_pages for this combo (max across cached pages)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT MAX(total_pages) FROM page_registry WHERE combo_key = ?",
                (combo_key,),
            ).fetchone()
            return row[0] if row and row[0] is not None else 0

    def get_page_registry_stats(self) -> Dict[str, Any]:
        """Return summary stats from the page registry for progress display."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM page_registry").fetchone()[0]
            fresh = conn.execute(
                "SELECT COUNT(*) FROM page_registry WHERE fingerprint != 'empty'"
            ).fetchone()[0]
            empty = total - fresh
            total_fetches = conn.execute(
                "SELECT SUM(fetch_count) FROM page_registry"
            ).fetchone()[0] or 0
            return {
                "total_cached_pages": total,
                "pages_with_results": fresh,
                "empty_pages": empty,
                "total_fetches": total_fetches,
            }

    # ---- bulk job queue methods ----
    def has_pending_jobs(self) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM bulk_jobs WHERE status = 'pending' LIMIT 1"
            ).fetchone()
            return row is not None

    def count_jobs(self) -> Dict[str, int]:
        """Return counts by status."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM bulk_jobs GROUP BY status"
            ).fetchall()
            return {r[0]: r[1] for r in rows}

    def insert_jobs(self, jobs: List[Dict]):
        """Bulk insert job records."""
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                """INSERT INTO bulk_jobs
                   (language, genre_id, decade_start, sort_by, page, priority, status, created_at, wave)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                [
                    (j["language"], j.get("genre_id"), j.get("decade_start"),
                     j["sort_by"], j["page"], j["priority"], now, j.get("wave", 1))
                    for j in jobs
                ],
            )
            conn.commit()

    def pick_next_job(self) -> Optional[Dict]:
        """Atomically pick the next pending job (lowest priority number first = highest priority)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT * FROM bulk_jobs
                   WHERE status = 'pending'
                   ORDER BY priority ASC, id ASC
                   LIMIT 1"""
            ).fetchone()
            if not row:
                return None
            job = dict(row)
            conn.execute(
                "UPDATE bulk_jobs SET status = 'in_progress' WHERE id = ?",
                (job["id"],),
            )
            conn.commit()
            return job

    def complete_job(self, job_id: int, movies_found: int):
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """UPDATE bulk_jobs
                   SET status = 'done', completed_at = ?, movies_found = ?
                   WHERE id = ?""",
                (now, movies_found, job_id),
            )
            conn.commit()

    def fail_job(self, job_id: int, error_msg: str):
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """UPDATE bulk_jobs
                   SET status = 'failed', completed_at = ?, error_msg = ?
                   WHERE id = ?""",
                (now, error_msg[:500], job_id),
            )
            conn.commit()

    def clear_jobs(self, status: Optional[str] = None):
        """Clear job queue. If status given, only clear that status."""
        with sqlite3.connect(str(self.db_path)) as conn:
            if status:
                conn.execute("DELETE FROM bulk_jobs WHERE status = ?", (status,))
            else:
                conn.execute("DELETE FROM bulk_jobs")
            conn.commit()

    def get_job_progress_by_language(self) -> List[Dict]:
        """Get per-language job progress summary."""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                """SELECT language, priority,
                          SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done,
                          SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                          SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as in_progress,
                          SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                          COUNT(*) as total,
                          SUM(CASE WHEN status='done' THEN movies_found ELSE 0 END) as movies_found
                   FROM bulk_jobs
                   GROUP BY language
                   ORDER BY priority ASC, language ASC"""
            ).fetchall()
            return [
                {
                    "language": r[0], "priority": r[1], "done": r[2],
                    "pending": r[3], "in_progress": r[4], "failed": r[5],
                    "total": r[6], "movies_found": r[7],
                }
                for r in rows
            ]


class EnrichmentPipeline:
    """Background pipeline to grow the movie corpus."""

    def __init__(self):
        from src.services.cloud_vectordb import get_cloud_vectordb
        from src.services.movie_service import get_movie_service

        self.cloud_db = get_cloud_vectordb()
        self.movie_service = get_movie_service()
        self.tracker = _IndexedTracker()

    def _get_embedder(self):
        """Lazy load text embedder (heavy import)."""
        from src.core.embeddings.text_embedder import get_text_embedder
        return get_text_embedder()

    @staticmethod
    def _make_combo_key(job: Dict) -> str:
        """Build a unique key for a language+genre+decade+sort combo."""
        return (
            f"{job['language']}|{job.get('genre_id') or -1}"
            f"|{job.get('decade_start') or -1}|{job['sort_by']}"
        )

    # ================================================================
    # Existing enrichment cycles (unchanged)
    # ================================================================

    def run_full_cycle(self):
        """Run complete enrichment cycle across all strategies and languages."""
        logger.info("Starting FULL enrichment cycle")
        start = time.time()
        total_new = 0

        for strategy_name, strategy_params in ENRICHMENT_STRATEGIES:
            for language in ENRICHMENT_LANGUAGES:
                try:
                    new_count = self._run_strategy(strategy_name, strategy_params, language)
                    total_new += new_count
                except Exception as e:
                    logger.warning(f"Strategy {strategy_name}/{language} failed: {e}")

        elapsed = time.time() - start
        logger.info(
            f"Full enrichment complete: {total_new} new movies indexed in {elapsed:.1f}s. "
            f"Total indexed: {self.tracker.count()}"
        )
        return total_new

    def run_light_cycle(self):
        """Quick enrichment: trending only (runs on API startup)."""
        logger.info("Starting LIGHT enrichment cycle (trending only)")
        start = time.time()
        total_new = 0

        for language in ENRICHMENT_LANGUAGES[:3]:  # Just top 3 languages
            try:
                new_count = self._run_strategy("trending_weekly", {"time_window": "week"}, language)
                total_new += new_count
            except Exception as e:
                logger.warning(f"Light enrichment failed for {language}: {e}")

        elapsed = time.time() - start
        logger.info(f"Light enrichment complete: {total_new} new movies in {elapsed:.1f}s")
        return total_new

    def enrich_user_movies(self, user_id: str):
        """Index all movies a user has rated (ensures their taste is in the DB)."""
        logger.info(f"Enriching movies for user {user_id}")
        try:
            from src.services.user_service import get_user_service
            user_service = get_user_service()
            ratings = user_service.get_user_ratings(user_id)

            if not ratings:
                logger.info(f"No ratings found for user {user_id}")
                return 0

            already_indexed = self.tracker.get_indexed_ids()
            new_movie_ids = [
                r["movie_id"] for r in ratings
                if str(r["movie_id"]) not in already_indexed
            ]

            if not new_movie_ids:
                logger.info(f"All {len(ratings)} rated movies already indexed")
                return 0

            # Fetch full movie details
            movies = []
            for mid in new_movie_ids:
                try:
                    movie = self.movie_service.get_movie_by_id(tmdb_id=int(mid))
                    if movie:
                        movies.append(movie)
                except Exception:
                    continue

            if movies:
                self._embed_and_upsert(movies, source=f"user_{user_id}")

            logger.info(f"Enriched {len(movies)} movies for user {user_id}")
            return len(movies)

        except Exception as e:
            logger.error(f"User enrichment failed for {user_id}: {e}")
            return 0

    def migrate_from_chromadb(self):
        """Migrate existing ChromaDB movies to cloud vector DBs."""
        logger.info("Migrating existing ChromaDB movies to cloud vector DBs")
        try:
            from src.core.vectordb.chroma_client import get_chroma_client

            chroma = get_chroma_client()
            try:
                chroma.get_collection(settings.chroma_collection_movies)
            except Exception:
                logger.warning("No local ChromaDB collection found, nothing to migrate")
                return 0

            all_data = chroma.collection.get(
                include=["embeddings", "metadatas", "documents"]
            )

            ids = all_data.get("ids") or []
            embeddings = all_data.get("embeddings")
            metadatas = all_data.get("metadatas") or []

            if not ids or embeddings is None or len(embeddings) == 0:
                logger.warning("No data found in ChromaDB")
                return 0

            # Convert to the format expected by cloud_db.upsert_movies
            movie_dicts = []
            embedding_list = []

            for i, chroma_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                emb = embeddings[i]

                # Convert numpy array to list if needed
                if hasattr(emb, 'tolist'):
                    emb = emb.tolist()

                tmdb_id = str(meta.get("movieId", chroma_id.replace("movie_", "")))

                movie_dicts.append({
                    "tmdb_id": tmdb_id,
                    "title": meta.get("title", ""),
                    "overview": meta.get("overview", ""),
                    "genres": meta.get("genres", ""),
                    "year": int(meta.get("year", 0) or 0),
                    "vote_average": float(meta.get("vote_average", 0) or 0),
                    "vote_count": int(meta.get("vote_count", 0) or 0),
                    "original_language": meta.get("original_language", ""),
                    "director": meta.get("director", ""),
                    "cast": meta.get("cast", ""),
                    "poster_path": meta.get("poster_path", ""),
                })
                embedding_list.append(emb)

            if movie_dicts:
                counts = self.cloud_db.upsert_movies(movie_dicts, embedding_list)
                self.tracker.mark_indexed(
                    [m["tmdb_id"] for m in movie_dicts], source="chromadb_migration"
                )
                logger.info(f"Migrated {len(movie_dicts)} movies from ChromaDB -> {counts}")
                return len(movie_dicts)

            return 0

        except Exception as e:
            logger.error(f"ChromaDB migration failed: {e}")
            return 0

    # ================================================================
    # BULK LOCAL ENRICHMENT — Hindi-first pipeline
    # ================================================================

    def run_bulk_local(
        self,
        target_gb: float = 15.0,
        max_pages: int = 500,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Main entry point for bulk local enrichment.

        Args:
            target_gb: Target corpus size in GB.
            max_pages: Maximum pages to process in this run.
            progress_callback: Optional callback(info_dict) called after each job.

        Returns:
            Summary dict with total_new, pages_processed, etc.
        """
        logger.info(f"Starting bulk local enrichment (target={target_gb}GB, max_pages={max_pages})")

        # Generate jobs if queue is empty (smart page-aware generation)
        if not self.tracker.has_pending_jobs():
            logger.info("No pending jobs — generating smart page-aware jobs...")
            self._generate_jobs()

        # Check if anything was generated
        if not self.tracker.has_pending_jobs():
            logger.info("No jobs needed — all pages fresh and fully indexed")
            return {
                "total_new": 0,
                "pages_processed": 0,
                "pages_skipped": 0,
                "elapsed": 0.0,
                "total_indexed": self.tracker.count(),
            }

        # Process jobs
        result = self._process_jobs(max_pages=max_pages, progress_callback=progress_callback)

        logger.info(
            f"Bulk enrichment run complete: {result['total_new']} new movies, "
            f"{result['pages_processed']} pages processed, "
            f"{result.get('pages_skipped', 0)} skipped (cached)"
        )
        return result

    def _generate_jobs(self):
        """Generate jobs intelligently using the page registry.

        For each combo (language + genre + decade + sort):
        1. Re-check stale pages (TTL expired)
        2. Check pages with unindexed movies
        3. Auto-discover new pages up to TMDB's reported total_pages
        Skips pages that are fresh AND fully indexed (zero cost).
        """
        already_indexed = self.tracker.get_indexed_ids()
        jobs: List[Dict] = []
        skipped = 0

        def _should_create_job(combo_key: str, page: int, sort_by: str) -> bool:
            """Return True if this page needs processing."""
            nonlocal skipped
            cached = self.tracker.get_page_cache(combo_key, page)
            if not cached:
                return True  # Never fetched

            # Skip confirmed empty pages (only re-check after long TTL)
            if cached["fingerprint"] == "empty":
                age = (datetime.now() - datetime.fromisoformat(cached["last_fetched_at"])).days
                if age < 30:  # Empty pages unlikely to gain content quickly
                    skipped += 1
                    return False
                return True  # Re-check after 30 days

            age = (datetime.now() - datetime.fromisoformat(cached["last_fetched_at"])).days
            ttl = STALE_TTL_DAYS.get(sort_by, DEFAULT_TTL)
            if age >= ttl:
                return True  # Stale
            # Fresh — check if all movies are indexed
            cached_ids = set(cached["tmdb_ids"].split(",")) if cached["tmdb_ids"] else set()
            if not cached_ids or cached_ids.issubset(already_indexed):
                skipped += 1
                return False  # Fresh + fully indexed
            return True  # Has unindexed movies

        def _explore_limit(combo_key: str, explore_depth: int) -> int:
            """Determine how deep to explore pages for this combo.

            If we already know total_pages from TMDB (from a prior fetch),
            cap at that — no point generating jobs for pages beyond what exists.
            Otherwise use explore_depth as the ceiling for first-time exploration.
            """
            total_pages = self.tracker.get_total_pages_for_combo(combo_key)
            max_explored = self.tracker.get_max_explored_page(combo_key)

            if total_pages > 0:
                # We know how many pages TMDB has — use it as the real ceiling
                ceiling = min(total_pages, 500)
            else:
                # Never fetched yet — use configured depth as starting point
                ceiling = explore_depth

            # Always explore a few pages beyond what we've seen (in case TMDB grew)
            return min(max(ceiling, max_explored + 2), 500)

        for cfg in BULK_LANGUAGE_CONFIG:
            lang = cfg["language"]
            priority = cfg["priority"]
            genre_ids = cfg.get("genre_ids", [])
            decades = cfg.get("decades", [])
            explore_depth = cfg.get("explore_depth", cfg.get("pages_per_combo", 1))

            # 1. Genre x Decade combos (popularity)
            for genre_id in genre_ids:
                for decade in decades:
                    combo_key = f"{lang}|{genre_id}|{decade}|popularity.desc"
                    explore_up_to = _explore_limit(combo_key, explore_depth)

                    for page in range(1, explore_up_to + 1):
                        if _should_create_job(combo_key, page, "popularity.desc"):
                            jobs.append({
                                "language": lang,
                                "genre_id": genre_id,
                                "decade_start": decade,
                                "sort_by": "popularity.desc",
                                "page": page,
                                "priority": priority,
                                "wave": 1,
                            })

            # 2. Popular pages (no genre/decade filter)
            popular_pages = cfg.get("popular_pages", 0)
            if popular_pages:
                combo_key = f"{lang}|-1|-1|popularity.desc"
                pop_depth = cfg.get("popular_explore_depth", popular_pages)
                explore_up_to = _explore_limit(combo_key, pop_depth)

                for page in range(1, explore_up_to + 1):
                    if _should_create_job(combo_key, page, "popularity.desc"):
                        jobs.append({
                            "language": lang,
                            "genre_id": None,
                            "decade_start": None,
                            "sort_by": "popularity.desc",
                            "page": page,
                            "priority": priority,
                            "wave": 1,
                        })

            # 3. Top-rated per decade
            tr_decades = cfg.get("top_rated_decades", [])
            tr_pages = cfg.get("top_rated_pages", 0)
            tr_depth = cfg.get("top_rated_explore_depth", tr_pages)
            for decade in tr_decades:
                combo_key = f"{lang}|-1|{decade}|vote_average.desc"
                explore_up_to = _explore_limit(combo_key, tr_depth)

                for page in range(1, explore_up_to + 1):
                    if _should_create_job(combo_key, page, "vote_average.desc"):
                        jobs.append({
                            "language": lang,
                            "genre_id": None,
                            "decade_start": decade,
                            "sort_by": "vote_average.desc",
                            "page": page,
                            "priority": priority,
                            "wave": 1,
                        })

        self.tracker.insert_jobs(jobs)
        logger.info(
            f"Generated {len(jobs)} smart enrichment jobs "
            f"(skipped {skipped} fresh+indexed pages)"
        )

    def _process_jobs(
        self,
        max_pages: int = 500,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Process jobs from the queue in priority order.

        Streaming style: one TMDB page at a time, embed in batches.
        Tracks cache hit/skip statistics from the page registry.
        """
        import requests

        embedder = self._get_embedder()
        already_indexed = self.tracker.get_indexed_ids()

        total_new = 0
        pages_processed = 0
        pages_skipped = 0  # skipped by page registry (fresh + indexed)
        pages_fetched = 0  # actually called TMDB API
        jobs_processed = 0
        start_time = time.time()

        while pages_processed < max_pages:
            job = self.tracker.pick_next_job()
            if not job:
                logger.info("No more pending jobs in queue")
                break

            try:
                new_movies = self._execute_job(job, already_indexed, embedder)
                self.tracker.complete_job(job["id"], len(new_movies))
                total_new += len(new_movies)

                # Track cache status
                cache_status = job.get("_cache_status", "fetch_new")
                if cache_status.startswith("skip"):
                    pages_skipped += 1
                else:
                    pages_fetched += 1

                # Add newly indexed IDs to our local set
                for m in new_movies:
                    already_indexed.add(m["tmdb_id"])

            except Exception as e:
                logger.warning(f"Job {job['id']} failed: {e}")
                self.tracker.fail_job(job["id"], str(e))
                pages_fetched += 1  # failed fetch still counts as an API call

            pages_processed += 1
            jobs_processed += 1

            # Progress callback
            if progress_callback:
                elapsed = time.time() - start_time
                rate = pages_processed / elapsed if elapsed > 0 else 0
                progress_callback({
                    "pages_processed": pages_processed,
                    "max_pages": max_pages,
                    "total_new": total_new,
                    "pages_skipped": pages_skipped,
                    "pages_fetched": pages_fetched,
                    "current_job": job,
                    "cache_status": job.get("_cache_status", ""),
                    "rate": rate,
                    "elapsed": elapsed,
                    "total_indexed": self.tracker.count(),
                })

            # Memory safety: gc every 100 jobs
            if jobs_processed % 100 == 0:
                gc.collect()
                logger.info(f"GC after {jobs_processed} jobs. Total new: {total_new}")

            # Rate limit: 0.3s between API calls (skip delay for cache hits)
            if not job.get("_cache_status", "").startswith("skip"):
                time.sleep(0.3)

        return {
            "total_new": total_new,
            "pages_processed": pages_processed,
            "pages_skipped": pages_skipped,
            "pages_fetched": pages_fetched,
            "elapsed": time.time() - start_time,
            "total_indexed": self.tracker.count(),
        }

    def _execute_job(
        self,
        job: Dict,
        already_indexed: Set[str],
        embedder,
    ) -> List[Dict]:
        """Execute a single bulk job with page-registry awareness.

        Flow:
        1. Check page_registry for cached fingerprint
        2. Skip if fresh + all movies indexed (zero API cost)
        3. Fetch from TMDB if stale/new/has unindexed movies
        4. Compare fingerprint to detect content changes
        5. Process only genuinely new movies

        Returns list of movie dicts that were newly indexed.
        Sets job["_cache_status"] as a side-effect for progress reporting.
        """
        import requests

        lang = job["language"]
        genre_id = job.get("genre_id")
        decade_start = job.get("decade_start")
        sort_by = job["sort_by"]
        page = job["page"]
        priority = job["priority"]
        combo_key = self._make_combo_key(job)

        # 1. Check page registry
        cached = self.tracker.get_page_cache(combo_key, page)

        if cached:
            fetched_at = datetime.fromisoformat(cached["last_fetched_at"])
            age_days = (datetime.now() - fetched_at).days
            ttl = STALE_TTL_DAYS.get(sort_by, DEFAULT_TTL)

            if age_days < ttl:
                # Page is fresh — check if all movies already indexed
                cached_ids = set(cached["tmdb_ids"].split(",")) if cached["tmdb_ids"] else set()
                unindexed = cached_ids - already_indexed
                if not unindexed:
                    # ALL movies on this page are indexed — skip entirely (0 API cost)
                    job["_cache_status"] = "skip_fresh"
                    return []
                # Some unindexed — need to re-fetch for full data
                job["_cache_status"] = "fetch_unindexed"
            else:
                job["_cache_status"] = "fetch_stale"
        else:
            job["_cache_status"] = "fetch_new"

        # 2. Build TMDB discover params
        params = {
            "api_key": self.movie_service.api_key,
            "with_original_language": lang,
            "sort_by": sort_by,
            "page": page,
        }
        if genre_id:
            params["with_genres"] = str(genre_id)
        if decade_start:
            params["primary_release_date.gte"] = f"{decade_start}-01-01"
            params["primary_release_date.lte"] = f"{decade_start + 9}-12-31"
        if sort_by == "vote_average.desc":
            params["vote_count.gte"] = 100

        url = f"{self.movie_service.base_url}/discover/movie"
        response = requests.get(url, params=params, timeout=15)

        if response.status_code != 200:
            raise RuntimeError(f"TMDB API returned {response.status_code}")

        data = response.json()
        results = data.get("results", [])
        tmdb_total_pages = data.get("total_pages", 0)
        tmdb_total_results = data.get("total_results", 0)

        if not results:
            # Empty page — record in registry to prevent future fetches
            self.tracker.upsert_page_cache(
                combo_key, page, "empty", "",
                tmdb_total_pages, tmdb_total_results, 0,
            )
            return []

        # 3. Compute fingerprint
        page_ids = sorted(str(r["id"]) for r in results)
        fingerprint = hashlib.md5(",".join(page_ids).encode()).hexdigest()

        # 4. Compare to cached fingerprint (change detection)
        if cached and cached["fingerprint"] == fingerprint:
            # Content identical — just update timestamp
            self.tracker.upsert_page_cache(
                combo_key, page, fingerprint, ",".join(page_ids),
                tmdb_total_pages, tmdb_total_results, len(results),
            )
            # Still check for unindexed movies (might have failed last time)
            new_items = [r for r in results if str(r["id"]) not in already_indexed]
            if not new_items:
                job["_cache_status"] = "skip_unchanged"
                return []
        else:
            # NEW or CHANGED content
            self.tracker.upsert_page_cache(
                combo_key, page, fingerprint, ",".join(page_ids),
                tmdb_total_pages, tmdb_total_results, len(results),
            )
            new_items = [r for r in results if str(r["id"]) not in already_indexed]
            if not new_items:
                return []

        # 5. Fetch full details for new movies (to get credits/genres)
        movies = []
        movie_dicts = []
        for item in new_items:
            tmdb_id = int(item["id"])
            try:
                movie = self.movie_service.get_movie_by_id(tmdb_id=tmdb_id)
                if movie:
                    movies.append(movie)
                    time.sleep(0.1)  # Gentle rate limiting for detail calls
            except Exception:
                # Fall back to basic parsing
                movie = self.movie_service._parse_tmdb_search_result(item)
                if movie:
                    movies.append(movie)

        if not movies:
            return []

        # Build text representations for embedding
        texts = []
        for m in movies:
            parts = [m.metadata.title or ""]
            if m.metadata.overview:
                parts.append(m.metadata.overview)
            if m.metadata.genres:
                parts.append(" ".join(m.metadata.genres))
            if m.metadata.director:
                parts.append(f"Directed by {m.metadata.director}")
            if m.metadata.cast:
                parts.append(f"Starring {', '.join(m.metadata.cast[:5])}")
            texts.append(". ".join(parts))

        # Batch embed
        embeddings = embedder.embed_batch(texts, show_progress=False)

        # Prepare movie dicts for upsert
        for m in movies:
            movie_dicts.append({
                "tmdb_id": m.metadata.tmdb_id,
                "title": m.metadata.title or "",
                "overview": m.metadata.overview or "",
                "genres": ", ".join(m.metadata.genres) if m.metadata.genres else "",
                "year": m.metadata.year or 0,
                "vote_average": m.metadata.vote_average or 0.0,
                "vote_count": m.metadata.vote_count or 0,
                "original_language": m.metadata.original_language or "",
                "director": m.metadata.director or "",
                "cast": ", ".join(m.metadata.cast[:5]) if m.metadata.cast else "",
                "poster_path": m.metadata.poster_path or "",
            })

        # Upsert to all backends
        self.cloud_db.upsert_movies(movie_dicts, embeddings.tolist())

        # Track indexed IDs
        source = f"bulk_{lang}_{sort_by}"
        self.tracker.mark_indexed(
            [md["tmdb_id"] for md in movie_dicts],
            source=source,
            language=lang,
            priority=priority,
        )

        return movie_dicts

    # ================================================================
    # Rotation (overnight cleanup)
    # ================================================================

    def rotate_unused(self, keep_gb: float = 15.0, keep_days: int = 30) -> Dict[str, Any]:
        """Remove least-used movies when corpus exceeds target size.

        Removes movies where usage_count = 0 and indexed_at older than keep_days,
        starting from lowest priority tier (Gujarati/Punjabi first).
        """
        logger.info(f"Starting rotation (keep={keep_gb}GB, keep_days={keep_days})")

        candidates = self.tracker.get_rotation_candidates(keep_days=keep_days)
        if not candidates:
            logger.info("No rotation candidates found")
            return {"removed": 0, "candidates": 0}

        # Estimate current size (~16 KB per movie)
        total_movies = self.tracker.count()
        est_size_gb = (total_movies * 16 * 1024) / (1024 ** 3)

        if est_size_gb <= keep_gb:
            logger.info(f"Corpus {est_size_gb:.2f}GB <= {keep_gb}GB target, no rotation needed")
            return {"removed": 0, "candidates": len(candidates), "size_gb": est_size_gb}

        # Calculate how many to remove
        excess_movies = int((est_size_gb - keep_gb) / (16 * 1024 / (1024 ** 3)))
        to_remove = candidates[:excess_movies]

        if not to_remove:
            return {"removed": 0, "candidates": len(candidates), "size_gb": est_size_gb}

        tmdb_ids = [c["tmdb_id"] for c in to_remove]

        # Delete from vector DBs
        try:
            self.cloud_db.delete_movies(tmdb_ids)
        except Exception as e:
            logger.warning(f"Cloud delete failed (continuing with tracker removal): {e}")

        # Remove from tracker
        self.tracker.remove_movies(tmdb_ids)

        logger.info(f"Rotation complete: removed {len(tmdb_ids)} movies")
        return {
            "removed": len(tmdb_ids),
            "candidates": len(candidates),
            "size_gb": est_size_gb,
        }

    # ================================================================
    # Stats / progress methods
    # ================================================================

    def get_bulk_progress(self) -> Dict[str, Any]:
        """Return bulk job queue stats for UI/CLI, including page registry info."""
        job_counts = self.tracker.count_jobs()
        by_language = self.tracker.get_job_progress_by_language()
        total_indexed = self.tracker.count()
        registry_stats = self.tracker.get_page_registry_stats()

        total_jobs = sum(job_counts.values())
        done_jobs = job_counts.get("done", 0)
        pending_jobs = job_counts.get("pending", 0)
        failed_jobs = job_counts.get("failed", 0)

        return {
            "total_jobs": total_jobs,
            "done": done_jobs,
            "pending": pending_jobs,
            "failed": failed_jobs,
            "in_progress": job_counts.get("in_progress", 0),
            "pct_complete": (done_jobs / total_jobs * 100) if total_jobs > 0 else 0,
            "by_language": by_language,
            "total_indexed": total_indexed,
            "est_size_mb": total_indexed * 16 / 1024,  # ~16 KB per movie
            "page_registry": registry_stats,
        }

    def get_language_distribution(self) -> Dict[str, int]:
        """Return movie count per language from tracker."""
        return self.tracker.get_language_distribution()

    def track_usage(self, tmdb_ids: List[str]):
        """Increment usage counters for movies returned in search/recommendations."""
        self.tracker.increment_usage(tmdb_ids)

    # ================================================================
    # Internal (existing methods, unchanged)
    # ================================================================

    def _run_strategy(self, strategy_name: str, params: Dict, language: str) -> int:
        """Run a single strategy for a single language. Returns count of new movies."""
        already_indexed = self.tracker.get_indexed_ids()

        # Fetch movies from TMDB
        movies = self._fetch_by_strategy(strategy_name, params, language)

        # Filter out already indexed
        new_movies = [
            m for m in movies
            if m.metadata.tmdb_id and m.metadata.tmdb_id not in already_indexed
        ]

        if not new_movies:
            return 0

        # Fetch full details for movies that lack overview
        enriched = []
        for m in new_movies:
            if not m.metadata.overview:
                try:
                    full = self.movie_service.get_movie_by_id(int(m.metadata.tmdb_id))
                    if full:
                        enriched.append(full)
                        continue
                except Exception:
                    pass
            enriched.append(m)

        self._embed_and_upsert(enriched, source=f"{strategy_name}_{language}")
        return len(enriched)

    def _fetch_by_strategy(self, name: str, params: Dict, language: str) -> list:
        """Fetch movies using a named strategy."""
        if name == "trending_weekly":
            return self.movie_service.get_trending_movies(
                time_window=params.get("time_window", "week"),
                language=language,
            )
        elif name == "popular_by_language":
            return self.movie_service.get_popular_by_language(
                language=language,
                limit=20,
            )
        elif name == "top_rated":
            discover_params = {
                "sort_by": params.get("sort_by", "vote_average.desc"),
                "vote_count.gte": params.get("vote_count.gte", 200),
                "with_original_language": language,
                "page": 1,
                "_pages": 1,
                "_strategy": "enrichment_top_rated",
                "_target_k": 20,
            }
            return self.movie_service.discover_by_criteria(discover_params, limit=20)
        elif name == "recent_releases":
            return self.movie_service.get_recent_releases(
                language=language,
                days=params.get("days", 180),
            )
        else:
            logger.warning(f"Unknown enrichment strategy: {name}")
            return []

    def _embed_and_upsert(self, movies: list, source: str):
        """Generate embeddings and upsert to cloud vector DBs."""
        if not movies:
            return

        embedder = self._get_embedder()

        # Build text representations
        texts = []
        for m in movies:
            parts = [m.metadata.title or ""]
            if m.metadata.overview:
                parts.append(m.metadata.overview)
            if m.metadata.genres:
                parts.append(" ".join(m.metadata.genres))
            if m.metadata.director:
                parts.append(f"Directed by {m.metadata.director}")
            if m.metadata.cast:
                parts.append(f"Starring {', '.join(m.metadata.cast[:5])}")
            texts.append(". ".join(parts))

        # Batch embed
        embeddings = embedder.embed_batch(texts, show_progress=len(texts) > 50)

        # Prepare movie dicts
        movie_dicts = []
        for m in movies:
            movie_dicts.append({
                "tmdb_id": m.metadata.tmdb_id,
                "title": m.metadata.title or "",
                "overview": m.metadata.overview or "",
                "genres": ", ".join(m.metadata.genres) if m.metadata.genres else "",
                "year": m.metadata.year or 0,
                "vote_average": m.metadata.vote_average or 0.0,
                "vote_count": m.metadata.vote_count or 0,
                "original_language": m.metadata.original_language or "",
                "director": m.metadata.director or "",
                "cast": ", ".join(m.metadata.cast[:5]) if m.metadata.cast else "",
                "poster_path": m.metadata.poster_path or "",
            })

        # Upsert to all backends
        self.cloud_db.upsert_movies(movie_dicts, embeddings.tolist())

        # Track indexed IDs
        self.tracker.mark_indexed(
            [m["tmdb_id"] for m in movie_dicts],
            source=source,
        )

        logger.info(f"Enrichment ({source}): indexed {len(movie_dicts)} movies")
