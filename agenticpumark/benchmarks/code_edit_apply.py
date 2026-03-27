"""Code Edit Application benchmark.

Coding agents like Claude Code, Cursor, and Copilot apply edits to source
files via exact string matching — NOT traditional diff/patch. The Edit tool
pattern works as follows:
  1. Load the entire file into memory
  2. Search for an exact `old_string` substring
  3. Verify the match is UNIQUE in the file (full scan required)
  4. Replace the matched text with `new_string`
  5. Snapshot the original for undo/rewind (file checkpoint)
  6. Write the modified content back

This was identified by introspecting Claude Code's live tool behavior.
The Edit tool's uniqueness check is a full-text scan on every edit — for
large files this is non-trivial. Agents typically chain 5-20 edits per
task, each requiring the full scan. This benchmark also covers the related
pattern of applying search-and-replace across multiple files (refactoring).
"""

import hashlib
import random
import re
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_FILES = 60
FILE_LINES = 400
EDITS_PER_FILE = 12
MULTI_FILE_REFACTORS = 15
FILES_PER_REFACTOR = 20
LARGE_FILE_LINES = 3000
LARGE_FILE_EDITS = 25


def _generate_code_file(seed: int, num_lines: int = FILE_LINES) -> str:
    """Generate a realistic Python source file as a single string."""
    rng = random.Random(seed)
    imports = [
        "import os", "import sys", "import json", "import re",
        "import hashlib", "import logging", "from pathlib import Path",
        "from typing import Optional, List, Dict",
        "from dataclasses import dataclass, field",
    ]
    class_names = [
        "DataProcessor", "RequestHandler", "ConfigManager",
        "CacheService", "EventDispatcher", "QueryBuilder",
        "AuthMiddleware", "ResponseFormatter", "TaskScheduler",
    ]
    method_names = [
        "process", "handle", "validate", "transform", "execute",
        "initialize", "cleanup", "serialize", "deserialize", "dispatch",
    ]
    var_names = [
        "result", "data", "config", "context", "response",
        "buffer", "cache", "query", "payload", "status",
    ]

    lines: list[str] = []

    # File header
    lines.append(f'"""Module {seed}: auto-generated source file."""')
    lines.append("")
    for imp in rng.sample(imports, k=min(rng.randint(3, 6), len(imports))):
        lines.append(imp)
    lines.append("")
    lines.append(f"logger = logging.getLogger(__name__)")
    lines.append("")

    while len(lines) < num_lines:
        cls = rng.choice(class_names)
        lines.append(f"class {cls}_{seed}_{len(lines)}:")
        lines.append(f'    """Handler for {cls.lower()} operations."""')
        lines.append("")
        lines.append(f"    def __init__(self, {rng.choice(var_names)}: str = \"\"):")
        lines.append(f"        self.{rng.choice(var_names)} = {rng.choice(var_names)}")
        lines.append(f"        self._cache: Dict[str, Any] = {{}}")
        lines.append("")

        for _ in range(rng.randint(2, 5)):
            if len(lines) >= num_lines:
                break
            method = rng.choice(method_names)
            params = ", ".join(
                f"{rng.choice(var_names)}_{j}: {rng.choice(['str', 'int', 'bool', 'list'])}"
                for j in range(rng.randint(1, 4))
            )
            lines.append(f"    def {method}_{len(lines)}(self, {params}):")
            body_lines = rng.randint(3, 10)
            for bl in range(body_lines):
                if len(lines) >= num_lines:
                    break
                indent = "        "
                if bl == 0:
                    lines.append(f'{indent}"""Perform {method} operation."""')
                elif rng.random() < 0.15:
                    lines.append(f"{indent}# TODO: optimize this section")
                elif rng.random() < 0.2:
                    lines.append(f"{indent}logger.debug(f\"Processing {{self.{rng.choice(var_names)}}}\")")
                elif rng.random() < 0.3:
                    v = rng.choice(var_names)
                    lines.append(f"{indent}if {v}_{bl} is not None:")
                    lines.append(f"{indent}    {rng.choice(var_names)} = {v}_{bl}")
                else:
                    lines.append(f"{indent}{rng.choice(var_names)}_{bl} = self.{rng.choice(method_names)}_{rng.randint(0, 100)}({rng.randint(0, 999)})")
            lines.append("")

    return "\n".join(lines[:num_lines])


def _generate_edit(file_content: str, seed: int) -> tuple[str, str] | None:
    """Generate a realistic (old_string, new_string) edit pair.

    Picks an actual substring from the file to ensure it exists,
    then creates a modified version.
    """
    rng = random.Random(seed)
    lines = file_content.split("\n")
    if len(lines) < 5:
        return None

    # Pick a contiguous block of 2-6 lines
    block_size = rng.randint(2, min(6, len(lines) - 1))
    start = rng.randint(0, len(lines) - block_size)
    old_lines = lines[start : start + block_size]
    old_string = "\n".join(old_lines)

    if not old_string.strip():
        return None

    # Generate a modified version
    new_lines = list(old_lines)
    action = rng.choice(["modify_line", "add_line", "rename_var", "add_comment"])
    if action == "modify_line":
        idx = rng.randint(0, len(new_lines) - 1)
        indent = len(new_lines[idx]) - len(new_lines[idx].lstrip())
        new_lines[idx] = " " * indent + f"updated_value = process_v2({rng.randint(0, 9999)})"
    elif action == "add_line":
        idx = rng.randint(0, len(new_lines))
        if new_lines:
            indent = len(new_lines[0]) - len(new_lines[0].lstrip())
        else:
            indent = 8
        new_lines.insert(idx, " " * indent + f"new_step_{rng.randint(0, 999)} = True")
    elif action == "rename_var":
        old_var = rng.choice(["result", "data", "config", "context", "buffer"])
        new_var = f"updated_{old_var}"
        new_lines = [line.replace(old_var, new_var) for line in new_lines]
    elif action == "add_comment":
        idx = rng.randint(0, len(new_lines))
        if new_lines:
            indent = len(new_lines[0]) - len(new_lines[0].lstrip())
        else:
            indent = 8
        new_lines.insert(idx, " " * indent + f"# Fixed: handle edge case for {rng.choice(['null', 'empty', 'timeout', 'retry'])}")

    new_string = "\n".join(new_lines)

    if old_string == new_string:
        return None
    return old_string, new_string


