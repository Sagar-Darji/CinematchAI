"""Trace Service - Pipeline trace storage for monitoring and debugging."""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()


class TraceService:
    """SQLite-backed pipeline trace storage."""

    def __init__(self):
        """Initialize trace service."""
        self.db_path = Path(settings.data_dir) / "traces.db"
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for traces."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_traces (
                trace_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                total_duration_ms REAL,
                retrieval_source TEXT,
                candidate_count INTEGER DEFAULT 0,
                final_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running',
                context_json TEXT,
                steps_json TEXT DEFAULT '[]'
            )
        """)

        conn.commit()
        conn.close()

        logger.info(f"Trace database initialized at {self.db_path}")

    def start_trace(self, user_id: str, context: Optional[Dict] = None) -> str:
        """Start a new pipeline trace. Returns trace_id."""
        trace_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO pipeline_traces
                (trace_id, user_id, started_at, status, context_json, steps_json)
            VALUES (?, ?, ?, 'running', ?, '[]')
            """,
            (trace_id, user_id, now, json.dumps(context or {})),
        )

        conn.commit()
        conn.close()

        logger.info(f"Started trace {trace_id} for user {user_id}")
        return trace_id

    def add_step(
        self,
        trace_id: str,
        agent_name: str,
        duration_ms: float,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Add a processing step to a trace."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Get current steps
        cursor.execute(
            "SELECT steps_json FROM pipeline_traces WHERE trace_id = ?",
            (trace_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return

        steps = json.loads(row[0]) if row[0] else []
        steps.append({
            "agent_name": agent_name,
            "duration_ms": round(duration_ms, 1),
            "summary": summary,
            "details": details or {},
        })

        cursor.execute(
            "UPDATE pipeline_traces SET steps_json = ? WHERE trace_id = ?",
            (json.dumps(steps), trace_id),
        )

        conn.commit()
        conn.close()

    def complete_trace(
        self,
        trace_id: str,
        retrieval_source: str = "unknown",
        candidate_count: int = 0,
        final_count: int = 0,
    ):
        """Mark trace as completed."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        # Calculate total duration
        cursor.execute(
            "SELECT started_at FROM pipeline_traces WHERE trace_id = ?",
            (trace_id,),
        )
        row = cursor.fetchone()
        total_duration_ms = 0.0
        if row and row[0]:
            started = datetime.fromisoformat(row[0])
            total_duration_ms = (datetime.utcnow() - started).total_seconds() * 1000

        cursor.execute(
            """
            UPDATE pipeline_traces
            SET status = 'completed',
                completed_at = ?,
                total_duration_ms = ?,
                retrieval_source = ?,
                candidate_count = ?,
                final_count = ?
            WHERE trace_id = ?
            """,
            (now, round(total_duration_ms, 1), retrieval_source, candidate_count, final_count, trace_id),
        )

        conn.commit()
        conn.close()

        logger.info(f"Completed trace {trace_id} in {total_duration_ms:.0f}ms")

    def fail_trace(self, trace_id: str, error: str):
        """Mark trace as failed."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        now = datetime.utcnow().isoformat()

        cursor.execute(
            "SELECT started_at FROM pipeline_traces WHERE trace_id = ?",
            (trace_id,),
        )
        row = cursor.fetchone()
        total_duration_ms = 0.0
        if row and row[0]:
            started = datetime.fromisoformat(row[0])
            total_duration_ms = (datetime.utcnow() - started).total_seconds() * 1000

        # Store error in steps
        cursor.execute(
            "SELECT steps_json FROM pipeline_traces WHERE trace_id = ?",
            (trace_id,),
        )
        row = cursor.fetchone()
        steps = json.loads(row[0]) if row and row[0] else []
        steps.append({
            "agent_name": "error",
            "duration_ms": 0,
            "summary": f"Pipeline failed: {error}",
            "details": {"error": error},
        })

        cursor.execute(
            """
            UPDATE pipeline_traces
            SET status = 'failed',
                completed_at = ?,
                total_duration_ms = ?,
                steps_json = ?
            WHERE trace_id = ?
            """,
            (now, round(total_duration_ms, 1), json.dumps(steps), trace_id),
        )

        conn.commit()
        conn.close()

        logger.info(f"Failed trace {trace_id}: {error}")

    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """Get a single trace by ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM pipeline_traces WHERE trace_id = ?",
            (trace_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_dict(row)

    def get_recent_traces(self, limit: int = 20) -> List[Dict]:
        """Get recent traces."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM pipeline_traces ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(r) for r in rows]

    def get_user_traces(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get traces for a specific user."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM pipeline_traces WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_dict(r) for r in rows]

    def get_stats(self) -> Dict:
        """Get aggregate trace statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM pipeline_traces")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT AVG(total_duration_ms) FROM pipeline_traces WHERE status = 'completed'"
        )
        avg_duration = cursor.fetchone()[0] or 0.0

        cursor.execute(
            "SELECT retrieval_source, COUNT(*) FROM pipeline_traces WHERE retrieval_source IS NOT NULL GROUP BY retrieval_source"
        )
        source_dist = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            "SELECT status, COUNT(*) FROM pipeline_traces GROUP BY status"
        )
        status_dist = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            "total_requests": total,
            "avg_duration_ms": round(avg_duration, 1),
            "source_distribution": source_dist,
            "status_distribution": status_dist,
        }

    def _row_to_dict(self, row) -> Dict:
        """Convert a database row to a dictionary."""
        return {
            "trace_id": row[0],
            "user_id": row[1],
            "started_at": row[2],
            "completed_at": row[3],
            "total_duration_ms": row[4],
            "retrieval_source": row[5],
            "candidate_count": row[6],
            "final_count": row[7],
            "status": row[8],
            "context": json.loads(row[9]) if row[9] else {},
            "steps": json.loads(row[10]) if row[10] else [],
        }


# Singleton instance
_trace_service = None


def get_trace_service() -> TraceService:
    """Get trace service instance."""
    global _trace_service
    if _trace_service is None:
        _trace_service = TraceService()
    return _trace_service
