"""Base class for all benchmarks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import math
import statistics
import time


@dataclass
class BenchmarkStats:
    """Statistical summary of benchmark iterations."""

    mean: float
    median: float
    stddev: float
    cv: float  # coefficient of variation (stddev / mean)
    ci_95_low: float  # 95% confidence interval lower bound
    ci_95_high: float  # 95% confidence interval upper bound
    min: float
    max: float

    @classmethod
    def from_times(cls, times: list[float]) -> "BenchmarkStats":
        n = len(times)
        mean = statistics.mean(times)
        median = statistics.median(times)
        stddev = statistics.stdev(times) if n > 1 else 0.0
        cv = stddev / mean if mean > 0 else 0.0
        # 95% CI using t-distribution approximation (1.96 for large n, ~2.0 for small)
        t_value = 2.776 if n <= 5 else (2.262 if n <= 10 else 1.96)
        margin = t_value * (stddev / math.sqrt(n)) if n > 1 else 0.0
        return cls(
            mean=mean,
            median=median,
            stddev=stddev,
            cv=cv,
            ci_95_low=mean - margin,
            ci_95_high=mean + margin,
            min=min(times),
            max=max(times),
        )


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""

    name: str
    elapsed_seconds: float  # median time
    iterations: list[float]
    ops_completed: int
    description: str
    stats: BenchmarkStats = field(default_factory=lambda: BenchmarkStats(0, 0, 0, 0, 0, 0, 0, 0))

    @property
    def is_multi_threaded(self) -> bool:
        return self.name in ("concurrent_dispatch", "subprocess_spawning")


WARMUP_ITERATIONS = 1
ADAPTIVE_STDDEV_THRESHOLD = 0.05  # 5% CV triggers additional iterations
ADAPTIVE_MAX_EXTRA = 4  # at most double the requested iterations


class BaseBenchmark(ABC):
    """Base class that all benchmarks inherit from."""

    name: str = "base"
    description: str = ""
    weight: float = 0.0

    @abstractmethod
    def run_once(self) -> int:
        """Run one iteration of the benchmark.

        Returns the number of operations completed.
        """

    def run(self, iterations: int = 5) -> BenchmarkResult:
        """Run the benchmark with warm-up and adaptive iteration count."""
        # Warm-up: run untimed iterations to stabilize caches
        for _ in range(WARMUP_ITERATIONS):
            self.run_once()

        # Timed iterations
        times: list[float] = []
        total_ops = 0

        for _ in range(iterations):
            start = time.perf_counter()
            ops = self.run_once()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            total_ops += ops

        # Adaptive: if CV is too high, run more iterations (up to ADAPTIVE_MAX_EXTRA)
        extra_run = 0
        while extra_run < ADAPTIVE_MAX_EXTRA and len(times) >= 3:
            cv = statistics.stdev(times) / statistics.mean(times) if statistics.mean(times) > 0 else 0
            if cv <= ADAPTIVE_STDDEV_THRESHOLD:
                break
            start = time.perf_counter()
            ops = self.run_once()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            total_ops += ops
            extra_run += 1

        stats = BenchmarkStats.from_times(times)
        avg_ops = total_ops // len(times)

        return BenchmarkResult(
            name=self.name,
            elapsed_seconds=stats.median,
            iterations=times,
            ops_completed=avg_ops,
            description=self.description,
            stats=stats,
        )
