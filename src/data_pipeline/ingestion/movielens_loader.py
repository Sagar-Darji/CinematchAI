"""MovieLens dataset loader."""

import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from tqdm import tqdm

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MovieLensLoader:
    """Loader for MovieLens 25M dataset."""

    DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-25m.zip"
    DATASET_NAME = "ml-25m"

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize MovieLens loader.

        Args:
            data_dir: Directory for data storage. If None, uses settings.
        """
        settings = get_settings()
        self.data_dir = data_dir or settings.raw_data_dir / "movielens"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.dataset_dir = self.data_dir / self.DATASET_NAME
        self.zip_path = self.data_dir / f"{self.DATASET_NAME}.zip"

    def download(self, force: bool = False) -> Path:
        """
        Download MovieLens dataset.

        Args:
            force: Force re-download even if file exists.

        Returns:
            Path to downloaded zip file.
        """
        if self.zip_path.exists() and not force:
            logger.info(f"Dataset already downloaded: {self.zip_path}")
            return self.zip_path

        logger.info(f"Downloading MovieLens dataset from {self.DATASET_URL}")

        # Stream download with progress bar
        response = requests.get(self.DATASET_URL, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))

        with open(self.zip_path, "wb") as f, tqdm(
            desc="Downloading",
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                pbar.update(len(chunk))

        logger.info(f"Download complete: {self.zip_path}")
        return self.zip_path

    def extract(self, force: bool = False) -> Path:
        """
        Extract MovieLens dataset.

        Args:
            force: Force re-extraction even if directory exists.

        Returns:
            Path to extracted dataset directory.
        """
        if self.dataset_dir.exists() and not force:
            logger.info(f"Dataset already extracted: {self.dataset_dir}")
            return self.dataset_dir

        if not self.zip_path.exists():
            raise FileNotFoundError(f"Zip file not found: {self.zip_path}")

        logger.info(f"Extracting {self.zip_path}")

        with zipfile.ZipFile(self.zip_path, "r") as zip_ref:
            zip_ref.extractall(self.data_dir)

        logger.info(f"Extraction complete: {self.dataset_dir}")
        return self.dataset_dir

    def load_movies(self) -> pd.DataFrame:
        """
        Load movies.csv.

        Returns:
            DataFrame with movies.
        """
        movies_path = self.dataset_dir / "movies.csv"
        if not movies_path.exists():
            raise FileNotFoundError(f"movies.csv not found: {movies_path}")

        logger.info(f"Loading movies from {movies_path}")
        df = pd.read_csv(movies_path)

        # Parse genres
        df["genres"] = df["genres"].str.split("|")

        # Extract year from title
        df["year"] = df["title"].str.extract(r"\((\d{4})\)$")[0].astype("Int64")
        df["title_clean"] = df["title"].str.replace(r"\s*\(\d{4}\)$", "", regex=True)

        logger.info(f"Loaded {len(df)} movies")
        return df

    def load_ratings(self, sample_frac: Optional[float] = None) -> pd.DataFrame:
        """
        Load ratings.csv.

        Args:
            sample_frac: Optional fraction to sample (0-1) for faster loading.

        Returns:
            DataFrame with ratings.
        """
        ratings_path = self.dataset_dir / "ratings.csv"
        if not ratings_path.exists():
            raise FileNotFoundError(f"ratings.csv not found: {ratings_path}")

        logger.info(f"Loading ratings from {ratings_path}")

        if sample_frac and 0 < sample_frac < 1:
            logger.info(f"Sampling {sample_frac*100}% of ratings")
            # Read in chunks and sample
            chunks = []
            for chunk in pd.read_csv(ratings_path, chunksize=1000000):
                sampled = chunk.sample(frac=sample_frac)
                chunks.append(sampled)
            df = pd.concat(chunks, ignore_index=True)
        else:
            df = pd.read_csv(ratings_path)

        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

        logger.info(f"Loaded {len(df)} ratings")
        return df

    def load_tags(self) -> pd.DataFrame:
        """
        Load tags.csv.

        Returns:
            DataFrame with tags.
        """
        tags_path = self.dataset_dir / "tags.csv"
        if not tags_path.exists():
            raise FileNotFoundError(f"tags.csv not found: {tags_path}")

        logger.info(f"Loading tags from {tags_path}")
        df = pd.read_csv(tags_path)

        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")

        logger.info(f"Loaded {len(df)} tags")
        return df

    def load_links(self) -> pd.DataFrame:
        """
        Load links.csv (MovieLens ID to TMDB/IMDB ID mapping).

        Returns:
            DataFrame with links.
        """
        links_path = self.dataset_dir / "links.csv"
        if not links_path.exists():
            raise FileNotFoundError(f"links.csv not found: {links_path}")

        logger.info(f"Loading links from {links_path}")
        df = pd.read_csv(links_path)

        # Convert to string for easier handling
        df["imdbId"] = "tt" + df["imdbId"].astype(str).str.zfill(7)
        df["tmdbId"] = df["tmdbId"].astype("Int64").astype(str)

        logger.info(f"Loaded {len(df)} links")
        return df

    def load_all(self, sample_ratings_frac: Optional[float] = None) -> dict:
        """
        Load all MovieLens datasets.

        Args:
            sample_ratings_frac: Optional fraction to sample ratings.

        Returns:
            Dictionary with all DataFrames.
        """
        return {
            "movies": self.load_movies(),
            "ratings": self.load_ratings(sample_frac=sample_ratings_frac),
            "tags": self.load_tags(),
            "links": self.load_links(),
        }


def get_movielens_loader() -> MovieLensLoader:
    """Get configured MovieLens loader."""
    return MovieLensLoader()
