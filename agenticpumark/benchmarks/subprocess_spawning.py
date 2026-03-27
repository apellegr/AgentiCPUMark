"""Subprocess Spawning benchmark.

AI agents constantly spawn external processes: git commands, test runners,
linters, compilers, MCP servers, and shell commands. The fork/exec overhead,
pipe management, and output collection pattern is one of the largest CPU
costs in real agent workloads. SWE-Agent profiling shows subprocess execution
accounts for 43-79% of total task latency.
"""

import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from agenticpumark.benchmarks.base import BaseBenchmark

# Number of rapid sequential spawns (simulating agent tool-call chains)
SEQUENTIAL_SPAWNS = 200
# Number of parallel spawns (simulating concurrent tool dispatch)
PARALLEL_SPAWNS = 100
# Number of spawns with large stdout (simulating test runner / compiler output)
LARGE_OUTPUT_SPAWNS = 50
# Lines of output per large-output spawn
OUTPUT_LINES = 500
# Number of pipe-chained spawns (simulating shell pipelines)
PIPE_CHAIN_SPAWNS = 80
PIPE_CHAIN_DEPTH = 3


class SubprocessSpawningBenchmark(BaseBenchmark):
    name = "subprocess_spawning"
    description = "Process fork/exec, pipe management, and output collection"
    weight = 0.10

    def __init__(self, max_threads: int = 8):
        self.max_threads = max_threads

    def run_once(self) -> int:
        ops = 0
        ops += self._sequential_spawns()
        ops += self._parallel_spawns()
        ops += self._large_output_spawns()
        ops += self._pipe_chain_spawns()
        return ops

    def _sequential_spawns(self) -> int:
        """Rapid sequential process spawns simulating an agent tool-call chain.

        Mirrors the pattern: think -> spawn git status -> collect output ->
        think -> spawn grep -> collect output -> think -> spawn edit...
        """
        ops = 0
        python = sys.executable
        for i in range(SEQUENTIAL_SPAWNS):
            result = subprocess.run(
                [python, "-c", f"import os; print(os.getpid(), {i})"],
                capture_output=True,
                text=True,
            )
            _ = result.stdout.strip()
            ops += 1
        return ops

    def _parallel_spawns(self) -> int:
        """Concurrent process spawns simulating parallel tool dispatch."""
        ops = 0
        python = sys.executable

        with ThreadPoolExecutor(max_workers=self.max_threads) as pool:
            futures = []
            for i in range(PARALLEL_SPAWNS):
                cmd = [python, "-c", f"import json; print(json.dumps({{'id': {i}, 'status': 'ok'}}))"]
                futures.append(pool.submit(subprocess.run, cmd, capture_output=True, text=True))

            for future in as_completed(futures):
                result = future.result()
                _ = result.stdout.strip()
                ops += 1

        return ops

    def _large_output_spawns(self) -> int:
        """Spawn processes that produce large stdout, simulating test/compiler output.

        Agents must buffer and parse large outputs from pytest, cargo test,
        compiler warnings, etc.
        """
        ops = 0
        python = sys.executable
        script = f"for i in range({OUTPUT_LINES}): print(f'line {{i}}: ' + 'x' * 120)"

        for _ in range(LARGE_OUTPUT_SPAWNS):
            result = subprocess.run(
                [python, "-c", script],
                capture_output=True,
                text=True,
            )
            lines = result.stdout.splitlines()
            # Simulate parsing the output (extracting pass/fail counts, etc.)
            count = sum(1 for line in lines if "line" in line)
            ops += 1 + count

        return ops

    def _pipe_chain_spawns(self) -> int:
        """Spawn chains of piped processes simulating shell pipelines.

        Agents run commands like: grep -r pattern | sort | head -20
        """
        ops = 0
        python = sys.executable

        for i in range(PIPE_CHAIN_SPAWNS):
            # Build a pipeline: generate data | filter | transform
            gen_script = f"""
import json, sys
for j in range(100):
    print(json.dumps({{"id": j, "value": j * {i + 1}, "tag": "item"}}))
"""
            filter_script = """
import json, sys
for line in sys.stdin:
    obj = json.loads(line)
    if obj["value"] % 3 == 0:
        print(json.dumps(obj))
"""
            transform_script = """
import json, sys
results = []
for line in sys.stdin:
    obj = json.loads(line)
    obj["processed"] = True
    results.append(obj)
print(json.dumps({"count": len(results), "ids": [r["id"] for r in results[:10]]}))
"""
            p1 = subprocess.Popen(
                [python, "-c", gen_script],
                stdout=subprocess.PIPE,
            )
            p2 = subprocess.Popen(
                [python, "-c", filter_script],
                stdin=p1.stdout,
                stdout=subprocess.PIPE,
            )
            p1.stdout.close()
            p3 = subprocess.Popen(
                [python, "-c", transform_script],
                stdin=p2.stdout,
                stdout=subprocess.PIPE,
                text=True,
            )
            p2.stdout.close()

            output, _ = p3.communicate()
            p1.wait()
            p2.wait()
            _ = output.strip()
            ops += PIPE_CHAIN_DEPTH

        return ops
