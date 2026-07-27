"""
SQL branch nodes: run only when recommended_db_type == "sql".
These take the trunk's raw entities and turn them into a normalized,
relationally sound design before SQL generation.
"""

import json
from graph.state import DesignState
from graph.llm import invoke_llm,invoke_llm_json
from validation.sql_sandbox import validate_ddl

def relationship_validator(state: DesignState) -> dict:
    """
    Infers explicit relationships (one-to-one, one-to-many, many-to-many)
    between entities, based on their attributes and the access patterns.
    Downstream, normalization_checker and sql_generator both depend on
    this relationship list instead of re-guessing from raw attributes.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    patterns_summary = json.dumps(state["access_patterns"], indent=2)

    prompt = f"""You are a database architect identifying relationships
between entities for a relational (SQL) design.

Entities:
{entities_summary}

Access patterns:
{patterns_summary}

Identify every DIRECT relationship between entities — i.e. relationships
backed by an actual foreign-key-like attribute, or a genuinely missing
one that the access patterns require.

Do NOT invent a many-to-many relationship between two entities if that
relationship is already fully represented through an existing entity
that connects them (e.g. if Order already links Customer and
Restaurant with its own attributes, do not also add a separate
Customer<->Restaurant many-to-many relationship — Order already
captures that connection). Only propose a real join/junction entity
when no such connecting entity already exists in the data.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "relationships": [
    {{
      "from_entity": "EntityName",
      "to_entity": "EntityName",
      "type": "one-to-one" or "one-to-many" or "many-to-many",
      "description": "short explanation of the relationship"
    }}
  ]
}}
"""
    result = invoke_llm_json(prompt)
    return {"relationships": result["relationships"]}


def normalization_checker(state: DesignState) -> dict:
    """
    Reviews entities against the now-known relationships and flags/fixes
    normalization violations: e.g. a field that stores a comma-separated
    list or a loose string where it should be a proper relationship, or
    a many-to-many relationship with no explicit join table entity.

    Returns possibly-revised entities (with fixes applied) plus a list
    of human-readable notes explaining what was changed and why.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    relationships_summary = json.dumps(state["relationships"], indent=2)

    prompt = f"""You are a database architect performing a normalization
review (up to 3NF) on this relational design.

Entities:
{entities_summary}

Relationships:
{relationships_summary}

Check for:
1. Attributes that should be foreign keys but are loose strings/lists
   (e.g. a "menu" field storing item names as text instead of a real
   MenuItem relationship).
2. Many-to-many relationships with no explicit join/junction entity.
3. Repeating groups or multi-valued attributes stored as a single field.
4. Redundant data that duplicates another entity's fields.

IMPORTANT: Only modify or remove an attribute if it is a genuine,
specific normalization violation from the list above. Do NOT remove,
rename, or alter any attribute just because its name seems generic,
unclear, or placeholder-like (e.g. "new_field", "data", "value") --
the user may have added it deliberately, and an unclear name is not
itself a normalization violation. When in doubt, preserve the
attribute exactly as given.

For every violation found, fix it directly in the entities list (add
join entities if needed, replace loose fields with proper FK attributes
named like "xId"). If an entity is fine, leave it unchanged.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "entities": [ ...full corrected entity list, same shape as input... ],
  "notes": [ "short note describing each fix made, or 'No violations found' if none" ]
}}
"""
    result = invoke_llm_json(prompt)
    return {
        "entities": result["entities"],
        "normalization_notes": result["notes"],
    }


def sql_generator(state: DesignState, max_repair_attempts: int = 2) -> dict:
    """
    Converts the normalized entities + relationships into actual MySQL
    DDL, then validates it via SQLite. If validation fails, feeds the
    specific error back to the model and asks it to fix the DDL --
    this is the retry-repair pattern applied to a structural validation
    failure, not just a JSON parse failure.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    relationships_summary = json.dumps(state["relationships"], indent=2)
    patterns_summary = json.dumps(state["access_patterns"], indent=2)

    base_prompt = f"""You are a MySQL database engineer. Generate complete,
valid MySQL DDL for this design.

Entities:
{entities_summary}

Relationships:
{relationships_summary}

Access patterns (use these to decide which columns need indexes):
{patterns_summary}

Rules:
- Every entity becomes a CREATE TABLE statement.
- "id" attributes become `id INT AUTO_INCREMENT PRIMARY KEY`.
- Map types: string -> VARCHAR(255) (TEXT if clearly long-form like a
  description), integer -> INT, float -> DECIMAL(10,2), boolean ->
  BOOLEAN, date -> DATE, datetime -> DATETIME.
