"""Streaming JSON Parse benchmark.

AI agent clients (Claude Code, Cursor, Copilot, etc.) receive LLM responses
as Server-Sent Event (SSE) streams. Tool call arguments arrive as
`input_json_delta` fragments — partial JSON strings that must be
accumulated, validated, and assembled into complete objects. This is the
agent's main hot loop: it runs continuously during every API response,
often processing hundreds of chunks per second.

This benchmark was added after introspecting Claude Code's live behavior.
Profiling showed that every API turn involves:
  1. Parsing chunked HTTP/SSE framing (event: / data: lines)
  2. Deserializing each SSE event envelope (small JSON objects)
  3. Accumulating `input_json_delta` text fragments into a buffer
  4. Attempting JSON parse on the growing buffer to detect completion
  5. Handling multiple concurrent tool calls within a single response
  6. Processing interleaved text deltas and tool-call deltas
"""

import json
import random
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_RESPONSES = 50
TOOL_CALLS_PER_RESPONSE = 5
CHUNKS_PER_TOOL_CALL = 40
TEXT_DELTAS_PER_RESPONSE = 80
MULTI_STREAM_SESSIONS = 20  # parallel sub-agent sessions


def _generate_tool_call_json(seed: int) -> str:
    """Generate a realistic tool call JSON that will be fragmented."""
    rng = random.Random(seed)
    tool_names = [
        "Read", "Edit", "Grep", "Glob", "Bash", "Write",
        "WebSearch", "WebFetch", "mcp__github__search",
        "mcp__postgres__query", "mcp__filesystem__read",
    ]
    tool = rng.choice(tool_names)

    if tool == "Read":
        args = {
            "file_path": f"/home/user/project/src/{'pkg_' + str(rng.randint(0, 20))}/{'module_' + str(rng.randint(0, 50))}.py",
            "offset": rng.randint(0, 500),
            "limit": rng.randint(50, 200),
        }
    elif tool == "Edit":
        old_lines = [f"    line_{i} = compute({rng.randint(0, 999)})" for i in range(rng.randint(3, 12))]
        new_lines = [f"    updated_{i} = process({rng.randint(0, 999)})" for i in range(rng.randint(3, 12))]
        args = {
            "file_path": f"/home/user/project/src/module_{rng.randint(0, 50)}.py",
            "old_string": "\n".join(old_lines),
            "new_string": "\n".join(new_lines),
        }
    elif tool == "Grep":
        args = {
            "pattern": f"def {rng.choice(['process', 'handle', 'validate', 'transform'])}.*{rng.choice(['data', 'request', 'input', 'result'])}",
            "path": "/home/user/project/src",
            "output_mode": rng.choice(["content", "files_with_matches"]),
            "glob": "*.py",
        }
    elif tool == "Bash":
        cmds = [
            f"cd /home/user/project && python -m pytest tests/ -x -v 2>&1 | head -50",
            f"git diff --stat HEAD~{rng.randint(1, 5)}",
            f"rg -l 'TODO|FIXME|HACK' --type py | head -20",
            f"python -c 'import json; print(json.dumps({{\"status\": \"ok\"}}))'",
        ]
        args = {"command": rng.choice(cmds), "description": "Run command"}
    else:
        args = {
            f"param_{i}": f"value_{rng.randint(0, 9999)}" * rng.randint(1, 5)
            for i in range(rng.randint(2, 8))
        }

    return json.dumps({
        "type": "tool_use",
        "id": f"toolu_{seed:08x}",
        "name": tool,
        "input": args,
    })


def _fragment_json(full_json: str, num_chunks: int, rng: random.Random) -> list[str]:
    """Split a JSON string into irregular chunks (simulating SSE deltas)."""
    chunks = []
    pos = 0
    remaining = len(full_json)
    for i in range(num_chunks - 1):
        if pos >= len(full_json):
            break
        # Chunks are irregularly sized (real SSE chunks vary widely)
        max_size = max(1, remaining // (num_chunks - i))
        chunk_size = rng.randint(1, max(1, max_size * 2))
        chunk_size = min(chunk_size, len(full_json) - pos)
        chunks.append(full_json[pos : pos + chunk_size])
        pos += chunk_size
        remaining = len(full_json) - pos
    if pos < len(full_json):
        chunks.append(full_json[pos:])
    return chunks


def _generate_sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _generate_sse_stream(seed: int) -> str:
    """Generate a full SSE stream for one API response with interleaved content."""
    rng = random.Random(seed)
    events: list[str] = []

    # message_start
    events.append(_generate_sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": f"msg_{seed:08x}",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-4-6",
            "usage": {"input_tokens": rng.randint(1000, 50000), "output_tokens": 0},
        },
    }))

    block_index = 0

    # Interleave text blocks and tool-use blocks
    for tc_idx in range(TOOL_CALLS_PER_RESPONSE):
        # Text block before each tool call (reasoning)
        events.append(_generate_sse_event("content_block_start", {
            "type": "content_block_start",
            "index": block_index,
            "content_block": {"type": "text", "text": ""},
        }))
        reasoning_text = f"Let me analyze step {tc_idx + 1}. I need to " + " ".join(
            rng.choices(["check", "verify", "read", "search", "examine", "process"], k=rng.randint(5, 20))
        ) + f" the relevant {'files' if rng.random() < 0.5 else 'code'}."
        # Text arrives as small deltas
        for i in range(0, len(reasoning_text), rng.randint(3, 15)):
            chunk = reasoning_text[i : i + rng.randint(3, 15)]
            events.append(_generate_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": block_index,
                "delta": {"type": "text_delta", "text": chunk},
            }))
        events.append(_generate_sse_event("content_block_stop", {
            "type": "content_block_stop",
            "index": block_index,
        }))
        block_index += 1

        # Tool-use block
        tool_json = _generate_tool_call_json(seed * 100 + tc_idx)
        tool_obj = json.loads(tool_json)
        events.append(_generate_sse_event("content_block_start", {
            "type": "content_block_start",
            "index": block_index,
            "content_block": {
                "type": "tool_use",
                "id": tool_obj["id"],
                "name": tool_obj["name"],
                "input": {},
            },
        }))

        # Input arrives as JSON delta fragments
        input_json = json.dumps(tool_obj["input"])
        fragments = _fragment_json(input_json, CHUNKS_PER_TOOL_CALL, rng)
        for frag in fragments:
            events.append(_generate_sse_event("content_block_delta", {
                "type": "content_block_delta",
                "index": block_index,
                "delta": {"type": "input_json_delta", "partial_json": frag},
            }))

        events.append(_generate_sse_event("content_block_stop", {
            "type": "content_block_stop",
            "index": block_index,
        }))
        block_index += 1

    # message_delta (stop reason)
    events.append(_generate_sse_event("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use"},
        "usage": {"output_tokens": rng.randint(200, 2000)},
    }))

    events.append(_generate_sse_event("message_stop", {"type": "message_stop"}))

    return "".join(events)


