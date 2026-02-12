"""Browse Page - Explore movies by language and region."""

import streamlit as st
import requests
from typing import List, Dict, Optional

st.set_page_config(
    page_title="Browse - CineMatch AI",
    page_icon="🌍",
    layout="wide",
)

# Constants
API_BASE_URL = "http://localhost:8000/api/v1"

REGIONAL_CINEMA = {
    "🎬 Bollywood (Hindi)": {"language": "hi", "region": "IN", "emoji": "🇮🇳"},
    "🎭 K-Drama Movies (Korean)": {"language": "ko", "region": "KR", "emoji": "🇰🇷"},
    "🎌 Japanese Cinema": {"language": "ja", "region": "JP", "emoji": "🇯🇵"},
    "🎥 French Cinema": {"language": "fr", "region": "FR", "emoji": "🇫🇷"},
    "🌟 Gujarati Cinema": {"language": "gu", "region": "IN", "emoji": "🇮🇳"},
    "🎪 Tamil Cinema": {"language": "ta", "region": "IN", "emoji": "🇮🇳"},
    "🎬 Telugu Cinema": {"language": "te", "region": "IN", "emoji": "🇮🇳"},
    "🎥 Spanish Cinema": {"language": "es", "region": "ES", "emoji": "🇪🇸"},
    "🎭 German Cinema": {"language": "de", "region": "DE", "emoji": "🇩🇪"},
    "🌟 Italian Cinema": {"language": "it", "region": "IT", "emoji": "🇮🇹"},
}

LANGUAGE_OPTIONS = {
    "English": "en",
    "Hindi": "hi",
    "Korean": "ko",
    "Japanese": "ja",
    "Gujarati": "gu",
    "Tamil": "ta",
    "Telugu": "te",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
    "Italian": "it",
    "Chinese": "zh",
    "Arabic": "ar",
    "Portuguese": "pt",
    "Russian": "ru",
    "Bengali": "bn",
    "Marathi": "mr",
    "Punjabi": "pa",
    "Malayalam": "ml",
    "Kannada": "kn",
}


@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_popular_by_language(language: str, region: Optional[str] = None, limit: int = 12) -> List[Dict]:
    """Fetch popular movies by language."""
    try:
        url = f"{API_BASE_URL}/movies/popular/{language}"
        params = {"limit": limit}
        if region:
            params["region"] = region

        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("movies", [])
    except Exception as e:
        st.error(f"Failed to fetch movies: {e}")
    return []


@st.cache_data(ttl=3600)
def fetch_trending(time_window: str = "week", language: Optional[str] = None, limit: int = 12) -> List[Dict]:
    """Fetch trending movies."""
    try:
        url = f"{API_BASE_URL}/movies/trending"
        params = {"time_window": time_window, "limit": limit}
        if language:
            params["language"] = language

        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("movies", [])
    except Exception as e:
        st.error(f"Failed to fetch trending movies: {e}")
    return []


@st.cache_data(ttl=1800)
def fetch_recent_releases(language: Optional[str] = None, region: Optional[str] = None, days: int = 90, limit: int = 12) -> List[Dict]:
    """Fetch recent releases."""
    try:
        url = f"{API_BASE_URL}/movies/recent"
        params = {"days": days}
        if language:
            params["language"] = language
        if region:
            params["region"] = region

        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("movies", [])[:limit]
    except Exception as e:
        st.error(f"Failed to fetch recent releases: {e}")
    return []


@st.cache_data(ttl=600)
def search_movies(query: str, language: Optional[str] = None, year: Optional[int] = None, limit: int = 12) -> List[Dict]:
    """Search movies."""
    try:
        url = f"{API_BASE_URL}/movies/search"
        params = {"query": query, "limit": limit}
        if language:
            params["language"] = language
        if year:
            params["year"] = year

        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get("movies", [])
    except Exception as e:
        st.error(f"Failed to search movies: {e}")
    return []


def display_movie_card(movie: Dict, show_details: bool = True):
    """Display a movie card."""
    poster_url = (
        f"https://image.tmdb.org/t/p/w300{movie['poster_path']}"
        if movie.get("poster_path")
        else "https://via.placeholder.com/300x450?text=No+Poster"
    )

    st.image(poster_url, use_container_width=True)

    title = movie["title"]
    year = movie.get("year", "N/A")
    st.markdown(f"**{title}**")
    st.caption(f"📅 {year}")

    if movie.get("vote_average"):
        st.caption(f"⭐ {movie['vote_average']:.1f}/10")

    if show_details:
        genres = ", ".join(movie.get("genres", [])[:2])
        if genres:
            st.caption(f"🎭 {genres}")


# Header
st.markdown("# 🌍 Browse Movies")
st.markdown("Explore movies from around the world")

# Tabs for different browsing modes
tab1, tab2, tab3, tab4 = st.tabs(["🔥 Trending", "🌍 Regional Cinema", "🆕 Recent Releases", "🔍 Search"])

