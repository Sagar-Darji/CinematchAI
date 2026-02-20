"""Auth routes — register, login (password), login (Google OAuth), /me."""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator

from config.settings import get_settings
from src.core.auth.jwt import create_access_token
from src.core.auth.password import hash_password, verify_password
from src.services.user_service import get_user_service
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ── Schemas ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]{3,32}$", v):
            raise ValueError("Username must be 3–32 characters: letters, numbers, _ or -")
        return v

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    """Frontend sends the raw Google ID token string."""
    id_token: str
    username: str | None = None  # required only for first-time Google sign-up


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    is_new_user: bool


# ── Helpers ────────────────────────────────────────────────────────────────────

def _verify_google_token(id_token: str) -> dict:
    """Verify Google ID token and return its payload."""
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    settings = get_settings()
    client_id = settings.google_client_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server",
        )
    try:
        payload = google_id_token.verify_oauth2_token(
            id_token, google_requests.Request(), client_id
        )
        return payload
    except Exception as exc:
        logger.warning(f"Google token verification failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """Create a new account with username + email + password."""
    svc = get_user_service()

    # Email uniqueness check
    if svc.get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # Username uniqueness check
    if svc.get_user_profile(req.username):
        raise HTTPException(status_code=409, detail="Username already taken")

    # Create a stub profile row so the user_id exists in the DB
    now = datetime.now(timezone.utc).isoformat()
    import sqlite3, json
    from pathlib import Path
    from config.settings import get_settings as _gs
    db_path = Path(_gs().data_dir) / "users.db"
    stub_profile = json.dumps({"user_id": req.username, "total_ratings": 0, "is_cold_start": True})
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, created_at, updated_at, profile_json) VALUES (?,?,?,?)",
        (req.username, now, now, stub_profile)
    )
    conn.commit()
    conn.close()

    # Write auth credentials
    svc.set_auth_credentials(
        user_id=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        auth_provider="password",
    )

    token = create_access_token(req.username, req.email)
    logger.info(f"New user registered: {req.username} ({req.email})")
    return AuthResponse(token=token, user_id=req.username, email=req.email, is_new_user=True)


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Sign in with email + password."""
    svc = get_user_service()
    record = svc.get_user_by_email(req.email)

    if not record:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if record["auth_provider"] == "google":
        raise HTTPException(status_code=400, detail="This account uses Google sign-in. Please use 'Continue with Google'.")
    if not record["password_hash"] or not verify_password(req.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(record["user_id"], record["email"])
    return AuthResponse(token=token, user_id=record["user_id"], email=record["email"], is_new_user=False)


@router.post("/google", response_model=AuthResponse)
async def google_login(req: GoogleLoginRequest):
    """Sign in or register via Google OAuth ID token."""
    payload = _verify_google_token(req.id_token)

    google_id = payload["sub"]
    email     = payload.get("email", "").lower().strip()
    svc       = get_user_service()

    # Existing Google user
    existing = svc.get_user_by_google_id(google_id)
    if existing:
        token = create_access_token(existing["user_id"], existing["email"])
        return AuthResponse(token=token, user_id=existing["user_id"],
                            email=existing["email"], is_new_user=False)

    # Existing account with same email (was password user, now logging in via Google)
    by_email = svc.get_user_by_email(email)
    if by_email:
        svc.set_auth_credentials(
            user_id=by_email["user_id"],
            email=email,
            password_hash=by_email["password_hash"],  # keep existing password too
            auth_provider="google",
            google_id=google_id,
        )
        token = create_access_token(by_email["user_id"], email)
        return AuthResponse(token=token, user_id=by_email["user_id"],
                            email=email, is_new_user=False)

    # Brand new Google user — need a username
    username = (req.username or "").strip()
    if not username:
        # Auto-derive from email prefix, ensure it's unique
        base = re.sub(r"[^a-zA-Z0-9_]", "_", email.split("@")[0])[:20]
        username = base
        counter = 1
        while svc.get_user_profile(username):
            username = f"{base}_{counter}"
            counter += 1

    if svc.get_user_profile(username):
        raise HTTPException(status_code=409, detail="Username already taken. Please choose another.")

    now = datetime.now(timezone.utc).isoformat()
    import sqlite3, json
    from pathlib import Path
    from config.settings import get_settings as _gs
    db_path = Path(_gs().data_dir) / "users.db"
    stub_profile = json.dumps({"user_id": username, "total_ratings": 0, "is_cold_start": True})
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, created_at, updated_at, profile_json) VALUES (?,?,?,?)",
        (username, now, now, stub_profile)
    )
    conn.commit()
    conn.close()

    svc.set_auth_credentials(
        user_id=username,
        email=email,
        password_hash=None,
        auth_provider="google",
        google_id=google_id,
    )

    token = create_access_token(username, email)
    logger.info(f"New Google user: {username} ({email})")
    return AuthResponse(token=token, user_id=username, email=email, is_new_user=True)


@router.get("/me")
async def me(token: str):
    """Validate a token and return current user info."""
    from src.core.auth.jwt import decode_access_token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    svc = get_user_service()
    record = svc.get_auth_record(payload["sub"])
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": record["user_id"],
        "email": record["email"],
        "auth_provider": record["auth_provider"],
    }
