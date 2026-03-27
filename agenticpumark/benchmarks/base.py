"""Base class for all benchmarks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time


@dataclass
class BenchmarkResult:
    """Result from a single benchmark run."""

    name: str
    elapsed_seconds: float
    iterations: list[float]
    ops_completed: int
    description: str


class BaseBenchmark(ABC):
    """Base class that all benchmarks inherit from."""

    name: str = "base"
    description: str = ""
    weight: float = 0.0  # Weight in composite score

    @abstractmethod
    def run_once(self) -> int:
        """Run one iteration of the benchmark.

        Returns the number of operations completed.
        """

    def run(self, iterations: int = 3) -> BenchmarkResult:
        """Run the benchmark for the given number of iterations."""
        times: list[float] = []
        total_ops = 0

        for _ in range(iterations):
            start = time.perf_counter()
            ops = self.run_once()
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            total_ops += ops

        median_time = sorted(times)[len(times) // 2]

        return BenchmarkResult(
            name=self.name,
            elapsed_seconds=median_time,
            iterations=times,
            ops_completed=total_ops // iterations,
            description=self.description,
        )