# Tab 1: Trending
with tab1:
    st.markdown("### 🔥 What's Trending")

    col1, col2 = st.columns([3, 1])
    with col1:
        time_window = st.radio(
            "Time Window",
            ["week", "day"],
            format_func=lambda x: "This Week" if x == "week" else "Today",
            horizontal=True,
        )
    with col2:
        filter_lang = st.selectbox(
            "Language Filter",
            ["All Languages"] + list(LANGUAGE_OPTIONS.keys()),
            key="trending_lang"
        )

    selected_lang = None if filter_lang == "All Languages" else LANGUAGE_OPTIONS[filter_lang]

    trending_movies = fetch_trending(time_window=time_window, language=selected_lang, limit=12)

    if trending_movies:
        cols = st.columns(4)
        for idx, movie in enumerate(trending_movies):
            with cols[idx % 4]:
                display_movie_card(movie)
    else:
        st.info("Start the API server to browse trending movies!")
        st.code("python -m uvicorn src.api.main:app --reload --port 8000", language="bash")

# Tab 2: Regional Cinema
with tab2:
    st.markdown("### 🌍 Explore Regional Cinema")
    st.caption("Discover movies from different cultures and languages")

    # Display all regional cinema sections
    for section_name, config in REGIONAL_CINEMA.items():
        st.markdown(f"## {section_name}")

        movies = fetch_popular_by_language(
            language=config["language"],
            region=config["region"],
            limit=8
        )

        if movies:
            cols = st.columns(4)
            for idx, movie in enumerate(movies[:8]):
                with cols[idx % 4]:
                    display_movie_card(movie, show_details=True)
        else:
            st.info(f"No {section_name} movies available. Start the API server!")

        st.markdown("---")

# Tab 3: Recent Releases
with tab3:
    st.markdown("### 🆕 Recent Releases")

    col1, col2, col3 = st.columns(3)
    with col1:
        days_back = st.selectbox(
            "Time Period",
            [30, 60, 90, 180],
            format_func=lambda x: f"Last {x} days",
            index=2
        )
    with col2:
        recent_lang = st.selectbox(
            "Language",
            ["All Languages"] + list(LANGUAGE_OPTIONS.keys()),
            key="recent_lang"
        )
    with col3:
        recent_region = st.text_input(
            "Region Code (e.g., US, IN, KR)",
            placeholder="Optional",
            key="recent_region"
        )

    selected_recent_lang = None if recent_lang == "All Languages" else LANGUAGE_OPTIONS[recent_lang]
    selected_recent_region = recent_region.strip() if recent_region.strip() else None

    recent_movies = fetch_recent_releases(
        language=selected_recent_lang,
        region=selected_recent_region,
        days=days_back,
        limit=12
    )

    if recent_movies:
        cols = st.columns(4)
        for idx, movie in enumerate(recent_movies):
            with cols[idx % 4]:
                display_movie_card(movie)
    else:
        st.info("No recent releases found. Try different filters!")

# Tab 4: Search
with tab4:
    st.markdown("### 🔍 Search Movies")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        search_query = st.text_input(
            "Search for a movie",
            placeholder="e.g., Inception, Avatar, Dangal...",
            key="search_query"
        )
    with col2:
        search_lang = st.selectbox(
            "Language",
            ["All Languages"] + list(LANGUAGE_OPTIONS.keys()),
            key="search_lang"
        )
    with col3:
        search_year = st.number_input(
            "Year (Optional)",
            min_value=1900,
            max_value=2030,
            value=None,
            step=1,
            key="search_year"
        )

    if search_query:
        selected_search_lang = None if search_lang == "All Languages" else LANGUAGE_OPTIONS[search_lang]

        search_results = search_movies(
            query=search_query,
            language=selected_search_lang,
            year=search_year,
            limit=12
        )

        if search_results:
            st.success(f"Found {len(search_results)} results")
            cols = st.columns(4)
            for idx, movie in enumerate(search_results):
                with cols[idx % 4]:
                    display_movie_card(movie)
        else:
            st.warning(f"No results found for '{search_query}'")
    else:
        st.info("Enter a movie title to search")

# Sidebar
with st.sidebar:
    st.markdown("## 🌍 Language Guide")

    st.markdown("### Popular Regional Cinema")
    st.markdown("""
    - 🇮🇳 **India**: Hindi, Gujarati, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, Punjabi
    - 🇰🇷 **Korea**: Korean (K-Drama)
    - 🇯🇵 **Japan**: Japanese (Anime, J-Drama)
    - 🇫🇷 **France**: French
    - 🇪🇸 **Spain**: Spanish
    - 🇩🇪 **Germany**: German
    - 🇮🇹 **Italy**: Italian
    - 🇨🇳 **China**: Chinese
    - 🇧🇷 **Brazil**: Portuguese
    - 🇷🇺 **Russia**: Russian
    """)

    st.markdown("---")

    st.markdown("### 💡 Pro Tips")
    st.markdown("""
    - Use **Language Filter** to find movies in your preferred language
    - Explore **Regional Cinema** to discover cultural gems
    - Check **Recent Releases** for latest movies
    - Use **Search** to find specific titles
    """)

    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("app.py")
