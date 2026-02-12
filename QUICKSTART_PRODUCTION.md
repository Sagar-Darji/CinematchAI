# 🚀 Quick Start: From MVP to Production

## For Someone New to Full Stack (You!)

Think of building a production system like building a house:
- **MVP (Current):** You have a tent 🏕️ (works, but basic)
- **Production:** You want a house 🏠 (scalable, reliable)
- **Netflix-Level:** You want a skyscraper 🏢 (handles millions)

---

## 📋 Phase 1: Docker (Start Here - Week 1)

### What is Docker? (Simple Explanation)
**Docker = Shipping Container for Code**

Imagine you have a recipe that works on your laptop, but fails on your friend's computer (different Python version, missing libraries, etc.). Docker solves this by packaging EVERYTHING your code needs into a "container" that runs anywhere.

### Step 1: Install Docker
```bash
# Mac
brew install docker

# Or download from: https://www.docker.com/products/docker-desktop
```

### Step 2: Create Dockerfile for Your API

Create `Dockerfile` in your project root:
```dockerfile
# Start with Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY . .

# Expose port 8000
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 3: Build and Run

```bash
# Build Docker image
docker build -t cinematch-api .

# Run container
docker run -p 8000:8000 cinematch-api

# Visit http://localhost:8000 - it works! 🎉
```

**What just happened?**
1. Docker packaged your code + Python + all libraries
2. Created a "container" (mini virtual machine)
3. Your API now runs in isolation (clean environment)

---

## 📋 Phase 2: Docker Compose (Week 2)

### What is Docker Compose?
**Docker Compose = Run Multiple Containers Together**

Your app needs: API + Database + Redis + ChromaDB
Docker Compose starts all of them with ONE command!

### Step 1: Create docker-compose.yml

Create `docker-compose.yml` in your project root:
```yaml
version: '3.8'

services:
  # Your API
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://cinematch:password@postgres:5432/cinematch
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  # PostgreSQL Database
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

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # Streamlit UI
  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    ports:
      - "8501:8501"
    depends_on:
      - api

volumes:
  postgres_data:
```

### Step 2: Run Everything

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop everything
docker-compose down
```

**What just happened?**
- Started 4 containers (API, DB, Redis, UI)
- They can talk to each other by name (e.g., `postgres:5432`)
- All data persists in volumes
- ONE command to start/stop everything!

---

## 📋 Phase 3: PostgreSQL Migration (Week 3)

### Why Change from SQLite?

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| **Concurrent writes** | 1 user | 1000s of users ✅ |
| **Size limit** | ~1GB | Unlimited ✅ |
| **Replication** | ❌ | ✅ Multi-region |
| **Performance** | Good | Excellent ✅ |

### Step 1: Update Database Config

```python
# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Before: SQLite
    # database_url: str = "sqlite:///data/cinematch.db"

    # After: PostgreSQL
    database_url: str = "postgresql://cinematch:password@postgres:5432/cinematch"

    class Config:
        env_file = ".env"
```

### Step 2: Create Migration Script

```python
# scripts/migrate_sqlite_to_postgres.py
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch

def migrate():
    # Connect to SQLite
    sqlite_conn = sqlite3.connect('data/cinematch.db')
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        "postgresql://cinematch:password@localhost:5432/cinematch"
    )
    pg_cursor = pg_conn.cursor()

    # Migrate users table
    sqlite_cursor.execute("SELECT * FROM users")
    users = sqlite_cursor.fetchall()

    execute_batch(
        pg_cursor,
        "INSERT INTO users (user_id, username, created_at) VALUES (%s, %s, %s)",
        users
    )

    # Migrate ratings table
    sqlite_cursor.execute("SELECT * FROM ratings")
    ratings = sqlite_cursor.fetchall()

    execute_batch(
        pg_cursor,
        "INSERT INTO ratings (user_id, movie_id, rating, created_at) VALUES (%s, %s, %s, %s)",
        ratings
    )

    pg_conn.commit()
    print(f"✅ Migrated {len(users)} users and {len(ratings)} ratings")

if __name__ == "__main__":
    migrate()
```

### Step 3: Run Migration

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Wait 10 seconds for it to start
sleep 10

# Run migration
python scripts/migrate_sqlite_to_postgres.py

# Output: ✅ Migrated 5 users and 783 ratings
```

---

## 📋 Phase 4: Add Redis Caching (Week 4)

### Why Cache?

**Without Cache:**
- User requests recommendations
- Generate profile (30s) + RAG (5s) + LLM (10s) = 45 seconds
- User requests again 5 minutes later
- Generate AGAIN = another 45 seconds ❌

**With Cache:**
- User requests recommendations
- Generate once = 45 seconds
- Cache for 15 minutes
- User requests again
- Return from cache = 10ms ✅ (4500x faster!)

### Step 1: Install Redis Client

```bash
pip install redis
```

### Step 2: Add Caching to Recommendations

```python
# src/api/routes/recommendations.py
import redis
import hashlib
import json

