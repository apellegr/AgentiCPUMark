"""Schema Validation & JSON Repair benchmark.

Every MCP tool call involves JSON Schema validation of inputs and outputs.
LLMs also frequently produce malformed JSON that agent infrastructure must
repair before parsing: trailing commas, missing brackets, markdown code
fences, unquoted keys, single quotes, and truncated output. This benchmark
measures the CPU cost of schema compilation, validation, and repair at the
frequency seen in real agent workloads.
"""

import json
import re
import random
from agenticpumark.benchmarks.base import BaseBenchmark

NUM_SCHEMAS = 100
VALIDATIONS_PER_SCHEMA = 50
MALFORMED_REPAIRS = 1000
NESTED_VALIDATION_DEPTH = 8


def _generate_schema(seed: int) -> dict:
    """Generate a JSON Schema typical of MCP tool definitions."""
    rng = random.Random(seed)
    types = ["string", "integer", "number", "boolean", "array", "object"]

    def make_property(depth: int = 0) -> dict:
        ptype = rng.choice(types if depth < 3 else types[:4])
        prop: dict = {"type": ptype}
        if ptype == "string":
            if rng.random() < 0.3:
                prop["enum"] = [f"opt_{i}" for i in range(rng.randint(2, 8))]
            if rng.random() < 0.2:
                prop["minLength"] = 1
                prop["maxLength"] = rng.randint(100, 10000)
            if rng.random() < 0.15:
                prop["pattern"] = r"^[a-zA-Z0-9_-]+$"
        elif ptype == "integer":
            if rng.random() < 0.4:
                prop["minimum"] = 0
                prop["maximum"] = rng.randint(10, 10000)
        elif ptype == "number":
            if rng.random() < 0.3:
                prop["minimum"] = 0.0
                prop["maximum"] = 1.0
        elif ptype == "array":
            prop["items"] = make_property(depth + 1)
            if rng.random() < 0.3:
                prop["minItems"] = 1
                prop["maxItems"] = rng.randint(5, 100)
        elif ptype == "object" and depth < 3:
            num_props = rng.randint(2, 6)
            props = {}
            for j in range(num_props):
                props[f"field_{j}"] = make_property(depth + 1)
            prop["properties"] = props
            prop["required"] = [f"field_{k}" for k in range(min(2, num_props))]
        return prop

    num_properties = rng.randint(3, 15)
    properties = {}
    for i in range(num_properties):
        properties[f"param_{i}"] = make_property()

    required = [f"param_{i}" for i in range(min(4, num_properties))]

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _generate_valid_instance(schema: dict, seed: int) -> dict:
    """Generate a value that conforms to the given schema."""
    rng = random.Random(seed)

    def gen_value(prop: dict) -> object:
        ptype = prop.get("type", "string")
        if ptype == "string":
            if "enum" in prop:
                return rng.choice(prop["enum"])
            length = rng.randint(prop.get("minLength", 1), min(prop.get("maxLength", 50), 50))
            return "".join(rng.choices("abcdefghijklmnop0123456789_-", k=length))
        elif ptype == "integer":
            lo = prop.get("minimum", 0)
            hi = prop.get("maximum", 1000)
            return rng.randint(lo, hi)
        elif ptype == "number":
            lo = prop.get("minimum", 0.0)
            hi = prop.get("maximum", 100.0)
            return round(rng.uniform(lo, hi), 4)
        elif ptype == "boolean":
            return rng.choice([True, False])
        elif ptype == "array":
            items_schema = prop.get("items", {"type": "string"})
            count = rng.randint(prop.get("minItems", 1), min(prop.get("maxItems", 5), 5))
            return [gen_value(items_schema) for _ in range(count)]
        elif ptype == "object":
            obj = {}
            for key, sub_schema in prop.get("properties", {}).items():
                obj[key] = gen_value(sub_schema)
            return obj
        return None

    result = {}
    for key, prop in schema.get("properties", {}).items():
        result[key] = gen_value(prop)
    return result


