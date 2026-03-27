"""Benchmark runner that orchestrates all benchmark executions."""

import sys

from agenticpumark.benchmarks import ALL_BENCHMARKS, THREADED_BENCHMARKS
from agenticpumark.benchmarks.base import BenchmarkResult


class BenchmarkRunner:
    """Orchestrates benchmark execution."""

    def __init__(
        self,
        iterations: int = 5,
        max_threads: int = 8,
        verbose: bool = False,
    ):
        self.iterations = iterations
        self.max_threads = max_threads
        self.verbose = verbose

    def run(self, benchmark_name: str | None = None) -> list[BenchmarkResult]:
        """Run benchmarks and return results.

        Args:
            benchmark_name: If provided, run only this benchmark. Otherwise run all.
        """
        if benchmark_name:
            if benchmark_name not in ALL_BENCHMARKS:
                print(
                    f"Unknown benchmark: {benchmark_name}\n"
                    f"Available: {', '.join(ALL_BENCHMARKS.keys())}",
                    file=sys.stderr,
                )
                sys.exit(1)
            benchmarks_to_run = {benchmark_name: ALL_BENCHMARKS[benchmark_name]}
        else:
            benchmarks_to_run = ALL_BENCHMARKS

        results: list[BenchmarkResult] = []

        for name, bench_class in benchmarks_to_run.items():
            if self.verbose:
                print(f"Running {name} (warm-up + timed)...", file=sys.stderr)

            if bench_class in THREADED_BENCHMARKS:
                bench = bench_class(max_threads=self.max_threads)
            else:
                bench = bench_class()

            result = bench.run(iterations=self.iterations)
            results.append(result)

            if self.verbose:
                s = result.stats
                print(
                    f"  {name}: {s.median:.3f}s "
                    f"(mean={s.mean:.3f}s, stddev={s.stddev:.3f}s, "
                    f"CV={s.cv:.1%}, runs={len(result.iterations)})",
                    file=sys.stderr,
                )

        return results
