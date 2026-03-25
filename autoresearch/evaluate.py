"""Fast evaluator for autoresearch experiments.

Uses proxy quality metrics that measure recommendation quality directly:
- Genre alignment: Do recs match the user's preferred genres?
- Personalization: Director/actor/language familiarity
- Quality: Average TMDB rating of recommended movies
- Diversity: Genre spread across recommendations
- Novelty: Not just recommending blockbusters

These are much more sensitive to parameter changes than exact-match hit rate
on an open catalog.

Usage:
    python -m autoresearch.evaluate
    python -m autoresearch.evaluate --users 1 --contexts 3
"""

import os
import sys
import json
import time
import sqlite3
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import Counter

# Project root
_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Force SQLite mode
os.environ.pop("AUTH_DATABASE_URL", None)
os.environ.pop("DATABASE_URL", None)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Force Ollama for pipeline LLM calls during autoresearch (avoid Groq rate limits)
if os.environ.get("LLM_PROVIDER") == "ollama":
    os.environ.setdefault("OLLAMA_MODEL_MAIN", "llama3.1:8b")
    os.environ.setdefault("OLLAMA_MODEL_FAST", "llama3.1:8b")

import numpy as np

from src.utils.logging import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(_root) / "data" / "users.db"


# ── Composite weights ────────────────────────────────────────────────────────
COMPOSITE_WEIGHTS = {
    "genre_alignment":  0.25,   # Do recs match user's favorite genres?
    "personalization":  0.20,   # Director/actor/language familiarity
    "quality":          0.20,   # Average TMDB vote_average of recs
    "diversity":        0.20,   # Genre spread in recommendations
    "novelty":          0.15,   # Avoiding only ultra-popular blockbusters
}

# ── Contexts to evaluate across ──────────────────────────────────────────────
EVAL_CONTEXTS = [
    {},
    {"mood": "happy", "time_of_day": "evening", "companion": "alone"},
    {"mood": "thoughtful", "time_of_day": "night", "companion": "alone"},
    {"mood": "bored", "time_of_day": "afternoon", "companion": "friends"},
    {"mood": "relaxed", "time_of_day": "morning", "companion": "family"},
]


def load_user_ratings(user_id: str) -> List[Dict]:
    """Load all ratings for a user from local SQLite DB."""
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT movie_id, rating, timestamp FROM ratings WHERE user_id = ? ORDER BY timestamp ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_test_users(min_ratings: int = 20) -> List[str]:
    """Get users with enough ratings for meaningful evaluation."""
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT user_id, COUNT(*) as cnt FROM ratings GROUP BY user_id HAVING cnt >= ? ORDER BY cnt DESC",
        (min_ratings,),
    ).fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


def _extract_user_preferences(ratings: List[Dict]) -> Dict:
    """Extract user's genre/director/actor/language preferences from ratings."""
    from src.services.movie_service import get_movie_service
    movie_service = get_movie_service()

    genre_counts: Counter = Counter()
    liked_genre_counts: Counter = Counter()
    directors: Counter = Counter()
    actors: Counter = Counter()
    languages: Counter = Counter()

    for r in ratings:
        try:
            movie = movie_service.get_movie_by_id(tmdb_id=int(r["movie_id"]))
            if not movie:
                continue
            genres = [g.lower() for g in (movie.metadata.genres or [])]
            genre_counts.update(genres)
            if float(r["rating"]) >= 3.5:
                liked_genre_counts.update(genres)
            if movie.metadata.director:
                directors[movie.metadata.director.lower()] += 1
            for actor in (movie.metadata.cast or [])[:3]:
                actors[actor.lower()] += 1
            if movie.metadata.original_language:
                languages[movie.metadata.original_language] += 1
        except Exception:
            continue

    fav_genres = set(g for g, _ in liked_genre_counts.most_common(5))
    fav_directors = set(d for d, _ in directors.most_common(5))
    fav_actors = set(a for a, _ in actors.most_common(10))
    pref_languages = set(l for l, _ in languages.most_common(3))

    return {
        "fav_genres": fav_genres,
        "all_genres": set(genre_counts.keys()),
        "fav_directors": fav_directors,
        "fav_actors": fav_actors,
        "pref_languages": pref_languages,
        "rated_movie_ids": set(str(r["movie_id"]) for r in ratings),
    }


