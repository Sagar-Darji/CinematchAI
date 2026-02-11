"""Hybrid embedding generation combining text and image embeddings."""

from pathlib import Path
from typing import Optional

import numpy as np

from config.settings import get_settings
from src.core.embeddings.image_embedder import get_image_embedder
from src.core.embeddings.text_embedder import get_text_embedder
from src.utils.logging import get_logger

logger = get_logger(__name__)


class HybridEmbedder:
    """Hybrid embedder combining text and image embeddings."""

    def __init__(
        self,
        text_weight: Optional[float] = None,
        image_weight: Optional[float] = None,
        device: Optional[str] = None,
    ):
        """
        Initialize hybrid embedder.

        Args:
            text_weight: Weight for text embeddings. If None, uses settings.
            image_weight: Weight for image embeddings. If None, uses settings.
            device: Device to use. If None, auto-detects.
        """
        settings = get_settings()

        self.text_weight = text_weight or settings.hybrid_text_weight
        self.image_weight = image_weight or settings.hybrid_image_weight

        # Validate weights
        if not np.isclose(self.text_weight + self.image_weight, 1.0):
            logger.warning(
                f"Weights don't sum to 1.0: text={self.text_weight}, image={self.image_weight}"
            )

        # Initialize embedders
        logger.info("Initializing text and image embedders...")
        self.text_embedder = get_text_embedder(device=device)
        self.image_embedder = get_image_embedder(device=device)

        logger.info(
            f"Hybrid embedder ready (text_weight={self.text_weight}, image_weight={self.image_weight})"
        )

    def combine_embeddings(
        self, text_embedding: np.ndarray, image_embedding: np.ndarray
    ) -> np.ndarray:
        """
        Combine text and image embeddings using weighted fusion.

        Args:
            text_embedding: Text embedding vector.
            image_embedding: Image embedding vector.

        Returns:
            Hybrid embedding vector.
        """
        # Normalize individual embeddings
        text_norm = text_embedding / np.linalg.norm(text_embedding)
        image_norm = image_embedding / np.linalg.norm(image_embedding)

        # Project to same dimension if needed
        if len(text_norm) != len(image_norm):
            # Pad shorter one with zeros or truncate longer one
            max_dim = max(len(text_norm), len(image_norm))
            if len(text_norm) < max_dim:
                text_norm = np.pad(text_norm, (0, max_dim - len(text_norm)))
            if len(image_norm) < max_dim:
                image_norm = np.pad(image_norm, (0, max_dim - len(image_norm)))

        # Weighted combination
        hybrid = self.text_weight * text_norm + self.image_weight * image_norm

        # Normalize final embedding
        hybrid = hybrid / np.linalg.norm(hybrid)

        return hybrid

    def embed_movie(
        self,
        title: str,
        overview: Optional[str] = None,
        genres: Optional[list] = None,
        poster_path: Optional[Path] = None,
        **kwargs,
    ) -> np.ndarray:
        """
        Generate hybrid embedding for a movie.

        Args:
            title: Movie title.
            overview: Plot overview.
            genres: List of genres.
            poster_path: Path to poster image.
            **kwargs: Additional metadata for text embedding.

        Returns:
            Hybrid embedding vector.
        """
        # Generate text embedding
        text_embedding = self.text_embedder.embed_movie(
            title=title, overview=overview, genres=genres, **kwargs
        )

        # Generate image embedding if poster available
        if poster_path and Path(poster_path).exists():
            image_embedding = self.image_embedder.embed_image(poster_path)
        else:
            # Use zero vector if no poster
            image_embedding = np.zeros(self.image_embedder.embedding_dim)
            logger.debug(f"No poster for {title}, using zero image embedding")

        # Combine embeddings
        hybrid_embedding = self.combine_embeddings(text_embedding, image_embedding)

        return hybrid_embedding

    def embed_batch_hybrid(
        self,
        text_embeddings: np.ndarray,
        image_embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        Combine batches of text and image embeddings.

        Args:
            text_embeddings: Array of text embeddings (n, text_dim).
            image_embeddings: Array of image embeddings (n, image_dim).

        Returns:
            Array of hybrid embeddings (n, max_dim).
        """
        n_samples = text_embeddings.shape[0]
        hybrid_embeddings = []

        for i in range(n_samples):
            hybrid = self.combine_embeddings(text_embeddings[i], image_embeddings[i])
            hybrid_embeddings.append(hybrid)

        return np.array(hybrid_embeddings)

    def save_embeddings(self, embeddings: np.ndarray, save_path: Path) -> None:
        """
        Save embeddings to disk.

        Args:
            embeddings: Embedding array.
            save_path: Path to save file.
        """
        save_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(save_path, embeddings)
        logger.info(f"Saved hybrid embeddings to {save_path} (shape: {embeddings.shape})")

    def load_embeddings(self, load_path: Path) -> np.ndarray:
        """
        Load embeddings from disk.

        Args:
            load_path: Path to load file.

        Returns:
            Embedding array.
        """
        embeddings = np.load(load_path)
        logger.info(f"Loaded hybrid embeddings from {load_path} (shape: {embeddings.shape})")
        return embeddings


def get_hybrid_embedder(
    text_weight: Optional[float] = None,
    image_weight: Optional[float] = None,
    device: Optional[str] = None,
) -> HybridEmbedder:
    """
    Get configured hybrid embedder.

    Args:
        text_weight: Weight for text embeddings.
        image_weight: Weight for image embeddings.
        device: Device to use.

    Returns:
        Hybrid embedder instance.
    """
    return HybridEmbedder(text_weight=text_weight, image_weight=image_weight, device=device)
