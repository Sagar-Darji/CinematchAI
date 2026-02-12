"""CineMatch AI - Main Streamlit Application."""

import streamlit as st
import requests
from typing import List, Dict

# Page configuration
st.set_page_config(
    page_title="CineMatch AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
    <style>
    .main-header {
        font-size: 48px;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    .subtitle {
        font-size: 18px;
        color: #666;
        margin-bottom: 30px;
    }
    .feature-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Helper functions


@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_trending_movies(limit: int = 6) -> List[Dict]:
    """Fetch trending movies from API."""
    try:
        response = requests.get(
            "http://localhost:8000/api/v1/movies/trending?time_window=week",
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("movies", [])[:limit]
    except Exception as e:
        st.warning(f"Could not fetch trending movies: {e}")
    return []


def display_movie_card(movie: Dict):
    """Display a movie card."""
    poster_url = (
        f"https://image.tmdb.org/t/p/w300{movie['poster_path']}"
        if movie.get("poster_path")
        else "https://via.placeholder.com/300x450?text=No+Poster"
    )

    st.image(poster_url, use_container_width=True)
    st.markdown(f"**{movie['title']}** ({movie.get('year', 'N/A')})")
    if movie.get("vote_average"):
        st.caption(f"⭐ {movie['vote_average']:.1f}/10")
    genres = ", ".join(movie.get("genres", [])[:2])
    if genres:
        st.caption(f"🎭 {genres}")


# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

# Header
st.markdown('<h1 class="main-header">🎬 CineMatch AI</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Multi-Agent Movie Recommendation System with RAG & Multi-Modal Embeddings</p>',
    unsafe_allow_html=True,
)

# Welcome Section
if not st.session_state.onboarded:
    st.markdown("## Welcome! 👋")

    st.markdown(
        """
        CineMatch AI uses **6 specialized AI agents** working together to provide you with:

        - 🎯 **Personalized Recommendations** - Tailored to your unique taste
        - 🧠 **Explainable AI** - Understand why each movie is recommended
        - 🌍 **Context-Aware** - Considers your mood, time, and viewing situation
        - 👥 **Group Recommendations** - Find movies everyone will enjoy
        - 🔍 **Serendipity** - Discover hidden gems outside your comfort zone
        - 🖼️ **Multi-Modal** - Analyzes both plot and poster aesthetics
        """
    )

    st.markdown("---")

    # Trending Movies Section
    st.markdown("### 🔥 Trending This Week")
    st.caption("Popular movies on TMDB right now")

    trending_movies = fetch_trending_movies(limit=6)
    if trending_movies:
        cols = st.columns(6)
        for idx, movie in enumerate(trending_movies):
            with cols[idx]:
                display_movie_card(movie)
    else:
        st.info("Start the API server to see trending movies!")
        st.code("python -m uvicorn src.api.main:app --reload --port 8000", language="bash")

    st.markdown("---")

    # Get Started Section
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### Get Started")

        # Check if user already has an ID
        existing_user = st.text_input(
            "Have an account? Enter your username:",
            placeholder="e.g., john_doe",
        )

        if st.button("Continue as Existing User", use_container_width=True):
            if existing_user:
                st.session_state.user_id = existing_user
                st.session_state.onboarded = True
                st.success(f"Welcome back, {existing_user}!")
                st.rerun()
            else:
                st.error("Please enter your username")

        st.markdown("---")
        st.markdown("**New User?**")

        if st.button("Start Onboarding →", type="primary", use_container_width=True):
            st.switch_page("pages/2_🎬_Recommendations.py")

else:
    # User is onboarded - show dashboard
    st.success(f"Welcome back, **{st.session_state.user_id}**! 🎉")

    st.markdown("## What would you like to do?")

    # Navigation cards (4 columns)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🎬 Recommendations</h3>
                <p>AI-powered personalized suggestions</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Get Recommendations", use_container_width=True):
            st.switch_page("pages/2_🎬_Recommendations.py")

    with col2:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🌍 Browse</h3>
                <p>Explore movies by language & region</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Browse Movies", use_container_width=True):
            st.switch_page("pages/5_🌍_Browse.py")

    with col3:
        st.markdown(
            """
            <div class="feature-card">
                <h3>👥 Group Mode</h3>
                <p>Find movies for your group</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start Group Session", use_container_width=True):
            st.switch_page("pages/3_👥_Group_Mode.py")

    with col4:
        st.markdown(
            """
            <div class="feature-card">
                <h3>📊 My Profile</h3>
                <p>View your taste & stats</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("View Profile", use_container_width=True):
            st.switch_page("pages/4_📊_Profile.py")

    st.markdown("---")

    # Trending Movies Section for Dashboard
    st.markdown("### 🔥 Trending This Week")
    st.caption("Popular movies on TMDB - Discover what's hot right now!")

    trending_movies = fetch_trending_movies(limit=6)
    if trending_movies:
        cols = st.columns(6)
        for idx, movie in enumerate(trending_movies):
            with cols[idx]:
                display_movie_card(movie)
    else:
        st.info("Start the API server to see trending movies!")
        st.code("python -m uvicorn src.api.main:app --reload --port 8000", language="bash")

# Sidebar
with st.sidebar:
    st.markdown("## About")

    st.markdown(
        """
        **CineMatch AI** is a portfolio project demonstrating:

        - 🤖 **Multi-Agent Systems** (LangGraph)
        - 🔍 **RAG Architecture** (ChromaDB)
        - 🎨 **Multi-Modal AI** (Text + Image)
        - ⚡ **Production Deployment** (FastAPI + Streamlit)

        **Tech Stack:**
        - Ollama (Llama 3.1)
        - Sentence Transformers
        - CLIP (Image Embeddings)
        - FastAPI
        - Streamlit
        """
    )

    st.markdown("---")

    if st.session_state.onboarded:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.onboarded = False
            st.rerun()

    st.markdown("---")
    st.markdown("**Version:** 1.0.0")
    st.markdown("**Author:** CineMatch AI Team")
