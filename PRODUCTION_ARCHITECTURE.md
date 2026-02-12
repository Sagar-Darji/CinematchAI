# 🏗️ Production Architecture - Netflix-Level System Design

## Executive Summary

**Current State:** MVP with local deployment (SQLite, local Chroma, single machine)
**Target State:** Production-grade, scalable, cloud-native system

**Think of it like building levels:**
- **Level 1 (Current):** Single house 🏠
- **Level 2 (Next):** Apartment building 🏢
- **Level 3 (Production):** Skyscraper with multiple towers 🌆

---

## 🎯 Current System Analysis

### What You Have Now (MVP)

```
┌─────────────────────────────────────────┐
│         Single Machine (Your Laptop)     │
├─────────────────────────────────────────┤
│  Streamlit UI (Port 8501)                │
│  FastAPI Backend (Port 8000)             │
│  SQLite Database (File: data/users.db)   │
│  ChromaDB (File: data/vectordb/)         │
│  Ollama LLM (Local)                      │
└─────────────────────────────────────────┘
```

### Current Strengths ✅
- **Working AI system** with 6 agents
- **Multi-modal embeddings** (text + image)
- **Async background tasks** (Letterboxd import)
- **Explainable AI** (generates reasoning)
- **Multi-language support**

### Current Limitations ❌
- **Single point of failure** (one machine crashes = everything down)
- **Not scalable** (can't handle 1000+ concurrent users)
- **No redundancy** (no backups if disk fails)
- **Local database** (SQLite can't handle concurrent writes)
- **No monitoring** (can't see errors in production)
- **No CI/CD** (manual deployment)
- **No load balancing** (one server handles all traffic)

---

## 🏛️ Production Architecture Design

### High-Level Architecture (Netflix-Level)

```
┌────────────────────────────────────────────────────────────────┐
│                         USERS (Global)                          │
│                     🌍 1M+ concurrent users                     │
└────────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────┐
│                      CDN (CloudFlare)                           │
│              Cache static assets, DDoS protection               │
└────────────────────┬───────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────────────┐
│                   Load Balancer (AWS ALB)                       │
│            Distributes traffic across servers                   │
└────────┬───────────────────────────────────┬───────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐
│  Web Tier       │                 │  Web Tier       │
│  (Kubernetes)   │                 │  (Kubernetes)   │
│                 │                 │                 │
│  - Frontend Pod │                 │  - Frontend Pod │
│    (React/Next) │                 │    (React/Next) │
│  - Replicas: 10 │                 │  - Replicas: 10 │
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         └───────────────┬───────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                   API Gateway (Kong/AWS API GW)                 │
│   - Rate limiting                                               │
│   - Authentication (JWT)                                        │
│   - API versioning                                              │
└────────┬───────────────────────────────────┬───────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐
│  API Tier       │                 │  API Tier       │
│  (Kubernetes)   │                 │  (Kubernetes)   │
│                 │                 │                 │
│  - FastAPI Pods │                 │  - FastAPI Pods │
│  - Replicas: 20 │                 │  - Replicas: 20 │
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         └───────────────┬───────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Agent Tier  │ │  Agent Tier  │ │  Agent Tier  │
│ (Kubernetes) │ │ (Kubernetes) │ │ (Kubernetes) │
│              │ │              │ │              │
│ - AI Agent   │ │ - AI Agent   │ │ - AI Agent   │
│   Workers    │ │   Workers    │ │   Workers    │
│ - GPU Nodes  │ │ - GPU Nodes  │ │ - GPU Nodes  │
│ - Replicas:  │ │ - Replicas:  │ │ - Replicas:  │
│   50         │ │   50         │ │   50         │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  PostgreSQL  │ │  Redis       │ │  ChromaDB    │
│  (Primary)   │ │  (Cache)     │ │  Cluster     │
│              │ │              │ │              │
│  RDS         │ │  ElastiCache │ │  - 3 nodes   │
│  Multi-AZ    │ │  - Sessions  │ │  - Replicas  │
│  - Replicas  │ │  - Results   │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
         │
         ▼
┌──────────────┐
│  S3 Storage  │
│              │
│  - Embeddings│
│  - Posters   │
│  - Backups   │
└──────────────┘
```

---

## 📊 Component Breakdown (Explained Simply)

### 1. **Frontend (Web Tier)**

**What it is:** The UI that users see (like Netflix's website)

**Current:** Streamlit (great for MVP, not for production scale)
**Production:** React/Next.js (what Netflix uses)

**Why change?**
- Streamlit refreshes entire page (slow)
- React updates only what changed (fast)
- Better mobile support
- More customizable

**Deployment:**
```yaml
# Kubernetes Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cinematch-frontend
spec:
  replicas: 10  # 10 copies running
  selector:
    matchLabels:
      app: cinematch-frontend
  template:
    metadata:
      labels:
        app: cinematch-frontend
    spec:
      containers:
      - name: frontend
        image: cinematch/frontend:v1.0.0
        ports:
        - containerPort: 3000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

**What this means:**
- `replicas: 10` = 10 servers running your frontend
- If one crashes, 9 others keep working
- Load balancer distributes users across all 10

---

### 2. **API Gateway (Entry Point)**

**What it is:** The security guard and traffic cop for your API

**Think of it like:** Airport security + traffic controller

**What it does:**
- **Authentication:** "Is this user logged in?"
- **Rate limiting:** "User X can only make 100 requests/minute"
- **Routing:** "Send recommendation requests to API servers"
- **Monitoring:** "Log all requests for debugging"

**Options:**
- **Kong** (Open source, flexible)
- **AWS API Gateway** (Managed, easy)
- **Nginx** (Lightweight, fast)

**Example Config (Kong):**
```yaml
# Rate limiting
plugins:
  - name: rate-limiting
    config:
      minute: 100
      hour: 1000
      policy: local

# JWT Authentication
  - name: jwt
    config:
      secret_is_base64: false

# CORS
  - name: cors
    config:
      origins:
        - https://cinematch.ai
```

---

### 3. **Database Strategy**

#### Current: SQLite (File-based)
```
❌ Problems:
- Can't handle concurrent writes (only 1 write at a time)
- Stored on one machine (no redundancy)
- No replication
- Limited to ~100K rows efficiently
```

#### Production: PostgreSQL (AWS RDS)
```
✅ Benefits:
- Handles 1000s of concurrent connections
- Multi-AZ (copies in multiple data centers)
- Automatic backups
- Read replicas (scale reads)
- ACID compliance (data integrity)
```

**Database Schema (Production-Ready):**
```sql
-- Users table (optimized for scale)
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    profile_embedding_version INT DEFAULT 1,

    -- Indexes for fast lookups
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
);

-- Ratings table (partitioned by date for performance)
CREATE TABLE ratings (
    rating_id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    movie_id VARCHAR(50) NOT NULL,
    rating DECIMAL(2,1) CHECK (rating >= 0.5 AND rating <= 5.0),
    watched BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Composite index for common queries
    INDEX idx_user_movie (user_id, movie_id),
    INDEX idx_movie (movie_id),
    INDEX idx_created_at (created_at)
) PARTITION BY RANGE (created_at);

-- Partition by month (for billions of ratings)
CREATE TABLE ratings_2024_01 PARTITION OF ratings
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Profile embeddings (cached)
CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) UNIQUE,
    embedding VECTOR(768),  -- pgvector extension
    metadata JSONB,
    version INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    INDEX idx_user_id (user_id),
    INDEX idx_embedding_hnsw ON user_profiles
        USING hnsw (embedding vector_cosine_ops)
);

-- Recommendations cache
CREATE TABLE recommendations_cache (
    cache_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    context_hash VARCHAR(64),
    recommendations JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    INDEX idx_user_context (user_id, context_hash),
    INDEX idx_expires_at (expires_at)
);
```

**Why this is better:**
- `PARTITION BY RANGE` = Split table into chunks (faster queries)
- `VECTOR` type = Store embeddings directly in PostgreSQL
- `JSONB` = Store flexible data efficiently
- Indexes = Fast lookups (like book index)

---

### 4. **Caching Layer (Redis)**

**What it is:** Super-fast temporary storage (like RAM)

**Think of it like:** Your phone's recently opened apps (instant access)

**What to cache:**
- User sessions (who's logged in)
- Recent recommendations (don't recompute)
- Movie metadata (don't fetch from TMDB every time)
- Profile embeddings (don't regenerate every time)

**Cache Strategy:**
```python
# Example: Cache recommendations for 15 minutes
import redis
import json

redis_client = redis.Redis(host='redis-cluster', port=6379)

def get_recommendations(user_id: str, context: dict, k: int):
    # Generate cache key
    context_hash = hashlib.md5(json.dumps(context).encode()).hexdigest()
    cache_key = f"recs:{user_id}:{context_hash}:{k}"

    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss - generate recommendations
    recommendations = _generate_recommendations(user_id, context, k)

    # Cache for 15 minutes
    redis_client.setex(
        cache_key,
        900,  # 15 minutes in seconds
        json.dumps(recommendations)
    )

    return recommendations
```

**Cache Hit Ratio Target:** 80%+
- Means 80% of requests served from cache (instant)
- Only 20% hit the expensive AI agents

---

### 5. **Vector Database (ChromaDB Cluster)**

**Current:** Single ChromaDB instance (file-based)
**Production:** ChromaDB cluster with replication

**Why cluster?**
- **Redundancy:** If one node fails, others continue
- **Load distribution:** Spread queries across nodes
- **Faster queries:** Parallel search across nodes

**Architecture:**
```
┌─────────────────────────────────────────┐
│         ChromaDB Cluster                │
├─────────────────────────────────────────┤
│  Node 1 (Primary)                        │
│  - Movies collection (20M vectors)       │
│  - Users collection (10M vectors)        │
│                                          │
│  Node 2 (Replica)                        │
│  - Read replica for load distribution    │
│                                          │
│  Node 3 (Replica)                        │
│  - Read replica for load distribution    │
└─────────────────────────────────────────┘
```

**Alternative (Netflix uses this):**
- **Pinecone** (Managed, scales to billions)
- **Weaviate** (Open source, production-grade)
- **Milvus** (Distributed, Kubernetes-native)

---

### 6. **Message Queue (Celery + RabbitMQ/SQS)**

**What it is:** Task queue for background jobs

**Think of it like:** Post office (drop off task, pick up later)

**Why needed:**
- Letterboxd import (783 ratings = 100 seconds)
- Profile regeneration (30-40 seconds)
- Batch embedding generation
- Email notifications

**Current:** FastAPI BackgroundTasks (good for MVP)
**Production:** Celery with message broker (scalable)

**Architecture:**
```
┌─────────────┐
│  API Server │
│             │
│  1. User    │
│     uploads │
│     CSV     │
│             │
│  2. Create  │
│     job_id  │
│             │
│  3. Return  │
│     202     │
└──────┬──────┘
       │
       │ Publish task
       ▼
┌──────────────┐
│  RabbitMQ    │
│  (Queue)     │
│              │
│  - Task: id  │
│    csv_data  │
└──────┬───────┘
       │
       │ Consume task
       ▼
┌──────────────┐
│  Celery      │
│  Workers     │
│  (50 nodes)  │
│              │
│  Process in  │
│  parallel    │
└──────┬───────┘
       │
       │ Update status
       ▼
┌──────────────┐
│  Redis       │
│  (Results)   │
└──────────────┘
```

**Celery Configuration:**
```python
# celery_config.py
from celery import Celery

app = Celery(
    'cinematch',
    broker='amqp://rabbitmq:5672',
    backend='redis://redis:6379/0'
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Performance tuning
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,

    # Task routing
    task_routes={
        'cinematch.tasks.import_letterboxd': {'queue': 'import'},
        'cinematch.tasks.generate_embeddings': {'queue': 'embeddings'},
        'cinematch.tasks.recommendations': {'queue': 'recommendations'},
    },
)

# Task example
@app.task(bind=True, max_retries=3)
def import_letterboxd(self, job_id: str, user_id: str, csv_content: str):
    try:
        # Import logic
        service = get_letterboxd_service()
        result = service.import_from_csv(user_id, csv_content)
        return result
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

---

### 7. **Containerization (Docker)**

**What is Docker?** Package your app with everything it needs

**Think of it like:** Shipping container (standardized, runs anywhere)

**Dockerfile (FastAPI):**
```dockerfile
# Multi-stage build (smaller image)
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production image
FROM python:3.11-slim

# Create non-root user (security)
RUN useradd -m -u 1000 cinematch

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /home/cinematch/.local

# Copy application
COPY --chown=cinematch:cinematch . .

# Switch to non-root user
USER cinematch

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Docker Compose (Local Development):**
```yaml
version: '3.8'

services:
  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    depends_on:
      - api

  # API
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://cinematch:password@postgres:5432/cinematch
      - REDIS_URL=redis://redis:6379/0
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8001
    depends_on:
      - postgres
      - redis
      - chromadb
    volumes:
      - ./data:/app/data

  # PostgreSQL
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_USER=cinematch
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=cinematch
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # ChromaDB
  chromadb:
    image: chromadb/chroma:latest
    environment:
      - CHROMA_SERVER_AUTH_CREDENTIALS=cinematch:password
    volumes:
      - chroma_data:/chroma/chroma
    ports:
      - "8001:8000"

  # Celery Worker
  celery_worker:
    build: ./backend
    command: celery -A src.workers.celery_app worker -l info -Q import,embeddings,recommendations
    environment:
      - DATABASE_URL=postgresql://cinematch:password@postgres:5432/cinematch
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=amqp://rabbitmq:5672
    depends_on:
      - postgres
      - redis
      - rabbitmq

  # RabbitMQ
  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=cinematch
      - RABBITMQ_DEFAULT_PASS=password

volumes:
  postgres_data:
  redis_data:
  chroma_data:
```

**Run with one command:**
```bash
docker-compose up -d
```

---

### 8. **Kubernetes (Orchestration)**

**What is Kubernetes (K8s)?** Manages hundreds of containers

**Think of it like:** Air traffic control for containers

**Why Kubernetes?**
- **Auto-scaling:** Add servers when traffic spikes
- **Self-healing:** Restart crashed containers
- **Load balancing:** Distribute traffic
- **Rolling updates:** Update without downtime
- **Resource management:** Optimize CPU/memory usage

**Kubernetes Deployment:**
```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cinematch-api
  namespace: production
spec:
  replicas: 20  # Start with 20 pods
  selector:
    matchLabels:
      app: cinematch-api
  template:
    metadata:
      labels:
        app: cinematch-api
        version: v1.0.0
    spec:
      containers:
      - name: api
        image: cinematch/api:v1.0.0
        ports:
        - containerPort: 8000

        # Environment variables from secrets
        envFrom:
        - secretRef:
            name: cinematch-secrets

        # Resource limits (prevents one pod hogging resources)
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"

        # Health checks
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10

        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5

        # Graceful shutdown
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]

