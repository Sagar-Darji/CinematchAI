#!/usr/bin/env python3
"""CineMatch AI AutoResearch — Autonomous Parameter Optimization Loop.

Inspired by Karpathy's autoresearch: an AI agent iteratively modifies
``autoresearch/params.py``, the evaluator runs the recommendation pipeline,
and improvements are kept while regressions are reverted.

Usage:
    python -m autoresearch.run                          # default: 20 experiments
    python -m autoresearch.run --experiments 50          # longer run
    python -m autoresearch.run --provider anthropic      # use Claude as the AI agent
    python -m autoresearch.run --provider groq           # use Groq/Llama (free)
    python -m autoresearch.run --provider ollama         # use local Ollama

The loop:
    1. AI agent reads current params.py + experiment history
    2. AI agent proposes a small change (1-3 params) with a hypothesis
    3. Evaluator runs the recommendation pipeline
    4. If composite_score improved → KEEP (git commit)
    5. If composite_score declined → REVERT (git checkout)
    6. Log result and repeat
"""

import os
import sys
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Force SQLite mode (no Postgres dependency)
os.environ.pop("AUTH_DATABASE_URL", None)
os.environ.pop("DATABASE_URL", None)

# Force Ollama for pipeline LLM calls to avoid Groq rate limits
# The autoresearch AI agent can still use any provider separately
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_MODEL_MAIN"] = "llama3.1:8b"
os.environ["OLLAMA_MODEL_FAST"] = "llama3.1:8b"

_root = str(Path(__file__).parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

PARAMS_FILE = Path(__file__).parent / "params.py"
LOG_FILE = Path(__file__).parent / "log.jsonl"
BEST_FILE = Path(__file__).parent / "best_params.py"
PROGRAM_FILE = Path(__file__).parent / "program.md"


def read_file(path: Path) -> str:
    return path.read_text()


def write_file(path: Path, content: str):
    path.write_text(content)


def backup_params():
    """Save a copy of params.py before experiment."""
    shutil.copy2(PARAMS_FILE, PARAMS_FILE.with_suffix(".py.bak"))


def revert_params():
    """Restore params.py from backup."""
    bak = PARAMS_FILE.with_suffix(".py.bak")
    if bak.exists():
        shutil.copy2(bak, PARAMS_FILE)


def save_best(score: float):
    """Copy current params.py to best_params.py."""
    shutil.copy2(PARAMS_FILE, BEST_FILE)
    print(f"  ★ New best score: {score:.6f} → saved to best_params.py")


def log_experiment(entry: Dict):
    """Append one JSON line to log.jsonl."""
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(last_n: int = 10) -> str:
    """Load last N experiments from log for the AI agent's context."""
    if not LOG_FILE.exists():
        return "No experiments yet."

    lines = LOG_FILE.read_text().strip().split("\n")
    recent = lines[-last_n:]

    summaries = []
    for line in recent:
        try:
            e = json.loads(line)
            status = "✓ KEPT" if e.get("kept") else "✗ REVERTED"
            summaries.append(
                f"  Exp #{e['experiment_id']}: {status} | "
                f"score={e['composite_score']:.6f} (Δ{e.get('delta', 0):+.6f}) | "
                f"{e.get('experiment_note', 'no note')}"
            )
        except json.JSONDecodeError:
            continue

    return "\n".join(summaries) if summaries else "No experiments yet."


# ---------------------------------------------------------------------------
# AI Agent Providers
# ---------------------------------------------------------------------------

def _call_anthropic(prompt: str) -> str:
    """Call Claude API."""
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_groq_fast(prompt: str) -> str:
    """Call Groq API with Llama 3.1 8B (faster, less rate-limited)."""
    from groq import Groq
    from config.settings import get_settings
    api_key = os.environ.get("GROQ_API_KEY") or get_settings().groq_api_key
    client = Groq(api_key=api_key)
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"  ⏳ Rate limited, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
            else:
                raise


def _call_groq(prompt: str) -> str:
    """Call Groq API (Llama) with retry on rate limit."""
    from groq import Groq
    from config.settings import get_settings
    api_key = os.environ.get("GROQ_API_KEY") or get_settings().groq_api_key
    client = Groq(api_key=api_key)
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "429" in str(e) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"  ⏳ Rate limited, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
            else:
                raise


def _call_ollama(prompt: str) -> str:
    """Call local Ollama with extended timeout for large prompts."""
    import requests
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1:8b",
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 8192},
        },
        timeout=600,
    )
    return resp.json()["response"]


