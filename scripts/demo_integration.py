#!/usr/bin/env python3
"""
Demo script to showcase scalability integration.

Run this to see the new features in action!
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_on_demand_enrichment():
    """Demo on-demand movie enrichment."""
    print_section("🎬 Demo 1: On-Demand Movie Enrichment")

    from src.services.movie_service import get_movie_service

    movie_service = get_movie_service()

    print("Fetching 'Inception' (TMDB ID: 27205) on-demand from TMDB API...")
    time.sleep(0.5)

    movie = movie_service.get_movie_by_id(tmdb_id=27205)

    if movie:
        print("\n✅ Movie fetched successfully!")
        print(f"\nTitle: {movie.metadata.title}")
        print(f"Year: {movie.metadata.year}")
        print(f"Director: {movie.metadata.director}")
        print(f"Genres: {', '.join(movie.metadata.genres)}")
        print(f"Rating: {movie.metadata.vote_average}/10")
        print(f"Cast: {', '.join(movie.metadata.cast[:3])}")
        print(f"\nOverview: {movie.metadata.overview[:200]}...")
        print(f"\n💾 Cached for 24 hours - next request will be instant!")
    else:
        print("❌ Failed to fetch movie")


def demo_trending_movies():
    """Demo trending movies retrieval."""
    print_section("🔥 Demo 2: Trending Movies This Week")

    from src.services.movie_service import get_movie_service

    movie_service = get_movie_service()

    print("Fetching trending movies from TMDB API...")
    time.sleep(0.5)

    movies = movie_service.get_trending_movies(time_window="week")

    if movies:
        print(f"\n✅ Retrieved {len(movies)} trending movies!")
        print("\nTop 5 Trending:")
        for i, movie in enumerate(movies[:5], 1):
            print(
                f"  {i}. {movie.metadata.title} ({movie.metadata.year}) - ⭐ {movie.metadata.vote_average:.1f}/10"
            )
        print(f"\n💾 Cached for 1 hour - reflects current popular culture!")
    else:
        print("❌ Failed to fetch trending movies")


def demo_regional_cinema():
    """Demo regional cinema support."""
    print_section("🌍 Demo 3: Regional Cinema Support")

    from src.services.movie_service import get_movie_service

    movie_service = get_movie_service()

    regions = [
        ("hi", "IN", "Bollywood"),
        ("ko", "KR", "Korean"),
        ("ja", "JP", "Japanese"),
    ]

    for lang, region, name in regions:
        print(f"\nFetching popular {name} movies...")
        time.sleep(0.5)

        movies = movie_service.get_popular_by_language(
            language=lang,
            region=region,
            limit=3,
        )

        if movies:
            print(f"✅ Top 3 {name} movies:")
            for i, movie in enumerate(movies, 1):
                rating = (
                    f"⭐ {movie.metadata.vote_average:.1f}/10"
                    if movie.metadata.vote_average
                    else "N/A"
                )
                print(
                    f"  {i}. {movie.metadata.title} ({movie.metadata.year}) - {rating}"
                )
        else:
            print(f"❌ Failed to fetch {name} movies")


def demo_on_demand_retrieval():
    """Demo on-demand retrieval in workflow."""
    print_section("🔍 Demo 4: On-Demand Retrieval in Workflow")

    from src.agents.graph.tools import retrieve_on_demand_movies

    print("Retrieving movies on-demand for context: language=hi, region=IN...")
    time.sleep(0.5)

    movies = retrieve_on_demand_movies(language="hi", region="IN", k=10)

    if movies:
        print(f"\n✅ Retrieved {len(movies)} movies on-demand!")
        print(f"   • Half from trending")
        print(f"   • Half from popular Hindi/India")
        print(f"\nSample movies:")
        for i, movie in enumerate(movies[:5], 1):
            print(
                f"  {i}. {movie.metadata.title} ({movie.metadata.year}) - {', '.join(movie.metadata.genres[:2])}"
            )
        print(f"\n🚀 This supports UNLIMITED movies from TMDB API!")
    else:
        print("❌ Failed to retrieve movies")


def demo_cold_start():
    """Demo cold-start retrieval."""
    print_section("❄️ Demo 5: Enhanced Cold-Start Retrieval")

    from src.agents.graph.tools import cold_start_retrieval

    print("Simulating cold-start for new user...")
    time.sleep(0.5)

    state = {"context": {"language": "en"}}
    state = cold_start_retrieval(state)

    candidate_movies = state.get("candidate_movies", [])

    if candidate_movies:
        print(f"\n✅ Cold-start retrieval: {len(candidate_movies)} diverse candidates!")
        print("\nFirst 5 movies for onboarding:")
        for i, movie in enumerate(candidate_movies[:5], 1):
            genres = ", ".join(movie.metadata.genres[:2])
            print(
                f"  {i}. {movie.metadata.title} ({movie.metadata.year}) - {genres}"
            )
        print(
            f"\n🎯 Perfect for onboarding - diverse, popular, trending!"
        )
    else:
        print("❌ Failed cold-start retrieval")


def demo_letterboxd_import():
    """Demo Letterboxd import capability."""
    print_section("📥 Demo 6: Letterboxd Import (API)")

    print("This feature allows users to import their Letterboxd history!")
    print("\nExample CSV format:")
    print("-" * 70)
    print("Date,Name,Year,Letterboxd URI,Rating")
    print("2024-01-15,Inception,2010,https://letterboxd.com/film/inception/,4.5")
    print("2024-01-14,The Dark Knight,2008,...,5.0")
    print("2024-01-13,Interstellar,2014,...,4.0")
    print("-" * 70)

    print("\n✅ API Endpoint: POST /api/v1/users/import/letterboxd")
    print("\nBenefits:")
    print("  • Instant onboarding (import hundreds of ratings)")
    print("  • No manual rating required")
    print("  • Preserves existing user history")
    print("  • Competitive with Letterboxd!")

    print("\n💡 Test with:")
    print('   python scripts/test_scalability_apis.py')


def main():
    """Run all demos."""
    print("\n" + "🎬" * 35)
    print("\n  CineMatch AI - Scalability Integration Demo")
    print("  " + "-" * 66)
    print("  From 1,000 movies → Millions of movies")
    print("  From static data → Live TMDB API")
    print("  From English-only → Global (100+ languages)")
    print("\n" + "🎬" * 35)

    print("\n⚠️  Note: Some demos require API server running:")
    print("   python -m uvicorn src.api.main:app --reload --port 8000")

    # Support non-interactive mode
    import os
    interactive = os.isatty(0)
    if interactive:
        input("\nPress Enter to start demos...")

    try:
        # Demo 1: On-demand enrichment
        demo_on_demand_enrichment()
        if interactive:
            input("\nPress Enter to continue...")

        # Demo 2: Trending movies
        demo_trending_movies()
        if interactive:
            input("\nPress Enter to continue...")

        # Demo 3: Regional cinema
        demo_regional_cinema()
        if interactive:
            input("\nPress Enter to continue...")

        # Demo 4: On-demand retrieval
        demo_on_demand_retrieval()
        if interactive:
            input("\nPress Enter to continue...")

        # Demo 5: Cold-start
        demo_cold_start()
        if interactive:
            input("\nPress Enter to continue...")

        # Demo 6: Letterboxd import
        demo_letterboxd_import()

        print("\n" + "=" * 70)
        print("  ✅ All Demos Complete!")
        print("=" * 70)

        print("\n🚀 Next Steps:")
        print("  1. Test API endpoints: python scripts/test_scalability_apis.py")

        print("  3. See trending movies on homepage!")
        print("  4. Read INTEGRATION_COMPLETE.md for details")

        print("\n🏆 CineMatch AI is now production-grade!")
        print("   Scalable • Fresh • Global • Intelligent\n")

    except KeyboardInterrupt:
        print("\n\n❌ Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during demo: {e}")
        print("Make sure API server is running:")
        print("  python -m uvicorn src.api.main:app --reload --port 8000")


if __name__ == "__main__":
    main()
