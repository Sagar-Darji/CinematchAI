"""CineMatch AI - Main Streamlit Application."""

import streamlit as st

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

    # Navigation cards
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="feature-card">
                <h3>🎬 Get Recommendations</h3>
                <p>Discover movies tailored to your taste and current mood</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Browse Recommendations", use_container_width=True):
            st.switch_page("pages/2_🎬_Recommendations.py")

    with col2:
        st.markdown(
            """
            <div class="feature-card">
                <h3>👥 Group Mode</h3>
                <p>Find movies that everyone in your group will love</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start Group Session", use_container_width=True):
            st.switch_page("pages/3_👥_Group_Mode.py")

    with col3:
        st.markdown(
            """
            <div class="feature-card">
                <h3>📊 My Profile</h3>
                <p>View your taste profile and watching statistics</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("View Profile", use_container_width=True):
            st.switch_page("pages/4_📊_Profile.py")

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
