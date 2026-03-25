"""Smart TMDB Query Strategy — translates user preferences into targeted discover API queries.

Improvements over v1:
- Uses top 4 genres instead of 2 (#4)
- Director/actor-aware queries via TMDB with_crew/with_cast (#1)
- without_genres for companion filtering (#1)
- Smart exploration picks genre neighbors, not random (#7)
- Multi-query variants per strategy for ensemble retrieval (#8)
"""

import random
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

# Viewing-situation → TMDB genre IDs string + sort order
SITUATION_QUERY_MAP = {
    "late_night_solo":          ("27,53,878",  "vote_average.desc"),  # Horror, Thriller, Sci-Fi
    "family_movie_night":       ("10751,16",   "popularity.desc"),    # Family, Animation
    "weekend_social_gathering": ("35,28",      "popularity.desc"),    # Comedy, Action
    "weeknight_unwind":         ("18,10749",   "vote_average.desc"),  # Drama, Romance
    "lazy_weekend_afternoon":   ("12,14",      "popularity.desc"),    # Adventure, Fantasy
    "weeknight_date":           ("10749,18",   "vote_average.desc"),  # Romance, Drama
    "weekend_relaxation":       ("35,12",      "popularity.desc"),    # Comedy, Adventure
}

# Genre neighbors — genres that pair well together for exploration (#7)
# If user likes genre A, exploring genre B is a good diversification move.
GENRE_NEIGHBORS = {
    28:    [12, 878, 53],         # Action → Adventure, Sci-Fi, Thriller
    12:    [14, 28, 878],         # Adventure → Fantasy, Action, Sci-Fi
    16:    [10751, 35, 14],       # Animation → Family, Comedy, Fantasy
    35:    [10749, 18, 16],       # Comedy → Romance, Drama, Animation
    80:    [53, 9648, 18],        # Crime → Thriller, Mystery, Drama
    99:    [36, 10402, 878],      # Documentary → History, Music, Sci-Fi
    18:    [10749, 36, 9648],     # Drama → Romance, History, Mystery
    10751: [16, 35, 12],          # Family → Animation, Comedy, Adventure
    14:    [12, 878, 16],         # Fantasy → Adventure, Sci-Fi, Animation
    36:    [10752, 18, 99],       # History → War, Drama, Documentary
    27:    [53, 9648, 878],       # Horror → Thriller, Mystery, Sci-Fi
    10402: [18, 99, 35],          # Music → Drama, Documentary, Comedy
    9648:  [53, 80, 27],          # Mystery → Thriller, Crime, Horror
    10749: [18, 35, 9648],        # Romance → Drama, Comedy, Mystery
    878:   [12, 14, 53],          # Sci-Fi → Adventure, Fantasy, Thriller
    53:    [80, 9648, 28],        # Thriller → Crime, Mystery, Action
    10752: [36, 18, 28],          # War → History, Drama, Action
    37:    [28, 12, 18],          # Western → Action, Adventure, Drama
}

