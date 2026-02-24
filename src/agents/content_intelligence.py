"""Content Intelligence Agent - Deep movie content analysis."""

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List

import diskcache

from config.settings import get_settings
from src.agents.base_agent import BaseAgent
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Persistent cache for LLM-analyzed content features (themes, micro-genres)
_cache_path = "/tmp/content_features" if os.environ.get("LAMBDA_TASK_ROOT") else str(Path(get_settings().data_dir) / "cache" / "content_features")
_content_cache = diskcache.Cache(
    _cache_path,
    size_limit=100 * 1024 * 1024,  # 100MB
)


class ContentIntelligenceAgent(BaseAgent):
    """Agent that performs deep content analysis of movies."""

    def __init__(self):
        """Initialize Content Intelligence agent."""
        super().__init__(
            name="Content Intelligence",
            description="Deep movie content analysis and micro-genre extraction",
            temperature=0.5,  # Moderate creativity for content analysis
            use_fast_model=False,  # Use main model for better analysis
        )

    # Mood-to-tone mapping: which tones fit which moods (16 moods)
    MOOD_TONE_AFFINITY = {
        # ── Original 8 ───────────────────────────────────────────────────────
        "happy":       {"light": 1.0, "whimsical": 0.8, "balanced": 0.4, "intense": 0.2, "serious": 0.1, "dark": 0.0},
        "sad":         {"serious": 0.8, "balanced": 0.6, "light": 0.5, "whimsical": 0.4, "dark": 0.3, "intense": 0.2},
        "stressed":    {"light": 0.9, "whimsical": 0.8, "balanced": 0.5, "serious": 0.2, "intense": 0.0, "dark": 0.0},
        "bored":       {"intense": 0.9, "dark": 0.7, "balanced": 0.5, "serious": 0.4, "light": 0.3, "whimsical": 0.3},
        "thoughtful":  {"serious": 0.9, "dark": 0.7, "balanced": 0.6, "intense": 0.4, "light": 0.2, "whimsical": 0.2},
        "energetic":   {"intense": 0.9, "light": 0.6, "balanced": 0.5, "dark": 0.4, "whimsical": 0.3, "serious": 0.2},
        "nostalgic":   {"balanced": 0.8, "light": 0.7, "serious": 0.6, "whimsical": 0.6, "dark": 0.3, "intense": 0.3},
        "adventurous": {"intense": 0.8, "balanced": 0.7, "dark": 0.6, "whimsical": 0.5, "light": 0.4, "serious": 0.3},
        # ── New 8 ────────────────────────────────────────────────────────────
        "romantic":    {"light": 0.9, "balanced": 0.6, "whimsical": 0.4, "serious": 0.5, "dark": 0.1, "intense": 0.1},
        "anxious":     {"light": 0.8, "whimsical": 0.7, "balanced": 0.4, "serious": 0.2, "intense": 0.0, "dark": 0.0},
        "excited":     {"intense": 0.9, "light": 0.7, "balanced": 0.5, "whimsical": 0.4, "dark": 0.3, "serious": 0.2},
        "lonely":      {"serious": 0.7, "light": 0.6, "balanced": 0.6, "dark": 0.4, "whimsical": 0.3, "intense": 0.2},
        "inspired":    {"serious": 0.9, "intense": 0.6, "balanced": 0.5, "dark": 0.3, "light": 0.2, "whimsical": 0.2},
        "curious":     {"serious": 0.8, "dark": 0.5, "balanced": 0.6, "intense": 0.4, "light": 0.3, "whimsical": 0.3},
        "relaxed":     {"light": 0.8, "balanced": 0.7, "whimsical": 0.6, "serious": 0.3, "dark": 0.1, "intense": 0.0},
        "melancholic": {"dark": 0.6, "serious": 0.8, "balanced": 0.5, "light": 0.3, "intense": 0.3, "whimsical": 0.1},
    }

    # Genres that are NOT family-friendly
    NON_FAMILY_GENRES = {"horror", "thriller", "crime", "war"}

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze movie content features, then score and rerank candidates.

        Args:
            state: Current state with candidate_movies or movie data.

        Returns:
            Updated state with content_features and reranked candidate_movies.
        """
        self.log_processing("Starting content analysis")

        candidate_movies = state.get("candidate_movies", [])

        if not candidate_movies:
            self.log_processing("No candidate movies yet, skipping content analysis")
            state["content_features"] = {}
            return state

        # Run cheap heuristic analysis (tone/pacing/complexity) for ALL candidates,
        # and deep LLM analysis (themes/micro-genres) for top 10 only.
        content_features = {}

        for i, movie in enumerate(candidate_movies):
            movie_id = str(movie.metadata.tmdb_id)
            if i < 10:
                features = self._analyze_movie_content(movie)
            else:
                features = self._analyze_movie_content_fast(movie)
            content_features[movie_id] = features

        state["content_features"] = content_features

        # Score and rerank candidates using preferences + context
        user_profile = state.get("user_profile")
        context_factors = state.get("context_factors", {})
        context = state.get("context", {})

        context_weights = state.get("context_weights", {})
        scored_movies = self._score_and_rerank(
            candidate_movies, content_features, user_profile, context_factors, context,
            context_weights,
        )

        # LLM reranking: single Groq call to reorder the top-20 candidates.
        # Only runs for non-cold-start users with a Groq API key configured.
        if self._should_llm_rerank(user_profile):
            scored_movies = self._llm_rerank_top20(
                scored_movies, user_profile, context_factors
            )

        original_count = len(candidate_movies)
        state["candidate_movies"] = scored_movies
        state["processing_steps"] = state.get("processing_steps", []) + [
            f"Content Intelligence: Analyzed {len(content_features)} movies, "
            f"reranked to {len(scored_movies)} (from {original_count})"
        ]

        return state

    def _should_llm_rerank(self, user_profile) -> bool:
        """Return True when a Groq-powered reranking pass is worthwhile."""
        try:
            settings = get_settings()
            return (
                bool(settings.groq_api_key)
                and user_profile is not None
                and not getattr(user_profile, "is_cold_start", True)
                and getattr(user_profile, "total_ratings", 0) >= 5
            )
        except Exception:
            return False

    def _llm_rerank_top20(self, candidates: List, user_profile, context_factors: Dict) -> List:
        """Rerank the top-20 candidates with a single batched Groq prompt.

        Sends one call with all 20 movies; the LLM returns a score 0-10 per
        movie.  Reranked list replaces the top-20; the rest are appended as-is.
        Falls back silently to the original order on any error.
        """
        import re as _re

        if not candidates or len(candidates) < 5:
            return candidates

        top = candidates[:20]
        rest = candidates[20:]

        # Compact profile summary
        prefs = getattr(user_profile, "preferences", None)
        fav_genres = ", ".join((prefs.favorite_genres or [])[:4]) if prefs else ""
        fav_dirs = ", ".join((prefs.favorite_directors or [])[:2]) if prefs else ""
        fav_langs = ", ".join((prefs.preferred_languages or [])[:2]) if prefs else ""
        mood = context_factors.get("mood", "")
        companion = context_factors.get("companion", "alone")
        time_of_day = context_factors.get("time_of_day", "")
        is_weekend = context_factors.get("is_weekend", False)
        nl_ctx = (context_factors.get("natural_language_context") or "")[:120]

        lines = []
        for i, m in enumerate(top):
            md = m.metadata
            genres_str = ", ".join((md.genres or [])[:3])
            lines.append(
                f"{i}: \"{md.title}\" ({md.year or '?'}) "
                f"[{genres_str}] dir:{md.director or '?'} "
                f"lang:{md.original_language or '?'} "
                f"rating:{md.vote_average or '?'}/10"
            )

        ctx_line = (
            f"mood={mood or 'none'}, watching_with={companion}, "
            f"time={time_of_day}, {'weekend' if is_weekend else 'weekday'}"
        )
        if nl_ctx:
            ctx_line += f", request='{nl_ctx}'"

        prompt = (
            f"Rate each movie 0-10 for fit with this user.\n\n"
            f"User: loves [{fav_genres}], directors [{fav_dirs}], "
            f"preferred languages [{fav_langs}].\n"
            f"Context: {ctx_line}.\n\n"
            f"Movies:\n" + "\n".join(lines) +
            "\n\nReply ONLY with lines like \"0:8.5\" (index:score). No text."
        )

        try:
            response = self.generate_response(
                prompt=prompt,
                system_prompt="Score movies for recommendation fit. Output INDEX:SCORE pairs only.",
                max_tokens=220,
            )
            scores: Dict[int, float] = {}
            for line in response.strip().splitlines():
                m = _re.match(r"(\d+)\s*[:=]\s*(\d+\.?\d*)", line.strip())
                if m:
                    idx, val = int(m.group(1)), float(m.group(2))
                    if 0 <= idx < len(top):
                        scores[idx] = val / 10.0

            # Only reorder if LLM provided scores for ≥ half the candidates
            if len(scores) >= len(top) // 2:
                reordered = sorted(range(len(top)), key=lambda i: scores.get(i, 0.5), reverse=True)
                logger.info(f"LLM reranking: scored {len(scores)}/{len(top)} candidates")
                return [top[i] for i in reordered] + rest

        except Exception as e:
            logger.warning(f"LLM reranking failed (using heuristic order): {e}")

        return candidates

    def _analyze_movie_content(self, movie) -> Dict[str, Any]:
        """
        Perform deep content analysis on a single movie.

        Args:
            movie: Movie object.

        Returns:
            Content features dictionary.
        """
        metadata = movie.metadata

        # Extract basic features
        features = {
            "title": metadata.title,
            "genres": metadata.genres,
            "themes": self._extract_themes(metadata),
            "micro_genres": self._extract_micro_genres(metadata),
            "tone": self._analyze_tone(metadata),
            "pacing": self._estimate_pacing(metadata),
            "complexity": self._estimate_complexity(metadata),
        }

        return features

    def _analyze_movie_content_fast(self, movie) -> Dict[str, Any]:
        """
        Fast content analysis using only heuristics (no LLM calls).

        Args:
            movie: Movie object.

        Returns:
            Content features dictionary.
        """
        metadata = movie.metadata

        features = {
            "title": metadata.title,
            "genres": metadata.genres,
            "themes": self._genre_to_themes(metadata.genres),
            "micro_genres": self._combine_genres(metadata.genres),
            "tone": self._analyze_tone(metadata),
            "pacing": self._estimate_pacing(metadata),
            "complexity": self._estimate_complexity(metadata),
        }

        return features

    def _score_and_rerank(
        self,
        candidates: List,
        content_features: Dict[str, Dict],
        user_profile,
        context_factors: Dict[str, Any],
        context: Dict[str, Any],
        context_weights: Dict[str, float] = None,
    ) -> List:
        """
        Score candidates by relevance and filter out mismatches.

        Args:
            candidates: List of Movie objects.
            content_features: Analyzed features per movie_id.
            user_profile: User profile (may be None for cold-start).
            context_factors: Detected context (mood, companion, etc.).
            context: Raw user context (language, year_min, year_max, NL context).

        Returns:
            Reranked and filtered list of Movie objects.
        """
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

        # Get user preferences
        fav_genres = set()
        disliked_genres = set()
        fav_directors = set()
        fav_actors = set()
        preferred_languages: list = []
        if user_profile and hasattr(user_profile, "preferences"):
            fav_genres = {g.lower() for g in (user_profile.preferences.favorite_genres or [])}
            disliked_genres = {g.lower() for g in (user_profile.preferences.disliked_genres or [])}
            fav_directors = {d.lower() for d in (user_profile.preferences.favorite_directors or [])}
            fav_actors = {a.lower() for a in (user_profile.preferences.favorite_actors or [])}
            preferred_languages = list(user_profile.preferences.preferred_languages or [])

        # NL context keywords for matching against themes/micro-genres
        nl_keywords = [w for w in nl_context.split() if len(w) > 2] if nl_context else []

        scored = []
        for movie in candidates:
            movie_id = str(movie.metadata.tmdb_id)
            features = content_features.get(movie_id, {})
            movie_genres = {g.lower() for g in (features.get("genres") or movie.metadata.genres or [])}
            tone = features.get("tone", "balanced")

            # --- Hard filters: remove clearly wrong movies ---

            # Year filter enforcement (catch anything that slipped through DB filter)
            movie_year = movie.metadata.year
            if year_min and movie_year and movie_year < int(year_min):
                continue
            if year_max and movie_year and movie_year > int(year_max):
                continue

            # Language post-filter
            if language and movie.metadata.original_language:
                if movie.metadata.original_language != language:
                    continue

            # --- Soft scoring ---
            score = 0.5  # Base score

            # 1. Genre match with user preferences (±0.25)
            if fav_genres:
                genre_overlap = len(movie_genres & fav_genres)
                score += min(genre_overlap * 0.1, 0.25)
            if disliked_genres and (movie_genres & disliked_genres):
                score -= 0.2

            # 2. Tone-mood affinity (±0.15)
            if mood and mood.lower() in self.MOOD_TONE_AFFINITY:
                affinity = self.MOOD_TONE_AFFINITY[mood.lower()].get(tone, 0.4)
                score += (affinity - 0.4) * 0.3  # Range: -0.12 to +0.18

            # 3. Companion appropriateness (±0.2)
            if companion == "family":
                if movie_genres & self.NON_FAMILY_GENRES:
                    score -= 0.25  # Penalize non-family content
                if "family" in movie_genres or "animation" in movie_genres:
                    score += 0.15
            elif companion == "partner":
                if "romance" in movie_genres:
                    score += 0.1

            # 4. Director / actor affinity (±0.20)
            movie_director = (movie.metadata.director or "").lower()
            if fav_directors and movie_director and movie_director in fav_directors:
                score += 0.15
            movie_cast = {a.lower() for a in (movie.metadata.cast or [])}
            if fav_actors:
                actor_hits = len(movie_cast & fav_actors)
                score += min(actor_hits * 0.07, 0.14)

            # 5. Language preference (±0.12)
            # Only applies when no explicit language filter was set in context.
            # Boost movies in languages the user watches frequently; penalise
            # movies in languages they have never rated.
            if preferred_languages and not language:
                movie_lang = movie.metadata.original_language or ""
                if movie_lang and movie_lang in preferred_languages:
                    rank = preferred_languages.index(movie_lang)
                    score += max(0.12 - rank * 0.04, 0.04)  # 1st lang +0.12, 2nd +0.08, 3rd +0.04
                elif movie_lang and movie_lang not in preferred_languages:
                    score -= 0.06  # Soft penalty for completely foreign-to-user languages

            # 7. Natural language context keyword matching (±0.15)
            if nl_keywords:
                themes = [t.lower() for t in (features.get("themes") or [])]
                micro_genres = [mg.lower() for mg in (features.get("micro_genres") or [])]
                overview = (movie.metadata.overview or "").lower()
                searchable = " ".join(themes + micro_genres) + " " + " ".join(movie_genres) + " " + overview

                keyword_hits = sum(1 for kw in nl_keywords if kw in searchable)
                score += min(keyword_hits * 0.05, 0.15)

            # 8. Recency / nostalgia alignment (±0.10)
            # Uses nostalgia_tendency from profile: 0=prefers new films, 1=prefers classics
            if user_profile and hasattr(user_profile, "preferences"):
                nostalgia = getattr(user_profile.preferences, "nostalgia_tendency", 0.5)
                movie_year = movie.metadata.year or 2000
                movie_age = min(max((2025 - movie_year) / 50.0, 0.0), 1.0)
                alignment = 1.0 - abs(nostalgia - movie_age)
                score += (alignment - 0.5) * 0.20  # Range: -0.10 to +0.10

            # 9. Sequel penalty: if title looks like a sequel and user hasn't
            # established a track record with this franchise, soft-penalise.
            import re as _re
            _SEQUEL_RE = _re.compile(
                r'\b(2|3|4|5|II|III|IV|V|VI|Part\s+2|Chapter\s+2|Returns|'
                r'Rises|Reloaded|Revolutions|Resurrection|Reborn|Unleashed)\b',
                _re.IGNORECASE,
            )
            if _SEQUEL_RE.search(movie.metadata.title or ""):
                score -= 0.08

            # 10. Context weights (time_of_day / companion / weekend signals)
            if context_weights:
                cw = context_weights

                # family_friendly → boost family/animation, penalise adult genres
                fw = cw.get("family_friendly", 0.0)
                if fw:
                    if "family" in movie_genres or "animation" in movie_genres:
                        score += fw * 0.20
                    if movie_genres & {"horror", "thriller", "crime", "war"}:
                        score -= fw * 0.30

                # romantic → boost romance
                rw = cw.get("romantic", 0.0)
                if rw and "romance" in movie_genres:
                    score += rw * 0.12

                # atmospheric (night) → boost thriller/horror/mystery
                aw = cw.get("atmospheric", 0.0)
                if aw and movie_genres & {"thriller", "horror", "mystery"}:
                    score += aw * 0.12

                # lighthearted (morning) → boost comedy, penalise heavy drama
                lhw = cw.get("lighthearted", 0.0)
                if lhw:
                    if "comedy" in movie_genres:
                        score += lhw * 0.15
                    elif "drama" in movie_genres and not movie_genres & {"comedy", "romance"}:
                        score -= lhw * 0.10

                # thought_provoking / cerebral → boost drama/sci-fi/mystery
                tpw = max(cw.get("thought_provoking", 0.0), cw.get("cerebral", 0.0))
                if tpw and movie_genres & {"drama", "science fiction", "mystery"}:
                    score += tpw * 0.12

                # short_runtime preference → use pacing as proxy
                srw = cw.get("short_runtime", 0.0)
                if srw:
                    pacing = features.get("pacing", "moderate")
                    if pacing == "fast":
                        score += srw * 0.08
                    elif pacing == "slow":
                        score -= srw * 0.05

                # immersive (weekend) → boost epic/adventure genres
                imw = cw.get("immersive", 0.0)
                if imw and movie_genres & {"adventure", "fantasy", "science fiction", "action"}:
                    score += imw * 0.08

                # uplifting → boost feel-good genres
                uw = cw.get("uplifting", 0.0)
                if uw and movie_genres & {"comedy", "family", "animation"}:
                    score += uw * 0.10

            scored.append((score, movie))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Hard-filter: drop definite mismatches (score < 0.35) but keep at
        # least min_keep candidates so we never starve the downstream pipeline.
        num_requested = max(5, len(candidates) // 3)
        MIN_SCORE_THRESHOLD = 0.35
        viable = [(s, m) for s, m in scored if s >= MIN_SCORE_THRESHOLD]
        if len(viable) >= num_requested:
            scored = viable
            logger.info(
                f"Hard filter (score ≥ {MIN_SCORE_THRESHOLD}): "
                f"{len(candidates)} → {len(scored)} candidates"
            )

        reranked = [movie for _, movie in scored]

        logger.info(
            f"Content reranking: {len(candidates)} → {len(reranked)} candidates "
            f"(mood={mood}, companion={companion}, language={language})"
        )

        return reranked

    def _content_cache_key(self, metadata, suffix: str) -> str:
        """Build a stable cache key from movie ID + overview hash."""
        overview_hash = hashlib.md5((metadata.overview or "").encode()).hexdigest()[:8]
        return f"content:{metadata.tmdb_id}:{overview_hash}:{suffix}"

    def _extract_themes(self, metadata) -> List[str]:
        """Extract thematic elements from movie (cached)."""
        cache_key = self._content_cache_key(metadata, "themes")
        cached = _content_cache.get(cache_key)
        if cached is not None:
            return cached

        themes = []

        if metadata.overview:
            prompt = f"""Analyze this movie plot and extract 3-5 core themes.

