"""Release Calendar - Now Playing, Upcoming Theater & OTT releases."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
import requests
from datetime import datetime
from typing import List, Dict, Optional

from src.ui.components.movie_card import render_movie_card
from src.ui.styles import inject_cinema_theme

st.set_page_config(
    page_title="Release Calendar - CineMatch AI",
    page_icon="📅",
    layout="wide",
)
inject_cinema_theme()

API_BASE_URL = "http://localhost:8000/api/v1"

# TMDB watch provider IDs
OTT_PROVIDERS = {
    "All Major Platforms": "8|9|337|2|384|15",
    "🔴 Netflix": "8",
    "🟡 Prime Video": "9",
    "🔵 Disney+": "337",
    "⬛ Apple TV+": "2",
    "🟣 HBO Max / Max": "384",
    "🟢 Hulu": "15",
}

REGIONS = {
    "🌐 Global (US)": "US",
    "🇮🇳 India": "IN",
    "🇬🇧 UK": "GB",
    "🇨🇦 Canada": "CA",
    "🇦🇺 Australia": "AU",
    "🇩🇪 Germany": "DE",
    "🇫🇷 France": "FR",
    "🇰🇷 South Korea": "KR",
    "🇯🇵 Japan": "JP",
}

LANGUAGE_OPTIONS = {
    "All Languages": None,
    "English": "en",
    "Hindi": "hi",
    "Korean": "ko",
    "Japanese": "ja",
    "Tamil": "ta",
    "Telugu": "te",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
}


@st.cache_data(ttl=3600)
def fetch_now_playing(region: Optional[str], language: Optional[str], page: int = 1) -> List[Dict]:
    try:
        params = {"page": page}
        if region:
            params["region"] = region
        if language:
            params["language"] = language
        resp = requests.get(f"{API_BASE_URL}/movies/now-playing", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("movies", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=3600)
def fetch_upcoming(region: Optional[str], language: Optional[str], page: int = 1) -> List[Dict]:
    try:
        params = {"page": page}
        if region:
            params["region"] = region
        if language:
            params["language"] = language
        resp = requests.get(f"{API_BASE_URL}/movies/upcoming", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("movies", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=3600)
def fetch_ott_releases(providers: str, region: str, language: Optional[str], days: int, page: int = 1) -> List[Dict]:
    try:
        params = {"providers": providers, "region": region, "days": days, "page": page}
        if language:
            params["language"] = language
        resp = requests.get(f"{API_BASE_URL}/movies/ott-releases", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("movies", [])
    except Exception:
        pass
    return []


def _movie_grid(movies: List[Dict], cols: int = 4, key_prefix: str = ""):
    """Render a responsive movie grid."""
    if not movies:
        st.info("No movies found. Make sure the API server is running.")
        st.code("python -m uvicorn src.api.main:app --reload --port 8000", language="bash")
        return

    for i in range(0, len(movies), cols):
        row = st.columns(cols)
        for j, col in enumerate(row):
            idx = i + j
            if idx >= len(movies):
                break
            movie = movies[idx]
            with col:
                poster = movie.get("poster_path")
                st.image(
                    f"https://image.tmdb.org/t/p/w300{poster}" if poster
                    else "https://via.placeholder.com/300x450?text=No+Poster",
                    use_container_width=True,
                )
                title = movie.get("title", "")
                st.caption(f"**{title[:22]}**")
                if movie.get("vote_average"):
                    st.caption(f"⭐ {float(movie['vote_average']):.1f}/10")
                if movie.get("year"):
                    st.caption(f"📅 {movie['year']}")
                genres = movie.get("genres") or []
                if genres:
                    st.caption(", ".join(genres[:2]))
                with st.expander("🎬 Details & Watch"):
                    render_movie_card(movie=movie)


# ── Page header ──────────────────────────────────────────────────────────────
st.markdown("# 📅 Release Calendar")
st.markdown(f"*Updated {datetime.now().strftime('%B %d, %Y')}*")

tab1, tab2, tab3 = st.tabs(["🎭 Now in Theaters", "🗓️ Coming Soon", "📺 OTT / Streaming"])

# ── Tab 1: Now Playing ────────────────────────────────────────────────────────
with tab1:
    st.markdown("### 🎭 Now Playing in Theaters")

    c1, c2, c3 = st.columns(3)
    with c1:
        np_region_label = st.selectbox("Region", list(REGIONS.keys()), key="np_region")
    with c2:
        np_lang_label = st.selectbox("Language", list(LANGUAGE_OPTIONS.keys()), key="np_lang")
    with c3:
        np_page = st.number_input("Page", min_value=1, max_value=20, value=1, step=1, key="np_page")

    np_region = REGIONS[np_region_label]
    np_lang = LANGUAGE_OPTIONS[np_lang_label]

    with st.spinner("Fetching theaters now playing..."):
        np_movies = fetch_now_playing(region=np_region, language=np_lang, page=np_page)

    st.caption(f"Showing {len(np_movies)} movies currently in theaters")
    _movie_grid(np_movies, cols=4, key_prefix="np")

# ── Tab 2: Upcoming ───────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 🗓️ Coming Soon to Theaters")

    c1, c2, c3 = st.columns(3)
    with c1:
        up_region_label = st.selectbox("Region", list(REGIONS.keys()), key="up_region")
    with c2:
        up_lang_label = st.selectbox("Language", list(LANGUAGE_OPTIONS.keys()), key="up_lang")
    with c3:
        up_page = st.number_input("Page", min_value=1, max_value=20, value=1, step=1, key="up_page")

    up_region = REGIONS[up_region_label]
    up_lang = LANGUAGE_OPTIONS[up_lang_label]

    with st.spinner("Fetching upcoming releases..."):
        up_movies = fetch_upcoming(region=up_region, language=up_lang, page=up_page)

    # Sort by release year for a calendar-like feel
    up_movies_sorted = sorted(
        up_movies,
        key=lambda m: m.get("year") or 0,
    )

    st.caption(f"Showing {len(up_movies_sorted)} upcoming movies")
    _movie_grid(up_movies_sorted, cols=4, key_prefix="up")

# ── Tab 3: OTT Releases ───────────────────────────────────────────────────────
with tab3:
    st.markdown("### 📺 Latest OTT / Streaming Releases")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ott_provider_label = st.selectbox("Platform", list(OTT_PROVIDERS.keys()), key="ott_platform")
    with c2:
        ott_region_label = st.selectbox("Region", list(REGIONS.keys()), key="ott_region")
    with c3:
        ott_lang_label = st.selectbox("Language", list(LANGUAGE_OPTIONS.keys()), key="ott_lang")
    with c4:
        ott_days = st.selectbox(
            "Released within",
            [7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"Last {x} days",
            key="ott_days",
        )

    ott_providers = OTT_PROVIDERS[ott_provider_label]
    ott_region = REGIONS[ott_region_label]
    ott_lang = LANGUAGE_OPTIONS[ott_lang_label]

    with st.spinner(f"Fetching {ott_provider_label} releases..."):
        ott_movies = fetch_ott_releases(
            providers=ott_providers,
            region=ott_region,
            language=ott_lang,
            days=ott_days,
        )

    if ott_movies:
        st.caption(f"Showing {len(ott_movies)} recent streaming releases on {ott_provider_label}")
        _movie_grid(ott_movies, cols=4, key_prefix="ott")
    else:
        st.info(
            f"No OTT releases found for **{ott_provider_label}** in **{ott_region_label}** "
            f"within the last **{ott_days} days**. Try a wider date range or different region."
        )

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📅 Release Calendar")
    st.markdown("""
    Track what's showing near you and what just landed on streaming.

    ### 🎭 Now in Theaters
    Movies currently playing at cinemas worldwide.

    ### 🗓️ Coming Soon
    Upcoming theatrical releases — plan your next movie night.

    ### 📺 OTT / Streaming
    Recent releases on:
    - 🔴 Netflix
    - 🟡 Prime Video
    - 🔵 Disney+
    - ⬛ Apple TV+
    - 🟣 HBO Max
    - 🟢 Hulu
    """)
    st.markdown("---")
    st.caption("Data sourced from TMDB · Updated hourly")

    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("app.py")
