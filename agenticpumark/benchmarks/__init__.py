"""Benchmark modules for AgentiCPUMark."""

from agenticpumark.benchmarks.context_switching import ContextSwitchingBenchmark
from agenticpumark.benchmarks.json_processing import JsonProcessingBenchmark
from agenticpumark.benchmarks.text_processing import TextProcessingBenchmark
from agenticpumark.benchmarks.tree_search import TreeSearchBenchmark
from agenticpumark.benchmarks.concurrent_dispatch import ConcurrentDispatchBenchmark
from agenticpumark.benchmarks.memory_pressure import MemoryPressureBenchmark
from agenticpumark.benchmarks.subprocess_spawning import SubprocessSpawningBenchmark
from agenticpumark.benchmarks.diff_patch import DiffPatchBenchmark
from agenticpumark.benchmarks.html_parsing import HtmlParsingBenchmark
from agenticpumark.benchmarks.schema_validation import SchemaValidationBenchmark
from agenticpumark.benchmarks.streaming_parse import StreamingParseBenchmark
from agenticpumark.benchmarks.code_edit_apply import CodeEditApplyBenchmark

ALL_BENCHMARKS = {
    "context_switching": ContextSwitchingBenchmark,
    "json_processing": JsonProcessingBenchmark,
    "text_processing": TextProcessingBenchmark,
    "tree_search": TreeSearchBenchmark,
    "concurrent_dispatch": ConcurrentDispatchBenchmark,
    "memory_pressure": MemoryPressureBenchmark,
    "subprocess_spawning": SubprocessSpawningBenchmark,
    "diff_patch": DiffPatchBenchmark,
    "html_parsing": HtmlParsingBenchmark,
    "schema_validation": SchemaValidationBenchmark,
    "streaming_parse": StreamingParseBenchmark,
    "code_edit_apply": CodeEditApplyBenchmark,
}

# Benchmarks that require max_threads parameter
THREADED_BENCHMARKS = {ConcurrentDispatchBenchmark, SubprocessSpawningBenchmark}