# Companion → genres to exclude via without_genres (#1)
COMPANION_EXCLUDE_GENRES = {
    "family": [27, 53, 80, 10752],    # Horror, Thriller, Crime, War
    "kids":   [27, 53, 80, 10752, 18], # + Drama
}


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

        Strategy allocation:
        1. GENRE-BASED      (35%) — user's top 4 favourite genres (#4)
        2. EXPLORATION       (10%) — smart genre neighbors, not random (#7)
        3. MOOD-MATCHED      (15-25%) — if mood present in context
        4. DECADE-BASED      (10%) — user's preferred decades
        5. LANGUAGE-SPECIFIC  (10%) — if language set
        6. DIRECTOR/ACTOR    (10%) — favourite directors/actors from profile (#1)
        7. NL-FREEFORM       (25%) — if natural language context present
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
        viewing_situation = context_factors.get("viewing_situation", "casual_viewing")
        companion = context_factors.get("companion") or context.get("companion")
        nl_context = (
            context_factors.get("natural_language_context")
            or context.get("natural_language_context")
            or ""
        )

        # Companion-based genre exclusion (#1)
        without_genres_str = self._get_without_genres(companion)

        # ---- 1. GENRE-BASED (35% of k) — now uses top 4 genres (#4) ----
        genre_k = max(int(k * 0.35), 5)
        if top_genres:
            genre_list = top_genres[:4]  # Expanded from 2 to 4 (#4)
            per_genre = max(genre_k // len(genre_list), 2)
            for genre_name in genre_list:
                genre_id = TMDB_GENRE_IDS.get(genre_name)
                if genre_id:
                    q = self._genre_query(
                        genre_ids=[genre_id],
                        sort_by="vote_average.desc",
                        pages=max(1, per_genre // 20),
                        year_min=year_min,
                        year_max=year_max,
                    )
                    if without_genres_str:
                        q["without_genres"] = without_genres_str
                    q["_strategy"] = "genre_based"
                    q["_target_k"] = per_genre
                    queries.append(self._apply_context_filters(q, context))
        else:
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

        # ---- 2. EXPLORATION (10% of k) — smart genre neighbors (#7) ----
        mood_explicit = bool(mood)
        explore_k = max(int(k * 0.05) if mood_explicit else int(k * 0.10), 2)

        if nl_context and len(nl_context) > 15:
            nl_params = self._parse_nl_to_tmdb_params(nl_context, year_min, year_max)
            if nl_params:
                nl_params["_strategy"] = "nl_freeform"
                nl_params["_target_k"] = max(int(k * 0.25), 5)
                queries.append(nl_params)
            else:
                self._add_exploration_query(
                    queries, viewing_situation, explore_k, unexplored,
                    year_min, year_max, context, explored_genre_ids,
                )
        else:
            self._add_exploration_query(
                queries, viewing_situation, explore_k, unexplored,
                year_min, year_max, context, explored_genre_ids,
            )

        # ---- 3. MOOD-MATCHED (25% of k when explicit, else 15%) ----
        mood_k = max(int(k * 0.25) if mood_explicit else int(k * 0.15), 3)
        if mood and mood.lower() in MOOD_GENRE_MAP:
            mood_genres = MOOD_GENRE_MAP[mood.lower()]
            user_genre_ids = {TMDB_GENRE_IDS[g] for g in top_genres if g in TMDB_GENRE_IDS}
            if user_genre_ids:
                intersected = [gid for gid in mood_genres if gid in user_genre_ids]
                mood_genres = intersected if len(intersected) >= 2 else mood_genres

            # Primary mood query
            q = self._genre_query(
                genre_ids=mood_genres[:2],
                sort_by="popularity.desc",
                pages=1,
                year_min=year_min,
                year_max=year_max,
            )
            if without_genres_str:
                q["without_genres"] = without_genres_str
            q["_strategy"] = "mood_matched"
            q["_target_k"] = mood_k
            queries.append(self._apply_context_filters(q, context))

            # Ensemble variant: same mood, different sort (#8)
            if mood_k >= 6:
                q2 = self._genre_query(
                    genre_ids=mood_genres[:2],
                    sort_by="vote_average.desc",
                    pages=1,
                    year_min=year_min,
                    year_max=year_max,
                )
                q2["vote_count.gte"] = 100
                if without_genres_str:
                    q2["without_genres"] = without_genres_str
                q2["_strategy"] = "mood_matched_quality"
                q2["_target_k"] = mood_k // 2
                queries.append(self._apply_context_filters(q2, context))

        # ---- 4. DECADE-BASED (10% of k) ----
        decade_k = max(int(k * 0.10), 3)
        if preferred_decades:
            decade = preferred_decades[0]
            q = self._genre_query(
                genre_ids=[],
                sort_by="vote_average.desc",
                pages=1,
                year_min=decade,
                year_max=decade + 9,
            )
            q["vote_count.gte"] = 200
            q["_strategy"] = "decade_based"
            q["_target_k"] = decade_k
            queries.append(self._apply_context_filters(q, context))

        # ---- 5. LANGUAGE-SPECIFIC (10% of k) ----
        lang_k = max(int(k * 0.10), 3)
        if language:
            q = {
                "sort_by": "popularity.desc",
                "with_original_language": language,
                "vote_count.gte": 50,
                "page": random.randint(1, 5),
                "_strategy": "language_specific",
                "_target_k": lang_k,
            }
            if year_min:
                q["primary_release_date.gte"] = f"{year_min}-01-01"
            if year_max:
                q["primary_release_date.lte"] = f"{year_max}-12-31"
            queries.append(q)

        # ---- 6. DIRECTOR/ACTOR queries (#1) ----
        self._add_director_actor_queries(
            queries, user_profile, k, year_min, year_max, context, without_genres_str,
        )

        logger.info(
            f"SmartQuery: built {len(queries)} discover queries "
            f"(genres={top_genres[:4]}, mood={mood}, situation={viewing_situation}, "
            f"nl={'yes' if nl_context else 'no'}, lang={language}, companion={companion})"
        )
        return queries

    # ---------------------------------------------------------------- helpers

    def _get_without_genres(self, companion: Optional[str]) -> str:
        """Build without_genres string for companion filtering (#1)."""
        if not companion:
            return ""
        exclude = COMPANION_EXCLUDE_GENRES.get(companion.lower(), [])
        return ",".join(str(gid) for gid in exclude) if exclude else ""

    def _add_director_actor_queries(
        self,
        queries: list,
        user_profile,
        k: int,
        year_min,
        year_max,
        context: dict,
        without_genres_str: str,
    ) -> None:
        """Add director/actor-based discover queries (#1).

        Uses TMDB search/person to resolve names → IDs, then discover with_crew/with_cast.
        """
        if not user_profile:
            return

        prefs = getattr(user_profile, "preferences", None)
        if not prefs:
            return

        director_k = max(int(k * 0.05), 2)
        actor_k = max(int(k * 0.05), 2)

        # Director query — top favourite director
        fav_directors = getattr(prefs, "favorite_directors", None) or []
        if fav_directors:
            person_id = self._resolve_tmdb_person_id(fav_directors[0])
            if person_id:
                q: Dict[str, Any] = {
                    "with_crew": str(person_id),
                    "sort_by": "vote_average.desc",
                    "vote_count.gte": 30,
                    "page": random.randint(1, 3),
                    "_strategy": "director_affinity",
                    "_target_k": director_k,
                }
                if without_genres_str:
                    q["without_genres"] = without_genres_str
                if year_min:
                    q["primary_release_date.gte"] = f"{year_min}-01-01"
                if year_max:
                    q["primary_release_date.lte"] = f"{year_max}-12-31"
                queries.append(self._apply_context_filters(q, context))

        # Actor query — top favourite actor
        fav_actors = getattr(prefs, "favorite_actors", None) or []
        if fav_actors:
            person_id = self._resolve_tmdb_person_id(fav_actors[0])
            if person_id:
                q = {
                    "with_cast": str(person_id),
                    "sort_by": "popularity.desc",
                    "vote_count.gte": 30,
                    "page": random.randint(1, 3),
                    "_strategy": "actor_affinity",
                    "_target_k": actor_k,
                }
                if without_genres_str:
                    q["without_genres"] = without_genres_str
                if year_min:
                    q["primary_release_date.gte"] = f"{year_min}-01-01"
                if year_max:
                    q["primary_release_date.lte"] = f"{year_max}-12-31"
                queries.append(self._apply_context_filters(q, context))

    def _resolve_tmdb_person_id(self, name: str) -> Optional[int]:
        """Resolve a person name to a TMDB person ID via search/person API."""
        try:
            import requests
            from config.settings import get_settings
            settings = get_settings()
            url = f"https://api.themoviedb.org/3/search/person"
            resp = requests.get(
                url,
                params={"api_key": settings.tmdb_api_key, "query": name},
                timeout=5,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    person_id = results[0].get("id")
                    logger.debug(f"Resolved '{name}' → TMDB person {person_id}")
                    return person_id
        except Exception as e:
            logger.debug(f"Person ID resolve failed for '{name}': {e}")
        return None

    def _add_exploration_query(
        self,
        queries: list,
        viewing_situation: str,
        explore_k: int,
        unexplored: list,
        year_min,
        year_max,
        context: dict,
        explored_genre_ids: set = None,
    ) -> None:
        """Append exploration query: situation-aware > genre neighbors > random (#7)."""
        if viewing_situation in SITUATION_QUERY_MAP:
            genre_str, sort_by = SITUATION_QUERY_MAP[viewing_situation]
            q: Dict[str, Any] = {
                "with_genres": genre_str,
                "sort_by": sort_by,
                "vote_count.gte": 50,
                "page": random.randint(1, 3),
                "_strategy": "situation_based",
                "_target_k": explore_k,
            }
            if year_min:
                q["primary_release_date.gte"] = f"{year_min}-01-01"
            if year_max:
                q["primary_release_date.lte"] = f"{year_max}-12-31"
            queries.append(self._apply_context_filters(q, context))
        elif explored_genre_ids:
            # Smart exploration: pick genre neighbors of user's favorites (#7)
            neighbor_candidates = set()
            for gid in explored_genre_ids:
                if gid in GENRE_NEIGHBORS:
                    for neighbor in GENRE_NEIGHBORS[gid]:
                        if neighbor not in explored_genre_ids:
                            neighbor_candidates.add(neighbor)

            if neighbor_candidates:
                explore_genres = random.sample(
                    list(neighbor_candidates), min(2, len(neighbor_candidates))
                )
            elif unexplored:
                explore_genres = random.sample(unexplored, min(2, len(unexplored)))
            else:
                return

            q = self._genre_query(
                genre_ids=explore_genres,
                sort_by="popularity.desc",
                pages=1,
                year_min=year_min,
                year_max=year_max,
            )
            q["_strategy"] = "exploration_neighbor"
            q["_target_k"] = explore_k
            queries.append(self._apply_context_filters(q, context))
        elif unexplored:
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

    def _parse_nl_to_tmdb_params(
        self,
        nl_text: str,
        year_min=None,
        year_max=None,
    ) -> Optional[Dict[str, Any]]:
        """Call LLM to parse freeform natural language into TMDB discover params."""
        try:
            from config.settings import get_settings
            settings = get_settings()
            if not settings.groq_api_key:
                return None

            import json
            import re
            from groq import Groq

            client = Groq(api_key=settings.groq_api_key)

            parse_prompt = (
                f'Parse this movie request into TMDB discover params JSON.\n'
                f'Request: "{nl_text}"\n'
                f'Return ONLY a JSON object. Valid keys: with_genres (comma-separated TMDB genre IDs), '
                f'with_original_language (ISO code), sort_by, vote_average.gte, '
                f'with_keywords (comma-separated TMDB keyword IDs), '
                f'with_runtime.gte (min minutes), with_runtime.lte (max minutes).\n'
                f'TMDB IDs — Action:28 Adventure:12 Animation:16 Comedy:35 Crime:80 '
                f'Drama:18 Family:10751 Fantasy:14 History:36 Horror:27 Music:10402 '
                f'Mystery:9648 Romance:10749 SciFi:878 Thriller:53 War:10752.\n'
                f'Example: {{"with_genres": "10749,35", "sort_by": "popularity.desc"}}'
            )

            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": parse_prompt}],
                max_tokens=120,
                temperature=0.0,
            )
            text = resp.choices[0].message.content.strip()
            m = re.search(r'\{[^{}]+\}', text)
            if not m:
                return None

            params: Dict[str, Any] = json.loads(m.group(0))
            params.setdefault("vote_count.gte", 30)
            params.setdefault("page", 1)
            if year_min:
                params["primary_release_date.gte"] = f"{year_min}-01-01"
            if year_max:
                params["primary_release_date.lte"] = f"{year_max}-12-31"

            logger.info(f"NL→TMDB parse: '{nl_text[:60]}' → {params}")
            return params

        except Exception as e:
            logger.warning(f"NL→TMDB parse failed (non-critical): {e}")
            return None

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
            "page": random.randint(1, 5),
        }
        if genre_ids:
            params["with_genres"] = ",".join(str(gid) for gid in genre_ids)
        if year_min:
            params["primary_release_date.gte"] = f"{year_min}-01-01"
        if year_max:
            params["primary_release_date.lte"] = f"{year_max}-12-31"
        params["_pages"] = max(1, min(pages, 3))
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
