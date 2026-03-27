"""CLI entry point for AgentiCPUMark."""

import argparse
import json
import os
import sys

from agenticpumark.runner import BenchmarkRunner
from agenticpumark.report import print_report, format_json_report


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agenticpumark",
        description="CPU benchmark focused on AI agentic workloads",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="Run only the named benchmark",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of timed iterations per benchmark (default: 5)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=os.cpu_count() or 4,
        help="Max threads for concurrent benchmarks (default: CPU count)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed per-iteration results",
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(
        iterations=args.iterations,
        max_threads=args.threads,
        verbose=args.verbose,
    )

    results = runner.run(benchmark_name=args.benchmark)

    if args.json_output:
        print(json.dumps(format_json_report(results), indent=2))
    else:
        print_report(results, verbose=args.verbose)


if __name__ == "__main__":
    main()
