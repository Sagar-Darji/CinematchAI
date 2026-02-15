# CineMatch AI — Quick Start Guide

Everything you need to run the full stack: Streamlit app, React app, FastAPI backend, enrichment pipeline, and the interactive admin console.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | `python --version` |
| Node.js 18+ | `node --version` — needed for React frontend |
| TMDB API key | Free at https://www.themoviedb.org/settings/api |
| Groq API key (recommended) | Free at https://console.groq.com — 25× faster than local |
| Ollama (optional local fallback) | `ollama pull llama3.1:8b` |

---

## 1. Environment Setup

```bash
cd /path/to/CinematchAI
source venv/bin/activate

cp .env.example .env
# Edit .env — set at minimum:
#   TMDB_API_KEY=your_key
#   GROQ_API_KEY=your_key   ← recommended (free tier)
```

Key `.env` settings:
```env
# Primary LLM (Groq is fast + free)
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL_MAIN=llama-3.1-70b-versatile
GROQ_MODEL_FAST=llama-3.1-8b-instant

# TMDB for movie metadata
TMDB_API_KEY=your_tmdb_key_here

# Optional: Zilliz or Qdrant cloud vector DB
ZILLIZ_URI=https://xxx.zillizcloud.com
ZILLIZ_TOKEN=your_token

# Optional: multimodal poster embeddings (requires ~600 MB CLIP download)
USE_MULTIMODAL_EMBEDDINGS=false
```

---

## 2. Start the Backend (FastAPI)

The API must be running for both UIs to work.

```bash
# Terminal 1
cd /path/to/CinematchAI
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## 3. Option A — Streamlit UI (classic, zero build step)

```bash
# Terminal 2
cd /path/to/CinematchAI
source venv/bin/activate
streamlit run src/ui/app.py
```

Open: http://localhost:8501

### Streamlit pages

| Page | What it does |
|------|-------------|
| 🏠 Home | Onboarding — rate movies to build your profile |
| 🎬 Recommendations | AI-powered picks with live agent trace + movie reveal cascade |
| 👥 Group Mode | Recommendations for multiple users at once |
| 📊 Profile | Taste profile, genre breakdown, rating history |
| 🌍 Browse | Poster grid — search by title, genre, language |

> Admin functionality has been moved to the interactive CLI (see section 5).

---

## 4. Option B — React Frontend (cinema dark theme, recommended)

Built with React 19 + Vite + TypeScript + Tailwind CSS + Zustand.

### Install & run (first time)

```bash
# Terminal 2
cd /path/to/CinematchAI/frontend
npm install
npm run dev
```

Open: http://localhost:3000

### Subsequent runs

```bash
cd /path/to/CinematchAI/frontend
npm run dev
```

### React pages

| Route | Design inspiration | What it does |
|-------|-------------------|-------------|
| `/` | — | Home: username entry, feature overview |
| `/recommendations` | unveil.fr | Live agent trace panel, cascading movie reveal, full card with VidSrc embed |
| `/browse` | nothing-to-watch | Dense poster grid, genre filter chips, inline expanded card |
| `/profile` | — | Rating count, top genre bar chart, embedding status |

### Build for production

```bash
cd /path/to/CinematchAI/frontend
npm run build
# Output: frontend/dist/  — serve with any static host
```

---

## 5. Interactive Admin Console (CLI)

Fully menu-driven — just press a number, no commands to type.

```bash
cd /path/to/CinematchAI
source venv/bin/activate
python scripts/cinematch_cli.py
```

```
┌─────────────────────────────────────────────────────────────┐
│         🎬  CineMatch AI  v2.0.0                            │
│  Interactive Admin Console — press a number, no commands    │
└─────────────────────────────────────────────────────────────┘

 [1]  📊  Corpus Stats           counts, language distribution, backend health
 [2]  🌍  Bulk Enrichment        interactive language + page config, then runs
 [3]  📈  Job Progress           live view of pending / done / failed jobs
 [4]  🔄  Overnight Rotation     prune stale movies, refresh corpus
 [5]  🔍  Search Index           look up any movie by title or TMDB ID
 [6]  🗑️   Clear Job Queue        choose pending, failed, or all
 [7]  🧪  Test Recommendation    run full AI pipeline for any user_id
 [8]  🔌  LLM Health Check       test Groq + Ollama latency
 [0]  🚪  Exit
