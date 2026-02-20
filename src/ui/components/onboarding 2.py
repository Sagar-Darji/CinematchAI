"""Onboarding Component - Interactive cold-start flow."""

import streamlit as st
import requests
from typing import Dict, List
from src.ui.session import save_session


API_BASE_URL = "http://localhost:8000"


def render_onboarding_flow():
    """
    Render interactive onboarding flow for new users.

    Returns:
        Boolean indicating if onboarding is complete.
    """
    st.markdown("## 🎬 Welcome to CineMatch AI!")
    st.markdown(
        """
        To get started, we need to understand your movie preferences.
        Choose one of the options below:
        """
    )

    # Onboarding method selection
    tab1, tab2 = st.tabs(["📥 Import from Letterboxd", "⭐ Rate Movies Manually"])

    with tab1:
        letterboxd_complete = _render_letterboxd_import()
        if letterboxd_complete:
            return True

    with tab2:
        manual_complete = _render_manual_onboarding()
        if manual_complete:
            return True

    return False


def _render_letterboxd_import() -> bool:
    """
    Render Letterboxd CSV import interface.

    Returns:
        True if import is successful.
    """
    st.markdown("### 📥 Import Your Letterboxd History")
    st.markdown(
        """
        Already have a Letterboxd account? Import your ratings instantly!

        **How to export from Letterboxd:**
        1. Go to [letterboxd.com/settings/data](https://letterboxd.com/settings/data)
        2. Click "Export your data"
        3. Download the ZIP file
        4. Extract and upload the `ratings.csv` file below
        """
    )

    st.markdown("---")

    # User ID input
    user_id = st.text_input(
        "Enter your username:",
        value="",
        placeholder="e.g., john_doe",
        key="letterboxd_user_id",
    )

    # CSV file upload
    uploaded_file = st.file_uploader(
        "Upload your Letterboxd ratings.csv",
        type=["csv"],
        help="Export your data from Letterboxd and upload the ratings.csv file",
    )

    if uploaded_file and user_id:
        # Preview
        st.markdown("#### Preview")
        try:
            import pandas as pd
            from io import StringIO

            csv_content = uploaded_file.getvalue().decode("utf-8")
            df = pd.read_csv(StringIO(csv_content))

            # Show preview
            st.dataframe(df.head(10), use_container_width=True)
            st.caption(f"Total entries: {len(df)} movies")

            # Import button
            if st.button("🚀 Import Ratings", type="primary", use_container_width=True):
                return _import_from_letterboxd(user_id, csv_content)

        except Exception as e:
            st.error(f"Failed to read CSV: {e}")
            st.info("Make sure you uploaded the correct ratings.csv file from Letterboxd")

    elif uploaded_file:
        st.warning("Please enter a username first")
    else:
        st.info("Upload your Letterboxd ratings.csv file to get started")

    return False


def _import_from_letterboxd(user_id: str, csv_content: str) -> bool:
    """Import ratings from Letterboxd CSV with async polling."""
    import time

    with st.spinner("🎬 Starting Letterboxd import..."):
        try:
            # Start import (returns immediately)
            payload = {
                "user_id": user_id,
                "csv_content": csv_content,
            }

            response = requests.post(
                f"{API_BASE_URL}/api/v1/users/import/letterboxd",
                json=payload,
                timeout=10,  # Quick timeout (just to start job)
            )

            if response.status_code == 202:  # Accepted
                data = response.json()
                job_id = data["job_id"]
                total_movies = data["total_movies"]

                st.info(f"📋 Import job created: {job_id}")
                st.info(f"📊 Total movies to import: {total_movies}")

                # Poll for status
                progress_bar = st.progress(0, text="Starting import...")
                status_text = st.empty()

                max_polls = 600  # Max 10 minutes (600 * 1 second)
                poll_count = 0

                while poll_count < max_polls:
                    # Check status
                    status_resp = requests.get(
                        f"{API_BASE_URL}/api/v1/users/jobs/{job_id}",
                        timeout=5,
                    )

                    if status_resp.status_code == 200:
                        job_data = status_resp.json()
                        status = job_data["status"]
                        progress = job_data.get("progress", 0)

                        # Calculate imported count
                        imported_so_far = int((progress / 100.0) * total_movies)

                        # Update UI
                        progress_bar.progress(
                            progress / 100.0,
                            text=f"Importing... {progress}%"
                        )
                        status_text.text(
                            f"📥 Progress: {imported_so_far}/{total_movies} movies processed"
                        )

                        if status == "completed":
                            # Success
                            result = job_data.get("result", {})
                            imported = result.get("imported_count", 0)
                            failed = result.get("failed_count", 0)
                            success_rate = result.get("success_rate", 0) * 100

                            progress_bar.progress(1.0, text="✅ Import complete!")

                            st.success(
                                f"✅ Successfully imported {imported}/{total_movies} ratings!\n\n"
                                f"Success rate: {success_rate:.1f}%\n\n"
                                f"✅ Imported: {imported} | ❌ Failed: {failed}"
                            )

                            # Save user ID to session (persistent)
                            st.session_state.user_id = user_id
                            st.session_state.onboarded = True
                            save_session(user_id)

                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                            return True

                        elif status == "failed":
                            # Failed
                            error_msg = job_data.get("error_message", "Unknown error")
                            progress_bar.progress(0, text="❌ Import failed")
                            st.error(f"❌ Import failed: {error_msg}")
                            return False

                        # Still running, wait and poll again
                        poll_count += 1
                        time.sleep(1)  # Poll every 1 second
                    else:
                        st.error("Failed to check job status")
                        return False

                # Timeout
                st.error(f"⏱️ Import timed out after {max_polls} seconds. Check job status later.")
                return False

            else:
                st.error(f"Failed to start import: {response.text}")
                return False

        except Exception as e:
            st.error(f"Error during import: {e}")
            import traceback
            st.code(traceback.format_exc())
            return False


