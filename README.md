# AgentiCPUMark

A CPU benchmark designed to measure performance on workloads characteristic of AI agent execution.

## Why?

AI agents (like coding assistants, autonomous research tools, and tool-using LLM systems) stress CPUs differently than traditional benchmarks measure. They involve rapid context switching, heavy JSON serialization, large-text manipulation, tree-search planning, concurrent tool dispatch, and memory-intensive context management — often all at once.

**AgentiCPUMark** targets these specific workload patterns to give a realistic picture of how a CPU performs when running AI agent infrastructure.

## Benchmark Suite

| Benchmark | What it measures |
|---|---|
| **Context Switching** | Rapid coroutine/thread switching simulating agent reasoning loops with interleaved tool calls |
| **JSON Processing** | Serialization & deserialization of deeply nested structures (tool schemas, function calls, responses) |
| **Text Processing** | Tokenizer-like text chunking, regex-heavy parsing, and large string manipulation |
| **Tree Search** | Monte Carlo tree search and beam search simulating agent planning/reasoning |
| **Concurrent Dispatch** | Thread-pool throughput for parallel tool execution with shared state coordination |
| **Memory Pressure** | Large working-set manipulation simulating context window management (128K+ token contexts) |

## Installation

```bash
pip install .
```

## Usage

Run the full suite:

```bash
agenticpumark
```

Run a specific benchmark:

```bash
agenticpumark --benchmark json_processing
```

Options:

```
--benchmark NAME    Run only the named benchmark
--iterations N      Number of iterations per benchmark (default: 3)
--threads N         Max threads for concurrent benchmarks (default: CPU count)
--json              Output results as JSON
--verbose           Show detailed per-iteration results
```

## Scoring

Each benchmark produces a raw time in seconds. Scores are normalized against a reference system (baseline: AMD Ryzen 9 7950X) to produce a score where **1000 = reference performance**. Higher is better.

The **composite AgentiCPUMark score** is a weighted geometric mean:

| Benchmark | Weight |
|---|---|
| Context Switching | 15% |
| JSON Processing | 20% |
| Text Processing | 20% |
| Tree Search | 20% |
| Concurrent Dispatch | 15% |
| Memory Pressure | 10% |

## Contributing

Contributions welcome! Please open an issue to discuss new benchmark ideas before submitting a PR.

## License

MIT
