"""Tests for StatsService — pure-function aggregation + the upsert/get round trip."""

from datetime import datetime, timezone

import pytest

from src.services.stats_service import StatsService, get_stats_service


def _it(rating, *, ts=None, media_type="movie", year=None, genres=None,
        director=None, cast=None, runtime=None, lang=None,
        vote_average=None, vote_count=None, title=None):
    """Helper to build an enriched item dict matching what `compute()` would
    produce after TMDB resolution."""
    return {
        "rating": float(rating),
        "timestamp": ts,
        "media_type": media_type,
        "year": year,
        "genres": genres or [],
        "director": director,
        "cast": cast or [],
        "runtime": runtime,
        "original_language": lang,
        "vote_average": vote_average,
        "vote_count": vote_count,
        "title": title,
    }


def test_aggregate_handles_empty_input():
    """Pure-function call with no items returns sensible zeros."""
    out = StatsService._aggregate([])
    assert out["total_films"] == 0
    assert out["total_series"] == 0
    assert out["avg_rating"] is None
    assert out["rating_histogram"] == [
        {"rating": round(0.5 * i, 1), "count": 0} for i in range(1, 11)
    ]
    assert out["top_genres"] == []
    assert out["insights"] == []


def test_aggregate_splits_movies_and_series():
    items = [
        _it(4.0, media_type="movie"),
        _it(3.5, media_type="movie"),
        _it(4.5, media_type="tv"),
    ]
    out = StatsService._aggregate(items)
    assert out["total_films"] == 2
    assert out["total_series"] == 1


def test_aggregate_films_this_year_uses_timestamp_year():
    """films_this_year reflects when watched, not when produced."""
    current_year = datetime.now(timezone.utc).year
    items = [
        _it(4.0, ts=f"{current_year}-01-15T00:00:00", year=2018),  # watched this year
        _it(3.5, ts=f"{current_year}-08-02T00:00:00", year=1999),  # watched this year
        _it(4.0, ts=f"{current_year - 2}-05-01T00:00:00", year=2010),  # earlier year
        _it(2.5, ts=None, year=2020),  # missing timestamp
    ]
    out = StatsService._aggregate(items)
    assert out["films_this_year"] == 2


def test_aggregate_decade_breakdown_groups_by_release_decade():
    items = [
        _it(4.0, year=1995),
        _it(3.5, year=1998),
        _it(4.0, year=2012),
        _it(2.5, year=2024),
    ]
    out = StatsService._aggregate(items)
    decades = {d["decade"]: d["count"] for d in out["decade_breakdown"]}
    assert decades == {1990: 2, 2010: 1, 2020: 1}


def test_aggregate_top_directors_with_avg_rating():
    items = [
        _it(5.0, director="Christopher Nolan"),
        _it(4.0, director="Christopher Nolan"),
        _it(4.5, director="Christopher Nolan"),
        _it(3.0, director="Greta Gerwig"),
    ]
    out = StatsService._aggregate(items)
    nolan = next(d for d in out["top_directors"] if d["name"] == "Christopher Nolan")
    assert nolan["count"] == 3
    assert nolan["avg_rating"] == round((5.0 + 4.0 + 4.5) / 3, 2)


def test_aggregate_director_loyalty_insight_only_at_threshold():
    """Only emit the insight when count >= 3."""
    items = [_it(4.0, director="Greta Gerwig"), _it(4.5, director="Greta Gerwig")]
    out = StatsService._aggregate(items)
    types = [i["type"] for i in out["insights"]]
    assert "director_loyalty" not in types  # 2 < 3

    items.append(_it(5.0, director="Greta Gerwig"))
    out = StatsService._aggregate(items)
    types = [i["type"] for i in out["insights"]]
    assert "director_loyalty" in types


def test_aggregate_hidden_gem_pct_and_insight():
    items = [
        _it(4.0, vote_count=5_000),       # gem
        _it(3.5, vote_count=12_000),      # gem
        _it(4.5, vote_count=900_000),     # popular
        _it(2.5, vote_count=2_000_000),   # popular
    ]
    out = StatsService._aggregate(items)
    assert out["hidden_gem_pct"] == 50.0
    types = [i["type"] for i in out["insights"]]
    assert "hidden_gem" in types


def test_aggregate_foreign_pct():
    items = [
        _it(4.0, lang="en"),
        _it(3.5, lang="ko"),
        _it(4.0, lang="ja"),
        _it(4.5, lang="en"),
    ]
    out = StatsService._aggregate(items)
    assert out["foreign_pct"] == 50.0


def test_aggregate_histogram_snaps_to_half_star_buckets():
    items = [_it(4.5), _it(4.5), _it(3.0), _it(0.5), _it(5.0)]
    out = StatsService._aggregate(items)
    histogram = {b["rating"]: b["count"] for b in out["rating_histogram"]}
    assert histogram[4.5] == 2
    assert histogram[3.0] == 1
    assert histogram[0.5] == 1
    assert histogram[5.0] == 1


def test_upsert_get_round_trip(monkeypatch):
    """Ensure the JSON columns serialize/deserialize correctly."""
    import uuid
    svc = get_stats_service()
    user_id = f"test-stats-{uuid.uuid4().hex[:12]}"
    payload = {
        "total_films": 833,
        "total_series": 12,
        "films_this_year": 42,
        "avg_rating": 3.8,
        "rating_histogram": [{"rating": 4.0, "count": 100}],
        "year_breakdown": {"2024": 200},
        "decade_breakdown": [{"decade": 2010, "label": "2010s", "count": 300}],
        "top_genres": [{"name": "Crime", "count": 199}],
        "top_directors": [{"name": "Nolan", "count": 8, "avg_rating": 4.6}],
        "top_actors": [{"name": "De Niro", "count": 12}],
        "total_runtime_minutes": 90_000,
        "foreign_pct": 32.0,
        "hidden_gem_pct": 18.0,
        "generosity_score": 0.3,
        "insights": [{"type": "director_loyalty", "title": "Director loyalty",
                      "value": "Nolan", "context": "8 films · avg 4.6★"}],
        "llm_personality": "You're drawn to dense, cerebral thrillers …",
    }
    svc.upsert(user_id, payload)
    row = svc.get(user_id)
    assert row is not None
    assert row["total_films"] == 833
    assert row["total_series"] == 12
    assert row["films_this_year"] == 42
    assert row["avg_rating"] == 3.8
    assert row["top_directors"][0]["name"] == "Nolan"
    assert row["llm_personality"].startswith("You're drawn")
    assert row["stale"] is False


def test_mark_stale_creates_row_if_missing():
    import uuid
    svc = get_stats_service()
    user_id = f"test-stale-{uuid.uuid4().hex[:12]}"
    svc.mark_stale(user_id)
    row = svc.get(user_id)
    assert row is not None
    assert row["stale"] is True


def test_singleton_returns_same_instance():
    a = get_stats_service()
    b = get_stats_service()
    assert a is b
    assert isinstance(a, StatsService)
