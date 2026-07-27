"""
NoSQL branch nodes: run only when recommended_db_type == "nosql".
Unlike the SQL branch (which normalizes to reduce redundancy), this
branch deliberately denormalizes around the access patterns found in
the trunk -- that's the central design difference the whole project
is built to demonstrate.
"""

import json
from graph.state import DesignState
from graph.llm import invoke_llm_json
from validation.nosql_sandbox import validate_mongo_schema


def embed_reference_advisor(state: DesignState) -> dict:
    """
    For every relationship found in the trunk, decides whether the
    child should be EMBEDDED inside the parent document or REFERENCED
    by ID -- based on the access patterns, not just relationship
    cardinality. This decision drives everything downstream: the
    partition key choice and the actual document shape.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    relationships_summary = json.dumps(state["relationships"], indent=2)
    patterns_summary = json.dumps(state["access_patterns"], indent=2)

    prompt = f"""You are a MongoDB data modeling expert deciding, for
each relationship, whether to EMBED the related data inside the parent
document or REFERENCE it by ID in a separate collection.

Entities:
{entities_summary}

Relationships:
{relationships_summary}

Access patterns (this is what the decision should be driven by):
{patterns_summary}

Decision guidance:
- EMBED when the related data is almost always read together with its
  parent, is bounded in size (won't grow unboundedly), and is rarely
  or never queried independently of the parent.
- REFERENCE when the related data is large/unbounded, needs to be
  queried independently, or is shared/reused across many parent
  documents (embedding would duplicate it everywhere it's used).
- A one-to-many relationship does not automatically mean embed --
  check the access patterns for whether the child is ever queried on
  its own.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "decisions": [
    {{
      "from_entity": "EntityName",
      "to_entity": "EntityName",
      "decision": "embed" or "reference",
      "reasoning": "one sentence tied to a specific access pattern"
    }}
  ]
}}

Include a decision for every relationship listed above.
"""
    result = invoke_llm_json(prompt)

    notes = [
        f"{d['from_entity']} -> {d['to_entity']}: {d['decision'].upper()} — {d['reasoning']}"
        for d in result["decisions"]
    ]

    return {"embed_vs_reference_notes": notes, "embed_decisions_raw": result["decisions"]}


def partition_key_designer(state: DesignState) -> dict:
    """
    For each collection that will be its own top-level MongoDB
    collection (i.e. every entity that ended up as a REFERENCE target,
    or has no relationships at all), recommends a partition/shard key
    based on the dominant access pattern for that entity -- so queries
    can be routed to a single shard instead of scattering.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    patterns_summary = json.dumps(state["access_patterns"], indent=2)
    decisions_summary = json.dumps(state["embed_decisions_raw"], indent=2)

    prompt = f"""You are a MongoDB sharding expert choosing shard/partition
keys for each top-level collection in this design.

Entities:
{entities_summary}

Access patterns:
{patterns_summary}

Embed/reference decisions (entities that appear as "to_entity" with
decision "reference" become their own top-level collection; entities
that only appear as "embed" targets do NOT get their own collection,
skip them):
{decisions_summary}

For each top-level collection, recommend a shard key that routes the
dominant access pattern for that entity to a single shard (avoid
choosing a key like a timestamp alone, which creates a hot shard for
all recent writes -- prefer compound keys like {{channelId: 1, createdAt: -1}}
when a "get all X for a Y, sorted by time" pattern exists).

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "shard_keys": [
    {{
      "entity": "EntityName",
      "shard_key": "e.g. {{ channelId: 1, createdAt: -1 }}",
      "reasoning": "one sentence tied to a specific access pattern"
    }}
  ]
}}

Only include entities that are actual top-level collections (per the
reference decisions above), not entities that only get embedded.
"""
    result = invoke_llm_json(prompt)

    notes = [
        f"{sk['entity']}: {sk['shard_key']} — {sk['reasoning']}"
        for sk in result["shard_keys"]
    ]

    return {"partition_key": json.dumps(result["shard_keys"]), "partition_key_notes": notes}



def document_schema_generator(state: DesignState, max_repair_attempts: int = 2) -> dict:
    """
    Builds the MongoDB document schema, then validates it via
    jsonschema (generated sample documents). If validation fails,
    feeds the specific error back to the model and asks it to fix
    the schema -- same retry-repair pattern used in sql_generator.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    decisions_summary = json.dumps(state["embed_decisions_raw"], indent=2)
    shard_keys_summary = state["partition_key"]

    base_prompt = f"""You are a MongoDB schema designer. Produce the final
document schema for each top-level collection.

Entities:
{entities_summary}

Embed/reference decisions:
{decisions_summary}

Shard keys already decided:
{shard_keys_summary}

Rules:
- Every entity that is never "embed"-ded into another becomes its own
  top-level collection with a JSON Schema.
- Entities marked "embed" as a "to_entity" do NOT get their own
  top-level collection -- their fields become a nested object or
  array of objects inside the parent's schema instead.
- Referenced entities keep a field like "xId" of BSON type
  "objectId" pointing to the other collection, instead of nesting.
- Use standard JSON Schema types: "string", "int", "double", "bool",
  "date", "objectId", "array", "object".
- Every field name listed in a "required" array MUST exactly match a
  key that also exists in that same object's "properties". Do not
  require "id" if the property is named "_id", or vice versa -- use
  "_id" consistently for the document's own identifier.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "collections": {{
    "CollectionName": {{
      "bsonType": "object",
      "required": ["field1", "field2"],
      "properties": {{
        "_id": {{"bsonType": "objectId"}},
        "field1": {{"bsonType": "string"}}
      }}
    }}
  }}
}}
"""

    prompt = base_prompt
    collections = {}

    for attempt in range(max_repair_attempts + 1):
        result = invoke_llm_json(prompt)
        collections = result["collections"]

        validation = validate_mongo_schema(collections)
        if validation["passed"]:
            return {"mongo_schema": collections}

        if attempt == max_repair_attempts:
            return {"mongo_schema": collections}

        print(f"[document_schema_generator] Validation failed (attempt {attempt + 1}), asking model to repair...")
        errors_text = "\n".join(validation["errors"])
        prompt = f"""{base_prompt}

Your previous attempt produced this schema:
\"\"\"{json.dumps(collections, indent=2)}\"\"\"

Validating it produced these errors:
{errors_text}

Fix the schema to resolve these specific errors (likely a mismatch
between "required" field names and "properties" keys). Respond with
ONLY the corrected JSON, same shape as before.
"""

    return {"mongo_schema": collections}

def nosql_validator(state: DesignState) -> dict:
    """
    Runs the generated MongoDB schema through jsonschema validation
    (via generated sample documents) and stores the result in state.
    """
    result = validate_mongo_schema(state["mongo_schema"])
    return {
        "validation_passed": result["passed"],
        "validation_errors": result["errors"],
    }