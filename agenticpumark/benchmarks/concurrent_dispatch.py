"""Concurrent Dispatch benchmark.

Agents frequently execute multiple tools in parallel: web searches,
file reads, API calls, and database queries all dispatched concurrently
with results aggregated back into the reasoning loop. This benchmark
measures thread-pool throughput with realistic shared-state coordination.
"""

import threading
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_TOOL_CALLS = 2000
AGGREGATION_ROUNDS = 50


def _simulate_web_search(query_id: int) -> dict:
    """Simulate a web search tool: text hashing + JSON construction."""
    query = f"search query {query_id} about AI agents and tool use"
    results = []
    for i in range(10):
        content = f"Result {i} for query {query_id}: " + query * 3
        digest = hashlib.sha256(content.encode()).hexdigest()
        results.append({
            "title": f"Result {i}",
            "snippet": content[:200],
            "hash": digest,
            "score": math.log(i + 2) * (query_id % 7 + 1),
        })
    return {"query_id": query_id, "results": results}


def _simulate_file_read(file_id: int) -> dict:
    """Simulate reading and parsing a file."""
    content = f"File {file_id} content: " + "x" * (1000 + file_id % 5000)
    lines = [content[i : i + 80] for i in range(0, len(content), 80)]
    word_count = sum(len(line.split()) for line in lines)
    checksum = hashlib.md5(content.encode()).hexdigest()
    return {"file_id": file_id, "lines": len(lines), "words": word_count, "checksum": checksum}


def _simulate_api_call(call_id: int) -> dict:
    """Simulate an API call with JSON serialization overhead."""
    request = {
        "method": "POST",
        "endpoint": f"/api/v1/resource/{call_id}",
        "body": {
            "data": [math.sin(i * call_id * 0.01) for i in range(50)],
            "metadata": {"call_id": call_id, "retry": call_id % 3},
        },
    }
    wire = json.dumps(request)
    parsed = json.loads(wire)
    # Simulate response processing
    response_data = sum(parsed["body"]["data"])
    return {"call_id": call_id, "response_sum": response_data, "size": len(wire)}


class ConcurrentDispatchBenchmark(BaseBenchmark):
    name = "concurrent_dispatch"
    description = "Thread-pool throughput for parallel tool execution with shared state"
    weight = 0.15

    def __init__(self, max_threads: int = 8):
        self.max_threads = max_threads

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Parallel tool dispatch with mixed workload types
        tools = [_simulate_web_search, _simulate_file_read, _simulate_api_call]
        results_store: list[dict] = []
        lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=self.max_threads) as pool:
            futures = []
            for i in range(NUM_TOOL_CALLS):
                tool_fn = tools[i % len(tools)]
                futures.append(pool.submit(tool_fn, i))

            for future in as_completed(futures):
                result = future.result()
                with lock:
                    results_store.append(result)
                ops += 1

        # Phase 2: Concurrent aggregation with contention
        # Simulate multiple agents reading from a shared result store
        aggregated: dict[str, float] = {}
        agg_lock = threading.Lock()

        def aggregate_chunk(start: int, end: int) -> int:
            local_ops = 0
            local_agg: dict[str, float] = {}
            for idx in range(start, min(end, len(results_store))):
                r = results_store[idx]
                key = str(r.get("query_id", r.get("file_id", r.get("call_id", 0))) % AGGREGATION_ROUNDS)
                serialized = json.dumps(r)
                local_agg[key] = local_agg.get(key, 0) + len(serialized)
                local_ops += 1

            with agg_lock:
                for k, v in local_agg.items():
                    aggregated[k] = aggregated.get(k, 0) + v

            return local_ops

        chunk_size = len(results_store) // self.max_threads + 1
        with ThreadPoolExecutor(max_workers=self.max_threads) as pool:
            futures = []
            for i in range(0, len(results_store), chunk_size):
                futures.append(pool.submit(aggregate_chunk, i, i + chunk_size))

            for future in as_completed(futures):
                ops += future.result()

        return ops