PROVIDERS = {
    "anthropic": _call_anthropic,
    "groq": _call_groq,
    "groq_fast": _call_groq_fast,
    "ollama": _call_ollama,
}


# ---------------------------------------------------------------------------
# The AI Agent Prompt
# ---------------------------------------------------------------------------

def build_agent_prompt(
    current_params: str,
    history: str,
    best_score: float,
    current_score: float,
    experiment_id: int,
) -> str:
    """Build the prompt that tells the AI agent what to do."""

    program = ""
    if PROGRAM_FILE.exists():
        program = read_file(PROGRAM_FILE)

    return f"""You are an autonomous AI researcher optimizing the CineMatch AI
movie recommendation system. Your goal is to maximize the composite quality
score by tuning parameters in params.py.

{program}

## Current params.py
```python
{current_params}
```

## Experiment History (recent)
{history}

## Current State
- Best score so far: {best_score:.6f}
- Last score: {current_score:.6f}
- Experiment #{experiment_id}

## Your Task
1. Analyze the history — which changes helped? which hurt?
2. Form a hypothesis about what to change next
3. Change 1-3 parameters (stay within documented [min, max] ranges)
4. Update EXPERIMENT_NOTE with your hypothesis

## Rules
- Output ONLY the complete new params.py file content
- Do NOT change key names — only values
- Do NOT add or remove keys
- Change 1-3 params per experiment (small, testable diffs)
- Be strategic: if recent experiments failed, try a different direction
- Start with high-impact params (content scoring, retrieval ratios)
- Use the [min, max] ranges in the comments as bounds

## Output
Return the COMPLETE params.py file (everything from the docstring to the
closing brace). No markdown fences, no explanation — just the Python code.
"""


