"""Letterboxd Import Service - Import ratings from Letterboxd CSV export."""

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import StringIO
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import requests

from src.services.user_service import get_user_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


class LetterboxdService:
    """Service for importing Letterboxd data."""

    def __init__(self):
        """Initialize Letterboxd service."""
        self.user_service = get_user_service()
        self.tmdb_base_url = "https://api.themoviedb.org/3"

    def import_from_csv(
        self,
        user_id: str,
        csv_content: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, any]:
        """
        Import ratings from Letterboxd CSV export with progress tracking.

        Letterboxd CSV format:
        Date,Name,Year,Letterboxd URI,Rating

        Args:
            user_id: User ID to import for.
            csv_content: CSV file content as string.
            progress_callback: Optional callback function(current, total) for progress updates.

        Returns:
            Import statistics.
        """
        logger.info(f"Importing Letterboxd ratings for user_id={user_id}")

        try:
            # Parse CSV
            df = pd.read_csv(StringIO(csv_content))

            # Validate columns
            required_cols = ["Name", "Year", "Rating"]
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"CSV must contain columns: {required_cols}")

            # Filter rated movies (Rating is not empty)
            rated_df = df[df["Rating"].notna()].copy()

            total = len(rated_df)
            has_date_col = "Date" in df.columns
            logger.info(
                f"Found {total} rated movies in CSV"
                + (" (with watch dates)" if has_date_col else " (no Date column — using import time)")
            )

            # Build a list of (title, year, rating, timestamp) per row first,
            # then do TMDB search in parallel — sequential per-row search was
            # taking 1-2s × 800+ rows, blowing past the 5-min Lambda timeout.

            def _row_ts(row) -> Optional[str]:
                """Preserve the original Letterboxd watch/log date when present."""
                if not has_date_col:
                    return None
                raw_date = row.get("Date")
                if not pd.notna(raw_date):
                    return None
                try:
                    parsed = pd.to_datetime(raw_date, errors="coerce")
                    if pd.notna(parsed):
                        return parsed.isoformat()
                except Exception:
                    pass
                return None

            tasks: List[Tuple[int, str, float, float, Optional[str]]] = []
            for _, row in rated_df.iterrows():
                tasks.append((
                    len(tasks),                # stable index
                    str(row["Name"]),          # title
                    float(row["Rating"]),      # rating
                    row["Year"],                # year (may be NaN)
                    _row_ts(row),
                ))

            tmdb_results: Dict[int, Optional[int]] = {}

            def _resolve(idx: int, title: str, year: float) -> Tuple[int, Optional[int]]:
                try:
                    tid = self._search_tmdb_movie(title, year)
                except Exception as exc:
                    logger.warning(f"TMDB search threw for {title!r}: {exc}")
                    tid = None
                return idx, tid

            # Parallel resolve. TMDB allows 40 req/10s globally; 8 workers
            # keeps us comfortably under that even if another worker is
            # warming a different user. Cuts wall-clock from ~20min for
            # 800 rows to ~90-120s on a warm cache.
            completed = 0
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [
                    pool.submit(_resolve, idx, title, year)
                    for idx, title, _rating, year, _ts in tasks
                ]
                for fut in as_completed(futures):
                    idx, tid = fut.result()
                    tmdb_results[idx] = tid
                    completed += 1
                    if progress_callback and (completed % 25 == 0 or completed == total):
                        # First half of progress is dedicated to TMDB resolve.
                        progress_callback(completed // 2, total)

            # Now write all the ratings (sequential — fast against Postgres).
            imported = 0
            failed = 0
            tmdb_mapping: Dict[str, int] = {}
            for idx, title, rating, year, ts in tasks:
                tid = tmdb_results.get(idx)
                if tid:
                    self.user_service.add_rating(
                        user_id=user_id,
                        movie_id=str(tid),
                        rating=rating,
                        watched=True,
                        timestamp=ts,
                    )
                    tmdb_mapping[title] = tid
                    imported += 1
                else:
                    logger.warning(f"Could not find TMDB match for: {title} ({year})")
                    failed += 1
                done = imported + failed
                if progress_callback and (done % 25 == 0 or done == total):
                    # Second half of progress for DB writes.
                    progress_callback(total // 2 + done // 2, total)

            logger.info(
                f"Import complete: {imported} imported, {failed} failed"
            )

            return {
                "user_id": user_id,
                "total_movies": total,
                "imported_count": imported,
                "failed_count": failed,
                "success_rate": imported / total if total > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to import Letterboxd CSV: {e}")
            raise

    def _search_tmdb_movie(
        self, title: str, year: Optional[int] = None
    ) -> Optional[int]:
        """
        Search TMDB for movie by title and year.

        Args:
            title: Movie title.
            year: Release year (optional).

        Returns:
            TMDB movie ID or None if not found.
        """
        from config.settings import get_settings

        settings = get_settings()

        if not settings.tmdb_api_key:
            logger.warning("TMDB API key not set, cannot search movies")
            return None

        try:
            # Search TMDB
            url = f"{self.tmdb_base_url}/search/movie"
            params = {
                "api_key": settings.tmdb_api_key,
                "query": title,
            }

            if year:
                params["year"] = int(year)

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if results:
                    # Return first result (best match)
                    return results[0]["id"]

            return None

        except Exception as e:
            logger.warning(f"TMDB search failed for {title}: {e}")
            return None


# Singleton
_letterboxd_service = None


def get_letterboxd_service() -> LetterboxdService:
    """Get Letterboxd service instance."""
    global _letterboxd_service
    if _letterboxd_service is None:
        _letterboxd_service = LetterboxdService()
    return _letterboxd_service
