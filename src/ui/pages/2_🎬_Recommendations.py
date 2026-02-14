"""Recommendations Page - Main recommendation interface."""

import time
import streamlit as st
import requests
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.ui.components.movie_card import render_movie_card
from src.ui.components.onboarding import render_onboarding_flow
from src.ui.session import restore_streamlit_session
from src.ui.styles import inject_cinema_theme

st.set_page_config(page_title="Recommendations - CineMatch AI", page_icon="🎬", layout="wide")
inject_cinema_theme()

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
            st.toast("Feedback saved! Your profile will improve.")
        else:
            st.error("Failed to save feedback")

    except Exception as e:
        st.error(f"Error: {e}")


# Restore persistent session
restore_streamlit_session()

# Header
st.title("🎬 Your Personalized Recommendations")

# Check if user is onboarded
if not st.session_state.onboarded:
    st.info("Welcome! Let's get you started with a quick onboarding.")
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
        st.markdown("### 🤖 AI Agent Processing Pipeline")

        progress_container = st.container()
        status_container = st.empty()

        # Agent step icons and labels
        AGENT_ICONS = {
            "Profile Analyzer": "🧠",
            "Context-Aware": "🌍",
            "Retrieval": "🔍",
            "Content Intelligence": "🎯",
            "Serendipity": "✨",
            "Explanation": "💬",
            "Aggregation": "📊",
            "Supervisor": "👁️",
        }

        trace_placeholder = st.empty()
        status_placeholder = st.empty()

        def _render_trace(steps_so_far, running_step=None):
            lines = ["**🎬 CineMatch is thinking...**\n"]
            for s in steps_so_far:
                icon = AGENT_ICONS.get(s["step"], "✅")
                lines.append(f"{icon} **{s['step']}** — {s['detail']}")
            if running_step:
                icon = AGENT_ICONS.get(running_step, "⚙️")
                lines.append(f"{icon} **{running_step}** — *(processing...)*")
            trace_placeholder.markdown("\n\n".join(lines))

        try:
            payload = {
                "user_id": st.session_state.user_id,
                "context": context if context else None,
                "k": num_recommendations,
                "use_hybrid": use_hybrid,
            }

            # 1. Submit async job
            submit_resp = requests.post(
                f"{API_BASE_URL}/api/v1/recommendations/async",
                json=payload,
                timeout=15,
            )
            if submit_resp.status_code not in (200, 202):
                st.error(f"Failed to submit job: {submit_resp.text}")
                st.session_state.recommendations = []
                st.stop()

            job_id = submit_resp.json()["job_id"]
            _render_trace([], running_step="Profile Analyzer")

            # 2. Poll for results with live trace updates
            deadline = time.time() + 120
            seen_steps = 0

            while time.time() < deadline:
                poll = requests.get(
                    f"{API_BASE_URL}/api/v1/recommendations/result/{job_id}",
                    timeout=10,
                )
                if poll.status_code != 200:
                    break

                data = poll.json()
                steps = data.get("steps", [])

                # Show any new steps
                if len(steps) > seen_steps:
                    seen_steps = len(steps)
                    next_agents = ["Profile Analyzer", "Context-Aware", "Retrieval",
                                   "Content Intelligence", "Serendipity", "Explanation", "Aggregation"]
                    running = next_agents[seen_steps] if seen_steps < len(next_agents) else None
                    _render_trace(steps, running_step=running)

                job_status = data.get("status")
                if job_status == "complete":
                    result = data.get("result", {})
                    st.session_state.recommendations = result.get("recommendations", [])
                    st.session_state.context_factors = result.get("context_factors", {})
                    st.session_state.processing_steps = result.get("processing_steps", [])
                    st.session_state.trace_id = result.get("trace_id")
                    _render_trace(steps)
                    num_recs = len(st.session_state.recommendations)
                    status_placeholder.success(f"✅ Pipeline complete — {num_recs} recommendations ready!")
                    time.sleep(1.5)
                    trace_placeholder.empty()
                    status_placeholder.empty()
                    break
                elif job_status == "failed":
                    st.error(f"Pipeline failed: {data.get('error', 'unknown error')}")
                    st.session_state.recommendations = []
                    break

                time.sleep(0.5)
            else:
                st.error("Timed out waiting for recommendations.")
                st.session_state.recommendations = []

        except Exception as e:
            st.error(f"Error connecting to API: {e}")
            st.session_state.recommendations = []

        st.markdown("---")

    recommendations = st.session_state.get("recommendations", [])

    if recommendations:
        # Data source badge & trace info
        trace_id = st.session_state.get("trace_id")
        if trace_id:
            # Fetch trace to get data source
            try:
                trace_resp = requests.get(
                    f"{API_BASE_URL}/api/v1/admin/traces/{trace_id}",
                    timeout=5,
                )
                if trace_resp.status_code == 200:
                    trace_data = trace_resp.json()
                    source = trace_data.get("retrieval_source", "unknown")
                    duration = trace_data.get("total_duration_ms")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if source == "chromadb_personalized":
                            st.success("Data Source: ChromaDB (Personalized)")
                        elif source == "tmdb_cold_start":
                            st.warning("Data Source: TMDB API (Cold Start)")
                        else:
                            st.info(f"Data Source: {source}")
                    with col2:
                        if duration:
                            st.info(f"Pipeline Duration: {duration:.0f}ms")
                    with col3:
                        st.caption(f"Trace: `{trace_id[:8]}`")
            except Exception:
                pass

        # Show context factors
        if st.session_state.get("context_factors"):
            with st.expander("Detected Context", expanded=False):
                context_factors = st.session_state.context_factors
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Time of Day", context_factors.get("time_of_day", "N/A").title())
                with col2:
                    st.metric("Day", context_factors.get("day_of_week", "N/A"))
                with col3:
                    st.metric("Season", context_factors.get("season", "N/A").title())

        # Show real processing steps from API
        if st.session_state.get("processing_steps"):
            with st.expander("AI Processing Log", expanded=False):
                for step in st.session_state.processing_steps:
                    st.write(f"- {step}")

                # Show detailed trace steps if available
                trace_id = st.session_state.get("trace_id")
                if trace_id:
                    try:
                        trace_resp = requests.get(
                            f"{API_BASE_URL}/api/v1/admin/traces/{trace_id}",
                            timeout=5,
                        )
                        if trace_resp.status_code == 200:
                            trace_data = trace_resp.json()
                            steps = trace_data.get("steps", [])
                            if steps:
                                st.markdown("**Agent Timing:**")
                                for s in steps:
                                    agent = s.get("agent_name", "?")
                                    dur = s.get("duration_ms", 0)
                                    summary = s.get("summary", "")
                                    st.write(f"  - **{agent}** ({dur:.0f}ms): {summary}")
                    except Exception:
                        pass

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
                if st.button("Loved it!", key=f"love_{movie.get('tmdb_id')}"):
                    _submit_feedback(movie.get("tmdb_id"), 5.0)

            with col3:
                if st.button("Not for me", key=f"dislike_{movie.get('tmdb_id')}"):
                    _submit_feedback(movie.get("tmdb_id"), 1.0)

            st.markdown("---")

    else:
        st.info("No recommendations available. Click 'Refresh Recommendations' to generate.")