def _validate(instance: object, schema: dict) -> list[str]:
    """Validate a JSON instance against a schema. Returns list of errors.

    This is a simplified but realistic validator covering the types and
    constraints used in MCP tool schemas.
    """
    errors: list[str] = []

    def check(value: object, sch: dict, path: str) -> None:
        expected_type = sch.get("type")
        if expected_type == "object":
            if not isinstance(value, dict):
                errors.append(f"{path}: expected object, got {type(value).__name__}")
                return
            # Check required fields
            for req in sch.get("required", []):
                if req not in value:
                    errors.append(f"{path}: missing required field '{req}'")
            # Check additional properties
            if not sch.get("additionalProperties", True):
                allowed = set(sch.get("properties", {}).keys())
                for key in value:
                    if key not in allowed:
                        errors.append(f"{path}: unexpected field '{key}'")
            # Recurse into properties
            for key, prop_schema in sch.get("properties", {}).items():
                if key in value:
                    check(value[key], prop_schema, f"{path}.{key}")
        elif expected_type == "array":
            if not isinstance(value, list):
                errors.append(f"{path}: expected array, got {type(value).__name__}")
                return
            min_items = sch.get("minItems")
            max_items = sch.get("maxItems")
            if min_items is not None and len(value) < min_items:
                errors.append(f"{path}: too few items ({len(value)} < {min_items})")
            if max_items is not None and len(value) > max_items:
                errors.append(f"{path}: too many items ({len(value)} > {max_items})")
            items_schema = sch.get("items", {})
            for i, item in enumerate(value):
                check(item, items_schema, f"{path}[{i}]")
        elif expected_type == "string":
            if not isinstance(value, str):
                errors.append(f"{path}: expected string, got {type(value).__name__}")
                return
            if "enum" in sch and value not in sch["enum"]:
                errors.append(f"{path}: value not in enum")
            if "minLength" in sch and len(value) < sch["minLength"]:
                errors.append(f"{path}: string too short")
            if "maxLength" in sch and len(value) > sch["maxLength"]:
                errors.append(f"{path}: string too long")
            if "pattern" in sch and not re.match(sch["pattern"], value):
                errors.append(f"{path}: pattern mismatch")
        elif expected_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"{path}: expected integer")
                return
            if "minimum" in sch and value < sch["minimum"]:
                errors.append(f"{path}: below minimum")
            if "maximum" in sch and value > sch["maximum"]:
                errors.append(f"{path}: above maximum")
        elif expected_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"{path}: expected number")
                return
            if "minimum" in sch and value < sch["minimum"]:
                errors.append(f"{path}: below minimum")
            if "maximum" in sch and value > sch["maximum"]:
                errors.append(f"{path}: above maximum")
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"{path}: expected boolean")

    check(instance, schema, "$")
    return errors


def _repair_json(malformed: str) -> str | None:
    """Attempt to repair malformed JSON from LLM output.

    Handles common LLM JSON errors:
    - Markdown code fences (```json ... ```)
    - Trailing commas
    - Single quotes instead of double quotes
    - Unquoted keys
    - Truncated output (missing closing brackets)
    - Comments (// and /* */)
    """
    text = malformed.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Remove comments
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # Replace single quotes with double quotes (careful with apostrophes)
    text = re.sub(r"(?<=[\[{,:\s])'|'(?=[\]},:.\s])", '"', text)

    # Quote unquoted keys: word: -> "word":
    text = re.sub(r"(?<=[\{,\s])(\w+)\s*:", r'"\1":', text)

    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Fix truncated output: balance brackets
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")
    text += "]" * max(0, open_brackets)
    text += "}" * max(0, open_braces)

    try:
        _ = json.loads(text)
        return text
    except json.JSONDecodeError:
        return None


