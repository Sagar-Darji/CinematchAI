"""Build embeddings for all movies."""

import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from config.settings import get_settings
from src.core.embeddings import get_hybrid_embedder, get_image_embedder, get_text_embedder
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def build_text_embeddings(movies_df: pd.DataFrame, save_dir: Path) -> None:
    """
    Build text embeddings for all movies.

    Args:
        movies_df: DataFrame with movie data.
        save_dir: Directory to save embeddings.
    """
    logger.info("=" * 60)
    logger.info("Building Text Embeddings")
    logger.info("=" * 60)

    text_embedder = get_text_embedder()

    # Prepare combined text for each movie
    movie_texts = []
    for _, movie in tqdm(movies_df.iterrows(), total=len(movies_df), desc="Preparing texts"):
        # Combine title, overview, genres
        parts = [str(movie.get("title_clean", movie.get("title", "")))]

        if pd.notna(movie.get("overview")):
            parts.append(str(movie["overview"]))

        genres = movie.get("tmdb_genres")
        if isinstance(genres, list) and len(genres) > 0:
            parts.append(" ".join(genres))
        elif genres is not None and not (isinstance(genres, float) and pd.isna(genres)):
            parts.append(str(genres))

        if pd.notna(movie.get("director")):
            parts.append(f"Directed by {movie['director']}")

        cast = movie.get("cast")
        if isinstance(cast, list) and len(cast) > 0:
            top_cast = cast[:5]  # Top 5
            parts.append(f"Starring {', '.join(top_cast)}")

        combined = ". ".join(parts)
        movie_texts.append(combined)

    # Generate embeddings in batch
    logger.info(f"Generating text embeddings for {len(movie_texts)} movies...")
    text_embeddings = text_embedder.embed_batch(
        movie_texts, batch_size=32, show_progress=True
    )

    # Save embeddings
    save_path = save_dir / "movie_text_embeddings.npy"
    text_embedder.save_embeddings(text_embeddings, save_path)

    logger.info(f"✓ Text embeddings saved: {text_embeddings.shape}")


def build_image_embeddings(movies_df: pd.DataFrame, save_dir: Path) -> None:
    """
    Build image embeddings for movie posters.

    Args:
        movies_df: DataFrame with movie data.
        save_dir: Directory to save embeddings.
    """
    logger.info("=" * 60)
    logger.info("Building Image Embeddings")
    logger.info("=" * 60)

    image_embedder = get_image_embedder()
    settings = get_settings()

    # Collect poster paths
    poster_paths = []
    for _, movie in movies_df.iterrows():
        poster_path = movie.get("poster_local_path")
        if pd.notna(poster_path) and Path(poster_path).exists():
            poster_paths.append(Path(poster_path))
        else:
            # Use None for missing posters (will be handled as zeros)
            poster_paths.append(None)

    # Generate embeddings
    logger.info(f"Generating image embeddings for {len(poster_paths)} posters...")

    image_embeddings = []
    valid_count = 0

    for i, poster_path in enumerate(tqdm(poster_paths, desc="Processing posters")):
        if poster_path is not None:
            try:
                embedding = image_embedder.embed_image(poster_path, normalize=True)
                image_embeddings.append(embedding)
                valid_count += 1
            except Exception as e:
                logger.warning(f"Failed to process poster {poster_path}: {e}")
                # Use zero embedding for failed images
                zero_emb = np.zeros(image_embedder.embedding_dim)
                image_embeddings.append(zero_emb)
        else:
            # Use zero embedding for missing posters
            import numpy as np
            zero_emb = np.zeros(image_embedder.embedding_dim)
            image_embeddings.append(zero_emb)

    import numpy as np
    image_embeddings = np.array(image_embeddings)

    # Save embeddings
    save_path = save_dir / "movie_image_embeddings.npy"
    image_embedder.save_embeddings(image_embeddings, save_path)

    logger.info(f"✓ Image embeddings saved: {image_embeddings.shape}")
    logger.info(f"  Valid posters processed: {valid_count}/{len(poster_paths)}")


def build_hybrid_embeddings(save_dir: Path) -> None:
    """
    Build hybrid embeddings by combining text and image embeddings.

    Args:
        save_dir: Directory with saved embeddings.
    """
    logger.info("=" * 60)
    logger.info("Building Hybrid Embeddings")
    logger.info("=" * 60)

    import numpy as np

    # Load text and image embeddings
    text_embeddings = np.load(save_dir / "movie_text_embeddings.npy")
    image_embeddings = np.load(save_dir / "movie_image_embeddings.npy")

    logger.info(f"Text embeddings shape: {text_embeddings.shape}")
    logger.info(f"Image embeddings shape: {image_embeddings.shape}")

    # Initialize hybrid embedder
    hybrid_embedder = get_hybrid_embedder()

    # Combine embeddings
    logger.info("Combining text and image embeddings...")
    hybrid_embeddings = hybrid_embedder.embed_batch_hybrid(
        text_embeddings, image_embeddings
    )

    # Save hybrid embeddings
    save_path = save_dir / "movie_hybrid_embeddings.npy"
    hybrid_embedder.save_embeddings(hybrid_embeddings, save_path)

    logger.info(f"✓ Hybrid embeddings saved: {hybrid_embeddings.shape}")


def main():
    """Main embedding generation script."""
    parser = argparse.ArgumentParser(description="Build movie embeddings")
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Build only text embeddings",
    )
    parser.add_argument(
        "--image-only",
        action="store_true",
        help="Build only image embeddings",
    )
    parser.add_argument(
        "--no-hybrid",
        action="store_true",
        help="Skip hybrid embedding generation",
    )

    args = parser.parse_args()

    # Setup logging
    log_file = Path("logs") / "build_embeddings.log"
    setup_logging(log_file=log_file)

    logger.info("Starting embedding generation...")

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

        # Create embeddings directory
        embeddings_dir = settings.embeddings_dir
        embeddings_dir.mkdir(parents=True, exist_ok=True)

        # Build embeddings based on arguments
        if not args.image_only:
            build_text_embeddings(movies_df, embeddings_dir)

        if not args.text_only:
            build_image_embeddings(movies_df, embeddings_dir)

        if not args.no_hybrid and not args.text_only and not args.image_only:
            build_hybrid_embeddings(embeddings_dir)

        logger.info("=" * 60)
        logger.info("EMBEDDING GENERATION COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"\nEmbeddings saved to: {embeddings_dir}")
        logger.info("\nNext step:")
        logger.info("  python scripts/build_vectordb.py")

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
