"""Movie Card Component - Reusable movie display card."""

import streamlit as st
import streamlit.components.v1 as components
from typing import Dict, Any, Optional

# Ordered list of embed providers. The first available one is used; if it fails
# the inline JS rotates to the next.  Update this list whenever a provider
# changes domain — no other file needs touching.
EMBED_SOURCES = [
    {"name": "VidSrc",    "url": "https://vsembed.su/embed/movie/{tmdb_id}"},
    {"name": "VidSrc.to", "url": "https://vidsrc.to/embed/movie/{tmdb_id}"},
    {"name": "VidSrc.xyz","url": "https://vidsrc.xyz/embed/movie/{tmdb_id}"},
    {"name": "2embed",    "url": "https://www.2embed.cc/embed/{tmdb_id}"},
]


def render_movie_card(
    movie: Dict[str, Any],
    explanation: Optional[str] = None,
    rank: Optional[int] = None,
    score: Optional[float] = None,
    is_exploration: bool = False,
):
    """
    Render a movie card with poster, metadata, expandable details, and VidSrc embed.

    CSS is NOT injected here — call inject_cinema_theme() once at page level.

    Args:
        movie: Movie dictionary with metadata.
        explanation: Optional explanation text.
        rank: Optional rank number.
        score: Optional recommendation score.
        is_exploration: Whether this is an exploratory recommendation.
    """
    tmdb_id = movie.get("tmdb_id") or movie.get("id") or 0

    with st.container():
        cols = st.columns([1, 3])

        # Left: Poster
        with cols[0]:
            poster_path = movie.get("poster_path")
            if poster_path and str(poster_path) not in ("N/A", "None", ""):
                st.image(f"https://image.tmdb.org/t/p/w300{poster_path}", use_container_width=True)
            else:
                title_short = (movie.get("title") or "?")[:25]
                st.markdown(
                    f"""
                    <div style="
                        width:100%;aspect-ratio:2/3;
                        background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
                        display:flex;align-items:center;justify-content:center;
                        border-radius:8px;color:#f5c518;font-size:13px;
                        text-align:center;padding:8px;border:1px solid #1e1e2e;
                    ">{title_short}</div>
                    """,
                    unsafe_allow_html=True,
                )

        # Right: Info
        with cols[1]:
            title = movie.get("title") or "Unknown Title"
            year = movie.get("year") or ""

            rank_prefix = f"#{rank} " if rank else ""
            st.markdown(f"### {rank_prefix}{title}")

            # Metadata pills
            parts = []
            if year:
                parts.append(f"📅 {year}")
            genres = movie.get("genres") or []
            if genres:
                parts.append(f"🎭 {', '.join(genres[:3])}")
            vote_avg = movie.get("vote_average")
            if vote_avg:
                parts.append(f"⭐ {float(vote_avg):.1f}/10")
            director = movie.get("director")
            if director:
                parts.append(f"🎬 {director}")
            if parts:
                st.caption(" · ".join(parts))

            # Exploration badge
            if is_exploration:
                st.markdown(
                    '<span style="background:#e50914;color:white;padding:2px 8px;'
                    'border-radius:10px;font-size:11px;font-weight:bold;">🔍 Discovery Pick</span>',
                    unsafe_allow_html=True,
                )

            # Animated match score bar (pure HTML — no st.progress to avoid version issues)
            if score is not None:
                pct = int(score * 100)
                bar_color = "#f5c518" if pct >= 70 else ("#e50914" if pct >= 40 else "#8a8a9a")
                st.markdown(
                    f"""
                    <div style="margin:6px 0 4px">
                        <div style="display:flex;align-items:center;gap:8px">
                            <span style="color:#8a8a9a;font-size:11px;min-width:70px">Match score</span>
                            <div style="flex:1;background:#1e1e2e;border-radius:4px;height:6px">
                                <div style="width:{pct}%;background:{bar_color};height:6px;
                                     border-radius:4px;transition:width 0.8s ease"></div>
                            </div>
                            <span style="color:{bar_color};font-size:13px;font-weight:bold;min-width:36px">{pct}%</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Plot summary
            overview = movie.get("overview") or ""
            if overview:
                with st.expander("📖 Plot Summary"):
                    st.write(overview)

            # Explanation
            if explanation:
                with st.expander("💡 Why This Was Recommended"):
                    st.info(explanation)

            # Watch Now embed — rotates through EMBED_SOURCES on failure
            if tmdb_id:
                with st.expander("▶️ Watch Now"):
                    st.caption(
                        "Ad redirects blocked by iframe sandbox · "
                        "Availability varies by region. Use ⟳ to try another source."
                    )
                    sources_js = str(
                        [s["url"].format(tmdb_id=tmdb_id) for s in EMBED_SOURCES]
                    )
                    source_names_js = str([s["name"] for s in EMBED_SOURCES])
                    components.html(
                        f"""
                        <div style="position:relative;">
                          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                            <span id="src-label" style="font-size:12px;color:#aaa;font-family:sans-serif;">
                              {EMBED_SOURCES[0]['name']}
                            </span>
                            <button onclick="nextSource()"
                              style="font-size:11px;padding:2px 8px;border-radius:4px;
                                     border:1px solid #555;background:#222;color:#ccc;cursor:pointer;">
                              ⟳ Try next source
                            </button>
                          </div>
                          <iframe id="embed-frame"
                              src="{EMBED_SOURCES[0]['url'].format(tmdb_id=tmdb_id)}"
                              width="100%"
                              height="450"
                              frameborder="0"
                              referrerpolicy="no-referrer"
                              sandbox="allow-scripts allow-same-origin allow-forms"
                              allow="autoplay; fullscreen"
                              loading="lazy"
                              style="border-radius:8px;"
                          ></iframe>
                        </div>
                        <script>
                          var _sources = {sources_js};
                          var _names   = {source_names_js};
                          var _idx     = 0;
                          function nextSource() {{
                            _idx = (_idx + 1) % _sources.length;
                            document.getElementById('embed-frame').src = _sources[_idx];
                            document.getElementById('src-label').textContent  = _names[_idx];
                          }}
                        </script>
                        """,
                        height=500,
                    )


def render_movie_grid(
    movies: list,
    explanations: Dict[str, str] = None,
    scores: Dict[str, float] = None,
    cols_per_row: int = 2,
):
    """
    Render movies in a grid using render_movie_card.

    Args:
        movies: List of movie dictionaries.
        explanations: Optional dict of tmdb_id → explanation.
        scores: Optional dict of tmdb_id → score.
        cols_per_row: Number of columns per row.
    """
    explanations = explanations or {}
    scores = scores or {}

    for i in range(0, len(movies), cols_per_row):
        row_cols = st.columns(cols_per_row)
        for j, col in enumerate(row_cols):
            idx = i + j
            if idx < len(movies):
                movie = movies[idx]
                movie_id = str(movie.get("tmdb_id") or movie.get("id") or idx)
                with col:
                    render_movie_card(
                        movie=movie,
                        explanation=explanations.get(movie_id),
                        score=scores.get(movie_id),
                        rank=idx + 1,
                    )


def render_movie_poster_grid(movies: list, cols_per_row: int = 6):
    """
    Compact poster-only grid for home/trending sections.

    Clicking the title expands a mini-card inline.

    Args:
        movies: List of movie dicts.
        cols_per_row: Columns per row.
    """
    for i in range(0, len(movies), cols_per_row):
        row_cols = st.columns(cols_per_row)
        for j, col in enumerate(row_cols):
            idx = i + j
            if idx < len(movies):
                movie = movies[idx]
                with col:
                    poster_path = movie.get("poster_path")
                    if poster_path:
                        st.image(
                            f"https://image.tmdb.org/t/p/w300{poster_path}",
                            use_container_width=True,
                        )
                    else:
                        st.image(
                            "https://via.placeholder.com/300x450?text=No+Poster",
                            use_container_width=True,
                        )
                    title = (movie.get("title") or "")[:20]
                    st.caption(f"**{title}**")
                    if movie.get("vote_average"):
                        st.caption(f"⭐ {float(movie['vote_average']):.1f}")

                    # Inline expander with full card on click
                    with st.expander("Details"):
                        render_movie_card(movie=movie)
