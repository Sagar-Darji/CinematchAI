#!/usr/bin/env python3
"""Live dashboard for autoresearch experiments.

Usage:
    python -m autoresearch.dashboard              # one-shot summary
    python -m autoresearch.dashboard --watch      # live refresh every 10s
"""

import json
import time
import argparse
from pathlib import Path

LOG_FILE = Path(__file__).parent / "log.jsonl"


def load_experiments():
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text().strip().split("\n"):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def print_dashboard(entries):
    if not entries:
        print("No experiments yet.")
        return

    print("\033[2J\033[H")  # Clear screen
    print("=" * 80)
    print("  CineMatch AI AutoResearch Dashboard")
    print("=" * 80)

    baseline = entries[0]["composite_score"] if entries else 0
    best = max(e["composite_score"] for e in entries)
    kept = sum(1 for e in entries[1:] if e.get("kept"))
    total = len(entries) - 1  # exclude baseline

    print(f"\n  Baseline: {baseline:.6f}  |  Best: {best:.6f}  |  "
          f"Improvement: {best - baseline:+.6f}")
    print(f"  Experiments: {total}  |  Kept: {kept}/{total} "
          f"({100*kept/max(total,1):.0f}%)")

    # Score progression chart (ASCII)
    print(f"\n  Score Progression:")
    scores = [e["composite_score"] for e in entries]
    min_s = min(scores) * 0.95
    max_s = max(scores) * 1.05
    rng = max_s - min_s if max_s > min_s else 1.0
    width = 50

    for i, e in enumerate(entries):
        s = e["composite_score"]
        bar_len = int((s - min_s) / rng * width)
        bar = "█" * bar_len
        status = "★" if s == best else ("✓" if e.get("kept") else "✗")
        label = f"#{e['experiment_id']:>3}"
        print(f"  {label} {status} {bar} {s:.6f}")

    # Recent experiments detail
    print(f"\n  Recent Experiments:")
    print(f"  {'#':>4} {'Status':<10} {'Score':>10} {'Delta':>10} {'Note'}")
    print(f"  {'─'*4} {'─'*10} {'─'*10} {'─'*10} {'─'*40}")

    for e in entries[-15:]:
        eid = e["experiment_id"]
        status = "BASELINE" if eid == 0 else ("✓ KEPT" if e.get("kept") else "✗ REVERT")
        score = e["composite_score"]
        delta = e.get("delta", 0.0)
        note = (e.get("experiment_note", "")[:40])
        print(f"  {eid:>4} {status:<10} {score:>10.6f} {delta:>+10.6f} {note}")

    # Best experiment details
    best_entry = max(entries, key=lambda e: e["composite_score"])
    if best_entry.get("metrics"):
        print(f"\n  Best Experiment #{best_entry['experiment_id']} Metrics:")
        for k, v in best_entry["metrics"].items():
            print(f"    {k}: {v:.4f}")

    print(f"\n  Last updated: {entries[-1].get('timestamp', 'unknown')}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Live refresh")
    parser.add_argument("--interval", type=int, default=10, help="Refresh interval (seconds)")
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                entries = load_experiments()
                print_dashboard(entries)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        entries = load_experiments()
        print_dashboard(entries)


if __name__ == "__main__":
    main()
