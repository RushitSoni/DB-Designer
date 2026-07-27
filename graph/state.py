"""
Shared state that flows through every node in the pipeline.

Every node in the graph receives this state, reads the fields it needs,
and returns a dict of updates that LangGraph merges back in. Nothing a
later node needs should ever be thrown away by an earlier one.
"""

from typing import TypedDict, Literal, Optional


class Entity(TypedDict):
    """One entity/table discovered in the requirement text."""
    name: str
    description: str
    attributes: list[dict]  # e.g. [{"name": "email", "type": "string", "required": True}]


class Relationship(TypedDict):
    """A relationship between two entities."""
    from_entity: str
    to_entity: str
    type: Literal["one-to-one", "one-to-many", "many-to-many"]
    description: str


class AccessPattern(TypedDict):
    """A query/access pattern the app needs to support efficiently."""
    description: str          # e.g. "Get all orders for a user, sorted by date"
    entities_involved: list[str]
    frequency: Literal["high", "medium", "low"]


class DesignState(TypedDict, total=False):
    # ---- Input ----
    requirement: str                          # raw text the user gave us
    db_type_override: Optional[Literal["sql", "nosql", "auto"]]

    # ---- Trunk stage outputs ----
    analyzed_requirement: str                 # cleaned/structured summary
    entities: list[Entity]
    relationships: list[Relationship]
    access_patterns: list[AccessPattern]
    recommended_db_type: Literal["sql", "nosql"]
    db_type_reasoning: str

    # ---- SQL branch outputs ----
    normalization_notes: list[str]
    sql_ddl: str
    sql_constraints: list[str]
    sql_indexes: list[str]

    # ---- NoSQL branch outputs (Phase 2, empty for now) ----
    embed_vs_reference_notes: list[str]
    partition_key: Optional[str]
    mongo_schema: Optional[dict]
    embed_decisions_raw: list[dict]           # internal: from_entity/to_entity/decision/reasoning, used by document_schema_generator
    partition_key_notes: list[str]
    
    # ---- Validation ----
    validation_passed: bool
    validation_errors: list[str]

    # ---- Output ----
    mermaid_diagram: str
    data_dictionary: str

    # ---- Pipeline control ----
    errors: list[str]                         # accumulated errors for retry-repair later