---
# Auto-scaling based on CPU/memory
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cinematch-api-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cinematch-api
  minReplicas: 20
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Scale up if CPU > 70%
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80  # Scale up if memory > 80%

---
# Service (load balancer)
apiVersion: v1
kind: Service
metadata:
  name: cinematch-api-service
  namespace: production
spec:
  selector:
    app: cinematch-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

**What this means:**
- Starts with 20 API servers
- Auto-scales to 100 if traffic increases
- Each server gets 512MB RAM, 0.5 CPU cores
- Health checks every 10 seconds
- Load balancer distributes traffic

---

### 9. **Helm (Package Manager for K8s)**

**What is Helm?** App Store for Kubernetes

**Think of it like:** `npm install` for Kubernetes

**Helm Chart Structure:**
```
cinematch-helm/
├── Chart.yaml              # Metadata
├── values.yaml             # Configuration
├── templates/
│   ├── deployment.yaml     # API deployment
│   ├── service.yaml        # Load balancer
│   ├── ingress.yaml        # External access
│   ├── configmap.yaml      # Config
│   ├── secrets.yaml        # Passwords/keys
│   └── hpa.yaml            # Auto-scaling
└── charts/
    ├── postgresql/         # Database
    ├── redis/              # Cache
    └── rabbitmq/           # Queue
```

