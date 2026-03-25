"""Monkey-patch CineMatch agents to read values from autoresearch/params.py.

Call ``apply_patches()`` once before running the recommendation workflow.
This replaces hard-coded constants in every agent with the current values
from ``PARAMS``, letting the autoresearch loop tweak behaviour without
touching agent source files.
"""

import importlib
import sys
from pathlib import Path
from typing import Dict, Any

# Ensure project root on path
_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


def _load_params() -> Dict[str, Any]:
    """Import (or reload) params.py and return PARAMS dict."""
    import autoresearch.params as _mod
    importlib.reload(_mod)
    return _mod.PARAMS


def _p(params: Dict[str, Any], key: str, default: Any = None):
    """Lookup a param with fallback."""
    return params.get(key, default)


# ---------------------------------------------------------------------------
# Patch functions per agent
# ---------------------------------------------------------------------------

def _patch_content_intelligence(P: Dict[str, Any]):
    """Patch ContentIntelligenceAgent._score_and_rerank to read from PARAMS.

    The original method has ~20 hardcoded constants. This replaces the entire
    method with one that reads every constant from the PARAMS dict.
    """
    import re as _re
    from src.agents import content_intelligence as mod

    cls = mod.ContentIntelligenceAgent
    _original_score_and_rerank = cls._score_and_rerank

    def patched_score_and_rerank(
        self, candidates, content_features, user_profile,
        context_factors, context, context_weights=None,
    ):
        mood = context_factors.get("mood")
        companion = context_factors.get("companion", "alone")
        nl_context = (
            context.get("natural_language_context", "")
            or context_factors.get("natural_language_context", "")
            or ""
        ).lower()
        year_min = context.get("year_min") or context_factors.get("year_min")
        year_max = context.get("year_max") or context_factors.get("year_max")
        language = context.get("language") or context_factors.get("language")

        fav_genres = set()
        disliked_genres = set()
        fav_directors = set()
        fav_actors = set()
        preferred_languages = []
        if user_profile and hasattr(user_profile, "preferences"):
            fav_genres = {g.lower() for g in (user_profile.preferences.favorite_genres or [])}
            disliked_genres = {g.lower() for g in (user_profile.preferences.disliked_genres or [])}
            fav_directors = {d.lower() for d in (user_profile.preferences.favorite_directors or [])}
            fav_actors = {a.lower() for a in (user_profile.preferences.favorite_actors or [])}
            preferred_languages = list(user_profile.preferences.preferred_languages or [])

        nl_keywords = [w for w in nl_context.split() if len(w) > 2] if nl_context else []

        # Read all scoring constants from PARAMS
        BASE_SCORE = P.get("content.base_score", 0.5)
        GENRE_PER = P.get("content.genre_match_per_genre", 0.1)
        GENRE_CAP = P.get("content.genre_match_cap", 0.25)
        DISLIKED_PEN = P.get("content.disliked_genre_penalty", 0.2)
        TONE_FACTOR = P.get("content.tone_mood_factor", 0.3)
        TONE_BASE = P.get("content.tone_mood_baseline", 0.4)
        FAMILY_PEN = P.get("content.family_penalty", 0.25)
        FAMILY_BOOST = P.get("content.family_animation_boost", 0.15)
        ROMANCE_BOOST = P.get("content.romance_boost", 0.1)
        DIR_BOOST = P.get("content.director_affinity_boost", 0.15)
        ACTOR_W = P.get("content.actor_hit_weight", 0.07)
        ACTOR_CAP = P.get("content.actor_hit_cap", 0.14)
        LANG_FIRST = P.get("content.lang_first_bonus", 0.12)
        LANG_DECAY = P.get("content.lang_rank_decay", 0.04)
        LANG_MIN = P.get("content.lang_min_bonus", 0.04)
        FOREIGN_PEN = P.get("content.foreign_lang_penalty", 0.06)
        KW_WEIGHT = P.get("content.keyword_hit_weight", 0.05)
        KW_CAP = P.get("content.keyword_hit_cap", 0.15)
        NOST_NORM = P.get("content.nostalgia_norm", 50.0)
        NOST_WEIGHT = P.get("content.nostalgia_weight", 0.20)
        SEQUEL_PEN = P.get("content.sequel_penalty", 0.08)
        MIN_THRESH = P.get("content.min_score_threshold", 0.35)
        # Context weight multipliers
        CW_FAM_BOOST = P.get("content.cw_family_boost", 0.20)
        CW_FAM_PEN = P.get("content.cw_family_penalty", 0.30)
        CW_ROMANCE = P.get("content.cw_romance", 0.12)
        CW_ATMOS = P.get("content.cw_atmospheric", 0.12)
        CW_LH_COMEDY = P.get("content.cw_lighthearted_comedy", 0.15)
        CW_LH_DRAMA_PEN = P.get("content.cw_lighthearted_drama_penalty", 0.10)
        CW_THOUGHT = P.get("content.cw_thought_provoking", 0.12)
        CW_SHORT_BOOST = P.get("content.cw_short_runtime_boost", 0.08)
        CW_SLOW_PEN = P.get("content.cw_slow_runtime_penalty", 0.05)
        CW_IMMERSIVE = P.get("content.cw_immersive", 0.08)
        CW_UPLIFTING = P.get("content.cw_uplifting", 0.10)

        _SEQUEL_RE = _re.compile(
            r'\b(2|3|4|5|II|III|IV|V|VI|Part\s+2|Chapter\s+2|Returns|'
            r'Rises|Reloaded|Revolutions|Resurrection|Reborn|Unleashed)\b',
            _re.IGNORECASE,
        )

        scored = []
        for movie in candidates:
            movie_id = str(movie.metadata.tmdb_id)
            features = content_features.get(movie_id, {})
            movie_genres = {g.lower() for g in (features.get("genres") or movie.metadata.genres or [])}
            tone = features.get("tone", "balanced")

            # Hard filters
            movie_year = movie.metadata.year
            if year_min and movie_year and movie_year < int(year_min):
                continue
            if year_max and movie_year and movie_year > int(year_max):
                continue
            if language and movie.metadata.original_language:
                if movie.metadata.original_language != language:
                    continue

            # --- Soft scoring (all from PARAMS) ---
            score = BASE_SCORE

            # 1. Genre match
            if fav_genres:
                genre_overlap = len(movie_genres & fav_genres)
                score += min(genre_overlap * GENRE_PER, GENRE_CAP)
            if disliked_genres and (movie_genres & disliked_genres):
                score -= DISLIKED_PEN

            # 2. Tone-mood affinity
            if mood and mood.lower() in self.MOOD_TONE_AFFINITY:
                affinity = self.MOOD_TONE_AFFINITY[mood.lower()].get(tone, TONE_BASE)
                score += (affinity - TONE_BASE) * TONE_FACTOR

            # 3. Companion appropriateness
            if companion == "family":
                if movie_genres & self.NON_FAMILY_GENRES:
                    score -= FAMILY_PEN
                if "family" in movie_genres or "animation" in movie_genres:
                    score += FAMILY_BOOST
            elif companion == "partner":
                if "romance" in movie_genres:
                    score += ROMANCE_BOOST

            # 4. Director / actor affinity
            movie_director = (movie.metadata.director or "").lower()
            if fav_directors and movie_director and movie_director in fav_directors:
                score += DIR_BOOST
            movie_cast = {a.lower() for a in (movie.metadata.cast or [])}
            if fav_actors:
                actor_hits = len(movie_cast & fav_actors)
                score += min(actor_hits * ACTOR_W, ACTOR_CAP)

            # 5. Language preference
            if preferred_languages and not language:
                movie_lang = movie.metadata.original_language or ""
                if movie_lang and movie_lang in preferred_languages:
                    rank = preferred_languages.index(movie_lang)
                    score += max(LANG_FIRST - rank * LANG_DECAY, LANG_MIN)
                elif movie_lang and movie_lang not in preferred_languages:
                    score -= FOREIGN_PEN

            # 7. NL keyword matching
            if nl_keywords:
                themes = [t.lower() for t in (features.get("themes") or [])]
                micro_genres = [mg.lower() for mg in (features.get("micro_genres") or [])]
                overview = (movie.metadata.overview or "").lower()
                searchable = " ".join(themes + micro_genres) + " " + " ".join(movie_genres) + " " + overview
                keyword_hits = sum(1 for kw in nl_keywords if kw in searchable)
                score += min(keyword_hits * KW_WEIGHT, KW_CAP)

            # 8. Nostalgia alignment
            if user_profile and hasattr(user_profile, "preferences"):
                nostalgia = getattr(user_profile.preferences, "nostalgia_tendency", 0.5)
                m_year = movie.metadata.year or 2000
                movie_age = min(max((2025 - m_year) / NOST_NORM, 0.0), 1.0)
                alignment = 1.0 - abs(nostalgia - movie_age)
                score += (alignment - 0.5) * NOST_WEIGHT

            # 9. Sequel penalty
            if _SEQUEL_RE.search(movie.metadata.title or ""):
                score -= SEQUEL_PEN

            # 10. Context weights
            if context_weights:
                cw = context_weights
                fw = cw.get("family_friendly", 0.0)
                if fw:
                    if "family" in movie_genres or "animation" in movie_genres:
                        score += fw * CW_FAM_BOOST
                    if movie_genres & {"horror", "thriller", "crime", "war"}:
                        score -= fw * CW_FAM_PEN

                rw = cw.get("romantic", 0.0)
                if rw and "romance" in movie_genres:
                    score += rw * CW_ROMANCE

                aw = cw.get("atmospheric", 0.0)
                if aw and movie_genres & {"thriller", "horror", "mystery"}:
                    score += aw * CW_ATMOS

                lhw = cw.get("lighthearted", 0.0)
                if lhw:
                    if "comedy" in movie_genres:
                        score += lhw * CW_LH_COMEDY
                    elif "drama" in movie_genres and not movie_genres & {"comedy", "romance"}:
                        score -= lhw * CW_LH_DRAMA_PEN

                tpw = max(cw.get("thought_provoking", 0.0), cw.get("cerebral", 0.0))
                if tpw and movie_genres & {"drama", "science fiction", "mystery"}:
                    score += tpw * CW_THOUGHT

                srw = cw.get("short_runtime", 0.0)
                if srw:
                    pacing = features.get("pacing", "moderate")
                    if pacing == "fast":
                        score += srw * CW_SHORT_BOOST
                    elif pacing == "slow":
                        score -= srw * CW_SLOW_PEN

                imw = cw.get("immersive", 0.0)
                if imw and movie_genres & {"adventure", "fantasy", "science fiction", "action"}:
                    score += imw * CW_IMMERSIVE

                uw = cw.get("uplifting", 0.0)
                if uw and movie_genres & {"comedy", "family", "animation"}:
                    score += uw * CW_UPLIFTING

            scored.append((score, movie))

        scored.sort(key=lambda x: x[0], reverse=True)

        num_requested = max(5, len(candidates) // 3)
        viable = [(s, m) for s, m in scored if s >= MIN_THRESH]
        if len(viable) >= num_requested:
            scored = viable
            mod.logger.info(
                f"Hard filter (score >= {MIN_THRESH}): "
                f"{len(candidates)} -> {len(scored)} candidates"
            )

        reranked = [movie for _, movie in scored]
        mod.logger.info(
            f"Content reranking: {len(candidates)} -> {len(reranked)} candidates "
            f"(mood={mood}, companion={companion}, language={language})"
        )
        return reranked

    cls._score_and_rerank = patched_score_and_rerank
    mod._AR_PARAMS = P


def _patch_critic(P: Dict[str, Any]):
    """Patch critic module-level thresholds."""
    from src.agents import critic as mod

    mod._QUALITY_FLOOR = P.get("critic.quality_floor", 5.5)
    mod._QUALITY_MIN_VOTES = int(P.get("critic.quality_min_votes", 200))
    mod._FAIL_THRESHOLD = int(P.get("critic.fail_threshold", 2))


def _patch_context_aware(P: Dict[str, Any]):
    """Patch ContextAwareAgent._calculate_context_weights."""
    from src.agents.context_aware import ContextAwareAgent

    _orig = ContextAwareAgent._calculate_context_weights

    def patched_weights(self, context_factors):
        weights = {}

        time_of_day = context_factors.get("time_of_day", "evening")
        if time_of_day == "morning":
            weights["lighthearted"] = P.get("context.morning_lighthearted", 0.8)
            weights["uplifting"] = P.get("context.morning_uplifting", 0.7)
            weights["short_runtime"] = P.get("context.morning_short_runtime", 0.6)
        elif time_of_day == "afternoon":
            weights["lighthearted"] = P.get("context.afternoon_lighthearted", 0.6)
            weights["moderate_length"] = P.get("context.afternoon_moderate_length", 0.7)
        elif time_of_day == "evening":
            weights["engaging"] = P.get("context.evening_engaging", 0.8)
            weights["quality"] = P.get("context.evening_quality", 0.9)
        else:
            weights["atmospheric"] = P.get("context.night_atmospheric", 0.7)
            weights["thought_provoking"] = P.get("context.night_thought_provoking", 0.6)

        companion = context_factors.get("companion", "alone")
        if companion == "family":
            weights["family_friendly"] = P.get("context.family_friendly", 1.0)
            weights["crowd_pleaser"] = P.get("context.family_crowd_pleaser", 0.8)
        elif companion == "friends":
            weights["social"] = P.get("context.friends_social", 0.9)
            weights["entertaining"] = P.get("context.friends_entertaining", 0.8)
        elif companion == "partner":
            weights["romantic"] = P.get("context.partner_romantic", 0.7)
            weights["quality"] = P.get("context.partner_quality", 0.8)
        else:
            weights["personal_interest"] = P.get("context.alone_personal_interest", 1.0)
            weights["exploration"] = P.get("context.alone_exploration", 0.6)

        if context_factors.get("is_weekend"):
            weights["longer_runtime_ok"] = P.get("context.weekend_longer_runtime", 0.7)
            weights["immersive"] = P.get("context.weekend_immersive", 0.8)
        else:
            weights["efficient_runtime"] = P.get("context.weekday_efficient_runtime", 0.7)
            weights["relaxing"] = P.get("context.weekday_relaxing", 0.6)

        mood = context_factors.get("mood")
        if mood:
            mood_weights = self._mood_to_weights(mood)
            weights.update(mood_weights)

        return weights

    ContextAwareAgent._calculate_context_weights = patched_weights


def _patch_retrieval(P: Dict[str, Any]):
    """Patch retrieval dynamic split and context blending."""
    from src.agents.graph import tools as mod

    _orig_split = mod._dynamic_split

    def patched_split(user_profile, context, has_embedding, k):
        if not has_embedding:
            return (0, k)

        total_ratings = getattr(user_profile, "total_ratings", 0) if user_profile else 0
        exploration_rate = 0.3
        if user_profile:
            prefs = getattr(user_profile, "preferences", None)
            if prefs:
                exploration_rate = getattr(prefs, "exploration_rate", 0.3)

        db_ratio = P.get("retrieval.base_db_ratio", 0.80)

        if total_ratings >= 100:
            db_ratio += P.get("retrieval.high_ratings_boost", 0.10)
        elif total_ratings >= 50:
            db_ratio += P.get("retrieval.mid_ratings_boost", 0.05)
        elif total_ratings < 15:
            db_ratio -= P.get("retrieval.low_ratings_penalty", 0.15)

        db_ratio -= (exploration_rate - 0.3) * P.get("retrieval.exploration_influence", 0.3)

        nl_context = context.get("natural_language_context") or context.get("query") or ""
        if nl_context and len(nl_context) > 10:
            db_ratio -= P.get("retrieval.nl_context_impact", 0.15)

        db_min = P.get("retrieval.db_ratio_min", 0.15)
        db_max = P.get("retrieval.db_ratio_max", 0.85)
        db_ratio = max(db_min, min(db_max, db_ratio))

        db_k = int(round(k * db_ratio))
        tmdb_k = k - db_k
        return (db_k, tmdb_k)

    mod._dynamic_split = patched_split


def _patch_supervisor(P: Dict[str, Any]):
    """Patch supervisor aggregation constants."""
    from src.agents import supervisor as mod

    mod._AR_NUM_RECS = int(P.get("supervisor.num_recommendations", 10))
    mod._AR_SCORE_DECAY = P.get("supervisor.score_decay_per_rank", 0.05)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_patched = False


def apply_patches():
    """Load PARAMS and monkey-patch all agents. Safe to call multiple times."""
    global _patched

    P = _load_params()

    _patch_critic(P)
    _patch_context_aware(P)
    _patch_retrieval(P)
    _patch_supervisor(P)
    _patch_content_intelligence(P)

    _patched = True
    return P


def reload_and_patch():
    """Force-reload params.py and re-apply all patches. Use between experiments."""
    global _patched
    _patched = False
    return apply_patches()
