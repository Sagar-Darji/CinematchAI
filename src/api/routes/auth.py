"""Auth routes — register, login (password), login (Google OAuth), /me."""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator

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
    identifier: str  # email or username
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
    svc.create_user_stub(req.username)

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
    """Sign in with email or username + password."""
    svc = get_user_service()
    identifier = req.identifier.strip()

    # Try email first, then fall back to username lookup
    record = svc.get_user_by_email(identifier)
    if not record:
        record = svc.get_user_by_username(identifier)

    if not record:
        raise HTTPException(status_code=401, detail="Invalid email/username or password")
    if record["auth_provider"] == "google":
        raise HTTPException(status_code=400, detail="This account uses Google sign-in. Please use 'Continue with Google'.")
    if not record["password_hash"] or not verify_password(req.password, record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email/username or password")

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

    # Create stub profile row
    svc.create_user_stub(username)

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


# ── Password Reset ─────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


def _send_reset_email(to_email: str, reset_link: str) -> bool:
    """Send reset email via SMTP. Returns True on success, False if SMTP not configured."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    settings = get_settings()
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password]):
        return False

    from_addr = settings.smtp_from or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset your CineMatch AI password"
    msg["From"] = from_addr
    msg["To"] = to_email

    text = f"Reset your password:\n\n{reset_link}\n\nThis link expires in 1 hour."
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px">
      <h2 style="color:#c9a84c">CineMatch AI</h2>
      <p>You requested a password reset. Click the button below to set a new password.</p>
      <a href="{reset_link}" style="display:inline-block;background:#c9a84c;color:#0a0a0f;padding:14px 28px;border-radius:10px;font-weight:bold;text-decoration:none;margin:16px 0">
        Reset Password
      </a>
      <p style="color:#888;font-size:13px">This link expires in 1 hour. If you didn't request a reset, ignore this email.</p>
    </div>"""
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(from_addr, to_email, msg.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(from_addr, to_email, msg.as_string())
        return True
    except Exception as exc:
        logger.error(f"SMTP send failed: {exc}")
        return False


@router.post("/forgot-password", status_code=200)
async def forgot_password(req: ForgotPasswordRequest):
    """
    Request a password reset link.
    Always returns 200 (never reveals whether the email exists).
    """
    import secrets
    from datetime import datetime, timezone, timedelta

    svc = get_user_service()
    email = req.email.lower().strip()
    user = svc.get_user_by_email(email)

    if user:
        if user.get("auth_provider") == "google" and not user.get("password_hash"):
            # Google-only account — still return 200, just don't send a reset
            logger.info(f"Forgot-password: {email} is Google-only, skipping reset email")
            return {"message": "If that email is registered, a reset link has been sent."}

        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        svc.set_reset_token(user["user_id"], token, expires_at)

        settings = get_settings()
        app_url = getattr(settings, "app_url", None) or "http://localhost:3000"
        reset_link = f"{app_url}/reset-password?token={token}"

        sent = _send_reset_email(email, reset_link)
        if not sent:
            # Dev fallback: log the link so it can be used without email config
            logger.warning(f"[DEV] Password reset link for {email}: {reset_link}")

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
async def reset_password(req: ResetPasswordRequest):
    """Consume a reset token and set a new password."""
    svc = get_user_service()
    user_id = svc.consume_reset_token(req.token.strip())
    if not user_id:
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired.")

    svc.update_password(user_id, hash_password(req.new_password))
    logger.info(f"Password reset for user: {user_id}")
    return {"message": "Password updated successfully. You can now sign in."}

