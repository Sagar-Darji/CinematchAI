#!/usr/bin/env python3
"""
Fetch full TMDB dataset and index into Qdrant.

Steps:
  1. Download TMDB daily export (all movie IDs + popularity)
  2. Sort by popularity desc, take top N (default 600K — fits 4 GB Qdrant free)
  3. Skip IDs already in Qdrant
  4. Fetch movie details from TMDB API concurrently (40 req/s)
  5. Embed with Voyage AI (300 RPM)
  6. Upsert into Qdrant (resumable via local SQLite checkpoint)

Usage:
    set -a && source .env && set +a
    venv/bin/python3 scripts/fetch_full_tmdb.py

Env vars required:
    TMDB_API_KEY, VOYAGE_API_KEY, QDRANT_URL, QDRANT_API_KEY

Options:
    --max-movies     Max movies to index (default 600000)
    --tmdb-workers   Concurrent TMDB API workers (default 30)
    --rpm            Voyage AI RPM (default 300)
    --batch-size     Voyage AI embed batch size (default 128)
    --min-popularity Min popularity threshold (default 0.5)
    --checkpoint     Path to SQLite checkpoint DB (default /tmp/tmdb_checkpoint.db)
    --skip-fetch     Skip TMDB API fetch, use checkpoint data only
"""

import argparse
import asyncio
import gzip
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlretrieve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Checkpoint DB ─────────────────────────────────────────────────────────────

def init_checkpoint(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            tmdb_id     INTEGER PRIMARY KEY,
            title       TEXT,
            overview    TEXT,
            genres      TEXT,
            director    TEXT,
            "cast"      TEXT,
            poster_path TEXT,
            lang        TEXT,
            release_date TEXT,
            vote_average REAL,
            vote_count  INTEGER,
            popularity  REAL,
            status      TEXT DEFAULT 'pending'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON movies(status)")
    conn.commit()
    return conn


def build_embed_text(row: dict) -> str:
    parts = [row.get("title", "")]
    if row.get("overview"):
        parts.append(row["overview"][:400])
    if row.get("genres"):
        parts.append("Genres: " + row["genres"])
    if row.get("director"):
        parts.append("Director: " + row["director"])
    if row.get("cast"):
        parts.append("Cast: " + row["cast"][:200])
    yr = row.get("release_date", "")[:4]
    if yr:
        parts.append(f"Year: {yr}")
    return " | ".join(filter(None, parts))[:1000]


# ── TMDB fetch ────────────────────────────────────────────────────────────────

async def fetch_movie_detail(session, tmdb_id: int, api_key: str, semaphore: asyncio.Semaphore):
    import aiohttp
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}&append_to_response=credits&language=en-US"
    async with semaphore:
        for attempt in range(4):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    if resp.status == 404:
                        return None
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    genres = ", ".join(g["name"] for g in data.get("genres", []))
                    credits = data.get("credits", {})
                    director = next(
                        (c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"), ""
                    )
                    cast = ", ".join(
                        c["name"] for c in credits.get("cast", [])[:5]
                    )
                    return {
                        "tmdb_id": tmdb_id,
                        "title": data.get("title", ""),
                        "overview": (data.get("overview") or "")[:800],
                        "genres": genres,
                        "director": director,
                        "cast": cast,
                        "poster_path": data.get("poster_path", ""),
                        "lang": data.get("original_language", "en"),
                        "release_date": data.get("release_date", ""),
                        "vote_average": float(data.get("vote_average") or 0),
                        "vote_count": int(data.get("vote_count") or 0),
                        "popularity": float(data.get("popularity") or 0),
                    }
            except Exception:
                await asyncio.sleep(1)
    return None


async def fetch_all_details(ids, api_key: str, conn: sqlite3.Connection, workers: int = 30):
    """Fetch TMDB details for all IDs, saving to checkpoint DB."""
    import aiohttp
    semaphore = asyncio.Semaphore(workers)
    total = len(ids)
    done = 0
    start = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_movie_detail(session, mid, api_key, semaphore) for mid in ids]
        batch_size = 500
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            results = await asyncio.gather(*batch_tasks)
            rows = [r for r in results if r]
            if rows:
                conn.executemany("""
                    INSERT OR REPLACE INTO movies
                        (tmdb_id, title, overview, genres, director, "cast", poster_path,
                         lang, release_date, vote_average, vote_count, popularity, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'fetched')
                """, [(r["tmdb_id"], r["title"], r["overview"], r["genres"], r["director"],
                       r["cast"], r["poster_path"], r["lang"], r["release_date"],
                       r["vote_average"], r["vote_count"], r["popularity"]) for r in rows])
                conn.commit()
            done += len(batch_tasks)
            elapsed = time.time() - start
            rate = done / elapsed
            eta = (total - done) / rate if rate > 0 else 0
            print(f"\rFetching: {done:,}/{total:,}  ({done/total*100:.1f}%)  "
                  f"{rate:.0f}/s  ETA {eta/60:.0f}m   ", end="", flush=True)
    print()


