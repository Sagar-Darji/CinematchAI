"""Recommendations Page - Main recommendation interface."""

import streamlit as st
import requests
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.ui.components.movie_card import render_movie_card
from src.ui.components.onboarding import render_onboarding_flow

st.set_page_config(page_title="Recommendations - CineMatch AI", page_icon="🎬", layout="wide")

API_BASE_URL = "http://localhost:8000"

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

# Header
st.title("🎬 Your Personalized Recommendations")

# Check if user is onboarded
if not st.session_state.onboarded:
    st.info("👋 Welcome! Let's get you started with a quick onboarding.")
    onboarding_complete = render_onboarding_flow()

    if onboarding_complete:
        st.rerun()
else:
    # User is onboarded - show recommendations
    st.markdown(f"**Welcome, {st.session_state.user_id}!**")

    # Context filters in sidebar
    with st.sidebar:
        st.markdown("## 🎯 Customize Your Recommendations")

        st.markdown("### Context")

        time_of_day = st.selectbox(
            "Time of Day",
            options=["", "morning", "afternoon", "evening", "night"],
            format_func=lambda x: "Auto-detect" if x == "" else x.title(),
        )

        mood = st.selectbox(
            "Current Mood",
            options=[
                "",
                "happy",
                "sad",
                "stressed",
                "bored",
                "thoughtful",
                "energetic",
                "nostalgic",
                "adventurous",
            ],
            format_func=lambda x: "Any" if x == "" else x.title(),
        )

        companion = st.selectbox(
            "Watching With",
            options=["", "alone", "partner", "friends", "family"],
            format_func=lambda x: "Anyone" if x == "" else x.title(),
        )

        st.markdown("### Preferences")

        num_recommendations = st.slider(
            "Number of Recommendations",
            min_value=5,
            max_value=20,
            value=10,
        )

        use_hybrid = st.checkbox(
            "Use Visual Analysis (Poster Aesthetics)",
            value=True,
            help="Includes poster image analysis in recommendations",
        )

        st.markdown("---")

        refresh_button = st.button("🔄 Refresh Recommendations", use_container_width=True)

    # Build context dict
    context = {}
    if time_of_day:
        context["time_of_day"] = time_of_day
    if mood:
        context["mood"] = mood
    if companion:
        context["companion"] = companion

    # Get recommendations
    if "recommendations" not in st.session_state or refresh_button:
        with st.spinner("🎬 Analyzing your preferences and generating recommendations..."):
            try:
                payload = {
                    "user_id": st.session_state.user_id,
                    "context": context if context else None,
                    "k": num_recommendations,
                    "use_hybrid": use_hybrid,
                }

                response = requests.post(
                    f"{API_BASE_URL}/api/v1/recommendations",
                    json=payload,
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    st.session_state.recommendations = data.get("recommendations", [])
                    st.session_state.context_factors = data.get("context_factors", {})
                    st.session_state.processing_steps = data.get("processing_steps", [])
                else:
                    st.error(f"Failed to get recommendations: {response.text}")
                    st.session_state.recommendations = []

            except Exception as e:
                st.error(f"Error connecting to API: {e}")
                st.session_state.recommendations = []

    recommendations = st.session_state.get("recommendations", [])

    if recommendations:
        # Show context factors
        if st.session_state.get("context_factors"):
            with st.expander("🔍 Detected Context", expanded=False):
                context_factors = st.session_state.context_factors
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Time of Day", context_factors.get("time_of_day", "N/A").title())
                with col2:
                    st.metric("Day", context_factors.get("day_of_week", "N/A"))
                with col3:
                    st.metric("Season", context_factors.get("season", "N/A").title())

        # Show processing steps
        if st.session_state.get("processing_steps"):
            with st.expander("🤖 AI Processing Pipeline", expanded=False):
                for step in st.session_state.processing_steps:
                    st.text(f"✓ {step}")

        st.markdown("---")
        st.markdown(f"### 🎯 Top {len(recommendations)} Recommendations")

        # Display recommendations
        for rec in recommendations:
            movie = rec.get("movie", {})
            explanation = rec.get("explanation", "")
            rank = rec.get("rank", 0)
            score = rec.get("score", 0.0)
            is_exploration = rec.get("is_exploration", False)

            render_movie_card(
                movie=movie,
                explanation=explanation,
                rank=rank,
                score=score,
                is_exploration=is_exploration,
            )

            # Rating feedback
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.markdown("*How do you feel about this recommendation?*")

            with col2:
                if st.button("👍 Loved it!", key=f"love_{movie.get('tmdb_id')}"):
                    _submit_feedback(movie.get("tmdb_id"), 5.0)

            with col3:
                if st.button("👎 Not for me", key=f"dislike_{movie.get('tmdb_id')}"):
                    _submit_feedback(movie.get("tmdb_id"), 1.0)

            st.markdown("---")

    else:
        st.info("No recommendations available. Click 'Refresh Recommendations' to generate.")


def _submit_feedback(movie_id: int, rating: float):
    """Submit user feedback."""
    try:
        payload = {
            "user_id": st.session_state.user_id,
            "movie_id": str(movie_id),
            "rating": rating,
            "watched": False,  # Feedback, not watched yet
        }

        response = requests.post(
            f"{API_BASE_URL}/api/v1/users/feedback",
            json=payload,
            timeout=10,
        )

        if response.status_code == 200:
            st.toast("✅ Feedback saved! Your profile will improve.")
        else:
            st.error("Failed to save feedback")

    except Exception as e:
        st.error(f"Error: {e}")
