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

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_movies_from_chroma_sqlite(db_path: str, limit: int = None):
    """Extract all 108K movies + metadata from the existing ChromaDB SQLite.
    Uses chroma:document (the pre-built text already used for embeddings) directly.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)

    # Pull every embedding row + all its metadata key-values in one query
    query = """
        SELECT
            e.id AS row_id,
            MAX(CASE WHEN m.key = 'chroma:document' THEN m.string_value END) AS document,
            MAX(CASE WHEN m.key = 'title'            THEN m.string_value END) AS title,
            MAX(CASE WHEN m.key = 'overview'         THEN m.string_value END) AS overview,
            MAX(CASE WHEN m.key = 'genres'           THEN m.string_value END) AS genres,
            MAX(CASE WHEN m.key = 'director'         THEN m.string_value END) AS director,
            MAX(CASE WHEN m.key = 'cast'             THEN m.string_value END) AS cast,
            MAX(CASE WHEN m.key = 'poster_path'      THEN m.string_value END) AS poster_path,
            MAX(CASE WHEN m.key = 'original_language' THEN m.string_value END) AS original_language,
            MAX(CASE WHEN m.key = 'release_date'     THEN m.string_value END) AS release_date,
            MAX(CASE WHEN m.key = 'movieId'          THEN m.string_value END) AS movie_id,
            MAX(CASE WHEN m.key = 'vote_average'     THEN m.string_value END) AS vote_average,
            MAX(CASE WHEN m.key = 'vote_count'       THEN m.string_value END) AS vote_count
        FROM embeddings e
        LEFT JOIN embedding_metadata m ON e.id = m.id
        GROUP BY e.id
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = conn.execute(query).fetchall()
    conn.close()
    print(f"Loaded {len(rows):,} movies from ChromaDB SQLite")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Re-index 108K movies into Qdrant using Voyage AI")
    parser.add_argument("--batch-size", type=int, default=128, help="Texts per Voyage API call (max 128)")
    parser.add_argument("--upsert-batch", type=int, default=500, help="Points per Qdrant upsert call")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for testing (default: all)")
    parser.add_argument("--collection", type=str, default="cinematch_movies", help="Qdrant collection name")
    parser.add_argument("--model", type=str, default="voyage-3", help="Voyage AI model")
    parser.add_argument("--chroma-db", type=str, default="data/vectordb/chroma.sqlite3", help="Path to ChromaDB SQLite")
    parser.add_argument("--resume-from", type=int, default=0, help="Skip first N movies (resume interrupted run)")
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the Qdrant collection before indexing")
    parser.add_argument("--rpm", type=int, default=3, help="Voyage AI rate limit in requests/min (free=3, paid=300)")
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

    # Load movies from existing ChromaDB SQLite (all 108K with metadata)
    movies = load_movies_from_chroma_sqlite(args.chroma_db, limit=args.limit)

    if args.resume_from > 0:
        movies = movies[args.resume_from:]
        print(f"Resuming from movie #{args.resume_from}, {len(movies):,} remaining")

    # Init clients
    vo = voyageai.Client(api_key=voyage_key)
    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=60)

    # Ensure collection exists with 1024-dim (voyage-3); recreate if --recreate passed
    collections = [c.name for c in qdrant.get_collections().collections]
    if args.collection in collections and args.recreate:
        qdrant.delete_collection(args.collection)
        print(f"Deleted existing Qdrant collection '{args.collection}'")
        collections = []
    if args.collection not in collections:
        qdrant.create_collection(
            collection_name=args.collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection '{args.collection}'")
    else:
        print(f"Using existing Qdrant collection '{args.collection}'")

    # Extract document texts (pre-built in ChromaDB, column index 1)
    texts = [row[1] or row[2] or "unknown movie" for row in movies]  # document or title fallback

    # Embed + upsert in lockstep batches to avoid storing all 108K embeddings in RAM
    print(f"Embedding & upserting {len(texts):,} movies (batch={args.batch_size}, rpm={args.rpm}) ...")
    # Proactive rate limiting: ensure minimum gap between API calls
    min_gap = 60.0 / args.rpm  # seconds between calls (e.g. 20s at 3 RPM)
    point_id = args.resume_from  # global, ever-incrementing — never resets
    points = []
    last_call_at = 0.0

    import time
    for i in tqdm(range(0, len(texts), args.batch_size), desc="Progress"):
        chunk_texts = texts[i : i + args.batch_size]
        chunk_rows  = movies[i : i + args.batch_size]

        # Proactive rate limit: wait until min_gap has elapsed since last call
        elapsed = time.time() - last_call_at
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)

        # Retry loop with backoff for rate-limit errors
        result = None
        last_exc = None
        for attempt in range(8):
            try:
                last_call_at = time.time()
                result = vo.embed(chunk_texts, model=args.model, input_type="document")
                break
            except Exception as e:
                last_exc = e
                if "rate" in str(e).lower() or "429" in str(e):
                    wait = min_gap * (attempt + 2)  # progressive backoff
                    tqdm.write(f"Rate limit hit — waiting {wait:.0f}s (attempt {attempt+1}/8)")
                    time.sleep(wait)
                else:
                    raise
        if result is None:
            raise RuntimeError(f"All retry attempts exhausted at batch {i}. Last error: {last_exc}\n"
                               f"Resume with --resume-from {args.resume_from + i}")

        for row, emb in zip(chunk_rows, result.embeddings):
            point_id += 1  # unique ID for every movie
            row_id, doc, title, overview, genres, director, cast, poster_path, lang, release_date, movie_id, vote_avg, vote_cnt = row
            year = 0
            if release_date and len(str(release_date)) >= 4:
                try: year = int(str(release_date)[:4])
                except: pass

            payload = {
                "title":             str(title or ""),
                "overview":          str(overview or "")[:1000],
                "genres":            str(genres or ""),
                "year":              year,
                "vote_average":      float(vote_avg or 0),
                "vote_count":        int(vote_cnt or 0) if str(vote_cnt or "").isdigit() else 0,
                "original_language": str(lang or "en"),
                "director":          str(director or ""),
                "cast":              str(cast or "")[:500],
                "poster_path":       str(poster_path or ""),
                "movie_id":          str(movie_id or row_id),
            }
            points.append(PointStruct(id=point_id, vector=emb, payload=payload))

        if len(points) >= args.upsert_batch:
            qdrant.upsert(collection_name=args.collection, points=points)
            points = []

    if points:
        qdrant.upsert(collection_name=args.collection, points=points)

    count = qdrant.count(collection_name=args.collection).count
    print(f"\n✅ Done! {count:,} points in Qdrant collection '{args.collection}'")


if __name__ == "__main__":
    main()
