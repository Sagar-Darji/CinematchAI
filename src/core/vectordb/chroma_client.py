"""Chroma vector database client."""

from pathlib import Path
from typing import Dict, List, Optional, Union

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ChromaClient:
    """Chroma vector database client for movie embeddings."""

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize Chroma client.

        Args:
            persist_directory: Directory for persistent storage. If None, uses settings.
            collection_name: Collection name. If None, uses settings.
        """
        settings = get_settings()
        self.persist_directory = persist_directory or settings.chroma_persist_dir
        self.collection_name = collection_name or settings.chroma_collection_movies

        # Create persist directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing Chroma client at {self.persist_directory}")

        # Initialize Chroma client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Get or create collection
        self.collection = None
        logger.info(f"Chroma client ready")

    def create_collection(
        self,
        collection_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Create a new collection.

        Args:
            collection_name: Collection name. If None, uses default.
            metadata: Collection metadata.
        """
        collection_name = collection_name or self.collection_name

        # Default metadata for HNSW indexing
        default_metadata = {
            "hnsw:space": "cosine",  # cosine distance for similarity
            "hnsw:construction_ef": 200,  # Higher = better quality, slower indexing
            "hnsw:M": 16,  # Number of connections per layer
        }

        if metadata:
            default_metadata.update(metadata)

        logger.info(f"Creating collection: {collection_name}")

        try:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata=default_metadata,
            )
            logger.info(f"Collection '{collection_name}' created successfully")
        except Exception as e:
            logger.warning(f"Collection may already exist: {e}")
            self.collection = self.client.get_collection(name=collection_name)

    def get_collection(self, collection_name: Optional[str] = None):
        """
        Get existing collection.

        Args:
            collection_name: Collection name. If None, uses default.

        Returns:
            Chroma collection.
        """
        collection_name = collection_name or self.collection_name
        self.collection = self.client.get_collection(name=collection_name)
        logger.info(f"Retrieved collection: {collection_name}")
        return self.collection

    def add_embeddings(
        self,
        embeddings: np.ndarray,
        ids: List[str],
        metadatas: Optional[List[Dict]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """
        Add embeddings to collection.

        Args:
            embeddings: Embedding vectors (n_samples, embedding_dim).
            ids: Unique IDs for each embedding.
            metadatas: Metadata dictionaries for each embedding.
            documents: Optional text documents for each embedding.
        """
        if self.collection is None:
            raise ValueError("No collection selected. Call create_collection() or get_collection() first.")

        # Convert numpy array to list
        embeddings_list = embeddings.tolist()

        logger.info(f"Adding {len(ids)} embeddings to collection")

        # Add to collection
        self.collection.add(
            embeddings=embeddings_list,
            ids=ids,
            metadatas=metadatas,
            documents=documents,
        )

        logger.info(f"✓ Added {len(ids)} embeddings successfully")

    def query(
        self,
        query_embedding: Union[np.ndarray, List[float]],
        n_results: int = 10,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None,
    ) -> Dict:
        """
        Query collection for similar embeddings.

        Args:
            query_embedding: Query embedding vector.
            n_results: Number of results to return.
            where: Metadata filter (e.g., {"genre": "Action"}).
            where_document: Document content filter.

        Returns:
            Query results with ids, distances, metadatas, documents.
        """
        if self.collection is None:
            raise ValueError("No collection selected.")

        # Convert numpy to list if needed
        if isinstance(query_embedding, np.ndarray):
            query_embedding = query_embedding.tolist()

        # Ensure it's a 2D list (batch of 1)
        if not isinstance(query_embedding[0], list):
            query_embedding = [query_embedding]

        logger.debug(f"Querying for {n_results} similar items")

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where,
            where_document=where_document,
        )

        return results

    def similarity_search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Search for k most similar items.

        Args:
            query_embedding: Query embedding vector.
            k: Number of results.
            filter_dict: Metadata filters.

        Returns:
            List of result dictionaries with id, distance, metadata.
        """
        results = self.query(
            query_embedding=query_embedding,
            n_results=k,
            where=filter_dict,
        )

        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "id": results["ids"][0][i],
                "distance": results["distances"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else None,
                "document": results["documents"][0][i] if results["documents"] else None,
            })

        return formatted_results

    def delete_collection(self, collection_name: Optional[str] = None) -> None:
        """
        Delete a collection.

        Args:
            collection_name: Collection name. If None, uses default.
        """
        collection_name = collection_name or self.collection_name
        logger.warning(f"Deleting collection: {collection_name}")
        self.client.delete_collection(name=collection_name)
        self.collection = None

    def count(self) -> int:
        """
        Get number of items in collection.

        Returns:
            Number of items.
        """
        if self.collection is None:
            return 0
        return self.collection.count()

    def get_by_ids(self, ids: List[str]) -> Dict:
        """
        Get items by IDs.

        Args:
            ids: List of IDs to retrieve.

        Returns:
            Retrieved items with embeddings, metadatas, documents.
        """
        if self.collection is None:
            raise ValueError("No collection selected.")

        return self.collection.get(ids=ids)


def get_chroma_client(
    persist_directory: Optional[Path] = None,
    collection_name: Optional[str] = None,
) -> ChromaClient:
    """
    Get configured Chroma client.

    Args:
        persist_directory: Directory for persistent storage.
        collection_name: Collection name.

    Returns:
        Chroma client instance.
    """
    return ChromaClient(persist_directory=persist_directory, collection_name=collection_name)