# Connect to Redis
redis_client = redis.Redis(
    host='localhost',  # or 'redis' in Docker
    port=6379,
    decode_responses=True
)

@router.post("/recommendations")
async def get_recommendations(request: RecommendationRequest):
    # Generate cache key
    context_str = json.dumps(request.context, sort_keys=True)
    cache_key = f"recs:{request.user_id}:{hashlib.md5(context_str.encode()).hexdigest()}:{request.k}"

    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        logger.info(f"✅ Cache hit for {request.user_id}")
        return json.loads(cached)

    # Cache miss - generate recommendations
    logger.info(f"❌ Cache miss for {request.user_id} - generating...")
    recommendations = await _generate_recommendations(request)

    # Cache for 15 minutes (900 seconds)
    redis_client.setex(
        cache_key,
        900,
        json.dumps(recommendations)
    )

    return recommendations
```

### Step 3: Test Cache

```bash
# First request (cache miss)
curl -X POST http://localhost:8000/api/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "k": 10}'
# Response time: 45 seconds

# Second request (cache hit!)
curl -X POST http://localhost:8000/api/v1/recommendations \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "k": 10}'
# Response time: 10ms ✅ (4500x faster!)
```

**What just happened?**
- First request: Generate recommendations (slow)
- Store result in Redis with 15-minute expiration
- Second request: Return from Redis (instant!)
- After 15 minutes: Cache expires, generate fresh results

---

## 📋 Phase 5: Deploy to Cloud (Week 5-6)

### Option A: Simple Deployment (AWS EC2)

**What is EC2?** Virtual computer in the cloud (like renting a laptop on Amazon)

### Step 1: Launch EC2 Instance

```bash
# 1. Go to AWS Console → EC2 → Launch Instance
# 2. Choose:
#    - AMI: Ubuntu 22.04
#    - Instance type: t3.large (2 vCPU, 8GB RAM)
#    - Storage: 50GB
# 3. Create and save SSH key (cinematch-key.pem)
# 4. Launch!

# 5. Connect to your instance
chmod 400 cinematch-key.pem
ssh -i cinematch-key.pem ubuntu@<your-ec2-ip>
```

### Step 2: Install Docker on EC2

```bash
# On EC2 instance
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

# Logout and login again
exit
ssh -i cinematch-key.pem ubuntu@<your-ec2-ip>
```

### Step 3: Deploy Your App

```bash
# On EC2 instance

# Clone your repo
git clone https://github.com/yourusername/cinematch-ai.git
cd cinematch-ai

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://cinematch:password@postgres:5432/cinematch
REDIS_URL=redis://redis:6379
TMDB_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
EOF

# Start everything
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Step 4: Access Your App

```
# Your app is now live!
http://<your-ec2-ip>:8501  # Streamlit UI
http://<your-ec2-ip>:8000  # FastAPI

# Share with friends!
```

**Cost:** ~$50/month for t3.large instance

---

## 📋 Phase 6: Add Domain Name (Week 7)

### Step 1: Buy Domain (Optional)

```
# Go to Namecheap/GoDaddy
# Buy: cinematch.ai ($12/year)
```

### Step 2: Point Domain to EC2

```bash
# In your domain provider (Namecheap):
# Add A Record:
# Type: A
# Host: @
# Value: <your-ec2-ip>
# TTL: 300

# Add CNAME for www:
# Type: CNAME
# Host: www
# Value: cinematch.ai
# TTL: 300

# Wait 10-30 minutes for DNS propagation
```

### Step 3: Add HTTPS (Let's Encrypt - FREE)

```bash
# On EC2 instance
sudo apt install -y certbot nginx

# Get SSL certificate (FREE from Let's Encrypt)
sudo certbot --nginx -d cinematch.ai -d www.cinematch.ai

# Certbot automatically configures Nginx
# Your site is now HTTPS! 🔒
```

**Now your app is live at:** https://cinematch.ai ✅

---

## 📋 Common Issues & Solutions

### Issue 1: Docker Build Fails

```bash
# Error: "Cannot connect to Docker daemon"
# Solution: Start Docker Desktop

# Error: "Port 8000 already in use"
# Solution: Kill process using port
lsof -ti:8000 | xargs kill -9

# Error: "No space left on device"
# Solution: Clean up Docker
docker system prune -a
```

