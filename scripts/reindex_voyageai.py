#!/usr/bin/env python3
"""
One-time offline script: re-index 62K movies into Qdrant Cloud using Voyage AI embeddings.

Run this ONCE locally before deploying to AWS:
    VOYAGE_API_KEY=<key> QDRANT_URL=<url> QDRANT_API_KEY=<key> python scripts/reindex_voyageai.py

Requirements: pip install voyageai qdrant-client pandas pyarrow tqdm
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def build_movie_text(row: pd.Series) -> str:
    """Combine movie metadata into a rich document string for indexing."""
    parts = [str(row.get("title", ""))]
    overview = row.get("overview", "")
    if overview and str(overview) != "nan":
        parts.append(str(overview))
    genres = row.get("genres", "")
    if genres and str(genres) != "nan":
        parts.append(str(genres))
    director = row.get("director", "")
    if director and str(director) != "nan":
        parts.append(f"Directed by {director}")
    cast = row.get("cast", "")
    if cast and str(cast) != "nan":
        cast_str = str(cast)
        parts.append(f"Starring {cast_str[:200]}")
    return ". ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Re-index movies into Qdrant using Voyage AI")
    parser.add_argument("--batch-size", type=int, default=128, help="Texts per Voyage API call (max 128)")
    parser.add_argument("--upsert-batch", type=int, default=500, help="Points per Qdrant upsert call")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for testing (default: all)")
    parser.add_argument("--collection", type=str, default="cinematch_movies", help="Qdrant collection name")
    parser.add_argument("--model", type=str, default="voyage-3", help="Voyage AI model")
    args = parser.parse_args()

    voyage_key = os.environ.get("VOYAGE_API_KEY")
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")

    if not voyage_key:
        sys.exit("ERROR: VOYAGE_API_KEY env var is required")
    if not qdrant_url or not qdrant_key:
        sys.exit("ERROR: QDRANT_URL and QDRANT_API_KEY env vars are required")

    import voyageai
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
    from tqdm import tqdm

    print(f"Loading movies from data/processed/movies_enriched.parquet ...")
    df = pd.read_parquet("data/processed/movies_enriched.parquet")
    if args.limit:
        df = df.head(args.limit)
    print(f"Loaded {len(df):,} movies")

    # Init clients
    vo = voyageai.Client(api_key=voyage_key)
    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=60)

    # Ensure collection exists with 1024-dim (voyage-3)
    collections = [c.name for c in qdrant.get_collections().collections]
    if args.collection not in collections:
        qdrant.create_collection(
            collection_name=args.collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection '{args.collection}'")
    else:
        print(f"Using existing Qdrant collection '{args.collection}'")

    # Build document texts
    print("Building document strings ...")
    texts = [build_movie_text(row) for _, row in df.iterrows()]

    # Embed in batches via Voyage AI
    print(f"Embedding {len(texts):,} movies with Voyage AI ({args.model}) ...")
    all_embeddings: list[np.ndarray] = []
    for i in tqdm(range(0, len(texts), args.batch_size), desc="Voyage batches"):
        chunk = texts[i : i + args.batch_size]
        result = vo.embed(chunk, model=args.model, input_type="document")
        all_embeddings.extend(result.embeddings)

    print(f"Embeddings ready: {len(all_embeddings)} vectors of dim {len(all_embeddings[0])}")

    # Upsert to Qdrant in batches
    print("Upserting to Qdrant Cloud ...")
    points = []
    for idx, (_, row) in enumerate(df.iterrows()):
        tmdb_id = str(row.get("tmdb_id", row.get("id", idx)))
        payload = {
            "title": str(row.get("title", "")),
            "overview": str(row.get("overview", ""))[:1000],
            "genres": str(row.get("genres", "")),
            "year": int(row.get("year", row.get("release_year", 0)) or 0),
            "vote_average": float(row.get("vote_average", 0.0) or 0.0),
            "vote_count": int(row.get("vote_count", 0) or 0),
            "original_language": str(row.get("original_language", "en")),
            "director": str(row.get("director", "")),
            "cast": str(row.get("cast", ""))[:500],
            "poster_path": str(row.get("poster_path", "")),
            "tmdb_id": tmdb_id,
        }
        points.append(PointStruct(id=idx + 1, vector=all_embeddings[idx], payload=payload))

        if len(points) >= args.upsert_batch:
            qdrant.upsert(collection_name=args.collection, points=points)
            points = []

    if points:
        qdrant.upsert(collection_name=args.collection, points=points)

    count = qdrant.count(collection_name=args.collection).count
    print(f"\n✅ Done! {count:,} points in Qdrant collection '{args.collection}'")


if __name__ == "__main__":
    main()
