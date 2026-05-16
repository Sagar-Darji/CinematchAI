"""Letterboxd Import Service - Import ratings from Letterboxd CSV export."""

import csv
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, Callable, Dict, List, Optional, Tuple

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

    # ── ZIP extraction ────────────────────────────────────────────────────

    # CSVs we know how to ingest from a Letterboxd export. Filenames are
    # always lower-cased before lookup so case-variant exports still hit.
    _ZIP_FILES = {
        "ratings": "ratings.csv",
        "diary": "diary.csv",
        "reviews": "reviews.csv",
        "watchlist": "watchlist.csv",
        "watched": "watched.csv",
        "likes_films": "likes/films.csv",
    }

    def extract_zip_export(self, zip_bytes: bytes) -> Dict[str, Any]:
        """Open a Letterboxd ZIP export in-memory and produce everything
        downstream consumers need.

        Returns:
            {
              "merged_ratings_csv": str | None,  # ratings.csv with `Date`
                  # overridden by diary.csv's `Watched Date` where matched
                  # by Letterboxd URI (fallback: Name + Year). None when
                  # ratings.csv is absent — the ratings worker won't run.
              "reviews":   [ {tmdb_hint, name, year, uri, rating, review_text, watched_date} ],
              "watchlist": [ {name, year, uri} ],
              "watched":   [ {name, year, uri, date} ],
              "likes":     [ {name, year, uri} ],
              "diary_count":   int,  # how many diary rows we overlaid
              "ratings_count": int,
            }

        Tolerates missing files — every section is optional. Raises
        ValueError only when the ZIP itself is malformed.
        """
        try:
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
        except zipfile.BadZipFile as e:
            raise ValueError(f"Uploaded file is not a valid ZIP: {e}")

        # Build a case-insensitive name → ZipInfo map so likes/films.csv
        # resolves whether the export uses "Likes/films.csv" or anything.
        name_map: Dict[str, str] = {n.lower(): n for n in zf.namelist()}

        def _read(lname: str) -> Optional[pd.DataFrame]:
            actual = name_map.get(lname)
            if not actual:
                return None
            try:
                with zf.open(actual) as fh:
                    return pd.read_csv(fh)
            except Exception as exc:
                logger.warning(f"Letterboxd ZIP: failed to read {actual}: {exc}")
                return None

        ratings_df = _read(self._ZIP_FILES["ratings"])
        diary_df = _read(self._ZIP_FILES["diary"])
        reviews_df = _read(self._ZIP_FILES["reviews"])
        watchlist_df = _read(self._ZIP_FILES["watchlist"])
        watched_df = _read(self._ZIP_FILES["watched"])
        likes_df = _read(self._ZIP_FILES["likes_films"])

        result: Dict[str, Any] = {
            "merged_ratings_csv": None,
            "reviews": [],
            "watchlist": [],
            "watched": [],
            "likes": [],
            "diary_count": 0,
            "ratings_count": 0,
        }

        # ── Merge ratings + diary's Watched Date ──────────────────────
        if ratings_df is not None and not ratings_df.empty:
            merged = self._overlay_watched_dates(ratings_df, diary_df)
            buf = StringIO()
            merged.to_csv(buf, index=False)
            result["merged_ratings_csv"] = buf.getvalue()
            result["ratings_count"] = int(len(merged))
            if diary_df is not None:
                result["diary_count"] = int(self._last_overlay_hits)

        # ── Reviews ───────────────────────────────────────────────────
        if reviews_df is not None and not reviews_df.empty:
            result["reviews"] = self._parse_reviews(reviews_df)

        # ── Watchlist / watched / likes ───────────────────────────────
        for key, df in (
            ("watchlist", watchlist_df),
            ("watched", watched_df),
            ("likes", likes_df),
        ):
            if df is not None and not df.empty:
                result[key] = self._parse_simple_list(df)

        return result

    _last_overlay_hits: int = 0

    def _overlay_watched_dates(
        self,
        ratings_df: pd.DataFrame,
        diary_df: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        """Return a copy of ratings_df with its `Date` column replaced by
        diary.csv's `Watched Date` wherever a row matches by Letterboxd URI
        (preferred — canonical) or (Name, Year) (fallback).

        Letterboxd's ratings.csv `Date` is the rating-add date, NOT when the
        film was watched. Users who back-fill their library on Letterboxd
        end up with every row stamped to one day, which then masquerades
        as "watched in 2026" everywhere downstream. diary.csv has the real
        `Watched Date` for any film logged to the diary.
        """
        merged = ratings_df.copy()
        if "Date" not in merged.columns:
            merged["Date"] = None

        self._last_overlay_hits = 0
        if diary_df is None or diary_df.empty:
            return merged
        if "Watched Date" not in diary_df.columns:
            return merged

        # Build lookups from diary. Watched Date is the column we want; URI
        # is the canonical join key.
        uri_to_watched: Dict[str, str] = {}
        ny_to_watched: Dict[Tuple[str, str], str] = {}
        for _, row in diary_df.iterrows():
            wd = row.get("Watched Date")
            if not pd.notna(wd):
                continue
            wd_str = str(wd)
            uri = row.get("Letterboxd URI")
            if pd.notna(uri) and str(uri).strip():
                uri_to_watched[str(uri).strip()] = wd_str
            name = row.get("Name")
            year = row.get("Year")
            if pd.notna(name):
                ny_key = (str(name).strip().lower(), str(year) if pd.notna(year) else "")
                ny_to_watched.setdefault(ny_key, wd_str)

        hits = 0
        new_dates: List[Any] = []
        for _, row in merged.iterrows():
            chosen: Optional[str] = None
            uri = row.get("Letterboxd URI") if "Letterboxd URI" in merged.columns else None
            if pd.notna(uri) and str(uri).strip() in uri_to_watched:
                chosen = uri_to_watched[str(uri).strip()]
            else:
                name = row.get("Name")
                year = row.get("Year") if "Year" in merged.columns else None
                if pd.notna(name):
                    ny_key = (str(name).strip().lower(), str(year) if pd.notna(year) else "")
                    chosen = ny_to_watched.get(ny_key)
            if chosen:
                hits += 1
                new_dates.append(chosen)
            else:
                # Fall back to whatever Date was already there (rating-add date).
                new_dates.append(row.get("Date"))

        merged["Date"] = new_dates
        self._last_overlay_hits = hits
        logger.info(
            f"Letterboxd ZIP: overlaid {hits}/{len(merged)} ratings with diary Watched Date"
        )
        return merged

    @staticmethod
    def _parse_reviews(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """reviews.csv columns: Date, Name, Year, Letterboxd URI, Rating,
        Rewatch, Review, Tags, Watched Date."""
        out: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            text = row.get("Review")
            if not pd.notna(text) or not str(text).strip():
                continue
            entry: Dict[str, Any] = {
                "name": str(row["Name"]) if pd.notna(row.get("Name")) else None,
                "year": int(row["Year"]) if pd.notna(row.get("Year")) and float(row["Year"]).is_integer() else None,
                "uri": str(row["Letterboxd URI"]) if pd.notna(row.get("Letterboxd URI")) else None,
                "rating": float(row["Rating"]) if pd.notna(row.get("Rating")) else None,
                "review_text": str(text).strip(),
                "watched_date": str(row["Watched Date"]) if pd.notna(row.get("Watched Date")) else None,
            }
            if entry["name"]:
                out.append(entry)
        return out

    @staticmethod
    def _parse_simple_list(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generic (Name, Year, URI[, Date]) parser for watchlist / watched
        / likes/films exports."""
        out: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            name = row.get("Name")
            if not pd.notna(name):
                continue
            entry: Dict[str, Any] = {
                "name": str(name).strip(),
                "year": int(row["Year"]) if pd.notna(row.get("Year")) and float(row["Year"]).is_integer() else None,
                "uri": str(row["Letterboxd URI"]) if pd.notna(row.get("Letterboxd URI")) else None,
                "date": str(row["Date"]) if "Date" in df.columns and pd.notna(row.get("Date")) else None,
            }
            out.append(entry)
        return out

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

    def import_chunk(
        self,
        user_id: str,
        csv_content: str,
        start_row: int,
        end_row: int,
        skip_if_unchanged: bool = True,
    ) -> Dict[str, int]:
        """Import a slice [start_row, end_row) of an already-parsed
        Letterboxd CSV. Designed for the chunked Lambda worker — each
        chunk runs in well under the 300s Lambda timeout.

        Returns: {imported, failed, processed} for this chunk.
        """
        df = pd.read_csv(StringIO(csv_content))
        if not all(c in df.columns for c in ("Name", "Year", "Rating")):
            raise ValueError("CSV must contain Name, Year, Rating columns")
        rated_df = df[df["Rating"].notna()].copy()
        chunk_df = rated_df.iloc[start_row:end_row]
        if chunk_df.empty:
            return {"imported": 0, "failed": 0, "processed": 0}

        has_date_col = "Date" in df.columns

        def _row_ts(row) -> Optional[str]:
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
        for _, row in chunk_df.iterrows():
            tasks.append((
                len(tasks),
                str(row["Name"]),
                float(row["Rating"]),
                row["Year"],
                _row_ts(row),
            ))

        # Parallel TMDB resolves over the chunk only. 8 workers stays well
        # under the 40-req/10s TMDB rate limit even with one other user
        # importing concurrently.
        tmdb_results: Dict[int, Optional[int]] = {}

        def _resolve(idx: int, title: str, year: float) -> Tuple[int, Optional[int]]:
            try:
                tid = self._search_tmdb_movie(title, year)
            except Exception as exc:
                logger.warning(f"TMDB search threw for {title!r}: {exc}")
                tid = None
            return idx, tid

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(_resolve, idx, title, year)
                for idx, title, _rating, year, _ts in tasks
            ]
            for fut in as_completed(futures):
                idx, tid = fut.result()
                tmdb_results[idx] = tid

        imported = 0
        failed = 0
        for idx, title, rating, year, ts in tasks:
            tid = tmdb_results.get(idx)
            if tid:
                self.user_service.add_rating(
                    user_id=user_id,
                    movie_id=str(tid),
                    rating=rating,
                    watched=True,
                    timestamp=ts,
                    skip_if_unchanged=skip_if_unchanged,
                    source="letterboxd",
                )
                imported += 1
            else:
                logger.warning(f"Could not find TMDB match for: {title} ({year})")
                failed += 1

        return {"imported": imported, "failed": failed, "processed": len(tasks)}

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

        Cached on /tmp (Lambda) or ./data/cache (local) by
        (normalized_title, year). Titles don't change, so a 30-day TTL is
        plenty. Letterboxd re-imports of the same library become near
        instant — every search after the first is < 1ms.
        """
        from config.settings import get_settings
        from src.services.movie_service import cache as _tmdb_cache

        settings = get_settings()

        if not settings.tmdb_api_key:
            logger.warning("TMDB API key not set, cannot search movies")
            return None

        # Cache lookup — same diskcache instance the rest of the TMDB code
        # uses, so we don't add a second cache dir on Lambda /tmp.
        try:
            year_part = int(year) if year and (isinstance(year, int) or float(year).is_integer()) else ""
        except (TypeError, ValueError):
            year_part = ""
        cache_key = f"lb_search:{(title or '').strip().lower()}:{year_part}"
        try:
            cached = _tmdb_cache.get(cache_key)
            if cached is not None:
                # Sentinel `0` means "previously searched, no match" — also
                # cacheable so we don't re-hit TMDB for known-misses.
                return int(cached) if cached else None
        except Exception:
            pass  # cache miss / bad pickle — fall through and hit TMDB

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

            tmdb_id: Optional[int] = None
            ok = response.status_code == 200
            if ok:
                data = response.json()
                results = data.get("results", [])
                if results:
                    tmdb_id = int(results[0]["id"])

            # Persist outcome ONLY when the lookup actually returned a 200.
            # Caching a miss from a 429/5xx would poison the cache for 30
            # days — that's how a previous import burned through TMDB rate
            # limits and silently dropped 226 watchlist entries.
            if ok:
                try:
                    _tmdb_cache.set(cache_key, tmdb_id or 0, expire=30 * 24 * 3600)
                except Exception:
                    pass
            elif response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    f"TMDB search transient {response.status_code} for {title!r} — not caching"
                )
            return tmdb_id

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
