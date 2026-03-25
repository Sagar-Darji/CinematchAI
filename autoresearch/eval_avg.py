#!/usr/bin/env python3
"""Run evaluation N times and return the average — reduces TMDB API variance."""
import os, sys, json
from pathlib import Path

os.environ.pop("AUTH_DATABASE_URL", None)
os.environ.pop("DATABASE_URL", None)
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_MODEL_MAIN"] = "llama3.1:8b"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from autoresearch.evaluate import run_evaluation
import numpy as np

def eval_averaged(n_runs=3, n_contexts=3):
    all_scores = []
    all_metrics = {k: [] for k in ["genre_alignment", "personalization", "quality", "diversity", "novelty"]}

    for i in range(n_runs):
        r = run_evaluation(n_users=1, k=10, n_contexts=n_contexts)
        all_scores.append(r["composite_score"])
        for k in all_metrics:
            all_metrics[k].append(r["metrics"][k])

    avg_score = float(np.mean(all_scores))
    avg_metrics = {k: round(float(np.mean(v)), 4) for k, v in all_metrics.items()}
    std = float(np.std(all_scores))

    print(f"  Composite: {avg_score:.6f} (±{std:.4f}, runs: {[f'{s:.4f}' for s in all_scores]})")
    for k, v in avg_metrics.items():
        print(f"  {k:>20}: {v:.4f}")
    return avg_score, avg_metrics

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    eval_averaged(n_runs=n)
