"""JSON Processing benchmark.

AI agents communicate almost entirely via JSON: tool schemas, function call
arguments, structured responses, conversation histories. This benchmark
measures serialization and deserialization throughput on structures that
mirror real agent traffic.
"""

import json
import random
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_TOOL_SCHEMAS = 200
NUM_CONVERSATIONS = 100
MESSAGES_PER_CONVERSATION = 50
NUM_ROUND_TRIPS = 500


def _generate_tool_schema(seed: int) -> dict:
    """Generate a realistic tool-use JSON schema."""
    rng = random.Random(seed)
    param_count = rng.randint(2, 12)
    params = {}
    for j in range(param_count):
        ptype = rng.choice(["string", "integer", "boolean", "array", "object"])
        param: dict = {"type": ptype, "description": f"Parameter {j} for tool {seed}"}
        if ptype == "array":
            param["items"] = {"type": "string"}
        if ptype == "object":
            param["properties"] = {
                f"sub_{k}": {"type": "string"} for k in range(rng.randint(1, 5))
            }
        params[f"param_{j}"] = param

    return {
        "name": f"tool_{seed}",
        "description": f"A tool that performs operation {seed} with various parameters",
        "parameters": {
            "type": "object",
            "properties": params,
            "required": [f"param_{k}" for k in range(min(3, param_count))],
        },
    }


def _generate_conversation(seed: int) -> list[dict]:
    """Generate a realistic multi-turn agent conversation."""
    rng = random.Random(seed)
    messages = []
    roles = ["user", "assistant", "tool"]
    for i in range(MESSAGES_PER_CONVERSATION):
        role = roles[i % 3]
        content: str | list[dict]
        if role == "tool":
            content = json.dumps({
                "result": {"data": [rng.random() for _ in range(20)]},
                "metadata": {"latency_ms": rng.randint(10, 500)},
            })
        elif role == "assistant":
            content = [
                {"type": "text", "text": f"Step {i}: analyzing results..."},
                {
                    "type": "tool_use",
                    "name": f"tool_{rng.randint(0, 50)}",
                    "arguments": {
                        f"param_{k}": f"value_{rng.randint(0, 1000)}"
                        for k in range(rng.randint(1, 6))
                    },
                },
            ]
        else:
            content = f"User message {i} with context about task {seed}"

        messages.append({"role": role, "content": content})
    return messages


class JsonProcessingBenchmark(BaseBenchmark):
    name = "json_processing"
    description = "Serialization & deserialization of agent tool schemas and conversations"
    weight = 0.20

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Generate and serialize tool schemas
        schemas = [_generate_tool_schema(i) for i in range(NUM_TOOL_SCHEMAS)]
        serialized_schemas = []
        for schema in schemas:
            serialized_schemas.append(json.dumps(schema, separators=(",", ":")))
            ops += 1

        # Phase 2: Deserialize all schemas back
        for s in serialized_schemas:
            _ = json.loads(s)
            ops += 1

        # Phase 3: Generate, serialize, and deserialize conversations
        for i in range(NUM_CONVERSATIONS):
            conversation = _generate_conversation(i)
            encoded = json.dumps(conversation)
            decoded = json.loads(encoded)
            # Simulate extracting tool calls from the conversation
            for msg in decoded:
                if isinstance(msg.get("content"), list):
                    for block in msg["content"]:
                        if block.get("type") == "tool_use":
                            _ = json.dumps(block["arguments"])
                            ops += 1
            ops += 2  # serialize + deserialize

        # Phase 4: Rapid small round-trips (function call -> result pattern)
        for i in range(NUM_ROUND_TRIPS):
            call = {
                "id": f"call_{i}",
                "function": f"tool_{i % 50}",
                "arguments": {"query": f"search term {i}", "limit": i % 20 + 1},
            }
            wire = json.dumps(call)
            back = json.loads(wire)
            result = {"id": back["id"], "output": {"matches": list(range(back["arguments"]["limit"]))}}
            wire2 = json.dumps(result)
            _ = json.loads(wire2)
            ops += 4

        return ops
