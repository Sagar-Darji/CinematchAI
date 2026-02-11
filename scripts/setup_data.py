"""Setup script to download and prepare MovieLens and TMDB data."""

import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from config.settings import get_settings
from src.data_pipeline.ingestion.movielens_loader import get_movielens_loader
from src.data_pipeline.ingestion.poster_downloader import get_poster_downloader
from src.data_pipeline.ingestion.tmdb_fetcher import get_tmdb_client
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def download_movielens(force: bool = False) -> dict:
    """
    Download and extract MovieLens dataset.

    Args:
        force: Force re-download.

    Returns:
        Dictionary with DataFrames.
    """
    logger.info("=" * 60)
    logger.info("STEP 1: Downloading MovieLens Dataset")
    logger.info("=" * 60)

    loader = get_movielens_loader()

    # Download and extract
    loader.download(force=force)
    loader.extract(force=force)

    # Load all datasets
    logger.info("Loading MovieLens datasets...")
    data = loader.load_all(sample_ratings_frac=None)  # Load full dataset

    logger.info(f"Movies: {len(data['movies'])}")
    logger.info(f"Ratings: {len(data['ratings'])}")
    logger.info(f"Tags: {len(data['tags'])}")
    logger.info(f"Links: {len(data['links'])}")

    return data


def enrich_with_tmdb(
    movies_df: pd.DataFrame,
    links_df: pd.DataFrame,
    max_movies: int = None,
) -> pd.DataFrame:
    """
    Enrich movies with TMDB metadata.

    Args:
        movies_df: MovieLens movies DataFrame.
        links_df: MovieLens links DataFrame.
        max_movies: Maximum number of movies to enrich (for testing).

    Returns:
        Enriched movies DataFrame.
    """
    logger.info("=" * 60)
    logger.info("STEP 2: Enriching with TMDB Metadata")
    logger.info("=" * 60)

    # Merge with links to get TMDB IDs
    movies_with_links = movies_df.merge(links_df, on="movieId", how="left")

    if max_movies:
        logger.info(f"Limiting to {max_movies} movies for testing")
        movies_with_links = movies_with_links.head(max_movies)

    tmdb_client = get_tmdb_client()
    enriched_movies = []

    logger.info(f"Enriching {len(movies_with_links)} movies with TMDB data...")

    for _, movie in tqdm(movies_with_links.iterrows(), total=len(movies_with_links), desc="Enriching"):
        try:
            # Skip if no TMDB ID
            if pd.isna(movie["tmdbId"]):
                enriched_movies.append(movie.to_dict())
                continue

            # Get TMDB details
            tmdb_id = str(int(float(movie["tmdbId"])))
            details = tmdb_client.get_movie_details(tmdb_id)

            # Create enriched record
            enriched = movie.to_dict()
            enriched.update({
                "overview": details.get("overview"),
                "tagline": details.get("tagline"),
                "release_date": details.get("release_date"),
                "tmdb_genres": [g["name"] for g in details.get("genres", [])],
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
            })

            # Extract cast and crew
            credits = details.get("credits", {})
            cast = credits.get("cast", [])[:10]
            crew = credits.get("crew", [])

            enriched["cast"] = [c["name"] for c in cast]
            directors = [c["name"] for c in crew if c.get("job") == "Director"]
            enriched["director"] = directors[0] if directors else None

            enriched_movies.append(enriched)

        except Exception as e:
            logger.warning(f"Failed to enrich movie {movie['movieId']}: {e}")
            enriched_movies.append(movie.to_dict())

    enriched_df = pd.DataFrame(enriched_movies)
    logger.info(f"Enrichment complete: {len(enriched_df)} movies")

    return enriched_df


def download_posters(
    movies_df: pd.DataFrame,
    max_posters: int = None,
) -> pd.DataFrame:
    """
    Download movie posters.

    Args:
        movies_df: Movies DataFrame with poster_path column.
        max_posters: Maximum number of posters to download.

    Returns:
        DataFrame with poster_local_path column.
    """
    logger.info("=" * 60)
    logger.info("STEP 3: Downloading Posters")
    logger.info("=" * 60)

    downloader = get_poster_downloader()
    return downloader.download_batch(
        movies_df,
        max_downloads=max_posters,
        size="w500",
    )


def save_processed_data(data: dict, movies_enriched: pd.DataFrame) -> None:
    """
    Save processed data to parquet files.

    Args:
        data: Original MovieLens data.
        movies_enriched: Enriched movies DataFrame.
    """
    logger.info("=" * 60)
    logger.info("STEP 4: Saving Processed Data")
    logger.info("=" * 60)

    settings = get_settings()
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)

    # Save enriched movies
    movies_path = settings.processed_data_dir / "movies_enriched.parquet"
    movies_enriched.to_parquet(movies_path, index=False)
    logger.info(f"Saved enriched movies: {movies_path}")

    # Save ratings
    ratings_path = settings.processed_data_dir / "ratings.parquet"
    data["ratings"].to_parquet(ratings_path, index=False)
    logger.info(f"Saved ratings: {ratings_path}")

    # Save tags
    tags_path = settings.processed_data_dir / "tags.parquet"
    data["tags"].to_parquet(tags_path, index=False)
    logger.info(f"Saved tags: {tags_path}")

    logger.info("All data saved successfully!")


def main():
    """Main setup script."""
    parser = argparse.ArgumentParser(description="Setup MovieLens and TMDB data")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download of MovieLens dataset",
    )
    parser.add_argument(
        "--max-movies",
        type=int,
        default=None,
        help="Maximum number of movies to enrich (for testing)",
    )
    parser.add_argument(
        "--max-posters",
        type=int,
        default=None,
        help="Maximum number of posters to download (for testing)",
    )
    parser.add_argument(
        "--skip-tmdb",
        action="store_true",
        help="Skip TMDB enrichment",
    )
    parser.add_argument(
        "--skip-posters",
        action="store_true",
        help="Skip poster downloads",
    )

    args = parser.parse_args()

    # Setup logging
    settings = get_settings()
    log_file = Path("logs") / "setup_data.log"
    setup_logging(log_file=log_file)

    logger.info("Starting data setup...")
    logger.info(f"Arguments: {args}")

    try:
        # Step 1: Download MovieLens
        data = download_movielens(force=args.force_download)

        # Step 2: Enrich with TMDB
        if not args.skip_tmdb:
            movies_enriched = enrich_with_tmdb(
                data["movies"],
                data["links"],
                max_movies=args.max_movies,
            )
        else:
            logger.info("Skipping TMDB enrichment")
            movies_enriched = data["movies"]

        # Step 3: Download posters
        if not args.skip_posters and not args.skip_tmdb:
            movies_enriched = download_posters(
                movies_enriched,
                max_posters=args.max_posters,
            )
        else:
            logger.info("Skipping poster downloads")

        # Step 4: Save processed data
        save_processed_data(data, movies_enriched)

        logger.info("=" * 60)
        logger.info("DATA SETUP COMPLETE!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Run: python scripts/build_embeddings.py")
        logger.info("2. Run: python scripts/build_vectordb.py")

    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
