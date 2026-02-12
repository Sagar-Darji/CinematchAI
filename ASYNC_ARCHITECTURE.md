# 🚀 Production-Grade Async Architecture for CineMatch AI

## Problem: Timeout with Large Letterboxd Imports

**Issue:** With 783 ratings, the synchronous import takes ~100 seconds (Profile Analyzer alone), exceeding the 120s timeout.

**Root Cause:**
- Synchronous blocking request
- ProfileAnalyzer generates embeddings for ALL ratings sequentially
- No progress feedback
- Client timeout (120s)

## Solution: Multi-Tier Async Architecture

We'll implement 3 tiers of async processing, from simple to enterprise-grade:

1. **FastAPI BackgroundTasks** (Built-in, no infra) ← Start here
2. **Celery + Redis** (Production-grade, scalable)
3. **Apache Kafka** (Enterprise-grade, event streaming)

---

## Solution 1: FastAPI BackgroundTasks ⚡

### Why This First?
- ✅ Built into FastAPI (no new dependencies)
- ✅ No additional infrastructure (Redis, Kafka, etc.)
- ✅ Perfect for MVP and small-to-medium scale
- ✅ Can handle 1000s of requests/day
- ❌ Limited to single-machine (not distributed)
- ❌ No persistence (lost on restart)

### Architecture

```
User uploads CSV → API creates job → Returns job_id (202 Accepted)
                        ↓
                   Background worker starts
                        ↓
    Imports ratings + generates embeddings (async)
                        ↓
    Updates job status (pending → running → completed)
                        ↓
              User polls GET /jobs/{job_id}
                        ↓
           Receives progress updates + result
```

### Implementation Steps

#### Step 1: Job Tracking Service

**File:** `src/services/job_service.py` (ALREADY CREATED ✅)

Features:
- SQLite-based job tracking
- Job states: pending, running, completed, failed
- Progress tracking (0-100%)
- Result storage

#### Step 2: Update Letterboxd Service for Progress Callbacks

**File:** `src/services/letterboxd_service.py`

```python
def import_from_csv(
    self,
    user_id: str,
    csv_content: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,  # NEW
):
    """Import ratings with progress tracking."""

    # Parse CSV
    df = pd.read_csv(StringIO(csv_content))
    rated_df = df[df["Rating"].notna()]

    total = len(rated_df)
    imported = 0
    failed = 0

    for idx, row in rated_df.iterrows():
        try:
            # Import rating
            tmdb_id = self._search_tmdb_movie(row["Name"], row["Year"])
            if tmdb_id:
                self.user_service.add_rating(user_id, str(tmdb_id), ...)
                imported += 1
            else:
                failed += 1

            # Report progress every 10 ratings
            if progress_callback and (imported + failed) % 10 == 0:
                progress_callback(imported + failed, total)

        except Exception as e:
            failed += 1
            logger.warning(f"Failed to import {row['Name']}: {e}")

    # Final progress
    if progress_callback:
        progress_callback(total, total)

    return {
        "total_movies": total,
        "imported_count": imported,
        "failed_count": failed,
        "success_rate": imported / total if total > 0 else 0,
    }
```

#### Step 3: Update API Endpoint

**File:** `src/api/routes/users.py`

