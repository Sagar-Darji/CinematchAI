"""Admin Dashboard - Pipeline monitoring and system health."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
import requests

st.set_page_config(page_title="Admin - CineMatch AI", page_icon="🔧", layout="wide")

API_BASE_URL = "http://localhost:8000"

st.title("🔧 Admin Dashboard")

# --- Section 1: System Health ---
st.markdown("## System Health")

try:
    resp = requests.get(f"{API_BASE_URL}/api/v1/admin/stats", timeout=10)
    if resp.status_code == 200:
        stats = resp.json()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # API status - if we got here, API is up
            st.metric("API Status", "Online")

        with col2:
            st.metric("ChromaDB Movies", stats.get("chromadb_count", 0))

        with col3:
            st.metric("Total Users", stats.get("total_users", 0))

        with col4:
            st.metric("Total Ratings", stats.get("total_ratings", 0))

        # Trace stats
        trace_stats = stats.get("trace_stats", {})
        if trace_stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Requests", trace_stats.get("total_requests", 0))
            with col2:
                avg_ms = trace_stats.get("avg_duration_ms", 0)
                st.metric("Avg Duration", f"{avg_ms:.0f}ms" if avg_ms else "N/A")
            with col3:
                status_dist = trace_stats.get("status_distribution", {})
                failed = status_dist.get("failed", 0)
                st.metric("Failed Requests", failed)
    else:
        st.error(f"API returned status {resp.status_code}")
except requests.ConnectionError:
    st.error("Cannot connect to API at localhost:8000. Is the server running?")
except Exception as e:
    st.error(f"Error fetching stats: {e}")

st.markdown("---")

# --- Section 2: Source Distribution ---
st.markdown("## Data Source Distribution")

try:
    resp = requests.get(f"{API_BASE_URL}/api/v1/admin/stats", timeout=10)
    if resp.status_code == 200:
        stats = resp.json()
        source_dist = stats.get("trace_stats", {}).get("source_distribution", {})

        if source_dist:
            import pandas as pd

            source_labels = {
                "chromadb_personalized": "ChromaDB (Personalized)",
                "tmdb_cold_start": "TMDB API (Cold Start)",
                "chromadb_cold_start": "ChromaDB (Cold Start)",
                "unknown": "Unknown",
            }

            chart_data = {
                source_labels.get(k, k): v for k, v in source_dist.items()
            }
            df = pd.DataFrame(
                {"Source": list(chart_data.keys()), "Count": list(chart_data.values())}
            )
            st.bar_chart(df.set_index("Source"))
        else:
            st.info("No pipeline traces yet. Generate some recommendations to see data source distribution.")
except Exception:
    pass

st.markdown("---")

# --- Section 3: Pipeline Log ---
st.markdown("## Pipeline Log")

filter_user = st.text_input("Filter by User ID (optional)", key="trace_filter_user")

try:
    params = {"limit": 20}
    if filter_user:
        params["user_id"] = filter_user

    resp = requests.get(f"{API_BASE_URL}/api/v1/admin/traces", params=params, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        traces = data.get("traces", [])

        if not traces:
            st.info("No pipeline traces found.")
        else:
            for trace in traces:
                trace_id = trace.get("trace_id", "")[:8]
                status = trace.get("status", "unknown")
                user = trace.get("user_id", "N/A")
                source = trace.get("retrieval_source", "N/A")
                duration = trace.get("total_duration_ms")
                final_count = trace.get("final_count", 0)
                started = trace.get("started_at", "")

                # Status badge
                if status == "completed":
                    badge = "✅"
                elif status == "running":
                    badge = "🔄"
                else:
                    badge = "❌"

                # Source badge
                source_badge = ""
                if source == "chromadb_personalized":
                    source_badge = "🟢 ChromaDB"
                elif source == "tmdb_cold_start":
                    source_badge = "🟡 TMDB API"
                elif source:
                    source_badge = f"⚪ {source}"

                duration_str = f"{duration:.0f}ms" if duration else "N/A"

                header = f"{badge} `{trace_id}` | User: **{user}** | {source_badge} | {duration_str} | {final_count} results | {started[:19]}"

                with st.expander(header, expanded=False):
                    steps = trace.get("steps", [])
                    if steps:
                        for step in steps:
                            agent = step.get("agent_name", "Unknown")
                            step_dur = step.get("duration_ms", 0)
                            summary = step.get("summary", "")
                            details = step.get("details", {})

                            st.markdown(f"**{agent}** ({step_dur:.0f}ms) — {summary}")
                            if details:
                                st.json(details)
                    else:
                        st.write("No step details recorded.")

                    # Full context
                    ctx = trace.get("context", {})
                    if ctx:
                        st.markdown("**Context:**")
                        st.json(ctx)
except Exception as e:
    st.error(f"Error fetching traces: {e}")

st.markdown("---")

# --- Section 4: Profile Inspector ---
st.markdown("## Profile Inspector")

inspect_user = st.text_input("Enter User ID to inspect", key="inspect_user")

if inspect_user:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/v1/admin/users/{inspect_user}/profile",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()

            if data.get("has_running_job"):
                st.warning("Profile is being rebuilt... data may be stale.")

            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Ratings", data.get("total_ratings", 0))
            with col2:
                st.metric("Profile Status", data.get("profile_status", "none"))
            with col3:
                cold = data.get("is_cold_start", True)
                st.metric("Cold Start", "Yes" if cold else "No")
            with col4:
                avg = data.get("avg_rating_given")
                st.metric("Avg Rating", f"{avg:.1f}" if avg else "N/A")

            # Preferences
            prefs = data.get("preferences", {})
            if prefs:
                st.markdown("### Preferences")
                col1, col2 = st.columns(2)
                with col1:
                    genres = prefs.get("favorite_genres", [])
                    if genres:
                        st.markdown("**Favorite Genres:** " + ", ".join(genres))
                    directors = prefs.get("favorite_directors", [])
                    if directors:
                        st.markdown("**Favorite Directors:** " + ", ".join(directors))
                with col2:
                    st.metric("Exploration Rate", f"{prefs.get('exploration_rate', 0):.0%}")
                    st.metric("Risk Tolerance", f"{prefs.get('risk_tolerance', 0):.0%}")

            # Temporal patterns
            temporal = data.get("temporal_patterns", {})
            if temporal and any(v for v in temporal.values() if v):
                st.markdown("### Temporal Patterns")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Peak Time:** {temporal.get('peak_viewing_time', 'N/A')}")
                with col2:
                    st.write(f"**Peak Day:** {temporal.get('peak_viewing_day', 'N/A')}")
                with col3:
                    st.write(f"**Weekend Pref:** {temporal.get('weekend_preference', 'N/A')}")

            # Import history
            jobs = data.get("jobs", [])
            if jobs:
                st.markdown("### Import History")
                for job in jobs:
                    st.write(
                        f"- **{job['job_type']}** | {job['status']} | {job['created_at'][:19]} | "
                        f"Progress: {job['progress']}/{job['total']}"
                    )

            # Recent ratings
            recent = data.get("recent_ratings", [])
            if recent:
                st.markdown("### Recent Ratings")
                for r in recent[:10]:
                    st.write(f"- Movie `{r['movie_id']}` — ⭐ {r['rating']}/5.0 — {r['timestamp'][:19]}")
        else:
            st.warning(f"User not found or error: {resp.text}")
    except Exception as e:
        st.error(f"Error inspecting user: {e}")
