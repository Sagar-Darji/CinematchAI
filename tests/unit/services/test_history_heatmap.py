"""Tests for HistoryService.get_heatmap — the diary-heatmap data source."""

import uuid

from src.services.history_service import get_history_service


def _user() -> str:
    return f"test-heat-{uuid.uuid4().hex[:12]}"


def test_heatmap_groups_watches_by_day():
    svc = get_history_service()
    user_id = _user()
    try:
        # Three watches: two movies and a TV episode. Recorded with
        # CURRENT_TIMESTAMP, so they all bucket into "today" — the test asserts
        # we get a single date key with count >= 3, not specific dates.
        svc.record(user_id, 1, "movie", "A")
        svc.record(user_id, 2, "movie", "B")
        svc.record(user_id, 3, "tv", "C")

        from datetime import datetime, timezone
        year = datetime.now(timezone.utc).year
        counts = svc.get_heatmap(user_id, year)
        assert sum(counts.values()) == 3
        # All 3 records bucketed into one calendar day.
        assert len(counts) == 1
    finally:
        svc.clear(user_id)


def test_heatmap_filters_by_year():
    svc = get_history_service()
    user_id = _user()
    try:
        svc.record(user_id, 1, "movie", "A")
        # A different year should have zero entries even though the user has
        # records in another year.
        counts = svc.get_heatmap(user_id, 1995)
        assert counts == {}
    finally:
        svc.clear(user_id)


def test_heatmap_empty_for_unknown_user():
    svc = get_history_service()
    counts = svc.get_heatmap(f"nobody-{uuid.uuid4().hex}", 2026)
    assert counts == {}