```python
from fastapi import BackgroundTasks
from src.services.job_service import JobService, JobType, JobStatus, get_job_service

@router.post(
    "/import/letterboxd",
    status_code=status.HTTP_202_ACCEPTED,  # Changed from 200
)
async def import_letterboxd(
    request: LetterboxdImportRequest,
    background_tasks: BackgroundTasks,  # NEW
):
    """
    Import Letterboxd ratings (ASYNC).

    Returns immediately with job_id.
    Poll GET /users/jobs/{job_id} for status.
    """
    # Parse CSV to get total count
    import pandas as pd
    from io import StringIO

    df = pd.read_csv(StringIO(request.csv_content))
    rated_df = df[df["Rating"].notna()]
    total_movies = len(rated_df)

    # Create job
    job_service = get_job_service()
    job_id = job_service.create_job(
        job_type=JobType.LETTERBOXD_IMPORT,
        user_id=request.user_id,
        total=total_movies,
    )

    # Run import in background
    background_tasks.add_task(
        _import_letterboxd_background,
        job_id=job_id,
        user_id=request.user_id,
        csv_content=request.csv_content,
    )

    # Return immediately
    return {
        "job_id": job_id,
        "user_id": request.user_id,
        "total_movies": total_movies,
        "status": "pending",
        "message": f"Import started. Check status at GET /api/v1/users/jobs/{job_id}",
        "poll_url": f"/api/v1/users/jobs/{job_id}",
    }


def _import_letterboxd_background(job_id: str, user_id: str, csv_content: str):
    """Background task for Letterboxd import."""
    from src.services.letterboxd_service import get_letterboxd_service

    job_service = get_job_service()

    try:
        # Update status to running
        job_service.update_job_status(job_id, JobStatus.RUNNING, progress=0)

        logger.info(f"Starting Letterboxd import for job {job_id}")

        # Run import with progress callback
        service = get_letterboxd_service()

        def progress_callback(current: int, total: int):
            """Progress callback for job tracking."""
            progress = int((current / total) * 100)
            job_service.update_job_status(job_id, JobStatus.RUNNING, progress=progress)

        result = service.import_from_csv(
            user_id=user_id,
            csv_content=csv_content,
            progress_callback=progress_callback,
        )

        # Update result
        job_service.update_job_result(job_id, result)
        job_service.update_job_status(job_id, JobStatus.COMPLETED, progress=100)

        logger.info(f"Completed Letterboxd import for job {job_id}")

    except Exception as e:
        logger.error(f"Failed Letterboxd import for job {job_id}: {e}", exc_info=True)
        job_service.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e),
        )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status by ID."""
    job_service = get_job_service()
    job = job_service.get_job_status(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return job
```

#### Step 4: Update UI to Poll for Status

**File:** `src/ui/components/onboarding.py`

```python
def _import_from_letterboxd(user_id: str, csv_content: str) -> bool:
    """Import ratings from Letterboxd CSV with polling."""
    import time

    with st.spinner("🎬 Starting Letterboxd import..."):
        try:
            # Start import (returns immediately)
            payload = {
                "user_id": user_id,
                "csv_content": csv_content,
            }

            response = requests.post(
                f"{API_BASE_URL}/api/v1/users/import/letterboxd",
                json=payload,
                timeout=10,  # Quick timeout (just to start job)
            )

            if response.status_code == 202:  # Accepted
                data = response.json()
                job_id = data["job_id"]
                total_movies = data["total_movies"]

                # Poll for status
                progress_bar = st.progress(0)
                status_text = st.empty()

                while True:
                    # Check status
                    status_resp = requests.get(
                        f"{API_BASE_URL}/api/v1/users/jobs/{job_id}",
                        timeout=5,
                    )

                    if status_resp.status_code == 200:
                        job_data = status_resp.json()
                        status = job_data["status"]
                        progress = job_data.get("progress", 0)

                        # Update UI
                        progress_bar.progress(progress / 100.0)
                        status_text.text(f"Importing... {progress}% ({progress * total_movies // 100}/{total_movies} movies)")

                        if status == "completed":
                            # Success
                            result = job_data.get("result", {})
                            imported = result.get("imported_count", 0)
                            success_rate = result.get("success_rate", 0) * 100

                            st.success(
                                f"✅ Successfully imported {imported}/{total_movies} ratings ({success_rate:.1f}% success rate)!"
                            )

                            # Save user ID to session
                            st.session_state.user_id = user_id
                            st.session_state.onboarded = True

                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                            return True

                        elif status == "failed":
                            # Failed
                            error_msg = job_data.get("error_message", "Unknown error")
                            st.error(f"❌ Import failed: {error_msg}")
                            return False

                        # Still running, wait and poll again
                        time.sleep(2)
                    else:
                        st.error("Failed to check job status")
                        return False
            else:
                st.error(f"Failed to start import: {response.text}")
                return False

        except Exception as e:
            st.error(f"Error during import: {e}")
            return False
```

### Testing

