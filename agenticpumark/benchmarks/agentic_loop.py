"""Agentic Coding Loop benchmark.

This benchmark was designed by running Claude Code on the AgentiCPUMark
repository itself and tracing exactly what it does when writing code.
Five different tasks were profiled (small feature, test file creation,
multi-file refactor, bug fix, complex multi-file feature) across 3-30
turns each.

Every coding task follows the same computational cycle:

  Glob (discover structure)
    -> Grep (find symbols/patterns)
      -> Read (load file contents)
        -> Edit (substring match + uniqueness check + replace)
          -> Verify (run command, parse output)
            -> Serialize (append result to growing conversation)
              -> Loop

The distinctive property is that the *conversation state grows
monotonically* with each turn. Turn 1 serializes ~50K tokens of context;
turn 30 serializes ~800K tokens. Each iteration adds tool call + result
to the history, and the *entire history* is re-serialized every turn
(for API calls and session persistence).

Profiling results from live Claude Code sessions:

  Task Type         | Turns | Input Tokens | Output Tokens
  Small feature     |   9   |    132K      |     1.7K
  Test file (new)   |  23   |    559K      |     6.2K
  Multi-file refact |  10   |    101K      |     1.1K
  Bug find+fix      |   3   |     52K      |     0.5K
  Complex feature   |  30   |    801K      |     8.4K

This benchmark simulates the full cycle, including the growing-context
serialization pressure that makes later turns progressively more expensive.
"""

import hashlib
import json
import random
import re
import tempfile
import os
import shutil
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_TASKS = 8
TURNS_PER_TASK = 15
NUM_PROJECT_FILES = 40
FILE_LINES = 200


def _generate_project_file(seed: int, num_lines: int = FILE_LINES) -> str:
    """Generate a realistic Python source file."""
    rng = random.Random(seed)
    identifiers = [
        "process_data", "handle_request", "validate_input", "transform_output",
        "fetch_results", "build_query", "parse_response", "init_config",
        "cleanup_resources", "dispatch_event", "schedule_task", "compute_hash",
        "merge_results", "filter_items", "aggregate_stats", "render_template",
    ]
    types = ["str", "int", "bool", "list", "dict", "Optional[str]", "List[int]"]

    lines: list[str] = []
    lines.append(f'"""Module {seed}: generated source."""')
    lines.append("import json")
    lines.append("import logging")
    lines.append(f"logger = logging.getLogger(__name__)")
    lines.append("")

    while len(lines) < num_lines:
        cls_name = f"Service_{seed}_{len(lines)}"
        lines.append(f"class {cls_name}:")
        lines.append(f'    """Service class for module {seed}."""')
        lines.append("")
        lines.append(f"    def __init__(self, name: str = \"\"):")
        lines.append(f"        self.name = name")
        lines.append(f"        self._state = {{}}")
        lines.append("")

        for _ in range(rng.randint(2, 5)):
            if len(lines) >= num_lines:
                break
            method = rng.choice(identifiers)
            params = ", ".join(
                f"{rng.choice(identifiers).split('_')[0]}_{j}: {rng.choice(types)}"
                for j in range(rng.randint(1, 3))
            )
            lines.append(f"    def {method}_{len(lines)}(self, {params}):")
            for bl in range(rng.randint(3, 8)):
                if len(lines) >= num_lines:
                    break
                indent = "        "
                if bl == 0:
                    lines.append(f'{indent}"""Perform {method} operation."""')
                elif rng.random() < 0.1:
                    lines.append(f"{indent}# TODO: optimize this")
                else:
                    var = rng.choice(identifiers).split("_")[0]
                    lines.append(f"{indent}{var}_{bl} = self.{rng.choice(identifiers).split('_')[0]}({rng.randint(0, 999)})")
            lines.append("")

    return "\n".join(lines[:num_lines])