def extract_params_code(response: str) -> str:
    """Extract Python code from AI response, stripping markdown fences."""
    text = response.strip()

    # Remove markdown code fences if present
    if text.startswith("```python"):
        text = text[len("```python"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    # Validate it looks like params.py
    if "PARAMS" not in text or "EXPERIMENT_NOTE" not in text:
        raise ValueError("AI response doesn't contain valid params.py content")

    # Try to compile it
    compile(text, "params.py", "exec")

    return text


def extract_json_diff(response: str) -> dict:
    """Extract JSON diff from AI response for Ollama/small models.

    Expected format:
    {"note": "hypothesis", "changes": {"param.key": new_value, ...}}
    """
    text = response.strip()

    # Remove markdown fences
    if "```json" in text:
        text = text[text.index("```json") + 7:]
    elif "```" in text:
        text = text[text.index("```") + 3:]
    if text.endswith("```"):
        text = text[:-3]

    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON found in AI response")

    return json.loads(text[start:end])


def apply_json_diff(diff: dict) -> str:
    """Apply a JSON diff to current params.py and return new content."""
    current = read_file(PARAMS_FILE)

    # Load current params
    ns = {}
    exec(compile(current, "params.py", "exec"), ns)
    params = ns["PARAMS"]

    # Apply changes (with range enforcement from _PARAM_GROUPS)
    changes = diff.get("changes", {})
    # Build range lookup
    ranges = {}
    for group_params in _PARAM_GROUPS.values():
        for key, lo, hi in group_params:
            ranges[key] = (lo, hi)

    for key, value in changes.items():
        if key in params:
            # Clamp to valid range if known
            if key in ranges:
                lo, hi = ranges[key]
                if isinstance(value, (int, float)):
                    value = max(lo, min(hi, value))
            params[key] = value

    # Rebuild params.py with updated values
    note = diff.get("note", "no note")
    lines = current.split("\n")
    new_lines = []
    for line in lines:
        # Update EXPERIMENT_NOTE
        if line.strip().startswith("EXPERIMENT_NOTE"):
            new_lines.append(f'EXPERIMENT_NOTE = "{note}"')
            continue

        # Update param values
        matched = False
        for key, value in changes.items():
            # Match lines like: "content.genre_match_per_genre":  0.12,
            if f'"{key}"' in line and ":" in line:
                # Preserve the comment
                comment_idx = line.find("#")
                comment = line[comment_idx:] if comment_idx > 0 else ""
                # Rebuild line
                prefix = line[:line.index(":") + 1]
                val_str = f"{value}" if isinstance(value, int) else f"{value}"
                padding = max(1, 40 - len(prefix) - len(val_str) - 1)
                new_lines.append(f"{prefix}{' ' * padding}{val_str},{' ' * max(1, 5 - len(str(value)))}{comment}")
                matched = True
                break
        if not matched:
            new_lines.append(line)

    return "\n".join(new_lines)


import random

# Parameter groups for directed exploration (with valid [min, max] ranges)
_PARAM_GROUPS = {
    "retrieval": [
        ("retrieval.base_db_ratio", 0.6, 0.9),
        ("retrieval.context_blend_history", 0.5, 0.8),
        ("retrieval.context_blend_current", 0.2, 0.5),
        ("retrieval.cf_fraction", 0.15, 0.35),
        ("retrieval.cf_weight_multiplier", 0.7, 1.0),
        ("retrieval.genre_boost", 0.1, 0.5),
        ("retrieval.exploration_influence", 0.2, 0.5),
        ("retrieval.nl_context_impact", 0.1, 0.25),
        ("retrieval.avoid_genre_penalty", 0.3, 0.7),
    ],
    "content_scoring": [
        ("content.genre_match_per_genre", 0.05, 0.2),
        ("content.genre_match_cap", 0.15, 0.35),
        ("content.base_score", 0.3, 0.7),
        ("content.tone_mood_factor", 0.1, 0.5),
        ("content.tone_mood_baseline", 0.2, 0.6),
        ("content.director_affinity_boost", 0.1, 0.2),
        ("content.actor_hit_weight", 0.05, 0.1),
        ("content.actor_hit_cap", 0.1, 0.2),
        ("content.keyword_hit_weight", 0.02, 0.1),
        ("content.keyword_hit_cap", 0.1, 0.25),
        ("content.min_score_threshold", 0.2, 0.5),
    ],
    "language_nostalgia": [
        ("content.lang_first_bonus", 0.08, 0.15),
        ("content.lang_rank_decay", 0.02, 0.06),
        ("content.lang_min_bonus", 0.02, 0.06),
        ("content.foreign_lang_penalty", 0.03, 0.1),
        ("content.nostalgia_weight", 0.1, 0.3),
        ("content.nostalgia_norm", 30.0, 60.0),
        ("content.sequel_penalty", 0.05, 0.15),
    ],
    "serendipity": [
        ("serendipity.default_exploration_rate", 0.1, 0.5),
        ("serendipity.genre_sim_weight", 0.4, 0.8),
        ("serendipity.year_sim_weight", 0.2, 0.6),
        ("serendipity.year_norm", 30.0, 70.0),
        ("serendipity.exploration_genre_overlap", 0.2, 0.5),
    ],
    "critic": [
        ("critic.quality_floor", 4.5, 6.5),
        ("critic.quality_min_votes", 100, 500),
        ("critic.fail_threshold", 1, 3),
        ("critic.min_keep_floor", 3, 8),
        ("critic.filter_bubble_count", 2, 4),
    ],
    "context_weights": [
        ("content.cw_family_boost", 0.1, 0.3),
        ("content.cw_family_penalty", 0.15, 0.4),
        ("content.cw_romance", 0.08, 0.15),
        ("content.cw_atmospheric", 0.08, 0.15),
        ("content.cw_lighthearted_comedy", 0.1, 0.2),
        ("content.cw_thought_provoking", 0.08, 0.15),
        ("content.cw_uplifting", 0.06, 0.15),
    ],
    "profile": [
        ("profile.disliked_rating_threshold", 2.0, 3.0),
        ("profile.exploration_rate_norm", 15.0, 30.0),
        ("profile.exploration_rate_cap", 0.3, 0.7),
        ("profile.risk_tolerance_offset", 0.2, 0.4),
        ("profile.time_decay_factor", -0.005, -0.001),
    ],
}


def build_compact_prompt(
    current_params_dict: dict,
    history: str,
    best_score: float,
    current_score: float,
    experiment_id: int,
) -> str:
    """Build a compact prompt for smaller models (Ollama 8B).

    Rotates focus areas to encourage exploration diversity.
    """
    # Rotate focus area based on experiment
    group_names = list(_PARAM_GROUPS.keys())
    focus_group = group_names[experiment_id % len(group_names)]
    focus_params = _PARAM_GROUPS[focus_group]

    # Also pick a random secondary group for diversity
    other_groups = [g for g in group_names if g != focus_group]
    secondary_group = random.choice(other_groups)
    secondary_params = random.sample(
        _PARAM_GROUPS[secondary_group],
        min(2, len(_PARAM_GROUPS[secondary_group]))
    )

    all_focus = focus_params + secondary_params

    param_lines = []
    for key, lo, hi in all_focus:
        val = current_params_dict.get(key, "?")
        param_lines.append(f"  {key}: {val}  (range: [{lo}, {hi}])")
    params_str = "\n".join(param_lines)

    return f"""You optimize a movie recommendation system by tuning parameters.
Score is 0-1 (higher=better), composed of genre_alignment(25%), personalization(20%), quality(20%), diversity(20%), novelty(15%).

Focus area this experiment: {focus_group}

Parameters to consider:
{params_str}

History:
{history}

Best score: {best_score:.4f} | Last score: {current_score:.4f} | Experiment #{experiment_id}

IMPORTANT: Try a DIFFERENT strategy than recent failed experiments.
Change 1-2 parameters within their [min, max] range.
Output ONLY a JSON object, nothing else:
{{"note": "your hypothesis", "changes": {{"param.key": new_value}}}}

JSON:"""


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def run_autoresearch(
    n_experiments: int = 20,
    provider: str = "groq",
    n_users: int = 3,
    n_contexts: int = 2,
    k: int = 10,
):
    """Run the autoresearch loop."""

    call_llm = PROVIDERS.get(provider)
    if not call_llm:
        raise ValueError(f"Unknown provider: {provider}. Choose from: {list(PROVIDERS.keys())}")

    print("=" * 70)
    print("  CineMatch AI AutoResearch")
    print(f"  Provider: {provider} | Experiments: {n_experiments}")
    print(f"  Eval: {n_users} users × {n_contexts} contexts × top-{k}")
    print("=" * 70)

    # Step 0: Run baseline evaluation
    print("\n[0] Running baseline evaluation...")
    from autoresearch.evaluate import run_evaluation

    baseline = run_evaluation(n_users=n_users, k=k, n_contexts=n_contexts)
    best_score = baseline["composite_score"]
    current_score = best_score

    log_experiment({
        "experiment_id": 0,
        "timestamp": datetime.now().isoformat(),
        "composite_score": best_score,
        "delta": 0.0,
        "metrics": baseline["metrics"],
        "kept": True,
        "experiment_note": "baseline",
        "elapsed_seconds": baseline["elapsed_seconds"],
    })

    save_best(best_score)
    print(f"  Baseline score: {best_score:.6f}")
    print(f"  Metrics: {json.dumps(baseline['metrics'], indent=2)}")

    # Main loop
    kept_count = 0
    for exp_id in range(1, n_experiments + 1):
        # Pace experiments to avoid rate limits (only needed for Groq pipeline)
        if exp_id > 1 and provider not in ("ollama",):
            print("  ⏳ Cooling down 60s to avoid rate limits...")
            time.sleep(60)
        print(f"\n{'─' * 70}")
        print(f"[{exp_id}/{n_experiments}] Experiment starting...")

        # 1. Build prompt with current state
        current_params = read_file(PARAMS_FILE)
        history = load_history(last_n=15)
        use_compact = provider in ("ollama",)  # JSON-diff mode for small models

        if use_compact:
            # Load current PARAMS dict for compact prompt
            ns = {}
            exec(compile(current_params, "params.py", "exec"), ns)
            prompt = build_compact_prompt(
                current_params_dict=ns["PARAMS"],
                history=history,
                best_score=best_score,
                current_score=current_score,
                experiment_id=exp_id,
            )
        else:
            prompt = build_agent_prompt(
                current_params=current_params,
                history=history,
                best_score=best_score,
                current_score=current_score,
                experiment_id=exp_id,
            )

        # 2. Ask AI agent for new params
        print("  Asking AI agent for parameter changes...")
        try:
            response = call_llm(prompt)
            if use_compact:
                diff = extract_json_diff(response)
                new_code = apply_json_diff(diff)
            else:
                new_code = extract_params_code(response)
        except Exception as e:
            print(f"  ✗ AI agent error: {e}")
            log_experiment({
                "experiment_id": exp_id,
                "timestamp": datetime.now().isoformat(),
                "composite_score": current_score,
                "delta": 0.0,
                "metrics": {},
                "kept": False,
                "experiment_note": f"AI error: {e}",
                "elapsed_seconds": 0,
            })
            continue

        # 3. Backup & write new params
        backup_params()
        write_file(PARAMS_FILE, new_code)

        # Read the experiment note
        try:
            ns = {}
            exec(compile(new_code, "params.py", "exec"), ns)
            note = ns.get("EXPERIMENT_NOTE", "no note")
        except Exception:
            note = "parse error"

        print(f"  Hypothesis: {note}")

        # 4. Evaluate
        print("  Evaluating...")
        try:
            result = run_evaluation(n_users=n_users, k=k, n_contexts=n_contexts)
            new_score = result["composite_score"]
        except Exception as e:
            print(f"  ✗ Evaluation error: {e}")
            revert_params()
            log_experiment({
                "experiment_id": exp_id,
                "timestamp": datetime.now().isoformat(),
                "composite_score": current_score,
                "delta": 0.0,
                "metrics": {},
                "kept": False,
                "experiment_note": f"Eval error: {e}",
                "elapsed_seconds": 0,
            })
            continue

        delta = new_score - current_score

        # 5. Keep or revert
        if new_score >= current_score:
            # KEEP
            current_score = new_score
            kept_count += 1
            kept = True
            status = "✓ KEPT"

            if new_score > best_score:
                best_score = new_score
                save_best(best_score)
        else:
            # REVERT
            revert_params()
            kept = False
            status = "✗ REVERTED"

        print(f"  {status} | score={new_score:.6f} (Δ{delta:+.6f}) | best={best_score:.6f}")
        print(f"  Metrics: genre={result['metrics']['genre_alignment']:.4f} "
              f"person={result['metrics']['personalization']:.4f} "
              f"quality={result['metrics']['quality']:.4f} "
              f"diversity={result['metrics']['diversity']:.4f} "
              f"novelty={result['metrics']['novelty']:.4f}")
        print(f"  Time: {result['elapsed_seconds']}s")

        log_experiment({
            "experiment_id": exp_id,
            "timestamp": datetime.now().isoformat(),
            "composite_score": new_score,
            "delta": delta,
            "metrics": result["metrics"],
            "kept": kept,
            "experiment_note": note,
            "elapsed_seconds": result["elapsed_seconds"],
        })

    # Summary
    print("\n" + "=" * 70)
    print("  AUTORESEARCH COMPLETE")
    print(f"  Experiments: {n_experiments}")
    print(f"  Kept: {kept_count}/{n_experiments} ({100*kept_count/max(n_experiments,1):.0f}%)")
    print(f"  Baseline score: {baseline['composite_score']:.6f}")
    print(f"  Best score:     {best_score:.6f}")
    print(f"  Improvement:    {best_score - baseline['composite_score']:+.6f}")
    print(f"  Log: {LOG_FILE}")
    print(f"  Best params: {BEST_FILE}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="CineMatch AI AutoResearch Loop")
    parser.add_argument("--experiments", type=int, default=20, help="Number of experiments")
    parser.add_argument("--provider", choices=["anthropic", "groq", "groq_fast", "ollama"], default="groq",
                        help="AI agent provider")
    parser.add_argument("--users", type=int, default=3, help="Test users per evaluation")
    parser.add_argument("--contexts", type=int, default=2, help="Contexts per user (1-5)")
    parser.add_argument("--k", type=int, default=10, help="Top-K recommendations")
    args = parser.parse_args()

    run_autoresearch(
        n_experiments=args.experiments,
        provider=args.provider,
        n_users=args.users,
        n_contexts=args.contexts,
        k=args.k,
    )


if __name__ == "__main__":
    main()
