"""JWT creation and verification."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from config.settings import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

_DEV_FALLBACK = "cinematch-dev-secret-change-in-prod"


def _secret() -> str:
    """Resolve the JWT signing secret.

    In production (DEPLOYMENT_ENV=production) we refuse to start without an
    explicitly-set JWT_SECRET — silently signing tokens with the dev
    placeholder used to be a vector for forging tokens against the deployed
    Lambda. Local dev keeps the placeholder so first-run setup works.
    """
    s = get_settings()
    raw = getattr(s, "jwt_secret", None) or os.environ.get("JWT_SECRET") or ""

    # The pydantic-settings default for jwt_secret is also _DEV_FALLBACK, so we
    # have to treat that string as "not configured" rather than as a real key.
    if raw and raw != _DEV_FALLBACK:
        return raw

    deployment_env = (
        os.environ.get("DEPLOYMENT_ENV")
        or getattr(s, "deployment_env", None)
        or "development"
    ).lower()
    if deployment_env == "production":
        raise RuntimeError(
            "JWT_SECRET is not configured. Refusing to use the development "
            "fallback in production. Set the JWT_SECRET environment variable "
            "to a long random string (e.g. `openssl rand -hex 32`)."
        )
    return _DEV_FALLBACK


def create_access_token(user_id: str, email: Optional[str] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire}
    if email:
        payload["email"] = email
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Returns payload dict with 'sub' (user_id) on success, None on failure."""
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None
