"""Report formatting for AgentiCPUMark results."""

import platform
import os
from agenticpumark import __version__
from agenticpumark.benchmarks.base import BenchmarkResult
from agenticpumark.scoring import (
    compute_score,
    compute_composite_score,
    compute_single_agent_score,
    compute_multi_agent_score,
)

W = 75  # report width


def _get_system_info() -> dict:
    """Gather system information for the report."""
    info = {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 0,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
    }
    # Try to get CPU model name on Linux
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return info


def print_report(results: list[BenchmarkResult], verbose: bool = False) -> None:
    """Print a formatted benchmark report to stdout."""
    sys_info = _get_system_info()

    print()
    print("=" * W)
    print(f"  AgentiCPUMark v{__version__}")
    print("  CPU Benchmark for AI Agentic Workloads")
    print("=" * W)
    print()
    cpu_model = sys_info.get("cpu_model", sys_info["processor"])
    print(f"  CPU:         {cpu_model}")
    print(f"  Cores:       {sys_info['cpu_count']}")
    print(f"  Platform:    {sys_info['platform']}")
    print(f"  Python:      {sys_info['python_version']}")
    print(f"  Arch:        {sys_info['architecture']}")
    print()
    print("-" * W)
    print(f"  {'Benchmark':<25} {'Time (s)':>8} {'StdDev':>8} {'CV':>7} {'Ops':>10} {'Score':>8}")
    print("-" * W)

    for result in results:
        score = compute_score(result)
        s = result.stats
        print(
            f"  {result.name:<25} {s.median:>8.3f} {s.stddev:>8.3f} {s.cv:>6.1%} "
            f"{result.ops_completed:>10,} {score:>8.0f}"
        )

        if verbose:
            print(
                f"    mean={s.mean:.3f}s  "
                f"95% CI=[{s.ci_95_low:.3f}, {s.ci_95_high:.3f}]  "
                f"min={s.min:.3f}s  max={s.max:.3f}s  "
                f"runs={len(result.iterations)}"
            )
            for i, t in enumerate(result.iterations):
                marker = " *" if t == s.median else ""
                print(f"      iter {i + 1}: {t:.4f}s{marker}")

    print("-" * W)

    single = compute_single_agent_score(results)
    multi = compute_multi_agent_score(results)
    composite = compute_composite_score(results)
    print()
    print(f"  {'Single-Agent Speed':>40}  {single:>8.0f}")
    print(f"  {'Multi-Agent Throughput':>40}  {multi:>8.0f}")
    print(f"  {'OVERALL COMPOSITE':>40}  {composite:>8.0f}")
    print()
    print("  (Reference: 1000 = AMD Ryzen 9 7950X | Higher is better)")
    print("=" * W)
    print()


def format_json_report(results: list[BenchmarkResult]) -> dict:
    """Format results as a JSON-serializable dictionary."""
    sys_info = _get_system_info()
    benchmarks = []

    for result in results:
        s = result.stats
        benchmarks.append({
            "name": result.name,
            "description": result.description,
            "elapsed_seconds": round(s.median, 4),
            "ops_completed": result.ops_completed,
            "score": round(compute_score(result), 1),
            "statistics": {
                "mean": round(s.mean, 4),
                "median": round(s.median, 4),
                "stddev": round(s.stddev, 4),
                "cv": round(s.cv, 4),
                "ci_95": [round(s.ci_95_low, 4), round(s.ci_95_high, 4)],
                "min": round(s.min, 4),
                "max": round(s.max, 4),
                "iterations": len(result.iterations),
            },
            "raw_times": [round(t, 4) for t in result.iterations],
        })

    return {
        "version": __version__,
        "system": sys_info,
        "benchmarks": benchmarks,
        "scores": {
            "single_agent_speed": round(compute_single_agent_score(results), 1),
            "multi_agent_throughput": round(compute_multi_agent_score(results), 1),
            "composite": round(compute_composite_score(results), 1),
        },
    }
