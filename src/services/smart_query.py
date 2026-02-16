"""Smart TMDB Query Strategy — translates user preferences into targeted discover API queries."""

from typing import Any, Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

TMDB_GENRE_IDS = {
    "Action": 28,
    "Adventure": 12,
    "Animation": 16,
    "Comedy": 35,
    "Crime": 80,
    "Documentary": 99,
    "Drama": 18,
    "Family": 10751,
    "Fantasy": 14,
    "History": 36,
    "Horror": 27,
    "Music": 10402,
    "Mystery": 9648,
    "Romance": 10749,
    "Science Fiction": 878,
    "TV Movie": 10770,
    "Thriller": 53,
    "War": 10752,
    "Western": 37,
}

# Reverse lookup: id -> name
GENRE_ID_TO_NAME = {v: k for k, v in TMDB_GENRE_IDS.items()}

MOOD_GENRE_MAP = {
    # ── Original 8 ───────────────────────────────────────────────────────────
    "happy":       [35, 10751, 16],      # Comedy, Family, Animation
    "sad":         [18, 10749],          # Drama, Romance
    "stressed":    [35, 16, 10402],      # Comedy, Animation, Music
    "bored":       [28, 878, 53],        # Action, Sci-Fi, Thriller
    "thoughtful":  [18, 9648, 36],       # Drama, Mystery, History
    "energetic":   [28, 12, 878],        # Action, Adventure, Sci-Fi
    "nostalgic":   [18, 10749, 35],      # Drama, Romance, Comedy
    "adventurous": [12, 14, 878],        # Adventure, Fantasy, Sci-Fi
    # ── New 8 ────────────────────────────────────────────────────────────────
    "romantic":    [10749, 18, 35],      # Romance, Drama, Comedy
    "anxious":     [35, 16, 10751],      # Comedy, Animation, Family (escapism)
    "excited":     [28, 12, 878],        # Action, Adventure, Sci-Fi
    "lonely":      [18, 10749, 35],      # Drama, Romance, Comedy
    "inspired":    [36, 99, 10402],      # History, Documentary, Music
    "curious":     [9648, 99, 878],      # Mystery, Documentary, Sci-Fi
    "relaxed":     [10402, 16, 35],      # Music, Animation, Comedy
    "melancholic": [18, 10749, 9648],    # Drama, Romance, Mystery
}

ALL_GENRE_IDS = list(TMDB_GENRE_IDS.values())