class AgenticLoopBenchmark(BaseBenchmark):
    name = "agentic_loop"
    description = "Full Glob->Grep->Read->Edit->Verify cycle with growing conversation state"
    weight = 0.10

    def run_once(self) -> int:
        ops = 0

        # Create a temporary "project" on disk
        project_dir = tempfile.mkdtemp(prefix="agenticpumark_loop_")
        try:
            ops += self._run_tasks(project_dir)
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)

        return ops

    def _run_tasks(self, project_dir: str) -> int:
        ops = 0

        # Set up project structure
        src_dir = os.path.join(project_dir, "src")
        os.makedirs(src_dir, exist_ok=True)

        file_paths: list[str] = []
        for i in range(NUM_PROJECT_FILES):
            subdir = os.path.join(src_dir, f"pkg_{i % 5}")
            os.makedirs(subdir, exist_ok=True)
            path = os.path.join(subdir, f"module_{i}.py")
            content = _generate_project_file(i)
            with open(path, "w") as f:
                f.write(content)
            file_paths.append(path)
            ops += 1

        # Run multiple "agent tasks" on this project
        for task_idx in range(NUM_TASKS):
            ops += self._run_single_task(project_dir, file_paths, task_idx)

        return ops

    def _run_single_task(self, project_dir: str, file_paths: list[str], task_seed: int) -> int:
        """Simulate one complete agent coding task with growing conversation."""
        rng = random.Random(task_seed)
        ops = 0

        # The conversation history grows with each turn, just like in a real agent
        conversation: list[dict] = [
            {
                "role": "system",
                "content": "You are a coding assistant. " * 50,  # ~200 tokens
            },
            {
                "role": "user",
                "content": f"Task {task_seed}: modify the project to improve module handling. " * 10,
            },
        ]

        for turn in range(TURNS_PER_TASK):
            tool_calls: list[dict] = []
            tool_results: list[dict] = []

            # --- STEP 1: Glob (discover project structure) ---
            discovered: list[str] = []
            for root, dirs, files in os.walk(project_dir):
                for fname in files:
                    if fname.endswith(".py"):
                        full = os.path.join(root, fname)
                        discovered.append(full)
                        ops += 1

            tool_calls.append({
                "type": "tool_use", "name": "Glob",
                "input": {"pattern": "**/*.py"},
            })
            tool_results.append({
                "type": "tool_result",
                "content": json.dumps(discovered[:20]),
            })

            # --- STEP 2: Grep (search for pattern) ---
            search_patterns = [
                r"def \w+_\d+\(self",
                r"class \w+:",
                r"# TODO:",
                r"self\._state",
                r"logger\.\w+",
                r"import \w+",
            ]
            pattern = re.compile(rng.choice(search_patterns))
            grep_results: list[dict] = []

            target_files = rng.sample(file_paths, k=min(10, len(file_paths)))
            for fpath in target_files:
                with open(fpath, "r") as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            grep_results.append({
                                "file": fpath,
                                "line": line_num,
                                "text": line.rstrip(),
                            })
                            ops += 1

            tool_calls.append({
                "type": "tool_use", "name": "Grep",
                "input": {"pattern": pattern.pattern, "path": project_dir},
            })
            tool_results.append({
                "type": "tool_result",
                "content": json.dumps(grep_results[:50]),
            })

            # --- STEP 3: Read (load file contents) ---
            if grep_results:
                target = rng.choice(grep_results)["file"]
            else:
                target = rng.choice(file_paths)

            with open(target, "r") as f:
                file_content = f.read()
            ops += 1

            tool_calls.append({
                "type": "tool_use", "name": "Read",
                "input": {"file_path": target},
            })
            # Tool result includes full file content (this is what makes
            # conversation history grow — file contents accumulate)
            tool_results.append({
                "type": "tool_result",
                "content": file_content,
            })

            # --- STEP 4: Edit (exact substring match + replace) ---
            lines = file_content.split("\n")
            if len(lines) > 10:
                # Pick a block to edit
                block_start = rng.randint(5, len(lines) - 6)
                block_size = rng.randint(2, 5)
                old_lines = lines[block_start : block_start + block_size]
                old_string = "\n".join(old_lines)

                if old_string.strip():
                    # Uniqueness check (full file scan, exactly like Claude Code)
                    first_pos = file_content.find(old_string)
                    second_pos = file_content.find(old_string, first_pos + 1)
                    is_unique = first_pos != -1 and second_pos == -1
                    ops += 1

                    if not is_unique and first_pos != -1:
                        # Extend context to make it unique (real agent behavior)
                        ctx = 1
                        while ctx < 5:
                            s = max(0, block_start - ctx)
                            e = min(len(lines), block_start + block_size + ctx)
                            old_string = "\n".join(lines[s:e])
                            if file_content.count(old_string) == 1:
                                is_unique = True
                                break
                            ctx += 1
                            ops += 1

                    if is_unique:
                        # Snapshot for undo
                        snapshot = hashlib.sha256(file_content.encode()).hexdigest()
                        ops += 1

                        # Apply edit
                        new_lines = list(old_lines)
                        idx = rng.randint(0, len(new_lines) - 1)
                        indent = len(new_lines[idx]) - len(new_lines[idx].lstrip())
                        new_lines[idx] = " " * indent + f"updated_v{turn} = process({rng.randint(0, 9999)})"
                        new_string = "\n".join(new_lines)

                        file_content = file_content.replace(old_string, new_string, 1)

                        # Write back
                        with open(target, "w") as f:
                            f.write(file_content)
                        ops += 1

                        tool_calls.append({
                            "type": "tool_use", "name": "Edit",
                            "input": {
                                "file_path": target,
                                "old_string": old_string,
                                "new_string": new_string,
                            },
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "content": "Edit applied successfully.",
                        })

            # --- STEP 5: Verify (simulate running a check command) ---
            # In real agents this is subprocess.run(pytest/lint/typecheck)
            # Here we simulate parsing structured output
            verify_output = {
                "passed": rng.randint(10, 50),
                "failed": rng.randint(0, 2),
                "warnings": [
                    f"W{rng.randint(100,999)}: {rng.choice(['unused import', 'line too long', 'missing docstring'])}"
                    for _ in range(rng.randint(0, 5))
                ],
                "duration_s": round(rng.uniform(0.5, 5.0), 2),
            }
            verify_json = json.dumps(verify_output)
            parsed_verify = json.loads(verify_json)
            ops += 1

            tool_calls.append({
                "type": "tool_use", "name": "Bash",
                "input": {"command": "python -m pytest tests/ -x"},
            })
            tool_results.append({
                "type": "tool_result",
                "content": verify_json,
            })

            # --- STEP 6: Serialize growing conversation ---
            # This is the key insight: each turn appends to conversation
            # history, and the ENTIRE history is re-serialized every turn

            # Add assistant message with tool calls
            conversation.append({
                "role": "assistant",
                "content": [
                    {"type": "text", "text": f"Turn {turn}: analyzing results and making changes..."},
                    *tool_calls,
                ],
            })

            # Add tool results
            for tr in tool_results:
                conversation.append({
                    "role": "tool",
                    "content": tr["content"],
                })

            # Simulate API call serialization (the entire conversation
            # is serialized to JSON on every turn)
            api_payload = json.dumps(conversation)
            ops += len(api_payload) // 100  # proportional to payload size

            # Simulate session persistence (written to disk every turn)
            session_data = json.dumps({
                "session_id": f"sess_{task_seed}",
                "messages": conversation,
                "turn": turn,
            })
            _ = hashlib.sha256(session_data.encode()).hexdigest()
            ops += len(session_data) // 100

            # Simulate streaming response parsing for this turn
            # (agent receives response as SSE chunks)
            response_text = f"I've made the change in turn {turn}. " * rng.randint(5, 20)
            chunks = [response_text[i:i+rng.randint(3, 15)] for i in range(0, len(response_text), 10)]
            accumulated = ""
            for chunk in chunks:
                accumulated += chunk
                ops += 1

            # Add assistant response to conversation
            conversation.append({
                "role": "assistant",
                "content": response_text,
            })

        return ops
