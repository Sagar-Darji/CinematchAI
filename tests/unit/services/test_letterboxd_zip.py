"""Unit tests for the Letterboxd ZIP extractor — the diary-date overlay,
reviews/watchlist/likes parsing, and tolerance for missing files."""

import io
import zipfile

import pandas as pd

from src.services.letterboxd_service import get_letterboxd_service


def _make_zip(files: dict[str, str]) -> bytes:
    """Build an in-memory ZIP from {arcname: csv_content_string}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, content in files.items():
            zf.writestr(arcname, content)
    return buf.getvalue()


def test_zip_extracts_ratings_only():
    """Bare ratings.csv (no diary) — should pass through with Date column intact."""
    ratings = (
        "Date,Name,Year,Letterboxd URI,Rating\n"
        "2024-01-15,Inception,2010,https://letterboxd.com/film/inception/,4.5\n"
        "2024-03-20,Stalker,1979,https://letterboxd.com/film/stalker/,5\n"
    )
    zip_bytes = _make_zip({"ratings.csv": ratings})
    result = get_letterboxd_service().extract_zip_export(zip_bytes)

    assert result["ratings_count"] == 2
    assert result["diary_count"] == 0
    merged = pd.read_csv(io.StringIO(result["merged_ratings_csv"]))
    assert list(merged["Name"]) == ["Inception", "Stalker"]
    # No overlay — Date stays as Letterboxd's rating-add date.
    assert merged.loc[0, "Date"] == "2024-01-15"


def test_diary_overlay_replaces_date_by_uri():
    """diary.csv's Watched Date should overwrite ratings.csv's Date when
    Letterboxd URI matches — that's the canonical join key."""
    ratings = (
        "Date,Name,Year,Letterboxd URI,Rating\n"
        "2026-01-01,Inception,2010,https://letterboxd.com/film/inception/,4.5\n"
        "2026-01-01,Stalker,1979,https://letterboxd.com/film/stalker/,5\n"
    )
    diary = (
        "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
        # Inception was actually watched on 2024-06-15
        "2026-01-01,Inception,2010,https://letterboxd.com/film/inception/,4.5,No,,2024-06-15\n"
        # Stalker is in diary too with a different watch date
        "2026-01-01,Stalker,1979,https://letterboxd.com/film/stalker/,5,No,,2023-11-02\n"
    )
    zip_bytes = _make_zip({"ratings.csv": ratings, "diary.csv": diary})
    result = get_letterboxd_service().extract_zip_export(zip_bytes)

    assert result["diary_count"] == 2
    merged = pd.read_csv(io.StringIO(result["merged_ratings_csv"]))
    # Both rows should have been overlaid with the real Watched Date.
    assert merged.loc[merged["Name"] == "Inception", "Date"].iloc[0] == "2024-06-15"
    assert merged.loc[merged["Name"] == "Stalker", "Date"].iloc[0] == "2023-11-02"


def test_diary_overlay_falls_back_to_name_year():
    """If a row has no URI match, the (Name, Year) fallback should still
    pull the Watched Date from diary."""
    ratings = (
        "Date,Name,Year,Letterboxd URI,Rating\n"
        "2026-01-01,Inception,2010,,4.5\n"  # no URI on ratings row
    )
    diary = (
        "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
        "2026-01-01,Inception,2010,https://letterboxd.com/film/inception/,4.5,No,,2024-06-15\n"
    )
    zip_bytes = _make_zip({"ratings.csv": ratings, "diary.csv": diary})
    result = get_letterboxd_service().extract_zip_export(zip_bytes)
    merged = pd.read_csv(io.StringIO(result["merged_ratings_csv"]))
    assert merged.loc[0, "Date"] == "2024-06-15"
    assert result["diary_count"] == 1


