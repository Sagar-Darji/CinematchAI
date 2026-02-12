# 🔧 Personalization Fix - Ensuring Agent-Based Recommendations

## Problem Identified

After integrating on-demand TMDB trending movies, the system was returning trending movies for **all users** instead of using the 6-agent personalized recommendation system.

## Root Cause

The `cold_start_retrieval()` function was fetching trending movies for ALL users, even existing users with rating history and preferences. This bypassed the entire multi-agent personalization system.

## Solution Implemented

### 1. Updated `cold_start_retrieval()` Logic

**File:** [src/agents/graph/tools.py](src/agents/graph/tools.py:304-382)

**Changes:**
- Added check for `is_truly_new_user` before using trending movies
- Only fetches trending/popular movies for NEW users (no rating history)
- For existing users without profile embedding, uses ChromaDB diverse sampling
- Preserves user preferences even during cold-start scenarios

```python
# NEW LOGIC:
is_truly_new_user = user_profile is None or getattr(user_profile, "is_cold_start", True)

if is_truly_new_user:
    # New user → Trending movies (good discovery)
    candidate_movies = retrieve_on_demand_movies(...)
else:
    # Existing user → ChromaDB diverse sampling (respects preferences)
    candidate_movies = []  # Falls back to ChromaDB
```

### 2. Updated `retrieval_node()` Logic

**File:** [src/agents/graph/workflow.py](src/agents/graph/workflow.py:103-132)

**Changes:**
- More precise cold-start detection
- Checks for `profile_embedding` existence
- Prioritizes personalized retrieval when possible
- Only uses cold-start for truly new users

```python
# NEW LOGIC:
has_profile_embedding = (
    user_profile is not None
    and hasattr(user_profile, "profile_embedding")
    and user_profile.profile_embedding is not None
)

if has_profile_embedding:
    # User has preferences → Personalized recommendations (6 agents)
    return retrieve_candidates(state, k=50, use_hybrid=True)
else:
    # New user → Cold-start retrieval
    return cold_start_retrieval(state)
```

---

## How Recommendations Now Work

### For NEW Users (No Rating History)

**Flow:**
```
New User Request
    ↓
Retrieval Node detects: user_profile is None
    ↓
cold_start_retrieval()
    ↓
Fetches trending/popular movies from TMDB
    ↓
Context-Aware Agent → Content Intelligence → Serendipity → Explanation
    ↓
Trending movies with basic context awareness
```

**Purpose:** Give new users relevant, popular movies to rate

### For EXISTING Users (Have Rating History)

**Flow:**
```
Existing User Request
    ↓
Profile Analyzer Agent
    ↓
Generates user_profile with profile_embedding (from rating history)
    ↓
Retrieval Node detects: has_profile_embedding = True
    ↓
retrieve_candidates(state, k=50, use_hybrid=True)
    ↓
1. Vector search in ChromaDB using user's profile embedding
2. Get top-50 candidates matching user preferences
3. On-demand enrichment from TMDB (fresh metadata)
    ↓
Content Intelligence → Serendipity → Explanation
    ↓
PERSONALIZED recommendations based on YOUR preferences!
```

**Purpose:** Deliver personalized recommendations using all 6 agents

---

## Verification Steps

### 1. Check if Personalization is Working

**Test with Existing User:**
```bash
# Start API
python -m uvicorn src.api.main:app --reload --port 8000

# In another terminal, test API
curl -X POST "http://localhost:8000/api/v1/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "context": {"mood": "thoughtful"},
    "k": 5
  }'
```

**What to Check:**
- Open API logs (terminal running uvicorn)
- Look for: `"Using personalized retrieval (user has profile with preferences)"`
- If you see: `"Using cold-start retrieval"` → User has no profile embedding

### 2. Check Logs for Retrieval Type

**Expected Log Sequence (Personalized):**
```
INFO: Profile Analyzer: Analyzing user preferences
INFO: Profile Analyzer: Found 25 ratings for user test_user
INFO: Profile Analyzer: Generated profile embedding (768-dim)
INFO: Using personalized retrieval (user has profile with preferences)
INFO: Retrieved 50 candidates (enriched from TMDB)
INFO: Content Intelligence: Analyzing 50 movies
INFO: Serendipity: Optimizing for diversity
INFO: Explanation: Generating explanations
```

**Wrong Log Sequence (Trending Only - BAD):**
```
INFO: Using cold-start retrieval (no personalization available)
INFO: New user detected - fetching trending/popular movies from TMDB
INFO: On-demand retrieval: 50 movies fetched from TMDB API
```