class StreamingParseBenchmark(BaseBenchmark):
    name = "streaming_parse"
    description = "SSE stream parsing with fragmented tool-call JSON accumulation"
    weight = 0.08

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Parse SSE streams and accumulate tool calls
        for i in range(NUM_RESPONSES):
            stream = _generate_sse_stream(i)
            ops += self._parse_sse_stream(stream)

        # Phase 2: Simulate multiple concurrent sub-agent streams
        # (Claude Code runs sub-agents in parallel, each with its own stream)
        for session in range(MULTI_STREAM_SESSIONS):
            streams = [_generate_sse_stream(session * 100 + j) for j in range(3)]
            # Process streams in round-robin (simulating event loop multiplexing)
            stream_states: list[dict] = [
                {"lines": s.split("\n"), "pos": 0, "buffers": {}, "tool_calls": []}
                for s in streams
            ]
            active = True
            while active:
                active = False
                for state in stream_states:
                    if state["pos"] < len(state["lines"]):
                        active = True
                        # Process a small batch of lines from this stream
                        batch_end = min(state["pos"] + 5, len(state["lines"]))
                        for idx in range(state["pos"], batch_end):
                            line = state["lines"][idx]
                            if line.startswith("data: "):
                                try:
                                    event = json.loads(line[6:])
                                    delta = event.get("delta", {})
                                    block_idx = event.get("index", 0)

                                    if delta.get("type") == "input_json_delta":
                                        buf = state["buffers"].get(block_idx, "")
                                        buf += delta["partial_json"]
                                        state["buffers"][block_idx] = buf
                                        # Attempt parse to detect completion
                                        try:
                                            parsed = json.loads(buf)
                                            state["tool_calls"].append(parsed)
                                            state["buffers"].pop(block_idx, None)
                                        except json.JSONDecodeError:
                                            pass
                                        ops += 1
                                    elif delta.get("type") == "text_delta":
                                        _ = delta.get("text", "")
                                        ops += 1
                                except json.JSONDecodeError:
                                    pass
                        state["pos"] = batch_end

        # Phase 3: Rapid small-event parsing (ping/heartbeat pattern)
        # Real SSE connections send periodic pings
        for i in range(5000):
            event_str = f"event: ping\ndata: {{\"type\": \"ping\", \"ts\": {i}}}\n\n"
            lines = event_str.split("\n")
            for line in lines:
                if line.startswith("data: "):
                    _ = json.loads(line[6:])
                    ops += 1

        return ops

    def _parse_sse_stream(self, stream: str) -> int:
        """Parse a single SSE stream, accumulating tool calls."""
        ops = 0
        json_buffers: dict[int, str] = {}
        tool_calls: list[dict] = []
        text_content: list[str] = []
        current_event_type = ""

        for line in stream.split("\n"):
            if line.startswith("event: "):
                current_event_type = line[7:]
                ops += 1
            elif line.startswith("data: "):
                try:
                    event = json.loads(line[6:])
                    ops += 1

                    etype = event.get("type", "")

                    if etype == "content_block_delta":
                        delta = event["delta"]
                        block_index = event["index"]

                        if delta["type"] == "input_json_delta":
                            # Accumulate JSON fragment
                            buf = json_buffers.get(block_index, "")
                            buf += delta["partial_json"]
                            json_buffers[block_index] = buf

                            # Try to parse accumulated JSON (agents do this
                            # on every chunk to detect completion ASAP)
                            try:
                                parsed = json.loads(buf)
                                tool_calls.append(parsed)
                                json_buffers.pop(block_index, None)
                            except json.JSONDecodeError:
                                pass
                            ops += 1

                        elif delta["type"] == "text_delta":
                            text_content.append(delta["text"])
                            ops += 1

                    elif etype == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            # Initialize tool call tracking
                            json_buffers[event["index"]] = ""
                            ops += 1

                    elif etype in ("message_start", "message_delta", "message_stop",
                                   "content_block_stop"):
                        ops += 1

                except json.JSONDecodeError:
                    pass

        # Final: join all text content (agents need the full text)
        full_text = "".join(text_content)
        _ = len(full_text)
        ops += 1

        return ops
