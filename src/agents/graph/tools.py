"""Tools for agents to interact with external systems."""

from typing import Any, Dict, List

import numpy as np

from src.core.models import Movie
from src.core.vectordb.chroma_client import get_chroma_client
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
    filter_dict = _build_filter(context_factors)

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

        # Convert results to Movie objects
        candidate_movies = []

        for result in results:
            movie = _result_to_movie(result)
            if movie:
                candidate_movies.append(movie)

        logger.info(f"Retrieved {len(candidate_movies)} candidates")

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


def _build_filter(context_factors: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build Chroma filter from context factors.

    Args:
        context_factors: Context information.

    Returns:
        Filter dictionary for Chroma.
    """
    filter_dict = {}

    # Example: Filter by time of day → appropriate genres
    time_of_day = context_factors.get("time_of_day")

    if time_of_day == "morning":
        # Light, uplifting movies for morning
        # (In practice, you'd filter by genre metadata)
        pass
    elif time_of_day == "night":
        # Darker, atmospheric movies for night
        pass

    # Example: Filter by companion → family-friendly
    companion = context_factors.get("companion")
    if companion == "family":
        # Filter for family-friendly ratings (G, PG, PG-13)
        # filter_dict["rating"] = {"$in": ["G", "PG", "PG-13"]}
        pass

    # For now, return empty filter (no restrictions)
    return filter_dict if filter_dict else None


def _result_to_movie(result: Dict[str, Any]) -> Movie:
    """
    Convert Chroma search result to Movie object.

    Args:
        result: Search result from Chroma.

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

        return movie

    except Exception as e:
        logger.warning(f"Failed to convert result to Movie: {e}")
        return None


def cold_start_retrieval(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve diverse popular movies for cold-start users.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with candidate_movies.
    """
    logger.info("Performing cold-start retrieval (diverse popular movies)")

    try:
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
                    movie = _result_to_movie(result)
                    if movie:
                        candidate_movies.append(movie)

            if len(candidate_movies) >= 50:
                break

        candidate_movies = candidate_movies[:50]

        logger.info(f"Cold-start retrieval: {len(candidate_movies)} candidates")

        state["candidate_movies"] = candidate_movies
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Cold-Start Retrieval: {len(candidate_movies)} diverse popular movies"
        ]

    except Exception as e:
        logger.error(f"Cold-start retrieval failed: {e}")
        state["candidate_movies"] = []

    return state
