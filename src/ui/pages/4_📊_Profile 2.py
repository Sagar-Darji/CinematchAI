"""Profile Page - User statistics and preferences from real data."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
import requests
from src.ui.session import restore_streamlit_session

st.set_page_config(page_title="Profile - CineMatch AI", page_icon="📊", layout="wide")

API_BASE_URL = "http://localhost:8000"

# Restore persistent session
restore_streamlit_session()

# Header
st.title("📊 Your Profile")

# Check if user is onboarded
if not st.session_state.onboarded:
    st.warning("Please complete onboarding first")
    if st.button("Go to Recommendations Page"):
        st.switch_page("pages/2_🎬_Recommendations.py")
else:
    user_id = st.session_state.user_id
    st.markdown(f"## Welcome, **{user_id}**!")

    # Fetch real profile data from admin API
    profile_data = None
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/v1/admin/users/{user_id}/profile",
            timeout=10,
        )
        if resp.status_code == 200:
            profile_data = resp.json()
    except Exception as e:
        st.error(f"Failed to load profile: {e}")

    if profile_data is None:
        st.info("No profile data available yet. Import your Letterboxd ratings or rate some movies to build your profile.")
    else:
        # Running job warning
        if profile_data.get("has_running_job"):
            st.warning("Profile is being rebuilt... Some data may be updating.")

        # Real metrics
        prefs = profile_data.get("preferences", {})
        total_ratings = profile_data.get("total_ratings", 0)
        is_cold_start = profile_data.get("is_cold_start", True)
        avg_rating = profile_data.get("avg_rating_given")
        favorite_genres = prefs.get("favorite_genres", [])
        exploration_rate = prefs.get("exploration_rate", 0)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Movies Rated", total_ratings)

        with col2:
            status = "Active" if not is_cold_start else "Cold Start"
            st.metric("Profile Status", status)

        with col3:
            top_genre = favorite_genres[0] if favorite_genres else "N/A"
            st.metric("Top Genre", top_genre)

        with col4:
            st.metric("Exploration Rate", f"{exploration_rate:.0%}")

        st.markdown("---")

        # Preferences Section
        st.markdown("### 🎭 Your Preferences")

        tab1, tab2, tab3 = st.tabs(["Favorite Genres", "Favorite Directors", "Temporal Patterns"])

        with tab1:
            st.markdown("#### Top Genres")
            if favorite_genres:
                # Show genres with progress bars (proportional to position)
                for i, genre in enumerate(favorite_genres):
                    score = max(0.2, 1.0 - (i * 0.15))
                    st.progress(score, text=f"{genre}: {score*100:.0f}%")
            else:
                st.info("No genre preferences detected yet. Rate more movies to build preferences.")

        with tab2:
            st.markdown("#### Top Directors")
            directors = prefs.get("favorite_directors", [])
            if directors:
                for i, director in enumerate(directors, 1):
                    st.write(f"{i}. {director}")
            else:
                st.info("No director preferences detected yet.")

        with tab3:
            st.markdown("#### Viewing Patterns")
            temporal = profile_data.get("temporal_patterns", {})

            if temporal and any(v for v in temporal.values() if v):
                st.write("**Time Preferences:**")
                col1, col2 = st.columns(2)
                with col1:
                    weekend_pref = temporal.get("weekend_preference", "N/A")
                    st.metric("Weekend Preference", weekend_pref or "N/A")
                with col2:
                    weekday_pref = temporal.get("weekday_preference", "N/A")
                    st.metric("Weekday Preference", weekday_pref or "N/A")

                st.write("**Peak Viewing:**")
                col1, col2 = st.columns(2)
                with col1:
                    peak_time = temporal.get("peak_viewing_time", "N/A")
                    st.metric("Peak Time", (peak_time or "N/A").title())
                with col2:
                    peak_day = temporal.get("peak_viewing_day", "N/A")
                    st.metric("Peak Day", peak_day or "N/A")
            else:
                st.info("Not enough viewing data to detect temporal patterns.")

        st.markdown("---")

        # Recent Activity
        st.markdown("### 📜 Recent Activity")

        recent_ratings = profile_data.get("recent_ratings", [])
        if recent_ratings:
            for r in recent_ratings[:10]:
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    title = r.get("title", f"Movie {r['movie_id']}")
                    year = r.get("year")
                    if year:
                        st.write(f"**{title}** ({year})")
                    else:
                        st.write(f"**{title}**")

                with col2:
                    st.write(f"⭐ {r['rating']}/5.0")

                with col3:
                    ts = r.get("timestamp", "")
                    st.write(ts[:10] if ts else "N/A")
        else:
            st.info("No ratings recorded yet.")

        st.markdown("---")

        # Additional Stats
        if avg_rating:
            st.markdown("### 📈 Rating Stats")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Average Rating Given", f"{avg_rating:.1f} / 5.0")
            with col2:
                risk = prefs.get("risk_tolerance", 0)
                st.metric("Risk Tolerance", f"{risk:.0%}")

        st.markdown("---")

        # Actions
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Refresh Profile", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        with col2:
            if st.button("🗑️ Delete Account", use_container_width=True, type="secondary"):
                st.warning("This action cannot be undone!")
