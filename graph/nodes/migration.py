"""
Schema migration: converts an existing MySQL DDL schema into a
MongoDB document schema, or vice versa. This reuses the same
embed/reference reasoning and DDL generation logic as the main
design pipeline, but starts from an existing schema instead of a
plain-text requirement.
"""

import json
from graph.llm import invoke_llm, invoke_llm_json
from validation.sql_sandbox import validate_ddl
from validation.nosql_sandbox import validate_mongo_schema


def _parse_source_schema(source_schema: str, source_type: str) -> dict:
    """
    Reads an existing schema (DDL text or MongoDB JSON Schema text)
    and extracts entities/relationships from it, in the same shape
    our DesignState uses -- so downstream generation logic can be
    reused unchanged.
    """
    prompt = f"""You are a database schema analyst. Parse the following
{"MySQL DDL" if source_type == "sql" else "MongoDB JSON Schema"} and
extract its structure.

Schema:
\"\"\"{source_schema}\"\"\"

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "entities": [
    {{
      "name": "EntityName",
      "description": "one sentence describing this entity",
      "attributes": [
        {{"name": "attr_name", "type": "string|integer|float|boolean|date|datetime", "required": true}}
      ]
    }}
  ],
  "relationships": [
    {{
      "from_entity": "EntityName",
      "to_entity": "EntityName",
      "type": "one-to-one" or "one-to-many" or "many-to-many",
      "description": "short explanation, inferred from foreign keys or embedded/referenced structure"
    }}
  ]
}}
"""
    return invoke_llm_json(prompt)


def migrate_to_nosql(source_schema: str) -> dict:
    """
    MySQL DDL -> MongoDB schema. Reuses the same embed/reference
    reasoning nodes as the main NoSQL branch, just starting from a
    parsed existing schema instead of trunk-derived entities.
    """
    from graph.nodes.nosql_branch import (
        embed_reference_advisor,
        partition_key_designer,
        document_schema_generator,
    )

    parsed = _parse_source_schema(source_schema, "sql")

    # We don't have real access patterns for an existing schema (no
    # trunk ran), so we infer plausible ones directly from structure --
    # honest limitation: these are inferred, not observed from actual
    # usage, and may be less accurate than the greenfield design path.
    access_patterns_prompt = f"""Based on these entities and relationships,
infer the most likely high-frequency access patterns a typical
application using this schema would need.

Entities: {json.dumps(parsed['entities'], indent=2)}
Relationships: {json.dumps(parsed['relationships'], indent=2)}

Respond with ONLY valid JSON: {{"access_patterns": [{{"description": "...", "entities_involved": ["..."], "frequency": "high|medium|low"}}]}}
"""
    access_patterns = invoke_llm_json(access_patterns_prompt)["access_patterns"]

    state = {
        "entities": parsed["entities"],
        "relationships": parsed["relationships"],
        "access_patterns": access_patterns,
    }

    state.update(embed_reference_advisor(state))
    state.update(partition_key_designer(state))
    state.update(document_schema_generator(state))

    validation = validate_mongo_schema(state["mongo_schema"])

    return {
        "source_type": "sql",
        "target_type": "nosql",
        "mongo_schema": state["mongo_schema"],
        "embed_vs_reference_notes": state["embed_vs_reference_notes"],
        "validation_passed": validation["passed"],
        "validation_errors": validation["errors"],
        "inferred_access_patterns_note": (
            "Access patterns were inferred from schema structure, not "
            "observed from real usage -- accuracy depends on how well "
            "the original schema reflects actual query patterns."
        ),
    }


def migrate_to_sql(source_schema: str) -> dict:
    """
    MongoDB schema -> MySQL DDL. Reuses the SQL branch's normalization
    and generation logic, starting from a parsed existing schema.
    """
    from graph.nodes.sql_branch import normalization_checker, sql_generator

    parsed = _parse_source_schema(source_schema, "nosql")

    state = {
        "entities": parsed["entities"],
        "relationships": parsed["relationships"],
    }

    state.update(normalization_checker(state))

    # sql_generator expects access_patterns for index decisions; infer
    # simple defaults since we don't have real ones here either.
    state["access_patterns"] = [
        {"description": f"Look up {e['name']} by id", "entities_involved": [e["name"]], "frequency": "high"}
        for e in state["entities"]
    ]

    gen_result = sql_generator(state)

    return {
        "source_type": "nosql",
        "target_type": "sql",
        "sql_ddl": gen_result["sql_ddl"],
        "normalization_notes": state.get("normalization_notes", []),
        "validation_passed": gen_result.get("validation_passed", False),
        "validation_errors": gen_result.get("validation_errors", []),
    }


def run_migration(source_schema: str, target_type: str) -> dict:
    """Entry point: dispatches to the correct direction."""
    if target_type == "nosql":
        return migrate_to_nosql(source_schema)
    elif target_type == "sql":
        return migrate_to_sql(source_schema)
    else:
        raise ValueError(f"Unknown target_type: {target_type}")