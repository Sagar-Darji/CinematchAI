"""Movie Web Service — TMDB multi-signal graph + LLM Cinematic Fingerprint."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from diskcache import Cache
from requests.adapters import HTTPAdapter

from config.settings import get_settings
from src.utils.logging import get_logger

import os

logger = get_logger(__name__)
settings = get_settings()

# On Lambda, /tmp is the only writable directory
_cache_dir = "/tmp/movie_web" if os.environ.get("LAMBDA_TASK_ROOT") else "./data/cache/movie_web"
_web_cache = Cache(_cache_dir)

TMDB_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w185"

EDGE_DIRECTOR = "director"
EDGE_ACTOR = "actor"
EDGE_KEYWORD = "keyword"
EDGE_SIMILAR = "similar"
EDGE_GENRE = "genre"


class MovieWebService:
    """Generate movie similarity graphs via TMDB multi-signal retrieval + LLM vibe scoring."""

    def __init__(self):
        self.api_key = settings.tmdb_api_key
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_maxsize=20, pool_connections=10)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    # ──────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────

    def get_movie_web(self, movie_name: str, max_nodes: int = 35) -> Optional[Dict]:
        """Return a similarity graph centred on *movie_name*.

        Response shape:
            {seed, nodes, edges, stats}
        Returns None if the movie cannot be found.
        """
        cache_key = f"web:v1:{movie_name.lower().strip()}:{max_nodes}"
        cached = _web_cache.get(cache_key)
        if cached:
            logger.info(f"[MovieWeb] Cache hit: '{movie_name}'")
            return cached

        # 1 — Find seed
        seed = self._find_seed_movie(movie_name)
        if not seed:
            return None

        # 2 — Fetch candidates
        candidates, similar_ids, rec_ids = self._fetch_candidates(seed)
        logger.info(f"[MovieWeb] {len(candidates)} raw candidates for '{seed['title']}'")

        # 3 — Structural scoring
        self._score_structural(seed, candidates, similar_ids, rec_ids)

        # 4 — Take top-40 by structural score; LLM scores the top-25 of those
        candidates.sort(key=lambda c: c["structural_score"], reverse=True)
        top_all = candidates[:40]
        top_llm = top_all[:25]  # LLM only re-ranks the cream of the crop

        # 5 — LLM cinematic fingerprint re-scoring (graceful fallback)
        try:
            llm_scores = self._llm_rescore(seed, top_llm)
        except Exception as exc:
            logger.warning(f"[MovieWeb] LLM rescore failed, using structural only: {exc}")
            llm_scores = {c["id"]: 0.5 for c in top_llm}

        # 6 — Score fusion  (structural 40 % + vibe 60 %)
        #     Candidates outside top-25 get vibe=0.5 (neutral) as fallback
        for c in top_all:
            vibe = llm_scores.get(c["id"], 0.5)
            c["final_score"] = round(c["structural_score"] * 0.40 + vibe * 0.60, 4)

        top_all.sort(key=lambda c: c["final_score"], reverse=True)
        final_nodes = top_all[:max_nodes]

        # 7 — Build edges
        edges = self._build_edges(seed, final_nodes)

        result = {
            "seed": self._format_node(seed, 1.0, is_seed=True),
            "nodes": [self._format_node(c, c["final_score"]) for c in final_nodes],
            "edges": edges,
            "stats": {
                "candidates_evaluated": len(candidates),
                "nodes": len(final_nodes) + 1,
                "edges": len(edges),
                "keywords_used": len(seed.get("keyword_ids", [])),
            },
        }

        _web_cache.set(cache_key, result, expire=86400)  # 24 h
        return result

    # ──────────────────────────────────────────────────────────────
    # Step 1 — Seed lookup
    # ──────────────────────────────────────────────────────────────

    def _find_seed_movie(self, movie_name: str) -> Optional[Dict]:
        try:
            resp = self._session.get(
                f"{TMDB_BASE}/search/movie",
                params={"api_key": self.api_key, "query": movie_name},
                timeout=10,
            )
            results = resp.json().get("results", []) if resp.status_code == 200 else []
            if not results:
                return None
            best = max(results, key=lambda x: x.get("popularity", 0))
            return self._fetch_full_movie(best["id"])
        except Exception as exc:
            logger.error(f"[MovieWeb] Seed lookup failed for '{movie_name}': {exc}")
            return None

    def _fetch_full_movie(self, tmdb_id: int) -> Optional[Dict]:
        ck = f"fmovie:{tmdb_id}"
        hit = _web_cache.get(ck)
        if hit:
            return hit

        try:
            resp = self._session.get(
                f"{TMDB_BASE}/movie/{tmdb_id}",
                params={"api_key": self.api_key, "append_to_response": "credits,keywords"},
                timeout=10,
            )
            if resp.status_code != 200:
                return None
            d = resp.json()

            crew = d.get("credits", {}).get("crew", [])
            cast = d.get("credits", {}).get("cast", [])
            kws = d.get("keywords", {}).get("keywords", [])

            director = next(
                (p["name"] for p in crew if p.get("job") == "Director"), None
            )
            director_id = next(
                (p["id"] for p in crew if p.get("job") == "Director"), None
            )

            movie = {
                "id": d["id"],
                "title": d.get("title", "Unknown"),
                "year": (d.get("release_date") or "")[:4] or None,
                "genres": [g["name"] for g in d.get("genres", [])],
                "genre_ids": [g["id"] for g in d.get("genres", [])],
                "overview": d.get("overview", ""),
                "vote_average": d.get("vote_average"),
                "poster_path": d.get("poster_path"),
                "director": director,
                "director_id": director_id,
                "cast": [c["name"] for c in cast[:5]],
                "cast_ids": [c["id"] for c in cast[:2]],
                "keywords": [k["name"] for k in kws[:15]],
                "keyword_ids": [k["id"] for k in kws[:8]],
            }
            _web_cache.set(ck, movie, expire=86400)
            return movie
        except Exception as exc:
            logger.error(f"[MovieWeb] Full movie fetch failed ({tmdb_id}): {exc}")
            return None

    # ──────────────────────────────────────────────────────────────
    # Step 2 — Parallel candidate retrieval
    # ──────────────────────────────────────────────────────────────

    def _fetch_candidates(
        self, seed: Dict
    ) -> Tuple[List[Dict], Set[int], Set[int]]:
        seed_id = seed["id"]
        kw_ids = seed.get("keyword_ids", [])
        director_id = seed.get("director_id")
        cast_ids = seed.get("cast_ids", [])

        pool: Dict[int, Dict] = {}
        similar_ids: Set[int] = set()
        rec_ids: Set[int] = set()

        # ── build task list ───────────────────────────────────────
        tasks: List[Tuple[str, str, Dict]] = [
            ("similar", f"{TMDB_BASE}/movie/{seed_id}/similar",
             {"api_key": self.api_key}),
            ("recommendations", f"{TMDB_BASE}/movie/{seed_id}/recommendations",
             {"api_key": self.api_key}),
        ]
        for kid in kw_ids[:8]:
            tasks.append((
                "keyword", f"{TMDB_BASE}/discover/movie",
                {"api_key": self.api_key, "with_keywords": kid,
                 "sort_by": "popularity.desc"},
            ))
        if director_id:
            tasks.append((
                "director", f"{TMDB_BASE}/discover/movie",
                {"api_key": self.api_key, "with_crew": director_id,
                 "sort_by": "vote_average.desc"},
            ))
        for aid in cast_ids[:2]:
            tasks.append((
                "actor", f"{TMDB_BASE}/discover/movie",
                {"api_key": self.api_key, "with_cast": aid,
                 "sort_by": "popularity.desc"},
            ))

        # ── execute in parallel ───────────────────────────────────
        def _get(url: str, params: Dict) -> List[Dict]:
            try:
                r = self._session.get(url, params=params, timeout=8)
                return r.json().get("results", []) if r.status_code == 200 else []
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=14) as ex:
            futures = {ex.submit(_get, url, params): t for t, url, params in tasks}
            for fut in as_completed(futures, timeout=20):
                task_type = futures[fut]
                try:
                    items = fut.result()
                except Exception:
                    continue

                for item in items:
                    mid = item.get("id")
                    if not mid or mid == seed_id:
                        continue

                    if mid not in pool:
                        pool[mid] = {
                            "id": mid,
                            "title": item.get("title", "Unknown"),
                            "year": (item.get("release_date") or "")[:4] or None,
                            "genre_ids": item.get("genre_ids", []),
                            "genres": [],
                            "overview": item.get("overview", ""),
                            "vote_average": item.get("vote_average"),
                            "poster_path": item.get("poster_path"),
                            "in_similar": False,
                            "in_recs": False,
                            "shared_director": False,
                            "shared_actor": False,
                            "keyword_overlap_count": 0,
                        }

                    if task_type == "similar":
                        pool[mid]["in_similar"] = True
                        similar_ids.add(mid)
                    elif task_type == "recommendations":
                        pool[mid]["in_recs"] = True
                        rec_ids.add(mid)
                    elif task_type == "keyword":
                        pool[mid]["keyword_overlap_count"] += 1
                    elif task_type == "director":
                        pool[mid]["shared_director"] = True
                    elif task_type == "actor":
                        pool[mid]["shared_actor"] = True

        # Resolve genre names
        try:
            from src.services.smart_query import GENRE_ID_TO_NAME
            for c in pool.values():
                c["genres"] = [
                    GENRE_ID_TO_NAME[g] for g in c["genre_ids"] if g in GENRE_ID_TO_NAME
                ]
        except Exception:
            pass

        return list(pool.values()), similar_ids, rec_ids

    # ──────────────────────────────────────────────────────────────
    # Step 3 — Structural scoring + edge-type tagging
    # ──────────────────────────────────────────────────────────────

    def _score_structural(
        self,
        seed: Dict,
        candidates: List[Dict],
        similar_ids: Set[int],
        rec_ids: Set[int],
    ) -> None:
        seed_genre_ids = set(seed.get("genre_ids", []))
        n_genres = max(len(seed_genre_ids), 1)

        for c in candidates:
            genre_overlap = len(set(c.get("genre_ids", [])) & seed_genre_ids)
            kw_score = min(c["keyword_overlap_count"], 8) / 8.0

            score = (
                kw_score * 0.40
                + (0.18 if c["in_similar"] else 0.0)
                + (0.12 if c["in_recs"] else 0.0)
                + (genre_overlap / n_genres) * 0.15
                + (0.25 if c["shared_director"] else 0.0)
                + (0.15 if c["shared_actor"] else 0.0)
            )
            c["structural_score"] = min(score, 1.0)

            # Dominant edge type
            if c["shared_director"]:
                c["edge_type"] = EDGE_DIRECTOR
            elif c["shared_actor"]:
                c["edge_type"] = EDGE_ACTOR
            elif c["keyword_overlap_count"] > 0:
                c["edge_type"] = EDGE_KEYWORD
            elif c["in_similar"]:
                c["edge_type"] = EDGE_SIMILAR
            else:
                c["edge_type"] = EDGE_GENRE

    # ──────────────────────────────────────────────────────────────
    # Step 4 — LLM cinematic fingerprint re-scoring
    # ──────────────────────────────────────────────────────────────

    def _llm_rescore(self, seed: Dict, candidates: List[Dict]) -> Dict[int, float]:
        from groq import Groq  # lazy import — avoids hard dep if Groq not installed

        client = Groq(api_key=settings.groq_api_key)
        model = settings.groq_model_main

        # -- fingerprint (cached 7 days) --
        fp_key = f"fp:{seed['id']}"
        fingerprint: Optional[str] = _web_cache.get(fp_key)
        if not fingerprint:
            fp_prompt = (
                f"Describe the movie '{seed['title']}' ({seed.get('year','')}) in exactly "
                f"5 comma-separated words of cinematic feel: tone, pacing, emotional weight, "
                f"narrative style, core vibe. Example: 'tense, slow-burn, heartbreaking, "
                f"non-linear, cerebral'. Reply ONLY those 5 words."
            )
            fp_resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": fp_prompt}],
                max_tokens=50,
                temperature=0.3,
            )
            fingerprint = fp_resp.choices[0].message.content.strip()
            _web_cache.set(fp_key, fingerprint, expire=604800)  # 7 days

        logger.info(f"[MovieWeb] Fingerprint '{seed['title']}': {fingerprint}")

        # -- batched rescore --
        lines = "\n".join(
            f"{i}: {c['title']} ({c.get('year','?')})"
            for i, c in enumerate(candidates)
        )
        rescore_prompt = (
            f"Seed movie feel: {fingerprint}\n\n"
            f"Rate each film 0-10 for how similarly it would make a viewer FEEL "
            f"(tone, emotion, pacing — not just genre):\n{lines}\n\n"
            f"Reply ONLY in this exact format (index:score), space-separated: "
            f"0:8.5 1:7.2 2:9.1\nNo other text."
        )
        rs_resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": rescore_prompt}],
            max_tokens=300,
            temperature=0.1,
        )
        raw = rs_resp.choices[0].message.content.strip()

        scores: Dict[int, float] = {}
        for token in raw.replace("\n", " ").split():
            try:
                idx_s, score_s = token.split(":")
                idx = int(idx_s.strip())
                score = float(score_s.strip())
                if 0 <= idx < len(candidates):
                    scores[candidates[idx]["id"]] = min(score / 10.0, 1.0)
            except Exception:
                continue

        logger.info(f"[MovieWeb] LLM parsed {len(scores)}/{len(candidates)} scores")
        return scores

    # ──────────────────────────────────────────────────────────────
    # Step 5 — Edge construction
    # ──────────────────────────────────────────────────────────────

    def _build_edges(self, seed: Dict, nodes: List[Dict]) -> List[Dict]:
        edges: List[Dict] = []
        seed_id = seed["id"]

        # Seed → each node
        for n in nodes:
            reasons: List[str] = []
            if n.get("shared_director") and seed.get("director"):
                reasons.append(f"Directed by {seed['director']}")
            if n.get("shared_actor"):
                reasons.append("Shares lead actor(s) with seed")
            if n.get("in_similar"):
                reasons.append("TMDB similar list")
            if n.get("in_recs"):
                reasons.append("TMDB editorial pick")
            if n.get("keyword_overlap_count", 0) > 0:
                reasons.append(f"{n['keyword_overlap_count']} shared theme(s)")
            if not reasons:
                reasons.append("Genre family match")

            edges.append({
                "source": seed_id,
                "target": n["id"],
                "weight": round(n["final_score"], 3),
                "type": n.get("edge_type", EDGE_SIMILAR),
                "reasons": reasons,
            })

        # Inter-node edges where both share director or both share actor
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                inter_type = None
                inter_reasons: List[str] = []
                if a.get("shared_director") and b.get("shared_director"):
                    inter_type = EDGE_DIRECTOR
                    inter_reasons.append(
                        f"Both directed by {seed.get('director', 'same director')}"
                    )
                elif a.get("shared_actor") and b.get("shared_actor"):
                    inter_type = EDGE_ACTOR
                    inter_reasons.append("Both feature shared lead actor(s)")
                if inter_type:
                    edges.append({
                        "source": a["id"],
                        "target": b["id"],
                        "weight": round((a["final_score"] + b["final_score"]) / 2, 3),
                        "type": inter_type,
                        "reasons": inter_reasons,
                    })

        return edges

    # ──────────────────────────────────────────────────────────────
    # Formatting
    # ──────────────────────────────────────────────────────────────

    def _format_node(self, movie: Dict, score: float, is_seed: bool = False) -> Dict:
        pp = movie.get("poster_path")
        node: Dict[str, Any] = {
            "id": movie["id"],
            "title": movie.get("title", "Unknown"),
            "year": movie.get("year"),
            "genres": movie.get("genres", []),
            "poster_url": f"{POSTER_BASE}{pp}" if pp else None,
            "vote_average": movie.get("vote_average"),
            "overview": movie.get("overview", ""),
            "score": round(score, 3),
        }
        if is_seed:
            node["director"] = movie.get("director")
            node["cast"] = movie.get("cast", [])
            node["keywords"] = movie.get("keywords", [])
        else:
            node["edge_type"] = movie.get("edge_type", EDGE_SIMILAR)
            reasons: List[str] = []
            if movie.get("shared_director"):
                reasons.append("Same director")
            if movie.get("shared_actor"):
                reasons.append("Shares lead actor")
            if movie.get("in_similar"):
                reasons.append("TMDB similar")
            if movie.get("in_recs"):
                reasons.append("TMDB recommended")
            if movie.get("keyword_overlap_count", 0) > 0:
                reasons.append(f"{movie['keyword_overlap_count']} shared theme(s)")
            node["reasons"] = reasons or ["Genre match"]
        return node


# ── Singleton ──────────────────────────────────────────────────────────────────
_service: Optional[MovieWebService] = None


def get_movie_web_service() -> MovieWebService:
    global _service
    if _service is None:
        _service = MovieWebService()
    return _service