class SmartQueryStrategy:
    """Builds targeted TMDB discover queries from user profile + context."""

    def build_queries(
        self,
        user_profile: Optional[Any] = None,
        context: Optional[Dict] = None,
        context_factors: Optional[Dict] = None,
        k: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return a list of TMDB discover param dicts, each targeting a different angle.

        Total results across all queries should yield ~k candidates.

        Strategy allocation:
        1. GENRE-BASED     (40%) — user's top favourite genres
        2. EXPLORATION      (15%) — genres user hasn't tried
        3. MOOD-MATCHED     (15%) — if mood present in context
        4. DECADE-BASED     (15%) — user's preferred decades
        5. LANGUAGE-SPECIFIC (15%) — if language set
        """
        context = context or {}
        context_factors = context_factors or {}
        queries: List[Dict] = []

        # Gather user taste signals
        top_genres = self._get_top_genres(user_profile)
        explored_genre_ids = {TMDB_GENRE_IDS.get(g, 0) for g in top_genres}
        unexplored = [gid for gid in ALL_GENRE_IDS if gid not in explored_genre_ids and gid != 0]

        mood = context_factors.get("mood") or context.get("mood")
        language = context.get("language")
        year_min = context.get("year_min")
        year_max = context.get("year_max")
        preferred_decades = self._get_preferred_decades(user_profile)

        # ---- 1. GENRE-BASED (40% of k) ----
        genre_k = max(int(k * 0.40), 5)
        if top_genres:
            # Top 2 genres, split evenly
            for genre_name in top_genres[:2]:
                genre_id = TMDB_GENRE_IDS.get(genre_name)
                if genre_id:
                    per_genre = genre_k // min(len(top_genres[:2]), 2)
                    q = self._genre_query(
                        genre_ids=[genre_id],
                        sort_by="vote_average.desc",
                        pages=max(1, per_genre // 20),
                        year_min=year_min,
                        year_max=year_max,
                    )
                    q["_strategy"] = "genre_based"
                    q["_target_k"] = per_genre
                    queries.append(self._apply_context_filters(q, context))
        else:
            # No user data — popular movies
            q = self._genre_query(
                genre_ids=[],
                sort_by="popularity.desc",
                pages=max(1, genre_k // 20),
                year_min=year_min,
                year_max=year_max,
            )
            q["_strategy"] = "popular_fallback"
            q["_target_k"] = genre_k
            queries.append(self._apply_context_filters(q, context))

        # ---- 2. EXPLORATION (15% of k) ----
        explore_k = max(int(k * 0.15), 3)
        if unexplored:
            import random
            explore_genres = random.sample(unexplored, min(2, len(unexplored)))
            q = self._genre_query(
                genre_ids=explore_genres,
                sort_by="popularity.desc",
                pages=1,
                year_min=year_min,
                year_max=year_max,
            )
            q["_strategy"] = "exploration"
            q["_target_k"] = explore_k
            queries.append(self._apply_context_filters(q, context))

        # ---- 3. MOOD-MATCHED (15% of k) ----
        mood_k = max(int(k * 0.15), 3)
        if mood and mood.lower() in MOOD_GENRE_MAP:
            mood_genres = MOOD_GENRE_MAP[mood.lower()]
            q = self._genre_query(
                genre_ids=mood_genres[:2],
                sort_by="popularity.desc",
                pages=1,
                year_min=year_min,
                year_max=year_max,
            )
            q["_strategy"] = "mood_matched"
            q["_target_k"] = mood_k
            queries.append(self._apply_context_filters(q, context))

        # ---- 4. DECADE-BASED (15% of k) ----
        decade_k = max(int(k * 0.15), 3)
        if preferred_decades:
            decade = preferred_decades[0]  # top decade
            q = self._genre_query(
                genre_ids=[],
                sort_by="vote_average.desc",
                pages=1,
                year_min=decade,
                year_max=decade + 9,
            )
            q["vote_count.gte"] = 200  # quality filter for decade queries
            q["_strategy"] = "decade_based"
            q["_target_k"] = decade_k
            queries.append(self._apply_context_filters(q, context))

        # ---- 5. LANGUAGE-SPECIFIC (15% of k) ----
        lang_k = max(int(k * 0.15), 3)
        if language:
            q = {
                "sort_by": "popularity.desc",
                "with_original_language": language,
                "vote_count.gte": 50,
                "page": 1,
                "_strategy": "language_specific",
                "_target_k": lang_k,
            }
            if year_min:
                q["primary_release_date.gte"] = f"{year_min}-01-01"
            if year_max:
                q["primary_release_date.lte"] = f"{year_max}-12-31"
            queries.append(q)

        logger.info(
            f"SmartQuery: built {len(queries)} discover queries "
            f"(genres={top_genres[:3]}, mood={mood}, lang={language})"
        )
        return queries

    # ---------------------------------------------------------------- helpers
    def _genre_query(
        self,
        genre_ids: List[int],
        sort_by: str,
        pages: int,
        year_min: Optional[int],
        year_max: Optional[int],
    ) -> Dict[str, Any]:
        """Build a single discover query dict."""
        params: Dict[str, Any] = {
            "sort_by": sort_by,
            "vote_count.gte": 50,
            "page": 1,
        }
        if genre_ids:
            params["with_genres"] = ",".join(str(gid) for gid in genre_ids)
        if year_min:
            params["primary_release_date.gte"] = f"{year_min}-01-01"
        if year_max:
            params["primary_release_date.lte"] = f"{year_max}-12-31"
        params["_pages"] = max(1, min(pages, 3))  # cap at 3 pages
        return params

    def _apply_context_filters(self, params: Dict, context: Dict) -> Dict:
        """Add year, language, region filters from context to any query."""
        if context.get("language") and "with_original_language" not in params:
            params["with_original_language"] = context["language"]
        if context.get("region"):
            params["region"] = context["region"]
        return params

    def _get_top_genres(self, user_profile) -> List[str]:
        """Extract top genre names from user profile."""
        if not user_profile:
            return []
        # UserProfile.preferences.favorite_genres: List[str]
        prefs = getattr(user_profile, "preferences", None)
        if prefs:
            fav = getattr(prefs, "favorite_genres", None)
            if fav and isinstance(fav, list):
                return fav[:5]
        return []

    def _get_preferred_decades(self, user_profile) -> List[int]:
        """Extract preferred decades from user profile."""
        if not user_profile:
            return []
        # UserProfile.preferences.preferred_decades: List[int]
        prefs = getattr(user_profile, "preferences", None)
        if prefs:
            decades = getattr(prefs, "preferred_decades", None)
            if decades and isinstance(decades, list):
                return [int(d) for d in decades[:2]]
        return []


# Singleton
_smart_query: Optional[SmartQueryStrategy] = None


def get_smart_query() -> SmartQueryStrategy:
    """Get singleton SmartQueryStrategy instance."""
    global _smart_query
    if _smart_query is None:
        _smart_query = SmartQueryStrategy()
    return _smart_query