**values.yaml (Configuration):**
```yaml
# Application
app:
  name: cinematch
  version: 1.0.0
  environment: production

# API
api:
  replicaCount: 20
  image:
    repository: cinematch/api
    tag: v1.0.0
    pullPolicy: IfNotPresent

  resources:
    requests:
      memory: 512Mi
      cpu: 500m
    limits:
      memory: 1Gi
      cpu: 1000m

  autoscaling:
    enabled: true
    minReplicas: 20
    maxReplicas: 100
    targetCPUUtilizationPercentage: 70

# Database
postgresql:
  enabled: true
  auth:
    username: cinematch
    password: <from-secret>
    database: cinematch
  primary:
    persistence:
      size: 100Gi
  readReplicas:
    replicaCount: 2

# Cache
redis:
  enabled: true
  architecture: replication
  master:
    persistence:
      size: 10Gi
  replica:
    replicaCount: 2
```

**Deploy with one command:**
```bash
helm install cinematch ./cinematch-helm --namespace production
```

---

## 🚀 CI/CD Pipeline (Automated Deployment)

**What is CI/CD?** Automatic testing and deployment

**Think of it like:** Assembly line (code → test → deploy)

**Pipeline Stages:**
```
1. Code Push (GitHub)
   ↓
2. Build (Docker image)
   ↓
3. Test (Unit + Integration)
   ↓
4. Security Scan (Vulnerabilities)
   ↓
5. Deploy to Staging
   ↓
6. Run E2E Tests
   ↓
7. Deploy to Production (Blue-Green)
   ↓
8. Monitor (Alerts if errors)
```

