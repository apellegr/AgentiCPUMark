"""Context Switching benchmark.

Simulates the rapid coroutine/thread switching pattern of an AI agent
alternating between reasoning steps and tool calls. Agents typically
execute a tight loop: think -> call tool -> process result -> think again,
creating heavy context-switching pressure.
"""

import asyncio
import threading
import queue
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_AGENTS = 50
STEPS_PER_AGENT = 200
QUEUE_CONSUMERS = 8


class ContextSwitchingBenchmark(BaseBenchmark):
    name = "context_switching"
    description = "Rapid coroutine/thread switching simulating agent reasoning loops"
    weight = 0.15

    def run_once(self) -> int:
        ops = 0
        ops += self._run_async_switching()
        ops += self._run_thread_switching()
        return ops

    def _run_async_switching(self) -> int:
        """Simulate agents as coroutines rapidly yielding between think/act steps."""
        ops = 0

        async def agent_loop(agent_id: int) -> int:
            local_ops = 0
            state = 0
            for step in range(STEPS_PER_AGENT):
                # Simulate "thinking" — light compute then yield
                state = (state + agent_id * step) % 1_000_003
                await asyncio.sleep(0)  # yield to event loop
                # Simulate "tool call" — produce result then yield
                state = (state ^ (step * 31)) % 1_000_003
                await asyncio.sleep(0)
                local_ops += 2
            return local_ops

        async def run_all() -> int:
            tasks = [agent_loop(i) for i in range(NUM_AGENTS)]
            results = await asyncio.gather(*tasks)
            return sum(results)

        ops += asyncio.run(run_all())
        return ops

    def _run_thread_switching(self) -> int:
        """Simulate tool dispatch via thread pool with shared work queue."""
        work_queue: queue.Queue[int | None] = queue.Queue()
        result_count = 0
        lock = threading.Lock()

        def consumer() -> None:
            nonlocal result_count
            while True:
                item = work_queue.get()
                if item is None:
                    break
                # Simulate processing a tool result
                _ = sum(range(item % 100))
                with lock:
                    result_count += 1
                work_queue.task_done()

        threads = [threading.Thread(target=consumer) for _ in range(QUEUE_CONSUMERS)]
        for t in threads:
            t.start()

        total_items = NUM_AGENTS * STEPS_PER_AGENT
        for i in range(total_items):
            work_queue.put(i)

        work_queue.join()

        for _ in threads:
            work_queue.put(None)
        for t in threads:
            t.join()

        return result_count
