"""Group Mode Page - Multi-user recommendations with fairness."""

import streamlit as st
import requests
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.ui.components.movie_card import render_movie_card

st.set_page_config(page_title="Group Mode - CineMatch AI", page_icon="👥", layout="wide")

API_BASE_URL = "http://localhost:8000"

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "onboarded" not in st.session_state:
    st.session_state.onboarded = False

# Header
st.title("👥 Group Recommendations")
st.markdown("Find movies that everyone will enjoy with fairness optimization")

# Check if user is onboarded
if not st.session_state.onboarded:
    st.warning("⚠️ Please complete onboarding first")
    if st.button("Go to Recommendations Page"):
        st.switch_page("pages/2_🎬_Recommendations.py")
else:
    # Group setup
    st.markdown("## 🎯 Setup Your Group")

    # Current user is always included
    st.info(f"👤 You: **{st.session_state.user_id}** (always included)")

    # Add other users
    num_others = st.number_input(
        "How many other people?",
        min_value=1,
        max_value=10,
        value=2,
    )

    other_users = []
    for i in range(num_others):
        user = st.text_input(
            f"User {i+2} username:",
            key=f"user_{i}",
            placeholder=f"e.g., friend{i+1}",
        )
        if user:
            other_users.append(user)

    # Aggregation strategy
    col1, col2 = st.columns(2)

    with col1:
        strategy = st.selectbox(
            "Aggregation Strategy",
            options=["multiplicative", "least_misery", "average"],
            format_func=lambda x: {
                "multiplicative": "⚖️ Balanced (Multiplicative)",
                "least_misery": "🎯 Fair (Least Misery)",
                "average": "📊 Simple Average",
            }[x],
        )

    with col2:
        num_recommendations = st.slider(
            "Number of Recommendations",
            min_value=5,
            max_value=20,
            value=10,
        )

    # Strategy explanation
    strategy_info = {
        "multiplicative": "Balances everyone's preferences. Movies liked by multiple users get higher weight.",
        "least_misery": "Ensures minimum satisfaction. Avoids movies that anyone strongly dislikes.",
        "average": "Simple averaging of all preferences. Treats everyone equally.",
    }

    st.info(f"ℹ️ **{strategy.title()}:** {strategy_info[strategy]}")

    # Shared context (optional)
    with st.expander("🎬 Shared Context (Optional)"):
        companion = st.selectbox(
            "Watching With",
            options=["", "friends", "family"],
            format_func=lambda x: "Not specified" if x == "" else x.title(),
        )

        occasion = st.text_input(
            "Occasion (optional)",
            placeholder="e.g., movie night, birthday party",
        )

    st.markdown("---")

    # Generate recommendations button
    all_users = [st.session_state.user_id] + other_users

    if len(all_users) >= 2:
        if st.button("🎬 Generate Group Recommendations", type="primary", use_container_width=True):
            with st.spinner("🤖 Analyzing group preferences and optimizing fairness..."):
                try:
                    # Build context
                    context = {}
                    if companion:
                        context["companion"] = companion
                    if occasion:
                        context["occasion"] = occasion

                    payload = {
                        "user_ids": all_users,
                        "context": context if context else None,
                        "aggregation_strategy": strategy,
                        "k": num_recommendations,
                    }

                    response = requests.post(
                        f"{API_BASE_URL}/api/v1/groups/recommendations",
                        json=payload,
                        timeout=45,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.group_recommendations = data.get("recommendations", [])
                        st.session_state.fairness_score = data.get("fairness_score", 0.0)
                        st.session_state.satisfaction_distribution = data.get(
                            "satisfaction_distribution", {}
                        )
                        st.session_state.conflict_areas = data.get("conflict_areas", [])
                    else:
                        st.error(f"Failed to get recommendations: {response.text}")

                except Exception as e:
                    st.error(f"Error: {e}")

    else:
        st.warning("⚠️ Please add at least one other user to the group")

    # Display recommendations
    if "group_recommendations" in st.session_state:
        recommendations = st.session_state.group_recommendations

        if recommendations:
            st.markdown("---")
            st.markdown("## 🎯 Group Recommendations")

            # Fairness metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                fairness = st.session_state.fairness_score
                st.metric(
                    "Fairness Score",
                    f"{fairness:.2f}",
                    help="How equally satisfied everyone will be (0-1, higher is better)",
                )

            with col2:
                satisfaction = st.session_state.satisfaction_distribution
                if satisfaction:
                    avg_satisfaction = sum(satisfaction.values()) / len(satisfaction)
                    st.metric("Avg Satisfaction", f"{avg_satisfaction:.2f}")

            with col3:
                st.metric("Group Size", len(all_users))

            # Per-user satisfaction
            if st.session_state.satisfaction_distribution:
                with st.expander("📊 Per-User Satisfaction", expanded=False):
                    for user_id, score in st.session_state.satisfaction_distribution.items():
                        st.progress(score, text=f"{user_id}: {score:.2f}")

            # Conflicts
            if st.session_state.conflict_areas:
                with st.expander("⚠️ Detected Conflicts", expanded=False):
                    for conflict in st.session_state.conflict_areas:
                        st.warning(conflict)

            st.markdown("---")

            # Display movies
            for rec in recommendations:
                movie = rec.get("movie", {})
                explanation = rec.get("explanation", "")
                rank = rec.get("rank", 0)
                score = rec.get("score", 0.0)

                render_movie_card(
                    movie=movie,
                    explanation=explanation,
                    rank=rank,
                    score=score,
                    is_exploration=False,
                )

                st.markdown("---")
