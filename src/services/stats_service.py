"""Persisted user-stats service.

One row per user in `user_stats` holds everything the Profile page needs to
render its analytics: totals, breakdowns, top-N tables, four computed
insights, and an LLM-generated personality essay.

The compute job runs against the *full* ratings library (no [:200] cap), so
analytics are correct for power users with hundreds of imports. Triggered
from UserService.add_rating / record_feedback and at the end of the
Letterboxd import — the row is marked stale and a Lambda self-invoke fires
the recompute in the background; the read endpoint always returns whatever
is currently stored, so the UI is never blocked on the LLM call.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.db import get_db, register_pk
from src.utils.logging import get_logger

logger = get_logger(__name__)

_service: Optional["StatsService"] = None


def get_stats_service() -> "StatsService":
    global _service
    if _service is None:
        _service = StatsService()
    return _service


class StatsService:
    def __init__(self) -> None:
        self.db = get_db()
        self._ensure_schema()

    # ── Schema ────────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        try:
            with self.db.connect() as conn:
                # Use TRUE/FALSE (not 1/0) because Postgres rejects integer
                # defaults on BOOLEAN columns ("column 'stale' is of type
                # boolean but default expression is of type integer").
                # SQLite accepts TRUE/FALSE as boolean literals too.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_stats (
                        user_id TEXT PRIMARY KEY,
                        total_films INTEGER NOT NULL DEFAULT 0,
                        total_series INTEGER NOT NULL DEFAULT 0,
                        films_this_year INTEGER NOT NULL DEFAULT 0,
                        avg_rating REAL,
                        rating_histogram TEXT,
                        year_breakdown TEXT,
                        decade_breakdown TEXT,
                        top_genres TEXT,
                        top_directors TEXT,
                        top_actors TEXT,
                        total_runtime_minutes INTEGER,
                        foreign_pct REAL,
                        hidden_gem_pct REAL,
                        generosity_score REAL,
                        insights_json TEXT,
                        llm_personality TEXT,
                        computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        stale BOOLEAN DEFAULT TRUE
                    )
                    """
                )
            register_pk("user_stats", ["user_id"])
        except Exception as exc:
            logger.warning(f"user_stats schema init: {exc}")

    # ── Read / mark-stale / upsert ────────────────────────────────────────

    def get(self, user_id: str) -> Optional[dict]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_stats WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        # Decode JSON fields so callers see Python objects, not raw strings.
        for k in (
            "rating_histogram",
            "year_breakdown",
            "decade_breakdown",
            "top_genres",
            "top_directors",
            "top_actors",
            "insights_json",
        ):
            raw = d.get(k)
            if raw:
                try:
                    d[k] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    d[k] = None
        # SQLite represents booleans as 0/1.
        d["stale"] = bool(d.get("stale"))
        return d

    def is_stale(self, user_id: str) -> bool:
        row = self.get(user_id)
        if not row:
            return True
        return bool(row.get("stale", True))

    def mark_stale(self, user_id: str) -> None:
        try:
            with self.db.connect() as conn:
                # Use real booleans — Postgres rejects integer-typed values
                # on BOOLEAN columns.
                conn.execute(
                    "INSERT OR IGNORE INTO user_stats (user_id, stale) VALUES (?, ?)",
                    (user_id, True),
                )
                conn.execute(
                    "UPDATE user_stats SET stale = ? WHERE user_id = ?",
                    (True, user_id),
                )
        except Exception as exc:
            logger.warning(f"mark_stale failed for {user_id}: {exc}")

    def upsert(self, user_id: str, payload: Dict[str, Any]) -> None:
        """Replace the row with a fresh compute payload. Sets stale=0."""
        cols = (
            "user_id",
            "total_films",
            "total_series",
            "films_this_year",
            "avg_rating",
            "rating_histogram",
            "year_breakdown",
            "decade_breakdown",
            "top_genres",
            "top_directors",
            "top_actors",
            "total_runtime_minutes",
            "foreign_pct",
            "hidden_gem_pct",
            "generosity_score",
            "insights_json",
            "llm_personality",
            "computed_at",
            "stale",
        )
        values = (
            user_id,
            int(payload.get("total_films", 0)),
            int(payload.get("total_series", 0)),
            int(payload.get("films_this_year", 0)),
            payload.get("avg_rating"),
            json.dumps(payload.get("rating_histogram") or []),
            json.dumps(payload.get("year_breakdown") or {}),
            json.dumps(payload.get("decade_breakdown") or []),
            json.dumps(payload.get("top_genres") or []),
            json.dumps(payload.get("top_directors") or []),
            json.dumps(payload.get("top_actors") or []),
            payload.get("total_runtime_minutes"),
            payload.get("foreign_pct"),
            payload.get("hidden_gem_pct"),
            payload.get("generosity_score"),
            json.dumps(payload.get("insights") or []),
            payload.get("llm_personality"),
            datetime.now(timezone.utc).isoformat(),
            False,  # stale — real bool so Postgres BOOLEAN column accepts it
        )
        placeholders = ",".join(["?"] * len(cols))
        with self.db.connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO user_stats ({','.join(cols)}) VALUES ({placeholders})",
                values,
            )

    # ── Compute ───────────────────────────────────────────────────────────

    def compute(self, user_id: str) -> Dict[str, Any]:
        """Aggregate the user's full ratings library into a stats payload and
        persist it. Heavyweight — only call from the Lambda worker route.

        Returns the computed payload (also written to the DB).
        """
        from src.services.movie_service import get_movie_service
        from src.services.user_service import get_user_service

        t0 = time.time()
        ratings = get_user_service().get_user_ratings(user_id)
        if not ratings:
            payload = {
                "total_films": 0,
                "total_series": 0,
                "films_this_year": 0,
                "avg_rating": None,
                "rating_histogram": [],
                "year_breakdown": {},
                "decade_breakdown": [],
                "top_genres": [],
                "top_directors": [],
                "top_actors": [],
                "total_runtime_minutes": 0,
                "foreign_pct": 0.0,
                "hidden_gem_pct": 0.0,
                "generosity_score": 0.0,
                "insights": [],
                "llm_personality": None,
            }
            self.upsert(user_id, payload)
            return payload

        # Resolve movies in 200-row batches with parallel TMDB fetches per
        # batch. Batching keeps memory + Lambda-time bounded for users with
        # large libraries (5000+ ratings) and means a per-batch TMDB failure
        # doesn't wipe out the whole compute — surviving batches still feed
        # the aggregator. Cached on /tmp so subsequent runs are fast.
        ids = [int(r["movie_id"]) for r in ratings]
        batch_size = 200
        movies: List[Any] = [None] * len(ids)
        for start in range(0, len(ids), batch_size):
            end = min(start + batch_size, len(ids))
            chunk = ids[start:end]
            try:
                resolved = get_movie_service().get_media_auto_batch(chunk, max_workers=20)
                for i, m in enumerate(resolved):
                    movies[start + i] = m
                logger.info(
                    f"[stats] resolved batch {start}-{end} of {len(ids)} "
                    f"({sum(1 for m in resolved if m)}/{len(chunk)} hits)"
                )
            except Exception as exc:
                logger.warning(f"[stats] batch {start}-{end} failed entirely: {exc}")
                # Leave that batch as Nones — aggregator handles missing data.

        # Per-rating enrichment — keep ratings & movies aligned.
        enriched: List[dict] = []
        for r, m in zip(ratings, movies):
            md = getattr(m, "metadata", None) if m else None
            enriched.append({
                "rating": float(r["rating"]),
                "timestamp": r.get("timestamp"),
                "source": r.get("source") or "unknown",
                "title": getattr(md, "title", None),
                "year": getattr(md, "year", None),
                "media_type": getattr(md, "media_type", "movie") or "movie",
                "genres": getattr(md, "genres", []) or [],
                "director": getattr(md, "director", None),
                "cast": (getattr(md, "cast", None) or [])[:5],
                "runtime": getattr(md, "runtime", None),
                "original_language": getattr(md, "original_language", None),
                "vote_average": getattr(md, "vote_average", None),
                "vote_count": getattr(md, "vote_count", None),
            })

        payload = self._aggregate(enriched)
        payload["llm_personality"] = self._maybe_llm_personality(payload)
        self.upsert(user_id, payload)
        logger.info(
            f"Computed stats for {user_id}: {payload['total_films']} films, "
            f"{payload['total_series']} series, in {time.time() - t0:.1f}s"
        )
        return payload

    # ── Aggregation ───────────────────────────────────────────────────────

    @staticmethod
    def _aggregate(items: List[dict]) -> Dict[str, Any]:
        """Pure function — given enriched per-rating dicts, produce the full
        stats payload. Easy to unit-test.

        `items` may contain rows with `source == "implicit_feedback"` — those
        are 1-2★ likert reactions captured from the recommendation feed, not
        deliberate ratings. They still count toward "you watched this", so
        totals/runtime/genre+decade *breadth* include them, but they would
        skew avg_rating, the histogram, and the director/genre-lean insights
        (which assume a real star). We split once and use the right slice
        in the right place.
        """
        current_year = datetime.now(timezone.utc).year

        def _is_explicit(it: dict) -> bool:
            return it.get("source") != "implicit_feedback"

        explicit = [it for it in items if _is_explicit(it)]

        total_films = sum(1 for it in items if it["media_type"] == "movie")
        total_series = sum(1 for it in items if it["media_type"] == "tv")

        # Films watched this year — based on the rating timestamp (which now
        # reflects the original Letterboxd watch date thanks to PR 1).
        films_this_year = 0
        for it in items:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                if datetime.fromisoformat(ts.replace("Z", "+00:00")).year == current_year:
                    films_this_year += 1
            except Exception:
                continue

        # Histogram + avg are about *deliberate* stars only.
        ratings = [it["rating"] for it in explicit]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        # Histogram — half-star buckets.
        buckets = [round(0.5 * i, 1) for i in range(1, 11)]
        bucket_counts = Counter()
        for r in ratings:
            snapped = max(0.5, min(5.0, round(r * 2) / 2))
            bucket_counts[snapped] += 1
        rating_histogram = [{"rating": b, "count": bucket_counts.get(b, 0)} for b in buckets]

        # Year breakdown (when watched).
        year_counts: Counter = Counter()
        for it in items:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                year_counts[datetime.fromisoformat(ts.replace("Z", "+00:00")).year] += 1
            except Exception:
                continue
        year_breakdown = {str(k): v for k, v in sorted(year_counts.items())}

        # Decade breakdown (when produced).
        decade_counts: Counter = Counter()
        for it in items:
            y = it.get("year")
            if y is None:
                continue
            decade_counts[(int(y) // 10) * 10] += 1
        decade_breakdown = [
            {"decade": d, "label": f"{d}s", "count": c}
            for d, c in sorted(decade_counts.items())
        ]

        # Top-N tables. Genres/actors count breadth (use all items); directors
        # also surface avg user rating, so only deliberate ratings.
        genre_counts: Counter = Counter()
        actor_counts: Counter = Counter()
        for it in items:
            for g in it.get("genres") or []:
                genre_counts[g] += 1
            for actor in it.get("cast") or []:
                actor_counts[actor] += 1

        director_counts: Counter = Counter()
        director_rating_sum: Dict[str, float] = defaultdict(float)
        for it in explicit:
            d = it.get("director")
            if d:
                director_counts[d] += 1
                director_rating_sum[d] += it["rating"]

        top_genres = [{"name": g, "count": c} for g, c in genre_counts.most_common()]
        top_directors = [
            {
                "name": d,
                "count": c,
                "avg_rating": round(director_rating_sum[d] / c, 2) if c else None,
            }
            for d, c in director_counts.most_common(20)
        ]
        top_actors = [{"name": a, "count": c} for a, c in actor_counts.most_common(20)]

        total_runtime = sum(int(it["runtime"]) for it in items if it.get("runtime"))

        # Percentages over the whole resolved set.
        with_lang = [it for it in items if it.get("original_language")]
        foreign_pct = (
            round(
                100.0 * sum(1 for it in with_lang if it["original_language"] != "en") / len(with_lang),
                1,
            )
            if with_lang
            else 0.0
        )

        with_votes = [it for it in items if it.get("vote_count") is not None]
        hidden_gem_pct = (
            round(
                100.0 * sum(1 for it in with_votes if (it["vote_count"] or 0) < 100_000) / len(with_votes),
                1,
            )
            if with_votes
            else 0.0
        )

        # Generosity vs TMDB only makes sense over deliberate stars.
        with_tmdb = [it for it in explicit if it.get("vote_average") is not None]
        if with_tmdb:
            user_mean = sum(it["rating"] for it in with_tmdb) / len(with_tmdb)
            tmdb_mean = sum(it["vote_average"] / 2 for it in with_tmdb) / len(with_tmdb)
            generosity_score = round(user_mean - tmdb_mean, 2)
        else:
            generosity_score = 0.0

        # Genre lean — biggest delta in average rating between two top genres.
        # Only consider genres with >= 5 ratings to avoid noise, and only
        # deliberate ratings (1-2★ likerts would pull every genre toward 1.5).
        genre_avg: Dict[str, float] = {}
        genre_n: Counter = Counter()
        for it in explicit:
            for g in it.get("genres") or []:
                genre_avg[g] = genre_avg.get(g, 0.0) + it["rating"]
                genre_n[g] += 1
        genre_means = sorted(
            [(g, genre_avg[g] / genre_n[g], genre_n[g]) for g in genre_avg if genre_n[g] >= 5],
            key=lambda x: x[1],
            reverse=True,
        )
        genre_lean = None
        if len(genre_means) >= 2:
            top_g, top_mean, _ = genre_means[0]
            bot_g, bot_mean, _ = genre_means[-1]
            delta = round(top_mean - bot_mean, 2)
            if delta >= 0.3:  # only surface meaningful deltas
                genre_lean = {
                    "type": "genre_lean",
                    "title": "Genre lean",
                    "value": f"{top_g} > {bot_g}",
                    "context": f"+{delta}★ on {top_g} vs {bot_g}",
                }

        insights: List[Dict[str, Any]] = []
        if top_directors:
            d = top_directors[0]
            if d["count"] >= 3:
                insights.append({
                    "type": "director_loyalty",
                    "title": "Director loyalty",
                    "value": d["name"],
                    "context": f"{d['count']} films · avg {d['avg_rating']:.1f}★",
                })
        if decade_breakdown:
            top_decade = max(decade_breakdown, key=lambda d: d["count"])
            pct = round(100.0 * top_decade["count"] / len(items), 0)
            insights.append({
                "type": "decade_obsession",
                "title": "Decade obsession",
                "value": f"{top_decade['decade']}s",
                "context": f"{int(pct)}% of your library",
            })
        # Hidden gem detector — only show as an insight if non-trivial.
        if hidden_gem_pct >= 10:
            label = "Deep-cut watcher" if hidden_gem_pct >= 25 else "Some hidden gems"
            insights.append({
                "type": "hidden_gem",
                "title": "Hidden gem hunter",
                "value": f"{hidden_gem_pct}% of ratings",
                "context": f"{label} — films with <100K TMDB votes",
            })
        if genre_lean:
            insights.append(genre_lean)

        return {
            "total_films": total_films,
            "total_series": total_series,
            "films_this_year": films_this_year,
            "avg_rating": avg_rating,
            "rating_histogram": rating_histogram,
            "year_breakdown": year_breakdown,
            "decade_breakdown": decade_breakdown,
            "top_genres": top_genres,
            "top_directors": top_directors,
            "top_actors": top_actors,
            "total_runtime_minutes": total_runtime,
            "foreign_pct": foreign_pct,
            "hidden_gem_pct": hidden_gem_pct,
            "generosity_score": generosity_score,
            "insights": insights,
        }

    # ── LLM personality essay ─────────────────────────────────────────────

    @staticmethod
    def _maybe_llm_personality(payload: Dict[str, Any]) -> Optional[str]:
        """Generate a 3-4 sentence taste reading via Groq. Returns None on
        any failure — the rest of the stats payload still ships."""
        try:
            from src.utils.llm_client import LLMClient, LLMProvider
            from config.settings import get_settings

            settings = get_settings()
            if not settings.groq_api_key or settings.llm_provider != "groq":
                return None
            if (payload.get("total_films") or 0) + (payload.get("total_series") or 0) < 10:
                # Not enough signal for a useful reading.
                return None

            top_genres = ", ".join(
                f"{g['name']} ({g['count']})" for g in (payload.get("top_genres") or [])[:3]
            ) or "varied"
            top_director = (payload.get("top_directors") or [{}])[0]
            top_decade = max(payload.get("decade_breakdown") or [], key=lambda d: d["count"], default=None)
            decade_str = f"{top_decade['decade']}s" if top_decade else "no clear decade"

            generosity = payload.get("generosity_score") or 0.0
            generosity_str = (
                f"more generous than the crowd by {abs(generosity):.1f}★"
                if generosity > 0.1
                else f"harsher than the crowd by {abs(generosity):.1f}★"
                if generosity < -0.1
                else "near the crowd consensus"
            )

            prompt = (
                "You are a film critic profiling a viewer's taste based on their "
                "ratings library. In 3-4 sentences, in second person ('You'), write "
                "a personal, observational reading. Be specific and confident. "
                "No clichés like 'you love movies'. Mention concrete patterns from "
                "the data. Output the reading only — no preamble.\n\n"
                f"STATS:\n"
                f"- Total titles rated: {(payload.get('total_films') or 0) + (payload.get('total_series') or 0)}\n"
                f"- Average rating: {payload.get('avg_rating')}\n"
                f"- Top genres: {top_genres}\n"
                f"- Most-rated director: {top_director.get('name', 'none')} "
                f"({top_director.get('count', 0)} films, avg {top_director.get('avg_rating', 0)}★)\n"
                f"- Dominant decade: {decade_str}\n"
                f"- Foreign cinema: {payload.get('foreign_pct')}%\n"
                f"- Hidden gems (vote_count < 100K): {payload.get('hidden_gem_pct')}%\n"
                f"- Generosity vs TMDB: {generosity_str}\n"
            )

            client = LLMClient(
                provider=LLMProvider.GROQ,
                model=getattr(settings, "groq_model_fast", None) or None,
            )
            text = client.generate(
                prompt=prompt,
                system_prompt=None,
                temperature=0.6,
                max_tokens=240,
            )
            text = (text or "").strip().strip('"').strip()
            if not text:
                return None
            return text[:600]  # hard cap so it always fits a card
        except Exception as exc:
            logger.warning(f"LLM personality generation failed: {exc}")
            return None


# ── Trigger throttle ──────────────────────────────────────────────────────
#
# When the Profile page polls /stats every 4 seconds, naive "fire a worker
# every time the row is stale" turns into a thundering herd: a single user
# loading the page can dispatch 8-10 overlapping workers within ~30 seconds
# while the first one is still running. They all hit Postgres + TMDB + LLM,
# burn cost, and stomp each other's writes.
#
# This dict (one per Lambda container) records the last time we triggered a
# worker per user. The GET route consults `should_throttle_trigger` before
# dispatching. The value is short-lived — 90 seconds is enough to outlast a
# typical compute on a warm cache, and on a cold cache the user just waits
# the same 30s they would have anyway.

_TRIGGER_THROTTLE_SEC = 90
_last_triggered: Dict[str, float] = {}


def should_throttle_trigger(user_id: str) -> bool:
    last = _last_triggered.get(user_id)
    if last is None:
        return False
    return (time.time() - last) < _TRIGGER_THROTTLE_SEC


def mark_trigger(user_id: str) -> None:
    _last_triggered[user_id] = time.time()


# ── Lambda self-invoke worker dispatch ───────────────────────────────────


def invoke_stats_worker(user_id: str) -> None:
    """Fire-and-forget Lambda self-invoke that runs StatsService.compute on
    a fresh container so the request handler returns immediately. Mirrors
    the recommendation worker pattern in recommendation_service."""
    try:
        import boto3
        lambda_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get(
            "LAMBDA_FUNCTION_NAME", "cinematch-api"
        )
        if not os.environ.get("LAMBDA_DEPLOYMENT"):
            # Local dev: run synchronously in a thread instead of self-invoking.
            import threading
            threading.Thread(
                target=lambda: get_stats_service().compute(user_id),
                daemon=True,
            ).start()
            return
        payload = {"source": "stats-worker", "user_id": user_id}
        client = boto3.client(
            "lambda", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )
        client.invoke(
            FunctionName=lambda_name,
            InvocationType="Event",
            Payload=json.dumps(payload).encode(),
        )
        logger.info(f"Dispatched stats-worker for {user_id}")
    except Exception as exc:
        logger.warning(f"Failed to dispatch stats-worker for {user_id}: {exc}")
