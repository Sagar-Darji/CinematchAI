"""Import staging — stores user-uploaded CSVs in S3 so chunked workers can
stream slices of the file across many Lambda invocations without keeping
the CSV in the Lambda Event payload (256 KB hard limit) or in process
memory.

Bucket: `cinematch-imports-prod` (private, us-east-1). Lambda role has
CinematchImportsAccess (s3:PutObject / GetObject / DeleteObject on the
bucket's objects). 7-day lifecycle rule deletes stale objects.

Key pattern: `{user_id}/{job_id}.csv`. Keys are namespaced by user so
listing a user's imports is one prefix scan and one user can't see
another's CSV.
"""

import io
import os
from typing import Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

BUCKET = os.environ.get("IMPORTS_BUCKET", "cinematch-imports-prod")
REGION = os.environ.get("IMPORTS_REGION", "us-east-1")

_service: Optional["ImportStagingService"] = None


def get_import_staging_service() -> "ImportStagingService":
    global _service
    if _service is None:
        _service = ImportStagingService()
    return _service


class ImportStagingService:
    def __init__(self) -> None:
        self._client = None  # lazy — keeps unit-test imports cheap

    def _s3(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=REGION)
        return self._client

    @staticmethod
    def key_for(user_id: str, job_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return f"{safe}/{job_id}.csv"

    @staticmethod
    def extras_key_for(user_id: str, job_id: str) -> str:
        """Sister key holding ZIP-extracted reviews/watchlist/likes/watched
        JSON for the same job. Same 7-day lifecycle rule applies."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        return f"{safe}/{job_id}_extras.json"

    def put_extras(self, user_id: str, job_id: str, extras_payload: dict) -> str:
        """Persist the non-ratings ZIP sections (reviews, watchlist, likes,
        watched) so the chunk worker can ingest them after the ratings
        phase. Returns the S3 key."""
        import json as _json
        key = self.extras_key_for(user_id, job_id)
        body = _json.dumps(extras_payload).encode("utf-8")
        self._s3().put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        logger.info(f"Staged import extras at s3://{BUCKET}/{key} ({len(body)} bytes)")
        return key

    def get_extras(self, s3_key: str) -> dict:
        import json as _json
        obj = self._s3().get_object(Bucket=BUCKET, Key=s3_key)
        return _json.loads(obj["Body"].read().decode("utf-8"))

    def put_csv(self, user_id: str, job_id: str, csv_content: str) -> str:
        """Upload the raw CSV. Returns the S3 key for storage on the job row."""
        key = self.key_for(user_id, job_id)
        body = csv_content.encode("utf-8")
        self._s3().put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body,
            ContentType="text/csv",
            # Server-side encryption with S3-managed keys; same default the
            # avatar bucket uses, no key management overhead.
            ServerSideEncryption="AES256",
        )
        logger.info(f"Staged import CSV at s3://{BUCKET}/{key} ({len(body)} bytes)")
        return key

    def get_csv(self, s3_key: str) -> str:
        """Pull the full CSV (small enough that Range reads aren't worth it
        for typical libraries — a 5000-row Letterboxd ratings.csv is < 1 MB).
        Returns the decoded UTF-8 string."""
        obj = self._s3().get_object(Bucket=BUCKET, Key=s3_key)
        return obj["Body"].read().decode("utf-8")

    def delete(self, s3_key: str) -> None:
        try:
            self._s3().delete_object(Bucket=BUCKET, Key=s3_key)
        except Exception as exc:
            logger.warning(f"Failed to delete staged CSV {s3_key}: {exc}")
