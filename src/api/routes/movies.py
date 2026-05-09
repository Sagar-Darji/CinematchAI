"""Movie Browsing API Routes - Trending, Regional, Recent Releases."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas.response import ErrorResponse, MovieResponse, SeasonDetailResponse
from src.services.movie_service import get_movie_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/movies", tags=["movies"])


def _to_movie_response(movie, extras: dict | None = None) -> MovieResponse:
    """Convert a domain movie/media object to API response shape.

    `extras` is the optional dict returned by MovieService.get_detail_extras —
    only populated for the single-title detail endpoint. List endpoints
    (trending, search, etc.) pass None and the trailer/cast/similar fields
    stay at their defaults.
    """
    extras = extras or {}
    return MovieResponse(
        tmdb_id=int(movie.metadata.tmdb_id),
        title=movie.metadata.title,
        year=movie.metadata.year,
        genres=movie.metadata.genres,
        overview=movie.metadata.overview or "",
        vote_average=movie.metadata.vote_average,
        director=movie.metadata.director,
        creator=movie.metadata.creator,
        poster_path=movie.metadata.poster_path,
        backdrop_path=movie.metadata.backdrop_path,
        runtime=movie.metadata.runtime,
        original_language=movie.metadata.original_language,
        media_type=movie.metadata.media_type,
        season_count=movie.metadata.season_count,
        episode_count=movie.metadata.episode_count,
        seasons=[
            {
                "season_number": season.season_number,
                "name": season.name,
                "episode_count": season.episode_count,
                "air_date": season.air_date.isoformat() if season.air_date else None,
                "poster_path": season.poster_path,
            }
            for season in movie.metadata.seasons
        ],
        trailer_key=extras.get("trailer_key"),
        cast=extras.get("cast") or [],
        similar=extras.get("similar") or [],
    )


@router.get(
    "/trending",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_trending_movies(
    time_window: str = Query("week", description="Time window: day or week"),
    language: Optional[str] = Query(None, description="Filter by language (e.g., en, hi, ko, ja)"),
    page: int = Query(1, ge=1, le=500, description="Page number (default: 1)"),
    media_type: str = Query("movie", description="Media type: movie or tv"),
):
    """
    Get trending movies from TMDB.

    - **time_window**: "day" or "week" (default: week)
    - **language**: Optional language filter (ISO 639-1 code)
    - **page**: Page number for pagination (default: 1)

    Returns currently trending movies, optionally filtered by language.
    """
    logger.info(
        f"GET /movies/trending: media_type={media_type}, time_window={time_window}, language={language}, page={page}"
    )

    if time_window not in ["day", "week"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="time_window must be 'day' or 'week'",
        )

    try:
        service = get_movie_service()
        movies = service.get_trending_movies(
            time_window=time_window,
            language=language,
            page=page,
            media_type=media_type,
        )

        movie_responses = [_to_movie_response(movie) for movie in movies]

        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "time_window": time_window,
            "language": language,
            "page": page,
            "media_type": media_type,
        }

    except Exception as e:
        logger.error(f"Failed to get trending movies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trending movies",
        )


@router.get(
    "/popular/{language}",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_popular_by_language(
    language: str,
    region: Optional[str] = Query(None, description="Region code (e.g., IN, KR, JP)"),
    limit: int = Query(20, ge=1, le=50, description="Number of movies (max 50)"),
):
    """
    Get popular movies by language/region.

    - **language**: Language code (e.g., "hi" for Hindi, "ko" for Korean, "ja" for Japanese)
    - **region**: Optional region code (e.g., "IN" for India, "KR" for Korea)
    - **limit**: Number of movies (default: 20, max: 50)

    Returns popular movies in the specified language/region.
    """
    logger.info(
        f"GET /movies/popular/{language}: region={region}, limit={limit}"
    )

    try:
        service = get_movie_service()
        movies = service.get_popular_by_language(
            language=language,
            region=region,
            limit=limit,
        )

        movie_responses = [_to_movie_response(movie) for movie in movies]

        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "language": language,
            "region": region,
        }

    except Exception as e:
        logger.error(f"Failed to get popular movies for {language}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get popular movies for language {language}",
        )


@router.get(
    "/recent",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_recent_releases(
    language: Optional[str] = Query(None, description="Filter by language"),
    region: Optional[str] = Query(None, description="Filter by region"),
    days: int = Query(90, ge=1, le=365, description="Look back N days (default: 90)"),
):
    """
    Get recent movie releases.

    - **language**: Optional language filter (e.g., "en", "hi", "ko")
    - **region**: Optional region filter (e.g., "US", "IN", "KR")
    - **days**: Look back N days from today (default: 90, max: 365)

    Returns recent releases filtered by language/region.
    """
    logger.info(
        f"GET /movies/recent: language={language}, region={region}, days={days}"
    )

    try:
        service = get_movie_service()
        movies = service.get_recent_releases(
            language=language,
            region=region,
            days=days,
        )

        movie_responses = [_to_movie_response(movie) for movie in movies]

        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "language": language,
            "region": region,
            "days": days,
        }

    except Exception as e:
        logger.error(f"Failed to get recent releases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent releases",
        )


@router.get(
    "/search",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def search_movies(
    query: str = Query(..., min_length=1, description="Search query"),
    year: Optional[int] = Query(None, description="Filter by year"),
    language: Optional[str] = Query(None, description="Filter by language"),
    limit: int = Query(20, ge=1, le=50, description="Number of results (max 50)"),
    page: int = Query(1, ge=1, le=500, description="Page number (default: 1)"),
    media_type: str = Query("movie", description="Media type: movie or tv"),
):
    """
    Search movies by title.

    - **query**: Search query (movie title)
    - **year**: Optional year filter
    - **language**: Optional language filter
    - **limit**: Number of results (default: 20, max: 50)
    - **page**: Page number for pagination (default: 1)

    Returns movies matching the search query.
    """
    logger.info(
        f"GET /movies/search: media_type={media_type}, query={query}, year={year}, language={language}, limit={limit}, page={page}"
    )

    try:
        service = get_movie_service()
        movies = service.search_movies(
            query=query,
            year=year,
            language=language,
            limit=limit,
            page=page,
            media_type=media_type,
        )

        movie_responses = [_to_movie_response(movie) for movie in movies]

        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "query": query,
            "year": year,
            "language": language,
            "page": page,
            "media_type": media_type,
        }

    except Exception as e:
        logger.error(f"Failed to search movies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search movies",
        )


@router.get(
    "/now-playing",
    status_code=status.HTTP_200_OK,
    responses={500: {"model": ErrorResponse}},
)
async def get_now_playing(
    region: Optional[str] = Query(None, description="Region code (e.g., US, IN, GB)"),
    language: Optional[str] = Query(None, description="Language code (e.g., en, hi)"),
    page: int = Query(1, ge=1, le=500),
):
    """Get movies currently playing in theaters."""
    try:
        service = get_movie_service()
        movies = service.get_now_playing(region=region, language=language, page=page)
        movie_responses = [_to_movie_response(m) for m in movies]
        return {"movies": movie_responses, "count": len(movie_responses), "region": region, "page": page}
    except Exception as e:
        logger.error(f"Failed to get now playing: {e}")
        raise HTTPException(status_code=500, detail="Failed to get now playing movies")


@router.get(
    "/upcoming",
    status_code=status.HTTP_200_OK,
    responses={500: {"model": ErrorResponse}},
)
async def get_upcoming(
    region: Optional[str] = Query(None, description="Region code (e.g., US, IN, GB)"),
    language: Optional[str] = Query(None, description="Language code (e.g., en, hi)"),
    page: int = Query(1, ge=1, le=500),
):
    """Get upcoming theatrical releases."""
    try:
        service = get_movie_service()
        movies = service.get_upcoming(region=region, language=language, page=page)
        movie_responses = [_to_movie_response(m) for m in movies]
        return {"movies": movie_responses, "count": len(movie_responses), "region": region, "page": page}
    except Exception as e:
        logger.error(f"Failed to get upcoming: {e}")
        raise HTTPException(status_code=500, detail="Failed to get upcoming movies")


@router.get(
    "/ott-releases",
    status_code=status.HTTP_200_OK,
    responses={500: {"model": ErrorResponse}},
)
async def get_ott_releases(
    providers: Optional[str] = Query(None, description="Pipe-separated provider IDs (e.g. '8|9|337')"),
    region: str = Query("US", description="Watch region (e.g., US, IN, GB)"),
    language: Optional[str] = Query(None, description="Language filter"),
    days: int = Query(30, ge=1, le=365, description="Look back N days"),
    page: int = Query(1, ge=1, le=500),
):
    """Get recent OTT/streaming releases (Netflix, Prime Video, Disney+, etc.)."""
    try:
        service = get_movie_service()
        movies = service.get_ott_releases(
            provider_ids=providers,
            region=region,
            language=language,
            days=days,
            page=page,
        )
        movie_responses = [_to_movie_response(m) for m in movies]
        return {"movies": movie_responses, "count": len(movie_responses), "region": region, "days": days, "page": page}
    except Exception as e:
        logger.error(f"Failed to get OTT releases: {e}")
        raise HTTPException(status_code=500, detail="Failed to get OTT releases")


@router.get(
    "/discover",
    status_code=status.HTTP_200_OK,
)
async def discover_movies(
    genre: Optional[str] = Query(None, description="Genre name (e.g. Action, Comedy)"),
    language: Optional[str] = Query(None, description="Language code (e.g. en, hi, ko)"),
    limit: int = Query(40, ge=1, le=50, description="Number of results"),
    page: int = Query(1, ge=1, le=500, description="Page number (default: 1)"),
    media_type: str = Query("movie", description="Media type: movie or tv"),
):
    """
    Discover movies by genre and/or language via TMDB.

    Falls back to trending if no genre specified.
    """
    logger.info(
        f"GET /movies/discover: media_type={media_type}, genre={genre}, language={language}, limit={limit}, page={page}"
    )
    try:
        service = get_movie_service()
        if genre:
            movies = service.discover_media(
                genre=genre,
                language=language,
                limit=limit,
                page=page,
                media_type=media_type,
            )
        else:
            movies = service.get_trending_movies(
                time_window="week",
                language=language,
                page=page,
                media_type=media_type,
            )
            movies = movies[:limit]

        movie_responses = [_to_movie_response(m) for m in movies]
        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "genre": genre,
            "language": language,
            "page": page,
            "media_type": media_type,
        }
    except Exception as e:
        logger.error(f"Failed to discover movies: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover movies")


@router.get(
    "/{tmdb_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_movie_by_id(
    tmdb_id: int,
    media_type: str = Query("movie", description="Media type: movie or tv"),
):
    """
    Get movie details by TMDB ID.

    - **tmdb_id**: TMDB movie ID

    Returns detailed movie information from TMDB API.
    """
    logger.info(f"GET /movies/{tmdb_id}: media_type={media_type}")

    try:
        service = get_movie_service()
        movie = service.get_movie_by_id(tmdb_id=tmdb_id, media_type=media_type)

        if not movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Movie {tmdb_id} not found",
            )

        # Detail-page enrichment: trailer + rich cast + similar titles.
        extras = service.get_detail_extras(tmdb_id=tmdb_id, media_type=media_type)
        return _to_movie_response(movie, extras=extras)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get movie {tmdb_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get movie {tmdb_id}",
        )


@router.get(
    "/{tmdb_id}/seasons/{season_number}",
    status_code=status.HTTP_200_OK,
    response_model=SeasonDetailResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_season_episodes(tmdb_id: int, season_number: int):
    """
    Get the episode list for one season of a TV show.

    Powers the in-player episode picker drawer — returns thumbnails, titles,
    runtimes, and air dates per episode.
    """
    logger.info(f"GET /movies/{tmdb_id}/seasons/{season_number}")

    if season_number < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="season_number must be >= 0",
        )

    try:
        service = get_movie_service()
        result = service.get_season_episodes(tmdb_id=tmdb_id, season_number=season_number)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Season {season_number} of TV {tmdb_id} not found",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get season {tmdb_id}/{season_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get season {tmdb_id}/{season_number}",
        )
