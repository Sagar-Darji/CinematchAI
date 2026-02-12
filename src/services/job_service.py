"""Job Service - Async job tracking for background tasks."""

import json
import sqlite3
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()


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
    """Service for tracking background jobs."""

    def __init__(self):
        """Initialize job service."""
        self.db_path = Path(settings.data_dir) / "jobs.db"
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for jobs."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Jobs table
        cursor.execute("""
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

        conn.commit()
        conn.close()

        logger.info(f"Job database initialized at {self.db_path}")

    def create_job(
        self,
        job_type: JobType,
        user_id: str,
        total: int = 100,
    ) -> str:
        """
        Create a new job.

        Args:
            job_type: Type of job.
            user_id: User ID.
            total: Total units of work (for progress tracking).

        Returns:
            Job ID (UUID).
        """
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO jobs (job_id, job_type, user_id, status, created_at, total)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (job_id, job_type.value, user_id, JobStatus.PENDING.value, now, total),
        )

        conn.commit()
        conn.close()

        logger.info(f"Created job {job_id}: type={job_type}, user={user_id}")

        return job_id

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """
        Update job status.

        Args:
            job_id: Job ID.
            status: New status.
            progress: Progress (0-100).
            error_message: Error message if failed.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        updates = []
        params = []

        updates.append("status = ?")
        params.append(status.value)

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

        query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"
        cursor.execute(query, params)

        conn.commit()
        conn.close()

        logger.info(f"Updated job {job_id}: status={status}, progress={progress}")

    def update_job_result(self, job_id: str, result: Dict[str, Any]):
        """
        Update job result.

        Args:
            job_id: Job ID.
            result: Result dictionary.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        result_json = json.dumps(result)

        cursor.execute(
            "UPDATE jobs SET result_json = ? WHERE job_id = ?",
            (result_json, job_id),
        )

        conn.commit()
        conn.close()

        logger.info(f"Updated job {job_id} result")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status.

        Args:
            job_id: Job ID.

        Returns:
            Job status dictionary or None if not found.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT job_id, job_type, user_id, status, created_at, started_at,
                   completed_at, progress, total, result_json, error_message
            FROM jobs
            WHERE job_id = ?
        """,
            (job_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        job = {
            "job_id": row[0],
            "job_type": row[1],
            "user_id": row[2],
            "status": row[3],
            "created_at": row[4],
            "started_at": row[5],
            "completed_at": row[6],
            "progress": row[7],
            "total": row[8],
            "result": json.loads(row[9]) if row[9] else None,
            "error_message": row[10],
        }

        return job

    def get_user_jobs(
        self,
        user_id: str,
        job_type: Optional[JobType] = None,
        limit: int = 10,
    ) -> list:
        """
        Get user's jobs.

        Args:
            user_id: User ID.
            job_type: Filter by job type (optional).
            limit: Max number of jobs.

        Returns:
            List of job dictionaries.
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        if job_type:
            cursor.execute(
                """
                SELECT job_id, job_type, status, created_at, progress, total
                FROM jobs
                WHERE user_id = ? AND job_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (user_id, job_type.value, limit),
            )
        else:
            cursor.execute(
                """
                SELECT job_id, job_type, status, created_at, progress, total
                FROM jobs
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (user_id, limit),
            )

        rows = cursor.fetchall()
        conn.close()

        jobs = []
        for row in rows:
            jobs.append({
                "job_id": row[0],
                "job_type": row[1],
                "status": row[2],
                "created_at": row[3],
                "progress": row[4],
                "total": row[5],
            })

        return jobs


# Singleton instance
_job_service = None


def get_job_service() -> JobService:
    """Get job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service
