"""Performance Profiling - Identify bottlenecks and optimize."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import time
import cProfile
import pstats
from io import StringIO
from typing import Dict, List

from src.agents.graph.workflow import run_recommendation_workflow
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PerformanceProfiler:
    """Profile system performance and identify bottlenecks."""

    def __init__(self):
        """Initialize profiler."""
        self.results = {}

    def profile_recommendation_workflow(
        self,
        user_id: str = "test_user_123",
        num_runs: int = 10,
    ) -> Dict:
        """
        Profile the recommendation workflow.

        Args:
            user_id: User ID to test.
            num_runs: Number of runs for averaging.

        Returns:
            Profiling results.
        """
        logger.info(f"Profiling recommendation workflow ({num_runs} runs)...")

        # Warmup run
        logger.info("Warmup run...")
        run_recommendation_workflow(user_id=user_id, context={})

        # Timed runs
        durations = []

        for i in range(num_runs):
            start_time = time.time()

            final_state = run_recommendation_workflow(
                user_id=user_id,
                context={"time_of_day": "evening", "mood": "relaxed"},
            )

            duration = time.time() - start_time
            durations.append(duration)

            logger.info(f"Run {i+1}/{num_runs}: {duration:.3f}s")

        # Calculate statistics
        results = {
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "p50_duration": sorted(durations)[len(durations) // 2],
            "p95_duration": sorted(durations)[int(len(durations) * 0.95)],
            "p99_duration": sorted(durations)[int(len(durations) * 0.99)],
        }

        logger.info(f"Average duration: {results['avg_duration']:.3f}s")
        logger.info(f"P95 duration: {results['p95_duration']:.3f}s")

        return results

    def profile_detailed(self, user_id: str = "test_user_123"):
        """
        Detailed profiling with cProfile.

        Args:
            user_id: User ID to test.
        """
        logger.info("Running detailed profiling with cProfile...")

        # Create profiler
        profiler = cProfile.Profile()

        # Profile
        profiler.enable()
        run_recommendation_workflow(user_id=user_id, context={})
        profiler.disable()

        # Print stats
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(30)  # Top 30 functions

        print("\n" + "="*60)
        print("DETAILED PROFILING RESULTS (Top 30 Functions)")
        print("="*60)
        print(s.getvalue())

        # Save to file
        output_path = Path("evaluation/results/profile_stats.txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            ps = pstats.Stats(profiler, stream=f).sort_stats("cumulative")
            ps.print_stats()

        logger.info(f"Detailed profiling saved to {output_path}")

    def profile_agent_breakdown(self, user_id: str = "test_user_123") -> Dict:
        """
        Profile individual agent execution times.

        Args:
            user_id: User ID to test.

        Returns:
            Agent timing breakdown.
        """
        logger.info("Profiling individual agents...")

        # Run workflow and track processing steps
        final_state = run_recommendation_workflow(user_id=user_id, context={})

        processing_steps = final_state.get("processing_steps", [])

        print("\n" + "="*60)
        print("AGENT PROCESSING STEPS")
        print("="*60)

        for step in processing_steps:
            print(f"  ✓ {step}")

        print("="*60)

        return {"steps": processing_steps}

    def profile_memory_usage(self, user_id: str = "test_user_123") -> Dict:
        """
        Profile memory usage.

        Args:
            user_id: User ID to test.

        Returns:
            Memory usage stats.
        """
        logger.info("Profiling memory usage...")

        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())

            # Memory before
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Run workflow
            final_state = run_recommendation_workflow(user_id=user_id, context={})

            # Memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB

            mem_delta = mem_after - mem_before

            results = {
                "memory_before_mb": mem_before,
                "memory_after_mb": mem_after,
                "memory_delta_mb": mem_delta,
            }

            logger.info(f"Memory before: {mem_before:.2f} MB")
            logger.info(f"Memory after: {mem_after:.2f} MB")
            logger.info(f"Memory delta: {mem_delta:.2f} MB")

            return results

        except ImportError:
            logger.warning("psutil not installed, skipping memory profiling")
            return {}

    def run_full_profile(self):
        """Run complete performance profiling."""
        print("\n" + "="*60)
        print("CINEMATCH AI PERFORMANCE PROFILING")
        print("="*60)

        # Recommendation workflow timing
        workflow_results = self.profile_recommendation_workflow(num_runs=10)

        print("\n📊 Workflow Performance:")
        print(f"  Average: {workflow_results['avg_duration']:.3f}s")
        print(f"  P50: {workflow_results['p50_duration']:.3f}s")
        print(f"  P95: {workflow_results['p95_duration']:.3f}s")
        print(f"  P99: {workflow_results['p99_duration']:.3f}s")

        # Check against targets
        target_p95 = 2.0  # 2 seconds
        if workflow_results['p95_duration'] <= target_p95:
            print(f"  ✅ PASS: P95 <= {target_p95}s")
        else:
            print(f"  ❌ FAIL: P95 > {target_p95}s (target: {target_p95}s)")

        # Agent breakdown
        agent_results = self.profile_agent_breakdown()

        # Memory usage
        memory_results = self.profile_memory_usage()

        if memory_results:
            print("\n💾 Memory Usage:")
            print(f"  Before: {memory_results['memory_before_mb']:.2f} MB")
            print(f"  After: {memory_results['memory_after_mb']:.2f} MB")
            print(f"  Delta: {memory_results['memory_delta_mb']:.2f} MB")

            # Check against target
            target_mem = 14000  # 14GB in MB
            if memory_results['memory_after_mb'] <= target_mem:
                print(f"  ✅ PASS: Memory <= {target_mem} MB (14GB)")
            else:
                print(f"  ❌ FAIL: Memory > {target_mem} MB")

        # Detailed profiling
        print("\n🔍 Running detailed profiling...")
        self.profile_detailed()

        print("\n" + "="*60)
        print("PROFILING COMPLETE")
        print("="*60)
        print("\n📝 Optimization Recommendations:")
        print("  1. Check profile_stats.txt for bottlenecks")
        print("  2. Optimize slow functions (top of cumulative time)")
        print("  3. Add caching for frequently called functions")
        print("  4. Consider async/parallel execution where possible")
        print("  5. Optimize vector database queries (tune HNSW params)")
        print("="*60)


def main():
    """Run performance profiling."""
    profiler = PerformanceProfiler()
    profiler.run_full_profile()


if __name__ == "__main__":
    main()
