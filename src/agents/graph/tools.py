"""Tools for agents to interact with external systems.

Provides hybrid retrieval: Cloud Vector DB (Zilliz/Qdrant/ChromaDB) + Smart TMDB Discovery.
"""

import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.core.models import Movie
from src.core.vectordb.chroma_client import get_chroma_client
from src.services.movie_service import get_movie_service
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Hybrid retrieval (primary entry point)
# ---------------------------------------------------------------------------


def retrieve_candidates_hybrid(
    state: Dict[str, Any],
    k: int = 50,
    use_hybrid: bool = True,
) -> Dict[str, Any]:
    """Hybrid retrieval: Cloud vector DB + Smart TMDB discovery.

    Steps:
    1. Calculate dynamic split: (db_k, tmdb_k) = _dynamic_split(...)
    2. VECTOR DB: Search cloud DB (Zilliz -> Qdrant -> ChromaDB)
    3. SMART TMDB: Build discover queries -> fetch -> embed on-the-fly -> score
    4. Merge & deduplicate by tmdb_id
    5. Background: queue new TMDB movies for cloud indexing

    Works for both personalized and cold-start users.
    """
    logger.info(f"Hybrid retrieval: k={k}")

    user_profile = state.get("user_profile")
    context = state.get("context", {})
    context_factors = state.get("context_factors", {})

    has_embedding = (
        user_profile is not None
        and hasattr(user_profile, "profile_embedding")
        and user_profile.profile_embedding is not None
        and len(user_profile.profile_embedding) > 0
    )

    # 1. Dynamic split
    db_k, tmdb_k = _dynamic_split(user_profile, context, has_embedding, k)
    logger.info(f"Dynamic split: db_k={db_k}, tmdb_k={tmdb_k}")

    db_candidates: List[Tuple[float, Movie]] = []
    tmdb_candidates: List[Tuple[float, Movie]] = []

    # 2. Vector DB path (only if we have an embedding and allocation > 0)
    if has_embedding and db_k > 0:
        db_candidates = _vector_db_search(
            user_profile.profile_embedding, db_k, context, context_factors
        )
        logger.info(f"Vector DB: {len(db_candidates)} candidates")

    # 3. Smart TMDB path
    if tmdb_k > 0:
        tmdb_candidates = _smart_tmdb_search(
            user_profile, context, context_factors, tmdb_k,
            profile_embedding=user_profile.profile_embedding if has_embedding else None,
        )
        logger.info(f"Smart TMDB: {len(tmdb_candidates)} candidates")

    # 4. Merge & deduplicate
    merged = _merge_candidates(db_candidates, tmdb_candidates, k)
    logger.info(f"Merged: {len(merged)} unique candidates")

    # 5. Exclude movies the user has already rated — showing them again
    # makes recommendations feel broken regardless of algorithm quality.
    user_id = state.get("user_id", "")
    if user_id and user_profile and not getattr(user_profile, "is_cold_start", True):
        try:
            from src.services.user_service import get_user_service
            _ratings = get_user_service().get_user_ratings(user_id)
            rated_ids = {str(r["movie_id"]) for r in _ratings}
            if rated_ids:
                filtered = [m for m in merged if str(m.metadata.tmdb_id) not in rated_ids]
                # Only apply filter if we still have enough candidates
                if len(filtered) >= max(5, k // 3):
                    logger.info(
                        f"Already-seen filter: {len(merged) - len(filtered)} removed, "
                        f"{len(filtered)} remain"
                    )
                    merged = filtered
        except Exception as _e:
            logger.warning(f"Already-seen exclusion failed (non-critical): {_e}")

    # 6. Background: index new TMDB movies (fire-and-forget)
    if tmdb_candidates:
        _background_index_new_movies(tmdb_candidates)

    state["candidate_movies"] = merged
    state["processing_steps"] = state.get("processing_steps", []) + [
        f"Hybrid Retrieval: {len(db_candidates)} from vector DB + "
        f"{len(tmdb_candidates)} from TMDB discover = {len(merged)} candidates"
    ]

    return state


# ---------------------------------------------------------------------------
# Dynamic split
# ---------------------------------------------------------------------------


def _dynamic_split(
    user_profile,
    context: Dict,
    has_embedding: bool,
    k: int,
) -> Tuple[int, int]:
    """Calculate how many candidates from each source.

    Factors:
    - has_embedding: if False, 100% TMDB (cold start)
    - total_ratings: more ratings -> trust vector DB more
    - exploration_rate: high exploration -> more TMDB
    - natural_language context: specific request -> boost TMDB
    - cloud DB availability

    Returns (db_k, tmdb_k) that sum to k.
    """
    if not has_embedding:
        return (0, k)

    total_ratings = getattr(user_profile, "total_ratings", 0) if user_profile else 0
    exploration_rate = 0.3
    if user_profile:
        prefs = getattr(user_profile, "preferences", None)
        if prefs:
            exploration_rate = getattr(prefs, "exploration_rate", 0.3)

    # Base: start at 60% DB, 40% TMDB
    db_ratio = 0.60

    # Adjust by rating count (more ratings -> trust DB more)
    if total_ratings >= 100:
        db_ratio += 0.10
    elif total_ratings >= 50:
        db_ratio += 0.05
    elif total_ratings < 15:
        db_ratio -= 0.15

    # Adjust by exploration rate (higher -> more TMDB)
    db_ratio -= (exploration_rate - 0.3) * 0.3

    # Adjust if there's a specific natural language query
    nl_context = context.get("natural_language_context") or context.get("query") or ""
    if nl_context and len(nl_context) > 10:
        db_ratio -= 0.15  # Specific queries benefit from TMDB discover

    # Clamp
    db_ratio = max(0.15, min(0.85, db_ratio))

    db_k = int(round(k * db_ratio))
    tmdb_k = k - db_k
    return (db_k, tmdb_k)


# ---------------------------------------------------------------------------
# Vector DB search (cloud fallback chain)
# ---------------------------------------------------------------------------


def _vector_db_search(
    query_embedding: List[float],
    k: int,
    context: Dict,
    context_factors: Dict,
) -> List[Tuple[float, Movie]]:
    """Search cloud vector DB with fallback chain.

    Returns list of (score, Movie) sorted by score desc.
    """
    # Build a unified filter dict
    filters = _build_cloud_filter(context, context_factors)

    try:
        from src.services.cloud_vectordb import get_cloud_vectordb
        cloud_db = get_cloud_vectordb()

        results = cloud_db.search(
            query_embedding=query_embedding,
            k=k,
            filters=filters,
        )

        candidates = []
        for r in results:
            movie = _cloud_result_to_movie(r)
            if movie:
                candidates.append((r.get("score", 0.0), movie))

        # Track usage in background
        _background_track_usage(candidates)

        return candidates

    except Exception as e:
        logger.warning(f"Cloud vector DB search failed: {e}")
        # Ultimate fallback: direct ChromaDB search
        return _chroma_fallback_search(query_embedding, k, context, context_factors)


def _chroma_fallback_search(
    query_embedding: List[float],
    k: int,
    context: Dict,
    context_factors: Dict,
) -> List[Tuple[float, Movie]]:
    """Direct ChromaDB fallback when cloud_vectordb module fails entirely."""
    try:
        from config.settings import get_settings
        settings = get_settings()

        chroma_client = get_chroma_client(collection_name=settings.chroma_collection_movies)
        chroma_client.get_collection(settings.chroma_collection_movies)

        filter_dict = _build_chroma_filter(context_factors, context)
        results = chroma_client.similarity_search(
            query_embedding=query_embedding,
            k=k,
            filter_dict=filter_dict,
        )

        candidates = []
        for r in results:
            movie = _result_to_movie(r, enrich_from_tmdb=True)
            if movie:
                score = 1.0 - r.get("distance", 0.0)
                candidates.append((score, movie))

        return candidates
    except Exception as e:
        logger.error(f"ChromaDB fallback also failed: {e}")
        return []


def _build_cloud_filter(context: Dict, context_factors: Dict) -> Optional[Dict]:
    """Build a filter dict for CloudVectorDB.search()."""
    f: Dict[str, Any] = {}
    if context.get("language"):
        f["original_language"] = context["language"]
    if context.get("year_min"):
        f["year_min"] = int(context["year_min"])
    if context.get("year_max"):
        f["year_max"] = int(context["year_max"])
    return f if f else None


# ---------------------------------------------------------------------------
# Smart TMDB search
# ---------------------------------------------------------------------------


def _smart_tmdb_search(
    user_profile,
    context: Dict,
    context_factors: Dict,
    k: int,
    profile_embedding: Optional[List[float]] = None,
) -> List[Tuple[float, Movie]]:
    """Use SmartQueryStrategy to build discover queries, fetch, and score results."""
    try:
        from src.services.smart_query import get_smart_query
        movie_service = get_movie_service()

        strategy = get_smart_query()
        queries = strategy.build_queries(
            user_profile=user_profile,
            context=context,
            context_factors=context_factors,
            k=k,
        )

        all_movies: List[Movie] = []
        seen_ids: set = set()

        for query_params in queries:
            # Copy so discover_by_criteria can pop internal keys
            params = dict(query_params)
            target_k = params.get("_target_k", 20)
            movies = movie_service.discover_by_criteria(params, limit=target_k)
            for m in movies:
                if m.metadata.tmdb_id not in seen_ids:
                    seen_ids.add(m.metadata.tmdb_id)
                    all_movies.append(m)

        logger.info(
            f"Smart TMDB: {len(queries)} discover queries, {len(all_movies)} unique movies"
        )

        # Score by embedding similarity if possible
        if profile_embedding and all_movies:
            scored = _embed_and_score_tmdb_candidates(all_movies, profile_embedding)
            result = scored[:k]
        else:
            # No user embedding — rank by quality signal (vote_average × log popularity)
            # rather than arbitrary API order.
            import math as _math
            def _quality_score(m) -> float:
                va = float(m.metadata.vote_average or 5.0)
                vc = float(getattr(m.metadata, "vote_count", None) or 100)
                pop = float(getattr(m.metadata, "popularity", None) or 10.0)
                return (va / 10.0) * 0.6 + min(_math.log1p(pop) / 10.0, 1.0) * 0.4

            all_movies.sort(key=_quality_score, reverse=True)
            result = [(_quality_score(m), m) for m in all_movies[:k]]

        # Track usage in background
        _background_track_usage(result)
        return result

    except Exception as e:
        logger.error(f"Smart TMDB search failed: {e}")
        # Fallback: basic trending + popular
        return _basic_tmdb_fallback(context, k)


def _basic_tmdb_fallback(
    context: Dict, k: int
) -> List[Tuple[float, Movie]]:
    """Fallback when smart TMDB fails: just fetch trending + popular."""
    try:
        language = context.get("language")
        region = context.get("region")
        movies = retrieve_on_demand_movies(
            language=language, region=region, include_trending=True, k=k
        )
        return [(1.0 - i * 0.01, m) for i, m in enumerate(movies)]
    except Exception as e:
        logger.error(f"Basic TMDB fallback also failed: {e}")
        return []


def _embed_and_score_tmdb_candidates(
    movies: List[Movie],
    profile_embedding: List[float],
) -> List[Tuple[float, Movie]]:
    """Generate text embeddings for TMDB movies and score against profile embedding.

    Returns [(score, movie)] sorted by score descending.
    """
    try:
        from src.core.embeddings.text_embedder import get_text_embedder
        embedder = get_text_embedder()

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
            texts.append(". ".join(parts))

        # Batch embed
        embeddings = embedder.embed_batch(texts, show_progress=False)

        # Cosine similarity (embeddings are already normalized)
        profile_vec = np.array(profile_embedding, dtype=np.float32)
        norm_p = np.linalg.norm(profile_vec)
        if norm_p > 0:
            profile_vec = profile_vec / norm_p

        scored = []
        for i, movie in enumerate(movies):
            movie_vec = embeddings[i]
            score = float(np.dot(profile_vec, movie_vec))
            scored.append((score, movie))

        # Sort descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    except Exception as e:
        logger.warning(f"On-the-fly embedding failed, returning unscored: {e}")
        return [(0.5, m) for m in movies]


# ---------------------------------------------------------------------------
# Merge & deduplicate
# ---------------------------------------------------------------------------


def _merge_candidates(
    db_results: List[Tuple[float, Movie]],
    tmdb_results: List[Tuple[float, Movie]],
    k: int,
) -> List[Movie]:
    """Merge two scored lists, deduplicate by tmdb_id, sort by globally-normalised score.

    Scores are normalised across BOTH sources together so a mediocre TMDB result
    cannot rank above a good vector-DB result just because it happens to be the
    best within the TMDB bucket.
    """
    seen: set = set()
    raw: List[Tuple[float, Movie]] = []

    for source_results in [db_results, tmdb_results]:
        for score, movie in (source_results or []):
            tmdb_id = movie.metadata.tmdb_id
            if tmdb_id and tmdb_id not in seen:
                seen.add(tmdb_id)
                raw.append((score, movie))

    if not raw:
        return []

    # Global min-max normalisation
    all_scores = [s for s, _ in raw]
    max_s = max(all_scores)
    min_s = min(all_scores)
    rng = max_s - min_s if (max_s - min_s) > 1e-6 else 1.0

    normalised = [((s - min_s) / rng, m) for s, m in raw]
    normalised.sort(key=lambda x: x[0], reverse=True)
    return [movie for _, movie in normalised[:k]]


# ---------------------------------------------------------------------------
# Background indexing
# ---------------------------------------------------------------------------


def _background_track_usage(scored_candidates: List[Tuple[float, Movie]]):
    """Fire-and-forget: increment usage counters for returned movies."""
    if not scored_candidates:
        return

    def _track():
        try:
            from src.services.enrichment_pipeline import EnrichmentPipeline
            pipeline = EnrichmentPipeline()
            tmdb_ids = [
                m.metadata.tmdb_id for _, m in scored_candidates
                if m.metadata.tmdb_id
            ]
            if tmdb_ids:
                pipeline.track_usage(tmdb_ids)
        except Exception as e:
            logger.debug(f"Usage tracking failed (non-critical): {e}")

    thread = threading.Thread(target=_track, daemon=True)
    thread.start()


def _background_index_new_movies(tmdb_candidates: List[Tuple[float, Movie]]):
    """Fire-and-forget: index new TMDB movies into cloud vector DB."""
    def _index():
        try:
            from src.services.cloud_vectordb import get_cloud_vectordb
            from src.core.embeddings.text_embedder import get_text_embedder

            cloud_db = get_cloud_vectordb()
            indexed = cloud_db.get_indexed_ids()

            # Find movies not yet indexed
            new_movies = []
            for _, movie in tmdb_candidates:
                if movie.metadata.tmdb_id and movie.metadata.tmdb_id not in indexed:
                    new_movies.append(movie)

            if not new_movies:
                return

            # Generate embeddings
            embedder = get_text_embedder()
            texts = []
            for m in new_movies:
                parts = [m.metadata.title or ""]
                if m.metadata.overview:
                    parts.append(m.metadata.overview)
                if m.metadata.genres:
                    parts.append(" ".join(m.metadata.genres))
                if m.metadata.director:
                    parts.append(f"Directed by {m.metadata.director}")
                texts.append(". ".join(parts))

            embeddings = embedder.embed_batch(texts, show_progress=False)

            # Prepare movie dicts
            movie_dicts = []
            for m in new_movies:
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

            cloud_db.upsert_movies(movie_dicts, embeddings.tolist())
            logger.info(f"Background indexed {len(movie_dicts)} new movies")

        except Exception as e:
            logger.warning(f"Background indexing failed: {e}")

    thread = threading.Thread(target=_index, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# Cloud result -> Movie conversion
# ---------------------------------------------------------------------------


def _cloud_result_to_movie(result: Dict[str, Any]) -> Optional[Movie]:
    """Convert a CloudVectorDB search result to a Movie object.

    The result has {id, score, payload} where payload has movie fields.
    Enriches incomplete movies from TMDB.
    """
    try:
        from src.core.models import Movie, MovieMetadata

        payload = result.get("payload", {})
        tmdb_id = str(payload.get("tmdb_id") or payload.get("movieId") or result.get("id", ""))

        if not tmdb_id or tmdb_id == "0":
            return None

        genres_raw = payload.get("genres", "")
        if isinstance(genres_raw, str):
            genres = [g.strip() for g in genres_raw.split(",") if g.strip()]
        elif isinstance(genres_raw, list):
            genres = genres_raw
        else:
            genres = []

        cast_raw = payload.get("cast", "")
        if isinstance(cast_raw, str):
            cast_list = [c.strip() for c in cast_raw.split(",") if c.strip()]
        elif isinstance(cast_raw, list):
            cast_list = cast_raw
        else:
            cast_list = []

        movie_metadata = MovieMetadata(
            tmdb_id=tmdb_id,
            title=payload.get("title", "Unknown"),
            overview=payload.get("overview", ""),
            genres=genres,
            year=payload.get("year") if payload.get("year") else None,
            vote_average=payload.get("vote_average"),
            vote_count=payload.get("vote_count"),
            original_language=payload.get("original_language"),
            director=payload.get("director"),
            cast=cast_list,
            poster_path=payload.get("poster_path"),
        )

        movie = Movie(movie_id=tmdb_id, metadata=movie_metadata)

        # Enrich if incomplete
        movie = _enrich_movie_from_tmdb(movie)
        return movie

    except Exception as e:
        logger.warning(f"Failed to convert cloud result to Movie: {e}")
        return None


# ---------------------------------------------------------------------------
# Legacy functions (kept for backward compatibility)
# ---------------------------------------------------------------------------


def retrieve_candidates(
    state: Dict[str, Any],
    k: int = 50,
    use_hybrid: bool = True,
) -> Dict[str, Any]:
    """Legacy: delegates to retrieve_candidates_hybrid."""
    return retrieve_candidates_hybrid(state, k=k, use_hybrid=use_hybrid)


def retrieve_similar_to_movie(
    movie_id: str,
    k: int = 10,
    use_hybrid: bool = True,
) -> List[Movie]:
    """Retrieve movies similar to a given movie."""
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

        results = chroma_client.get_by_ids(ids=[f"movie_{movie_id}"])

        if not results["embeddings"]:
            logger.warning(f"Movie {movie_id} not found in vectordb")
            return []

        query_embedding = results["embeddings"][0]

        similar = chroma_client.similarity_search(
            query_embedding=query_embedding,
            k=k + 1,
            filter_dict=None,
        )

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


def _build_chroma_filter(
    context_factors: Dict[str, Any],
    context: Dict[str, Any] = None,
) -> Optional[Dict[str, Any]]:
    """Build Chroma filter from context factors and user context.

    Always applies a minimum quality gate (vote_average ≥ 5.5 with ≥ 20 votes)
    unless the user explicitly opts in to low-rated content via risk_tolerance.
    """
    conditions = []

    if context:
        language = context.get("language")
        if language:
            conditions.append({"original_language": {"$eq": language}})
        year_min = context.get("year_min")
        year_max = context.get("year_max")
        if year_min:
            conditions.append({"year": {"$gte": int(year_min)}})
        if year_max:
            conditions.append({"year": {"$lte": int(year_max)}})

    # Quality gate: skip obscure Z-grade content unless user has high risk_tolerance
    risk_tolerance = (context_factors or {}).get("risk_tolerance", 0.3)
    if risk_tolerance < 0.7:
        conditions.append({"vote_average": {"$gte": 5.5}})
        conditions.append({"vote_count": {"$gte": 20}})

    if len(conditions) == 1:
        return conditions[0]
    elif len(conditions) > 1:
        return {"$and": conditions}

    return None


# Keep old name for compatibility
_build_filter = _build_chroma_filter


def _enrich_movie_from_tmdb(movie: Movie, force_refresh: bool = False) -> Movie:
    """Enrich movie object with fresh data from TMDB API (on-demand)."""
    try:
        has_complete_data = (
            movie.metadata.title
            and movie.metadata.overview
            and movie.metadata.genres
            and not force_refresh
        )

        if has_complete_data:
            return movie

        movie_service = get_movie_service()
        tmdb_id = int(movie.metadata.tmdb_id) if movie.metadata.tmdb_id else None

        if not tmdb_id:
            return movie

        enriched_movie = movie_service.get_movie_by_id(tmdb_id=tmdb_id)
        if enriched_movie:
            return enriched_movie
        return movie

    except Exception as e:
        logger.warning(f"Failed to enrich movie from TMDB: {e}")
        return movie


def _result_to_movie(result: Dict[str, Any], enrich_from_tmdb: bool = True) -> Optional[Movie]:
    """Convert Chroma search result to Movie object."""
    try:
        from src.core.models import Movie, MovieMetadata

        metadata = result.get("metadata", {})

        genres_str = metadata.get("genres", "")
        genres = [g.strip() for g in genres_str.split(",") if g.strip()]

        chroma_id = result.get("id", "")
        movie_id = metadata.get("movieId", 0)
        if not movie_id and chroma_id.startswith("movie_"):
            movie_id = chroma_id.replace("movie_", "")

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

        movie = Movie(movie_id=str(movie_id), metadata=movie_metadata)

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
    """Retrieve movies on-demand from TMDB API (unlimited scale)."""
    logger.info(f"On-demand retrieval: language={language}, region={region}, k={k}")

    try:
        movie_service = get_movie_service()
        candidate_movies = []

        if include_trending:
            trending = movie_service.get_trending_movies(
                time_window="week", language=language,
            )
            candidate_movies.extend(trending[:k // 2])

        if language:
            popular = movie_service.get_popular_by_language(
                language=language, region=region, limit=k // 2,
            )
            candidate_movies.extend(popular)

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
    """Legacy cold-start: now delegates to hybrid retrieval."""
    return retrieve_candidates_hybrid(state, k=50, use_hybrid=True)
