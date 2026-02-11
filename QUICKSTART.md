# 🚀 Quick Start Guide

Get CineMatch AI up and running in minutes!

## Prerequisites

- **macOS** with M4 Pro (or any Mac with 16GB+ RAM)
- **Python 3.10+**
- **15GB free disk space** (for models and data)

## Step 1: Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the fast model (4.7GB)
ollama pull llama3.1:8b

# Verify it's working
ollama run llama3.1:8b "Hello! This is a test."
```

## Step 2: Get TMDB API Key (Free)

1. Go to https://www.themoviedb.org/signup
2. Sign up for a free account
3. Go to Settings → API → Create API Key
4. Choose "Developer" and fill in the form
5. Copy your API key

## Step 3: Set Up Python Environment

```bash
# Navigate to project directory
cd /Users/sagardarji/CinematchAI

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (takes ~5 minutes)
pip install -r requirements.txt
```

## Step 4: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env file and add your TMDB API key
nano .env  # or use your preferred editor
```

Update these lines in `.env`:
```bash
TMDB_API_KEY=your_api_key_here  # Paste your key
OLLAMA_MODEL_MAIN=llama3.1:8b   # Use 8B model
OLLAMA_MODEL_FAST=llama3.1:8b
```

## Step 5: Download and Process Data

**Quick Test (Recommended First):**
```bash
# Test with just 100 movies (~2 minutes)
python scripts/setup_data.py --max-movies 100 --max-posters 50
```

**Full Dataset (Takes ~2-3 hours):**
```bash
# Download MovieLens 25M + enrich with TMDB + download posters
python scripts/setup_data.py
```

This will:
- ✅ Download MovieLens dataset (250MB zip)
- ✅ Enrich ~62,000 movies with TMDB metadata
- ✅ Download movie posters
- ✅ Save processed data to `data/processed/`

## Step 6: Build Embeddings (Coming Soon)

```bash
# Generate text and image embeddings
python scripts/build_embeddings.py

# Build vector database
python scripts/build_vectordb.py
```

## Step 7: Run the Application (Coming Soon)

```bash
# Terminal 1: Start FastAPI backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start Streamlit UI
streamlit run src/ui/app.py
```

Then open:
- **UI:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

---

## Quick Test Commands

**Check if Ollama is running:**
```bash
curl http://localhost:11434/api/version
```

**Test TMDB API:**
```bash
# Should show movie details for "Inception"
curl "https://api.themoviedb.org/3/movie/27205?api_key=YOUR_KEY"
```

**Check Python packages:**
```bash
pip list | grep -E "langchain|chromadb|fastapi|streamlit"
```

---

## Troubleshooting

**Ollama not found:**
```bash
# Ensure Ollama is in PATH
which ollama

# If not found, restart terminal or add to PATH
export PATH="/usr/local/bin:$PATH"
```

**TMDB rate limit errors:**
- The free tier allows 40 requests per 10 seconds
- The script automatically handles rate limiting
- If you hit limits, wait a few minutes and retry

**Out of memory during data processing:**
```bash
# Use smaller sample for testing
python scripts/setup_data.py --max-movies 1000
```

**Dependencies fail to install:**
```bash
# Update pip first
pip install --upgrade pip

# Install with verbose output
pip install -r requirements.txt -v
```

---

## Current Progress

✅ **Week 1 Complete:**
- Project structure
- Configuration management
- Core data models
- Logging and caching

✅ **Week 2 In Progress:**
- Data pipeline (MovieLens + TMDB)
- TMDB API client with rate limiting
- Poster downloader

🔜 **Coming Next:**
- Embedding generation (text + images)
- Vector database setup
- Agent implementation

---

## Next Steps After Setup

Once data is downloaded and processed:

1. **Explore the data:**
   ```bash
   python -c "import pandas as pd; df = pd.read_parquet('data/processed/movies_enriched.parquet'); print(df.head())"
   ```

2. **Check data statistics:**
   - Number of movies
   - Number of ratings
   - Genre distribution

3. **Ready to build embeddings!**

---

## Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/cinematch-ai/issues)
- **Documentation:** Check `/docs` folder
- **Plan:** See `.claude/plans/abundant-drifting-planet.md` for detailed roadmap

Happy building! 🎬✨
