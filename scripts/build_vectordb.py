"""Build Chroma vector database from movie embeddings."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.core.vectordb import get_chroma_client
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def prepare_metadata(movie: pd.Series) -> dict:
    """
    Prepare metadata dictionary for a movie.

    Chroma metadata values must be str, int, float, or bool.

    Args:
        movie: Movie row from DataFrame.

    Returns:
        Metadata dictionary.
    """
    metadata = {}

    # Basic fields
    metadata["movieId"] = int(movie["movieId"])
    metadata["title"] = str(movie.get("title", ""))

    genres = movie.get("genres")
    if isinstance(genres, (list, np.ndarray)) and len(genres) > 0:
        metadata["genres"] = ", ".join(str(g) for g in genres)
    elif genres is not None and not (isinstance(genres, float) and pd.isna(genres)):
        metadata["genres"] = str(genres)

    # TMDB fields
    if pd.notna(movie.get("overview")):
        metadata["overview"] = str(movie["overview"])[:500]  # Truncate for Chroma limits

    if pd.notna(movie.get("director")):
        metadata["director"] = str(movie["director"])

    cast = movie.get("cast")
    if isinstance(cast, (list, np.ndarray)) and len(cast) > 0:
        metadata["cast"] = ", ".join(str(c) for c in cast[:5])

    tmdb_genres = movie.get("tmdb_genres")
    if isinstance(tmdb_genres, (list, np.ndarray)) and len(tmdb_genres) > 0:
        metadata["tmdb_genres"] = ", ".join(str(g) for g in tmdb_genres)

    if pd.notna(movie.get("vote_average")):
        metadata["vote_average"] = float(movie["vote_average"])

    if pd.notna(movie.get("vote_count")):
        metadata["vote_count"] = int(movie["vote_count"])

    if pd.notna(movie.get("popularity")):
        metadata["popularity"] = float(movie["popularity"])

    if pd.notna(movie.get("runtime")):
        metadata["runtime"] = int(movie["runtime"])

    if pd.notna(movie.get("release_date")):
        metadata["release_date"] = str(movie["release_date"])

    if pd.notna(movie.get("original_language")):
        metadata["original_language"] = str(movie["original_language"])

    if pd.notna(movie.get("poster_path")):
        metadata["poster_path"] = str(movie["poster_path"])

    if pd.notna(movie.get("poster_local_path")):
        metadata["poster_local_path"] = str(movie["poster_local_path"])

    return metadata


def build_vectordb(
    movies_df: pd.DataFrame,
    embeddings: np.ndarray,
    collection_name: str,
    embedding_type: str,
    force: bool = False,
) -> None:
    """
    Build a Chroma collection from embeddings.

    Args:
        movies_df: Movies DataFrame.
        embeddings: Embedding vectors.
        collection_name: Name for the Chroma collection.
        embedding_type: Type of embeddings (for logging).
        force: Force recreate collection if it exists.
    """
    logger.info("=" * 60)
    logger.info(f"Building Vector DB: {collection_name} ({embedding_type})")
    logger.info("=" * 60)

    assert len(movies_df) == len(embeddings), (
        f"Mismatch: {len(movies_df)} movies vs {len(embeddings)} embeddings"
    )

    chroma_client = get_chroma_client(collection_name=collection_name)

    # Delete existing collection if force
    if force:
        try:
            chroma_client.delete_collection(collection_name)
            logger.info(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass

    # Create collection
    chroma_client.create_collection(collection_name)

    # Prepare IDs, metadata, and documents
    ids = [f"movie_{int(row['movieId'])}" for _, row in movies_df.iterrows()]

    logger.info("Preparing metadata...")
    metadatas = [prepare_metadata(row) for _, row in movies_df.iterrows()]

    documents = []
    for _, row in movies_df.iterrows():
        parts = [str(row.get("title", ""))]
        if pd.notna(row.get("overview")):
            parts.append(str(row["overview"]))
        documents.append(". ".join(parts))

    # Add embeddings to collection
    logger.info(f"Adding {len(ids)} embeddings to collection...")
    chroma_client.add_embeddings(
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas,
        documents=documents,
    )

    count = chroma_client.count()
    logger.info(f"Collection '{collection_name}' now has {count} items")


def main():
    """Main vector database build script."""
    parser = argparse.ArgumentParser(description="Build Chroma vector database")
    parser.add_argument(
        "--embedding-type",
        choices=["text", "image", "hybrid", "all"],
        default="hybrid",
        help="Which embeddings to index (default: hybrid)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreate collections",
    )

    args = parser.parse_args()

    # Setup logging
    log_file = Path("logs") / "build_vectordb.log"
    setup_logging(log_file=log_file)

    logger.info("Starting vector database build...")
    logger.info(f"Arguments: {args}")

    try:
        settings = get_settings()

        # Load processed movies
        movies_path = settings.processed_data_dir / "movies_enriched.parquet"
        if not movies_path.exists():
            raise FileNotFoundError(
                f"Processed movies not found: {movies_path}\n"
                "Run 'python scripts/setup_data.py' first"
            )

        logger.info(f"Loading movies from {movies_path}")
        movies_df = pd.read_parquet(movies_path)
        logger.info(f"Loaded {len(movies_df)} movies")

        embeddings_dir = settings.embeddings_dir

        # Build collections based on embedding type
        embedding_configs = {
            "text": ("movie_text_embeddings.npy", f"{settings.chroma_collection_movies}_text"),
            "image": ("movie_image_embeddings.npy", f"{settings.chroma_collection_movies}_image"),
            "hybrid": ("movie_hybrid_embeddings.npy", settings.chroma_collection_movies),
        }

        types_to_build = (
            list(embedding_configs.keys()) if args.embedding_type == "all"
            else [args.embedding_type]
        )

        for emb_type in types_to_build:
            emb_file, collection_name = embedding_configs[emb_type]
            emb_path = embeddings_dir / emb_file

            if not emb_path.exists():
                logger.warning(f"Embeddings not found: {emb_path}, skipping {emb_type}")
                continue

            embeddings = np.load(emb_path)
            logger.info(f"Loaded {emb_type} embeddings: {embeddings.shape}")

            build_vectordb(
                movies_df=movies_df,
                embeddings=embeddings,
                collection_name=collection_name,
                embedding_type=emb_type,
                force=args.force,
            )

        logger.info("=" * 60)
        logger.info("VECTOR DATABASE BUILD COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"\nDatabase stored at: {settings.chroma_persist_dir}")

    except Exception as e:
        logger.error(f"Vector database build failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