**GitHub Actions Workflow:**
```yaml
# .github/workflows/deploy.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # Job 1: Build and test
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  # Job 2: Build Docker image
  build-docker:
    needs: build-and-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: |
          docker build -t cinematch/api:${{ github.sha }} .

      - name: Push to Docker Hub
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push cinematch/api:${{ github.sha }}

  # Job 3: Deploy to staging
  deploy-staging:
    needs: build-docker
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Kubernetes (Staging)
        run: |
          kubectl set image deployment/cinematch-api \
            api=cinematch/api:${{ github.sha }} \
            --namespace=staging

      - name: Wait for rollout
        run: |
          kubectl rollout status deployment/cinematch-api --namespace=staging

  # Job 4: E2E tests on staging
  e2e-tests:
    needs: deploy-staging
    runs-on: ubuntu-latest
    steps:
      - name: Run E2E tests
        run: |
          npm run test:e2e -- --baseUrl=https://staging.cinematch.ai

  # Job 5: Deploy to production (manual approval)
  deploy-production:
    needs: e2e-tests
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    steps:
      - name: Blue-Green Deployment
        run: |
          # Deploy to green (new version)
          kubectl set image deployment/cinematch-api-green \
            api=cinematch/api:${{ github.sha }} \
            --namespace=production

          # Wait for green to be ready
          kubectl rollout status deployment/cinematch-api-green --namespace=production

          # Switch traffic to green
          kubectl patch service cinematch-api-service \
            -p '{"spec":{"selector":{"version":"green"}}}' \
            --namespace=production

          # Keep blue for quick rollback
          echo "Blue version kept for 1 hour for potential rollback"
```

