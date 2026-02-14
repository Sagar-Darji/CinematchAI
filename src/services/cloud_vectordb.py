"""Cloud Vector DB Service — Zilliz (primary) + Qdrant (backup) + ChromaDB (fallback).

Provides a unified search/upsert interface with automatic failover.
Writes are replicated to all available backends.
Reads try primary first, then fall through the chain.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CloudVectorDB:
    """Multi-backend cloud vector store with automatic failover.

    Fallback chain: Zilliz Cloud -> Qdrant Cloud -> Local ChromaDB
    """

    EMBEDDING_DIM = 768
    COLLECTION_NAME = settings.cloud_vectordb_collection

    def __init__(self):
        self.zilliz = self._init_zilliz()
        self.qdrant = self._init_qdrant()
        self.chroma = self._init_chroma()

    # ------------------------------------------------------------------ init
    def _init_zilliz(self):
        """Connect to Zilliz Cloud. Returns None if not configured."""
        if not settings.zilliz_uri or not settings.zilliz_token:
            logger.info("Zilliz Cloud not configured — skipping")
            return None
        try:
            from pymilvus import MilvusClient

            client = MilvusClient(
                uri=settings.zilliz_uri,
                token=settings.zilliz_token,
            )
            # Ensure collection exists
            self._ensure_zilliz_collection(client)
            logger.info("Zilliz Cloud connected")
            return client
        except Exception as e:
            logger.warning(f"Zilliz Cloud init failed: {e}")
            return None

    def _ensure_zilliz_collection(self, client):
        """Create the Zilliz collection if it doesn't exist."""
        from pymilvus import CollectionSchema, DataType, FieldSchema

        if client.has_collection(self.COLLECTION_NAME):
            return

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.EMBEDDING_DIM),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="overview", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="genres", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="year", dtype=DataType.INT64),
            FieldSchema(name="vote_average", dtype=DataType.FLOAT),
            FieldSchema(name="vote_count", dtype=DataType.INT64),
            FieldSchema(name="original_language", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="director", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="cast", dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name="poster_path", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="tmdb_id", dtype=DataType.VARCHAR, max_length=32),
        ]
        schema = CollectionSchema(fields=fields, description="CineMatch movies")

        client.create_collection(
            collection_name=self.COLLECTION_NAME,
            schema=schema,
        )
        # Create vector index
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )
        client.create_index(
            collection_name=self.COLLECTION_NAME,
            index_params=index_params,
        )
        logger.info(f"Created Zilliz collection '{self.COLLECTION_NAME}'")

    def _init_qdrant(self):
        """Connect to Qdrant Cloud. Returns None if not configured."""
        if not settings.qdrant_url or not settings.qdrant_api_key:
            logger.info("Qdrant Cloud not configured — skipping")
            return None
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=30,
            )
            # Ensure collection exists
            collections = [c.name for c in client.get_collections().collections]
            if self.COLLECTION_NAME not in collections:
                client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection '{self.COLLECTION_NAME}'")
            logger.info("Qdrant Cloud connected")
            return client
        except Exception as e:
            logger.warning(f"Qdrant Cloud init failed: {e}")
            return None

    def _init_chroma(self):
        """Get local ChromaDB client (always available)."""
        try:
            from src.core.vectordb.chroma_client import get_chroma_client

            client = get_chroma_client()
            try:
                client.get_collection(settings.chroma_collection_movies)
            except Exception:
                # Collection may not exist yet — create it so upserts work
                try:
                    client.create_collection(settings.chroma_collection_movies)
                except Exception:
                    pass
            return client
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e}")
            return None

    # ---------------------------------------------------------------- search
    def search(
        self,
        query_embedding: list,
        k: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search with automatic failover: Zilliz -> Qdrant -> ChromaDB.

        Returns list of dicts: [{id, score, payload}, ...]
        """
        # Normalize embedding
        emb = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        emb_list = emb.tolist()

        # Try Zilliz
        if self.zilliz:
            try:
                results = self._search_zilliz(emb_list, k, filters)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Zilliz search failed, trying Qdrant: {e}")

        # Try Qdrant
        if self.qdrant:
            try:
                results = self._search_qdrant(emb_list, k, filters)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Qdrant search failed, trying ChromaDB: {e}")

        # Fallback to ChromaDB
        if self.chroma:
            try:
                return self._search_chroma(emb_list, k, filters)
            except Exception as e:
                logger.error(f"ChromaDB search also failed: {e}")

        return []

    def _search_zilliz(self, embedding: list, k: int, filters: Optional[Dict]) -> List[Dict]:
        """Search Zilliz Cloud."""
        filter_expr = self._build_zilliz_filter(filters) if filters else ""
        results = self.zilliz.search(
            collection_name=self.COLLECTION_NAME,
            data=[embedding],
            limit=k,
            output_fields=["title", "overview", "genres", "year", "vote_average",
                           "vote_count", "original_language", "director", "cast",
                           "poster_path", "tmdb_id"],
            filter=filter_expr,
        )
        formatted = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                formatted.append({
                    "id": hit["id"],
                    "score": hit["distance"],
                    "payload": entity,
                })
        return formatted

    def _search_qdrant(self, embedding: list, k: int, filters: Optional[Dict]) -> List[Dict]:
        """Search Qdrant Cloud."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

        query_filter = None
        if filters:
            conditions = []
            if "original_language" in filters:
                conditions.append(
                    FieldCondition(
                        key="original_language",
                        match=MatchValue(value=filters["original_language"]),
                    )
                )
            if "year_min" in filters or "year_max" in filters:
                range_kwargs = {}
                if "year_min" in filters:
                    range_kwargs["gte"] = filters["year_min"]
                if "year_max" in filters:
                    range_kwargs["lte"] = filters["year_max"]
                conditions.append(
                    FieldCondition(key="year", range=Range(**range_kwargs))
                )
            if conditions:
                query_filter = Filter(must=conditions)

        results = self.qdrant.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=embedding,
            limit=k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in results
        ]

    def _search_chroma(self, embedding: list, k: int, filters: Optional[Dict]) -> List[Dict]:
        """Search local ChromaDB."""
        chroma_filter = None
        if filters:
            conditions = []
            if "original_language" in filters:
                conditions.append({"original_language": filters["original_language"]})
            if "year_min" in filters:
                conditions.append({"year": {"$gte": int(filters["year_min"])}})
            if "year_max" in filters:
                conditions.append({"year": {"$lte": int(filters["year_max"])}})
            if len(conditions) == 1:
                chroma_filter = conditions[0]
            elif len(conditions) > 1:
                chroma_filter = {"$and": conditions}

        results = self.chroma.similarity_search(
            query_embedding=embedding,
            k=k,
            filter_dict=chroma_filter,
        )
        return [
            {
                "id": r["id"],
                "score": 1.0 - r.get("distance", 0.0),  # Chroma returns distance, convert to similarity
                "payload": r.get("metadata", {}),
            }
            for r in results
        ]

    @staticmethod
    def _build_zilliz_filter(filters: Dict) -> str:
        """Build Zilliz/Milvus filter expression string."""
        parts = []
        if "original_language" in filters:
            lang = filters["original_language"]
            parts.append(f'original_language == "{lang}"')
        if "year_min" in filters:
            parts.append(f"year >= {int(filters['year_min'])}")
        if "year_max" in filters:
            parts.append(f"year <= {int(filters['year_max'])}")
        return " and ".join(parts)

    # --------------------------------------------------------------- upsert
    def upsert_movies(
        self,
        movies: List[Dict[str, Any]],
        embeddings: List[list],
    ) -> Dict[str, int]:
        """Write to ALL available backends (best-effort replication).

        Args:
            movies: List of movie dicts with keys: id, title, overview, genres,
                    year, vote_average, vote_count, original_language, director,
                    cast, poster_path, tmdb_id.
            embeddings: Corresponding embedding vectors.

        Returns:
            Dict of counts written per backend.
        """
        counts = {}

        if self.zilliz:
            try:
                n = self._upsert_zilliz(movies, embeddings)
                counts["zilliz"] = n
            except Exception as e:
                logger.warning(f"Zilliz upsert failed: {e}")

        if self.qdrant:
            try:
                n = self._upsert_qdrant(movies, embeddings)
                counts["qdrant"] = n
            except Exception as e:
                logger.warning(f"Qdrant upsert failed: {e}")

        if self.chroma:
            try:
                n = self._upsert_chroma(movies, embeddings)
                counts["chroma"] = n
            except Exception as e:
                logger.warning(f"ChromaDB upsert failed: {e}")

        total = sum(counts.values())
        if total > 0:
            logger.info(f"Upserted {len(movies)} movies → {counts}")
        return counts

    def _upsert_zilliz(self, movies: List[Dict], embeddings: List[list]) -> int:
        """Upsert to Zilliz Cloud."""
        data = []
        for movie, emb in zip(movies, embeddings):
            row = {
                "id": str(movie.get("tmdb_id", movie.get("id", ""))),
                "embedding": emb,
                "title": (movie.get("title", "") or "")[:512],
                "overview": (movie.get("overview", "") or "")[:4096],
                "genres": (movie.get("genres", "") or "")[:512],
                "year": int(movie.get("year", 0) or 0),
                "vote_average": float(movie.get("vote_average", 0) or 0),
                "vote_count": int(movie.get("vote_count", 0) or 0),
                "original_language": (movie.get("original_language", "") or "")[:16],
                "director": (movie.get("director", "") or "")[:256],
                "cast": (movie.get("cast", "") or "")[:1024],
                "poster_path": (movie.get("poster_path", "") or "")[:256],
                "tmdb_id": str(movie.get("tmdb_id", movie.get("id", ""))),
            }
            data.append(row)

        self.zilliz.upsert(collection_name=self.COLLECTION_NAME, data=data)
        return len(data)

    def _upsert_qdrant(self, movies: List[Dict], embeddings: List[list]) -> int:
        """Upsert to Qdrant Cloud."""
        from qdrant_client.models import PointStruct

        points = []
        for movie, emb in zip(movies, embeddings):
            point_id = str(movie.get("tmdb_id", movie.get("id", "")))
            # Qdrant needs numeric or UUID ids — hash the string id
            import hashlib
            numeric_id = int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)
            payload = {
                "title": movie.get("title", ""),
                "overview": movie.get("overview", ""),
                "genres": movie.get("genres", ""),
                "year": int(movie.get("year", 0) or 0),
                "vote_average": float(movie.get("vote_average", 0) or 0),
                "vote_count": int(movie.get("vote_count", 0) or 0),
                "original_language": movie.get("original_language", ""),
                "director": movie.get("director", ""),
                "cast": movie.get("cast", ""),
                "poster_path": movie.get("poster_path", ""),
                "tmdb_id": str(movie.get("tmdb_id", movie.get("id", ""))),
            }
            points.append(PointStruct(id=numeric_id, vector=emb, payload=payload))

        self.qdrant.upsert(collection_name=self.COLLECTION_NAME, points=points)
        return len(points)

    def _upsert_chroma(self, movies: List[Dict], embeddings: List[list]) -> int:
        """Upsert to local ChromaDB."""
        if not self.chroma.collection:
            logger.warning("ChromaDB collection not initialized, skipping upsert")
            return 0

        ids = []
        metadatas = []
        documents = []

        for movie in movies:
            tmdb_id = str(movie.get("tmdb_id", movie.get("id", "")))
            ids.append(f"movie_{tmdb_id}")

            # Chroma metadata must be flat scalars
            meta = {
                "movieId": tmdb_id,
                "title": movie.get("title", "") or "",
                "overview": movie.get("overview", "") or "",
                "genres": movie.get("genres", "") or "",
                "year": int(movie.get("year", 0) or 0),
                "vote_average": float(movie.get("vote_average", 0) or 0),
                "vote_count": int(movie.get("vote_count", 0) or 0),
                "original_language": movie.get("original_language", "") or "",
                "director": movie.get("director", "") or "",
                "cast": movie.get("cast", "") or "",
                "poster_path": movie.get("poster_path", "") or "",
            }
            metadatas.append(meta)
            documents.append(f"{movie.get('title', '')}. {movie.get('overview', '')}")

        emb_array = np.array(embeddings, dtype=np.float32)
        self.chroma.collection.upsert(
            ids=ids,
            embeddings=emb_array.tolist(),
            metadatas=metadatas,
            documents=documents,
        )
        return len(ids)

    # --------------------------------------------------------------- counts
    def count(self) -> Dict[str, int]:
        """Return item counts from all backends."""
        counts = {}
        if self.zilliz:
            try:
                stats = self.zilliz.get_collection_stats(self.COLLECTION_NAME)
                counts["zilliz"] = stats.get("row_count", 0)
            except Exception:
                counts["zilliz"] = -1
        if self.qdrant:
            try:
                info = self.qdrant.get_collection(self.COLLECTION_NAME)
                counts["qdrant"] = info.points_count
            except Exception:
                counts["qdrant"] = -1
        if self.chroma:
            try:
                counts["chroma"] = self.chroma.count()
            except Exception:
                counts["chroma"] = -1
        return counts

    def is_available(self) -> Dict[str, bool]:
        """Health check for each backend."""
        status = {}
        if self.zilliz:
            try:
                self.zilliz.get_collection_stats(self.COLLECTION_NAME)
                status["zilliz"] = True
            except Exception:
                status["zilliz"] = False
        else:
            status["zilliz"] = False

        if self.qdrant:
            try:
                self.qdrant.get_collection(self.COLLECTION_NAME)
                status["qdrant"] = True
            except Exception:
                status["qdrant"] = False
        else:
            status["qdrant"] = False

        if self.chroma:
            try:
                self.chroma.count()
                status["chroma"] = True
            except Exception:
                status["chroma"] = False
        else:
            status["chroma"] = False

        return status

    # --------------------------------------------------------------- delete
    def delete_movies(self, tmdb_ids: List[str]) -> Dict[str, int]:
        """Delete movies from ALL available backends (for rotation).

        Args:
            tmdb_ids: List of TMDB ID strings to delete.

        Returns:
            Dict of counts deleted per backend.
        """
        if not tmdb_ids:
            return {}

        counts = {}

        # Zilliz: delete by primary key (id field = tmdb_id)
        if self.zilliz:
            try:
                id_filter = "id in [" + ",".join(f'"{tid}"' for tid in tmdb_ids) + "]"
                self.zilliz.delete(
                    collection_name=self.COLLECTION_NAME,
                    filter=id_filter,
                )
                counts["zilliz"] = len(tmdb_ids)
            except Exception as e:
                logger.warning(f"Zilliz delete failed: {e}")

        # Qdrant: delete by payload filter on tmdb_id
        if self.qdrant:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchAny
                self.qdrant.delete(
                    collection_name=self.COLLECTION_NAME,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="tmdb_id",
                                match=MatchAny(any=tmdb_ids),
                            )
                        ]
                    ),
                )
                counts["qdrant"] = len(tmdb_ids)
            except Exception as e:
                logger.warning(f"Qdrant delete failed: {e}")

        # ChromaDB: delete by chroma ids (movie_{tmdb_id})
        if self.chroma and self.chroma.collection:
            try:
                chroma_ids = [f"movie_{tid}" for tid in tmdb_ids]
                self.chroma.collection.delete(ids=chroma_ids)
                counts["chroma"] = len(tmdb_ids)
            except Exception as e:
                logger.warning(f"ChromaDB delete failed: {e}")

        if counts:
            logger.info(f"Deleted {len(tmdb_ids)} movies from backends: {counts}")
        return counts

    def get_indexed_ids(self) -> Set[str]:
        """Get all indexed TMDB IDs from the primary available backend."""
        # Try Zilliz first
        if self.zilliz:
            try:
                results = self.zilliz.query(
                    collection_name=self.COLLECTION_NAME,
                    filter="",
                    output_fields=["tmdb_id"],
                    limit=100000,
                )
                return {str(r["tmdb_id"]) for r in results if r.get("tmdb_id")}
            except Exception as e:
                logger.warning(f"Failed to get indexed IDs from Zilliz: {e}")

        # Try Qdrant
        if self.qdrant:
            try:
                ids = set()
                offset = None
                while True:
                    points, next_offset = self.qdrant.scroll(
                        collection_name=self.COLLECTION_NAME,
                        limit=1000,
                        offset=offset,
                        with_payload=True,
                    )
                    for p in points:
                        tmdb_id = p.payload.get("tmdb_id") if p.payload else None
                        if tmdb_id:
                            ids.add(str(tmdb_id))
                    if next_offset is None or not points:
                        break
                    offset = next_offset
                return ids
            except Exception as e:
                logger.warning(f"Failed to get indexed IDs from Qdrant: {e}")

        # Fallback to ChromaDB
        if self.chroma and self.chroma.collection:
            try:
                all_data = self.chroma.collection.get(include=[])
                return {
                    _id.replace("movie_", "")
                    for _id in (all_data.get("ids", []) or [])
                }
            except Exception as e:
                logger.warning(f"Failed to get indexed IDs from ChromaDB: {e}")

        return set()


# Singleton
_cloud_vectordb: Optional[CloudVectorDB] = None


def get_cloud_vectordb() -> CloudVectorDB:
    """Get singleton CloudVectorDB instance."""
    global _cloud_vectordb
    if _cloud_vectordb is None:
        _cloud_vectordb = CloudVectorDB()
    return _cloud_vectordb
