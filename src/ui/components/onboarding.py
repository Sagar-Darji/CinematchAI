"""Onboarding Component - Interactive cold-start flow."""

import streamlit as st
import requests
from typing import Dict, List


API_BASE_URL = "http://localhost:8000"


def render_onboarding_flow():
    """
    Render interactive onboarding flow for new users.

    Returns:
        Boolean indicating if onboarding is complete.
    """
    st.markdown("## 🎬 Welcome to CineMatch AI!")
    st.markdown(
        """
        To get started, we need to understand your movie preferences.
        **Rate at least 5 movies** below, and we'll create your personalized profile.
        """
    )

    # Initialize session state for ratings
    if "onboarding_ratings" not in st.session_state:
        st.session_state.onboarding_ratings = {}

    if "onboarding_movies" not in st.session_state:
        # Fetch onboarding movies
        with st.spinner("Loading movies..."):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/api/v1/users/onboarding-movies?k=20",
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    st.session_state.onboarding_movies = data.get("movies", [])
                else:
                    st.error("Failed to load onboarding movies")
                    st.session_state.onboarding_movies = []

            except Exception as e:
                st.error(f"Error connecting to API: {e}")
                st.session_state.onboarding_movies = _get_fallback_movies()

    movies = st.session_state.onboarding_movies

    if not movies:
        st.warning("No movies available for onboarding")
        return False

    # Display movies for rating
    st.markdown("### Rate These Movies")
    st.markdown("*Select a star rating (1-5) for movies you've seen*")

    # Progress indicator
    rated_count = len(st.session_state.onboarding_ratings)
    progress_text = f"Progress: {rated_count}/5 minimum ({rated_count} rated)"
    st.progress(
        min(rated_count / 5, 1.0),
        text=progress_text,
    )

    # Display movies in grid
    for i in range(0, min(len(movies), 20), 2):
        cols = st.columns(2)

        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(movies):
                movie = movies[idx]
                movie_id = str(movie.get("tmdb_id", ""))

                with col:
                    _render_rating_card(movie, movie_id)

    # Completion section
    st.markdown("---")

    if rated_count >= 5:
        st.success(f"✅ Great! You've rated {rated_count} movies.")

        # User ID input
        user_id = st.text_input(
            "Enter your username:",
            value="",
            placeholder="e.g., john_doe",
            key="onboarding_user_id",
        )

        if st.button("🚀 Complete Onboarding", type="primary", use_container_width=True):
            if not user_id:
                st.error("Please enter a username")
            else:
                return _complete_onboarding(user_id, st.session_state.onboarding_ratings)
    else:
        st.info(f"📝 Please rate at least {5 - rated_count} more movie(s) to continue.")

    return False


def _render_rating_card(movie: Dict, movie_id: str):
    """Render a single movie rating card."""
    with st.container():
        # Movie info
        title = movie.get("title", "Unknown")
        year = movie.get("year", "")
        genres = movie.get("genres", [])

        st.markdown(f"**{title}** ({year})")
        if genres:
            st.caption(f"🎭 {', '.join(genres[:2])}")

        # Rating selector
        current_rating = st.session_state.onboarding_ratings.get(movie_id, 0)

        rating = st.select_slider(
            "Rating",
            options=[0, 1, 2, 3, 4, 5],
            value=current_rating,
            format_func=lambda x: "⭐" * x if x > 0 else "Not Rated",
            key=f"rating_{movie_id}",
            label_visibility="collapsed",
        )

        # Update session state
        if rating > 0:
            st.session_state.onboarding_ratings[movie_id] = float(rating)
        elif movie_id in st.session_state.onboarding_ratings:
            del st.session_state.onboarding_ratings[movie_id]


def _complete_onboarding(user_id: str, ratings: Dict[str, float]) -> bool:
    """
    Complete onboarding by submitting to API.

    Args:
        user_id: User ID.
        ratings: Movie ratings (movie_id -> rating).

    Returns:
        True if successful.
    """
    with st.spinner("Creating your profile..."):
        try:
            payload = {
                "user_id": user_id,
                "ratings": ratings,
            }

            response = requests.post(
                f"{API_BASE_URL}/api/v1/users/onboard",
                json=payload,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                st.success("✅ Onboarding complete! Redirecting...")

                # Save user ID to session
                st.session_state.user_id = user_id
                st.session_state.onboarded = True

                # Clear onboarding data
                del st.session_state.onboarding_ratings
                del st.session_state.onboarding_movies

                st.rerun()
                return True
            else:
                st.error(f"Failed to onboard: {response.text}")
                return False

        except Exception as e:
            st.error(f"Error: {e}")
            return False


def _get_fallback_movies() -> List[Dict]:
    """Get fallback movies if API is unavailable."""
    return [
        {
            "tmdb_id": 550,
            "title": "Fight Club",
            "year": 1999,
            "genres": ["Drama"],
        },
        {
            "tmdb_id": 680,
            "title": "Pulp Fiction",
            "year": 1994,
            "genres": ["Crime", "Drama"],
        },
        {
            "tmdb_id": 13,
            "title": "Forrest Gump",
            "year": 1994,
            "genres": ["Comedy", "Drama", "Romance"],
        },
        {
            "tmdb_id": 155,
            "title": "The Dark Knight",
            "year": 2008,
            "genres": ["Action", "Crime", "Drama"],
        },
        {
            "tmdb_id": 278,
            "title": "The Shawshank Redemption",
            "year": 1994,
            "genres": ["Drama"],
        },
    ]
