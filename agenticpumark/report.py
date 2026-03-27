"""Report formatting for AgentiCPUMark results."""

import platform
import os
from agenticpumark import __version__
from agenticpumark.benchmarks.base import BenchmarkResult
from agenticpumark.scoring import compute_score, compute_composite_score


def _get_system_info() -> dict:
    """Gather system information for the report."""
    return {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 0,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
    }


def print_report(results: list[BenchmarkResult], verbose: bool = False) -> None:
    """Print a formatted benchmark report to stdout."""
    sys_info = _get_system_info()

    print()
    print("=" * 65)
    print(f"  AgentiCPUMark v{__version__}")
    print("  CPU Benchmark for AI Agentic Workloads")
    print("=" * 65)
    print()
    print(f"  System:      {sys_info['platform']}")
    print(f"  Processor:   {sys_info['processor']}")
    print(f"  CPU Cores:   {sys_info['cpu_count']}")
    print(f"  Python:      {sys_info['python_version']}")
    print(f"  Arch:        {sys_info['architecture']}")
    print()
    print("-" * 65)
    print(f"  {'Benchmark':<25} {'Time (s)':>10} {'Ops':>10} {'Score':>10}")
    print("-" * 65)

    for result in results:
        score = compute_score(result)
        print(
            f"  {result.name:<25} {result.elapsed_seconds:>10.3f} "
            f"{result.ops_completed:>10,} {score:>10.0f}"
        )

        if verbose:
            for i, t in enumerate(result.iterations):
                print(f"    iteration {i + 1}: {t:.3f}s")

    print("-" * 65)

    composite = compute_composite_score(results)
    print()
    print(f"  {'COMPOSITE SCORE':>40}  {composite:>10.0f}")
    print()
    print("  (Reference: 1000 = AMD Ryzen 9 7950X | Higher is better)")
    print("=" * 65)
    print()


def format_json_report(results: list[BenchmarkResult]) -> dict:
    """Format results as a JSON-serializable dictionary."""
    sys_info = _get_system_info()
    benchmarks = []

    for result in results:
        benchmarks.append({
            "name": result.name,
            "description": result.description,
            "elapsed_seconds": round(result.elapsed_seconds, 4),
            "ops_completed": result.ops_completed,
            "score": round(compute_score(result), 1),
            "iterations": [round(t, 4) for t in result.iterations],
        })

    return {
        "version": __version__,
        "system": sys_info,
        "benchmarks": benchmarks,
        "composite_score": round(compute_composite_score(results), 1),
    }