def score_recommendations(recs, prefs: Dict) -> Dict[str, float]:
    """Score a recommendation list against user preferences.

    Args:
        recs: List of Recommendation objects from the pipeline.
        prefs: User preferences dict from _extract_user_preferences.

    Returns:
        Dict of metric_name -> score (0-1).
    """
    if not recs:
        return {k: 0.0 for k in COMPOSITE_WEIGHTS}

    fav_genres = prefs["fav_genres"]
    fav_directors = prefs["fav_directors"]
    fav_actors = prefs["fav_actors"]
    pref_languages = prefs["pref_languages"]
    rated_ids = prefs["rated_movie_ids"]

    # ── Genre Alignment (0-1) ────────────────────────────────────────────
    genre_scores = []
    all_rec_genres: List[str] = []
    for rec in recs:
        movie_genres = set(g.lower() for g in (rec.movie.metadata.genres or []))
        all_rec_genres.extend(movie_genres)
        if fav_genres and movie_genres:
            overlap = len(movie_genres & fav_genres) / len(movie_genres)
            genre_scores.append(overlap)
        else:
            genre_scores.append(0.0)
    genre_alignment = float(np.mean(genre_scores)) if genre_scores else 0.0

    # ── Personalization (0-1) ────────────────────────────────────────────
    # Combines director match, actor match, language match, not-already-seen
    person_scores = []
    for rec in recs:
        score = 0.0
        mid = str(rec.movie.metadata.tmdb_id)
        director = (rec.movie.metadata.director or "").lower()
        cast = set(a.lower() for a in (rec.movie.metadata.cast or [])[:3])
        lang = rec.movie.metadata.original_language or ""

        # Director match (0.3)
        if director and director in fav_directors:
            score += 0.3
        # Actor match (0.3)
        if cast and fav_actors:
            actor_overlap = len(cast & fav_actors)
            score += min(actor_overlap * 0.15, 0.3)
        # Language match (0.2)
        if lang and lang in pref_languages:
            score += 0.2
        # Not already seen (0.2) — recommending unseen movies is better
        if mid not in rated_ids:
            score += 0.2

        person_scores.append(score)
    personalization = float(np.mean(person_scores)) if person_scores else 0.0

    # ── Quality (0-1) ────────────────────────────────────────────────────
    # Average TMDB vote_average normalized to 0-1 (scale: 0-10)
    vote_avgs = []
    for rec in recs:
        va = rec.movie.metadata.vote_average
        if va and va > 0:
            vote_avgs.append(va / 10.0)
    quality = float(np.mean(vote_avgs)) if vote_avgs else 0.5

    # ── Diversity (0-1) ──────────────────────────────────────────────────
    # Genre diversity: how many unique genres across all recommendations
    unique_genres = set(all_rec_genres)
    # Normalize: 1 genre = 0, 10+ genres = 1.0
    diversity = min(len(unique_genres) / 10.0, 1.0) if all_rec_genres else 0.0

    # Also add pairwise genre Jaccard distance
    if len(recs) >= 2:
        pairwise_distances = []
        for i, r1 in enumerate(recs):
            g1 = set(g.lower() for g in (r1.movie.metadata.genres or []))
            for r2 in recs[i+1:]:
                g2 = set(g.lower() for g in (r2.movie.metadata.genres or []))
                union = len(g1 | g2)
                if union > 0:
                    pairwise_distances.append(1 - len(g1 & g2) / union)
        if pairwise_distances:
            diversity = 0.5 * diversity + 0.5 * float(np.mean(pairwise_distances))

    # ── Novelty (0-1) ────────────────────────────────────────────────────
    # Inverse of average popularity (vote_count). Less popular = more novel.
    # Scale: log(vote_count) where 10K+ votes = 0 novelty, <100 votes = 1.0
    novelty_scores = []
    for rec in recs:
        vc = rec.movie.metadata.vote_count or 0
        if vc > 0:
            # log10(100)=2, log10(10000)=4 → normalize to 0-1 inversely
            log_pop = np.log10(max(vc, 1))
            nov = max(0.0, 1.0 - (log_pop - 2.0) / 2.0)  # 100 votes=1.0, 10K+=0.0
            novelty_scores.append(nov)
        else:
            novelty_scores.append(1.0)
    novelty = float(np.mean(novelty_scores)) if novelty_scores else 0.5

    return {
        "genre_alignment": round(genre_alignment, 6),
        "personalization": round(personalization, 6),
        "quality": round(quality, 6),
        "diversity": round(diversity, 6),
        "novelty": round(novelty, 6),
    }