```

**Bulk enrichment** (option 2) shows an interactive language picker — enter `0` for all languages, or space-separated numbers like `1 3` for specific ones.

---

## 6. Enrichment Pipeline (grow the corpus)

The pipeline fetches movies from TMDB, embeds them, and stores them in the vector database.

### Interactive way (recommended)

```bash
python scripts/cinematch_cli.py
# → option 2 (Bulk Enrichment)
# → pick languages, pages, target size
# → confirm → watch live progress bar
```

### Script way (for automation / cron jobs)

```bash
# Check current corpus size
python -m scripts.run_enrichment --stats

# Quick seed (~200 movies, ~2 min)
python -m scripts.run_enrichment --bulk --max-pages 10

# Medium run (~2,000 movies, ~15 min)
python -m scripts.run_enrichment --bulk --max-pages 100

# Hindi only (100 pages)
python -m scripts.run_enrichment --bulk --language hi --max-pages 100

# English + Tamil (50 pages each)
python -m scripts.run_enrichment --bulk --language en ta --max-pages 50

# Full overnight (~10,000 movies, ~1 hour)
python -m scripts.run_enrichment --bulk --max-pages 500

# Check progress
python -m scripts.run_enrichment --progress

# Rotate out stale movies (keep ≤ 15 GB)
python -m scripts.run_enrichment --rotate --target 15
```

The pipeline is **resumable** — Ctrl+C and restart with the same command; it picks up from the last completed job.

---

## 7. Language Priority (what gets indexed first)

| Priority | Language | Estimated Movies |
|----------|----------|-----------------|
| P1 HIGH | Hindi | ~8,000 |
| P2 MED | English | ~4,700 |
| P3 | Tamil, Telugu, Malayalam | ~5,200 combined |
| P3 | Korean, Japanese, French… | ~3,000 combined |
| **Total** | 10+ languages | **~19,000+** |

---

## 8. Typical Workflows

### First time (5 minutes to running)

```bash
# 1. Set up env
cp .env.example .env && nano .env  # add TMDB + Groq keys

# 2. Start API
uvicorn src.api.main:app --reload --port 8000 &

# 3. Seed corpus (2 min)
python -m scripts.run_enrichment --bulk --max-pages 10

# 4. Start UI — pick one:
streamlit run src/ui/app.py        # Streamlit on :8501
# OR
cd frontend && npm run dev          # React on :3000
```

### Daily operation

```bash
# Morning — check status (via CLI, option 3)
python scripts/cinematch_cli.py

# Expand corpus when idle (via CLI, option 2)
# → pick languages → enter 200 pages → confirm

# Nightly — rotate if over 15 GB (via CLI, option 4)
```

---

## 9. Troubleshooting

**"No module named 'src'"**
```bash
# Always run from the project root with venv active
cd /path/to/CinematchAI
source venv/bin/activate
```

**React app shows "Failed to fetch" for recommendations**
- Make sure the FastAPI server is running on port 8000
- The React dev server proxies `/api` → `localhost:8000` automatically

**TMDB 429 (rate limited)**
- The pipeline sleeps 0.3s between calls (≤4 req/s). If still hitting limits, reduce `--max-pages` or wait 30s.

**"No more pending jobs in queue"**
All jobs are done. To start a fresh run, use CLI option 6 → Clear ALL jobs, then option 2 → Bulk Enrichment.

**Groq errors (401 / no key)**
Set `GROQ_API_KEY` in `.env`. Free tier gives ~500 requests/day. Falls back to Ollama if unavailable.

**Slow recommendations (>30s)**
Switch to Groq: set `LLM_PROVIDER=groq` in `.env`. Groq runs the 70B model at 750 tok/s vs ~30 tok/s locally.

**VidSrc player not loading**
- Availability varies by region and title
- Ensure your browser allows iframes from `vidsrc.to`
- The `sandbox` attribute blocks ad redirects but not all players work everywhere
