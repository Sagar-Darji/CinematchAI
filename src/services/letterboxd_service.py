"""Letterboxd Import Service - Import ratings from Letterboxd CSV export."""

import csv
from datetime import datetime
from io import StringIO
from typing import Callable, Dict, List, Optional

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
            logger.info(f"Found {total} rated movies in CSV")

            # Import ratings
            imported = 0
            failed = 0
            tmdb_mapping = {}

            for idx, row in rated_df.iterrows():
                title = row["Name"]
                year = row["Year"]
                rating = float(row["Rating"])

                # Search TMDB for movie
                tmdb_id = self._search_tmdb_movie(title, year)

                if tmdb_id:
                    # Save rating
                    self.user_service.add_rating(
                        user_id=user_id,
                        movie_id=str(tmdb_id),
                        rating=rating,
                        watched=True,
                    )
                    tmdb_mapping[title] = tmdb_id
                    imported += 1
                else:
                    logger.warning(f"Could not find TMDB match for: {title} ({year})")
                    failed += 1

                # Report progress every 10 movies or on last movie
                current = imported + failed
                if progress_callback and (current % 10 == 0 or current == total):
                    progress_callback(current, total)
                    logger.debug(f"Progress: {current}/{total} ({current/total*100:.1f}%)")

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
