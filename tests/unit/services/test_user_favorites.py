"""Tests for UserService.get_favorites / set_favorites."""

import uuid

import pytest

from src.services.user_service import UserService, get_user_service


def _user(svc: UserService) -> str:
    user_id = f"test-fav-{uuid.uuid4().hex[:12]}"
    svc.create_user_stub(user_id)
    return user_id


def test_favorites_round_trip():
    svc = get_user_service()
    user_id = _user(svc)
    items = [
        {"tmdb_id": 680, "media_type": "movie", "title": "Pulp Fiction", "poster_path": "/x.jpg"},
        {"tmdb_id": 1396, "media_type": "tv", "title": "Breaking Bad", "poster_path": "/bb.jpg"},
    ]
    saved = svc.set_favorites(user_id, items)
    assert saved == items
    assert svc.get_favorites(user_id) == items


def test_favorites_caps_at_four():
    svc = get_user_service()
    user_id = _user(svc)
    items = [
        {"tmdb_id": i, "media_type": "movie", "title": f"M{i}"} for i in range(1, 7)
    ]
    saved = svc.set_favorites(user_id, items)
    assert len(saved) == 4
    assert [i["tmdb_id"] for i in saved] == [1, 2, 3, 4]


def test_favorites_dedupe_preserves_first_occurrence():
    svc = get_user_service()
    user_id = _user(svc)
    items = [
        {"tmdb_id": 1, "media_type": "movie", "title": "A"},
        {"tmdb_id": 1, "media_type": "movie", "title": "A duplicate"},
        {"tmdb_id": 1, "media_type": "tv", "title": "A but different media"},
    ]
    saved = svc.set_favorites(user_id, items)
    assert len(saved) == 2
    assert saved[0]["title"] == "A"
    assert saved[1]["media_type"] == "tv"


def test_favorites_validates_shape():
    svc = get_user_service()
    user_id = _user(svc)
    with pytest.raises(ValueError):
        svc.set_favorites(user_id, [{"tmdb_id": "nope", "media_type": "movie", "title": "X"}])
    with pytest.raises(ValueError):
        svc.set_favorites(user_id, [{"tmdb_id": 1, "media_type": "audiobook", "title": "X"}])
    with pytest.raises(ValueError):
        svc.set_favorites(user_id, [{"tmdb_id": 1, "media_type": "movie"}])  # missing title


def test_favorites_empty_for_unknown_user():
    svc = get_user_service()
    assert svc.get_favorites(f"nobody-{uuid.uuid4().hex}") == []


def test_set_empty_clears_favorites():
    svc = get_user_service()
    user_id = _user(svc)
    svc.set_favorites(user_id, [{"tmdb_id": 1, "media_type": "movie", "title": "A"}])
    assert len(svc.get_favorites(user_id)) == 1
    svc.set_favorites(user_id, [])
    assert svc.get_favorites(user_id) == []
