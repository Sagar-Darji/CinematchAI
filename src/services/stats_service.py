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
                # The unified profile_payload column holds the full
                # precomputed artifact the new Profile page reads in one
                # shot: identity, captions, overview, diary. Stored as
                # JSON-encoded text so SQLite + Postgres both work without
                # a custom adapter; Postgres treats TEXT cheaply.
                try:
                    conn.execute(
                        "ALTER TABLE user_stats ADD COLUMN profile_payload TEXT"
                    )
                except Exception:
                    pass  # column already exists — idempotent
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
            "profile_payload",
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
            "profile_payload",
            "computed_at",
            "stale",
        )
        profile_payload_value = payload.get("profile_payload")
        if isinstance(profile_payload_value, dict):
            profile_payload_serialized = json.dumps(profile_payload_value)
        elif isinstance(profile_payload_value, str):
            profile_payload_serialized = profile_payload_value
        else:
            profile_payload_serialized = None

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
            profile_payload_serialized,
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
        # Layered LLM personality essay — one Groq call returns a
        # structured object with teaser, bullets, longitudinal arc,
        # dense paragraph, letter, and quarterly entries. All generated
        # up-front so view time is a pure JSON read.
        personality = self._maybe_llm_personality(payload, enriched, user_id=user_id)
        # Legacy column gets the teaser text so /users/{id}/stats stays
        # usable for callers that haven't migrated yet.
        if isinstance(personality, dict):
            payload["llm_personality"] = personality.get("teaser")
        else:
            payload["llm_personality"] = personality
        # Assemble the precomputed Profile artifact. Builds for identity,
        # captions, overview, diary — everything the new Profile page
        # renders without computing at view time.
        try:
            favorites = get_user_service().get_favorites(user_id)
        except Exception:
            favorites = []
        payload["profile_payload"] = self._build_profile_payload(
            user_id=user_id,
            agg=payload,
            enriched=enriched,
            ratings=ratings,
            favorites=favorites,
            personality=personality if isinstance(personality, dict) else None,
        )
        self.upsert(user_id, payload)
        logger.info(
            f"Computed stats for {user_id}: {payload['total_films']} films, "
            f"{payload['total_series']} series, in {time.time() - t0:.1f}s"
        )
        return payload

    # ── Profile payload builders ─────────────────────────────────────────

    def _build_profile_payload(
        self,
        user_id: str,
        agg: Dict[str, Any],
        enriched: List[dict],
        ratings: List[dict],
        favorites: List[dict],
        personality: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compose the precomputed Profile artifact the new page consumes
        in a single read. Pure assembly — every input is already computed."""
        now = datetime.now(timezone.utc)
        return {
            "schema_version": 1,
            "computed_at": now.isoformat(),
            "identity": self._build_identity(user_id, agg, favorites, enriched),
            "overview": {
                "favorites":   favorites or [],
                "personality": personality or _empty_personality(),
                "insights":    agg.get("insights") or [],
                "top_genres":  agg.get("top_genres") or [],
                "decades":     agg.get("decade_breakdown") or [],
                "people": {
                    "directors": agg.get("top_directors") or [],
                    "actors":    agg.get("top_actors") or [],
                    "directors_by_language": agg.get("top_directors_by_lang") or {},
                    "actors_by_language":    agg.get("top_actors_by_lang") or {},
                    "languages":             agg.get("top_languages") or [],
                },
                "histogram":   agg.get("rating_histogram") or [],
                "totals": {
                    "films":   agg.get("total_films") or 0,
                    "series":  agg.get("total_series") or 0,
                    "runtime_minutes": agg.get("total_runtime_minutes") or 0,
                    "foreign_pct":     agg.get("foreign_pct") or 0.0,
                    "hidden_gem_pct":  agg.get("hidden_gem_pct") or 0.0,
                    "generosity_score": agg.get("generosity_score") or 0.0,
                    "avg_rating":      agg.get("avg_rating"),
                },
            },
            "diary": self._build_diary_payload(enriched),
        }

    @staticmethod
    def _build_identity(
        user_id: str,
        agg: Dict[str, Any],
        favorites: List[dict],
        enriched: List[dict],
    ) -> Dict[str, Any]:
        """Header strip: username (= user_id in this codebase, see
        rename_user), avatar from user_service.get_avatar_url, banner
        film + the 4 taste-first chips + rotating captions."""
        from src.services.user_service import get_user_service
        try:
            avatar_url = get_user_service().get_avatar_url(user_id)
        except Exception:
            avatar_url = None

        # Stat chips (taste-first set the user picked).
        decades = agg.get("decade_breakdown") or []
        top_decade = max(decades, key=lambda d: d.get("count", 0), default=None)
        top_director = (agg.get("top_directors") or [{}])[0] if agg.get("top_directors") else None
        top_genre = (agg.get("top_genres") or [{}])[0] if agg.get("top_genres") else None

        stat_chips = {
            "films": agg.get("total_films") or 0,
            "decade_lean": f"{top_decade['decade']}s" if top_decade else None,
            "top_director": {
                "name":  top_director.get("name") if top_director else None,
                "count": top_director.get("count") if top_director else None,
            } if top_director else None,
            "top_genre": {
                "name":  top_genre.get("name") if top_genre else None,
                "count": top_genre.get("count") if top_genre else None,
            } if top_genre else None,
        }

        # Banner: first favorite's poster path (the existing convention).
        banner_film_id: Optional[int] = None
        if favorites:
            try:
                banner_film_id = int(favorites[0].get("tmdb_id"))
            except (TypeError, ValueError):
                pass

        return {
            "user_id":  user_id,
            "username": user_id,  # by convention here user_id is the handle
            "avatar_url": avatar_url,
            "banner_film_id": banner_film_id,
            "stat_chips": stat_chips,
            "captions":  StatsService._build_captions(enriched),
        }

    @staticmethod
    def _build_captions(items: List[dict]) -> List[Dict[str, Any]]:
        """Return the 4 candidate captions the header rotates through:
        on_this_day, recent (7-day), streak, random_pick.

        Each is independently optional — missing data drops the caption.
        The frontend rotates whatever it gets."""
        if not items:
            return []
        today = datetime.now(timezone.utc).date()
        captions: List[Dict[str, Any]] = []

        # ── on_this_day ──────────────────────────────────────────────
        # Look for a rating with timestamp matching today's MM-DD in any
        # prior year. Take the highest-rated match for the most evocative
        # callout.
        on_this_day: Optional[dict] = None
        best_rating = -1.0
        for it in items:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date()
            except Exception:
                continue
            if d.month == today.month and d.day == today.day and d.year < today.year:
                r = float(it.get("rating") or 0)
                if r > best_rating:
                    best_rating = r
                    on_this_day = it.copy()
                    on_this_day["_year"] = d.year
        if on_this_day and on_this_day.get("title"):
            captions.append({
                "type": "on_this_day",
                "text": f"You watched {on_this_day['title']} on this day in {on_this_day['_year']}.",
            })

        # ── recent (7-day) ───────────────────────────────────────────
        from datetime import timedelta
        week_ago = today - timedelta(days=7)
        recent_count = 0
        for it in items:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date()
            except Exception:
                continue
            if d >= week_ago and d <= today:
                recent_count += 1
        if recent_count >= 3:  # under 3 = not interesting
            noun = "films" if recent_count != 1 else "film"
            captions.append({
                "type": "recent",
                "text": f"You rated {recent_count} {noun} this week.",
            })

        # ── streak (consecutive days with a rating ending today) ────
        rating_days = set()
        for it in items:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date()
            except Exception:
                continue
            rating_days.add(d)
        streak = 0
        cursor = today
        while cursor in rating_days:
            streak += 1
            cursor = cursor - timedelta(days=1)
        if streak >= 3:
            captions.append({
                "type": "streak",
                "text": f"{streak}-day rating streak.",
            })

        # ── random_pick: a random top-rated film ────────────────────
        import random
        top_rated = [it for it in items if (it.get("rating") or 0) >= 4.5 and it.get("title")]
        if top_rated:
            pick = random.choice(top_rated)
            captions.append({
                "type": "random_pick",
                "text": f"Top pick today: {pick['title']}.",
            })

        # Total ratings milestone — every 100 films crossed gets a
        # one-shot caption that sits in the rotation.
        total = sum(1 for it in items if it.get("media_type") == "movie")
        if total >= 100 and total % 100 == 0:
            captions.append({
                "type": "milestone",
                "text": f"You've crossed {total} films.",
            })
        elif total >= 100:
            # Nearest-100 callout that's still meaningful.
            nearest = (total // 100) * 100
            captions.append({
                "type": "milestone",
                "text": f"You've crossed {nearest} films.",
            })

        return captions

    @staticmethod
    def _build_diary_payload(items: List[dict]) -> Dict[str, Any]:
        """Diary tab data: year chart, per-year heatmaps, monthly
        highlight reel. Recently-watched list is paginated separately —
        not included in the blob."""
        year_chart: Dict[str, int] = {}
        # heatmaps: {year: {YYYY-MM-DD: count}} — count is # of titles
        # logged on that day, deduped if same film appears twice on the
        # same day.
        heatmaps: Dict[str, Dict[str, set]] = {}

        # Per-month aggregations for the highlight reel.
        from collections import defaultdict, Counter
        month_buckets: Dict[str, List[dict]] = defaultdict(list)

        for it in items:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date()
            except Exception:
                continue
            yr = str(d.year)
            year_chart[yr] = year_chart.get(yr, 0) + 1
            heatmaps.setdefault(yr, {}).setdefault(d.isoformat(), set()).add(
                (it.get("title") or "", it.get("media_type") or "movie")
            )
            month_buckets[f"{d.year:04d}-{d.month:02d}"].append(it)

        # Flatten heatmap sets to counts so the blob is JSON-safe.
        heatmaps_flat: Dict[str, Dict[str, int]] = {
            yr: {day: len(entries) for day, entries in days.items()}
            for yr, days in heatmaps.items()
        }

        # Monthly highlight reel — keep the last 6 months that have data,
        # most-recent first. Each: top film (highest rating, then most
        # recent), total watched, dominant genre.
        highlight_months = sorted(month_buckets.keys(), reverse=True)[:6]
        monthly_highlights: List[Dict[str, Any]] = []
        for m in highlight_months:
            bucket = month_buckets[m]
            top = max(
                bucket,
                key=lambda it: (float(it.get("rating") or 0), str(it.get("timestamp") or "")),
            )
            genre_counts: Counter = Counter()
            for it in bucket:
                for g in it.get("genres") or []:
                    genre_counts[g] += 1
            dom_genre = genre_counts.most_common(1)[0][0] if genre_counts else None
            monthly_highlights.append({
                "month":  m,
                "total":  len(bucket),
                "top_film": {
                    "title":  top.get("title"),
                    "year":   top.get("year"),
                    "rating": top.get("rating"),
                },
                "dominant_genre": dom_genre,
            })

        return {
            "year_chart":         year_chart,
            "heatmaps":           heatmaps_flat,
            "monthly_highlights": monthly_highlights,
        }

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
        # Per-language counters power the People panel's language toggle —
        # e.g. user wants to see "Top Hindi directors" vs "Top English
        # directors" without the dominant pool drowning out the smaller one.
        actor_counts_by_lang: Dict[str, Counter] = defaultdict(Counter)
        for it in items:
            for g in it.get("genres") or []:
                genre_counts[g] += 1
            lang = it.get("original_language") or "unknown"
            for actor in it.get("cast") or []:
                actor_counts[actor] += 1
                actor_counts_by_lang[lang][actor] += 1

        director_counts: Counter = Counter()
        director_rating_sum: Dict[str, float] = defaultdict(float)
        director_counts_by_lang: Dict[str, Counter] = defaultdict(Counter)
        director_rating_sum_by_lang: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for it in explicit:
            d = it.get("director")
            if d:
                director_counts[d] += 1
                director_rating_sum[d] += it["rating"]
                lang = it.get("original_language") or "unknown"
                director_counts_by_lang[lang][d] += 1
                director_rating_sum_by_lang[lang][d] += it["rating"]

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

        # Per-language top-N. Cap at top 5 languages by total ratings so the
        # frontend toggle stays sane; English + Hindi dominate most libraries
        # but we don't hard-code that.
        lang_totals: Counter = Counter()
        for it in items:
            lang_totals[it.get("original_language") or "unknown"] += 1
        top_langs = [lang for lang, _ in lang_totals.most_common(5) if lang != "unknown"]

        top_directors_by_lang: Dict[str, List[Dict[str, Any]]] = {}
        for lang in top_langs:
            counts = director_counts_by_lang.get(lang) or Counter()
            sums = director_rating_sum_by_lang.get(lang) or {}
            if not counts:
                continue
            top_directors_by_lang[lang] = [
                {
                    "name": d,
                    "count": c,
                    "avg_rating": round(sums.get(d, 0.0) / c, 2) if c else None,
                }
                for d, c in counts.most_common(10)
            ]

        top_actors_by_lang: Dict[str, List[Dict[str, Any]]] = {}
        for lang in top_langs:
            counts = actor_counts_by_lang.get(lang) or Counter()
            if not counts:
                continue
            top_actors_by_lang[lang] = [
                {"name": a, "count": c} for a, c in counts.most_common(10)
            ]

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
            "top_directors_by_lang": top_directors_by_lang,
            "top_actors_by_lang":    top_actors_by_lang,
            "top_languages":         top_langs,
            "total_runtime_minutes": total_runtime,
            "foreign_pct": foreign_pct,
            "hidden_gem_pct": hidden_gem_pct,
            "generosity_score": generosity_score,
            "insights": insights,
        }

    # ── LLM personality essay ─────────────────────────────────────────────

    @staticmethod
    def _maybe_llm_personality(
        payload: Dict[str, Any],
        enriched: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a layered taste-as-growth essay via Groq.

        Returns a dict with: teaser (3-4 lines), bullets (3 evidence
        strings), and longform (longitudinal_arc[3], dense_paragraph,
        letter, quarterly_entries[]). All produced in ONE Groq call
        returning JSON so view time is just a JSON read.

        Returns None on any failure or when the user has < 10 rated
        titles — the rest of the stats payload still ships."""
        try:
            from src.utils.llm_client import LLMClient, LLMProvider
            from config.settings import get_settings

            settings = get_settings()
            if not settings.groq_api_key or settings.llm_provider != "groq":
                return None
            total_titles = (payload.get("total_films") or 0) + (payload.get("total_series") or 0)
            if total_titles < 10:
                # Not enough signal for a useful reading.
                return None

            evidence = StatsService._build_personality_evidence(
                payload=payload,
                enriched=enriched or [],
                user_id=user_id,
            )

            prompt = (
                "You are writing a layered taste-as-personality reading for a "
                "film viewer. The reading should feel like a perceptive critic "
                "who has actually watched alongside them — naming the specific "
                "films, directors, and quotes that prove every claim. Never "
                "use a generic adjective without immediately citing the film "
                "or review that earns it.\n\n"
                "Return a JSON object with EXACTLY these keys:\n"
                "  teaser:    a 3-4 line paragraph (under 360 chars). MUST name at least 2 specific films from the library.\n"
                "  bullets:   array of 3 short evidence sentences (each under 130 chars). EACH bullet must cite at least one film by name + its star rating.\n"
                "  longform:\n"
                "    longitudinal_arc:  array of EXACTLY 3 paragraphs — who you were, how taste shifted, what it says now. Each paragraph names 1-2 specific films.\n"
                "    dense_paragraph:   one 150-180 word paragraph synthesizing taste + growth. Anchor in director patterns + at least 3 named films.\n"
                "    letter:            a stylized 'letter to a viewer' (~150 words) addressed in second person. Reference at least one review quote from the data.\n"
                "    quarterly_entries: array of short journal entries, one per quarter present in the data; each {quarter: 'YYYY Qn', text: '<60 words>'}. Each quarter MUST name at least one film actually rated that quarter.\n\n"
                "Write in second person ('You'). No clichés ('you love movies'). "
                "Lead with what's distinctive about THIS library, not what's common. "
                "When the library has multiple language traditions (e.g. Hindi + "
                "English), acknowledge the bridge — don't pretend one doesn't "
                "exist. Prefer naming films from the EVIDENCE block over inventing.\n\n"
                f"{evidence}\n"
            )

            client = LLMClient(
                provider=LLMProvider.GROQ,
                model=getattr(settings, "groq_model_fast", None) or None,
            )
            # Ask for JSON. Groq supports response_format={"type":"json_object"}
            # on llama-3.x — if the client doesn't pass that through we fall
            # back to extracting a {...} block from the response text.
            text = client.generate(
                prompt=prompt,
                system_prompt=(
                    "Output ONLY a JSON object with the requested keys. No "
                    "preamble, no markdown fences, no commentary. Every "
                    "specific film name and review quote in your output "
                    "must come from the EVIDENCE block — do not invent "
                    "titles or quotes."
                ),
                temperature=0.6,
                max_tokens=2000,
            )
            text = (text or "").strip()
            # Strip ```json fences if present.
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
                text = text.strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # Try to recover a {...} substring.
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        parsed = json.loads(text[start:end + 1])
                    except json.JSONDecodeError:
                        logger.warning("LLM personality: JSON parse failed after recovery")
                        return None
                else:
                    logger.warning("LLM personality: no JSON in response")
                    return None

            return StatsService._normalize_personality(parsed)
        except Exception as exc:
            logger.warning(f"LLM personality generation failed: {exc}")
            return None

    @staticmethod
    def _build_personality_evidence(
        payload: Dict[str, Any],
        enriched: List[dict],
        user_id: Optional[str],
    ) -> str:
        """Assemble a dense evidence block for the personality prompt.

        The previous version passed counts and percentages only — the LLM
        had to invent which films earned each label. This version surfaces
        ranked film names per director, per star tier, per language, plus
        the user's review excerpts so the model can quote them verbatim.
        """
        from collections import defaultdict, Counter

        # ── Index by director: top films + avg rating ────────────────────
        by_director: Dict[str, List[dict]] = defaultdict(list)
        for it in enriched:
            d = it.get("director")
            if not d:
                continue
            by_director[d].append(it)

        director_lines: List[str] = []
        for entry in (payload.get("top_directors") or [])[:6]:
            name = entry["name"]
            films = sorted(
                by_director.get(name, []),
                key=lambda f: float(f.get("rating") or 0),
                reverse=True,
            )[:4]
            picks = ", ".join(
                f"{f.get('title') or '?'} ({f.get('year') or '?'}) {float(f.get('rating') or 0):g}★"
                for f in films
            ) or "—"
            director_lines.append(
                f"  - {name} · {entry['count']} films · avg {entry.get('avg_rating') or 0}★ · {picks}"
            )

        # ── Per-language directors (lets the LLM acknowledge the bridge) ─
        lang_lines: List[str] = []
        by_lang_dirs = payload.get("top_directors_by_lang") or {}
        for lang in (payload.get("top_languages") or [])[:3]:
            picks = by_lang_dirs.get(lang) or []
            if not picks:
                continue
            top = ", ".join(f"{p['name']} ({p['count']})" for p in picks[:3])
            lang_lines.append(f"  - {lang}: {top}")

        # ── Rating tiers: which films earned each star value ─────────────
        by_tier: Dict[float, List[str]] = defaultdict(list)
        for it in enriched:
            r = float(it.get("rating") or 0)
            t = it.get("title")
            if not t or r <= 0:
                continue
            by_tier[r].append(t)
        tier_lines: List[str] = []
        for tier in (5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5):
            titles = by_tier.get(tier) or []
            if not titles:
                continue
            sample = ", ".join(titles[:4])
            tier_lines.append(f"  - {tier:g}★ ({len(titles)}): {sample}")

        # ── Hidden gems: high user rating, low TMDB vote_count ───────────
        gems = sorted(
            (
                it for it in enriched
                if (it.get("vote_count") or 0) < 50_000
                and float(it.get("rating") or 0) >= 3.5
                and it.get("title")
            ),
            key=lambda it: (float(it.get("rating") or 0), -(it.get("vote_count") or 0)),
            reverse=True,
        )[:5]
        gem_lines = [
            f"  - {g['title']} ({g.get('year') or '?'}) {float(g.get('rating') or 0):g}★, "
            f"only {g.get('vote_count') or 0} TMDB votes"
            for g in gems
        ] or ["  - (no clear hidden gems)"]

        # ── Decade breakdown with percentages ────────────────────────────
        decades = payload.get("decade_breakdown") or []
        total_dec = sum(d.get("count", 0) for d in decades) or 1
        decade_lines = [
            f"  - {d['label']}: {d['count']} films "
            f"({round(100 * d['count'] / total_dec)}%)"
            for d in sorted(decades, key=lambda d: d.get("decade", 0))
        ] or ["  - (no dated films)"]

        # ── Genre lean: top 5 with their counts ──────────────────────────
        genre_lines = [
            f"  - {g['name']}: {g['count']}"
            for g in (payload.get("top_genres") or [])[:6]
        ] or ["  - (no genres resolved)"]

        # ── User review excerpts — verbatim so the LLM can quote ─────────
        review_lines: List[str] = []
        if user_id:
            try:
                from src.services.review_service import get_review_service
                from src.services.movie_service import get_movie_service
                reviews = get_review_service().list_by_user(user_id, limit=20)
                # Resolve titles in batch.
                ids = [int(r["tmdb_id"]) for r in reviews if r.get("tmdb_id")]
                movies = get_movie_service().get_media_auto_batch(ids, max_workers=10) if ids else []
                title_by_id = {}
                for tid, m in zip(ids, movies):
                    md = getattr(m, "metadata", None) if m else None
                    if md and getattr(md, "title", None):
                        title_by_id[tid] = md.title
                for r in reviews[:8]:
                    text = (r.get("review_text") or "").strip().replace("\n", " ")
                    if not text:
                        continue
                    if len(text) > 200:
                        text = text[:200].rstrip() + "…"
                    title = title_by_id.get(int(r["tmdb_id"]), "?")
                    rating = r.get("rating")
                    rating_str = f"{float(rating):g}★" if rating is not None else "no rating"
                    review_lines.append(f'  - {title} ({rating_str}): "{text}"')
            except Exception as exc:
                logger.debug(f"personality evidence: review lookup skipped: {exc}")

        # ── YoY + per-quarter (existing helper) ──────────────────────────
        yoy_summary, quarter_summary = StatsService._build_yoy_summary(enriched)

        generosity = payload.get("generosity_score") or 0.0
        generosity_str = (
            f"more generous than the crowd by {abs(generosity):.1f}★"
            if generosity > 0.1
            else f"harsher than the crowd by {abs(generosity):.1f}★"
            if generosity < -0.1
            else "near the crowd consensus"
        )

        return (
            "EVIDENCE — every claim in the output must be grounded here:\n"
            f"- Total titles rated: {(payload.get('total_films') or 0) + (payload.get('total_series') or 0)}\n"
            f"- Average rating: {payload.get('avg_rating')}\n"
            f"- Foreign cinema: {payload.get('foreign_pct')}%\n"
            f"- Hidden-gem density (<100K TMDB votes): {payload.get('hidden_gem_pct')}%\n"
            f"- Crowd lean: {generosity_str}\n"
            "\nTOP DIRECTORS (name · count · avg · highest-rated picks):\n"
            + "\n".join(director_lines or ["  - (none)"])
            + "\n\nDIRECTORS BY LANGUAGE (top 3 per language):\n"
            + ("\n".join(lang_lines) if lang_lines else "  - (single language)")
            + "\n\nGENRES:\n"
            + "\n".join(genre_lines)
            + "\n\nDECADES:\n"
            + "\n".join(decade_lines)
            + "\n\nRATING TIERS (titles at each star level):\n"
            + ("\n".join(tier_lines) if tier_lines else "  - (no ratings)")
            + "\n\nHIDDEN GEMS (high rating, low TMDB vote count):\n"
            + "\n".join(gem_lines)
            + "\n\nREVIEW EXCERPTS (verbatim — quote these in the letter section):\n"
            + ("\n".join(review_lines) if review_lines else "  - (no reviews on file)")
            + f"\n\nYEAR-OVER-YEAR:\n{yoy_summary}\n\nPER-QUARTER TOP PICKS:\n{quarter_summary}"
        )

    @staticmethod
    def _build_yoy_summary(enriched: List[dict]) -> tuple[str, str]:
        """Render compact year-over-year + per-quarter signal lines for
        the LLM prompt. Returns (yoy_text, quarter_text)."""
        from collections import defaultdict, Counter
        by_year: Dict[int, List[dict]] = defaultdict(list)
        by_q: Dict[str, List[dict]] = defaultdict(list)
        for it in enriched:
            ts = it.get("timestamp")
            if not ts:
                continue
            try:
                d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                continue
            by_year[d.year].append(it)
            q = (d.month - 1) // 3 + 1
            by_q[f"{d.year} Q{q}"].append(it)

        yoy_lines: List[str] = []
        for yr in sorted(by_year.keys()):
            bucket = by_year[yr]
            avg = sum(float(b.get("rating") or 0) for b in bucket) / len(bucket) if bucket else 0
            genre_counts: Counter = Counter()
            for b in bucket:
                for g in b.get("genres") or []:
                    genre_counts[g] += 1
            top = genre_counts.most_common(1)[0][0] if genre_counts else "n/a"
            yoy_lines.append(f"  {yr}: {len(bucket)} films, avg {avg:.1f}★, top genre {top}")

        # Per-quarter top 3 by rating.
        q_lines: List[str] = []
        for q in sorted(by_q.keys()):
            bucket = sorted(by_q[q], key=lambda b: float(b.get("rating") or 0), reverse=True)[:3]
            titles = ", ".join(b.get("title") or "?" for b in bucket if b.get("title")) or "n/a"
            q_lines.append(f"  {q}: {titles}")

        return "\n".join(yoy_lines) or "  (no dated ratings)", "\n".join(q_lines) or "  (no dated ratings)"

    @staticmethod
    def _normalize_personality(parsed: Any) -> Optional[Dict[str, Any]]:
        """Coerce whatever shape the LLM returned into the canonical
        personality dict. Discards entries that don't pass minimal
        sanity checks rather than failing the whole compute."""
        if not isinstance(parsed, dict):
            return None
        teaser = str(parsed.get("teaser") or "").strip()
        bullets_raw = parsed.get("bullets") or []
        bullets = [str(b).strip() for b in bullets_raw if str(b or "").strip()][:5]
        longform_in = parsed.get("longform") or {}
        if not isinstance(longform_in, dict):
            longform_in = {}
        arc_raw = longform_in.get("longitudinal_arc") or []
        arc = [str(a).strip() for a in arc_raw if str(a or "").strip()][:3]
        dense_paragraph = str(longform_in.get("dense_paragraph") or "").strip()
        letter = str(longform_in.get("letter") or "").strip()
        quarterly_raw = longform_in.get("quarterly_entries") or []
        quarterly: List[Dict[str, Any]] = []
        if isinstance(quarterly_raw, list):
            for entry in quarterly_raw:
                if not isinstance(entry, dict):
                    continue
                q = str(entry.get("quarter") or "").strip()
                t = str(entry.get("text") or "").strip()
                if q and t:
                    quarterly.append({"quarter": q, "text": t})

        if not teaser:
            return None  # at minimum we need the teaser

        return {
            "teaser":  teaser[:600],
            "bullets": bullets,
            "longform": {
                "longitudinal_arc":  arc,
                "dense_paragraph":   dense_paragraph[:1500],
                "letter":            letter[:1500],
                "quarterly_entries": quarterly,
            },
        }


def _empty_personality() -> Dict[str, Any]:
    """Shape we always emit when no LLM essay is available — keeps the
    frontend rendering predictable instead of branching on null."""
    return {
        "teaser":  None,
        "bullets": [],
        "longform": {
            "longitudinal_arc": [],
            "dense_paragraph":  None,
            "letter":           None,
            "quarterly_entries": [],
        },
    }


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