Movie: {metadata.title}
Plot: {metadata.overview}

Themes should be single words or short phrases like: "redemption", "coming-of-age", "revenge", "family bonds", etc.

Return only the themes as a comma-separated list."""

            try:
                response = self.generate_response(
                    prompt=prompt,
                    system_prompt="You are a film analyst expert at identifying themes.",
                    max_tokens=100,
                )
                themes = [t.strip() for t in response.split(",") if t.strip()]
            except Exception as e:
                logger.warning(f"Failed to extract themes via LLM: {e}")
                themes = self._genre_to_themes(metadata.genres)

        result = themes[:5]
        _content_cache.set(cache_key, result, expire=7 * 86400)  # 7 days
        return result

    def _extract_micro_genres(self, metadata) -> List[str]:
        """Extract micro-genres (cached)."""
        cache_key = self._content_cache_key(metadata, "micro_genres")
        cached = _content_cache.get(cache_key)
        if cached is not None:
            return cached

        micro_genres = []

        if metadata.overview and metadata.genres:
            prompt = f"""Create 2-3 specific micro-genres for this movie.

Movie: {metadata.title}
Genres: {', '.join(metadata.genres)}
Plot: {metadata.overview[:300]}

Micro-genres should be creative combinations like:
- "heist-with-twist"
- "slow-burn-thriller"
- "female-led-action"
- "cerebral-sci-fi"
- "dark-comedy-crime"

