"""Poster image downloader for movies."""

from pathlib import Path
from typing import Optional

import pandas as pd
from tqdm import tqdm

from config.settings import get_settings
from src.data_pipeline.ingestion.tmdb_fetcher import get_tmdb_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PosterDownloader:
    """Downloads movie posters from TMDB."""

    def __init__(self, save_dir: Optional[Path] = None):
        """
        Initialize poster downloader.

        Args:
            save_dir: Directory to save posters. If None, uses settings.
        """
        settings = get_settings()
        self.save_dir = save_dir or (settings.raw_data_dir / "tmdb" / "posters")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.tmdb_client = get_tmdb_client()

    def download_poster(
        self, poster_path: str, size: str = "w500"
    ) -> Optional[Path]:
        """
        Download a single poster.

        Args:
            poster_path: TMDB poster path.
            size: Image size (w92, w154, w185, w342, w500, w780, original).

        Returns:
            Path to downloaded poster or None if failed.
        """
        return self.tmdb_client.download_poster(
            poster_path, size=size, save_dir=self.save_dir
        )

    def download_batch(
        self,
        movies_df: pd.DataFrame,
        poster_column: str = "poster_path",
        max_downloads: Optional[int] = None,
        size: str = "w500",
    ) -> pd.DataFrame:
        """
        Download posters for a batch of movies.

        Args:
            movies_df: DataFrame with movie data.
            poster_column: Column containing poster paths.
            max_downloads: Maximum number of posters to download.
            size: Image size.

        Returns:
            DataFrame with added 'poster_local_path' column.
        """
        if poster_column not in movies_df.columns:
            logger.warning(f"Column {poster_column} not found in DataFrame")
            return movies_df

        # Filter movies with poster paths
        has_poster = movies_df[poster_column].notna()
        to_download = movies_df[has_poster].copy()

        if max_downloads:
            to_download = to_download.head(max_downloads)

        logger.info(f"Downloading {len(to_download)} posters")

        # Download posters
        local_paths = []
        for poster_path in tqdm(to_download[poster_column], desc="Downloading posters"):
            local_path = self.download_poster(poster_path, size=size)
            local_paths.append(str(local_path) if local_path else None)

        # Add local paths to dataframe
        to_download["poster_local_path"] = local_paths

        # Merge back with original dataframe
        movies_df = movies_df.merge(
            to_download[["movieId", "poster_local_path"]],
            on="movieId",
            how="left",
        )

        successful = sum(1 for p in local_paths if p is not None)
        logger.info(f"Successfully downloaded {successful}/{len(to_download)} posters")

        return movies_df


def get_poster_downloader() -> PosterDownloader:
    """Get configured poster downloader."""
    return PosterDownloader()
