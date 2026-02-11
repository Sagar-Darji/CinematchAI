"""Text embedding generation using sentence-transformers."""

from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from config.settings import get_settings
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TextEmbedder:
    """Text embedding generator using sentence-transformers."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 32,
    ):
        """
        Initialize text embedder.

        Args:
            model_name: Model name. If None, uses settings.
            device: Device to use (mps, cuda, cpu). If None, auto-detects.
            batch_size: Batch size for encoding.
        """
        settings = get_settings()
        self.model_name = model_name or settings.text_embedding_model
        self.batch_size = batch_size

        # Auto-detect device
        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"  # Apple Silicon
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

        self.device = device
        logger.info(f"Loading text embedding model: {self.model_name} on {self.device}")

        # Load model
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        logger.info(f"Text embedder ready (dimension: {self.embedding_dim})")

    def embed_text(self, text: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        Generate embeddings for text.

        Args:
            text: Single text or list of texts.
            normalize: Normalize embeddings to unit length.

        Returns:
            Embedding array of shape (n_texts, embedding_dim).
        """
        if isinstance(text, str):
            text = [text]

        logger.debug(f"Encoding {len(text)} texts")

        # Encode with batching
        embeddings = self.model.encode(
            text,
            batch_size=self.batch_size,
            show_progress_bar=len(text) > 100,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
        )

        return embeddings

    def embed_movie(
        self,
        title: str,
        overview: Optional[str] = None,
        genres: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        director: Optional[str] = None,
        cast: Optional[List[str]] = None,
    ) -> np.ndarray:
        """
        Generate embedding for a movie by combining its metadata.

        Args:
            title: Movie title.
            overview: Plot overview.
            genres: List of genres.
            tags: User-generated tags.
            director: Director name.
            cast: Cast members.

        Returns:
            Movie embedding vector.
        """
        # Combine all text information
        parts = [title]

        if overview:
            parts.append(overview)

        if genres:
            parts.append(" ".join(genres))

        if tags:
            # Limit to top 10 tags to avoid too much noise
            parts.append(" ".join(tags[:10]))

        if director:
            parts.append(f"Directed by {director}")

        if cast:
            # Include top 5 cast members
            parts.append(f"Starring {', '.join(cast[:5])}")

        # Combine with separator
        combined_text = ". ".join(parts)

        # Generate embedding
        embedding = self.embed_text(combined_text, normalize=True)

        return embedding[0]  # Return single vector

    def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of texts.
            batch_size: Batch size. If None, uses default.
            show_progress: Show progress bar.

        Returns:
            Embedding array of shape (n_texts, embedding_dim).
        """
        batch_size = batch_size or self.batch_size

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        return embeddings

    def save_embeddings(self, embeddings: np.ndarray, save_path: Path) -> None:
        """
        Save embeddings to disk.

        Args:
            embeddings: Embedding array.
            save_path: Path to save file.
        """
        save_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(save_path, embeddings)
        logger.info(f"Saved embeddings to {save_path} (shape: {embeddings.shape})")

    def load_embeddings(self, load_path: Path) -> np.ndarray:
        """
        Load embeddings from disk.

        Args:
            load_path: Path to load file.

        Returns:
            Embedding array.
        """
        embeddings = np.load(load_path)
        logger.info(f"Loaded embeddings from {load_path} (shape: {embeddings.shape})")
        return embeddings


def get_text_embedder(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> TextEmbedder:
    """
    Get configured text embedder.

    Args:
        model_name: Model name. If None, uses settings.
        device: Device to use. If None, auto-detects.

    Returns:
        Text embedder instance.
    """
    return TextEmbedder(model_name=model_name, device=device)
