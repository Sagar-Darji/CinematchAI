"""Home Page - Entry point for the application."""

import streamlit as st

st.set_page_config(page_title="Home - CineMatch AI", page_icon="🏠", layout="wide")

# This is a duplicate of app.py content for navigation purposes
# Streamlit multi-page apps use numbered pages for ordering

st.markdown("## 🏠 Home")
st.info("Please use the main app (app.py) for the home page")

if st.button("← Return to Main App"):
    st.switch_page("app.py")
