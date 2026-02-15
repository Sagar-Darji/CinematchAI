"""Movie Browsing API Routes - Trending, Regional, Recent Releases."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas.response import ErrorResponse, MovieResponse
from src.services.movie_service import get_movie_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/movies", tags=["movies"])


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
):
    """
    Get trending movies from TMDB.

    - **time_window**: "day" or "week" (default: week)
    - **language**: Optional language filter (ISO 639-1 code)

    Returns currently trending movies, optionally filtered by language.
    """
    logger.info(f"GET /movies/trending: time_window={time_window}, language={language}")

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
        )

        # Convert to MovieResponse format
        movie_responses = [
            MovieResponse(
                tmdb_id=int(movie.metadata.tmdb_id),
                title=movie.metadata.title,
                year=movie.metadata.year,
                genres=movie.metadata.genres,
                overview=movie.metadata.overview,
                vote_average=movie.metadata.vote_average,
                director=movie.metadata.director,
                poster_path=movie.metadata.poster_path,
            )
            for movie in movies
        ]

        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "time_window": time_window,
            "language": language,
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

        movie_responses = [
            MovieResponse(
                tmdb_id=int(movie.metadata.tmdb_id),
                title=movie.metadata.title,
                year=movie.metadata.year,
                genres=movie.metadata.genres,
                overview=movie.metadata.overview,
                vote_average=movie.metadata.vote_average,
                director=movie.metadata.director,
                poster_path=movie.metadata.poster_path,
            )
            for movie in movies
        ]

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

        movie_responses = [
            MovieResponse(
                tmdb_id=int(movie.metadata.tmdb_id),
                title=movie.metadata.title,
                year=movie.metadata.year,
                genres=movie.metadata.genres,
                overview=movie.metadata.overview,
                vote_average=movie.metadata.vote_average,
                director=movie.metadata.director,
                poster_path=movie.metadata.poster_path,
            )
            for movie in movies
        ]

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
):
    """
    Search movies by title.

    - **query**: Search query (movie title)
    - **year**: Optional year filter
    - **language**: Optional language filter
    - **limit**: Number of results (default: 20, max: 50)

    Returns movies matching the search query.
    """
    logger.info(
        f"GET /movies/search: query={query}, year={year}, language={language}, limit={limit}"
    )

    try:
        service = get_movie_service()
        movies = service.search_movies(
            query=query,
            year=year,
            language=language,
            limit=limit,
        )

        movie_responses = [
            MovieResponse(
                tmdb_id=int(movie.metadata.tmdb_id),
                title=movie.metadata.title,
                year=movie.metadata.year,
                genres=movie.metadata.genres,
                overview=movie.metadata.overview,
                vote_average=movie.metadata.vote_average,
                director=movie.metadata.director,
                poster_path=movie.metadata.poster_path,
            )
            for movie in movies
        ]

        return {
            "movies": movie_responses,
            "count": len(movie_responses),
            "query": query,
            "year": year,
            "language": language,
        }

    except Exception as e:
        logger.error(f"Failed to search movies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search movies",
        )


@router.get(
    "/discover",
    status_code=status.HTTP_200_OK,
)
async def discover_movies(
    genre: Optional[str] = Query(None, description="Genre name (e.g. Action, Comedy)"),
    language: Optional[str] = Query(None, description="Language code (e.g. en, hi, ko)"),
    limit: int = Query(40, ge=1, le=50, description="Number of results"),
):
    """
    Discover movies by genre and/or language via TMDB.

    Falls back to trending if no genre specified.
    """
    logger.info(f"GET /movies/discover: genre={genre}, language={language}, limit={limit}")
    try:
        service = get_movie_service()
        # Use search with genre keyword, or trending as fallback
        if genre:
            movies = service.search_movies(query=genre, language=language, limit=limit)
        else:
            movies = service.get_trending_movies(time_window="week", language=language)
            movies = movies[:limit]

        movie_responses = [
            MovieResponse(
                tmdb_id=int(m.metadata.tmdb_id),
                title=m.metadata.title,
                year=m.metadata.year,
                genres=m.metadata.genres,
                overview=m.metadata.overview,
                vote_average=m.metadata.vote_average,
                director=m.metadata.director,
                poster_path=m.metadata.poster_path,
            )
            for m in movies
        ]
        return {"movies": movie_responses, "count": len(movie_responses), "genre": genre, "language": language}
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
async def get_movie_by_id(tmdb_id: int):
    """
    Get movie details by TMDB ID.

    - **tmdb_id**: TMDB movie ID

    Returns detailed movie information from TMDB API.
    """
    logger.info(f"GET /movies/{tmdb_id}")

    try:
        service = get_movie_service()
        movie = service.get_movie_by_id(tmdb_id=tmdb_id)

        if not movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Movie {tmdb_id} not found",
            )

        movie_response = MovieResponse(
            tmdb_id=int(movie.metadata.tmdb_id),
            title=movie.metadata.title,
            year=movie.metadata.year,
            genres=movie.metadata.genres,
            overview=movie.metadata.overview,
            vote_average=movie.metadata.vote_average,
            director=movie.metadata.director,
            poster_path=movie.metadata.poster_path,
        )

        return movie_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get movie {tmdb_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get movie {tmdb_id}",
        )
