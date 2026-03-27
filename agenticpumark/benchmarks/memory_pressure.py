"""Memory Pressure benchmark.

AI agents manage large context windows (128K+ tokens), maintain conversation
histories, perform similarity searches over cached results, and constantly
resize and reorganize working memory. This benchmark stresses memory bandwidth,
allocation patterns, and cache behavior with workloads sized to match real
agent memory footprints.
"""

import hashlib
import math
import random
from agenticpumark.benchmarks.base import BaseBenchmark

CONTEXT_TOKENS = 131_072  # 128K tokens
TOKEN_DIM = 64  # simplified embedding dimension
NUM_QUERIES = 500
HISTORY_ENTRIES = 10_000
CACHE_SIZE = 50_000
BURST_CYCLES = 30  # number of burst alloc/dealloc cycles
BURST_SIZE = 5_000  # objects per burst


class MemoryPressureBenchmark(BaseBenchmark):
    name = "memory_pressure"
    description = "Large working-set manipulation simulating context window management"
    weight = 0.10

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Allocate and fill a large "context window"
        # Simulates the memory layout of a 128K token context
        rng = random.Random(42)
        context = [[rng.random() for _ in range(TOKEN_DIM)] for _ in range(CONTEXT_TOKENS // 8)]
        ops += len(context)

        # Phase 2: Sliding-window attention simulation
        # Walk through context computing dot-product-like scores
        window_size = 512
        for start in range(0, len(context) - window_size, window_size // 2):
            window = context[start : start + window_size]
            query = context[min(start + window_size, len(context) - 1)]
            # Compute attention scores (simplified dot product)
            scores = []
            for vec in window:
                score = sum(a * b for a, b in zip(query, vec))
                scores.append(score)
            # Softmax-like normalization
            max_score = max(scores)
            exp_scores = [math.exp(s - max_score) for s in scores]
            total = sum(exp_scores)
            _ = [s / total for s in exp_scores]
            ops += window_size

        # Phase 3: Context truncation and reorganization
        # Simulate dropping old messages and compacting the context
        keep_ratio = 0.6
        kept = context[: int(len(context) * keep_ratio)]
        # "Summarize" dropped content into a single vector
        dropped = context[int(len(context) * keep_ratio) :]
        summary = [0.0] * TOKEN_DIM
        for vec in dropped:
            for j in range(TOKEN_DIM):
                summary[j] += vec[j]
        summary = [s / max(len(dropped), 1) for s in summary]
        kept.insert(0, summary)
        ops += len(dropped)

        # Phase 4: Key-value cache simulation
        # Agents cache tool results; simulate insertion and lookup patterns
        cache: dict[str, list[float]] = {}
        for i in range(CACHE_SIZE):
            key = hashlib.md5(f"cache_key_{i}".encode()).hexdigest()[:16]
            cache[key] = [rng.random() for _ in range(TOKEN_DIM)]
            ops += 1

        # Random access pattern (simulating cache lookups during generation)
        for i in range(NUM_QUERIES):
            key = hashlib.md5(f"cache_key_{rng.randint(0, CACHE_SIZE - 1)}".encode()).hexdigest()[:16]
            if key in cache:
                vec = cache[key]
                _ = sum(v * v for v in vec)  # simulate using the cached value
            ops += 1

        # Phase 5: History compaction (similar to conversation pruning)
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "tokens": rng.randint(10, 500)}
            for i in range(HISTORY_ENTRIES)
        ]
        # Compact: merge consecutive same-role entries
        compacted: list[dict] = []
        for entry in history:
            if compacted and compacted[-1]["role"] == entry["role"]:
                compacted[-1]["tokens"] += entry["tokens"]
            else:
                compacted.append(dict(entry))
            ops += 1

        # Phase 6: Burst allocation/deallocation cycles
        # Real agents show 15.4x peak/avg memory ratio due to tool execution bursts.
        # This phase simulates rapid alloc/dealloc of large working sets that happen
        # when agents spawn tools, process results, then discard intermediates.
        for cycle in range(BURST_CYCLES):
            # Burst allocate: simulate tool result processing
            burst_data: list[list[float]] = [
                [rng.random() for _ in range(TOKEN_DIM * 2)]
                for _ in range(BURST_SIZE)
            ]
            # Process the burst (simulate computing over tool results)
            running_sum = [0.0] * (TOKEN_DIM * 2)
            for vec in burst_data:
                for j in range(len(running_sum)):
                    running_sum[j] += vec[j]
            # Extract a small summary and discard the rest
            summary_vec = [s / BURST_SIZE for s in running_sum[:TOKEN_DIM]]
            _ = hashlib.sha256(str(summary_vec).encode()).hexdigest()
            # Burst deallocate: let the large list go out of scope
            del burst_data
            ops += BURST_SIZE

        return ops
