"""Session persistence for Streamlit — survives page refreshes."""

import json
import sqlite3
from pathlib import Path

_DB_PATH = Path("data") / "session.db"


def _get_conn():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    return conn


def save_session(user_id: str):
    """Persist user login so it survives Streamlit refresh."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO session (key, value) VALUES ('active_user', ?)",
        (json.dumps({"user_id": user_id, "onboarded": True}),),
    )
    conn.commit()
    conn.close()


def load_session() -> dict | None:
    """Load persisted session. Returns {"user_id": ..., "onboarded": True} or None."""
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT value FROM session WHERE key = 'active_user'"
        ).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def clear_session():
    """Clear persisted session (logout)."""
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM session WHERE key = 'active_user'")
        conn.commit()
        conn.close()
    except Exception:
        pass


def restore_streamlit_session():
    """Call at top of every page to restore session_state from DB if missing."""
    import streamlit as st

    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "onboarded" not in st.session_state:
        st.session_state.onboarded = False

    # Already have an active session in memory — nothing to do
    if st.session_state.user_id and st.session_state.onboarded:
        return

    # Try restoring from persistent store
    data = load_session()
    if data:
        st.session_state.user_id = data["user_id"]
        st.session_state.onboarded = data.get("onboarded", True)
