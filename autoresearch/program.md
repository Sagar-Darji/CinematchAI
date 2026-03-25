# CineMatch AI AutoResearch — Agent Program

You are optimizing a 7-agent movie recommendation system. The system uses
LangGraph to orchestrate: Profile Analyzer → Context-Aware → Retrieval →
Content Intelligence → Serendipity → Critic → Explanation → Aggregation.

## How the scoring works

The composite score is a weighted average of 5 proxy quality metrics (all 0-1, higher = better):
- **genre_alignment** (25%): Do recommended genres match the user's favorite genres?
- **personalization** (20%): Do recs feature familiar directors, actors, languages?
- **quality** (20%): Average TMDB vote_average of recommended movies (higher = better films)
- **diversity** (20%): Genre spread across recommendations (avoid filter bubbles)
- **novelty** (15%): Inverse of popularity — avoid only recommending blockbusters

The baseline score is ~0.61. Improvement targets:
- Genre alignment is currently ~0.54 — most room for improvement
- Personalization is ~0.30 — low, but limited by TMDB discover results
- Quality, diversity, novelty are already good (0.64-0.81)

## Parameter groups (ordered by expected impact)

### 1. Retrieval (highest impact — controls WHAT candidates enter the pipeline)
- `retrieval.base_db_ratio`: How much to trust the vector DB vs TMDB discover.
  Higher = more personalised (good for users with lots of ratings).
  Lower = more discovery (good for cold-start or diverse users).
- `retrieval.context_blend_history` / `context_blend_current`: Balance between
  "what the user historically likes" vs "what fits their current mood".
- `retrieval.cf_fraction`: Collaborative filtering share. Higher = more "users
  like you also watched" signal.

### 2. Content Intelligence scoring (controls HOW candidates are ranked)
- `content.genre_match_*`: Genre overlap bonuses. The most direct relevance signal.
- `content.min_score_threshold`: Hard filter cutoff. Too high → starves pipeline.
  Too low → noise passes through.
- `content.tone_mood_*`: Context-based reranking. Important when mood is specified.
- `content.director_affinity_boost`, `content.actor_hit_*`: Personalisation signals.

### 3. Serendipity (controls diversity vs relevance trade-off)
- `serendipity.default_exploration_rate`: Higher = more diverse but less precise.
  Lower = more focused but risk of filter bubble.
- `serendipity.genre_sim_weight` / `year_sim_weight`: How similarity is measured
  for MMR diversity.

### 4. Critic (quality gating)
- `critic.quality_floor`: Minimum vote average. Raising this cuts low-quality
  movies but might remove hidden gems.
- `critic.fail_threshold`: How many checks must fail before demotion.
  1 = aggressive filtering, 3 = permissive.

### 5. Context-Aware weights (fine-tuning for different situations)
- These control how much weight is given to time-of-day, companion, and mood.
- Usually lower impact than retrieval/scoring, but can help with specific contexts.

## Strategy tips

1. **Start with retrieval and content scoring** — these have the biggest
   impact on what movies make it into the final list.
2. **Make small changes** (1-3 params, ±10-20%). Large jumps are hard to learn from.
3. **If a direction works, explore further**. If genre_match helped, try
   adjusting related params (director, actor affinity).
4. **If several experiments fail**, try a completely different area (e.g., switch
   from scoring to retrieval ratios).
5. **Watch for trade-offs**: boosting precision often hurts recall. The composite
   score balances both.
6. **The hard filter threshold** (`content.min_score_threshold`) is very sensitive.
   Small changes here have outsized effects.