---

## 📊 Monitoring & Observability

**Why needed?** Know when things break BEFORE users complain

**Stack:**
- **Prometheus** (Metrics)
- **Grafana** (Dashboards)
- **ELK Stack** (Logs)
- **Jaeger** (Tracing)
- **Sentry** (Error tracking)

### Metrics to Track:

**System Metrics:**
- CPU usage per pod
- Memory usage per pod
- Network I/O
- Disk I/O

**Application Metrics:**
- Request rate (requests/second)
- Error rate (errors/second)
- Latency (P50, P95, P99)
- Cache hit ratio

**Business Metrics:**
- Recommendations generated/minute
- User signups/hour
- API usage by endpoint
- Revenue (if paid tier)

**Grafana Dashboard Example:**
```
┌─────────────────────────────────────────────────────┐
│  CineMatch AI - Production Dashboard                │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Request Rate │  │ Error Rate   │  │ Latency  │ │
│  │  5.2K/sec   │  │    0.05%     │  │  120ms   │ │
│  └──────────────┘  └──────────────┘  └──────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │  Request Rate Over Time                     │   │
│  │  ▂▃▅▇█▇▅▃▂▁▂▃▅▇█▇▅▃▂                      │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ API Pods     │  │ Agent Pods   │                │
│  │  23/100      │  │  67/100      │                │
│  │  Healthy: 23 │  │  Healthy: 67 │                │
│  └──────────────┘  └──────────────┘                │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │  Top 5 Slow Endpoints                       │   │
│  │  1. /recommendations (3.2s)                 │   │
│  │  2. /import/letterboxd (2.8s)               │   │
│  │  3. /movies/search (890ms)                  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Alerts (PagerDuty/Slack):**
```yaml
# Prometheus alerts
groups:
- name: cinematch-alerts
  rules:
  # High error rate
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }}% (threshold: 5%)"

  # Slow response times
  - alert: SlowResponseTime
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "95th percentile response time > 2s"

  # Pod crashes
  - alert: PodCrashLooping
    expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Pod {{ $labels.pod }} is crash looping"
