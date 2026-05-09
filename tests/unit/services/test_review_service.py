"""Tests for the reviews service — exercises the real local SQLite DB.

Each test uses a uuid-prefixed user_id so concurrent / repeated runs don't
collide, and cleans up its own rows.
"""

import uuid

import pytest

from src.services.review_service import ReviewService, get_review_service


def _user() -> str:
    return f"test-rev-{uuid.uuid4().hex[:12]}"


def test_upsert_and_get_round_trip():
    svc = get_review_service()
    user_id = _user()
    try:
        svc.upsert(user_id, 550, "movie", rating=4.5, review_text="Great")
        row = svc.get(user_id, 550, "movie")
        assert row is not None
        assert row["tmdb_id"] == 550
        assert row["media_type"] == "movie"
        assert row["rating"] == 4.5
        assert row["review_text"] == "Great"
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
    finally:
        svc.delete(user_id, 550, "movie")


def test_upsert_replaces_existing_and_preserves_created_at():
    svc = get_review_service()
    user_id = _user()
    try:
        svc.upsert(user_id, 680, "movie", rating=3.0)
        first = svc.get(user_id, 680, "movie")
        assert first is not None
        created_at = first["created_at"]

        svc.upsert(user_id, 680, "movie", rating=5.0, review_text="Reconsidered")
        second = svc.get(user_id, 680, "movie")
        assert second["rating"] == 5.0
        assert second["review_text"] == "Reconsidered"
        # created_at should not have changed even after the upsert.
        assert second["created_at"] == created_at
    finally:
        svc.delete(user_id, 680, "movie")


def test_list_by_user_orders_most_recent_first():
    import time
    svc = get_review_service()
    user_id = _user()
    try:
        # SQLite CURRENT_TIMESTAMP has 1-second resolution, so sleep enough
        # between writes to get distinct updated_at values.
        svc.upsert(user_id, 1, "movie", rating=3.0)
        time.sleep(1.05)
        svc.upsert(user_id, 2, "movie", rating=4.0)
        time.sleep(1.05)
        svc.upsert(user_id, 3, "tv", rating=4.5)
        items = svc.list_by_user(user_id)
        # Three entries, most recent (id=3) first.
        assert len(items) == 3
        assert items[0]["tmdb_id"] == 3
        assert items[0]["media_type"] == "tv"
    finally:
        for tid, mt in [(1, "movie"), (2, "movie"), (3, "tv")]:
            svc.delete(user_id, tid, mt)


def test_validation_requires_rating_or_text():
    svc = get_review_service()
    with pytest.raises(ValueError):
        svc.upsert(_user(), 1, "movie")
    with pytest.raises(ValueError):
        svc.upsert(_user(), 1, "movie", review_text="   ")


def test_validation_rejects_bad_rating_step():
    svc = get_review_service()
    with pytest.raises(ValueError):
        svc.upsert(_user(), 1, "movie", rating=4.3)


def test_validation_rejects_bad_media_type():
    svc = get_review_service()
    with pytest.raises(ValueError):
        svc.upsert(_user(), 1, "podcast", rating=3.0)


def test_delete_removes_row():
    svc = get_review_service()
    user_id = _user()
    svc.upsert(user_id, 42, "tv", rating=4.0)
    assert svc.get(user_id, 42, "tv") is not None
    svc.delete(user_id, 42, "tv")
    assert svc.get(user_id, 42, "tv") is None


def test_singleton_returns_same_instance():
    a = get_review_service()
    b = get_review_service()
    assert a is b
    assert isinstance(a, ReviewService)