# ── Embed + upsert ────────────────────────────────────────────────────────────

def embed_and_upsert(conn: sqlite3.Connection, args, qdrant, vo, collection: str):
    from qdrant_client.models import PointStruct
    from tqdm import tqdm

    # Fetch all 'fetched' rows with quality filter
    rows = conn.execute("""
        SELECT tmdb_id, title, overview, genres, director, "cast", poster_path,
               lang, release_date, vote_average, vote_count, popularity
        FROM movies
        WHERE status = 'fetched'
          AND title != ''
          AND (overview != '' OR vote_count > 20)
        ORDER BY popularity DESC
    """).fetchall()

    print(f"Embedding {len(rows):,} movies (batch={args.batch_size}, rpm={args.rpm}) ...")
    min_gap = 60.0 / args.rpm
    last_call = 0.0
    points = []
    point_id_offset = 200_000  # start above existing 108K IDs

    # Get existing Qdrant IDs to avoid duplicates
    print("Checking existing Qdrant points...")
    existing_ids = set()
    try:
        offset = None
        while True:
            result = qdrant.scroll(
                collection_name=collection,
                limit=1000,
                offset=offset,
                with_payload=["movie_id"],
                with_vectors=False,
            )
            for pt in result[0]:
                mid = pt.payload.get("movie_id") or pt.payload.get("tmdb_id")
                if mid:
                    existing_ids.add(str(mid))
            offset = result[1]
            if offset is None:
                break
        print(f"Found {len(existing_ids):,} already indexed")
    except Exception as e:
        print(f"Warning: could not check existing IDs: {e}")

    # Filter rows not yet indexed
    new_rows = [r for r in rows if str(r[0]) not in existing_ids]
    print(f"New movies to index: {len(new_rows):,}")

    texts = [build_embed_text({
        "title": r[1], "overview": r[2], "genres": r[3], "director": r[4],
        "cast": r[5], "release_date": r[8],
    }) for r in new_rows]

    upserted = 0
    for i in tqdm(range(0, len(texts), args.batch_size), desc="Embedding"):
        chunk_texts = texts[i:i + args.batch_size]
        chunk_rows = new_rows[i:i + args.batch_size]

        # Rate limiting
        elapsed = time.time() - last_call
        if elapsed < min_gap:
            time.sleep(min_gap - elapsed)

        result = None
        last_exc = None
        for attempt in range(8):
            try:
                last_call = time.time()
                result = vo.embed(chunk_texts, model=args.model, input_type="document")
                break
            except Exception as e:
                last_exc = e
                if "rate" in str(e).lower() or "429" in str(e):
                    wait = min_gap * (attempt + 2)
                    tqdm.write(f"Rate limit — waiting {wait:.0f}s")
                    time.sleep(wait)
                else:
                    raise
        if result is None:
            raise RuntimeError(f"Embed failed at batch {i}: {last_exc}")

        for row, emb in zip(chunk_rows, result.embeddings):
            tmdb_id, title, overview, genres, director, cast, poster_path, lang, release_date, vote_avg, vote_cnt, popularity = row
            year = 0
            if release_date and len(str(release_date)) >= 4:
                try: year = int(str(release_date)[:4])
                except: pass
            point_id_offset += 1
            points.append(PointStruct(
                id=point_id_offset,
                vector=emb,
                payload={
                    "tmdb_id": tmdb_id,
                    "movie_id": str(tmdb_id),
                    "title": title or "",
                    "overview": (overview or "")[:800],
                    "genres": genres or "",
                    "year": year,
                    "vote_average": float(vote_avg or 0),
                    "vote_count": int(vote_cnt or 0),
                    "original_language": lang or "en",
                    "director": director or "",
                    "cast": (cast or "")[:400],
                    "poster_path": poster_path or "",
                    "popularity": float(popularity or 0),
                },
            ))

        if len(points) >= args.upsert_batch:
            qdrant.upsert(collection_name=collection, points=points)
            upserted += len(points)
            # Mark as indexed in checkpoint
            ids = [p.payload["tmdb_id"] for p in points]
            conn.executemany("UPDATE movies SET status='indexed' WHERE tmdb_id=?", [(i,) for i in ids])
            conn.commit()
            points = []

    if points:
        qdrant.upsert(collection_name=collection, points=points)
        upserted += len(points)
        ids = [p.payload["tmdb_id"] for p in points]
        conn.executemany("UPDATE movies SET status='indexed' WHERE tmdb_id=?", [(i,) for i in ids])
        conn.commit()

    return upserted


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Index full TMDB dataset into Qdrant")
    parser.add_argument("--max-movies",     type=int,   default=600_000, help="Max movies to fetch (default 600K)")
    parser.add_argument("--tmdb-workers",   type=int,   default=30,      help="Concurrent TMDB API workers")
    parser.add_argument("--rpm",            type=int,   default=300,     help="Voyage AI RPM")
    parser.add_argument("--batch-size",     type=int,   default=128,     help="Voyage AI batch size")
    parser.add_argument("--upsert-batch",   type=int,   default=500,     help="Qdrant upsert batch size")
    parser.add_argument("--model",          type=str,   default="voyage-3")
    parser.add_argument("--collection",     type=str,   default="cinematch_movies")
    parser.add_argument("--min-popularity", type=float, default=0.5,     help="Min popularity score")
    parser.add_argument("--checkpoint",     type=str,   default="/tmp/tmdb_checkpoint.db")
    parser.add_argument("--skip-fetch",     action="store_true", help="Skip TMDB API fetch (use checkpoint)")
    args = parser.parse_args()

    # Validate env
    tmdb_key   = os.environ.get("TMDB_API_KEY")
    voyage_key = os.environ.get("VOYAGE_API_KEY")
    qdrant_url = os.environ.get("QDRANT_URL")
    qdrant_key = os.environ.get("QDRANT_API_KEY")
    for name, val in [("TMDB_API_KEY", tmdb_key), ("VOYAGE_API_KEY", voyage_key),
                      ("QDRANT_URL", qdrant_url), ("QDRANT_API_KEY", qdrant_key)]:
        if not val:
            sys.exit(f"ERROR: {name} env var is required")

    import voyageai
    from qdrant_client import QdrantClient

    vo     = voyageai.Client(api_key=voyage_key)
    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_key, timeout=60)

    conn = init_checkpoint(args.checkpoint)

    # ── Step 1: download TMDB daily export ────────────────────────────────────
    already_fetched = conn.execute("SELECT COUNT(*) FROM movies WHERE status != 'pending'").fetchone()[0]

    if not args.skip_fetch and already_fetched == 0:
        d = datetime.now() - timedelta(days=1)
        export_url = f"https://files.tmdb.org/p/exports/movie_ids_{d.month:02d}_{d.day:02d}_{d.year}.json.gz"
        gz_path = "/tmp/tmdb_export.json.gz"
        print(f"Downloading TMDB export from {export_url} ...")
        urlretrieve(export_url, gz_path)

        print("Parsing export, sorting by popularity ...")
        entries = []
        with gzip.open(gz_path, "rt") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("adult", False):
                        continue
                    pop = float(obj.get("popularity", 0))
                    if pop >= args.min_popularity:
                        entries.append((obj["id"], pop))
                except Exception:
                    continue

        entries.sort(key=lambda x: x[1], reverse=True)
        entries = entries[:args.max_movies]
        print(f"Selected {len(entries):,} movies (popularity ≥ {args.min_popularity}, top {args.max_movies:,})")

        # Seed checkpoint with IDs
        conn.executemany("INSERT OR IGNORE INTO movies (tmdb_id, popularity) VALUES (?,?)", entries)
        conn.commit()
        print(f"Checkpoint seeded: {len(entries):,} IDs")

    # ── Step 2: fetch TMDB API details ────────────────────────────────────────
    if not args.skip_fetch:
        pending = conn.execute("SELECT tmdb_id FROM movies WHERE status = 'pending'").fetchall()
        pending_ids = [r[0] for r in pending]
        if pending_ids:
            print(f"\nFetching details for {len(pending_ids):,} movies from TMDB API ...")
            print(f"Estimated time: {len(pending_ids)/30/60:.0f} min at {args.tmdb_workers} workers")
            asyncio.run(fetch_all_details(pending_ids, tmdb_key, conn, args.tmdb_workers))
        else:
            print("All TMDB details already fetched (checkpoint complete)")

    # ── Step 3: embed + upsert ────────────────────────────────────────────────
    fetched_count = conn.execute("SELECT COUNT(*) FROM movies WHERE status = 'fetched'").fetchone()[0]
    indexed_count = conn.execute("SELECT COUNT(*) FROM movies WHERE status = 'indexed'").fetchone()[0]
    print(f"\nCheckpoint: {fetched_count:,} ready to embed, {indexed_count:,} already indexed")

    if fetched_count == 0 and indexed_count == 0:
        print("Nothing to embed. Run without --skip-fetch first.")
        return

    upserted = embed_and_upsert(conn, args, qdrant, vo, args.collection)

    final_count = qdrant.count(collection_name=args.collection).count
    print(f"\n✅ Done! Upserted {upserted:,} new movies → {final_count:,} total in Qdrant")


if __name__ == "__main__":
    main()
