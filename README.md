# AgentiCPUMark

A CPU benchmark designed to measure performance on workloads characteristic of AI agent execution.

## Why?

AI agents (like coding assistants, autonomous research tools, and tool-using LLM systems) stress CPUs differently than traditional benchmarks measure. Research shows that **tool processing on CPUs accounts for 50-90% of total latency** in agentic workloads ([Georgia Tech/Intel, 2025](https://arxiv.org/abs/2511.00739)), making the CPU the actual bottleneck — not the GPU.

Agent workloads involve rapid context switching, heavy JSON serialization, large-text manipulation, tree-search planning, concurrent tool dispatch, subprocess spawning, diff computation, HTML parsing, schema validation, streaming response parsing, code edit application, and memory-intensive context management — often all interleaved.

**AgentiCPUMark** targets these specific workload patterns to give a realistic picture of how a CPU performs when running AI agent infrastructure.

## Benchmark Suite

### Single-Agent Speed (sequential, single-threaded workloads)

| Benchmark | What it measures |
|---|---|
| **JSON Processing** | Serialization & deserialization of tool schemas, function calls, and conversations |
| **Text Processing** | Tokenizer-like chunking, regex parsing, BPE-like frequency counting |
| **Tree Search** | Monte Carlo tree search and beam search simulating agent planning/reasoning |
| **Diff/Patch** | Line-by-line comparison, unified diff generation, and patch application |
| **HTML Parsing** | DOM tree construction, CSS-like queries, and HTML-to-markdown conversion |
| **Schema Validation** | JSON Schema compilation, validation, and malformed JSON repair |
| **Streaming Parse** | SSE stream parsing with fragmented tool-call JSON accumulation |
| **Code Edit Apply** | Exact substring search, uniqueness verification, and edit application |
| **Memory Pressure** | Large working-set manipulation, burst alloc/dealloc, context window management |

### Multi-Agent Throughput (concurrent, multi-threaded workloads)

| Benchmark | What it measures |
|---|---|
| **Context Switching** | Rapid coroutine/thread switching simulating agent reasoning loops |
| **Concurrent Dispatch** | Thread-pool throughput for parallel tool execution with shared state |
| **Subprocess Spawning** | Process fork/exec, pipe management, and output collection |

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
--iterations N      Timed iterations per benchmark (default: 5)
--threads N         Max threads for concurrent benchmarks (default: CPU count)
--json              Output results as JSON
--verbose           Show detailed per-iteration results with statistics
```

## Methodology

### Warm-up

Each benchmark runs 1 untimed warm-up iteration before timed runs begin. This stabilizes CPU caches and Python's internal optimizations.

### Adaptive Iterations

If the coefficient of variation (CV = stddev/mean) exceeds 5% after the initial iterations, additional runs are automatically added (up to 4 extra) to improve statistical confidence. This follows the [Phoronix Test Suite](https://www.phoronix-test-suite.com/) approach.

### Statistical Reporting

Each benchmark reports:
- **Median** time (primary metric, robust to outliers)
- **Mean**, **StdDev**, and **CV** (coefficient of variation)
- **95% Confidence Interval** (using t-distribution)
- **Min/Max** times across all iterations

### Scoring

Each benchmark's raw time is normalized against a reference system:

```
Score = 1000 * (reference_time / actual_time)
```

A score of **1000 = reference performance** (AMD Ryzen 9 7950X baseline). Higher is better.

### Composite Scores

Three composite scores are computed using weighted geometric means:

| Score | Benchmarks included | What it tells you |
|---|---|---|
| **Single-Agent Speed** | All sequential benchmarks | How fast a single agent executes |
| **Multi-Agent Throughput** | All concurrent benchmarks | How well the CPU scales with parallel agents |
| **Overall Composite** | All benchmarks | Combined agentic CPU performance |

The geometric mean prevents any single benchmark from dominating through outlier performance (following [SPEC CPU methodology](https://www.spec.org/cpu2017/)).

### Benchmark Weights

| Benchmark | Weight |
|---|---|
| JSON Processing | 12% |
| Text Processing | 10% |
| Tree Search | 10% |
| Subprocess Spawning | 10% |
| Context Switching | 8% |
| Concurrent Dispatch | 8% |
| Diff/Patch | 8% |
| Streaming Parse | 8% |
| Code Edit Apply | 8% |
| HTML Parsing | 7% |
| Schema Validation | 6% |
| Memory Pressure | 5% |

Weights reflect the relative frequency and CPU cost of each workload pattern in real agent systems, informed by profiling data from the [AgentCgroup](https://arxiv.org/abs/2602.09345) and [CPU-Centric Agentic AI](https://arxiv.org/abs/2511.00739) research.

## Example Output

```
===========================================================================
  AgentiCPUMark v0.1.0
  CPU Benchmark for AI Agentic Workloads
===========================================================================

  CPU:         AMD Ryzen 9 7950X 16-Core Processor
  Cores:       32
  Platform:    Linux-6.8.0-generic-x86_64-with-glibc2.39
  Python:      3.13.0
  Arch:        x86_64

---------------------------------------------------------------------------
  Benchmark                   Time (s)   StdDev      CV        Ops    Score
---------------------------------------------------------------------------
  context_switching              0.048    0.002    4.2%     30,000     1042
  json_processing                0.051    0.001    2.0%      4,300      980
  ...
---------------------------------------------------------------------------

                    Single-Agent Speed      1015
                 Multi-Agent Throughput      1030
                     OVERALL COMPOSITE      1020

  (Reference: 1000 = AMD Ryzen 9 7950X | Higher is better)
===========================================================================
```

## How Benchmarks Were Identified

The initial benchmark suite (v0.1.0–v0.2.0) was designed from published research:
- [A CPU-Centric Perspective on Agentic AI](https://arxiv.org/abs/2511.00739) (Georgia Tech/Intel) — profiled five agentic workloads and found CPU tool processing accounts for 50-90% of total latency
- [AgentCgroup](https://arxiv.org/abs/2602.09345) — measured OS-level resource usage of AI agents, revealing 15.4x peak/avg memory ratios and burst-silence CPU utilization patterns

Two additional benchmarks (**Streaming Parse** and **Code Edit Apply**) were added after **live introspection of Claude Code** (Anthropic's AI coding agent). We ran Claude Code on the AgentiCPUMark repo itself and traced its behavior:

- **Streaming Parse**: Claude Code receives LLM responses as Server-Sent Event (SSE) streams. Tool call arguments arrive as `input_json_delta` fragments — partial JSON strings that the client must accumulate chunk-by-chunk, attempting a `JSON.parse()` on every fragment to detect completion. Profiling showed this is the agent's main hot loop, running continuously during every API response. Multiple sub-agents can stream in parallel, multiplexing fragment accumulation across independent sessions. This pattern is universal across agent clients (Cursor, Copilot, etc.) and was not covered by our existing JSON Processing benchmark, which tests complete serialize/deserialize cycles rather than incremental fragment assembly.

- **Code Edit Apply**: Claude Code's Edit tool applies changes via exact substring matching, not traditional diff/patch. It loads the entire file, searches for an `old_string`, verifies the match is **unique** (requiring a second full scan), snapshots the original for undo, and applies the replacement. This is fundamentally different from the LCS-based diff computation in our Diff/Patch benchmark. For large files, the uniqueness scan is expensive. When the target string isn't unique, the agent must extend context by including surrounding lines and re-scan — a pattern of iteratively widening substring searches. Agents typically chain 5-20 such edits per task.

Both patterns were confirmed by measuring Claude Code's client-side overhead across multi-tool tasks (34ms/turn client processing, 7-22 turns per task).

## Design Principles

- **Zero external dependencies**: Pure Python stdlib. No pip install needed beyond the package itself.
- **Deterministic**: Fixed random seeds where applicable for reproducibility.
- **Real workload patterns**: Every benchmark targets an actual computational pattern observed in production agent systems, not synthetic micro-benchmarks.
- **Statistical rigor**: Warm-up runs, adaptive iteration counts, and full statistical reporting following established benchmarking best practices.

## References

- [A CPU-Centric Perspective on Agentic AI](https://arxiv.org/abs/2511.00739) — Georgia Tech / Intel (2025)
- [AgentCgroup: OS Resources of AI Agents](https://arxiv.org/abs/2602.09345) — profiling data on agent resource usage patterns
- [SPEC CPU 2017 Methodology](https://www.spec.org/cpu2017/) — scoring and composite methodology
- [AI Agents That Matter](https://arxiv.org/abs/2407.01502) — Princeton (2024), agent benchmarking methodology

## Contributing

Contributions welcome! Please open an issue to discuss new benchmark ideas before submitting a PR.

## License

MIT
