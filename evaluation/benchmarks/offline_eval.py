"""Offline Evaluation - Benchmark CineMatch AI on MovieLens test set."""

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple

from config.settings import get_settings
from evaluation.metrics.accuracy import evaluate_accuracy
from evaluation.metrics.diversity import evaluate_diversity
from evaluation.metrics.explainability import evaluate_explainability
from src.agents.graph.workflow import run_recommendation_workflow
from src.core.models import Movie
from src.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class OfflineEvaluator:
    """Offline evaluation on MovieLens test set."""

    def __init__(self, test_size: int = 100, k: int = 10):
        """
        Initialize evaluator.

        Args:
            test_size: Number of test users.
            k: Top-K recommendations to evaluate.
        """
        self.test_size = test_size
        self.k = k
        self.results = {}

    def load_test_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load and split MovieLens data into train/test.

        Returns:
            Tuple of (train_df, test_df).
        """
        logger.info("Loading MovieLens data...")

        # Load ratings
        ratings_path = Path(settings.data_dir) / "processed" / "ratings.parquet"

        if not ratings_path.exists():
            raise FileNotFoundError(
                f"Ratings not found at {ratings_path}. Run setup_data.py first."
            )

        ratings_df = pd.read_parquet(ratings_path)

        logger.info(f"Loaded {len(ratings_df)} ratings from {len(ratings_df['userId'].unique())} users")

        # Split: 80% train, 20% test (temporal split)
        # Sort by timestamp
        ratings_df = ratings_df.sort_values("timestamp")

        # Split by user (ensure each user has both train and test)
        train_dfs = []
        test_dfs = []

        for user_id, user_ratings in ratings_df.groupby("userId"):
            n = len(user_ratings)
            split_idx = int(n * 0.8)

            train_dfs.append(user_ratings.iloc[:split_idx])
            test_dfs.append(user_ratings.iloc[split_idx:])

        train_df = pd.concat(train_dfs, ignore_index=True)
        test_df = pd.concat(test_dfs, ignore_index=True)

        logger.info(f"Train: {len(train_df)} ratings, Test: {len(test_df)} ratings")

        return train_df, test_df

    def get_test_users(self, test_df: pd.DataFrame) -> List[str]:
        """
        Get test user IDs.

        Args:
            test_df: Test ratings dataframe.

        Returns:
            List of user IDs.
        """
        # Get users with at least 5 test ratings
        user_counts = test_df["userId"].value_counts()
        valid_users = user_counts[user_counts >= 5].index.tolist()

        # Sample test users
        if len(valid_users) > self.test_size:
            np.random.seed(42)
            test_users = np.random.choice(valid_users, self.test_size, replace=False)
        else:
            test_users = valid_users

        logger.info(f"Selected {len(test_users)} test users")

        return [str(uid) for uid in test_users]

    def get_recommendations_for_user(self, user_id: str) -> Tuple[List[str], List[str]]:
        """
        Get recommendations for a user using CineMatch AI.

        Args:
            user_id: User ID.

        Returns:
            Tuple of (recommended_movie_ids, explanations).
        """
        try:
            # Run recommendation workflow
            final_state = run_recommendation_workflow(
                user_id=user_id,
                context={},
                is_cold_start=False,
            )

            # Extract recommendations
            final_recs = final_state.get("final_recommendations", [])

            if not final_recs:
                logger.warning(f"No recommendations for user {user_id}")
                return [], []

            # Get movie IDs and explanations
            movie_ids = [str(rec.movie.metadata.tmdb_id) for rec in final_recs]
            explanations = [rec.explanation for rec in final_recs]

            return movie_ids, explanations

        except Exception as e:
            logger.error(f"Failed to get recommendations for user {user_id}: {e}")
            return [], []

    def get_baseline_recommendations(
        self,
        user_id: str,
        train_df: pd.DataFrame,
        method: str = "popular",
    ) -> List[str]:
        """
        Get baseline recommendations.

        Args:
            user_id: User ID.
            train_df: Training data.
            method: Baseline method ("popular", "random").

        Returns:
            List of recommended movie IDs.
        """
        if method == "popular":
            # Recommend most popular movies (not already rated by user)
            user_rated = train_df[train_df["userId"] == int(user_id)]["movieId"].unique()

            # Count movie ratings
            movie_counts = train_df["movieId"].value_counts()

            # Filter out user-rated movies
            candidates = [m for m in movie_counts.index if m not in user_rated]

            # Return top-K popular
            return [str(m) for m in candidates[: self.k]]

        elif method == "random":
            # Random recommendations
            all_movies = train_df["movieId"].unique()
            user_rated = train_df[train_df["userId"] == int(user_id)]["movieId"].unique()

            candidates = [m for m in all_movies if m not in user_rated]

            if len(candidates) > self.k:
                np.random.seed(42)
                selected = np.random.choice(candidates, self.k, replace=False)
            else:
                selected = candidates

            return [str(m) for m in selected]

        else:
            return []

    def evaluate_system(
        self,
        test_users: List[str],
        test_df: pd.DataFrame,
        train_df: pd.DataFrame,
    ) -> Dict:
        """
        Evaluate CineMatch AI system.

        Args:
            test_users: List of test user IDs.
            test_df: Test dataframe.
            train_df: Train dataframe.

        Returns:
            Evaluation results.
        """
        logger.info(f"Evaluating CineMatch AI on {len(test_users)} users")

        all_recommendations = []
        all_relevant_items = []
        all_relevance_scores = []
        all_explanations = []
        all_rec_movies = []

        for i, user_id in enumerate(test_users):
            logger.info(f"Processing user {i+1}/{len(test_users)}: {user_id}")

            # Get recommendations
            rec_ids, explanations = self.get_recommendations_for_user(user_id)

            if not rec_ids:
                continue

            # Get ground truth (test ratings >= 4.0)
            user_test = test_df[test_df["userId"] == int(user_id)]
            relevant = user_test[user_test["rating"] >= 4.0]["movieId"].unique()
            relevant_ids = [str(m) for m in relevant]

            # Create relevance score dict (rating / 5.0)
            relevance_dict = {}
            for _, row in user_test.iterrows():
                relevance_dict[str(row["movieId"])] = row["rating"] / 5.0

            # Store results
            all_recommendations.append(rec_ids)
            all_relevant_items.append(relevant_ids)
            all_relevance_scores.append(relevance_dict)
            all_explanations.extend(explanations)

            # Note: For diversity metrics, we need Movie objects
            # For now, we'll skip diversity evaluation (would need to load movies)

        # Evaluate accuracy
        accuracy_metrics = evaluate_accuracy(
            recommendations=all_recommendations,
            relevant_items=all_relevant_items,
            relevance_scores=all_relevance_scores,
            k=self.k,
        )

        # Evaluate explainability
        explainability_metrics = evaluate_explainability(all_explanations)

        # Combine results
        results = {
            "system": "CineMatch AI",
            "test_users": len(test_users),
            "k": self.k,
            "accuracy": accuracy_metrics,
            "explainability": explainability_metrics,
        }

        return results

    def evaluate_baseline(
        self,
        test_users: List[str],
        test_df: pd.DataFrame,
        train_df: pd.DataFrame,
        method: str = "popular",
    ) -> Dict:
        """
        Evaluate baseline method.

        Args:
            test_users: Test user IDs.
            test_df: Test dataframe.
            train_df: Train dataframe.
            method: Baseline method.

        Returns:
            Evaluation results.
        """
        logger.info(f"Evaluating baseline: {method}")

        all_recommendations = []
        all_relevant_items = []
        all_relevance_scores = []

        for user_id in test_users:
            # Get baseline recommendations
            rec_ids = self.get_baseline_recommendations(user_id, train_df, method)

            if not rec_ids:
                continue

            # Get ground truth
            user_test = test_df[test_df["userId"] == int(user_id)]
            relevant = user_test[user_test["rating"] >= 4.0]["movieId"].unique()
            relevant_ids = [str(m) for m in relevant]

            # Relevance scores
            relevance_dict = {}
            for _, row in user_test.iterrows():
                relevance_dict[str(row["movieId"])] = row["rating"] / 5.0

            all_recommendations.append(rec_ids)
            all_relevant_items.append(relevant_ids)
            all_relevance_scores.append(relevance_dict)

        # Evaluate accuracy
        accuracy_metrics = evaluate_accuracy(
            recommendations=all_recommendations,
            relevant_items=all_relevant_items,
            relevance_scores=all_relevance_scores,
            k=self.k,
        )

        results = {
            "system": f"Baseline ({method})",
            "test_users": len(test_users),
            "k": self.k,
            "accuracy": accuracy_metrics,
        }

        return results

    def run_evaluation(self) -> Dict:
        """
        Run complete offline evaluation.

        Returns:
            Full evaluation results.
        """
        logger.info("="*60)
        logger.info("Starting Offline Evaluation")
        logger.info("="*60)

        # Load data
        train_df, test_df = self.load_test_data()

        # Get test users
        test_users = self.get_test_users(test_df)

        # Evaluate CineMatch AI
        cinematch_results = self.evaluate_system(test_users, test_df, train_df)

        # Evaluate baselines
        popular_results = self.evaluate_baseline(
            test_users, test_df, train_df, method="popular"
        )

        random_results = self.evaluate_baseline(
            test_users, test_df, train_df, method="random"
        )

        # Combine results
        results = {
            "timestamp": datetime.now().isoformat(),
            "test_size": len(test_users),
            "k": self.k,
            "systems": {
                "cinematch_ai": cinematch_results,
                "baseline_popular": popular_results,
                "baseline_random": random_results,
            },
        }

        # Save results
        self._save_results(results)

        # Print summary
        self._print_summary(results)

        return results

    def _save_results(self, results: Dict):
        """Save evaluation results to JSON."""
        output_dir = Path("evaluation/results")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"offline_eval_{timestamp}.json"

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    def _print_summary(self, results: Dict):
        """Print evaluation summary."""
        print("\n" + "="*60)
        print("EVALUATION RESULTS SUMMARY")
        print("="*60)

        for system_name, system_results in results["systems"].items():
            print(f"\n{system_results['system']}:")
            print(f"  Test Users: {system_results['test_users']}")
            print(f"  Top-K: {system_results['k']}")

            if "accuracy" in system_results:
                print("\n  Accuracy Metrics:")
                for metric, value in system_results["accuracy"].items():
                    print(f"    {metric}: {value:.4f}")

            if "explainability" in system_results:
                print("\n  Explainability Metrics:")
                for metric, value in system_results["explainability"].items():
                    print(f"    {metric}: {value:.4f}")

        print("\n" + "="*60)


def main():
    """Run offline evaluation."""
    evaluator = OfflineEvaluator(test_size=100, k=10)
    results = evaluator.run_evaluation()

    print("\n✅ Evaluation complete!")


if __name__ == "__main__":
    main()