def _render_manual_onboarding() -> bool:
    """
    Render manual movie rating interface.

    Returns:
        True if onboarding is complete.
    """
    st.markdown("### ⭐ Rate Movies Manually")
    st.markdown("Rate at least 5 movies to create your personalized profile")

    # Initialize session state for ratings
    if "onboarding_ratings" not in st.session_state:
        st.session_state.onboarding_ratings = {}

    if "onboarding_movies" not in st.session_state:
        # Fetch onboarding movies
        with st.spinner("Loading movies..."):
            try:
                response = requests.get(
                    f"{API_BASE_URL}/api/v1/users/onboarding-movies?k=20",
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    st.session_state.onboarding_movies = data.get("movies", [])
                else:
                    st.error("Failed to load onboarding movies")
                    st.session_state.onboarding_movies = []

            except Exception as e:
                st.error(f"Error connecting to API: {e}")
                st.session_state.onboarding_movies = _get_fallback_movies()

    movies = st.session_state.onboarding_movies

    if not movies:
        st.warning("No movies available for onboarding")
        return False

    # Progress indicator
    rated_count = len(st.session_state.onboarding_ratings)
    progress_text = f"Progress: {rated_count}/5 minimum ({rated_count} rated)"
    st.progress(
        min(rated_count / 5, 1.0),
        text=progress_text,
    )

    st.markdown("---")
    st.markdown("*Select a star rating (1-5) for movies you've seen*")

    # Display movies in grid
    for i in range(0, min(len(movies), 20), 2):
        cols = st.columns(2)

        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(movies):
                movie = movies[idx]
                movie_id = str(movie.get("tmdb_id", ""))

                with col:
                    _render_rating_card(movie, movie_id)

    # Completion section
    st.markdown("---")

    if rated_count >= 5:
        st.success(f"✅ Great! You've rated {rated_count} movies.")

        # User ID input
        user_id = st.text_input(
            "Enter your username:",
            value="",
            placeholder="e.g., john_doe",
            key="onboarding_user_id",
        )

        if st.button("🚀 Complete Onboarding", type="primary", use_container_width=True):
            if not user_id:
                st.error("Please enter a username")
            else:
                return _complete_onboarding(user_id, st.session_state.onboarding_ratings)
    else:
        st.info(f"📝 Please rate at least {5 - rated_count} more movie(s) to continue.")

    return False


def _render_rating_card(movie: Dict, movie_id: str):
    """Render a single movie rating card."""
    with st.container():
        # Movie info
        title = movie.get("title", "Unknown")
        year = movie.get("year", "")
        genres = movie.get("genres", [])

        st.markdown(f"**{title}** ({year})")
        if genres:
            st.caption(f"🎭 {', '.join(genres[:2])}")

        # Rating selector
        current_rating = st.session_state.onboarding_ratings.get(movie_id, 0)

        rating = st.select_slider(
            "Rating",
            options=[0, 1, 2, 3, 4, 5],
            value=current_rating,
            format_func=lambda x: "⭐" * x if x > 0 else "Not Rated",
            key=f"rating_{movie_id}",
            label_visibility="collapsed",
        )

        # Update session state
        if rating > 0:
            st.session_state.onboarding_ratings[movie_id] = float(rating)
        elif movie_id in st.session_state.onboarding_ratings:
            del st.session_state.onboarding_ratings[movie_id]


def _complete_onboarding(user_id: str, ratings: Dict[str, float]) -> bool:
    """
    Complete onboarding by submitting to API.

    Args:
        user_id: User ID.
        ratings: Movie ratings (movie_id -> rating).

    Returns:
        True if successful.
    """
    with st.spinner("Creating your profile..."):
        try:
            payload = {
                "user_id": user_id,
                "ratings": ratings,
            }

            response = requests.post(
                f"{API_BASE_URL}/api/v1/users/onboard",
                json=payload,
                timeout=120,
            )

            if response.status_code in [200, 201]:
                st.success("✅ Onboarding complete! Redirecting...")

                # Save user ID to session (persistent)
                st.session_state.user_id = user_id
                st.session_state.onboarded = True
                save_session(user_id)

                # Clear onboarding data
                del st.session_state.onboarding_ratings
                del st.session_state.onboarding_movies

                st.rerun()
                return True
            else:
                st.error(f"Failed to onboard: {response.text}")
                return False

        except Exception as e:
            st.error(f"Error: {e}")
            return False


def _get_fallback_movies() -> List[Dict]:
    """Get fallback movies if API is unavailable."""
    return [
        {
            "tmdb_id": 550,
            "title": "Fight Club",
            "year": 1999,
            "genres": ["Drama"],
        },
        {
            "tmdb_id": 680,
            "title": "Pulp Fiction",
            "year": 1994,
            "genres": ["Crime", "Drama"],
        },
        {
            "tmdb_id": 13,
            "title": "Forrest Gump",
            "year": 1994,
            "genres": ["Comedy", "Drama", "Romance"],
        },
        {
            "tmdb_id": 155,
            "title": "The Dark Knight",
            "year": 2008,
            "genres": ["Action", "Crime", "Drama"],
        },
        {
            "tmdb_id": 278,
            "title": "The Shawshank Redemption",
            "year": 1994,
            "genres": ["Drama"],
        },
    ]
