"""Tools for agents to interact with external systems."""

from typing import Any, Dict, List, Optional

import numpy as np

from src.core.models import Movie
from src.core.vectordb.chroma_client import get_chroma_client
from src.services.movie_service import get_movie_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


def retrieve_candidates(
    state: Dict[str, Any],
    k: int = 50,
    use_hybrid: bool = True,
) -> Dict[str, Any]:
    """
    Retrieve candidate movies using vector similarity search.

    Args:
        state: Current workflow state.
        k: Number of candidates to retrieve.
        use_hybrid: Whether to use hybrid (text+image) embeddings.

    Returns:
        Updated state with candidate_movies.
    """
    logger.info(f"Retrieving {k} candidate movies (hybrid={use_hybrid})")

    # Get user profile embedding
    user_profile = state.get("user_profile")
    if not user_profile or not user_profile.profile_embedding:
        logger.warning("No user profile embedding available for retrieval")
        state["candidate_movies"] = []
        return state

    query_embedding = user_profile.profile_embedding

    # Get context factors for filtering
    context_factors = state.get("context_factors", {})
    context = state.get("context", {})
    filter_dict = _build_filter(context_factors, context=context)

    # Retrieve from vector database
    try:
        from config.settings import get_settings
        settings = get_settings()

        # Choose collection based on embedding type
        if use_hybrid:
            collection_name = settings.chroma_collection_movies
        else:
            collection_name = f"{settings.chroma_collection_movies}_text"

        chroma_client = get_chroma_client(collection_name=collection_name)
        chroma_client.get_collection(collection_name)

        results = chroma_client.similarity_search(
            query_embedding=query_embedding,
            k=k,
            filter_dict=filter_dict,
        )

        # Convert results to Movie objects and enrich from TMDB
        candidate_movies = []

        for result in results:
            # enrich_from_tmdb=True ensures we get fresh, complete data from TMDB API
            movie = _result_to_movie(result, enrich_from_tmdb=True)
            if movie:
                candidate_movies.append(movie)

        logger.info(f"Retrieved {len(candidate_movies)} candidates (enriched from TMDB)")

        state["candidate_movies"] = candidate_movies
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Retrieval: Retrieved {len(candidate_movies)} candidates (k={k}, hybrid={use_hybrid})"
        ]

    except Exception as e:
        logger.error(f"Failed to retrieve candidates: {e}")
        state["candidate_movies"] = []

    return state


def retrieve_similar_to_movie(
    movie_id: str,
    k: int = 10,
    use_hybrid: bool = True,
) -> List[Movie]:
    """
    Retrieve movies similar to a given movie.

    Args:
        movie_id: TMDB ID of the reference movie.
        k: Number of similar movies to retrieve.
        use_hybrid: Whether to use hybrid embeddings.

    Returns:
        List of similar movies.
    """
    logger.info(f"Retrieving {k} movies similar to movie_id={movie_id}")

    try:
        from config.settings import get_settings
        settings = get_settings()

        if use_hybrid:
            collection_name = settings.chroma_collection_movies
        else:
            collection_name = f"{settings.chroma_collection_movies}_text"

        chroma_client = get_chroma_client(collection_name=collection_name)
        chroma_client.get_collection(collection_name)

        # Get the movie's embedding
        results = chroma_client.get_by_ids(ids=[f"movie_{movie_id}"])

        if not results["embeddings"]:
            logger.warning(f"Movie {movie_id} not found in vectordb")
            return []

        query_embedding = results["embeddings"][0]

        # Retrieve similar movies
        similar = chroma_client.similarity_search(
            query_embedding=query_embedding,
            k=k + 1,  # +1 to exclude the query movie itself
            filter_dict=None,
        )

        # Convert to Movie objects (exclude the query movie)
        similar_movies = []
        for result in similar:
            if result.get("id") != str(movie_id):
                movie = _result_to_movie(result)
                if movie:
                    similar_movies.append(movie)

        return similar_movies[:k]

    except Exception as e:
        logger.error(f"Failed to retrieve similar movies: {e}")
        return []