Return only the micro-genres as a comma-separated list."""

            try:
                response = self.generate_response(
                    prompt=prompt,
                    system_prompt="You are a creative film cataloger.",
                    max_tokens=80,
                )
                micro_genres = [mg.strip() for mg in response.split(",") if mg.strip()]
            except Exception as e:
                logger.warning(f"Failed to extract micro-genres via LLM: {e}")
                micro_genres = self._combine_genres(metadata.genres)

        result = micro_genres[:3]
        _content_cache.set(cache_key, result, expire=7 * 86400)  # 7 days
        return result

    def _analyze_tone(self, metadata) -> str:
        """
        Analyze overall tone using weighted multi-genre scoring.

        Returns the tone with the highest cumulative weight across all genres,
        preventing first-genre bias for multi-genre movies.

        Args:
            metadata: Movie metadata.

        Returns:
            Tone description (light, dark, whimsical, serious, intense, balanced).
        """
        genres = {g.lower() for g in (metadata.genres or [])}

        # Per-genre tone weights; a genre can contribute to multiple tones
        tone_weights: Dict[str, float] = {
            "light": 0.0, "dark": 0.0, "whimsical": 0.0,
            "serious": 0.0, "intense": 0.0, "balanced": 0.0,
        }

        _GENRE_TONE: Dict[str, Dict[str, float]] = {
            "comedy":           {"light": 1.0, "whimsical": 0.3},
            "horror":           {"dark": 1.0, "intense": 0.5},
            "thriller":         {"dark": 0.8, "intense": 0.9},
            "drama":            {"serious": 1.0, "balanced": 0.3},
            "animation":        {"whimsical": 1.0, "light": 0.4},
            "family":           {"whimsical": 0.8, "light": 0.6},
            "action":           {"intense": 1.0, "balanced": 0.2},
            "adventure":        {"intense": 0.6, "balanced": 0.5},
            "romance":          {"light": 0.5, "serious": 0.4, "balanced": 0.4},
            "science fiction":  {"serious": 0.5, "intense": 0.4, "balanced": 0.4},
            "fantasy":          {"whimsical": 0.7, "balanced": 0.4},
            "mystery":          {"dark": 0.6, "serious": 0.5},
            "crime":            {"dark": 0.7, "intense": 0.5},
            "war":              {"dark": 0.8, "serious": 0.7, "intense": 0.5},
            "documentary":      {"serious": 0.9, "balanced": 0.3},
            "history":          {"serious": 0.7, "balanced": 0.4},
            "biography":        {"serious": 0.8, "balanced": 0.3},
            "music":            {"light": 0.4, "balanced": 0.5},
            "sport":            {"intense": 0.5, "balanced": 0.5},
            "western":          {"intense": 0.5, "serious": 0.4, "balanced": 0.3},
        }

        for genre in genres:
            for tone, weight in _GENRE_TONE.get(genre, {}).items():
                tone_weights[tone] += weight

        # If no genre matched, return balanced
        if all(v == 0.0 for v in tone_weights.values()):
            return "balanced"

        return max(tone_weights, key=lambda t: tone_weights[t])

    def _estimate_pacing(self, metadata) -> str:
        """
        Estimate pacing using weighted multi-genre scoring.

        Args:
            metadata: Movie metadata.

        Returns:
            Pacing category (fast, moderate, slow).
        """
        genres = {g.lower() for g in (metadata.genres or [])}

        pacing_weights = {"fast": 0.0, "moderate": 0.0, "slow": 0.0}

        _GENRE_PACING: Dict[str, Dict[str, float]] = {
            "action":           {"fast": 1.0},
            "thriller":         {"fast": 0.8, "moderate": 0.2},
            "horror":           {"fast": 0.6, "moderate": 0.4},
            "adventure":        {"fast": 0.6, "moderate": 0.4},
            "comedy":           {"moderate": 0.7, "fast": 0.3},
            "animation":        {"moderate": 0.6, "fast": 0.3},
            "drama":            {"slow": 0.7, "moderate": 0.3},
            "romance":          {"slow": 0.5, "moderate": 0.5},
            "documentary":      {"slow": 0.8, "moderate": 0.2},
            "history":          {"slow": 0.7, "moderate": 0.3},
            "biography":        {"slow": 0.6, "moderate": 0.4},
            "mystery":          {"moderate": 0.6, "slow": 0.4},
            "science fiction":  {"moderate": 0.5, "fast": 0.3, "slow": 0.2},
            "fantasy":          {"moderate": 0.6, "slow": 0.3},
            "crime":            {"moderate": 0.5, "fast": 0.3, "slow": 0.2},
        }

        for genre in genres:
            for pace, weight in _GENRE_PACING.get(genre, {}).items():
                pacing_weights[pace] += weight

        if all(v == 0.0 for v in pacing_weights.values()):
            return "moderate"

        return max(pacing_weights, key=lambda p: pacing_weights[p])

    def _estimate_complexity(self, metadata) -> str:
        """
        Estimate narrative complexity using weighted multi-genre scoring.

        Args:
            metadata: Movie metadata.

        Returns:
            Complexity level (simple, moderate, complex).
        """
        genres = {g.lower() for g in (metadata.genres or [])}

        complexity_weights = {"simple": 0.0, "moderate": 0.0, "complex": 0.0}

        _GENRE_COMPLEXITY: Dict[str, Dict[str, float]] = {
            "mystery":          {"complex": 1.0},
            "thriller":         {"complex": 0.8, "moderate": 0.2},
            "science fiction":  {"complex": 0.7, "moderate": 0.3},
            "crime":            {"complex": 0.5, "moderate": 0.5},
            "drama":            {"moderate": 0.7, "complex": 0.2},
            "history":          {"moderate": 0.6, "complex": 0.3},
            "war":              {"moderate": 0.6, "complex": 0.3},
            "biography":        {"moderate": 0.6, "complex": 0.2},
            "romance":          {"moderate": 0.6, "simple": 0.3},
            "action":           {"moderate": 0.5, "simple": 0.4},
            "adventure":        {"moderate": 0.5, "simple": 0.4},
            "comedy":           {"simple": 0.7, "moderate": 0.3},
            "family":           {"simple": 0.8},
            "animation":        {"simple": 0.6, "moderate": 0.3},
            "horror":           {"moderate": 0.5, "simple": 0.3},
            "documentary":      {"complex": 0.4, "moderate": 0.5},
            "fantasy":          {"moderate": 0.5, "complex": 0.3},
        }

        for genre in genres:
            for level, weight in _GENRE_COMPLEXITY.get(genre, {}).items():
                complexity_weights[level] += weight

        if all(v == 0.0 for v in complexity_weights.values()):
            return "moderate"

        return max(complexity_weights, key=lambda c: complexity_weights[c])

    def _genre_to_themes(self, genres: List[str]) -> List[str]:
        """Map genres to common themes (fallback for fast analysis)."""
        theme_map = {
            "Action":           ["heroism", "conflict", "survival"],
            "Adventure":        ["exploration", "discovery", "courage"],
            "Drama":            ["human-nature", "relationships", "struggle"],
            "Comedy":           ["humor", "satire", "absurdity"],
            "Horror":           ["fear", "survival", "the-unknown"],
            "Romance":          ["love", "relationships", "heartbreak"],
            "Science Fiction":  ["technology", "future", "identity"],
            "Thriller":         ["suspense", "deception", "danger"],
            "Mystery":          ["secrets", "investigation", "truth"],
            "Crime":            ["justice", "corruption", "morality"],
            "Animation":        ["imagination", "growth", "wonder"],
            "Family":           ["togetherness", "coming-of-age", "values"],
            "Fantasy":          ["magic", "good-vs-evil", "destiny"],
            "History":          ["legacy", "power", "sacrifice"],
            "War":              ["honor", "tragedy", "brotherhood"],
            "Biography":        ["ambition", "perseverance", "legacy"],
            "Documentary":      ["truth", "society", "awareness"],
            "Music":            ["passion", "identity", "expression"],
            "Sport":            ["determination", "teamwork", "triumph"],
        }

        themes = []
        for genre in genres:
            themes.extend(theme_map.get(genre, []))

        return list(dict.fromkeys(themes))  # deduplicate preserving order

    def _combine_genres(self, genres: List[str]) -> List[str]:
        """Combine genres into micro-genres (fallback)."""
        if len(genres) >= 2:
            return [f"{genres[0].lower()}-{genres[1].lower()}"]
        elif len(genres) == 1:
            return [f"{genres[0].lower()}-film"]
        return []


def get_content_intelligence_agent() -> ContentIntelligenceAgent:
    """Get configured Content Intelligence agent."""
    return ContentIntelligenceAgent()
