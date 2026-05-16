"""Profile read-side service.

Thin layer over the precomputed `user_stats.profile_payload` blob plus a
small set of live-query helpers for things the blob intentionally doesn't
hold (paginated diary timeline, paginated/filterable Films & Series
library).

Write path lives in `StatsService.compute()` — this service never writes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.db import get_db
from src.services.stats_service import get_stats_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

_service: Optional["ProfileService"] = None


def get_profile_service() -> "ProfileService":
    global _service
    if _service is None:
        _service = ProfileService()
    return _service


class ProfileService:
    """Read-only assembly + live queries that back the new Profile page."""

    def __init__(self) -> None:
        self.db = get_db()
        self.stats = get_stats_service()

    # ── Endpoints ─────────────────────────────────────────────────────

    def get_core(self, user_id: str) -> Dict[str, Any]:
        """Header-only payload: identity, favorites, computed_at, plus a
        live count of total films so the header updates immediately
        after a manual rating even when the analytics blob is stale.

        Returns 200 even when the analytics blob doesn't exist yet —
        cold-start users still get a usable header."""
        # Identity from the blob if present (gives us the banner film +
        # captions). Otherwise build a minimal fallback so cold users
        # render correctly.
        row = self.stats.get(user_id)
        payload = (row or {}).get("profile_payload") or {}
        identity = payload.get("identity") if isinstance(payload, dict) else None
        if not identity:
            from src.services.user_service import get_user_service
            try:
                avatar_url = get_user_service().get_avatar_url(user_id)
            except Exception:
                avatar_url = None
            identity = {
                "user_id":  user_id,
                "username": user_id,
                "avatar_url": avatar_url,
                "banner_film_id": None,
                "stat_chips": {},
                "captions":  [],
            }

        # Favorites are always live (cheap query, also editable in-place
        # so the blob would lag).
        from src.services.user_service import get_user_service
        try:
            favorites = get_user_service().get_favorites(user_id)
        except Exception:
            favorites = []

        live_total = self._live_films_count(user_id)
        computed_at = (row or {}).get("computed_at")

        return {
            "user_id":     user_id,
            "identity":    identity,
            "favorites":   favorites,
            "live_total":  live_total,
            "computed_at": computed_at,
            "is_stale":    self._is_stale(row, live_total, payload),
        }

    def get_analytics(self, user_id: str) -> Dict[str, Any]:
        """The precomputed Profile blob. Returns `{status: "pending"|"missing"}`
        for cold-start users so the frontend can render the import CTA
        instead of a skeleton."""
        row = self.stats.get(user_id)
        if not row:
            return {"status": "missing", "computed_at": None, "payload": None}

        payload = row.get("profile_payload")
        if not isinstance(payload, dict):
            # Row exists but the blob hasn't been written yet (recompute
            # in flight, or an old row from before this commit). Treat
            # as pending so the frontend keeps the friendly fallback.
            return {
                "status":      "pending" if row.get("stale") else "missing",
                "computed_at": row.get("computed_at"),
                "payload":     None,
            }

        return {
            "status":      "ok",
            "computed_at": row.get("computed_at"),
            "payload":     payload,
            "is_stale":    self._is_stale(row, self._live_films_count(user_id), payload),
        }

    def get_diary(
        self,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Paginated reverse-chronological list of rated films. The
        cursor is the timestamp of the last item in the previous page —
        the client sends it back to keep paging. Excludes implicit
        feedback rows since they're not 'watched' events."""
        limit = max(1, min(int(limit or 50), 100))
        params: List[Any] = [user_id]
        where = (
            "WHERE r.user_id = ? "
            "AND r.timestamp IS NOT NULL "
            "AND COALESCE(r.source, '') != 'implicit_feedback'"
        )
        if cursor:
            where += " AND r.timestamp < ?"
            params.append(cursor)
        params.append(limit + 1)  # over-fetch by 1 to detect more pages

        with self.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT r.movie_id, r.rating, r.timestamp, r.source,
                       rv.review_text
                FROM ratings r
                LEFT JOIN reviews rv
                  ON rv.user_id = r.user_id
                 AND rv.tmdb_id = CAST(r.movie_id AS INTEGER)
                 AND rv.media_type = 'movie'
                {where}
                ORDER BY r.timestamp DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

        items_raw = [dict(r) if isinstance(r, dict) else {
            "movie_id":    r[0],
            "rating":      r[1],
            "timestamp":   r[2],
            "source":      r[3],
            "review_text": r[4],
        } for r in rows]

        has_more = len(items_raw) > limit
        page = items_raw[:limit]

        # Enrich with TMDB metadata (title, poster, year, media_type).
        # Movies are batch-resolved through the same diskcache the
        # ratings worker warmed so most lookups are sub-ms.
        from src.services.movie_service import get_movie_service
        ids: List[int] = []
        for it in page:
            try:
                ids.append(int(it["movie_id"]))
            except (TypeError, ValueError):
                ids.append(0)
        try:
            resolved = get_movie_service().get_media_auto_batch(ids, max_workers=10)
        except Exception as exc:
            logger.warning(f"diary: TMDB batch resolve failed: {exc}")
            resolved = [None] * len(ids)

        items: List[Dict[str, Any]] = []
        for it, m in zip(page, resolved):
            md = getattr(m, "metadata", None) if m else None
            items.append({
                "movie_id":   it["movie_id"],
                "title":      getattr(md, "title", None),
                "year":       getattr(md, "year", None),
                "poster_path": getattr(md, "poster_path", None),
                "media_type": getattr(md, "media_type", "movie") or "movie",
                "rating":     it["rating"],
                "timestamp":  it["timestamp"],
                "review_text": it.get("review_text"),
            })

        next_cursor = page[-1]["timestamp"] if (has_more and page) else None
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    def get_library(
        self,
        user_id: str,
        media_type: str = "movie",
        sort: str = "date_watched",
        genres: Optional[List[str]] = None,
        decades: Optional[List[int]] = None,
        q: Optional[str] = None,
        cursor: Optional[int] = None,
        limit: int = 60,
    ) -> Dict[str, Any]:
        """Films / Series tab data with server-side sort + filter +
        search. Returns a paginated grid (poster_path, title, year,
        rating, timestamp)."""
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be movie|tv, got {media_type!r}")
        if sort not in ("rating", "date_watched", "title", "year"):
            sort = "date_watched"
        limit = max(1, min(int(limit or 60), 200))
        offset = max(0, int(cursor or 0))

        # Pull the user's ratings + enrich with metadata. We do the
        # filter/sort/search in Python after enrichment — the genre/year
        # fields live on TMDB, not in our DB, so a SQL-side filter
        # wouldn't see them anyway. For a 5000-rating library this is
        # ~30ms of in-memory work.
        from src.services.movie_service import get_movie_service
        from src.services.user_service import get_user_service

        ratings = get_user_service().get_user_ratings(user_id)
        if not ratings:
            return {"items": [], "next_cursor": None, "has_more": False, "total": 0}

        ids = [int(r["movie_id"]) for r in ratings]
        try:
            resolved = get_movie_service().get_media_auto_batch(ids, max_workers=20)
        except Exception as exc:
            logger.warning(f"library: TMDB batch resolve failed: {exc}")
            resolved = [None] * len(ids)

        candidates: List[Dict[str, Any]] = []
        for r, m in zip(ratings, resolved):
            md = getattr(m, "metadata", None) if m else None
            if md is None:
                # Unresolvable — skip rather than render an empty card.
                continue
            mt = getattr(md, "media_type", "movie") or "movie"
            if mt != media_type:
                continue
            year = getattr(md, "year", None)
            title = getattr(md, "title", None) or ""
            entry = {
                "movie_id":    r["movie_id"],
                "title":       title,
                "year":        year,
                "poster_path": getattr(md, "poster_path", None),
                "media_type":  mt,
                "rating":      r["rating"],
                "timestamp":   r.get("timestamp"),
                "genres":      getattr(md, "genres", []) or [],
            }
            candidates.append(entry)

        # ── Filters ────────────────────────────────────────────────
        if genres:
            wanted = {g.lower() for g in genres}
            candidates = [
                c for c in candidates
                if any((g or "").lower() in wanted for g in c["genres"])
            ]
        if decades:
            decade_set = {int(d) for d in decades}
            def _decade_of(y: Optional[int]) -> Optional[int]:
                if y is None:
                    return None
                return (int(y) // 10) * 10
            candidates = [c for c in candidates if _decade_of(c["year"]) in decade_set]
        if q:
            needle = q.lower().strip()
            if needle:
                candidates = [c for c in candidates if needle in (c["title"] or "").lower()]

        # ── Sort ───────────────────────────────────────────────────
        if sort == "rating":
            candidates.sort(key=lambda c: (float(c["rating"] or 0), c["timestamp"] or ""), reverse=True)
        elif sort == "title":
            candidates.sort(key=lambda c: (c["title"] or "").lower())
        elif sort == "year":
            candidates.sort(key=lambda c: (c["year"] or 0), reverse=True)
        else:  # date_watched
            candidates.sort(key=lambda c: c["timestamp"] or "", reverse=True)

        total = len(candidates)
        page = candidates[offset:offset + limit]
        has_more = (offset + len(page)) < total
        # Strip the genres field from the response — only used internally.
        for p in page:
            p.pop("genres", None)
        return {
            "items":       page,
            "next_cursor": offset + len(page) if has_more else None,
            "has_more":    has_more,
            "total":       total,
        }

    def recompute(self, user_id: str) -> None:
        """Mark the blob stale + dispatch a fresh compute. Called by
        POST /profile/{user_id}/recompute. Same path used by onboarding +
        import completion."""
        from src.services.stats_service import (
            invoke_stats_worker,
            mark_trigger,
            should_throttle_trigger,
        )
        self.stats.mark_stale(user_id)
        if should_throttle_trigger(user_id):
            logger.info(f"recompute: throttled for {user_id} (within 90s window)")
            return
        invoke_stats_worker(user_id)
        mark_trigger(user_id)

    # ── Helpers ───────────────────────────────────────────────────────

    def _live_films_count(self, user_id: str) -> int:
        """Cheap COUNT of explicit ratings — drives the header `Films`
        chip even when analytics are stale, so manual ratings update
        the total instantly while the blob waits for a recompute."""
        try:
            with self.db.connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM ratings "
                    "WHERE user_id = ? "
                    "AND COALESCE(source, '') != 'implicit_feedback'",
                    (user_id,),
                ).fetchone()
            if not row:
                return 0
            return int(row[0] if not isinstance(row, dict) else list(row.values())[0])
        except Exception as exc:
            logger.warning(f"_live_films_count failed for {user_id}: {exc}")
            return 0

    def _is_stale(
        self,
        row: Optional[Dict[str, Any]],
        live_total: int,
        payload: Optional[Dict[str, Any]],
    ) -> bool:
        """True when the precomputed totals lag behind the live count by
        a meaningful margin OR when the row is flagged stale. Drives the
        'Refreshing…' badge + 'Last refreshed' footer."""
        if not row:
            return True
        if bool(row.get("stale")):
            return True
        if not isinstance(payload, dict):
            return True
        cached_total = (payload.get("overview") or {}).get("totals", {}).get("films", 0)
        # Any drift triggers the badge — the user added at least one
        # rating since the last recompute.
        return cached_total != live_total