### Issue 2: Database Connection Failed

```bash
# Error: "could not connect to server"
# Solution: Check if PostgreSQL is running
docker-compose ps postgres

# If not running, start it
docker-compose up -d postgres

# Check logs
docker-compose logs postgres
```

### Issue 3: Out of Memory

```bash
# Error: "Killed (OOM)"
# Solution: Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory: 8GB

# Or use smaller batch sizes
# In your code, reduce batch_size from 32 to 8
```

---

## 📊 Monitoring Setup (Week 8)

### Simple Monitoring with Uptime Robot (FREE)

1. Go to https://uptimerobot.com (free account)
2. Add Monitor:
   - Type: HTTP(s)
   - URL: https://cinematch.ai/health
   - Interval: 5 minutes
3. Add Alert Contacts (your email)
4. When site goes down, you get email instantly!

### Add Health Endpoint

```python
# src/api/main.py
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database
        db.execute("SELECT 1")

        # Check Redis
        redis_client.ping()

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "cache": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 500
```

---

## 🎯 Your Roadmap (Next 3 Months)

### ✅ Week 1-2: Docker
- [ ] Install Docker Desktop
- [ ] Create Dockerfile
- [ ] Build and run API container
- [ ] Create docker-compose.yml
- [ ] Test locally

### ✅ Week 3: PostgreSQL
- [ ] Add PostgreSQL to docker-compose
- [ ] Migrate data from SQLite
- [ ] Test with 783 ratings
- [ ] Add indexes for performance

### ✅ Week 4: Redis Caching
- [ ] Add Redis to docker-compose
- [ ] Implement caching in API
- [ ] Test cache hit ratio
- [ ] Measure performance improvement

### ✅ Week 5-6: Cloud Deployment
- [ ] Create AWS account (free tier)
- [ ] Launch EC2 instance
- [ ] Deploy with Docker Compose
- [ ] Test from external network

### ✅ Week 7: Domain + HTTPS
- [ ] Buy domain (optional)
- [ ] Configure DNS
- [ ] Set up Let's Encrypt SSL
- [ ] Test HTTPS

### ✅ Week 8: Monitoring
- [ ] Set up Uptime Robot
- [ ] Add health check endpoint
- [ ] Configure email alerts
- [ ] Test alert system

### 🚀 Week 9-12: Advanced (Optional)
- [ ] Kubernetes (if handling 10K+ users)
- [ ] CI/CD pipeline (automated deployment)
- [ ] Load testing (find bottlenecks)
- [ ] Performance optimization

---

## 💡 Key Concepts Explained

### 1. Container vs VM

**Virtual Machine (Old Way):**
```
┌─────────────────────┐
│  Your App           │
│  ↓                  │
│  Guest OS (Ubuntu)  │  ← Heavy (GBs)
│  ↓                  │
│  Hypervisor         │
│  ↓                  │
│  Host OS            │
│  ↓                  │
│  Physical Hardware  │
└─────────────────────┘
```

**Container (New Way):**
```
┌─────────────────────┐
│  Your App           │  ← Light (MBs)
│  ↓                  │
│  Container Runtime  │
│  ↓                  │
│  Host OS            │
│  ↓                  │
│  Physical Hardware  │
└─────────────────────┘
```

**Benefits:**
- Containers are 10x lighter (MBs vs GBs)
- Start in seconds (vs minutes for VMs)
- Use less resources

---

### 2. How Docker Networking Works

```
┌────────────────────────────────────────┐
│  Docker Network (bridge)               │
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │   API    │→ │ Postgres │           │
│  │  :8000   │  │  :5432   │           │
│  └──────────┘  └──────────┘           │
│       ↓                                │
│  ┌──────────┐                          │
│  │  Redis   │                          │
│  │  :6379   │                          │
│  └──────────┘                          │
└────────────────────────────────────────┘
       ↕
   Port Mapping
       ↕
┌────────────────────────────────────────┐
│  Your Laptop                           │
│  localhost:8000 → API container        │
│  localhost:5432 → Postgres container   │
└────────────────────────────────────────┘
```

**How it works:**
1. Containers talk to each other by name (e.g., `postgres:5432`)
2. You access from outside via port mapping (localhost:5432)
3. Containers are isolated (secure)

---

### 3. Database Connections Explained

**Connection Pooling (Important!)**

**Bad (One connection per request):**
```python
# DON'T DO THIS
@app.get("/recommendations")
async def get_recs():
    db = connect_to_database()  # New connection (slow!)
    results = db.query("SELECT...")
    db.close()
    return results
```

