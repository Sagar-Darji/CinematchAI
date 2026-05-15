"""Tests for src/core/db.py — focuses on the SQL-translation layer that
converts SQLite-flavored INSERT OR REPLACE to a proper Postgres ON CONFLICT
clause. The pre-fix adapter hardcoded the (user_id, movie_id) ratings PK
and silently emitted invalid ON CONFLICT for any other multi-column PK
(watch_history, watchlist, reviews) — surfaced in production as
psycopg2.errors.InvalidColumnReference."""

from src.core import db as adapter
from src.core.db import _build_upsert_suffix, register_pk


def _fresh_registry():
    """Reset the PK registry between tests so they don't leak into each
    other. The registry is module-level state for performance, but tests
    should not depend on test ordering."""
    adapter._PK_REGISTRY.clear()


def test_single_column_pk_emits_simple_conflict_target():
    _fresh_registry()
    register_pk("users", ["user_id"])
    sql = "INSERT INTO users (user_id, created_at, updated_at, profile_json) VALUES (%s, %s, %s, %s)"
    suffix = _build_upsert_suffix(sql)
    assert suffix.startswith(" ON CONFLICT (user_id) DO UPDATE SET")
    assert "created_at=EXCLUDED.created_at" in suffix
    assert "updated_at=EXCLUDED.updated_at" in suffix
    assert "profile_json=EXCLUDED.profile_json" in suffix
    # PK columns must NOT appear in the UPDATE clause.
    assert "user_id=EXCLUDED.user_id" not in suffix


def test_two_column_pk_emits_compound_conflict_target():
    _fresh_registry()
    register_pk("ratings", ["user_id", "movie_id"])
    sql = "INSERT INTO ratings (user_id, movie_id, rating, watched, timestamp) VALUES (%s, %s, %s, %s, %s)"
    suffix = _build_upsert_suffix(sql)
    assert "ON CONFLICT (user_id, movie_id) DO UPDATE SET" in suffix
    assert "rating=EXCLUDED.rating" in suffix
    assert "user_id=EXCLUDED.user_id" not in suffix
    assert "movie_id=EXCLUDED.movie_id" not in suffix


def test_three_column_pk_emits_compound_conflict_target():
    """Regression: this is the watch_history/watchlist/reviews case that
    used to raise InvalidColumnReference because the old code emitted
    `ON CONFLICT (user_id)` for any non-ratings table."""
    _fresh_registry()
    register_pk("watch_history", ["user_id", "tmdb_id", "media_type"])
    sql = (
        "INSERT INTO watch_history "
        "(user_id, tmdb_id, media_type, title, poster_path, year, "
        "last_season, last_episode, watched_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)"
    )
    suffix = _build_upsert_suffix(sql)
    assert "ON CONFLICT (user_id, tmdb_id, media_type) DO UPDATE SET" in suffix
    assert "title=EXCLUDED.title" in suffix
    assert "last_season=EXCLUDED.last_season" in suffix
    # None of the three PK columns should be in the SET clause.
    for pk in ("user_id", "tmdb_id", "media_type"):
        assert f"{pk}=EXCLUDED.{pk}" not in suffix


def test_unregistered_table_falls_back_to_do_nothing():
    """If a table never called register_pk, the adapter should refuse to
    guess. Better to lose an upsert than to corrupt data with a wrong
    conflict target."""
    _fresh_registry()
    sql = "INSERT INTO mysterious_table (col_a, col_b, col_c) VALUES (%s, %s, %s)"
    suffix = _build_upsert_suffix(sql)
    assert suffix.strip() == "ON CONFLICT DO NOTHING"


def test_ratings_legacy_fallback_still_works():
    """Backward-compat path: ratings used to be hardcoded in the adapter
    instead of registered. If a service hasn't been updated yet to call
    register_pk, the legacy (user_id, movie_id) heuristic kicks in."""
    _fresh_registry()
    sql = "INSERT INTO ratings (user_id, movie_id, rating) VALUES (%s, %s, %s)"
    suffix = _build_upsert_suffix(sql)
    assert "ON CONFLICT (user_id, movie_id) DO UPDATE SET" in suffix
    assert "rating=EXCLUDED.rating" in suffix


def test_all_columns_in_pk_emits_do_nothing():
    """Edge case — if the only INSERT columns ARE the PK columns, there's
    nothing to update. DO NOTHING is correct."""
    _fresh_registry()
    register_pk("link_table", ["a", "b"])
    sql = "INSERT INTO link_table (a, b) VALUES (%s, %s)"
    suffix = _build_upsert_suffix(sql)
    assert "ON CONFLICT (a, b) DO NOTHING" in suffix
