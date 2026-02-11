"""Test script for CineMatch AI API endpoints."""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def print_response(response: requests.Response, title: str):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"📝 {title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print(f"{'='*60}\n")


def test_health():
    """Test health check endpoint."""
    response = requests.get(f"{BASE_URL}/api/v1/health")
    print_response(response, "Health Check")
    return response.status_code == 200


def test_root():
    """Test root endpoint."""
    response = requests.get(f"{BASE_URL}/")
    print_response(response, "Root Endpoint")
    return response.status_code == 200


def test_onboarding_movies():
    """Test getting onboarding movies."""
    response = requests.get(f"{BASE_URL}/api/v1/users/onboarding-movies?k=5")
    print_response(response, "Get Onboarding Movies")
    return response.status_code == 200


def test_onboarding():
    """Test user onboarding."""
    payload = {
        "user_id": "test_user_123",
        "ratings": {
            "550": 5.0,    # Fight Club
            "680": 4.5,    # Pulp Fiction
            "13": 4.0,     # Forrest Gump
            "155": 3.5,    # The Dark Knight
            "278": 5.0,    # The Shawshank Redemption
        },
        "preferences": {
            "favorite_genres": ["Drama", "Thriller"],
            "disliked_genres": ["Horror"],
        },
    }

    response = requests.post(f"{BASE_URL}/api/v1/users/onboard", json=payload)
    print_response(response, "User Onboarding")
    return response.status_code in [200, 201]


def test_recommendations():
    """Test single-user recommendations."""
    payload = {
        "user_id": "test_user_123",
        "context": {
            "time_of_day": "evening",
            "mood": "relaxed",
            "companion": "alone",
        },
        "k": 5,
        "use_hybrid": True,
    }

    response = requests.post(f"{BASE_URL}/api/v1/recommendations", json=payload)
    print_response(response, "Single-User Recommendations")
    return response.status_code == 200


def test_feedback():
    """Test submitting feedback."""
    payload = {
        "user_id": "test_user_123",
        "movie_id": "550",
        "rating": 4.5,
        "watched": True,
    }

    response = requests.post(f"{BASE_URL}/api/v1/users/feedback", json=payload)
    print_response(response, "Submit Feedback")
    return response.status_code == 200


def test_group_recommendations():
    """Test group recommendations."""
    payload = {
        "user_ids": ["test_user_123", "test_user_456", "test_user_789"],
        "context": {
            "companion": "friends",
            "occasion": "movie_night",
        },
        "aggregation_strategy": "multiplicative",
        "k": 5,
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/groups/recommendations", json=payload
    )
    print_response(response, "Group Recommendations")
    return response.status_code == 200


def main():
    """Run all API tests."""
    print("\n🧪 CineMatch AI API Test Suite")
    print("=" * 60)
    print(f"Testing API at: {BASE_URL}")
    print("=" * 60)

    tests = [
        ("Health Check", test_health),
        ("Root Endpoint", test_root),
        ("Onboarding Movies", test_onboarding_movies),
        ("User Onboarding", test_onboarding),
        ("Single-User Recommendations", test_recommendations),
        ("Submit Feedback", test_feedback),
        ("Group Recommendations", test_group_recommendations),
    ]

    results = {}

    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}...")
        try:
            success = test_func()
            results[test_name] = "✅ PASSED" if success else "❌ FAILED"
        except Exception as e:
            print(f"❌ Error: {e}")
            results[test_name] = f"❌ ERROR: {str(e)}"

    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    for test_name, result in results.items():
        print(f"{result} - {test_name}")

    passed = sum(1 for r in results.values() if "PASSED" in r)
    total = len(results)

    print(f"\n✨ {passed}/{total} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