**Good (Connection Pool):**
```python
# DO THIS
from sqlalchemy.pool import QueuePool

# Create pool (once at startup)
engine = create_engine(
    "postgresql://...",
    poolclass=QueuePool,
    pool_size=20,        # Keep 20 connections ready
    max_overflow=40,     # Create up to 40 more if needed
)

@app.get("/recommendations")
async def get_recs():
    # Reuse connection from pool (fast!)
    with engine.connect() as conn:
        results = conn.execute("SELECT...")
    return results
```

**Why this matters:**
- Opening connection = 100ms
- Using pooled connection = 1ms
- 100x faster!

---

## 🎓 Learning Resources (FREE)

### Docker
- **Tutorial:** https://www.docker.com/101-tutorial
- **YouTube:** "Docker Tutorial for Beginners" by TechWorld with Nana
- **Time:** 2-3 days

### PostgreSQL
- **Tutorial:** https://www.postgresqltutorial.com/
- **YouTube:** "PostgreSQL Tutorial" by Amigoscode
- **Time:** 1 week

### Redis
- **Tutorial:** https://redis.io/docs/getting-started/
- **YouTube:** "Redis Crash Course" by Web Dev Simplified
- **Time:** 2 days

### AWS Basics
- **Tutorial:** https://aws.amazon.com/getting-started/
- **YouTube:** "AWS Tutorial for Beginners" by freeCodeCamp
- **Time:** 1 week

### Nginx
- **Tutorial:** https://nginx.org/en/docs/beginners_guide.html
- **YouTube:** "Nginx Tutorial" by TechWorld with Nana
- **Time:** 1 day

---

## 🚨 Common Mistakes to Avoid

### 1. ❌ Hardcoding Secrets
```python
# BAD
DATABASE_URL = "postgresql://admin:password123@..."

# GOOD
DATABASE_URL = os.getenv("DATABASE_URL")
```

### 2. ❌ No Error Handling
```python
# BAD
@app.get("/recommendations")
async def get_recs():
    return generate_recommendations()  # What if it fails?

# GOOD
@app.get("/recommendations")
async def get_recs():
    try:
        return generate_recommendations()
    except Exception as e:
        logger.error(f"Failed to generate: {e}")
        return {"error": "Internal server error"}, 500
```

### 3. ❌ Not Using Connection Pooling
```python
# BAD
db = sqlite3.connect("data/cinematch.db")  # One connection for all

# GOOD
engine = create_engine("postgresql://...", pool_size=20)
```

### 4. ❌ No Logging
```python
# BAD
def process_ratings(user_id):
    # Silent failure, no way to debug

# GOOD
import logging
logger = logging.getLogger(__name__)

def process_ratings(user_id):
    logger.info(f"Processing ratings for {user_id}")
    try:
        # Process
        logger.info(f"✅ Processed {count} ratings")
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
```

---

## 📞 Next Steps

Pick your starting point:

**1. Start Simple (Recommended)**
```bash
# This week: Docker + Docker Compose
# Next week: PostgreSQL + Redis
# Week 3: Deploy to AWS EC2
# Week 4: Add domain + HTTPS
```

**2. Jump to Kubernetes**
(Only if you need to handle 10K+ users NOW)
- Read: PRODUCTION_ARCHITECTURE.md
- Focus on Kubernetes section
- Time: 3-4 weeks

**3. Learn by Watching**
YouTube playlist:
- "Docker Tutorial for Beginners" (1 hour)
- "PostgreSQL Tutorial" (2 hours)
- "Deploy to AWS" (1 hour)
- Total: 4 hours → You're 80% there!

---

## 💬 Questions?

Common questions from beginners:

**Q: Do I need to learn all of this?**
A: Start with Docker + PostgreSQL. Learn the rest as you grow.

**Q: How much will cloud hosting cost?**
A: $50-100/month for 1K users, $500-1000/month for 10K users

**Q: When should I use Kubernetes?**
A: When you have 10K+ concurrent users and $1000+/month budget

**Q: Can I use free hosting?**
A: Yes! Fly.io, Railway, Render have free tiers (but limited)

**Q: What's the #1 thing I should do now?**
A: **Dockerize your app** (everything else builds on this)

---

## 🎯 Success Checklist

After completing this guide, you'll have:

✅ Dockerized application (runs anywhere)
✅ PostgreSQL database (production-ready)
✅ Redis caching (10x faster responses)
✅ Deployed to cloud (live URL!)
✅ HTTPS enabled (secure)
✅ Monitoring set up (know when things break)
✅ Understanding of production concepts

**You're now 80% of the way to a production system!** 🎉

The remaining 20% (Kubernetes, advanced monitoring, etc.) is for scale (10K+ users). You can learn that when you get there.

---

Good luck! 🚀