def evaluate_single_user(
    user_id: str,
    context: Dict,
    prefs: Dict,
    k: int = 10,
) -> Dict[str, float]:
    """Run recommendations for one user+context and score them."""
    from src.agents.graph.workflow import run_recommendation_workflow

    try:
        state = run_recommendation_workflow(
            user_id=user_id,
            context=context,
            is_cold_start=False,
            k=k,
        )
    except Exception as e:
        logger.warning(f"Workflow failed for user {user_id}: {e}")
        return {k_: 0.0 for k_ in COMPOSITE_WEIGHTS}

    recs = state.get("final_recommendations", [])
    if not recs:
        return {k_: 0.0 for k_ in COMPOSITE_WEIGHTS}

    return score_recommendations(recs, prefs)


def run_evaluation(n_users: int = 1, k: int = 10, n_contexts: int = 1) -> Dict:
    """Run full evaluation and return results dict with composite score."""

    # Force SQLite mode
    import src.core.db as _db_mod
    _db_mod._adapter = None
    adapter = _db_mod.DBAdapter.__new__(_db_mod.DBAdapter)
    adapter.database_url = None
    adapter.db_path = _DB_PATH
    _db_mod._adapter = adapter

    import src.services.user_service as _us_mod
    _us_mod._user_service = None

    # Apply autoresearch patches
    from autoresearch.patch import reload_and_patch
    params = reload_and_patch()

    t0 = time.time()

    # Get test users
    all_users = get_test_users(min_ratings=20)
    test_users = all_users[:n_users]
    if not test_users:
        raise RuntimeError("No users with >= 20 ratings in local DB")

    contexts = EVAL_CONTEXTS[:n_contexts]
    logger.info(f"Evaluating {len(test_users)} users × {len(contexts)} contexts")

    all_metrics: List[Dict[str, float]] = []

    for uid in test_users:
        # Extract preferences from ALL ratings (these don't change)
        ratings = load_user_ratings(uid)
        logger.info(f"  user={uid}: {len(ratings)} ratings")

        prefs = _extract_user_preferences(ratings)
        logger.info(f"    fav_genres={prefs['fav_genres']}")

        for ctx in contexts:
            logger.info(f"    context={ctx}")
            m = evaluate_single_user(uid, ctx, prefs, k)
            all_metrics.append(m)
            logger.info(f"    → genre={m['genre_alignment']:.3f} person={m['personalization']:.3f} "
                        f"quality={m['quality']:.3f} diversity={m['diversity']:.3f} "
                        f"novelty={m['novelty']:.3f}")

    # Average across all user×context pairs
    avg = {}
    for key in COMPOSITE_WEIGHTS:
        avg[key] = float(np.mean([m[key] for m in all_metrics]))

    # Composite score
    composite = sum(COMPOSITE_WEIGHTS[k_] * avg[k_] for k_ in COMPOSITE_WEIGHTS)

    elapsed = time.time() - t0

    from autoresearch.params import EXPERIMENT_NOTE

    result = {
        "composite_score": round(composite, 6),
        "metrics": {k_: round(v, 6) for k_, v in avg.items()},
        "n_users": len(test_users),
        "n_contexts": len(contexts),
        "k": k,
        "elapsed_seconds": round(elapsed, 1),
        "experiment_note": EXPERIMENT_NOTE,
        "params_snapshot": {k_: v for k_, v in params.items()},
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="CineMatch AI autoresearch evaluator")
    parser.add_argument("--users", type=int, default=1, help="Number of test users")
    parser.add_argument("--contexts", type=int, default=1, help="Number of contexts (1-5)")
    parser.add_argument("--k", type=int, default=10, help="Top-K recommendations")
    args = parser.parse_args()

    result = run_evaluation(n_users=args.users, k=args.k, n_contexts=args.contexts)

    print("\n" + "=" * 60)
    print("AUTORESEARCH EVALUATION RESULT")
    print("=" * 60)
    print(f"  Composite Score:  {result['composite_score']:.6f}  (higher = better)")
    print(f"  Genre Alignment:  {result['metrics']['genre_alignment']:.4f}")
    print(f"  Personalization:  {result['metrics']['personalization']:.4f}")
    print(f"  Quality:          {result['metrics']['quality']:.4f}")
    print(f"  Diversity:        {result['metrics']['diversity']:.4f}")
    print(f"  Novelty:          {result['metrics']['novelty']:.4f}")
    print(f"  Time:             {result['elapsed_seconds']}s")
    print(f"  Note:             {result['experiment_note']}")
    print("=" * 60)

    return result


if __name__ == "__main__":
    main()