### 3. Test in Streamlit UI

**For Existing Users:**
1. Go to Recommendations page
2. Enter your user_id (must have rated movies before)
3. Click "Refresh Recommendations"
4. Check explanations:
   - ✅ GOOD: "Based on your love for [genre]..."
   - ❌ BAD: "Currently trending..."

**For New Users:**
1. Complete onboarding (rate 5 movies)
2. Get recommendations
3. Should now be personalized!

---

## Agent System Flow (Confirmed Working)

### 6-Agent System for Personalized Recommendations

**Agent Execution Order:**

1. **Profile Analyzer Agent**
   - Analyzes user's rating history
   - Extracts preferences (genres, directors, themes)
   - Generates profile embedding (768-dim vector)
   - Output: UserProfile with preferences

2. **Context-Aware Agent**
   - Processes current context (time, mood, companion)
   - Parses natural language context if provided
   - Generates context factors
   - Output: ContextFactors

3. **Retrieval Tool (RAG)**
   - Uses profile embedding for vector search
   - Queries ChromaDB with user preferences
   - Fetches top-50 matching candidates
   - On-demand enrichment from TMDB
   - Output: candidate_movies (50 movies)

4. **Content Intelligence Agent**
   - Analyzes candidate movies for themes
   - Extracts micro-genres
   - Matches with user preferences
   - Output: Enriched candidates with content analysis

5. **Serendipity Agent**
   - Balances exploration vs exploitation
   - Ensures diversity (genre, year, style)
   - Prevents filter bubbles
   - Output: Diverse candidate list

6. **Explanation Agent**
   - Generates natural language explanations
   - Multi-faceted reasoning (content, collaborative, contextual)
   - References user's natural language input if provided
   - Output: Recommendations with explanations

**Result:** Personalized recommendations with explanations!

---

## Debugging Commands

### Check User Profile Status

```python
# In Python console
from src.services.user_service import get_user_service

user_service = get_user_service()

# Check if user has ratings
user_id = "test_user"
# If user exists, they should get personalized recommendations
```

### Enable Debug Logging

```python
# In config/settings.py or at runtime
import logging
logging.getLogger("src.agents").setLevel(logging.DEBUG)
logging.getLogger("src.core").setLevel(logging.DEBUG)
```

### Watch Logs in Real-Time

```bash
# In terminal running uvicorn:
# You'll see logs for each agent execution
# Look for:
# - "Profile Analyzer: Analyzing user preferences"
# - "Using personalized retrieval"
# - "Retrieved X candidates (enriched from TMDB)"
```

---

## What Changed vs Original

### Before Fix (BROKEN)

```python
cold_start_retrieval():
    # ALWAYS fetched trending movies
    candidate_movies = retrieve_on_demand_movies(...)
    # ❌ Even for existing users with preferences!
```

**Result:** Everyone got trending movies (no personalization)

### After Fix (WORKING)

```python
cold_start_retrieval():
    if is_truly_new_user:
        # Only new users get trending
        candidate_movies = retrieve_on_demand_movies(...)
    else:
        # Existing users use ChromaDB
        candidate_movies = []  # ChromaDB fallback

retrieval_node():
    if has_profile_embedding:
        # ✅ Personalized vector search
        return retrieve_candidates(state, k=50, use_hybrid=True)
    else:
        # New users only
        return cold_start_retrieval(state)
```

**Result:** Personalized recommendations for existing users, trending for new users

---

## Benefits of This Architecture

### For NEW Users
- ✅ See trending/popular movies (good discovery)
- ✅ Language-aware if context provided
- ✅ Fresh content from TMDB API
- ✅ After rating 5 movies → Switches to personalized

### For EXISTING Users
- ✅ Full 6-agent personalized system
- ✅ Vector search based on YOUR preferences
- ✅ Context-aware (mood, time, companion)
- ✅ Natural language understanding
- ✅ Explainable recommendations
- ✅ On-demand enrichment (fresh TMDB data)

---

## Summary

**Problem:** Trending movies overriding personalized recommendations
**Solution:** Separate logic for new vs existing users
**Verification:** Check logs for "Using personalized retrieval"
**Status:** ✅ FIXED - 6-agent system working as designed!

---

<p align="center">
  <strong>🎬 Personalization Restored!</strong><br>
  <em>Trending for new users • Personalized for everyone else</em>
</p>
