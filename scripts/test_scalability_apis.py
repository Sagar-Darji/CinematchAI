#!/usr/bin/env python3
"""Test script for new scalability APIs."""

import requests
import json
from typing import Dict, Any


BASE_URL = "http://localhost:8000/api/v1"


def print_response(title: str, response: requests.Response):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2)[:500] + "..." if len(json.dumps(data)) > 500 else json.dumps(data, indent=2))
        print("✅ Success")
    else:
        print(f"❌ Error: {response.text}")


def test_trending_movies():
    """Test trending movies endpoint."""
    # Trending this week
    response = requests.get(f"{BASE_URL}/movies/trending?time_window=week")
    print_response("Trending Movies (Week)", response)

    # Trending today
    response = requests.get(f"{BASE_URL}/movies/trending?time_window=day")
    print_response("Trending Movies (Day)", response)

    # Trending Hindi movies
    response = requests.get(f"{BASE_URL}/movies/trending?time_window=week&language=hi")
    print_response("Trending Hindi Movies", response)


def test_popular_by_language():
    """Test popular by language endpoint."""
    # Popular Bollywood
    response = requests.get(f"{BASE_URL}/movies/popular/hi?region=IN&limit=10")
    print_response("Popular Bollywood Movies", response)

    # Popular Korean
    response = requests.get(f"{BASE_URL}/movies/popular/ko?region=KR&limit=10")
    print_response("Popular Korean Movies", response)

    # Popular Japanese
    response = requests.get(f"{BASE_URL}/movies/popular/ja?region=JP&limit=10")
    print_response("Popular Japanese Movies", response)


def test_recent_releases():
    """Test recent releases endpoint."""
    # Recent releases (all)
    response = requests.get(f"{BASE_URL}/movies/recent?days=90")
    print_response("Recent Releases (90 days)", response)

    # Recent Hindi releases
    response = requests.get(f"{BASE_URL}/movies/recent?language=hi&region=IN&days=60")
    print_response("Recent Hindi Releases", response)


def test_search_movies():
    """Test movie search endpoint."""
    # Search Inception
    response = requests.get(f"{BASE_URL}/movies/search?query=Inception&limit=5")
    print_response("Search: Inception", response)

    # Search with year filter
    response = requests.get(f"{BASE_URL}/movies/search?query=Avatar&year=2009&limit=5")
    print_response("Search: Avatar (2009)", response)

    # Search Hindi movies
    response = requests.get(f"{BASE_URL}/movies/search?query=Dangal&language=hi&limit=5")
    print_response("Search: Dangal (Hindi)", response)


def test_movie_by_id():
    """Test get movie by ID endpoint."""
    # Fight Club (TMDB ID: 550)
    response = requests.get(f"{BASE_URL}/movies/550")
    print_response("Movie Details: Fight Club (ID: 550)", response)

    # The Dark Knight (TMDB ID: 155)
    response = requests.get(f"{BASE_URL}/movies/155")
    print_response("Movie Details: The Dark Knight (ID: 155)", response)


def test_letterboxd_import():
    """Test Letterboxd import endpoint."""
    # Sample CSV data
    csv_content = """Date,Name,Year,Letterboxd URI,Rating
2024-01-15,Inception,2010,https://letterboxd.com/film/inception/,4.5
2024-01-14,The Dark Knight,2008,https://letterboxd.com/film/the-dark-knight/,5.0
2024-01-13,Interstellar,2014,https://letterboxd.com/film/interstellar/,4.0
2024-01-12,Fight Club,1999,https://letterboxd.com/film/fight-club/,4.5
2024-01-11,Pulp Fiction,1994,https://letterboxd.com/film/pulp-fiction/,5.0"""

    payload = {
        "user_id": "test_user_scalability",
        "csv_content": csv_content
    }

    response = requests.post(
        f"{BASE_URL}/users/import/letterboxd",
        json=payload
    )
    print_response("Letterboxd Import", response)


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 Testing Scalability API Endpoints")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print("Make sure FastAPI server is running on port 8000!")
    print("Start with: python -m uvicorn src.api.main:app --reload --port 8000")

    try:
        # Check if server is running
        response = requests.get("http://localhost:8000/api/v1/health", timeout=2)
        if response.status_code != 200:
            print("\n❌ API server is not healthy!")
            return
        print("\n✅ API server is running")
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server!")
        print("Please start the server first:")
        print("python -m uvicorn src.api.main:app --reload --port 8000")
        return

    # Run tests
    print("\n" + "🎬"*20)
    print("\n1️⃣  Testing Trending Movies")
    test_trending_movies()

    print("\n" + "🎬"*20)
    print("\n2️⃣  Testing Popular by Language")
    test_popular_by_language()

    print("\n" + "🎬"*20)
    print("\n3️⃣  Testing Recent Releases")
    test_recent_releases()

    print("\n" + "🎬"*20)
    print("\n4️⃣  Testing Movie Search")
    test_search_movies()

    print("\n" + "🎬"*20)
    print("\n5️⃣  Testing Movie by ID")
    test_movie_by_id()

    print("\n" + "🎬"*20)
    print("\n6️⃣  Testing Letterboxd Import")
    test_letterboxd_import()

    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check results above for any errors")
    print("2. Review SCALABILITY_IMPROVEMENTS.md for integration guide")
    print("3. Update recommendation workflow for on-demand fetching")
    print("4. Update Streamlit UI with new features")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
