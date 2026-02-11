"""Profile Page - User statistics and preferences."""

import streamlit as st
import requests

st.set_page_config(page_title="Profile - CineMatch AI", page_icon="📊", layout="wide")

API_BASE_URL = "http://localhost:8000"

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

# Header
st.title("📊 Your Profile")

# Check if user is onboarded
if not st.session_state.onboarded:
    st.warning("⚠️ Please complete onboarding first")
    if st.button("Go to Recommendations Page"):
        st.switch_page("pages/2_🎬_Recommendations.py")
else:
    st.markdown(f"## Welcome, **{st.session_state.user_id}**!")

    # Note: In a production app, you'd fetch this from the API
    # For now, we'll show a placeholder UI

    st.info(
        "📝 **Note:** Full profile analytics coming soon! "
        "This page will show your viewing history, preference trends, "
        "and personalized insights."
    )

    # Placeholder metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Movies Rated", "15", "+3 this week")

    with col2:
        st.metric("Recommendations Viewed", "47", "+12 today")

    with col3:
        st.metric("Favorite Genre", "Drama")

    with col4:
        st.metric("Exploration Rate", "30%")

    st.markdown("---")

    # Preferences Section
    st.markdown("### 🎭 Your Preferences")

    tab1, tab2, tab3 = st.tabs(["Favorite Genres", "Favorite Directors", "Temporal Patterns"])

    with tab1:
        st.markdown("#### Top Genres")
        # Placeholder data
        genres = {
            "Drama": 0.85,
            "Thriller": 0.72,
            "Crime": 0.65,
            "Sci-Fi": 0.58,
            "Action": 0.45,
        }

        for genre, score in genres.items():
            st.progress(score, text=f"{genre}: {score*100:.0f}%")

    with tab2:
        st.markdown("#### Top Directors")
        # Placeholder
        directors = [
            "Christopher Nolan",
            "Quentin Tarantino",
            "David Fincher",
            "Denis Villeneuve",
            "Martin Scorsese",
        ]

        for i, director in enumerate(directors, 1):
            st.write(f"{i}. {director}")

    with tab3:
        st.markdown("#### Viewing Patterns")

        st.write("**Weekday vs Weekend:**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Weekday", "40%")
        with col2:
            st.metric("Weekend", "60%")

        st.write("**Favorite Time:**")
        st.metric("Peak Time", "Evening (6 PM - 10 PM)")

    st.markdown("---")

    # Recent Activity
    st.markdown("### 📜 Recent Activity")

    # Placeholder recent ratings
    recent_ratings = [
        {"title": "Fight Club", "rating": 5.0, "date": "2024-01-15"},
        {"title": "Pulp Fiction", "rating": 4.5, "date": "2024-01-14"},
        {"title": "The Dark Knight", "rating": 5.0, "date": "2024-01-13"},
        {"title": "Inception", "rating": 4.5, "date": "2024-01-12"},
        {"title": "Interstellar", "rating": 5.0, "date": "2024-01-11"},
    ]

    for rating_data in recent_ratings:
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            st.write(f"**{rating_data['title']}**")

        with col2:
            st.write(f"⭐ {rating_data['rating']}/5.0")

        with col3:
            st.write(rating_data['date'])

    st.markdown("---")

    # Settings
    st.markdown("### ⚙️ Settings")

    with st.expander("Preferences"):
        st.slider("Exploration Rate", 0.0, 1.0, 0.3, 0.1, help="How adventurous should recommendations be?")
        st.checkbox("Include R-rated movies", value=True)
        st.checkbox("Prefer newer movies (2010+)", value=False)

    with st.expander("Privacy"):
        st.checkbox("Allow anonymous usage analytics", value=True)
        st.checkbox("Share taste profile for research", value=False)

    st.markdown("---")

    # Actions
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Refresh Profile", use_container_width=True):
            st.toast("Profile refreshed!")

    with col2:
        if st.button("🗑️ Delete Account", use_container_width=True, type="secondary"):
            st.warning("⚠️ This action cannot be undone!")