def _build_filter(context_factors: Dict[str, Any], context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Build Chroma filter from context factors and user context.

    Args:
        context_factors: Detected context information.
        context: Raw user context (language, region, year filters).

    Returns:
        Filter dictionary for Chroma, or None.
    """
    conditions = []

    # Language filter (from raw context)
    if context:
        language = context.get("language")
        if language:
            conditions.append({"original_language": language})

        # Year filters
        year_min = context.get("year_min")
        year_max = context.get("year_max")
        if year_min:
            conditions.append({"year": {"$gte": int(year_min)}})
        if year_max:
            conditions.append({"year": {"$lte": int(year_max)}})

    # Build final filter
    if len(conditions) == 1:
        return conditions[0]
    elif len(conditions) > 1:
        return {"$and": conditions}

    return None


def _enrich_movie_from_tmdb(movie: Movie, force_refresh: bool = False) -> Movie:
    """
    Enrich movie object with fresh data from TMDB API (on-demand).

    Args:
        movie: Movie object (may have incomplete data).
        force_refresh: Force refresh even if data exists.

    Returns:
        Enriched Movie object.
    """
    try:
        # Check if movie already has complete data
        has_complete_data = (
            movie.metadata.title
            and movie.metadata.overview
            and movie.metadata.genres
            and not force_refresh
        )

        if has_complete_data:
            return movie

        # Fetch from TMDB API
        movie_service = get_movie_service()
        tmdb_id = int(movie.metadata.tmdb_id) if movie.metadata.tmdb_id else None

        if not tmdb_id:
            logger.warning("Movie has no TMDB ID, cannot enrich")
            return movie

        enriched_movie = movie_service.get_movie_by_id(tmdb_id=tmdb_id)

        if enriched_movie:
            logger.debug(f"Enriched movie {tmdb_id} from TMDB API")
            return enriched_movie
        else:
            logger.warning(f"Failed to enrich movie {tmdb_id} from TMDB")
            return movie

    except Exception as e:
        logger.warning(f"Failed to enrich movie from TMDB: {e}")
        return movie


def _result_to_movie(result: Dict[str, Any], enrich_from_tmdb: bool = True) -> Optional[Movie]:
    """
    Convert Chroma search result to Movie object.

    Args:
        result: Search result from Chroma.
        enrich_from_tmdb: Whether to enrich with TMDB API data (on-demand).

    Returns:
        Movie object or None if conversion fails.
    """
    try:
        from src.core.models import Movie, MovieMetadata

        metadata = result.get("metadata", {})

        # Parse genres (stored as comma-separated string)
        genres_str = metadata.get("genres", "")
        genres = [g.strip() for g in genres_str.split(",") if g.strip()]

        # Extract movie ID from Chroma ID (format: "movie_<movieId>") or metadata
        chroma_id = result.get("id", "")
        movie_id = metadata.get("movieId", 0)
        if not movie_id and chroma_id.startswith("movie_"):
            movie_id = chroma_id.replace("movie_", "")

        # Parse cast from comma-separated string to list
        cast_raw = metadata.get("cast", "")
        if isinstance(cast_raw, str):
            cast_list = [c.strip() for c in cast_raw.split(",") if c.strip()]
        elif isinstance(cast_raw, list):
            cast_list = cast_raw
        else:
            cast_list = []

        movie_metadata = MovieMetadata(
            tmdb_id=str(movie_id),
            title=metadata.get("title", "Unknown"),
            overview=metadata.get("overview", ""),
            genres=genres,
            year=metadata.get("year"),
            vote_average=metadata.get("vote_average"),
            vote_count=metadata.get("vote_count"),
            director=metadata.get("director"),
            cast=cast_list,
            poster_path=metadata.get("poster_path"),
        )

        movie = Movie(
            movie_id=str(movie_id),
            metadata=movie_metadata,
        )

        # Enrich with TMDB API data if needed
        if enrich_from_tmdb and movie_id:
            movie = _enrich_movie_from_tmdb(movie)

        return movie

    except Exception as e:
        logger.warning(f"Failed to convert result to Movie: {e}")
        return None


def retrieve_on_demand_movies(
    language: Optional[str] = None,
    region: Optional[str] = None,
    include_trending: bool = True,
    k: int = 50,
) -> List[Movie]:
    """
    Retrieve movies on-demand from TMDB API (unlimited scale).

    Args:
        language: Language filter (e.g., "hi" for Hindi, "ko" for Korean).
        region: Region filter (e.g., "IN", "KR").
        include_trending: Whether to include trending movies.
        k: Number of movies to retrieve.

    Returns:
        List of movies fetched on-demand from TMDB.
    """
    logger.info(f"On-demand retrieval: language={language}, region={region}, k={k}")

    try:
        movie_service = get_movie_service()
        candidate_movies = []

        # 1. Get trending movies if requested
        if include_trending:
            trending = movie_service.get_trending_movies(
                time_window="week",
                language=language,
            )
            candidate_movies.extend(trending[:k // 2])  # Half from trending

        # 2. Get popular by language/region
        if language:
            popular = movie_service.get_popular_by_language(
                language=language,
                region=region,
                limit=k // 2,
            )
            candidate_movies.extend(popular)

        # 3. Remove duplicates (by TMDB ID)
        seen_ids = set()
        unique_movies = []
        for movie in candidate_movies:
            if movie.metadata.tmdb_id not in seen_ids:
                seen_ids.add(movie.metadata.tmdb_id)
                unique_movies.append(movie)

        result = unique_movies[:k]
        logger.info(f"On-demand retrieval: {len(result)} movies fetched from TMDB API")

        return result

    except Exception as e:
        logger.error(f"On-demand retrieval failed: {e}")
        return []


def cold_start_retrieval(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve diverse popular movies for cold-start users (NEW USERS ONLY).

    For new users: Uses TMDB API trending/popular movies
    For existing users without profile embedding: Uses ChromaDB diverse sampling

    Args:
        state: Current workflow state.

    Returns:
        Updated state with candidate_movies.
    """
    logger.info("Performing cold-start retrieval (diverse popular movies)")

    try:
        # Check if this is a TRULY NEW user (no rating history) vs user without profile embedding
        user_profile = state.get("user_profile")
        is_truly_new_user = user_profile is None or getattr(user_profile, "is_cold_start", True)

        # Extract language preference from context if available
        context = state.get("context", {})
        language = context.get("language")
        region = context.get("region")

        # Only use on-demand trending for TRULY NEW users
        # For existing users, use ChromaDB diverse sampling (they have preferences!)
        if is_truly_new_user:
            logger.info("New user detected - fetching trending/popular movies from TMDB")
            # Try on-demand retrieval first (TMDB API - unlimited movies)
            candidate_movies = retrieve_on_demand_movies(
                language=language,
                region=region,
                include_trending=True,
                k=50,
            )
        else:
            logger.info("Existing user without profile embedding - using ChromaDB diverse sampling")
            candidate_movies = []

        # Fallback to local ChromaDB if on-demand fails
        if not candidate_movies:
            logger.warning("On-demand retrieval failed, falling back to local ChromaDB")
            from config.settings import get_settings
            settings = get_settings()

            collection_name = settings.chroma_collection_movies
            chroma_client = get_chroma_client(collection_name=collection_name)
            chroma_client.get_collection(collection_name)

            # Retrieve diverse popular movies using a random-ish embedding
            # to get a spread of results
            rng = np.random.default_rng(42)
            candidate_movies = []
            seen_ids = set()

            # Multiple probes with different random embeddings for diversity
            for _ in range(5):
                query_embedding = rng.standard_normal(768).tolist()

                results = chroma_client.similarity_search(
                    query_embedding=query_embedding,
                    k=20,
                    filter_dict=None,
                )

                for result in results:
                    rid = result.get("id")
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        movie = _result_to_movie(result, enrich_from_tmdb=True)
                        if movie:
                            candidate_movies.append(movie)

                if len(candidate_movies) >= 50:
                    break

            candidate_movies = candidate_movies[:50]

        # Post-filter: TMDB trending API may return movies in other languages
        if language and candidate_movies:
            pre_filter_count = len(candidate_movies)
            candidate_movies = [
                m for m in candidate_movies
                if not m.metadata.original_language or m.metadata.original_language == language
            ]
            if len(candidate_movies) < pre_filter_count:
                logger.info(
                    f"Language post-filter ({language}): {pre_filter_count} → {len(candidate_movies)} movies"
                )

        logger.info(f"Cold-start retrieval: {len(candidate_movies)} candidates")

        state["candidate_movies"] = candidate_movies
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Cold-Start Retrieval: {len(candidate_movies)} diverse popular movies (on-demand from TMDB)"
        ]

    except Exception as e:
        logger.error(f"Cold-start retrieval failed: {e}")
        state["candidate_movies"] = []

    return state
