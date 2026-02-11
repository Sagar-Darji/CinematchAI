"""Accuracy Metrics - RMSE, MAE, Hit Rate, NDCG."""

import numpy as np
from typing import List, Dict, Tuple
from src.utils.logging import get_logger

logger = get_logger(__name__)


def rmse(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """
    Calculate Root Mean Squared Error.

    Args:
        predictions: Predicted ratings.
        actuals: Actual ratings.

    Returns:
        RMSE score.
    """
    if len(predictions) != len(actuals):
        raise ValueError("Predictions and actuals must have same length")

    mse = np.mean((predictions - actuals) ** 2)
    return np.sqrt(mse)


def mae(predictions: np.ndarray, actuals: np.ndarray) -> float:
    """
    Calculate Mean Absolute Error.

    Args:
        predictions: Predicted ratings.
        actuals: Actual ratings.

    Returns:
        MAE score.
    """
    if len(predictions) != len(actuals):
        raise ValueError("Predictions and actuals must have same length")

    return np.mean(np.abs(predictions - actuals))


def hit_rate_at_k(
    recommendations: List[List[str]],
    relevant_items: List[List[str]],
    k: int = 10,
) -> float:
    """
    Calculate Hit Rate@K.

    Hit Rate@K = (# users with at least 1 relevant item in top-K) / (# users)

    Args:
        recommendations: List of recommendation lists (movie IDs) for each user.
        relevant_items: List of relevant item lists for each user.
        k: Top-K to consider.

    Returns:
        Hit Rate@K score (0-1).
    """
    if len(recommendations) != len(relevant_items):
        raise ValueError("Recommendations and relevant_items must have same length")

    hits = 0

    for rec_list, rel_list in zip(recommendations, relevant_items):
        # Get top-K recommendations
        top_k = rec_list[:k]

        # Check if any relevant item is in top-K
        if any(item in rel_list for item in top_k):
            hits += 1

    return hits / len(recommendations) if recommendations else 0.0


def ndcg_at_k(
    recommendations: List[List[str]],
    relevance_scores: List[Dict[str, float]],
    k: int = 10,
) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain@K.

    NDCG@K measures ranking quality by considering position.

    Args:
        recommendations: List of recommendation lists for each user.
        relevance_scores: List of dicts mapping item_id -> relevance score.
        k: Top-K to consider.

    Returns:
        NDCG@K score (0-1).
    """
    if len(recommendations) != len(relevance_scores):
        raise ValueError("Recommendations and relevance_scores must have same length")

    ndcg_scores = []

    for rec_list, rel_dict in zip(recommendations, relevance_scores):
        # Get top-K recommendations
        top_k = rec_list[:k]

        # Calculate DCG
        dcg = 0.0
        for i, item_id in enumerate(top_k):
            relevance = rel_dict.get(item_id, 0.0)
            # DCG formula: rel / log2(i+2)
            dcg += relevance / np.log2(i + 2)

        # Calculate IDCG (ideal DCG)
        # Sort relevance scores in descending order
        ideal_relevances = sorted(rel_dict.values(), reverse=True)[:k]
        idcg = 0.0
        for i, relevance in enumerate(ideal_relevances):
            idcg += relevance / np.log2(i + 2)

        # Calculate NDCG
        if idcg > 0:
            ndcg = dcg / idcg
        else:
            ndcg = 0.0

        ndcg_scores.append(ndcg)

    return np.mean(ndcg_scores) if ndcg_scores else 0.0


def precision_at_k(
    recommendations: List[List[str]],
    relevant_items: List[List[str]],
    k: int = 10,
) -> float:
    """
    Calculate Precision@K.

    Precision@K = (# relevant items in top-K) / K

    Args:
        recommendations: List of recommendation lists for each user.
        relevant_items: List of relevant item lists for each user.
        k: Top-K to consider.

    Returns:
        Precision@K score (0-1).
    """
    if len(recommendations) != len(relevant_items):
        raise ValueError("Recommendations and relevant_items must have same length")

    precisions = []

    for rec_list, rel_list in zip(recommendations, relevant_items):
        # Get top-K recommendations
        top_k = rec_list[:k]

        # Count relevant items in top-K
        relevant_count = sum(1 for item in top_k if item in rel_list)

        precision = relevant_count / k if k > 0 else 0.0
        precisions.append(precision)

    return np.mean(precisions) if precisions else 0.0


def recall_at_k(
    recommendations: List[List[str]],
    relevant_items: List[List[str]],
    k: int = 10,
) -> float:
    """
    Calculate Recall@K.

    Recall@K = (# relevant items in top-K) / (# total relevant items)

    Args:
        recommendations: List of recommendation lists for each user.
        relevant_items: List of relevant item lists for each user.
        k: Top-K to consider.

    Returns:
        Recall@K score (0-1).
    """
    if len(recommendations) != len(relevant_items):
        raise ValueError("Recommendations and relevant_items must have same length")

    recalls = []

    for rec_list, rel_list in zip(recommendations, relevant_items):
        # Get top-K recommendations
        top_k = rec_list[:k]

        # Count relevant items in top-K
        relevant_count = sum(1 for item in top_k if item in rel_list)

        # Calculate recall
        recall = relevant_count / len(rel_list) if rel_list else 0.0
        recalls.append(recall)

    return np.mean(recalls) if recalls else 0.0


def evaluate_accuracy(
    recommendations: List[List[str]],
    relevant_items: List[List[str]],
    relevance_scores: List[Dict[str, float]],
    k: int = 10,
) -> Dict[str, float]:
    """
    Calculate all accuracy metrics.

    Args:
        recommendations: List of recommendation lists for each user.
        relevant_items: List of relevant item lists for each user.
        relevance_scores: List of dicts mapping item_id -> relevance score.
        k: Top-K to consider.

    Returns:
        Dictionary of metric name -> score.
    """
    logger.info(f"Evaluating accuracy metrics for {len(recommendations)} users, k={k}")

    metrics = {
        "hit_rate": hit_rate_at_k(recommendations, relevant_items, k=k),
        "ndcg": ndcg_at_k(recommendations, relevance_scores, k=k),
        "precision": precision_at_k(recommendations, relevant_items, k=k),
        "recall": recall_at_k(recommendations, relevant_items, k=k),
    }

    logger.info(f"Accuracy metrics: {metrics}")

    return metrics
