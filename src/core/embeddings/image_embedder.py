"""Image embedding generation using CLIP.

Supports local file paths, URLs (e.g. TMDB CDN poster URLs), and PIL Images.
"""

import io
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import requests as _http
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ImageEmbedder:
    """Image embedding generator using CLIP."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 16,
    ):
        """
        Initialize image embedder.

        Args:
            model_name: CLIP model name. If None, uses settings.
            device: Device to use (mps, cuda, cpu). If None, auto-detects.
            batch_size: Batch size for encoding.
        """
        settings = get_settings()
        self.model_name = model_name or settings.image_embedding_model
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
        logger.info(f"Loading CLIP model: {self.model_name} on {self.device}")

        # Load CLIP model and processor
        self.model = CLIPModel.from_pretrained(self.model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(self.model_name)

        # Set to eval mode
        self.model.eval()

        # Get embedding dimension
        self.embedding_dim = self.model.config.vision_config.hidden_size

        logger.info(f"Image embedder ready (dimension: {self.embedding_dim})")

    @staticmethod
    def _load_image(source: Union[str, Path, Image.Image]) -> Image.Image:
        """Load a PIL Image from a file path, HTTP/HTTPS URL, or existing PIL Image."""
        if isinstance(source, Image.Image):
            return source.convert("RGB")
        src_str = str(source)
        if src_str.startswith("http://") or src_str.startswith("https://"):
            resp = _http.get(src_str, timeout=5)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        return Image.open(source).convert("RGB")

    @torch.no_grad()
    def embed_image(
        self, image: Union[str, Path, Image.Image], normalize: bool = True
    ) -> np.ndarray:
        """
        Generate embedding for a single image.

        Args:
            image: File path, HTTPS URL, or PIL Image.
            normalize: Normalize embedding to unit length.

        Returns:
            Image embedding vector.
        """
        if not isinstance(image, Image.Image):
            image = self._load_image(image)

        # Process image
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        # Get image features
        image_features = self.model.get_image_features(**inputs)

        # Convert to numpy
        embedding = image_features.cpu().numpy()[0]

        # Normalize if requested
        if normalize:
            embedding = embedding / np.linalg.norm(embedding)

        return embedding

    @torch.no_grad()
    def embed_batch(
        self,
        images: List[Union[str, Path, Image.Image]],
        batch_size: Optional[int] = None,
        show_progress: bool = True,
        normalize: bool = True,
    ) -> np.ndarray:
        """
        Generate embeddings for a batch of images.

        Args:
            images: List of image paths or PIL Images.
            batch_size: Batch size. If None, uses default.
            show_progress: Show progress bar.
            normalize: Normalize embeddings.

        Returns:
            Embedding array of shape (n_images, embedding_dim).
        """
        batch_size = batch_size or self.batch_size
        embeddings = []

        # Process in batches
        for i in range(0, len(images), batch_size):
            batch = images[i : i + batch_size]

            # Load images — supports paths, URLs, and PIL Images
            batch_images = []
            for img in batch:
                try:
                    batch_images.append(self._load_image(img))
                except Exception as e:
                    logger.warning(f"Failed to load image {img}: {e}")
                    batch_images.append(Image.new("RGB", (224, 224), color="black"))

            # Process batch
            inputs = self.processor(images=batch_images, return_tensors="pt").to(self.device)

            # Get image features
            batch_features = self.model.get_image_features(**inputs)

            # Convert to numpy
            batch_embeddings = batch_features.cpu().numpy()

            embeddings.append(batch_embeddings)

            if show_progress and i % 100 == 0:
                logger.info(f"Processed {i}/{len(images)} images")

        # Concatenate all batches
        embeddings = np.concatenate(embeddings, axis=0)

        # Normalize if requested
        if normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            embeddings = embeddings / norms

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


def get_image_embedder(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> ImageEmbedder:
    """
    Get configured image embedder.

    Args:
        model_name: Model name. If None, uses settings.
        device: Device to use. If None, auto-detects.

    Returns:
        Image embedder instance.
    """
    return ImageEmbedder(model_name=model_name, device=device)
