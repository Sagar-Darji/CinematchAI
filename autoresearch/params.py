"""CineMatch AI Tunable Parameters — THE ONLY FILE THE AI AGENT MODIFIES.

This file mirrors every hard-coded constant scattered across the 7-agent
recommendation pipeline. During an autoresearch run the AI agent proposes
changes to PARAMS, the evaluator applies them via monkey-patching, and the
loop keeps or reverts based on the composite quality score.

Structure:
    PARAMS = {
        "<agent_name>.<param_name>": value,
        ...
    }

Rules for the AI agent:
    1. Only change values inside PARAMS — never rename keys.
    2. Stay within the documented [min, max] ranges.
    3. Change 1-3 params per experiment (small, testable diffs).
    4. Write a brief EXPERIMENT_NOTE explaining your hypothesis.
"""

# One-line hypothesis for the current experiment (AI agent fills this in)
EXPERIMENT_NOTE = "Exp1 best: genre_per=0.20, genre_cap=0.35, dir=0.20, actor_cap=0.20"

PARAMS = {
    # =========================================================================
    # Content Intelligence Agent  (src/agents/content_intelligence.py)
    # =========================================================================

    # --- Scoring weights (lines 331-459) ---
    "content.base_score":                    0.55,     # [0.3, 0.7]   starting score for each candidate
    "content.genre_match_per_genre": 0.20, # [0.05, 0.2]  bonus per overlapping genre
    "content.genre_match_cap":     0.35, # [0.15, 0.35] max total genre bonus
    "content.disliked_genre_penalty":        0.2,     # [0.1, 0.3]   penalty for disliked genre overlap
    "content.tone_mood_factor":              0.3,     # [0.1, 0.5]   multiplier for tone-mood alignment
    "content.tone_mood_baseline":            0.4,     # [0.2, 0.6]   neutral affinity level
    "content.family_penalty":                0.25,    # [0.15, 0.35] penalty for non-family with family companion
    "content.family_animation_boost":        0.15,    # [0.1, 0.25]  boost for family/animation with family
    "content.romance_boost":                 0.1,     # [0.05, 0.15] boost for romance with partner
    "content.director_affinity_boost":       0.20,    # [0.1, 0.2]   boost for favourite director
    "content.actor_hit_weight":     0.1,  # [0.05, 0.1]  bonus per matching actor
    "content.actor_hit_cap":                 0.20,    # [0.1, 0.2]   max total actor bonus
    "content.lang_first_bonus":              0.12,    # [0.08, 0.15] bonus for top preferred language
    "content.lang_rank_decay":               0.04,    # [0.02, 0.06] decay per additional language rank
    "content.lang_min_bonus":                0.04,    # [0.02, 0.06] floor for language bonus
    "content.foreign_lang_penalty": 0.05, # [0.03, 0.1]  penalty for non-preferred language
    "content.keyword_hit_weight":            0.05,    # [0.02, 0.1]  bonus per NL keyword match
    "content.keyword_hit_cap":               0.15,    # [0.1, 0.25]  max total keyword bonus
    "content.nostalgia_norm":                50.0,    # [30.0, 60.0] year-age normalization divisor
    "content.nostalgia_weight":    0.27, # [0.1, 0.3]   nostalgia alignment weight
    "content.sequel_penalty":                0.08,    # [0.05, 0.15] sequel penalty
    "content.min_score_threshold":           0.35,    # [0.2, 0.5]   hard filter cutoff

    # --- Context weight multipliers (lines 407-459) ---
    "content.cw_family_boost":               0.20,    # [0.1, 0.3]   family-friendly genre boost
    "content.cw_family_penalty":             0.30,    # [0.15, 0.4]  adult genre penalty for family
    "content.cw_romance":                    0.12,    # [0.08, 0.15] romance context weight
    "content.cw_atmospheric":                0.12,    # [0.08, 0.15] night thriller/horror boost
    "content.cw_lighthearted_comedy":        0.15,    # [0.1, 0.2]   morning comedy boost
    "content.cw_lighthearted_drama_penalty": 0.10,    # [0.05, 0.15] morning heavy drama penalty
    "content.cw_thought_provoking":          0.12,    # [0.08, 0.15] cerebral content boost
    "content.cw_short_runtime_boost":        0.08,    # [0.05, 0.12] fast-paced boost
    "content.cw_slow_runtime_penalty":       0.05,    # [0.02, 0.08] slow-paced penalty
    "content.cw_immersive":                  0.08,    # [0.05, 0.12] weekend epic boost
    "content.cw_uplifting":                  0.10,    # [0.06, 0.15] feel-good boost

    # --- LLM deep analysis ---
    "content.deep_analysis_top_n":           10,      # [5, 20]  how many movies get LLM theme extraction
    "content.llm_rerank_top_n":              20,      # [10, 30] how many candidates get LLM reranking

    # =========================================================================
    # Serendipity Agent  (src/agents/serendipity.py)
    # =========================================================================
    "serendipity.default_exploration_rate":  0.3,     # [0.1, 0.5]   default diversity factor
    "serendipity.mmr_min_candidates":        5,       # [2, 10]      min candidates to apply MMR
    "serendipity.genre_sim_weight":          0.6,     # [0.4, 0.8]   genre Jaccard weight in similarity
    "serendipity.year_sim_weight":           0.4,     # [0.2, 0.6]   year proximity weight in similarity
    "serendipity.year_norm":                 50.0,    # [30.0, 70.0] years per similarity unit
    "serendipity.exploration_genre_overlap": 0.3,     # [0.2, 0.5]   genre overlap threshold for exploration

    # =========================================================================
    # Adversarial Critic Agent  (src/agents/critic.py)
    # =========================================================================
    "critic.quality_floor":                  5.5,     # [4.5, 6.5]   min vote_average
    "critic.quality_min_votes":              200,     # [100, 500]   min votes for quality signal
    "critic.fail_threshold":                 2,       # [1, 3]       failures needed to demote
    "critic.min_keep_floor":                 5,       # [3, 8]       absolute minimum survivors
    "critic.min_ratings_genre_check":        15,      # [10, 20]     ratings for genre mismatch check
    "critic.fav_genres_limit":               5,       # [3, 8]       top genres to consider
    "critic.filter_bubble_count":            3,       # [2, 4]       same-genre count for bubble detect

    # =========================================================================
    # Profile Analyzer  (src/agents/profile_analyzer.py)
    # =========================================================================
    "profile.disliked_rating_threshold":     2.5,     # [2.0, 3.0]   ratings <= this → disliked
    "profile.favorite_genres_limit":         5,       # [3, 8]       top genres to extract
    "profile.favorite_directors_limit":      5,       # [3, 8]       top directors
    "profile.favorite_actors_limit":         8,       # [5, 12]      top actors
    "profile.top_billed_actors":             3,       # [2, 5]       max cast per film
    "profile.preferred_decades_limit":       3,       # [2, 4]       max decades
    "profile.exploration_rate_norm":         20.0,    # [15.0, 30.0] genre diversity normalization
    "profile.exploration_rate_cap":          0.50,    # [0.3, 0.7]   max exploration rate
    "profile.nostalgia_norm":                30.0,    # [20.0, 40.0] year diff normalization
    "profile.risk_tolerance_offset":         0.3,     # [0.2, 0.4]   base risk tolerance
    "profile.time_decay_factor":             -0.002,  # [-0.005, -0.001] recency decay

    # =========================================================================
    # Context-Aware Agent  (src/agents/context_aware.py)
    # =========================================================================
    # Time-based weights
    "context.morning_lighthearted":          0.8,     # [0.6, 1.0]
    "context.morning_uplifting":             0.7,     # [0.5, 0.9]
    "context.morning_short_runtime":         0.6,     # [0.4, 0.8]
    "context.afternoon_lighthearted":        0.6,     # [0.4, 0.8]
    "context.afternoon_moderate_length":     0.7,     # [0.5, 0.9]
    "context.evening_engaging":              0.8,     # [0.6, 1.0]
    "context.evening_quality":               0.9,     # [0.7, 1.0]
    "context.night_atmospheric":             0.7,     # [0.5, 0.9]
    "context.night_thought_provoking":       0.6,     # [0.4, 0.8]
    # Companion weights
    "context.family_friendly":               1.0,     # [0.8, 1.0]
    "context.family_crowd_pleaser":          0.8,     # [0.6, 1.0]
    "context.friends_social":                0.9,     # [0.7, 1.0]
    "context.friends_entertaining":          0.8,     # [0.6, 1.0]
    "context.partner_romantic":              0.7,     # [0.5, 0.9]
    "context.partner_quality":               0.8,     # [0.6, 1.0]
    "context.alone_personal_interest":       1.0,     # [0.8, 1.0]
    "context.alone_exploration":             0.6,     # [0.4, 0.8]
    # Weekend/weekday
    "context.weekend_longer_runtime":        0.7,     # [0.5, 0.9]
    "context.weekend_immersive":             0.8,     # [0.6, 1.0]
    "context.weekday_efficient_runtime":     0.7,     # [0.5, 0.9]
    "context.weekday_relaxing":              0.6,     # [0.4, 0.8]

    # =========================================================================
    # Retrieval / Hybrid Search  (src/agents/graph/tools.py)
    # =========================================================================
    "retrieval.default_k":                   50,      # [30, 100]    candidate count
    "retrieval.base_db_ratio":      0.7,  # [0.6, 0.9]   vector DB allocation
    "retrieval.high_ratings_boost":          0.10,    # [0.05, 0.15] DB boost for 100+ ratings
    "retrieval.mid_ratings_boost":           0.05,    # [0.02, 0.10] DB boost for 50+ ratings
    "retrieval.low_ratings_penalty":         0.15,    # [0.1, 0.25]  DB penalty for <15 ratings
    "retrieval.exploration_influence":       0.3,     # [0.2, 0.5]   exploration rate scaling
    "retrieval.nl_context_impact":           0.15,    # [0.1, 0.25]  NL query DB reduction
    "retrieval.db_ratio_min":                0.15,    # [0.1, 0.3]   min DB allocation
    "retrieval.db_ratio_max":                0.85,    # [0.7, 0.95]  max DB allocation
    "retrieval.context_blend_history": 0.7,  # [0.5, 0.8]   profile taste weight
    "retrieval.context_blend_current":       0.35,    # [0.2, 0.5]   current context weight
    "retrieval.cf_fraction":                 0.25,    # [0.15, 0.35] CF candidates as fraction of k
    "retrieval.cf_weight_multiplier":        0.85,    # [0.7, 1.0]   CF score multiplier
    "retrieval.genre_boost":                 0.3,     # [0.1, 0.5]   mood-genre tie-breaker
    "retrieval.avoid_genre_penalty":         0.5,     # [0.3, 0.7]   companion-avoid genre demote
    "retrieval.risk_tolerance_threshold":    0.7,     # [0.5, 0.9]   quality gate threshold
    "retrieval.quality_gate_min_avg":        5.5,     # [4.5, 6.5]   quality floor for low-risk
    "retrieval.quality_gate_min_votes":      20,      # [10, 50]     min votes for quality signal

    # =========================================================================
    # Supervisor / Aggregation  (src/agents/supervisor.py)
    # =========================================================================
    "supervisor.num_recommendations":        10,      # [5, 20]      final recommendation count
    "supervisor.score_decay_per_rank":       0.05,    # [0.01, 0.1]  score decrease per position

    # =========================================================================
    # Explanation Agent  (src/agents/explanation.py)
    # =========================================================================
    "explanation.batch_max_tokens":          1500,    # [1000, 2000] tokens for batch explanation
    "explanation.top_n":                     10,      # [5, 20]      movies to explain
}