```bash
# Start API
python -m uvicorn src.api.main:app --reload --port 8000

# Start UI
streamlit run src/ui/app.py

# Upload large CSV (783 ratings)
# Should see:
# 1. Immediate response (202 Accepted)
# 2. Progress bar updating every 2 seconds
# 3. No timeout!
```

**Expected Behavior:**
- API returns in <1 second with job_id
- UI polls every 2 seconds
- Progress bar updates: 0% → 25% → 50% → 75% → 100%
- Total time: ~100 seconds (but no timeout!)

---

## Solution 2: Celery + Redis (Production-Grade) 🏭

### Why Upgrade to Celery?

- ✅ Distributed task queue (multiple workers)
- ✅ Persistent (survives restarts)
- ✅ Retries and error handling
- ✅ Scheduled tasks (cron-like)
- ✅ Rate limiting
- ✅ Monitoring (Flower dashboard)
- ✅ Production-proven (Instagram, Pinterest, Reddit)

### Architecture

```
User → API → Redis (job queue) → Celery Worker 1 → SQLite (results)
                                ↘ Celery Worker 2
                                ↘ Celery Worker 3

User polls API → reads from SQLite → returns status
```

### Setup

#### Step 1: Install Dependencies

```bash
pip install celery redis flower
```

#### Step 2: Create Celery App

**File:** `src/workers/celery_app.py`

```python
from celery import Celery

# Configure Celery
celery_app = Celery(
    "cinematch",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,  # One task at a time
)
```

#### Step 3: Create Celery Tasks

**File:** `src/workers/tasks.py`

```python
from src.workers.celery_app import celery_app
from src.services.letterboxd_service import get_letterboxd_service
from src.services.job_service import get_job_service, JobStatus

@celery_app.task(bind=True)
def import_letterboxd_task(self, job_id: str, user_id: str, csv_content: str):
    """Celery task for Letterboxd import."""
    job_service = get_job_service()

    try:
        # Update status
        job_service.update_job_status(job_id, JobStatus.RUNNING, progress=0)

        # Run import
        service = get_letterboxd_service()

        def progress_callback(current: int, total: int):
            progress = int((current / total) * 100)
            job_service.update_job_status(job_id, JobStatus.RUNNING, progress=progress)
            self.update_state(state='PROGRESS', meta={'current': current, 'total': total})

        result = service.import_from_csv(
            user_id=user_id,
            csv_content=csv_content,
            progress_callback=progress_callback,
        )

        # Update result
        job_service.update_job_result(job_id, result)
        job_service.update_job_status(job_id, JobStatus.COMPLETED, progress=100)

        return result

    except Exception as e:
        job_service.update_job_status(job_id, JobStatus.FAILED, error_message=str(e))
        raise
```

#### Step 4: Update API to Use Celery

**File:** `src/api/routes/users.py`

```python
from src.workers.tasks import import_letterboxd_task

@router.post("/import/letterboxd", status_code=status.HTTP_202_ACCEPTED)
async def import_letterboxd(request: LetterboxdImportRequest):
    """Import Letterboxd ratings (Celery)."""

    # Parse CSV
    df = pd.read_csv(StringIO(request.csv_content))
    total_movies = len(df[df["Rating"].notna()])

    # Create job
    job_service = get_job_service()
    job_id = job_service.create_job(
        job_type=JobType.LETTERBOXD_IMPORT,
        user_id=request.user_id,
        total=total_movies,
    )

    # Submit to Celery
    import_letterboxd_task.delay(
        job_id=job_id,
        user_id=request.user_id,
        csv_content=request.csv_content,
    )

    return {
        "job_id": job_id,
        "user_id": request.user_id,
        "total_movies": total_movies,
        "status": "pending",
        "message": f"Import queued. Check status at GET /api/v1/users/jobs/{job_id}",
    }
```

#### Step 5: Start Infrastructure

```bash
# Start Redis
docker run -d -p 6379:6379 redis:alpine

# Start Celery worker
celery -A src.workers.celery_app worker --loglevel=info

# Start Flower (monitoring dashboard)
celery -A src.workers.celery_app flower --port=5555

# Start API
python -m uvicorn src.api.main:app --reload --port=8000
```

**Monitoring:**
- Flower dashboard: http://localhost:5555
- See tasks in progress, completed, failed
- Monitor worker health

