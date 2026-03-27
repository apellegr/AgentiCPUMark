"""Scoring system for AgentiCPUMark.

Scores are normalized against reference timings from a baseline system
(AMD Ryzen 9 7950X, Python 3.12, Linux). A score of 1000 means the system
matches the reference. Higher is better.
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
}

REFERENCE_SCORE = 1000

WEIGHTS: dict[str, float] = {
    "context_switching": 0.15,
    "json_processing": 0.20,
    "text_processing": 0.20,
    "tree_search": 0.20,
    "concurrent_dispatch": 0.15,
    "memory_pressure": 0.10,
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


def compute_composite_score(results: list[BenchmarkResult]) -> float:
    """Compute the weighted geometric mean composite score.

    Uses the geometric mean so that no single benchmark can dominate
    the composite score through outlier performance.
    """
    if not results:
        return 0.0

    log_sum = 0.0
    weight_sum = 0.0

    for result in results:
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