```

---

## 💰 Cost Optimization

**Current:** $0 (local laptop)
**Production (AWS):** ~$5,000-$10,000/month for Netflix-level scale

**Cost Breakdown:**
| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| **Kubernetes Cluster (EKS)** | $1,500 | 50 nodes (mix of CPU/GPU) |
| **RDS PostgreSQL (Multi-AZ)** | $800 | db.r6g.2xlarge + replicas |
| **ElastiCache Redis** | $400 | cache.r6g.large cluster |
| **S3 Storage** | $300 | 10TB embeddings + posters |
| **CloudFront CDN** | $500 | 10TB data transfer |
| **Load Balancer (ALB)** | $100 | 2 load balancers |
| **RabbitMQ (Amazon MQ)** | $200 | mq.m5.large |
| **Monitoring (Datadog)** | $600 | APM + Infrastructure |
| **GPU Instances (p3.2xlarge)** | $2,500 | 10 GPU nodes for LLM |
| **CloudWatch Logs** | $200 | Log storage |
| **Backups & Disaster Recovery** | $300 | S3 snapshots |
| **Misc (NAT Gateway, etc.)** | $200 | Networking |
| **Total** | **$7,600/month** | For 100K active users |

**Cost Optimization Strategies:**

1. **Use Spot Instances (Save 70%)**
   - For non-critical workers (Celery)
   - Fall back to on-demand if spot unavailable

2. **Auto-scaling (Save 50%)**
   - Scale down at night (fewer users)
   - Scale up during peak hours

3. **S3 Intelligent Tiering (Save 40%)**
   - Move old posters to Glacier

4. **Reserved Instances (Save 30%)**
   - Commit to 1-year for database/cache

5. **CDN Optimization (Save 60%)**
   - Cache aggressively
   - Use WebP images (smaller)

**After Optimization:** ~$4,000/month

---

## 🔐 Security Best Practices

### 1. **Network Security**
```yaml
# Network policy (isolate pods)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
spec:
  podSelector:
    matchLabels:
      app: cinematch-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: cinematch-frontend
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### 2. **Secrets Management**
```bash
# Use AWS Secrets Manager (not hardcoded)
aws secretsmanager create-secret \
  --name cinematch/production/db-password \
  --secret-string "super-secret-password"

# In Kubernetes, use external-secrets operator
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: cinematch-secrets
spec:
  secretStoreRef:
    name: aws-secrets-manager
  target:
    name: cinematch-secrets
  data:
  - secretKey: database-password
    remoteRef:
      key: cinematch/production/db-password
```

### 3. **Authentication & Authorization**
```python
# JWT-based auth
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"]
        )
        return payload["user_id"]
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/recommendations")
async def get_recommendations(user_id: str = Depends(verify_token)):
    # Only authenticated users can access
    pass
```

### 4. **Rate Limiting**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/recommendations")
@limiter.limit("100/minute")  # Max 100 requests/minute per IP
async def get_recommendations():
    pass
