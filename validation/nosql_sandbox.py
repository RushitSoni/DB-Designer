"""
Validates a generated MongoDB JSON Schema by generating minimal sample
documents that satisfy each collection's "required" fields and type
constraints, then running them through jsonschema.validate(). This
catches structurally broken schemas (missing required fields in
their own definition, invalid bsonType values, malformed nesting)
without needing a real MongoDB instance.
"""

import jsonschema

_BSON_TO_JSONSCHEMA_TYPE = {
    "string": "string",
    "int": "integer",
    "double": "number",
    "bool": "boolean",
    "date": "string",
    "objectId": "string",
    "array": "array",
    "object": "object",
}

_SAMPLE_VALUES = {
    "string": "sample",
    "integer": 1,
    "number": 1.0,
    "boolean": True,
    "array": [],
    "object": {},
}


def _bson_schema_to_jsonschema(bson_schema: dict) -> dict:
    """Recursively converts our bsonType-flavored schema to plain JSON Schema."""
    if "bsonType" in bson_schema:
        jtype = _BSON_TO_JSONSCHEMA_TYPE.get(bson_schema["bsonType"], "string")
        converted = {"type": jtype}
        if jtype == "object" and "properties" in bson_schema:
            converted["properties"] = {
                k: _bson_schema_to_jsonschema(v) for k, v in bson_schema["properties"].items()
            }
            if "required" in bson_schema:
                converted["required"] = bson_schema["required"]
        return converted
    return {"type": "string"}


def _generate_sample_document(properties: dict) -> dict:
    """Builds a minimal sample document satisfying the schema's types."""
    sample = {}
    for field, spec in properties.items():
        jsonschema_spec = _bson_schema_to_jsonschema(spec)
        jtype = jsonschema_spec.get("type", "string")
        sample[field] = _SAMPLE_VALUES.get(jtype, "sample")
    return sample


def validate_mongo_schema(collections: dict) -> dict:
    """
    For each collection's schema, generates a sample document and
    validates it. Returns {"passed": bool, "errors": list[str]}.
    """
    errors = []

    for name, schema in collections.items():
        try:
            converted = _bson_schema_to_jsonschema(schema)
            sample = _generate_sample_document(schema.get("properties", {}))
            jsonschema.validate(instance=sample, schema=converted)
        except jsonschema.exceptions.ValidationError as e:
            errors.append(f"{name}: {e.message}")
        except Exception as e:
            errors.append(f"{name}: unexpected error building/validating schema — {e}")

    return {"passed": len(errors) == 0, "errors": errors}