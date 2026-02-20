# 🚀 Deploy to Hugging Face Spaces

Complete guide for deploying CineMatch AI to Hugging Face Spaces (free hosting).

---

## Prerequisites

1. **Hugging Face Account**
   - Sign up at https://huggingface.co/join (free)

2. **Groq API Key** (free)
   - Sign up at https://console.groq.com
   - Get free API key (30 requests/minute)

3. **Git & HuggingFace CLI**
   ```bash
   # Install HuggingFace CLI
   pip install huggingface_hub[cli]

   # Login to HuggingFace
   huggingface-cli login
   # Paste your HF token when prompted
   ```

---

## Quick Deploy (Automated)

### Step 1: Run Deployment Script

```bash
python scripts/deploy_hf_spaces.py
```

This will:
- ✅ Check prerequisites
- ✅ Prepare deployment files
- ✅ Create HF Space
- ✅ Push code to HF

### Step 2: Add Secrets

Go to your Space settings:
`https://huggingface.co/spaces/YOUR_USERNAME/cinematch-ai/settings`

Add these secrets:
- **GROQ_API_KEY**: Your Groq API key (required)
- **TMDB_API_KEY**: Your TMDB API key (optional)
- **DATABASE_URL**: Supabase PostgreSQL URI (required for persistent users — see [Supabase Setup](#-persistent-users--supabase-setup))
- **JWT_SECRET**: Random secret for auth tokens — run `openssl rand -hex 32`
- **GOOGLE_CLIENT_ID**: Google OAuth Client ID (required for Google Sign-In — see [Google Sign-In Setup](#-google-sign-in-setup))

Add these **Variables** (public, not secret):
- **VITE_GOOGLE_CLIENT_ID**: Same value as GOOGLE_CLIENT_ID (needed by the frontend at build time)

### Step 3: Wait for Build

- Build takes 5-10 minutes
- Check "Building" status in Space
- View logs if any errors

### Step 4: Test Your Space

- Click "App" tab
- Complete onboarding (rate 5 movies)
- Get recommendations!

---

## 🗄️ Persistent Users — Supabase Setup

Without this, all user accounts and ratings are wiped every time the Space restarts.

### 1. Create a free Supabase project

1. Go to https://supabase.com and sign up (free)
2. Click **New project**, give it any name (e.g. `cinematch`)
3. Choose a region close to your HF Space region
4. Save the database password (you'll need it once)

### 2. Get the connection string

1. In Supabase dashboard → **Settings** → **Database**
2. Scroll to **Connection string** → select **URI** tab
3. Copy the string — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```
4. Replace `[YOUR-PASSWORD]` with your actual database password

### 3. Add to HF Spaces

Space settings → **Secrets** → add:
- **Name**: `DATABASE_URL`  **Value**: the full URI from step 2

That's it. The app automatically uses PostgreSQL when `DATABASE_URL` is set, and SQLite locally.

---

## 🔐 Google Sign-In Setup

Lets users sign in with one click — no password to remember. Their account persists in Supabase.

### 1. Create Google OAuth credentials

1. Go to https://console.cloud.google.com → create or select a project
2. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Under **Authorised JavaScript origins** add:
   ```
   https://YOUR-USERNAME-cinematch-ai.hf.space
   ```
   (replace with your actual HF Space URL — find it in Space settings)
5. Click **Create** → copy the **Client ID**

### 2. Add to HF Spaces

Space settings → **Secrets**:
- **GOOGLE_CLIENT_ID** = your Client ID

Space settings → **Variables** (public):
- **VITE_GOOGLE_CLIENT_ID** = same Client ID

> ⚠️ `VITE_GOOGLE_CLIENT_ID` must be a **Variable** (not a Secret) because Vite embeds it at build time. After adding it, push a commit or factory-reset the Space to trigger a rebuild.

---

## Manual Deploy

If automated script doesn't work, follow these manual steps:

### 1. Prepare Files

```bash
# Copy HF-optimized requirements
cp requirements-hf.txt requirements.txt

# Copy HF README
cp README_HF.md README.md
```

### 2. Create Space on HuggingFace

- Go to https://huggingface.co/new-space
- Name: `cinematch-ai`
- SDK: `Streamlit`
- Visibility: Public (or Private)
- Click "Create Space"

### 3. Push Code to Space

```bash
# Add HF Space as remote
git remote add spaces https://huggingface.co/spaces/YOUR_USERNAME/cinematch-ai

# Push code
git push spaces main
```

### 4. Configure Space

In Space settings:

**Secrets:**
```
GROQ_API_KEY=your_groq_api_key
TMDB_API_KEY=your_tmdb_api_key  # Optional
```

**Files:**
- Ensure `app_hf.py` is present
- Ensure `.streamlit/config.toml` is present
- Ensure `requirements.txt` (not requirements-hf.txt) is present

---

## Architecture on HF Spaces

### What Changes?

**Local Development:**
```
Ollama (local LLM) → sentence-transformers → ChromaDB (local)
```

**HF Spaces:**
```
Groq API (cloud LLM) → sentence-transformers → ChromaDB (in-memory)
```

### Key Differences

| Component | Local | HF Spaces |
|-----------|-------|-----------|
| **LLM** | Ollama (Llama 3.1 8B) | Groq API (Llama 3.1 70B) |
| **Embeddings** | Local (GPU/CPU) | Local (CPU only) |
| **Vector DB** | Persistent ChromaDB | In-memory ChromaDB |
| **Data** | Full 62K movies | Subset (~1K movies) |
| **Storage** | 50GB+ | < 1GB |

---

## Optimization for Free Tier

### Memory Limits

HF Spaces Free Tier: **16GB RAM**

**Optimizations:**
1. Load smaller movie subset (~1,000 movies)
2. Use in-memory ChromaDB (no persistence)
3. Lazy load embeddings
4. Cache aggressively

### Rate Limits

Groq Free Tier: **30 requests/minute**

**Optimizations:**
1. Cache LLM responses (1 hour TTL)
2. Use fast model for simple tasks
3. Batch LLM calls where possible

---

## Files Required for HF Spaces

### Core Files

- `app_hf.py` - Entry point for HF Spaces ✅
- `requirements.txt` - Python dependencies (from requirements-hf.txt) ✅
- `.streamlit/config.toml` - Streamlit configuration ✅
- `README.md` - Space description (from README_HF.md) ✅

### Application Code

- `src/` - All source code ✅
- `data/` - Minimal data (embeddings for ~1K movies) ⚠️
- `config/` - Configuration files ✅

### Excluded (Too Large)

- `data/raw/` - Raw MovieLens files (250MB)
- `data/processed/` - Full processed data
- Full vector database (too large for free tier)

---

## Troubleshooting

### Build Fails

**Error: Out of memory**
```
Solution: Reduce dataset size in config
- Set MAX_MOVIES=1000 in settings
- Use smaller embedding model
```

**Error: Dependencies conflict**
```
Solution: Check requirements-hf.txt
- Remove conflicting versions
- Use compatible versions
```

### App Crashes

**Error: Groq API rate limit**
```
Solution: Add aggressive caching
- Cache LLM responses for 1 hour
- Reduce concurrent requests
```

**Error: ChromaDB not found**
```
Solution: Rebuild vector DB on startup
- Add startup script to rebuild
- Use in-memory DB
```

### Slow Performance

**Issue: Cold start takes 30-60 seconds**
```
Expected on HF Spaces free tier
- First request initializes models
- Subsequent requests are faster
```

**Issue: Recommendations take >10 seconds**
```
Solution: Check Groq API latency
- Groq should respond in <1s
- If slow, may be rate limited
```

---

## Testing Your Deployment

### 1. Health Check

Visit: `https://YOUR_USERNAME-cinematch-ai.hf.space/api/v1/health`

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "agents_loaded": true,
  "vectordb_connected": true
}
```

### 2. Onboarding Flow

1. Open Space URL
2. Click "Start Onboarding"
3. Rate 5 movies
4. Submit
5. Should see recommendations

### 3. API Endpoints

Test with cURL:
```bash
curl -X POST "https://YOUR_USERNAME-cinematch-ai.hf.space/api/v1/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "k": 5
  }'
```

---

## Monitoring

### View Logs

- Go to Space settings → "Logs"
- Check for errors or warnings
- Monitor memory usage

### Check Performance

- Response time should be < 5 seconds
- Memory usage should stay < 14GB
- No frequent restarts

---

## Updating Your Space

### After Code Changes

```bash
# Commit changes
git add .
git commit -m "Update: description"

# Push to HF Spaces
git push spaces main

# Space will automatically rebuild
```

### After Dependency Changes

1. Update `requirements-hf.txt`
2. Copy to `requirements.txt`
3. Push to trigger rebuild

---

## Cost & Limits

### HF Spaces Free Tier

- ✅ **CPU**: 2 cores
- ✅ **RAM**: 16GB
- ✅ **Storage**: 50GB (ephemeral)
- ✅ **Bandwidth**: Unlimited
- ❌ **GPU**: Not available (upgrade required)

### Groq Free Tier

- ✅ **Requests**: 30/minute
- ✅ **Tokens**: 14,400/minute
- ✅ **Models**: Llama 3.1 70B, 8B, etc.

### Upgrade Options

**HF Spaces Pro** ($5/month):
- 4 cores, 32GB RAM
- Persistent storage
- Faster build times

**Groq Pro** (when available):
- Higher rate limits
- Priority access

---

## Security Best Practices

### Secrets Management

✅ **Use HF Spaces Secrets** (not .env files)
❌ **Never commit API keys** to git
✅ **Rotate keys regularly**

### Access Control

- Set Space to Private if needed
- Use authentication for sensitive features
- Rate limit API endpoints

---

## Example Deployment

**Live Demo:**
`https://huggingface.co/spaces/YOUR_USERNAME/cinematch-ai`

**Source Code:**
`https://github.com/yourusername/cinematch-ai`

---

## Support

### Getting Help

- **HF Spaces Issues**: https://huggingface.co/spaces
- **Groq API Issues**: https://console.groq.com
- **Project Issues**: GitHub Issues

### Common Issues

- Memory errors → Reduce dataset size
- Rate limits → Add caching
- Slow builds → Reduce dependencies

---

## Next Steps After Deployment

1. ✅ **Share Your Space**
   - Add to portfolio
   - Share on LinkedIn
   - Include in resume

2. ✅ **Create Demo Video**
   - Screen record using Space
   - 2-3 minute walkthrough

3. ✅ **Write Blog Post**
   - Technical architecture
   - Deployment challenges
   - Lessons learned

---

<p align="center">
  <strong>🎬 CineMatch AI on Hugging Face Spaces</strong><br>
  Free hosting for your AI portfolio project!
</p>
