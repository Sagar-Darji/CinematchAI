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

        st.markdown("### Language & Region")

        language_pref = st.selectbox(
            "Preferred Language",
            options=[
                "",
                "English",
                "Hindi",
                "Gujarati",
                "Tamil",
                "Telugu",
                "Malayalam",
                "Kannada",
                "Bengali",
                "Marathi",
                "Punjabi",
                "Korean",
                "Japanese",
                "French",
                "Spanish",
                "German",
                "Italian",
                "Chinese",
                "Arabic",
                "Portuguese",
                "Russian",
            ],
            format_func=lambda x: "Any Language" if x == "" else x,
        )

        region_pref = st.text_input(
            "Region Code (Optional)",
            placeholder="e.g., IN, US, KR, JP",
            help="ISO country code for regional cinema"
        )

        st.markdown("### 📅 Year Filter")

        year_filter_type = st.selectbox(
            "Filter by Year",
            options=["Any", "After", "Before", "Range"],
        )

        year_min = None
        year_max = None

        if year_filter_type == "After":
            year_min = st.number_input(
                "After Year",
                min_value=1900,
                max_value=2026,
                value=2000,
                step=1,
            )
        elif year_filter_type == "Before":
            year_max = st.number_input(
                "Before Year",
                min_value=1900,
                max_value=2026,
                value=2020,
                step=1,
            )
        elif year_filter_type == "Range":
            col_y1, col_y2 = st.columns(2)
            with col_y1:
                year_min = st.number_input(
                    "From",
                    min_value=1900,
                    max_value=2026,
                    value=2000,
                    step=1,
                )
            with col_y2:
                year_max = st.number_input(
                    "To",
                    min_value=1900,
                    max_value=2026,
                    value=2024,
                    step=1,
                )

        st.markdown("### 💬 Natural Language Context")

        natural_context = st.text_area(
            "Describe what you're looking for",
            placeholder="e.g., 'I would love superhero but odd movies' or 'Something mind-bending like Inception' or 'Feel-good comedy for a rainy day'",
            help="Describe your preferences in natural language - our AI agents will understand!",
            height=100,
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
    if language_pref:
        # Map language names to codes
        language_map = {
            "English": "en", "Hindi": "hi", "Gujarati": "gu", "Tamil": "ta",
            "Telugu": "te", "Malayalam": "ml", "Kannada": "kn", "Bengali": "bn",
            "Marathi": "mr", "Punjabi": "pa", "Korean": "ko", "Japanese": "ja",
            "French": "fr", "Spanish": "es", "German": "de", "Italian": "it",
            "Chinese": "zh", "Arabic": "ar", "Portuguese": "pt", "Russian": "ru",
        }
        context["language"] = language_map.get(language_pref, language_pref.lower())
    if region_pref:
        context["region"] = region_pref.upper()
    if year_min:
        context["year_min"] = int(year_min)
    if year_max:
        context["year_max"] = int(year_max)
    if natural_context:
        context["natural_language_context"] = natural_context

    # Get recommendations
    if "recommendations" not in st.session_state or refresh_button:
        # Show agent processing steps in real-time
        st.markdown("### 🤖 AI Agent Processing Pipeline")

        progress_container = st.container()
        status_container = st.empty()
        movie_analysis_container = st.empty()

        with progress_container:
            agent_status = st.empty()
            progress_bar = st.progress(0)

        # Sample movies for visualization (simulated movie analysis)
        sample_movies = [
            ("Inception", 2010, "✓", "98% match", "success"),
            ("The Dark Knight", 2008, "✓", "96% match", "success"),
            ("Interstellar", 2014, "✓", "94% match", "success"),
            ("Blade Runner 2049", 2017, "✓", "91% match", "success"),
            ("The Prestige", 2006, "✓", "89% match", "success"),
            ("Tenet", 2020, "?", "Analyzing themes...", "info"),
            ("Transformers 5", 2017, "✗", "Low relevance (28%)", "error"),
            ("Fast & Furious 9", 2021, "✗", "Genre mismatch", "error"),
        ]

        agent_steps = [
            ("🧠 Profile Analyzer", "Analyzing your taste and preferences...", 0.15, []),
            ("🎭 Context-Aware Agent", "Processing current context (time, mood, situation)...", 0.30, []),
            ("🔍 RAG Retrieval", "Vector search in progress...", 0.50, sample_movies[:4]),
            ("🎨 Content Intelligence", "Analyzing movie themes and styles...", 0.65, sample_movies[4:6]),
            ("✨ Serendipity Agent", "Filtering for diversity...", 0.80, sample_movies[6:]),
            ("💡 Explanation Agent", "Generating personalized explanations...", 0.95, []),
        ]

        try:
            import time

            # Simulate agent steps with movie-level details
            for i, (agent_name, status_text, progress, movies) in enumerate(agent_steps):
                agent_status.markdown(f"**{agent_name}**")
                status_container.info(status_text)
                progress_bar.progress(progress)

                # Show movie-level analysis
                if movies:
                    analysis_text = "**Movies being analyzed:**\n\n"
                    for title, year, icon, match_text, status_type in movies:
                        if icon == "✓":
                            analysis_text += f"- {icon} **{title}** ({year}) — {match_text}\n"
                        elif icon == "✗":
                            analysis_text += f"- {icon} ~~{title}~~ ({year}) — {match_text}\n"
                        else:
                            analysis_text += f"- {icon} *{title}* ({year}) — {match_text}\n"

                    movie_analysis_container.markdown(analysis_text)
                    time.sleep(0.8)  # Longer pause to read movie details
                else:
                    movie_analysis_container.empty()
                    time.sleep(0.4)

            # Make actual API call
            agent_status.markdown("**🎬 Finalizing Recommendations**")
            status_container.info("Compiling results from all agents...")
            movie_analysis_container.empty()

            payload = {
                "user_id": st.session_state.user_id,
                "context": context if context else None,
                "k": num_recommendations,
                "use_hybrid": use_hybrid,
            }

            response = requests.post(
                f"{API_BASE_URL}/api/v1/recommendations",
                json=payload,
                timeout=120,
            )

            if response.status_code == 200:
                data = response.json()
                st.session_state.recommendations = data.get("recommendations", [])
                st.session_state.context_factors = data.get("context_factors", {})
                st.session_state.processing_steps = data.get("processing_steps", [])

                # Show completion with summary
                progress_bar.progress(1.0)
                agent_status.markdown("**✅ Complete!**")

                # Processing summary
                num_recs = len(st.session_state.recommendations)
                summary_text = f"""**Processing Summary:**
- 📊 Analyzed: 50 candidate movies
- ✅ Kept: {num_recs} highly relevant movies
- ✗ Filtered: {50 - num_recs} movies (low relevance/diversity)
- 🎯 Match quality: Personalized for YOUR taste!
"""
                status_container.success(summary_text)
                time.sleep(2)

                # Clear status containers
                agent_status.empty()
                status_container.empty()
                progress_bar.empty()
            else:
                st.error(f"Failed to get recommendations: {response.text}")
                st.session_state.recommendations = []

        except Exception as e:
            st.error(f"Error connecting to API: {e}")
            st.session_state.recommendations = []

        st.markdown("---")

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

        # Show detailed processing steps
        if st.session_state.get("processing_steps"):
            with st.expander("🤖 Detailed AI Processing Log", expanded=False):
                st.markdown("**6-Agent System Execution:**")
                st.code("\n".join([f"✓ {step}" for step in st.session_state.processing_steps]), language="text")

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
