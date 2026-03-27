"""Text Processing benchmark.

Agents process large volumes of text: splitting documents into chunks,
applying regex patterns for extraction, searching and replacing content,
and performing tokenizer-like byte-pair operations. This benchmark
targets the string-manipulation hot paths in agent infrastructure.
"""

import re
import hashlib
from agenticpumark.benchmarks.base import BaseBenchmark

CORPUS_SIZE = 500_000  # characters
CHUNK_SIZES = [256, 512, 1024, 2048, 4096]
NUM_REGEX_PATTERNS = 20


def _build_corpus(size: int) -> str:
    """Build a pseudo-realistic text corpus without external dependencies."""
    words = [
        "the", "agent", "function", "tool", "result", "query", "search",
        "context", "window", "token", "embedding", "model", "inference",
        "parameter", "schema", "response", "request", "error", "success",
        "data", "pipeline", "batch", "stream", "async", "await", "process",
        "memory", "cache", "index", "vector", "dimension", "layer", "weight",
        "gradient", "optimize", "transform", "encode", "decode", "parse",
        "serialize", "validate", "dispatch", "execute", "monitor", "trace",
    ]
    corpus = []
    total = 0
    i = 0
    while total < size:
        word = words[i % len(words)]
        # Add some structure: newlines, punctuation
        if i % 15 == 0:
            word += ".\n"
        elif i % 7 == 0:
            word += ","
        corpus.append(word)
        total += len(word) + 1
        i += 1
    return " ".join(corpus)[:size]


def _build_regex_patterns() -> list[re.Pattern]:
    """Build regex patterns typical of agent text extraction."""
    patterns = [
        r"\b\w+_\w+\b",                     # snake_case identifiers
        r"\b[A-Z][a-z]+[A-Z]\w*\b",         # camelCase identifiers
        r'"[^"]{1,100}"',                    # quoted strings
        r"\b\d{1,5}\b",                      # numbers
        r"\b(?:error|Error|ERROR)\b",        # error mentions
        r"\b(?:function|tool|agent)\s+\w+",  # function/tool declarations
        r"```[\s\S]{1,200}?```",             # code blocks
        r"\b\w{10,}\b",                      # long words
        r"(?<=\s)\w+(?=,)",                  # words before commas
        r"\b(?:async|await|process)\b",      # async keywords
        r"\.\w+\(",                          # method calls
        r"\b[a-f0-9]{8,}\b",                # hex strings
        r"(?:https?://)\S+",                 # URLs
        r"\b\w+ing\b",                       # gerunds
        r"\b(?:the|a|an)\s+\w+",             # articles + noun
        r"\w+\.\w+\.\w+",                    # dotted paths
        r"\[\d+\]",                          # array indices
        r"\b\d+\.\d+\b",                     # floating point
        r"(?<=\n)\w+",                       # line starters
        r"\b\w+(?:ize|ise)\b",              # -ize/-ise verbs
    ]
    return [re.compile(p) for p in patterns[:NUM_REGEX_PATTERNS]]


class TextProcessingBenchmark(BaseBenchmark):
    name = "text_processing"
    description = "Tokenizer-like chunking, regex parsing, and string manipulation"
    weight = 0.20

    def run_once(self) -> int:
        ops = 0
        corpus = _build_corpus(CORPUS_SIZE)

        # Phase 1: Overlapping chunk splitting (like document chunking for RAG)
        for chunk_size in CHUNK_SIZES:
            overlap = chunk_size // 4
            pos = 0
            while pos < len(corpus):
                chunk = corpus[pos : pos + chunk_size]
                # Simulate computing a content hash for deduplication
                _ = hashlib.md5(chunk.encode()).hexdigest()
                pos += chunk_size - overlap
                ops += 1

        # Phase 2: Regex extraction across the corpus
        patterns = _build_regex_patterns()
        for pattern in patterns:
            matches = pattern.findall(corpus)
            ops += len(matches)

        # Phase 3: Byte-pair-like frequency counting
        pair_counts: dict[str, int] = {}
        for i in range(min(100_000, len(corpus) - 1)):
            pair = corpus[i : i + 2]
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
            ops += 1

        # Phase 4: Top-k frequent pair merging (simplified BPE step)
        sorted_pairs = sorted(pair_counts.items(), key=lambda x: -x[1])[:100]
        text = corpus[:50_000]
        for pair, _ in sorted_pairs[:20]:
            text = text.replace(pair, pair[0].upper() + pair[1].upper())
            ops += 1

        # Phase 5: Line-by-line processing (log parsing pattern)
        lines = corpus.split("\n")
        for line in lines:
            stripped = line.strip().lower()
            tokens = stripped.split()
            _ = len(tokens)
            ops += 1

        return ops
