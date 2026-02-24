"""Job Service - Async job tracking for background tasks."""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from src.core.db import get_db
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
        logger.info("Job database initialized")

    def create_job(self, job_type: JobType, user_id: str, total: int = 100) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with get_db().connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, job_type, user_id, status, created_at, total) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, job_type.value, user_id, JobStatus.PENDING.value, now, total),
            )
        logger.info(f"Created job {job_id}: type={job_type}, user={user_id}")
        return job_id

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
                "SELECT job_id, job_type, user_id, status, created_at, started_at, completed_at, progress, total, result_json, error_message FROM jobs WHERE job_id = ?",
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


