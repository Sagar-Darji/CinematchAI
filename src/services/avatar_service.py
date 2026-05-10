"""Avatar upload service — center-crops + resizes user-uploaded images and
stores them in a private S3 bucket. The DB stores a 7-day presigned GET URL
so the browser can fetch the image directly without going through Lambda.

The bucket (`cinematch-avatars-prod` in us-east-1) is private; access is via
the lambda role's CinematchAvatarsAccess inline policy. Local dev that
doesn't have AWS creds skips the S3 upload and stores nothing.
"""

import io
import os
from datetime import datetime, timezone
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

BUCKET = os.environ.get("AVATAR_BUCKET", "cinematch-avatars-prod")
REGION = os.environ.get("AVATAR_REGION", "us-east-1")
TARGET_SIZE = (256, 256)
MAX_INPUT_BYTES = 5 * 1024 * 1024  # reject anything bigger than 5 MB
PRESIGN_TTL_SECONDS = 7 * 24 * 3600  # 7 days

_service: Optional["AvatarService"] = None


def get_avatar_service() -> "AvatarService":
    global _service
    if _service is None:
        _service = AvatarService()
    return _service


class AvatarService:
    def __init__(self) -> None:
        self._client = None  # lazy

    def _s3(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=REGION)
        return self._client

    def _key(self, user_id: str) -> str:
        # Cheap path-safe identifier — user_ids are alphanum-ish already.
        # Append a cache-buster query later via versioned URL.
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return f"{safe}.jpg"

    def upload(self, user_id: str, image_bytes: bytes) -> str:
        """Resize + upload + return a presigned GET URL.

        Raises ValueError on bad input, RuntimeError on S3 failure.
        """
        if not image_bytes:
            raise ValueError("Empty upload")
        if len(image_bytes) > MAX_INPUT_BYTES:
            raise ValueError("Image too large (max 5 MB)")

        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(f"Pillow not installed: {exc}")

        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert("RGB")  # JPEG can't carry alpha
        except Exception as exc:
            raise ValueError(f"Could not decode image: {exc}")

        # Center-crop to a square, then resize to TARGET_SIZE.
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img.thumbnail(TARGET_SIZE, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        buf.seek(0)

        key = self._key(user_id)
        try:
            self._s3().put_object(
                Bucket=BUCKET,
                Key=key,
                Body=buf.getvalue(),
                ContentType="image/jpeg",
                CacheControl="public, max-age=86400",
            )
        except Exception as exc:
            raise RuntimeError(f"S3 upload failed: {exc}")

        return self._presign(key)

    def delete(self, user_id: str) -> None:
        key = self._key(user_id)
        try:
            self._s3().delete_object(Bucket=BUCKET, Key=key)
        except Exception as exc:
            logger.warning(f"Failed to delete avatar for {user_id}: {exc}")

    def refresh_url(self, user_id: str) -> Optional[str]:
        """Re-sign the existing object's URL — used when a stored URL nears
        expiry. Returns None if the object doesn't exist."""
        key = self._key(user_id)
        try:
            self._s3().head_object(Bucket=BUCKET, Key=key)
        except Exception:
            return None
        return self._presign(key)

    def _presign(self, key: str) -> str:
        url = self._s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=PRESIGN_TTL_SECONDS,
        )
        # Append a cache-buster (timestamp) so browsers/CloudFront pick up
        # a freshly-uploaded image even if the URL string hasn't changed.
        return f"{url}{'&' if '?' in url else '?'}v={int(datetime.now(timezone.utc).timestamp())}"
