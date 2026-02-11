"""Explainability Metrics - Evaluate quality of explanations."""

import numpy as np
from typing import List, Dict
from src.utils.logging import get_logger

logger = get_logger(__name__)


def explanation_length_score(explanations: List[str]) -> Dict[str, float]:
    """
    Analyze explanation lengths.

    Args:
        explanations: List of explanation strings.

    Returns:
        Dict with length statistics.
    """
    lengths = [len(exp.split()) for exp in explanations if exp]

    if not lengths:
        return {"avg_length": 0.0, "min_length": 0, "max_length": 0}

    return {
        "avg_length": np.mean(lengths),
        "min_length": int(np.min(lengths)),
        "max_length": int(np.max(lengths)),
        "std_length": np.std(lengths),
    }


def explanation_keyword_coverage(
    explanations: List[str],
    expected_keywords: List[str],
) -> float:
    """
    Calculate how many explanations contain expected keywords.

    Args:
        explanations: List of explanation strings.
        expected_keywords: Keywords that should appear (e.g., "genre", "director").

    Returns:
        Coverage score (0-1).
    """
    if not explanations or not expected_keywords:
        return 0.0

    coverage_counts = []

    for exp in explanations:
        exp_lower = exp.lower()
        # Count how many keywords appear
        keyword_count = sum(1 for kw in expected_keywords if kw.lower() in exp_lower)
        coverage = keyword_count / len(expected_keywords)
        coverage_counts.append(coverage)

    return np.mean(coverage_counts) if coverage_counts else 0.0


def explanation_diversity(explanations: List[str]) -> float:
    """
    Calculate diversity of explanations (how varied they are).

    Uses word-level overlap (Jaccard distance).

    Args:
        explanations: List of explanation strings.

    Returns:
        Diversity score (0-1, higher = more diverse).
    """
    if len(explanations) < 2:
        return 0.0

    # Tokenize explanations
    tokenized = [set(exp.lower().split()) for exp in explanations if exp]

    if len(tokenized) < 2:
        return 0.0

    # Calculate pairwise Jaccard distances
    distances = []

    for i, tokens1 in enumerate(tokenized):
        for tokens2 in tokenized[i + 1 :]:
            if not tokens1 or not tokens2:
                continue

            intersection = len(tokens1 & tokens2)
            union = len(tokens1 | tokens2)

            # Jaccard distance = 1 - Jaccard similarity
            distance = 1 - (intersection / union if union > 0 else 0)
            distances.append(distance)

    return np.mean(distances) if distances else 0.0


def explanation_specificity(explanations: List[str]) -> float:
    """
    Calculate specificity of explanations.

    Specific explanations contain concrete details (names, numbers).

    Args:
        explanations: List of explanation strings.

    Returns:
        Specificity score (0-1).
    """
    # Heuristic: count specific indicators
    specific_indicators = [
        "director",
        "actor",
        "rated",
        "year",
        "genre",
        "similar to",
        "loved",
        "enjoyed",
        "rated",
        "%",
        "/10",
    ]

    specificity_scores = []

    for exp in explanations:
        if not exp:
            continue

        exp_lower = exp.lower()

        # Count specific indicators
        count = sum(1 for indicator in specific_indicators if indicator in exp_lower)

        # Normalize by length (avoid penalizing short explanations)
        word_count = len(exp.split())
        specificity = min(count / max(word_count / 10, 1), 1.0)

        specificity_scores.append(specificity)

    return np.mean(specificity_scores) if specificity_scores else 0.0


def evaluate_explainability(
    explanations: List[str],
    expected_keywords: List[str] = None,
) -> Dict[str, float]:
    """
    Calculate all explainability metrics.

    Args:
        explanations: List of explanation strings.
        expected_keywords: Optional expected keywords.

    Returns:
        Dictionary of metric name -> score.
    """
    logger.info(f"Evaluating explainability for {len(explanations)} explanations")

    # Default expected keywords
    if expected_keywords is None:
        expected_keywords = [
            "genre",
            "director",
            "similar",
            "love",
            "enjoy",
            "preference",
            "context",
            "mood",
        ]

    # Length statistics
    length_stats = explanation_length_score(explanations)

    # Other metrics
    metrics = {
        "avg_length": length_stats["avg_length"],
        "keyword_coverage": explanation_keyword_coverage(explanations, expected_keywords),
        "diversity": explanation_diversity(explanations),
        "specificity": explanation_specificity(explanations),
    }

    logger.info(f"Explainability metrics: {metrics}")

    return metrics
