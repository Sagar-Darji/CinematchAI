"""Movie Card Component - Reusable movie display card."""

import streamlit as st
from typing import Dict, Any, Optional


def render_movie_card(
    movie: Dict[str, Any],
    explanation: Optional[str] = None,
    rank: Optional[int] = None,
    score: Optional[float] = None,
    is_exploration: bool = False,
):
    """
    Render a movie card with poster, metadata, and explanation.

    Args:
        movie: Movie dictionary with metadata.
        explanation: Optional explanation text.
        rank: Optional rank number.
        score: Optional recommendation score.
        is_exploration: Whether this is an exploratory recommendation.
    """
    with st.container():
        # Add border styling
        st.markdown(
            """
            <style>
            .movie-card {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 15px;
                background-color: #fafafa;
            }
            .movie-title {
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .movie-metadata {
                font-size: 14px;
                color: #666;
                margin-bottom: 10px;
            }
            .exploration-badge {
                background-color: #ff6b6b;
                color: white;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns([1, 3])

        # Left column: Poster
        with cols[0]:
            poster_path = movie.get("poster_path")
            if poster_path and poster_path != "N/A":
                # Use TMDB image CDN
                poster_url = f"https://image.tmdb.org/t/p/w200{poster_path}"
                st.image(poster_url, use_container_width=True)
            else:
                # Placeholder
                st.markdown(
                    f"""
                    <div style="
                        width: 100%;
                        aspect-ratio: 2/3;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        border-radius: 8px;
                        color: white;
                        font-size: 14px;
                        text-align: center;
                        padding: 10px;
                    ">
                        {movie.get('title', 'Unknown')[:30]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # Right column: Metadata and explanation
        with cols[1]:
            # Title and rank
            title = movie.get("title", "Unknown Title")
            year = movie.get("year", "")

            if rank:
                st.markdown(f"### #{rank} {title}")
            else:
                st.markdown(f"### {title}")

            # Metadata row
            metadata_parts = []
            if year:
                metadata_parts.append(f"📅 {year}")

            genres = movie.get("genres", [])
            if genres:
                metadata_parts.append(f"🎭 {', '.join(genres[:3])}")

            vote_average = movie.get("vote_average")
            if vote_average:
                metadata_parts.append(f"⭐ {vote_average:.1f}/10")

            director = movie.get("director")
            if director:
                metadata_parts.append(f"🎬 {director}")

            st.markdown(" • ".join(metadata_parts))

            # Exploration badge
            if is_exploration:
                st.markdown(
                    '<span class="exploration-badge">🔍 Exploration Pick</span>',
                    unsafe_allow_html=True,
                )

            # Score (if provided)
            if score is not None:
                st.progress(score, text=f"Match Score: {score*100:.0f}%")

            # Overview
            overview = movie.get("overview", "")
            if overview:
                with st.expander("📖 Plot Summary"):
                    st.write(overview)

            # Explanation
            if explanation:
                with st.expander("💡 Why We Recommend This", expanded=False):
                    st.info(explanation)


def render_movie_grid(movies: list, explanations: Dict[str, str] = None):
    """
    Render movies in a grid layout.

    Args:
        movies: List of movie dictionaries.
        explanations: Optional dict of movie_id -> explanation.
    """
    explanations = explanations or {}

    # Display in rows of 2
    for i in range(0, len(movies), 2):
        cols = st.columns(2)

        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(movies):
                movie = movies[idx]
                movie_id = str(movie.get("tmdb_id", ""))
                explanation = explanations.get(movie_id)

                with col:
                    render_movie_card(
                        movie=movie,
                        explanation=explanation,
                        rank=idx + 1,
                    )