### Benefits of Celery

1. **Distributed:** Run multiple workers on different machines
2. **Persistent:** Tasks survive app restarts
3. **Scalable:** Add workers dynamically based on load
4. **Monitoring:** Flower dashboard shows all tasks
5. **Retries:** Auto-retry failed tasks
6. **Priority:** High-priority tasks first
7. **Scheduled:** Cron-like scheduling for batch jobs

---

## Solution 3: Apache Kafka (Enterprise-Grade) 🏢

### Why Kafka?

- ✅ Event streaming (publish/subscribe)
- ✅ Massive scale (millions of messages/sec)
- ✅ Fault-tolerant (replication)
- ✅ Real-time data pipelines
- ✅ Used by: LinkedIn, Netflix, Uber, Airbnb
- ❌ Complex setup (Zookeeper, brokers, topics)
- ❌ Overkill for most projects

### When to Use Kafka?

- **Event sourcing:** Track all user actions as events
- **Real-time analytics:** Process streaming data
- **Microservices:** Decouple services via events
- **Massive scale:** 1M+ requests/day

### Architecture

```
User → API → Kafka Topic: "letterboxd.imports"
                ↓
    Consumer Group: "import-workers"
         ↓
    Worker 1, Worker 2, Worker 3 (parallel)
         ↓
    Process events → Update database
```

### Quick Setup (Docker)

```bash
# docker-compose.yml
version: '3'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

# Start
docker-compose up -d
```

**Implementation:** Similar to Celery, but replace Redis with Kafka topics.

---

## Comparison Table

| Feature | FastAPI BG Tasks | Celery + Redis | Kafka |
|---------|------------------|----------------|-------|
| **Setup Complexity** | ⭐ Trivial | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐⭐ High |
| **Infrastructure** | None | Redis | Kafka + Zookeeper |
| **Scalability** | Single machine | Multi-machine | Massive scale |
| **Persistence** | None (lost on restart) | Yes (Redis) | Yes (replicated) |
| **Monitoring** | Basic logs | Flower dashboard | Kafka UI + metrics |
| **Cost** | Free | Redis hosting (~$10/mo) | Kafka hosting (~$100/mo) |
| **Use Case** | MVP, small scale | Production | Enterprise, event streaming |
| **Max Throughput** | 100s req/sec | 1000s req/sec | Millions req/sec |

---

## Recommendation for CineMatch AI

### Start with FastAPI BackgroundTasks

**Reasons:**
1. ✅ No infrastructure (works immediately)
2. ✅ Handles 783 ratings without timeout
3. ✅ Good enough for demo/portfolio
4. ✅ Easy to upgrade to Celery later

### Upgrade to Celery when:
- Deploying to production
- Expecting 100+ imports/day
- Need distributed workers
- Need monitoring dashboard

### Use Kafka only if:
- Building event-driven microservices
- Need real-time analytics pipeline
- Massive scale (1M+ users)

---

## Implementation Steps (Quick Win)

1. **Use job_service.py** (already created ✅)
2. **Update letterboxd_service.py** - Add progress_callback parameter
3. **Update users.py API** - Use BackgroundTasks
4. **Update onboarding.py UI** - Poll for job status
5. **Test with 783 ratings** - Should work without timeout!

**Time to implement:** ~1 hour

---

## Production Deployment (Celery)

When ready for production:

```bash
# Install
pip install celery redis flower

# Add to requirements.txt
celery==5.3.4
redis==5.0.1
flower==2.0.1

# Deploy
docker-compose up -d redis
celery -A src.workers.celery_app worker -l info &
celery -A src.workers.celery_app flower --port=5555 &
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

**Monitoring:**
- Flower: http://your-domain:5555
- Redis: Monitor via Redis CLI

---

## Summary

✅ **Immediate fix:** FastAPI BackgroundTasks (no infrastructure)
✅ **Production-grade:** Celery + Redis (scalable, monitored)
✅ **Enterprise:** Kafka (only if needed)

**Start simple, scale when needed!**

<p align="center">
  <strong>🚀 From Timeout to Async Production System!</strong><br>
  <em>Background tasks → Job tracking → Progress updates → Scalable architecture</em>
</p>
