"""Voyage AI embedding generation — replaces sentence-transformers for AWS deployment.

Uses the Voyage AI API (voyage-3, 1024-dim) for zero-cold-start, no local model.
Free tier: 50M tokens for new users.  https://www.voyageai.com
"""

from typing import List, Optional, Union

import numpy as np

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

VOYAGE_MODEL = "voyage-3"
EMBEDDING_DIM = 1024


class VoyageEmbedder:
    """Text embedder backed by the Voyage AI API."""

    def __init__(self, api_key: Optional[str] = None, model: str = VOYAGE_MODEL):
        try:
            import voyageai
        except ImportError as e:
            raise ImportError("voyageai package not installed. Run: pip install voyageai") from e

        settings = get_settings()
        key = api_key or settings.voyage_api_key
        if not key:
            raise ValueError("VOYAGE_API_KEY is required for AWS deployment. Set it in .env")

        self.model = model
        self.embedding_dim = EMBEDDING_DIM
        self.client = voyageai.Client(api_key=key)
        logger.info(f"VoyageEmbedder ready (model={self.model}, dim={self.embedding_dim})")

    def embed_text(
        self,
        text: Union[str, List[str]],
        input_type: str = "query",
    ) -> np.ndarray:
        """Embed text(s) via Voyage AI API.

        Args:
            text: Single string or list of strings.
            input_type: "query" for search queries, "document" for indexing.

        Returns:
            np.ndarray of shape (n, 1024).
        """
        if isinstance(text, str):
            text = [text]

        result = self.client.embed(text, model=self.model, input_type=input_type)
        return np.array(result.embeddings, dtype=np.float32)

    def embed_movie(
        self,
        title: str,
        overview: Optional[str] = None,
        genres: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        director: Optional[str] = None,
        cast: Optional[List[str]] = None,
    ) -> np.ndarray:
        """Build a rich movie document string and embed it (for indexing)."""
        parts = [title]
        if overview:
            parts.append(overview)
        if genres:
            parts.append(" ".join(genres))
        if tags:
            parts.append(" ".join(tags[:10]))
        if director:
            parts.append(f"Directed by {director}")
        if cast:
            parts.append(f"Starring {', '.join(cast[:5])}")

        doc = ". ".join(parts)
        return self.embed_text(doc, input_type="document")[0]

    def embed_batch(
        self,
        texts: List[str],
        input_type: str = "document",
        batch_size: int = 128,
    ) -> np.ndarray:
        """Embed a large list in batches (Voyage max is 128 texts per call)."""
        all_embeddings: List[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            result = self.client.embed(chunk, model=self.model, input_type=input_type)
            all_embeddings.append(np.array(result.embeddings, dtype=np.float32))
            logger.debug(f"Voyage batch {i//batch_size + 1}: {len(chunk)} texts embedded")

        return np.vstack(all_embeddings)


def get_voyage_embedder(api_key: Optional[str] = None) -> VoyageEmbedder:
    """Return a configured VoyageEmbedder."""
    return VoyageEmbedder(api_key=api_key)