- required: true -> add NOT NULL. required: false -> column is nullable.
- Every "xId" attribute that matches a relationship becomes a proper
  FOREIGN KEY constraint referencing the correct table's id column.
- Do NOT add any inline INDEX or KEY clauses inside a CREATE TABLE
  statement. Instead, add every index as its own separate statement
  AFTER all CREATE TABLE statements, using the form:
  CREATE INDEX idx_tablename_column ON TableName (column);
  Add one for every foreign key column and every column that appears
  in a "high" frequency access pattern's filter or sort.
- Tables must be created in an order where referenced tables exist
  before tables that reference them (no forward references).
- Use InnoDB engine explicitly on every table.
- Wrap any table or column name that is a MySQL reserved word (like
  "Order") in backticks.

Respond with ONLY the raw SQL. No markdown fences, no explanation,
no comments outside the SQL itself. Every statement must end with a
semicolon.
"""

    prompt = base_prompt
    ddl = ""

    for attempt in range(max_repair_attempts + 1):
        raw = invoke_llm(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("sql"):
                cleaned = cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        ddl = cleaned.strip()

        validation = validate_ddl(ddl)
        if validation["passed"]:
            return {"sql_ddl": ddl, "validation_passed": True, "validation_errors": []}

        if attempt == max_repair_attempts:
            # Out of attempts -- return the best (still broken) version,
            # with validation results, rather than crashing the pipeline.
            return {
                "sql_ddl": ddl,
                "validation_passed": False,
                "validation_errors": validation["errors"],
            }

        print(f"[sql_generator] DDL validation failed (attempt {attempt + 1}), asking model to repair...")
        errors_text = "\n".join(validation["errors"])
        prompt = f"""{base_prompt}

Your previous attempt produced this DDL:
\"\"\"{ddl}\"\"\"

Running it against a validator produced these errors:
{errors_text}

Fix the DDL to resolve these specific errors. Respond with ONLY the
corrected raw SQL, same rules as before.
"""

    return {"sql_ddl": ddl}
    """
    Converts the normalized entities + relationships into actual MySQL
    DDL: CREATE TABLE statements with proper types, primary keys,
    foreign keys, and basic indexes on FK columns and high-frequency
    access-pattern fields.

    This DDL gets executed against SQLite in the next node to catch
    structural errors before anything is shown to the user.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    relationships_summary = json.dumps(state["relationships"], indent=2)
    patterns_summary = json.dumps(state["access_patterns"], indent=2)

    prompt = f"""You are a MySQL database engineer. Generate complete,
valid MySQL DDL for this design.

Entities:
{entities_summary}

Relationships:
{relationships_summary}

Access patterns (use these to decide which columns need indexes):
{patterns_summary}

Rules:
- Every entity becomes a CREATE TABLE statement.
- "id" attributes become `id INT AUTO_INCREMENT PRIMARY KEY`.
- Map types: string -> VARCHAR(255) (TEXT if clearly long-form like a
  description), integer -> INT, float -> DECIMAL(10,2), boolean ->
  BOOLEAN, date -> DATE, datetime -> DATETIME.
- required: true -> add NOT NULL. required: false -> column is nullable.
- Every "xId" attribute that matches a relationship becomes a proper
  FOREIGN KEY constraint referencing the correct table's id column.
- Add an index (CREATE INDEX) on any foreign key column and on any
  column that appears in a "high" frequency access pattern's filter
  or sort (e.g. orderDate for "sorted by date").
- Tables must be created in an order where referenced tables exist
  before tables that reference them (no forward references).
- Use InnoDB engine explicitly on every table.

Respond with ONLY the raw SQL. No markdown fences, no explanation,
no comments outside the SQL itself. Every statement must end with a
semicolon.
"""
    ddl = invoke_llm(prompt)

    # Strip markdown fences in case the model added them anyway
    cleaned = ddl.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("sql"):
            cleaned = cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    return {"sql_ddl": cleaned}


def sql_validator(state: DesignState) -> dict:
    """
    Runs the generated DDL through SQLite validation and stores the
    result in state. Downstream (Phase 6) the retry-repair node will
    use validation_errors to ask the model to fix its own output.
    """
    result = validate_ddl(state["sql_ddl"])
    return {
        "validation_passed": result["passed"],
        "validation_errors": result["errors"],
    }