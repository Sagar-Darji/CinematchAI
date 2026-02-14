"""UI styles helpers."""

from pathlib import Path
import streamlit as st


def inject_cinema_theme():
    """Inject the cinema dark theme CSS into the Streamlit app."""
    css_path = Path(__file__).parent / "cinema.css"
    try:
        css = css_path.read_text()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except Exception:
        pass  # Gracefully skip if file missing