```

---

## 📈 Scalability Roadmap

### Phase 1: MVP → 1K Users (Current)
- **Infrastructure:** Single machine
- **Database:** SQLite
- **Cost:** $0/month

### Phase 2: 1K → 10K Users (Next 3 months)
- **Infrastructure:** Docker Compose on single VM
- **Database:** PostgreSQL (managed)
- **Cache:** Redis
- **Cost:** $200-500/month
- **Focus:** Stability + monitoring

### Phase 3: 10K → 100K Users (6 months)
- **Infrastructure:** Kubernetes (3-5 nodes)
- **Database:** PostgreSQL with read replicas
- **Cache:** Redis cluster
- **Queue:** Celery + RabbitMQ
- **CDN:** CloudFront
- **Cost:** $1,500-3,000/month
- **Focus:** Auto-scaling + optimization

### Phase 4: 100K → 1M Users (1 year)
- **Infrastructure:** Multi-region Kubernetes
- **Database:** Sharded PostgreSQL
- **Cache:** Redis cluster (multi-AZ)
- **Queue:** Amazon SQS + Celery
- **CDN:** CloudFront + edge compute
- **Cost:** $5,000-10,000/month
- **Focus:** Global distribution + performance

### Phase 5: Netflix-Level (1M+ Users)
- **Infrastructure:** Multi-cloud (AWS + GCP)
- **Database:** Distributed (CockroachDB)
- **Cache:** Distributed cache (Aerospike)
- **Queue:** Kafka for event streaming
- **ML Serving:** Dedicated GPU clusters
- **Cost:** $50,000+/month
- **Focus:** 99.99% uptime + <100ms latency

---

## 🎯 Performance Targets

| Metric | Current | Phase 2 | Phase 3 | Phase 4 | Netflix-Level |
|--------|---------|---------|---------|---------|---------------|
| **Concurrent Users** | 1-10 | 1,000 | 10,000 | 100,000 | 1M+ |
| **Recommendations/sec** | 1-2 | 50 | 500 | 5,000 | 50,000 |
| **P95 Latency** | 60s | 5s | 2s | 500ms | 200ms |
| **Uptime** | 95% | 99% | 99.5% | 99.9% | 99.99% |
| **Cache Hit Ratio** | 0% | 50% | 70% | 85% | 95% |

---

## 🚀 Implementation Roadmap

### Week 1-2: Docker + Docker Compose
- Containerize all services
- Set up local development environment
- Add health checks

### Week 3-4: Database Migration
- SQLite → PostgreSQL
- Add indexes
- Implement connection pooling

### Week 5-6: Caching Layer
- Add Redis
- Cache recommendations (15 min TTL)
- Cache user profiles (1 hour TTL)

### Week 7-8: Message Queue
- Add Celery + RabbitMQ
- Move long tasks to background
- Add progress tracking

### Week 9-10: Kubernetes Setup
- Create K8s cluster (EKS/GKE)
- Write deployment manifests
- Set up Helm charts

### Week 11-12: CI/CD Pipeline
- GitHub Actions workflow
- Automated testing
- Blue-green deployments

### Week 13-14: Monitoring
- Prometheus + Grafana
- ELK stack for logs
- Sentry for errors

### Week 15-16: Load Testing
- Simulate 10K concurrent users
- Identify bottlenecks
- Optimize

---

## 📚 Learning Resources

### 1. **Docker**
- Tutorial: https://docs.docker.com/get-started/
- Practice: Build Dockerfile for your API
- Time: 1 week

### 2. **Kubernetes**
- Tutorial: https://kubernetes.io/docs/tutorials/
- Course: "Kubernetes for Beginners" (Udemy)
- Time: 2 weeks

### 3. **PostgreSQL**
- Tutorial: https://www.postgresql.org/docs/current/tutorial.html
- Book: "PostgreSQL: Up and Running"
- Time: 1 week

### 4. **Redis**
- Tutorial: https://redis.io/docs/getting-started/
- Course: "Redis University"
- Time: 3 days

### 5. **CI/CD**
- Tutorial: https://docs.github.com/en/actions
- Practice: Set up automated tests
- Time: 1 week

---

## 🎓 Key Takeaways

### What You Have (MVP)
✅ Working AI system with 6 agents
✅ Multi-modal recommendations
✅ Explainable AI
✅ Async background tasks

### What You Need (Production)
📦 **Containerization** (Docker)
☸️ **Orchestration** (Kubernetes)
🗄️ **Production Database** (PostgreSQL)
⚡ **Caching** (Redis)
📬 **Message Queue** (Celery + RabbitMQ)
📊 **Monitoring** (Prometheus + Grafana)
🚀 **CI/CD** (GitHub Actions)
🔐 **Security** (JWT, rate limiting, secrets)

### Priority Order (Start Here)
1. **Docker** (Package everything)
2. **PostgreSQL** (Replace SQLite)
3. **Redis** (Add caching)
4. **Kubernetes** (Orchestrate containers)
5. **Monitoring** (Know when things break)

---

## 💡 Next Steps

Ready to start? Pick one:

**Option 1: Quick Win (1 week)**
→ Dockerize your application
→ Set up Docker Compose with PostgreSQL + Redis
→ Deploy to single AWS EC2 instance

**Option 2: Production-Ready (3 months)**
→ Full Kubernetes setup
→ CI/CD pipeline
→ Monitoring + alerting
→ Handle 10K users

**Option 3: Netflix-Level (6+ months)**
→ Multi-region deployment
→ Auto-scaling + load balancing
→ Advanced monitoring
→ Handle 1M+ users

Which path interests you? I can provide detailed implementation guides for any phase! 🚀
