"""Scoring system for AgentiCPUMark.

Scores are normalized against reference timings from a baseline system
(AMD Ryzen 9 7950X, Python 3.12, Linux). A score of 1000 means the system
matches the reference. Higher is better.

Two composite scores are computed:
- Single-Agent Speed: weighted geometric mean of single-threaded benchmarks
- Multi-Agent Throughput: weighted geometric mean of multi-threaded benchmarks
- Overall Composite: weighted geometric mean of all benchmarks
"""

import math
from agenticpumark.benchmarks.base import BenchmarkResult

# Reference timings in seconds (AMD Ryzen 9 7950X baseline)
# These will be calibrated once the benchmark stabilizes.
# For now, use placeholder values that produce reasonable scores.
REFERENCE_TIMINGS: dict[str, float] = {
    "context_switching": 2.0,
    "json_processing": 1.5,
    "text_processing": 2.5,
    "tree_search": 3.0,
    "concurrent_dispatch": 2.0,
    "memory_pressure": 4.0,
    "subprocess_spawning": 5.0,
    "diff_patch": 2.0,
    "html_parsing": 1.5,
    "schema_validation": 2.0,
    "streaming_parse": 1.5,
    "code_edit_apply": 2.0,
}

REFERENCE_SCORE = 1000

# Weights for overall composite score (must sum to 1.0)
WEIGHTS: dict[str, float] = {
    "context_switching": 0.08,
    "json_processing": 0.12,
    "text_processing": 0.10,
    "tree_search": 0.10,
    "concurrent_dispatch": 0.08,
    "memory_pressure": 0.05,
    "subprocess_spawning": 0.10,
    "diff_patch": 0.08,
    "html_parsing": 0.07,
    "schema_validation": 0.06,
    "streaming_parse": 0.08,
    "code_edit_apply": 0.08,
}

# Benchmarks that are primarily single-threaded (measures single-agent speed)
SINGLE_AGENT_BENCHMARKS = {
    "json_processing", "text_processing", "tree_search",
    "diff_patch", "html_parsing", "schema_validation", "memory_pressure",
    "streaming_parse", "code_edit_apply",
}

# Benchmarks that are primarily multi-threaded (measures multi-agent throughput)
MULTI_AGENT_BENCHMARKS = {
    "context_switching", "concurrent_dispatch", "subprocess_spawning",
}


def compute_score(result: BenchmarkResult) -> float:
    """Compute the normalized score for a single benchmark result.

    Score = REFERENCE_SCORE * (reference_time / actual_time)
    A faster system gets a higher score.
    """
    ref_time = REFERENCE_TIMINGS.get(result.name, 1.0)
    if result.elapsed_seconds <= 0:
        return 0.0
    return REFERENCE_SCORE * (ref_time / result.elapsed_seconds)


def _weighted_geometric_mean(results: list[BenchmarkResult], benchmark_set: set[str] | None = None) -> float:
    """Compute the weighted geometric mean score for a subset of benchmarks."""
    log_sum = 0.0
    weight_sum = 0.0

    for result in results:
        if benchmark_set is not None and result.name not in benchmark_set:
            continue
        weight = WEIGHTS.get(result.name, 0.0)
        if weight <= 0:
            continue
        score = compute_score(result)
        if score <= 0:
            return 0.0
        log_sum += weight * math.log(score)
        weight_sum += weight

    if weight_sum <= 0:
        return 0.0

    return math.exp(log_sum / weight_sum)


def compute_composite_score(results: list[BenchmarkResult]) -> float:
    """Compute the overall weighted geometric mean composite score."""
    return _weighted_geometric_mean(results)


def compute_single_agent_score(results: list[BenchmarkResult]) -> float:
    """Compute the single-agent speed score (single-threaded benchmarks only)."""
    return _weighted_geometric_mean(results, SINGLE_AGENT_BENCHMARKS)


def compute_multi_agent_score(results: list[BenchmarkResult]) -> float:
    """Compute the multi-agent throughput score (multi-threaded benchmarks only)."""
    return _weighted_geometric_mean(results, MULTI_AGENT_BENCHMARKS)
