"""Benchmark modules for AgentiCPUMark."""

from agenticpumark.benchmarks.context_switching import ContextSwitchingBenchmark
from agenticpumark.benchmarks.json_processing import JsonProcessingBenchmark
from agenticpumark.benchmarks.text_processing import TextProcessingBenchmark
from agenticpumark.benchmarks.tree_search import TreeSearchBenchmark
from agenticpumark.benchmarks.concurrent_dispatch import ConcurrentDispatchBenchmark
from agenticpumark.benchmarks.memory_pressure import MemoryPressureBenchmark

ALL_BENCHMARKS = {
    "context_switching": ContextSwitchingBenchmark,
    "json_processing": JsonProcessingBenchmark,
    "text_processing": TextProcessingBenchmark,
    "tree_search": TreeSearchBenchmark,
    "concurrent_dispatch": ConcurrentDispatchBenchmark,
    "memory_pressure": MemoryPressureBenchmark,
}
