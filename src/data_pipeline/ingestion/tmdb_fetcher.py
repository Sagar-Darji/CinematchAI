"""TMDB API client with rate limiting."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import get_settings
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TMDBRateLimiter:
    """Rate limiter for TMDB API."""

    def __init__(self, max_requests: int = 40, time_window: int = 10):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window.
            time_window: Time window in seconds.
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests_made = []

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()

        # Remove requests outside time window
        self.requests_made = [t for t in self.requests_made if now - t < self.time_window]

        # Wait if at limit
        if len(self.requests_made) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests_made[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self.requests_made = []

        self.requests_made.append(time.time())


class TMDBClient:
    """TMDB API client with caching and rate limiting."""

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

    def __init__(self, api_key: Optional[str] = None, rate_limit: Optional[int] = None):
        """
        Initialize TMDB client.

        Args:
            api_key: TMDB API key. If None, uses settings.
            rate_limit: Rate limit (requests per 10 seconds). If None, uses settings.
        """
        settings = get_settings()
        self.api_key = api_key or settings.tmdb_api_key
        if not self.api_key:
            raise ValueError("TMDB API key not configured")

        self.rate_limiter = TMDBRateLimiter(
            max_requests=rate_limit or settings.tmdb_rate_limit
        )

        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

        logger.info("TMDB Client initialized")

    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make rate-limited request to TMDB API.

        Args:
            endpoint: API endpoint.
            params: Query parameters.

        Returns:
            JSON response.

        Raises:
            requests.HTTPError: If request fails.
        """
        self.rate_limiter.wait_if_needed()

        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["api_key"] = self.api_key

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API request failed: {e}")
            raise

    @cached(ttl=86400, key_prefix="tmdb_movie")  # 24 hour cache
    def get_movie_details(self, tmdb_id: str) -> Dict[str, Any]:
        """
        Get detailed movie information.

        Args:
            tmdb_id: TMDB movie ID.

        Returns:
            Movie details dictionary.
        """
        logger.debug(f"Fetching movie details for TMDB ID: {tmdb_id}")
        return self._make_request(f"movie/{tmdb_id}", params={"append_to_response": "credits"})

    @cached(ttl=86400, key_prefix="tmdb_search")
    def search_movie(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for movies by title.

        Args:
            query: Movie title to search.
            year: Optional year filter.

        Returns:
            List of movie search results.
        """
        params = {"query": query}
        if year:
            params["year"] = year

        logger.debug(f"Searching for movie: {query}")
        response = self._make_request("search/movie", params=params)
        return response.get("results", [])

    def download_poster(
        self, poster_path: str, size: str = "w500", save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Download movie poster image.

        Args:
            poster_path: Poster path from TMDB.
            size: Image size (w92, w154, w185, w342, w500, w780, original).
            save_dir: Directory to save poster. If None, uses settings.

        Returns:
            Path to downloaded poster or None if failed.
        """
        if not poster_path:
            return None

        settings = get_settings()
        save_dir = save_dir or (settings.raw_data_dir / "tmdb" / "posters")
        save_dir.mkdir(parents=True, exist_ok=True)

        # Create filename from poster path
        filename = poster_path.lstrip("/")
        save_path = save_dir / filename

        # Skip if already downloaded
        if save_path.exists():
            return save_path

        # Download poster
        url = f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
        self.rate_limiter.wait_if_needed()

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(response.content)

            logger.debug(f"Downloaded poster: {filename}")
            return save_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download poster {poster_path}: {e}")
            return None

    def get_popular_movies(self, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get popular movies.

        Args:
            page: Page number.

        Returns:
            List of popular movies.
        """
        response = self._make_request("movie/popular", params={"page": page})
        return response.get("results", [])

    def enrich_movie_metadata(self, movie_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich movie data with TMDB information.

        Args:
            movie_data: Movie data with at least 'title' and optionally 'year'.

        Returns:
            Enriched movie data.
        """
        title = movie_data.get("title")
        year = movie_data.get("year")

        if not title:
            logger.warning("Cannot enrich movie without title")
            return movie_data

        # Search for movie
        search_results = self.search_movie(title, year)
        if not search_results:
            logger.warning(f"No TMDB results for: {title}")
            return movie_data

        # Get first result (best match)
        tmdb_id = search_results[0]["id"]

        # Get detailed information
        details = self.get_movie_details(str(tmdb_id))

        # Extract relevant fields
        enriched = {
            **movie_data,
            "tmdb_id": tmdb_id,
            "overview": details.get("overview"),
            "tagline": details.get("tagline"),
            "release_date": details.get("release_date"),
            "genres": [g["name"] for g in details.get("genres", [])],
            "runtime": details.get("runtime"),
            "vote_average": details.get("vote_average"),
            "vote_count": details.get("vote_count"),
            "popularity": details.get("popularity"),
            "poster_path": details.get("poster_path"),
            "backdrop_path": details.get("backdrop_path"),
            "original_language": details.get("original_language"),
            "budget": details.get("budget"),
            "revenue": details.get("revenue"),
            "status": details.get("status"),
        }

        # Extract cast and crew
        credits = details.get("credits", {})
        cast = credits.get("cast", [])[:10]  # Top 10 cast members
        crew = credits.get("crew", [])

        enriched["cast"] = [c["name"] for c in cast]

        # Find director
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        enriched["director"] = directors[0] if directors else None

        return enriched


def get_tmdb_client() -> TMDBClient:
    """Get configured TMDB client."""
    return TMDBClient()
