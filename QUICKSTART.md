# Quick Start Guide

Get CineMatch AI running — the app, the API, the bulk enrichment pipeline, and the admin console.

---

## Prerequisites

- **Python 3.10+** with venv activated
- **Ollama** running locally (`ollama pull llama3.1:8b`)
- **TMDB API key** (free at https://www.themoviedb.org/settings/api)
- Cloud vector DB keys in `.env` (Zilliz and/or Qdrant — optional, ChromaDB works locally)

## 1. Environment Setup

```bash
cd /Users/sagardarji/CinematchAI
source venv/bin/activate

# Copy and edit env if not done yet
cp .env.example .env
# Edit .env — set TMDB_API_KEY at minimum
```

Required `.env` keys:
```
TMDB_API_KEY=your_key_here
OLLAMA_MODEL_MAIN=llama3.1:8b
OLLAMA_MODEL_FAST=llama3.1:8b
```

---

## 2. Start the Full App (3 terminals)

### Terminal 1 — Ollama (if not already running)
```bash
ollama serve
```

### Terminal 2 — FastAPI Backend
```bash
cd /Users/sagardarji/CinematchAI
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8000
```
- API Docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Terminal 3 — Streamlit UI
```bash
cd /Users/sagardarji/CinematchAI
source venv/bin/activate
streamlit run src/ui/app.py
```
- UI: http://localhost:8501

### Streamlit Pages
| Page | What it does |
|------|-------------|
| Home | Onboarding, rate movies to build your profile |
| Recommendations | Get AI-powered movie recommendations |
| Group Mode | Group recommendations for multiple users |
| Profile | View your taste profile and stats |
| Browse | Explore the movie catalog |
| Admin | Pipeline management from the browser |

---

## 3. Enrichment Pipeline CLI

Grow the movie corpus from the command line.

### Check current corpus size
```bash
python -m scripts.run_enrichment --stats
```

### Quick enrichment (trending movies, ~30s)
```bash
python -m scripts.run_enrichment --light
```

### Full strategy cycle (~4 min)
```bash
python -m scripts.run_enrichment --full
```

### Bulk Hindi-first enrichment (the big one)

**Test run — 10 pages (~200 movies, ~2 min):**
```bash
python -m scripts.run_enrichment --bulk --max-pages 10
```

**Medium run — 100 pages (~2,000 movies, ~15 min):**
```bash
python -m scripts.run_enrichment --bulk --max-pages 100
```

**Full run — 500 pages (~10,000 movies, ~1 hour):**
```bash
python -m scripts.run_enrichment --bulk --max-pages 500
```

**Overnight run — all 1,002 jobs:**
```bash
python -m scripts.run_enrichment --bulk --max-pages 10000
```

The pipeline is **resumable** — if you kill it mid-run (Ctrl+C), restart with the same command and it picks up where it left off.

### Check bulk job progress
```bash
python -m scripts.run_enrichment --progress
```

Shows per-language breakdown:
```
Language        Priority  Done     Pending   Failed   Movies     Progress
  Hindi         P1        120      305       0        2400       [########------------] 28.2%
  English       P2        0        246       0        0          [--------------------]  0.0%
  Tamil         P3        0        100       0        0          [--------------------]  0.0%
  ...
```

### Overnight rotation (remove unused movies)
```bash
python -m scripts.run_enrichment --rotate --target 15
```

### All CLI flags
```
--bulk                 Start/resume bulk enrichment
--max-pages N          Limit pages this run (default: 500)
--target N             Target corpus size in GB (default: 15)
--progress             Show job queue status
--rotate               Remove unused movies exceeding target size
--stats                Show corpus stats + language distribution
--full                 Full strategy enrichment cycle
--light                Trending-only quick cycle
--user USER_ID         Index a specific user's rated movies
--migrate              Migrate ChromaDB to cloud backends
```

---

## 4. Interactive Admin Console

Full menu-driven interface for managing everything.

```bash
python -m scripts.admin_cli
```

### Menu options:

```
==================================================
     CineMatch AI -- Admin Console
==================================================
  1. Corpus Stats          — movie counts, sizes, backend health, language distribution
  2. Start Bulk Enrichment — interactive: pick max-pages and target, watch live progress
  3. View Job Progress     — per-language table with progress bars
  4. Run Overnight Rotation — remove unused low-priority movies with confirmation
  5. Search Indexed Movies — look up any TMDB ID or source in the index
  6. Clear Job Queue       — clear all/failed/pending jobs
  7. Exit
==================================================
```

---

## 5. Priority Order (What Gets Indexed First)

| Priority | Language | Estimated Jobs | Estimated Movies |
|----------|----------|---------------|-----------------|
| P1 (HIGH) | Hindi | 425 | ~8,000 |
| P2 (MED) | English | 246 | ~4,700 |
| P3 (LOW) | Tamil | 100 | ~2,000 |
| P3 (LOW) | Telugu | 100 | ~2,000 |
| P3 (LOW) | Malayalam | 64 | ~1,200 |
| P3 (LOW) | Kannada | 18 | ~360 |
| P3 (LOW) | Bengali | 18 | ~360 |
| P3 (LOW) | Marathi | 15 | ~300 |
| P3 (LOW) | Gujarati | 8 | ~160 |
| P3 (LOW) | Punjabi | 8 | ~160 |
| **Total** | | **1,002** | **~19,000+** |

---

## 6. Typical Workflow

### First time setup:
```bash
# 1. Start Ollama
ollama serve

# 2. Seed corpus with a quick bulk run
python -m scripts.run_enrichment --bulk --max-pages 50

# 3. Check stats
python -m scripts.run_enrichment --stats

# 4. Start the app
uvicorn src.api.main:app --reload --port 8000 &
streamlit run src/ui/app.py
```

### Daily operation:
```bash
# Morning: check status
python -m scripts.run_enrichment --progress

# Expand corpus when you have time
python -m scripts.run_enrichment --bulk --max-pages 200

# Nightly: rotate out unused movies if over 15 GB
python -m scripts.run_enrichment --rotate
```

### Using the Admin Console instead:
```bash
python -m scripts.admin_cli
# Option 1 → see stats
# Option 2 → start bulk enrichment with live progress
# Option 3 → check progress anytime
```

---

## 7. Memory & Safety

- **Streaming**: processes 1 TMDB page (20 movies) at a time
- **Rate limiting**: 0.3s between API calls (stays under TMDB's 4 req/s)
- **GC**: `gc.collect()` every 100 jobs to prevent memory buildup
- **Resumable**: SQLite job queue persists across restarts
- **Embedder**: loaded once, reused across all batches
- **Usage tracking**: movies returned in searches get usage_count incremented automatically — rotation only removes movies nobody has seen

---

## Troubleshooting

**"No module named 'src'":**
```bash
# Always run from project root
cd /Users/sagardarji/CinematchAI
source venv/bin/activate
```

**TMDB 429 (rate limited):**
The pipeline already sleeps 0.3s between calls. If you still hit limits, reduce `--max-pages` or wait a few minutes.

**"No more pending jobs in queue":**
All jobs are complete. To re-run with fresh jobs:
```bash
python -m scripts.admin_cli
# Option 6 → Clear ALL jobs
# Option 2 → Start fresh
```

**Kill a stuck bulk run:**
Just Ctrl+C. Next `--bulk` picks up from the last completed job.
