"""Job Service - Async job tracking for background tasks."""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.db import get_db, register_pk
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobStatus(str, Enum):
    """Job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    """Job type enum."""
    LETTERBOXD_IMPORT = "letterboxd_import"
    PROFILE_BUILD = "profile_build"
    RECOMMENDATION_GENERATE = "recommendation_generate"


class JobService:
    """Service for tracking background jobs using shared DB (Supabase on Lambda, SQLite locally)."""

    def __init__(self):
        self._init_database()

    def _init_database(self):
        with get_db().connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    progress INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 100,
                    result_json TEXT,
                    error_message TEXT
                )
            """)
            # Chunked-import additions. Live jobs read these to resume after
            # a Lambda timeout: the next worker invocation reads
            # next_chunk_index, processes that chunk's slice of the S3
            # CSV, and atomically advances the counter.
            for col, definition in [
                ("chunk_size",       "INTEGER DEFAULT 50"),
                ("next_chunk_index", "INTEGER DEFAULT 0"),
                ("s3_key",           "TEXT"),
                # extras_s3_key holds a JSON blob of reviews/watchlist/likes/
                # watched extracted from the Letterboxd ZIP. NULL when the
                # upload was a bare ratings.csv (legacy path).
                ("extras_s3_key",    "TEXT"),
                # raw_s3_key holds the user's raw upload (ZIP or CSV) BEFORE
                # parsing. Set by the import endpoint, consumed once by the
                # letterboxd-prep worker. Lets the endpoint return 202 in
                # <2s no matter how heavy the parse path is.
                ("raw_s3_key",       "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {definition}")
                except Exception:
                    pass  # column already exists — idempotent
        register_pk("jobs", ["job_id"])
        logger.info("Job database initialized")

    def create_job(
        self,
        job_type: JobType,
        user_id: str,
        total: int = 100,
        s3_key: Optional[str] = None,
        chunk_size: Optional[int] = None,
        extras_s3_key: Optional[str] = None,
        raw_s3_key: Optional[str] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with get_db().connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, job_type, user_id, status, created_at, total, "
                "s3_key, chunk_size, next_chunk_index, extras_s3_key, raw_s3_key) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id, job_type.value, user_id, JobStatus.PENDING.value, now, total,
                    s3_key, chunk_size or 50, 0, extras_s3_key, raw_s3_key,
                ),
            )
        logger.info(f"Created job {job_id}: type={job_type}, user={user_id}")
        return job_id

    def update_job_fields(
        self,
        job_id: str,
        *,
        s3_key: Optional[str] = None,
        extras_s3_key: Optional[str] = None,
        total: Optional[int] = None,
    ) -> None:
        """Patch a subset of job fields. Used by the letterboxd-prep worker
        once preprocessing has produced the merged CSV + extras + row
        count; the chunk worker then reads these to start processing."""
        sets: List[str] = []
        params: List[Any] = []
        if s3_key is not None:
            sets.append("s3_key = ?")
            params.append(s3_key)
        if extras_s3_key is not None:
            sets.append("extras_s3_key = ?")
            params.append(extras_s3_key)
        if total is not None:
            sets.append("total = ?")
            params.append(total)
        if not sets:
            return
        params.append(job_id)
        with get_db().connect() as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?",
                tuple(params),
            )

    def advance_chunk(self, job_id: str, new_index: int, progress: int) -> None:
        """Atomically advance the chunk counter and progress in one UPDATE
        so concurrent workers don't double-process. Used by the chunked
        Letterboxd import worker after each chunk finishes."""
        with get_db().connect() as conn:
            conn.execute(
                "UPDATE jobs SET next_chunk_index = ?, progress = ?, "
                "status = ? WHERE job_id = ?",
                (new_index, progress, JobStatus.RUNNING.value, job_id),
            )

    def update_job_status(self, job_id: str, status: JobStatus, progress: Optional[int] = None, error_message: Optional[str] = None):
        now = datetime.utcnow().isoformat()
        updates = ["status = ?"]
        params = [status.value]
        if status == JobStatus.RUNNING:
            updates.append("started_at = ?")
            params.append(now)
        if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            updates.append("completed_at = ?")
            params.append(now)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)
        params.append(job_id)
        with get_db().connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?", params)
        logger.info(f"Updated job {job_id}: status={status}, progress={progress}")

    def update_job_result(self, job_id: str, result: Dict[str, Any]):
        with get_db().connect() as conn:
            conn.execute(
                "UPDATE jobs SET result_json = ? WHERE job_id = ?",
                (json.dumps(result), job_id),
            )
        logger.info(f"Updated job {job_id} result")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        with get_db().connect() as conn:
            row = conn.execute(
                "SELECT job_id, job_type, user_id, status, created_at, started_at, completed_at, "
                "progress, total, result_json, error_message, "
                "s3_key, chunk_size, next_chunk_index, extras_s3_key, raw_s3_key "
                "FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "job_id": row[0], "job_type": row[1], "user_id": row[2],
            "status": row[3], "created_at": row[4], "started_at": row[5],
            "completed_at": row[6], "progress": row[7], "total": row[8],
            "result": json.loads(row[9]) if row[9] else None,
            "error_message": row[10],
            "s3_key": row[11], "chunk_size": row[12], "next_chunk_index": row[13],
            "extras_s3_key": row[14], "raw_s3_key": row[15],
        }

    def get_user_jobs(self, user_id: str, job_type: Optional[JobType] = None, limit: int = 10) -> list:
        with get_db().connect() as conn:
            if job_type:
                rows = conn.execute(
                    "SELECT job_id, job_type, status, created_at, progress, total FROM jobs WHERE user_id = ? AND job_type = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, job_type.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT job_id, job_type, status, created_at, progress, total FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
        return [{"job_id": r[0], "job_type": r[1], "status": r[2], "created_at": r[3], "progress": r[4], "total": r[5]} for r in rows]


_job_service = None

def get_job_service() -> JobService:
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service


