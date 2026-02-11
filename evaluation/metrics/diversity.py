"""Diversity Metrics - Intra-list diversity, coverage, novelty."""

import numpy as np
from typing import List, Dict, Set
from collections import Counter
from src.core.models import Movie
from src.utils.logging import get_logger

logger = get_logger(__name__)


def intra_list_diversity(
    recommendations: List[Movie],
    diversity_metric: str = "genre",
) -> float:
    """
    Calculate intra-list diversity (how different items are within a list).

    Args:
        recommendations: List of recommended movies.
        diversity_metric: Metric to use ("genre", "year", "combined").

    Returns:
        Diversity score (0-1, higher = more diverse).
    """
    if len(recommendations) < 2:
        return 0.0

    total_distance = 0.0
    comparisons = 0

    for i, movie1 in enumerate(recommendations):
        for movie2 in recommendations[i + 1 :]:
            distance = _calculate_distance(movie1, movie2, diversity_metric)
            total_distance += distance
            comparisons += 1

    return total_distance / comparisons if comparisons > 0 else 0.0


def _calculate_distance(
    movie1: Movie,
    movie2: Movie,
    metric: str = "genre",
) -> float:
    """
    Calculate distance between two movies.

    Args:
        movie1: First movie.
        movie2: Second movie.
        metric: Distance metric ("genre", "year", "combined").

    Returns:
        Distance score (0-1).
    """
    if metric == "genre":
        return _genre_distance(movie1, movie2)
    elif metric == "year":
        return _year_distance(movie1, movie2)
    elif metric == "combined":
        genre_dist = _genre_distance(movie1, movie2)
        year_dist = _year_distance(movie1, movie2)
        return 0.7 * genre_dist + 0.3 * year_dist
    else:
        return 0.0


def _genre_distance(movie1: Movie, movie2: Movie) -> float:
    """Calculate genre distance (Jaccard distance)."""
    genres1 = set(movie1.metadata.genres or [])
    genres2 = set(movie2.metadata.genres or [])

    if not genres1 and not genres2:
        return 0.5  # Neutral if both have no genres

    intersection = len(genres1 & genres2)
    union = len(genres1 | genres2)

    # Jaccard distance = 1 - Jaccard similarity
    return 1 - (intersection / union if union > 0 else 0)


def _year_distance(movie1: Movie, movie2: Movie) -> float:
    """Calculate year distance (normalized)."""
    year1 = movie1.metadata.year or 2000
    year2 = movie2.metadata.year or 2000

    year_diff = abs(year1 - year2)

    # Normalize to 0-1 (50 years = max diversity)
    return min(year_diff / 50.0, 1.0)


def catalog_coverage(
    all_recommendations: List[List[str]],
    catalog_size: int,
) -> float:
    """
    Calculate catalog coverage (what % of catalog is recommended).

    Args:
        all_recommendations: All recommendation lists for all users.
        catalog_size: Total number of items in catalog.

    Returns:
        Coverage score (0-1).
    """
    # Collect all unique recommended items
    recommended_items = set()

    for rec_list in all_recommendations:
        recommended_items.update(rec_list)

    coverage = len(recommended_items) / catalog_size if catalog_size > 0 else 0.0

    return coverage


def gini_index(item_counts: Dict[str, int]) -> float:
    """
    Calculate Gini index (inequality of item distribution).

    Lower Gini = more equal distribution (better).
    Higher Gini = more concentrated (worse, popularity bias).

    Args:
        item_counts: Dict of item_id -> recommendation count.

    Returns:
        Gini index (0-1).
    """
    if not item_counts:
        return 0.0

    # Sort counts
    counts = sorted(item_counts.values())
    n = len(counts)

    # Calculate Gini coefficient
    cumulative_counts = np.cumsum(counts)
    total = cumulative_counts[-1]

    if total == 0:
        return 0.0

    # Gini = (2 * sum(i * count_i)) / (n * sum(count_i)) - (n+1)/n
    weighted_sum = sum((i + 1) * count for i, count in enumerate(counts))
    gini = (2 * weighted_sum) / (n * total) - (n + 1) / n

    return gini


