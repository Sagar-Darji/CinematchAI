"""Evaluation Metrics Module."""

from evaluation.metrics.accuracy import (
    evaluate_accuracy,
    hit_rate_at_k,
    mae,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    rmse,
)
from evaluation.metrics.diversity import (
    catalog_coverage,
    evaluate_diversity,
    gini_index,
    intra_list_diversity,
    novelty_score,
    serendipity_score,
)
from evaluation.metrics.explainability import (
    evaluate_explainability,
    explanation_diversity,
    explanation_keyword_coverage,
    explanation_length_score,
    explanation_specificity,
)

__all__ = [
    # Accuracy
    "evaluate_accuracy",
    "hit_rate_at_k",
    "mae",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "rmse",
    # Diversity
    "catalog_coverage",
    "evaluate_diversity",
    "gini_index",
    "intra_list_diversity",
    "novelty_score",
    "serendipity_score",
    # Explainability
    "evaluate_explainability",
    "explanation_diversity",
    "explanation_keyword_coverage",
    "explanation_length_score",
    "explanation_specificity",
]
