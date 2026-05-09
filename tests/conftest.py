"""Pytest config — make unit tests hermetic from the developer's local .env.

Without this, pytest picks up AUTH_DATABASE_URL / DATABASE_URL from .env and
the service classes try to connect to Postgres on import. We force SQLite
under a temp data dir so tests don't touch the developer's real DB.
"""

import os
import tempfile
from pathlib import Path

# Force-empty Postgres-pointing vars BEFORE settings/db singletons get touched.
# pydantic-settings loads from .env at instantiation time, so we have to set
# real env entries (which take precedence over .env) — popping isn't enough.
os.environ["AUTH_DATABASE_URL"] = ""
os.environ["DATABASE_URL"] = ""

# Redirect data_dir to a session-scoped tempdir so users.db and friends are
# isolated from the developer's working state.
_tmp = Path(tempfile.mkdtemp(prefix="cinematch-tests-"))
os.environ.setdefault("DATA_DIR", str(_tmp))


def pytest_configure(config):
    """Reset cached singletons that may have been populated by other imports
    before this file ran (e.g. when pytest discovers tests via __init__.py)."""
    try:
        from config.settings import get_settings
        get_settings.cache_clear()
    except Exception:
        pass
    try:
        from src.core import db as _db
        _db._adapter = None
    except Exception:
        pass
