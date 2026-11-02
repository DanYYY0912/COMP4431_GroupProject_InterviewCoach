"""Strict training/evaluation schemas; matching the application model boundary."""

import math


def obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


def arr(items):
    return {"type": "array", "items": items}


S = {"type": "string"}
B = {"type": "boolean"}
NULLABLE_S = {"type": ["string", "null"]}
COACH_TURN = obj(
    {
        "interviewer_text": {"type": "string", "minLength": 1, "maxLength": 4000},
        "question_type": {
            "type": "string",
            "enum": ["opening", "behavioral", "technical", "follow_up", "closing"],
        },
        "targeted_competencies": {
            "type": "array",
            "items": S,
            "minItems": 1,
            "maxItems": 8,
        },
        "adaptive_follow_up_reason": NULLABLE_S,
        "citation_ids": {"type": "array", "items": S, "minItems": 1, "maxItems": 4},
    }
)
STAR = obj(
    {
        "element": {
            "type": "string",
            "enum": ["Situation", "Task", "Action", "Result"],
        },
        "present": B,
        "evidence": S,
        "coaching": S,
    }
)
REPORT = obj(
    {
        "star": {"type": "array", "items": STAR, "minItems": 4, "maxItems": 4},
        "competencies": {
            "type": "array",
            "maxItems": 8,
            "items": obj(
                {
                    "name": S,
                    "evidence": S,
                    "feedback": S,
                    "citation_ids": {
                        "type": "array",
                        "items": S,
                        "minItems": 1,
                        "maxItems": 4,
                    },
                }
            ),
        },
        "strengths": {
            "type": "array",
            "maxItems": 4,
            "items": obj(
                {
                    "text": S,
                    "evidence": {"type": "string", "minLength": 1},
                }
            ),
        },
        "prioritized_improvement": {
            "type": "string",
            "minLength": 1,
            "maxLength": 1500,
        },
        "retry_exercise": {"type": "string", "minLength": 1, "maxLength": 2000},
    }
)
# These are the LLM boundary schemas, not the public SessionReport/Citation API.
# Backend attaches authoritative citation text and computes speech metrics itself.
SCHEMAS = {
    "question": COACH_TURN,
    "safety": COACH_TURN,
    "feedback": REPORT,
    "report": REPORT,
}


def validate(value, schema, path="$"):
    """Return errors for this small, explicit JSON Schema subset."""
    errors = []
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    match = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if kinds and not any(match.get(k, False) for k in kinds):
        return [f"{path}: wrong type, expected {kinds}"]
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and not math.isfinite(value)
    ):
        errors.append(f"{path}: nonfinite number")
    if isinstance(value, str) and not schema.get("minLength", 0) <= len(
        value
    ) <= schema.get("maxLength", float("inf")):
        errors.append(f"{path}: invalid string length")
    if isinstance(value, list) and not schema.get("minItems", 0) <= len(
        value
    ) <= schema.get("maxItems", float("inf")):
        errors.append(f"{path}: invalid array length")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: outside enum")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: missing")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key not in properties:
                if schema.get("additionalProperties") is False:
                    errors.append(f"{path}.{key}: unknown field")
            else:
                errors.extend(validate(item, properties[key], f"{path}.{key}"))
    if isinstance(value, list):
        for i, item in enumerate(value):
            errors.extend(validate(item, schema.get("items", {}), f"{path}[{i}]"))
    return errors