def _generate_malformed_json(seed: int) -> str:
    """Generate realistically malformed JSON that an LLM might produce."""
    rng = random.Random(seed)
    base_obj = {
        "tool": f"tool_{rng.randint(0, 50)}",
        "arguments": {
            f"param_{i}": f"value_{rng.randint(0, 999)}"
            for i in range(rng.randint(2, 8))
        },
        "metadata": {
            "step": rng.randint(1, 20),
            "confidence": round(rng.random(), 3),
        },
    }
    valid_json = json.dumps(base_obj, indent=2)

    # Apply one or more corruptions
    corruptions = rng.sample([
        "markdown_fence",
        "trailing_comma",
        "single_quotes",
        "unquoted_keys",
        "truncated",
        "comments",
    ], k=rng.randint(1, 3))

    result = valid_json
    for corruption in corruptions:
        if corruption == "markdown_fence":
            result = f"```json\n{result}\n```"
        elif corruption == "trailing_comma":
            # Add trailing comma before a closing brace
            result = result.replace("}\n}", "},\n}")
        elif corruption == "single_quotes":
            result = result.replace('"tool"', "'tool'").replace('"arguments"', "'arguments'")
        elif corruption == "unquoted_keys":
            result = re.sub(r'"(param_\d+)":', r"\1:", result)
        elif corruption == "truncated":
            cut_point = int(len(result) * rng.uniform(0.6, 0.9))
            result = result[:cut_point]
        elif corruption == "comments":
            lines = result.split("\n")
            insert_at = rng.randint(1, max(1, len(lines) - 2))
            lines.insert(insert_at, "  // LLM reasoning about this value")
            result = "\n".join(lines)

    return result


class SchemaValidationBenchmark(BaseBenchmark):
    name = "schema_validation"
    description = "JSON Schema validation, compilation, and malformed JSON repair"
    weight = 0.10

    def run_once(self) -> int:
        ops = 0

        # Phase 1: Generate and compile schemas
        schemas = [_generate_schema(i) for i in range(NUM_SCHEMAS)]
        ops += len(schemas)

        # Phase 2: Validate valid instances
        for i, schema in enumerate(schemas):
            for j in range(VALIDATIONS_PER_SCHEMA):
                instance = _generate_valid_instance(schema, seed=i * 1000 + j)
                errors = _validate(instance, schema)
                ops += 1

        # Phase 3: Validate invalid instances (intentionally wrong types)
        rng = random.Random(42)
        for i, schema in enumerate(schemas):
            for j in range(VALIDATIONS_PER_SCHEMA // 2):
                instance = _generate_valid_instance(schema, seed=i * 1000 + j)
                # Corrupt some fields
                keys = list(instance.keys())
                if keys:
                    corrupt_key = rng.choice(keys)
                    instance[corrupt_key] = rng.choice([
                        None, "wrong_type", 99999, True, [], {},
                    ])
                errors = _validate(instance, schema)
                ops += 1 + len(errors)

        # Phase 4: Repair malformed JSON from LLM output
        repair_success = 0
        for i in range(MALFORMED_REPAIRS):
            malformed = _generate_malformed_json(i)
            repaired = _repair_json(malformed)
            if repaired is not None:
                # Verify the repair produced valid JSON
                try:
                    parsed = json.loads(repaired)
                    repair_success += 1
                except json.JSONDecodeError:
                    pass
            ops += 1

        # Phase 5: Deeply nested schema validation
        # Some tool responses have deeply nested structures
        def make_nested_schema(depth: int) -> dict:
            if depth <= 0:
                return {"type": "string"}
            return {
                "type": "object",
                "properties": {
                    "value": {"type": "integer"},
                    "label": {"type": "string"},
                    "nested": make_nested_schema(depth - 1),
                },
                "required": ["value", "nested"],
            }

        def make_nested_instance(depth: int, seed: int) -> dict:
            r = random.Random(seed)
            if depth <= 0:
                return "leaf"  # type: ignore[return-value]
            return {
                "value": r.randint(0, 100),
                "label": f"level_{depth}",
                "nested": make_nested_instance(depth - 1, seed + 1),
            }

        for depth in range(1, NESTED_VALIDATION_DEPTH + 1):
            schema = make_nested_schema(depth)
            for j in range(50):
                instance = make_nested_instance(depth, j)
                errors = _validate(instance, schema)
                ops += depth  # validation cost scales with depth

        return ops
