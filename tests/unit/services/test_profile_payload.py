"""Tests for the precomputed Profile payload builders + ProfileService
filter/sort/search logic. All pure functions — no DB, no TMDB."""

from datetime import datetime, timezone, timedelta

from src.services.stats_service import StatsService, _empty_personality


def _ts(d):
    """Build an ISO timestamp for a given (year, month, day)."""
    return datetime(*d, tzinfo=timezone.utc).isoformat()


def _enriched(**kw):
    """One enriched-row dict with sensible defaults."""
    base = {
        "rating": 4.0,
        "timestamp": _ts((2025, 6, 1)),
        "source": "manual",
        "title": "Sample",
        "year": 2010,
        "media_type": "movie",
        "genres": ["Drama"],
        "director": "Sample Director",
        "cast": [],
        "runtime": 120,
        "original_language": "en",
        "vote_average": 7.5,
        "vote_count": 50000,
    }
    base.update(kw)
    return base


def test_empty_personality_shape():
    p = _empty_personality()
    assert p["teaser"] is None
    assert p["bullets"] == []
    assert "longform" in p and p["longform"]["longitudinal_arc"] == []


def test_build_captions_emits_on_this_day_and_streak():
    """A library with a rating exactly one year ago today should produce
    an on_this_day caption; a 3-day rating streak ending today should
    produce a streak caption."""
    today = datetime.now(timezone.utc).date()
    one_year_ago = today.replace(year=today.year - 1)
    items = [
        _enriched(
            title="Inception",
            timestamp=datetime(one_year_ago.year, one_year_ago.month, one_year_ago.day, tzinfo=timezone.utc).isoformat(),
            rating=4.5,
        ),
        # 3-day streak ending today
        _enriched(timestamp=datetime(today.year, today.month, today.day, tzinfo=timezone.utc).isoformat()),
        _enriched(timestamp=(datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=1)).isoformat()),
        _enriched(timestamp=(datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=2)).isoformat()),
        # High-rated film for random_pick
        _enriched(title="Stalker", rating=5.0),
    ]
    caps = StatsService._build_captions(items)
    types = [c["type"] for c in caps]
    assert "on_this_day" in types
    assert "streak" in types
    assert any("Inception" in c["text"] for c in caps if c["type"] == "on_this_day")


def test_build_captions_recent_threshold():
    """Fewer than 3 ratings in the past 7 days should NOT produce a
    'recent' caption — under-threshold is uninteresting."""
    today = datetime.now(timezone.utc)
    items = [
        _enriched(timestamp=(today - timedelta(days=1)).isoformat()),
        _enriched(timestamp=(today - timedelta(days=2)).isoformat()),
    ]
    caps = StatsService._build_captions(items)
    types = [c["type"] for c in caps]
    assert "recent" not in types


def test_build_diary_payload_buckets_correctly():
    items = [
        _enriched(timestamp=_ts((2024, 3, 15)), rating=4.0, title="A", genres=["Drama"]),
        _enriched(timestamp=_ts((2024, 3, 16)), rating=5.0, title="B", genres=["Drama", "Sci-Fi"]),
        _enriched(timestamp=_ts((2025, 1, 5)), rating=3.5, title="C", genres=["Comedy"]),
    ]
    diary = StatsService._build_diary_payload(items)
    assert diary["year_chart"] == {"2024": 2, "2025": 1}
    assert "2024-03-15" in diary["heatmaps"]["2024"]
    assert diary["heatmaps"]["2025"]["2025-01-05"] == 1
    # Each month should appear in the highlight reel; B is the top of March
    # because it has the higher rating.
    march = next(h for h in diary["monthly_highlights"] if h["month"] == "2024-03")
    assert march["top_film"]["title"] == "B"
    assert march["dominant_genre"] == "Drama"


def test_normalize_personality_strips_empty_bullets():
    """LLM may return bullets with empty/whitespace entries — those drop."""
    parsed = {
        "teaser": "Sample teaser",
        "bullets": ["Real bullet", "", "  ", "Another"],
        "longform": {
            "longitudinal_arc": ["P1", "", "P3"],
            "dense_paragraph": "Dense.",
            "letter": "Dear viewer,",
            "quarterly_entries": [
                {"quarter": "2024 Q1", "text": "First quarter."},
                {"quarter": "", "text": "no quarter"},  # dropped
                {"quarter": "2024 Q2", "text": ""},     # dropped
            ],
        },
    }
    out = StatsService._normalize_personality(parsed)
    assert out["teaser"] == "Sample teaser"
    assert out["bullets"] == ["Real bullet", "Another"]
    assert out["longform"]["longitudinal_arc"] == ["P1", "P3"]
    assert len(out["longform"]["quarterly_entries"]) == 1


def test_normalize_personality_requires_teaser():
    """No teaser → drop the whole thing rather than emit half-baked output."""
    assert StatsService._normalize_personality({"bullets": ["x"]}) is None
    assert StatsService._normalize_personality({"teaser": "  "}) is None
    assert StatsService._normalize_personality("not a dict") is None