class CodeEditApplyBenchmark(BaseBenchmark):
    name = "code_edit_apply"
    description = "Exact substring search, uniqueness verification, and edit application"
    weight = 0.08

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Generate files and apply sequential edits
        # Simulates an agent making multiple edits to a file
        for file_idx in range(NUM_FILES):
            content = _generate_code_file(file_idx)

            for edit_idx in range(EDITS_PER_FILE):
                edit = _generate_edit(content, file_idx * 1000 + edit_idx)
                if edit is None:
                    continue
                old_string, new_string = edit

                # Step 1: Exact substring search
                pos = content.find(old_string)
                if pos == -1:
                    ops += 1
                    continue

                # Step 2: Uniqueness verification (full scan)
                # Must verify old_string appears exactly once
                first = content.find(old_string)
                second = content.find(old_string, first + 1)
                is_unique = second == -1
                ops += 1

                if not is_unique:
                    # In Claude Code, this causes the edit to fail
                    ops += 1
                    continue

                # Step 3: Snapshot for undo (hash the original)
                snapshot_hash = hashlib.sha256(content.encode()).hexdigest()
                ops += 1

                # Step 4: Apply the replacement
                content = content[:pos] + new_string + content[pos + len(old_string) :]
                ops += 1

                # Step 5: Verify the edit was applied correctly
                verify_pos = content.find(new_string)
                assert verify_pos != -1
                ops += 1

        # Phase 2: Large file edits (stress the substring search)
        for file_idx in range(5):
            content = _generate_code_file(file_idx + 10000, num_lines=LARGE_FILE_LINES)

            for edit_idx in range(LARGE_FILE_EDITS):
                edit = _generate_edit(content, file_idx * 10000 + edit_idx)
                if edit is None:
                    continue
                old_string, new_string = edit

                # Full scan on large file
                pos = content.find(old_string)
                if pos == -1:
                    ops += 1
                    continue

                # Uniqueness check on large file
                second = content.find(old_string, pos + 1)
                is_unique = second == -1
                ops += 1

                if is_unique:
                    snapshot = hashlib.sha256(content.encode()).hexdigest()
                    content = content[:pos] + new_string + content[pos + len(old_string) :]
                    ops += 2

        # Phase 3: Multi-file refactoring (rename across codebase)
        # Simulates renaming a function/variable across many files
        for refactor_idx in range(MULTI_FILE_REFACTORS):
            rng = random.Random(refactor_idx + 50000)
            old_name = f"process_{refactor_idx}"
            new_name = f"handle_{refactor_idx}_v2"

            files: list[str] = []
            for f in range(FILES_PER_REFACTOR):
                content = _generate_code_file(refactor_idx * 100 + f, num_lines=150)
                # Inject the target identifier so we have something to rename
                content = content.replace("process", old_name, rng.randint(1, 5))
                files.append(content)

            # Scan all files for occurrences (like grep before edit)
            for content in files:
                occurrences = []
                start = 0
                while True:
                    pos = content.find(old_name, start)
                    if pos == -1:
                        break
                    occurrences.append(pos)
                    start = pos + 1
                ops += len(occurrences) + 1

                # Apply all replacements
                if occurrences:
                    new_content = content.replace(old_name, new_name)
                    # Verify all occurrences were replaced
                    remaining = new_content.find(old_name)
                    assert remaining == -1
                    # Snapshot
                    _ = hashlib.sha256(content.encode()).hexdigest()
                    ops += 2

        # Phase 4: Context-aware edit matching
        # When old_string isn't unique, agents extend it with surrounding context
        for i in range(30):
            content = _generate_code_file(i + 90000, num_lines=500)
            rng = random.Random(i + 90000)
            lines = content.split("\n")

            for _ in range(8):
                # Pick a target line
                target_idx = rng.randint(5, len(lines) - 6)
                target = lines[target_idx]

                if not target.strip():
                    continue

                # Check if target is unique
                count = content.count(target)
                ops += 1

                if count > 1:
                    # Extend context: include surrounding lines until unique
                    ctx_size = 1
                    while ctx_size < 5:
                        start = max(0, target_idx - ctx_size)
                        end = min(len(lines), target_idx + ctx_size + 1)
                        extended = "\n".join(lines[start:end])
                        if content.count(extended) == 1:
                            break
                        ctx_size += 1
                        ops += 1

                    # Apply edit with extended context
                    extended = "\n".join(lines[max(0, target_idx - ctx_size):min(len(lines), target_idx + ctx_size + 1)])
                    if content.count(extended) == 1:
                        indent = len(target) - len(target.lstrip())
                        new_line = " " * indent + f"fixed_value = updated({rng.randint(0, 999)})"
                        new_extended = extended.replace(target, new_line, 1)
                        content = content.replace(extended, new_extended, 1)
                        ops += 1

        return ops
