"""Movie Service - On-demand movie and TV data from TMDB API."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from diskcache import Cache

from config.settings import get_settings
from src.core.models import Movie, MovieMetadata, SeasonMetadata
from src.utils.logging import get_logger

import os

logger = get_logger(__name__)
settings = get_settings()

# On Lambda, /tmp is the only writable directory
_cache_dir = "/tmp/tmdb" if os.environ.get("LAMBDA_TASK_ROOT") else "./data/cache/tmdb"
cache = Cache(_cache_dir)

MOVIE_GENRE_NAME_TO_ID = {
    "Action": 28,
    "Adventure": 12,
    "Animation": 16,
    "Comedy": 35,
    "Crime": 80,
    "Documentary": 99,
    "Drama": 18,
    "Family": 10751,
    "Fantasy": 14,
    "History": 36,
    "Horror": 27,
    "Music": 10402,
    "Mystery": 9648,
    "Romance": 10749,
    "Science Fiction": 878,
    "Sci-Fi": 878,
    "Thriller": 53,
    "War": 10752,
    "Western": 37,
}

TV_GENRE_NAME_TO_ID = {
    "Action": 10759,
    "Action & Adventure": 10759,
    "Adventure": 10759,
    "Animation": 16,
    "Comedy": 35,
    "Crime": 80,
    "Documentary": 99,
    "Drama": 18,
    "Family": 10751,
    "Kids": 10762,
    "Mystery": 9648,
    "News": 10763,
    "Reality": 10764,
    "Sci-Fi": 10765,
    "Sci-Fi & Fantasy": 10765,
    "Soap": 10766,
    "Talk": 10767,
    "War": 10768,
    "War & Politics": 10768,
    "Western": 37,
}

MOVIE_GENRE_ID_TO_NAME = {v: k for k, v in MOVIE_GENRE_NAME_TO_ID.items()}
TV_GENRE_ID_TO_NAME = {
    10759: "Action & Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    10762: "Kids",
    9648: "Mystery",
    10763: "News",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
    10768: "War & Politics",
    37: "Western",
}


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

    def get_movie_by_id(self, tmdb_id: int, media_type: str = "movie") -> Optional[Movie]:
        """
        Get movie or TV item by TMDB ID (on-demand from API).

        Args:
            tmdb_id: TMDB movie ID.
            media_type: TMDB media type ("movie" or "tv").

        Returns:
            Movie object or None.
        """
        return self.get_media_by_id(tmdb_id=tmdb_id, media_type=media_type)

    def get_media_by_id(self, tmdb_id: int, media_type: str = "movie") -> Optional[Movie]:
        """Get a movie or TV show by TMDB ID."""
        media_type = self._normalize_media_type(media_type)
        cache_key = f"{media_type}_{tmdb_id}"

        # Check cache first
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/{media_type}/{tmdb_id}"
            params = {
                "api_key": self.api_key,
                "append_to_response": "credits",
            }

            response = self._session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                movie = self._parse_tmdb_media(data, media_type=media_type)

                # Cache for 24 hours
                cache.set(cache_key, movie, expire=86400)

                return movie

            return None

        except Exception as e:
            logger.error(f"Failed to fetch {media_type} {tmdb_id}: {e}")
            return None

    def get_detail_extras(self, tmdb_id: int, media_type: str = "movie") -> Dict[str, Any]:
        """Fetch trailer key, top cast (with profile photos), and similar titles
        for a single TMDB id. Returns a plain dict so it can be merged into the
        MovieResponse without touching the Movie domain model.

        Falls back gracefully on partial errors — keys may be missing or empty.
        Cached for 24h alongside the base detail fetch.
        """
        media_type = self._normalize_media_type(media_type)
        cache_key = f"detail_extras_{media_type}_{tmdb_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        result: Dict[str, Any] = {"trailer_key": None, "cast": [], "similar": []}
        try:
            url = f"{self.base_url}/{media_type}/{tmdb_id}"
            params = {
                "api_key": self.api_key,
                "append_to_response": "videos,similar,credits",
            }
            response = self._session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return result
            data = response.json()

            # Trailer: prefer YouTube + Trailer; fall back to Teaser; pick highest-quality
            videos = (data.get("videos") or {}).get("results", []) or []
            yt_videos = [v for v in videos if (v.get("site") == "YouTube") and v.get("key")]
            yt_videos.sort(
                key=lambda v: (
                    0 if v.get("type") == "Trailer" else 1 if v.get("type") == "Teaser" else 2,
                    -(v.get("size") or 0),
                    not v.get("official", False),
                )
            )
            if yt_videos:
                result["trailer_key"] = yt_videos[0].get("key")

            # Top cast (richer than the 5-name shortlist on Movie.metadata.cast)
            cast = ((data.get("credits") or {}).get("cast") or [])[:10]
            result["cast"] = [
                {
                    "name": c.get("name"),
                    "character": c.get("character"),
                    "profile_path": c.get("profile_path"),
                    "order": c.get("order"),
                }
                for c in cast
                if c.get("name")
            ]

            # Similar titles — top 12
            similar_results = ((data.get("similar") or {}).get("results") or [])[:12]
            result["similar"] = [
                {
                    "tmdb_id": int(s["id"]),
                    "title": s.get("title") or s.get("name") or "Unknown",
                    "year": self._extract_year(s.get("release_date") or s.get("first_air_date")),
                    "poster_path": s.get("poster_path"),
                    "vote_average": s.get("vote_average"),
                    "media_type": media_type,
                }
                for s in similar_results
                if s.get("id")
            ]

            cache.set(cache_key, result, expire=86400)
        except Exception as e:
            logger.warning(f"Failed to fetch detail extras for {media_type}/{tmdb_id}: {e}")

        return result

    def get_season_episodes(self, tmdb_id: int, season_number: int) -> Optional[Dict[str, Any]]:
        """Fetch a TV season's episode list from TMDB.

        Used by the in-player episode picker to show thumbnails, titles, and
        runtimes. Cached for 24h — episode lists for finished shows never
        change, and even airing shows only get a new episode weekly.
        """
        cache_key = f"season_{tmdb_id}_{season_number}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/tv/{tmdb_id}/season/{season_number}"
            params = {"api_key": self.api_key}
            response = self._session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None
            data = response.json()

            episodes = [
                {
                    "episode_number": ep["episode_number"],
                    "name": ep.get("name"),
                    "overview": ep.get("overview"),
                    "still_path": ep.get("still_path"),
                    "air_date": ep.get("air_date"),
                    "runtime": ep.get("runtime"),
                    "vote_average": ep.get("vote_average"),
                }
                for ep in data.get("episodes", [])
                if ep.get("episode_number") is not None
            ]

            result = {
                "tmdb_id": tmdb_id,
                "season_number": season_number,
                "name": data.get("name"),
                "overview": data.get("overview"),
                "poster_path": data.get("poster_path"),
                "air_date": data.get("air_date"),
                "episodes": episodes,
            }

            cache.set(cache_key, result, expire=86400)
            return result

        except Exception as e:
            logger.warning(f"Failed to fetch season {tmdb_id}/{season_number}: {e}")
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
        media_type: str = "movie",
    ) -> List[Movie]:
        """
        Search movies or TV shows by title.

        Args:
            query: Search query.
            year: Filter by year.
            language: Filter by language (e.g., "en", "hi", "ko", "ja").
            limit: Max results.
            page: Page number for pagination.
            media_type: TMDB media type ("movie" or "tv").

        Returns:
            List of movies.
        """
        try:
            media_type = self._normalize_media_type(media_type)
            url = f"{self.base_url}/search/{media_type}"
            params = {
                "api_key": self.api_key,
                "query": query,
                "page": page,
            }

            if year:
                params["year" if media_type == "movie" else "first_air_date_year"] = year

            if language:
                params["language"] = language

            response = self._session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                movies = []
                for item in results[:limit]:
                    movie = self._parse_tmdb_search_result(item, media_type=media_type)
                    if movie:
                        movies.append(movie)

                return movies

            return []

        except Exception as e:
            logger.error(f"Search failed for '{query}' ({media_type}): {e}")
            return []

    def get_trending_movies(
        self,
        time_window: str = "week",
        language: Optional[str] = None,
        page: int = 1,
        media_type: str = "movie",
    ) -> List[Movie]:
        """
        Get trending movies or TV shows.

        Args:
            time_window: "day" or "week".
            language: Filter by language.
            page: Page number for pagination.
            media_type: TMDB media type ("movie" or "tv").

        Returns:
            List of trending movies.
        """
        media_type = self._normalize_media_type(media_type)
        cache_key = f"trending_{media_type}_{time_window}_{language or 'all'}_{page}"

        # Check cache (1 hour for trending)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = f"{self.base_url}/trending/{media_type}/{time_window}"
            params = {"api_key": self.api_key, "page": page}

            if language:
                params["language"] = language

            response = self._session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                movies = []
                for item in results[:20]:
                    movie = self._parse_tmdb_search_result(item, media_type=media_type)
                    if movie:
                        movies.append(movie)

                # Cache for 1 hour
                cache.set(cache_key, movies, expire=3600)

                return movies

            return []

        except Exception as e:
            logger.error(f"Failed to get trending {media_type}: {e}")
            return []

    def discover_media(
        self,
        genre: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 20,
        page: int = 1,
        media_type: str = "movie",
    ) -> List[Movie]:
        """Discover movies or TV shows by TMDB genre/language filters."""
        media_type = self._normalize_media_type(media_type)
        cache_key = f"discover_{media_type}_{genre or 'all'}_{language or 'all'}_{limit}_{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached[:limit]

        try:
            url = f"{self.base_url}/discover/{media_type}"
            params: Dict[str, Any] = {
                "api_key": self.api_key,
                "sort_by": "popularity.desc",
                "page": page,
            }
            if language:
                params["with_original_language"] = language

            genre_id = self._resolve_genre_id(genre, media_type=media_type)
            if genre_id:
                params["with_genres"] = genre_id

            response = self._session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                movies = [
                    movie
                    for item in data.get("results", [])
                    if (movie := self._parse_tmdb_search_result(item, media_type=media_type))
                ][:limit]
                cache.set(cache_key, movies, expire=3600)
                return movies

            return []
        except Exception as e:
            logger.error(f"Failed to discover {media_type}: {e}")
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
                movie = self._parse_tmdb_search_result(item, media_type="movie")
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

    @staticmethod
    def _normalize_media_type(media_type: str) -> str:
        """Normalize caller input to TMDB media type."""
        return "tv" if str(media_type).lower() in {"tv", "series", "show"} else "movie"

    @staticmethod
    def _parse_date(value: Optional[str]):
        """Parse TMDB ISO date strings safely."""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _extract_year(value: Optional[str]) -> Optional[int]:
        """Extract year from a TMDB date field."""
        if not value:
            return None
        try:
            return int(value[:4])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _resolve_genre_id(genre: Optional[str], media_type: str) -> Optional[int]:
        """Resolve a genre label to the correct TMDB genre id."""
        if not genre:
            return None
        lookup = MOVIE_GENRE_NAME_TO_ID if media_type == "movie" else TV_GENRE_NAME_TO_ID
        return lookup.get(genre)

    def _parse_tmdb_movie(self, data: Dict) -> Movie:
        """Parse full TMDB movie response."""
        return self._parse_tmdb_media(data, media_type="movie")

    def _parse_tmdb_media(self, data: Dict, media_type: str = "movie") -> Movie:
        """Parse a full TMDB movie or TV detail response."""
        media_type = self._normalize_media_type(media_type)
        credits = data.get("credits", {})
        crew = credits.get("crew", [])
        cast = credits.get("cast", [])

        director = None
        if media_type == "movie":
            for person in crew:
                if person.get("job") == "Director":
                    director = person.get("name")
                    break

        creator = None
        created_by = [person.get("name") for person in data.get("created_by", []) if person.get("name")]
        if created_by:
            creator = ", ".join(created_by[:2])
        elif media_type == "tv":
            for person in crew:
                if person.get("job") in {"Creator", "Executive Producer"} and person.get("name"):
                    creator = person.get("name")
                    break

        runtime = data.get("runtime")
        if media_type == "tv":
            episode_runtime = data.get("episode_run_time") or []
            runtime = episode_runtime[0] if episode_runtime else None

        seasons = [
            SeasonMetadata(
                season_number=season["season_number"],
                name=season.get("name"),
                episode_count=season.get("episode_count"),
                air_date=self._parse_date(season.get("air_date")),
                poster_path=season.get("poster_path"),
            )
            for season in data.get("seasons", [])
            if season.get("season_number") is not None
        ]

        release_date = data.get("release_date") or data.get("first_air_date")
        cast_names = [person["name"] for person in cast[:5] if person.get("name")]
        spoken_languages = [
            lang.get("english_name") or lang.get("name") or lang.get("iso_639_1")
            for lang in data.get("spoken_languages", [])
            if lang.get("english_name") or lang.get("name") or lang.get("iso_639_1")
        ]

        metadata = MovieMetadata(
            tmdb_id=str(data["id"]),
            title=data.get("title") or data.get("name") or "Unknown",
            original_title=data.get("original_title") or data.get("original_name"),
            overview=data.get("overview", ""),
            tagline=data.get("tagline"),
            release_date=self._parse_date(release_date),
            year=self._extract_year(release_date),
            genres=[g["name"] for g in data.get("genres", [])],
            runtime=runtime,
            director=director,
            cast=cast_names,
            vote_average=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            popularity=data.get("popularity"),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            original_language=data.get("original_language"),
            spoken_languages=spoken_languages,
            media_type=media_type,
            creator=creator,
            season_count=data.get("number_of_seasons") if media_type == "tv" else None,
            episode_count=data.get("number_of_episodes") if media_type == "tv" else None,
            seasons=seasons,
            budget=data.get("budget"),
            revenue=data.get("revenue"),
            status=data.get("status"),
        )

        return Movie(movie_id=str(data["id"]), metadata=metadata)

    def _parse_tmdb_search_result(self, data: Dict, media_type: str = "movie") -> Optional[Movie]:
        """Parse TMDB search/discover/trending result."""
        try:
            media_type = self._normalize_media_type(
                data.get("media_type") if data.get("media_type") in {"movie", "tv"} else media_type
            )
            genre_lookup = MOVIE_GENRE_ID_TO_NAME if media_type == "movie" else TV_GENRE_ID_TO_NAME
            genre_ids = data.get("genre_ids", [])
            genres = [genre_lookup[gid] for gid in genre_ids if gid in genre_lookup]
            release_date = data.get("release_date") or data.get("first_air_date")

            metadata = MovieMetadata(
                tmdb_id=str(data["id"]),
                title=data.get("title") or data.get("name") or "Unknown",
                original_title=data.get("original_title") or data.get("original_name"),
                overview=data.get("overview", ""),
                genres=genres,
                year=self._extract_year(release_date),
                vote_average=data.get("vote_average"),
                vote_count=data.get("vote_count"),
                poster_path=data.get("poster_path"),
                original_language=data.get("original_language"),
                media_type=media_type,
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
