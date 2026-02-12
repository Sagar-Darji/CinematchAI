"""Movie Service - On-demand movie data from TMDB API (scalable to all movies)."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

import requests
from diskcache import Cache

from config.settings import get_settings
from src.core.models import Movie, MovieMetadata
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Cache for TMDB API responses (24 hours)
cache = Cache("./data/cache/tmdb")


class MovieService:
    """
    Scalable movie service using TMDB API on-demand.

    Supports:
    - ALL movies in the world (via TMDB)
    - Trending movies
    - Regional/language filtering
    - On-demand processing (no pre-processing needed)
    """

    def __init__(self):
        """Initialize movie service."""
        self.base_url = "https://api.themoviedb.org/3"
        self.api_key = settings.tmdb_api_key

    def get_movie_by_id(self, tmdb_id: int) -> Optional[Movie]:
        """
        Get movie by TMDB ID (on-demand from API).

        Args:
            tmdb_id: TMDB movie ID.

        Returns:
            Movie object or None.
        """
        cache_key = f"movie_{tmdb_id}"

        # Check cache first
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/movie/{tmdb_id}"
            params = {
                "api_key": self.api_key,
                "append_to_response": "credits",
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Build Movie object
                movie = self._parse_tmdb_movie(data)

                # Cache for 24 hours
                cache.set(cache_key, movie, expire=86400)

                return movie

            return None

        except Exception as e:
            logger.error(f"Failed to fetch movie {tmdb_id}: {e}")
            return None

    def search_movies(
        self,
        query: str,
        year: Optional[int] = None,
        language: Optional[str] = None,
        limit: int = 20,
    ) -> List[Movie]:
        """
        Search movies by title.

        Args:
            query: Search query.
            year: Filter by year.
            language: Filter by language (e.g., "en", "hi", "ko", "ja").
            limit: Max results.

        Returns:
            List of movies.
        """
        try:
            url = f"{self.base_url}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": query,
                "page": 1,
            }

            if year:
                params["year"] = year

            if language:
                params["language"] = language

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                movies = []
                for item in results[:limit]:
                    movie = self._parse_tmdb_search_result(item)
                    if movie:
                        movies.append(movie)

                return movies

            return []

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

    def get_trending_movies(
        self, time_window: str = "week", language: Optional[str] = None
    ) -> List[Movie]:
        """
        Get trending movies.

        Args:
            time_window: "day" or "week".
            language: Filter by language.

        Returns:
            List of trending movies.
        """
        cache_key = f"trending_{time_window}_{language or 'all'}"

        # Check cache (1 hour for trending)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/trending/movie/{time_window}"
            params = {"api_key": self.api_key}

            if language:
                params["language"] = language

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                movies = []
                for item in results[:20]:
                    movie = self._parse_tmdb_search_result(item)
                    if movie:
                        movies.append(movie)

                # Cache for 1 hour
                cache.set(cache_key, movies, expire=3600)

                return movies

            return []

        except Exception as e:
            logger.error(f"Failed to get trending movies: {e}")
            return []

    def get_popular_by_language(
        self, language: str, region: Optional[str] = None, limit: int = 20
    ) -> List[Movie]:
        """
        Get popular movies by language/region.

        Args:
            language: Language code (e.g., "hi" for Hindi, "ko" for Korean).
            region: Region code (e.g., "IN" for India, "KR" for Korea).
            limit: Max results.

        Returns:
            List of popular movies in that language/region.
        """
        cache_key = f"popular_{language}_{region or 'all'}"

        # Check cache (6 hours)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/discover/movie"
            params = {
                "api_key": self.api_key,
                "with_original_language": language,
                "sort_by": "popularity.desc",
                "page": 1,
            }

            if region:
                params["region"] = region

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                movies = []
                for item in results[:limit]:
                    movie = self._parse_tmdb_search_result(item)
                    if movie:
                        movies.append(movie)

                # Cache for 6 hours
                cache.set(cache_key, movies, expire=21600)

                return movies

            return []

        except Exception as e:
            logger.error(
                f"Failed to get popular movies for language {language}: {e}"
            )
            return []

    def get_recent_releases(
        self,
        language: Optional[str] = None,
        region: Optional[str] = None,
        days: int = 90,
    ) -> List[Movie]:
        """
        Get recent movie releases.

        Args:
            language: Filter by language.
            region: Filter by region.
            days: Look back N days from today.

        Returns:
            List of recent releases.
        """
        try:
            # Calculate date range
            today = datetime.now()
            start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")

            url = f"{self.base_url}/discover/movie"
            params = {
                "api_key": self.api_key,
                "primary_release_date.gte": start_date,
                "primary_release_date.lte": end_date,
                "sort_by": "popularity.desc",
                "page": 1,
            }

            if language:
                params["with_original_language"] = language

            if region:
                params["region"] = region

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                movies = []
                for item in results[:20]:
                    movie = self._parse_tmdb_search_result(item)
                    if movie:
                        movies.append(movie)

                return movies

            return []

        except Exception as e:
            logger.error(f"Failed to get recent releases: {e}")
            return []

    def _parse_tmdb_movie(self, data: Dict) -> Movie:
        """Parse full TMDB movie response."""
        # Extract credits
        credits = data.get("credits", {})
        crew = credits.get("crew", [])
        cast = credits.get("cast", [])

        director = None
        for person in crew:
            if person.get("job") == "Director":
                director = person.get("name")
                break

        cast_names = [person["name"] for person in cast[:5]]

        metadata = MovieMetadata(
            tmdb_id=str(data["id"]),
            title=data.get("title", "Unknown"),
            overview=data.get("overview", ""),
            genres=[g["name"] for g in data.get("genres", [])],
            year=int(data.get("release_date", "1900")[:4])
            if data.get("release_date")
            else None,
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            director=director,
            cast=cast_names,
            poster_path=data.get("poster_path"),
            original_language=data.get("original_language"),
        )

        return Movie(movie_id=str(data["id"]), metadata=metadata)

    def _parse_tmdb_search_result(self, data: Dict) -> Optional[Movie]:
        """Parse TMDB search result."""
        try:
            metadata = MovieMetadata(
                tmdb_id=str(data["id"]),
                title=data.get("title", "Unknown"),
                overview=data.get("overview", ""),
                genres=[],  # Search results don't include genre names
                year=int(data.get("release_date", "1900")[:4])
                if data.get("release_date")
                else None,
                vote_average=data.get("vote_average"),
                vote_count=data.get("vote_count"),
                poster_path=data.get("poster_path"),
                original_language=data.get("original_language"),
            )

            return Movie(movie_id=str(data["id"]), metadata=metadata)
        except Exception as e:
            logger.warning(f"Failed to parse TMDB result: {e}")
            return None


# Singleton
_movie_service = None


def get_movie_service() -> MovieService:
    """Get movie service instance."""
    global _movie_service
    if _movie_service is None:
        _movie_service = MovieService()
    return _movie_service