def test_ratings_without_diary_overlay_keeps_original_date():
    """A row with no diary match keeps its rating-add date — falling back
    to whatever was in ratings.csv. No 'None' strings, no NaN leaks."""
    ratings = (
        "Date,Name,Year,Letterboxd URI,Rating\n"
        "2026-01-01,Inception,2010,https://letterboxd.com/film/inception/,4.5\n"
        "2026-02-01,Solaris,1972,https://letterboxd.com/film/solaris/,5\n"
    )
    diary = (
        # Only Inception is in the diary; Solaris isn't.
        "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
        "2026-01-01,Inception,2010,https://letterboxd.com/film/inception/,4.5,No,,2024-06-15\n"
    )
    zip_bytes = _make_zip({"ratings.csv": ratings, "diary.csv": diary})
    result = get_letterboxd_service().extract_zip_export(zip_bytes)
    merged = pd.read_csv(io.StringIO(result["merged_ratings_csv"]))
    inception_date = merged.loc[merged["Name"] == "Inception", "Date"].iloc[0]
    solaris_date = merged.loc[merged["Name"] == "Solaris", "Date"].iloc[0]
    assert inception_date == "2024-06-15"
    assert solaris_date == "2026-02-01"


def test_parses_reviews_watchlist_likes():
    """Optional sections should parse cleanly. Empty review_text rows skip;
    name-less rows skip; everything else surfaces with name/year/uri."""
    ratings = (
        "Date,Name,Year,Letterboxd URI,Rating\n"
        "2024-01-15,Inception,2010,https://letterboxd.com/film/inception/,4.5\n"
    )
    reviews = (
        "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Review,Tags,Watched Date\n"
        "2024-01-15,Inception,2010,https://letterboxd.com/film/inception/,4.5,No,\"Mind-bending.\",heist,2024-01-15\n"
        # Empty review — should be dropped.
        "2024-02-01,Tenet,2020,https://letterboxd.com/film/tenet/,3,No,,thriller,2024-02-01\n"
    )
    watchlist = (
        "Date,Name,Year,Letterboxd URI\n"
        "2024-03-01,The Brutalist,2024,https://letterboxd.com/film/the-brutalist/\n"
    )
    likes_films = (
        "Date,Name,Year,Letterboxd URI\n"
        "2024-04-01,Stalker,1979,https://letterboxd.com/film/stalker/\n"
        "2024-04-01,Solaris,1972,https://letterboxd.com/film/solaris/\n"
    )
    zip_bytes = _make_zip({
        "ratings.csv": ratings,
        "reviews.csv": reviews,
        "watchlist.csv": watchlist,
        "likes/films.csv": likes_films,
    })
    result = get_letterboxd_service().extract_zip_export(zip_bytes)

    assert len(result["reviews"]) == 1
    assert result["reviews"][0]["name"] == "Inception"
    assert result["reviews"][0]["review_text"] == "Mind-bending."
    assert result["reviews"][0]["rating"] == 4.5

    assert len(result["watchlist"]) == 1
    assert result["watchlist"][0]["name"] == "The Brutalist"
    assert result["watchlist"][0]["year"] == 2024

    assert len(result["likes"]) == 2
    assert {item["name"] for item in result["likes"]} == {"Stalker", "Solaris"}


def test_missing_ratings_returns_null_csv():
    """A ZIP with only watchlist/likes (no ratings.csv) returns
    merged_ratings_csv=None so the caller can reject the upload."""
    zip_bytes = _make_zip({
        "watchlist.csv": "Date,Name,Year,Letterboxd URI\n2024-01-01,Test,2024,https://x/\n",
    })
    result = get_letterboxd_service().extract_zip_export(zip_bytes)
    assert result["merged_ratings_csv"] is None
    assert result["ratings_count"] == 0
    assert len(result["watchlist"]) == 1


def test_bad_zip_raises_value_error():
    import pytest
    with pytest.raises(ValueError):
        get_letterboxd_service().extract_zip_export(b"not a zip")
