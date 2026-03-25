"""Movie Service - On-demand movie data from TMDB API (scalable to all movies)."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from diskcache import Cache

from config.settings import get_settings
from src.core.models import Movie, MovieMetadata
from src.utils.logging import get_logger

import os

logger = get_logger(__name__)
settings = get_settings()

# On Lambda, /tmp is the only writable directory
_cache_dir = "/tmp/tmdb" if os.environ.get("LAMBDA_TASK_ROOT") else "./data/cache/tmdb"
cache = Cache(_cache_dir)


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
        # Connection pooling — reuse TCP connections across TMDB requests
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_maxsize=20, pool_connections=10)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

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

            response = self._session.get(url, params=params, timeout=10)

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

    def get_movies_batch(
        self, tmdb_ids: List[int], max_workers: int = 5
    ) -> List[Optional["Movie"]]:
        """Fetch multiple movies in parallel — fixes the N+1 loop in profile_analyzer.

        Args:
            tmdb_ids: List of TMDB movie IDs.
            max_workers: Concurrent TMDB requests (default 5 — gentle rate limit).

        Returns:
            List of Movie objects in the same order as tmdb_ids (None for failures).
        """
        results: dict = {}

        def _fetch(tid: int):
            return tid, self.get_movie_by_id(tmdb_id=tid)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch, tid): tid for tid in tmdb_ids}
            for future in as_completed(futures):
                try:
                    tid, movie = future.result(timeout=30)
                    results[tid] = movie
                except Exception as e:
                    logger.warning(f"Batch fetch failed for id {futures[future]}: {e}")
                    results[futures[future]] = None

        return [results.get(tid) for tid in tmdb_ids]

    def search_movies(
        self,
        query: str,
        year: Optional[int] = None,
        language: Optional[str] = None,
        limit: int = 20,
        page: int = 1,
    ) -> List[Movie]:
        """
        Search movies by title.

        Args:
            query: Search query.
            year: Filter by year.
            language: Filter by language (e.g., "en", "hi", "ko", "ja").
            limit: Max results.
            page: Page number for pagination.

        Returns:
            List of movies.
        """
        try:
            url = f"{self.base_url}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": query,
                "page": page,
            }

            if year:
                params["year"] = year

            if language:
                params["language"] = language

            response = self._session.get(url, params=params, timeout=10)

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
        self, time_window: str = "week", language: Optional[str] = None, page: int = 1
    ) -> List[Movie]:
        """
        Get trending movies.

        Args:
            time_window: "day" or "week".
            language: Filter by language.
            page: Page number for pagination.

        Returns:
            List of trending movies.
        """
        cache_key = f"trending_{time_window}_{language or 'all'}_{page}"

        # Check cache (1 hour for trending)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/trending/movie/{time_window}"
            params = {"api_key": self.api_key, "page": page}

            if language:
                params["language"] = language

            response = self._session.get(url, params=params, timeout=10)

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

            response = self._session.get(url, params=params, timeout=10)

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

            response = self._session.get(url, params=params, timeout=10)

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

    def get_now_playing(
        self, region: Optional[str] = None, language: Optional[str] = None, page: int = 1
    ) -> List[Movie]:
        """Get movies currently playing in theaters via TMDB now_playing endpoint."""
        cache_key = f"now_playing_{region or 'all'}_{language or 'all'}_{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/movie/now_playing"
            params = {"api_key": self.api_key, "page": page}
            if region:
                params["region"] = region
            if language:
                params["language"] = language

            response = self._session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                movies = [
                    m for item in data.get("results", [])
                    if (m := self._parse_tmdb_search_result(item))
                ]
                cache.set(cache_key, movies, expire=3600)
                return movies
            return []
        except Exception as e:
            logger.error(f"Failed to get now_playing: {e}")
            return []

    def get_upcoming(
        self, region: Optional[str] = None, language: Optional[str] = None, page: int = 1
    ) -> List[Movie]:
        """Get upcoming theatrical releases via TMDB upcoming endpoint."""
        cache_key = f"upcoming_{region or 'all'}_{language or 'all'}_{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/movie/upcoming"
            params = {"api_key": self.api_key, "page": page}
            if region:
                params["region"] = region
            if language:
                params["language"] = language

            response = self._session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                movies = [
                    m for item in data.get("results", [])
                    if (m := self._parse_tmdb_search_result(item))
                ]
                cache.set(cache_key, movies, expire=3600)
                return movies
            return []
        except Exception as e:
            logger.error(f"Failed to get upcoming: {e}")
            return []

    def get_ott_releases(
        self,
        provider_ids: Optional[str] = None,
        region: str = "US",
        language: Optional[str] = None,
        days: int = 30,
        page: int = 1,
    ) -> List[Movie]:
        """Get recent OTT/streaming releases via TMDB discover with watch providers.

        Args:
            provider_ids: Pipe-separated TMDB provider IDs (e.g. "8|9|337").
                          Defaults to Netflix|Prime|Disney+|Apple TV+|HBO Max.
            region: Region code for watch providers (default: US).
            language: Language filter.
            days: Look back N days for releases.
            page: Page number.
        """
        default_providers = "8|9|337|2|384"  # Netflix|Prime|Disney+|Apple TV+|HBO Max
        providers = provider_ids or default_providers
        cache_key = f"ott_{providers}_{region}_{language or 'all'}_{days}_{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            today = datetime.now()
            start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")

            url = f"{self.base_url}/discover/movie"
            params = {
                "api_key": self.api_key,
                "with_watch_providers": providers,
                "watch_region": region,
                "with_watch_monetization_types": "flatrate",
                "primary_release_date.gte": start_date,
                "primary_release_date.lte": end_date,
                "sort_by": "popularity.desc",
                "page": page,
            }
            if language:
                params["with_original_language"] = language

            response = self._session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                movies = [
                    m for item in data.get("results", [])
                    if (m := self._parse_tmdb_search_result(item))
                ]
                cache.set(cache_key, movies, expire=3600)
                return movies
            return []
        except Exception as e:
            logger.error(f"Failed to get OTT releases: {e}")
            return []

    def discover_by_criteria(self, params: Dict[str, Any], limit: int = 20) -> List[Movie]:
        """Execute a TMDB discover query with arbitrary params.

        Handles pagination (up to the number of pages in params['_pages']).
        If results < 50% of target, retries with relaxed filters (#2 multi-query fallback).
        Uses diskcache with 30min TTL keyed by sorted params hash.

        Args:
            params: TMDB discover API parameters (may include internal keys prefixed with '_').
            limit: Maximum movies to return.

        Returns:
            List of Movie objects.
        """
        # Separate internal keys from TMDB API params
        pages = int(params.pop("_pages", 1))
        strategy = params.pop("_strategy", "unknown")
        target_k = params.pop("_target_k", limit)
        actual_limit = min(limit, target_k)

        api_params = {k: v for k, v in sorted(params.items()) if not k.startswith("_")}
        param_hash = hashlib.md5(str(api_params).encode()).hexdigest()[:12]
        cache_key = f"discover_{param_hash}"

        cached = cache.get(cache_key)
        if cached:
            return cached[:actual_limit]

        start_page = int(api_params.pop("page", 1))

        try:
            all_movies = self._fetch_discover_pages(api_params, start_page, pages, actual_limit, strategy)

            # Multi-query fallback (#2): if we got < 50% of target, retry with relaxed filters
            if len(all_movies) < actual_limit // 2:
                seen_ids = {str(m.metadata.tmdb_id) for m in all_movies}
                relaxed = self._relax_discover_params(api_params)
                if relaxed:
                    fallback_movies = self._fetch_discover_pages(
                        relaxed, 1, pages, actual_limit - len(all_movies), f"{strategy}_relaxed",
                    )
                    for m in fallback_movies:
                        if str(m.metadata.tmdb_id) not in seen_ids:
                            all_movies.append(m)
                            seen_ids.add(str(m.metadata.tmdb_id))
                    logger.info(f"Discover fallback ({strategy}): +{len(fallback_movies)} from relaxed query")

            result = all_movies[:actual_limit]
            cache.set(cache_key, result, expire=1800)
            logger.info(f"Discover ({strategy}, page_start={start_page}): {len(result)} movies fetched")
            return result

        except Exception as e:
            logger.error(f"Discover ({strategy}) failed: {e}")
            return []

    def _fetch_discover_pages(
        self, api_params: Dict, start_page: int, pages: int, limit: int, strategy: str,
    ) -> List["Movie"]:
        """Fetch pages from TMDB discover API."""
        all_movies: List[Movie] = []
        seen_ids: set = set()

        for page in range(start_page, start_page + pages):
            url = f"{self.base_url}/discover/movie"
            request_params = {"api_key": self.api_key, **api_params, "page": page}

            response = self._session.get(url, params=request_params, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Discover API returned {response.status_code} for {strategy}")
                break

            data = response.json()
            for item in data.get("results", []):
                tmdb_id = str(item.get("id", ""))
                if tmdb_id in seen_ids:
                    continue
                seen_ids.add(tmdb_id)
                movie = self._parse_tmdb_search_result(item)
                if movie:
                    all_movies.append(movie)

            if len(all_movies) >= limit:
                break

        return all_movies[:limit]

    @staticmethod
    def _relax_discover_params(params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Relax discover params for fallback retry (#2).

        Strategies: lower vote_count, remove vote_average, broaden sort.
        Returns None if already at minimum constraints.
        """
        relaxed = dict(params)
        changed = False

        # Lower vote_count threshold
        vote_gte = relaxed.get("vote_count.gte")
        if vote_gte and int(vote_gte) > 20:
            relaxed["vote_count.gte"] = max(20, int(vote_gte) // 2)
            changed = True

        # Remove vote_average minimum
        if "vote_average.gte" in relaxed:
            del relaxed["vote_average.gte"]
            changed = True

        # Switch to popularity sort if currently by vote_average
        if relaxed.get("sort_by") == "vote_average.desc":
            relaxed["sort_by"] = "popularity.desc"
            changed = True

        return relaxed if changed else None

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
        """Parse TMDB search/discover/trending result (includes genre_ids)."""
        try:
            from src.services.smart_query import GENRE_ID_TO_NAME
            genre_ids = data.get("genre_ids", [])
            genres = [GENRE_ID_TO_NAME[gid] for gid in genre_ids if gid in GENRE_ID_TO_NAME]

            metadata = MovieMetadata(
                tmdb_id=str(data["id"]),
                title=data.get("title", "Unknown"),
                overview=data.get("overview", ""),
                genres=genres,
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