def novelty_score(
    recommendations: List[str],
    item_popularity: Dict[str, int],
    total_users: int,
) -> float:
    """
    Calculate novelty score (how unexpected recommendations are).

    Novelty = -log2(popularity)
    Higher novelty = less popular items recommended.

    Args:
        recommendations: List of recommended item IDs.
        item_popularity: Dict of item_id -> # users who rated it.
        total_users: Total number of users.

    Returns:
        Average novelty score.
    """
    novelties = []

    for item_id in recommendations:
        popularity = item_popularity.get(item_id, 1)

        # Calculate probability of item being known
        prob = popularity / total_users

        # Avoid log(0)
        prob = max(prob, 1e-10)

        # Novelty = -log2(probability)
        novelty = -np.log2(prob)

        novelties.append(novelty)

    return np.mean(novelties) if novelties else 0.0


def serendipity_score(
    recommendations: List[str],
    relevant_items: List[str],
    item_popularity: Dict[str, int],
    total_users: int,
) -> float:
    """
    Calculate serendipity score (unexpected + relevant).

    Serendipity = relevance * unexpectedness

    Args:
        recommendations: Recommended item IDs.
        relevant_items: Relevant item IDs (ground truth).
        item_popularity: Dict of item_id -> popularity.
        total_users: Total number of users.

    Returns:
        Serendipity score (0-1).
    """
    serendipity_scores = []

    for item_id in recommendations:
        # Relevance (binary: 1 if relevant, 0 otherwise)
        relevance = 1.0 if item_id in relevant_items else 0.0

        # Unexpectedness (inverse of popularity)
        popularity = item_popularity.get(item_id, 1)
        unexpectedness = 1 - (popularity / total_users)

        # Serendipity = relevance * unexpectedness
        serendipity = relevance * unexpectedness

        serendipity_scores.append(serendipity)

    return np.mean(serendipity_scores) if serendipity_scores else 0.0


def evaluate_diversity(
    all_recommendations: List[List[Movie]],
    all_relevant_items: List[List[str]],
    catalog_size: int,
    item_popularity: Dict[str, int],
    total_users: int,
) -> Dict[str, float]:
    """
    Calculate all diversity metrics.

    Args:
        all_recommendations: All recommendation lists (Movie objects).
        all_relevant_items: All relevant item lists (item IDs).
        catalog_size: Total catalog size.
        item_popularity: Item popularity counts.
        total_users: Total number of users.

    Returns:
        Dictionary of metric name -> score.
    """
    logger.info(f"Evaluating diversity metrics for {len(all_recommendations)} users")

    # Calculate intra-list diversity (average across all users)
    intra_diversities = []
    for rec_list in all_recommendations:
        diversity = intra_list_diversity(rec_list, diversity_metric="combined")
        intra_diversities.append(diversity)

    avg_intra_diversity = np.mean(intra_diversities) if intra_diversities else 0.0

    # Calculate catalog coverage
    all_rec_ids = [[str(m.metadata.tmdb_id) for m in recs] for recs in all_recommendations]
    coverage = catalog_coverage(all_rec_ids, catalog_size)

    # Calculate Gini index
    item_counts = Counter()
    for rec_ids in all_rec_ids:
        item_counts.update(rec_ids)

    gini = gini_index(dict(item_counts))

    # Calculate average novelty
    novelties = []
    for rec_ids in all_rec_ids:
        novelty = novelty_score(rec_ids, item_popularity, total_users)
        novelties.append(novelty)

    avg_novelty = np.mean(novelties) if novelties else 0.0

    # Calculate average serendipity
    serendipities = []
    for rec_ids, rel_items in zip(all_rec_ids, all_relevant_items):
        serendipity = serendipity_score(rec_ids, rel_items, item_popularity, total_users)
        serendipities.append(serendipity)

    avg_serendipity = np.mean(serendipities) if serendipities else 0.0

    metrics = {
        "intra_list_diversity": avg_intra_diversity,
        "catalog_coverage": coverage,
        "gini_index": gini,
        "novelty": avg_novelty,
        "serendipity": avg_serendipity,
    }

    logger.info(f"Diversity metrics: {metrics}")

    return metrics
