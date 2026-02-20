"""JWT creation and verification."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from config.settings import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def _secret() -> str:
    s = get_settings()
    secret = getattr(s, "jwt_secret", None) or "cinematch-dev-secret-change-in-prod"
    return secret


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
