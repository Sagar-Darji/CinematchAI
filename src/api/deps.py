"""FastAPI dependencies — auth resolution, etc."""

from typing import Optional

from fastapi import Header, HTTPException, status

from src.core.auth.jwt import decode_access_token


def _strip_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> str:
    """Resolve the authenticated user_id from a Bearer token.

    Raises 401 on missing or invalid token. Use as a FastAPI dependency on
    every endpoint that operates on user-owned data.
    """
    token = _strip_bearer(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(payload["sub"])


async def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    """Same as get_current_user, but returns None instead of raising.

    For endpoints that render different content for anonymous vs logged-in
    users (e.g. public movie detail pages).
    """
    token = _strip_bearer(authorization)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
