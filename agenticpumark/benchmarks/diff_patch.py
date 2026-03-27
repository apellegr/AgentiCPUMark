"""Diff/Patch Computation benchmark.

Coding agents live in a world of diffs: every file edit requires computing
a diff, generating patches, and applying them. Agents read git diffs to
understand changes, produce unified diffs for edits, and apply patches to
modify files. This benchmark measures the CPU cost of line-by-line comparison,
LCS computation, and patch generation/application at scale.
"""

import difflib
import hashlib
import random
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_FILE_PAIRS = 80
FILE_LINES = 300
EDIT_RATIO = 0.15  # 15% of lines changed per edit
PATCH_APPLY_ROUNDS = 100
MULTI_FILE_DIFFS = 30
FILES_PER_MULTI = 10


def _generate_source_file(seed: int, num_lines: int = FILE_LINES) -> list[str]:
    """Generate a realistic source-code-like file."""
    rng = random.Random(seed)
    indent_levels = [0, 4, 8, 12]
    keywords = [
        "def", "class", "if", "for", "while", "return", "import", "from",
        "try", "except", "with", "async", "await", "yield", "raise",
    ]
    identifiers = [
        "process_data", "handle_request", "validate_input", "transform",
        "result", "config", "context", "manager", "handler", "service",
        "query", "response", "client", "session", "buffer", "cache",
    ]
    lines = []
    for i in range(num_lines):
        indent = " " * rng.choice(indent_levels)
        if i % 20 == 0:
            lines.append(f"{indent}class {rng.choice(identifiers).title()}_{seed}_{i}:")
        elif i % 8 == 0:
            params = ", ".join(rng.choices(identifiers, k=rng.randint(1, 4)))
            kw = rng.choice(keywords)
            name = rng.choice(identifiers)
            lines.append(f"{indent}{kw} {name}_{i}({params}):")
        elif i % 5 == 0:
            action = rng.choice(["optimize", "refactor", "fix", "document"])
            lines.append(f"{indent}# TODO: {action} this section")
        else:
            lines.append(f"{indent}{rng.choice(identifiers)} = {rng.choice(identifiers)}_{i % 10}({rng.randint(0, 100)})")
    return lines


def _apply_edits(lines: list[str], seed: int, edit_ratio: float = EDIT_RATIO) -> list[str]:
    """Apply realistic edits to a file: insertions, deletions, modifications."""
    rng = random.Random(seed + 9999)
    result = list(lines)
    num_edits = max(1, int(len(result) * edit_ratio))

    for _ in range(num_edits):
        if not result:
            break
        action = rng.choice(["modify", "modify", "insert", "delete"])
        pos = rng.randint(0, len(result) - 1)

        if action == "modify":
            old = result[pos]
            indent = len(old) - len(old.lstrip())
            result[pos] = " " * indent + f"updated_value = process({rng.randint(0, 999)})"
        elif action == "insert":
            indent = "    " * rng.randint(0, 3)
            result.insert(pos, f"{indent}new_line_{rng.randint(0, 999)} = True")
        elif action == "delete":
            result.pop(pos)

    return result


class DiffPatchBenchmark(BaseBenchmark):
    name = "diff_patch"
    description = "Line-by-line diff computation, unified diff generation, and patch application"
    weight = 0.10

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Compute unified diffs between file pairs
        # Simulates "git diff" output that agents parse constantly
        diffs: list[list[str]] = []
        for i in range(NUM_FILE_PAIRS):
            original = _generate_source_file(i)
            modified = _apply_edits(original, i)
            diff = list(difflib.unified_diff(
                original, modified,
                fromfile=f"a/src/module_{i}.py",
                tofile=f"b/src/module_{i}.py",
                lineterm="",
            ))
            diffs.append(diff)
            ops += 1

        # Phase 2: Parse diffs to extract hunk information
        # Agents parse diffs to understand what changed
        for diff in diffs:
            hunks = 0
            additions = 0
            deletions = 0
            for line in diff:
                if line.startswith("@@"):
                    hunks += 1
                elif line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1
            ops += hunks + additions + deletions

        # Phase 3: Sequence matching (LCS-based) for similarity scoring
        # Used when agents need to find the best match for an edit location
        for i in range(NUM_FILE_PAIRS):
            original = _generate_source_file(i)
            modified = _apply_edits(original, i)
            matcher = difflib.SequenceMatcher(None, original, modified)
            ratio = matcher.ratio()
            blocks = matcher.get_matching_blocks()
            ops += len(blocks)

        # Phase 4: Generate and apply patches in sequence
        # Simulates the edit -> verify -> edit cycle of coding agents
        base_file = _generate_source_file(0, num_lines=200)
        current = list(base_file)
        for i in range(PATCH_APPLY_ROUNDS):
            edited = _apply_edits(current, i + 10000, edit_ratio=0.05)
            # Compute the diff
            diff = list(difflib.unified_diff(current, edited, lineterm=""))
            # "Apply" by computing a fresh merge
            merger = difflib.SequenceMatcher(None, current, edited)
            merged: list[str] = []
            for tag, i1, i2, j1, j2 in merger.get_opcodes():
                if tag == "equal":
                    merged.extend(current[i1:i2])
                elif tag == "replace":
                    merged.extend(edited[j1:j2])
                elif tag == "insert":
                    merged.extend(edited[j1:j2])
                elif tag == "delete":
                    pass  # skip deleted lines
            current = merged
            ops += len(diff)

        # Phase 5: Multi-file diff aggregation
        # Agents process PRs/commits with changes across many files
        for i in range(MULTI_FILE_DIFFS):
            all_changes: list[str] = []
            file_stats: dict[str, dict[str, int]] = {}
            for j in range(FILES_PER_MULTI):
                seed = i * FILES_PER_MULTI + j
                original = _generate_source_file(seed, num_lines=100)
                modified = _apply_edits(original, seed)
                diff = list(difflib.unified_diff(
                    original, modified,
                    fromfile=f"a/src/pkg_{i}/file_{j}.py",
                    tofile=f"b/src/pkg_{i}/file_{j}.py",
                    lineterm="",
                ))
                all_changes.extend(diff)
                adds = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
                dels = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
                file_stats[f"file_{j}.py"] = {"additions": adds, "deletions": dels}
                ops += 1

            # Compute aggregate stats (like a PR summary)
            total_adds = sum(s["additions"] for s in file_stats.values())
            total_dels = sum(s["deletions"] for s in file_stats.values())
            _ = hashlib.sha256("\n".join(all_changes).encode()).hexdigest()
            ops += 1

        return ops
