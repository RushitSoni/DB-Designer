"""
Wires all pipeline nodes into a single LangGraph StateGraph.

relationship_validator lives in the trunk (not the SQL branch) because
both SQL and NoSQL branches need to know the relationships between
entities -- SQL uses them for normalization/FKs, NoSQL uses them for
embed/reference decisions. Only normalization is genuinely SQL-specific.
"""

from langgraph.graph import StateGraph, END
from graph.state import DesignState
from graph.nodes.trunk import (
    requirement_analyzer,
    entity_extractor,
    access_pattern_extractor,
    db_type_recommender,
)
from graph.nodes.sql_branch import (
    relationship_validator,
    normalization_checker,
    sql_generator,
    sql_validator,
)
from graph.nodes.nosql_branch import (
    embed_reference_advisor,
    partition_key_designer,
    document_schema_generator,
    nosql_validator,
)
from graph.nodes.docs import mermaid_diagram_generator


def _route_by_db_type(state: DesignState) -> str:
    if state["recommended_db_type"] == "nosql":
        return "embed_reference_advisor"
    return "normalization_checker"


def build_graph():
    graph = StateGraph(DesignState)

    # Trunk (relationship_validator now lives here, shared by both branches)
    graph.add_node("requirement_analyzer", requirement_analyzer)
    graph.add_node("entity_extractor", entity_extractor)
    graph.add_node("access_pattern_extractor", access_pattern_extractor)
    graph.add_node("relationship_validator", relationship_validator)
    graph.add_node("db_type_recommender", db_type_recommender)

    # SQL branch (normalization_checker onward -- relationships already known)
    graph.add_node("normalization_checker", normalization_checker)
    graph.add_node("sql_generator", sql_generator)
    graph.add_node("sql_validator", sql_validator)

    # NoSQL branch
    graph.add_node("embed_reference_advisor", embed_reference_advisor)
    graph.add_node("partition_key_designer", partition_key_designer)
    graph.add_node("document_schema_generator", document_schema_generator)
    graph.add_node("nosql_validator", nosql_validator)

    # Docs (shared convergence point)
    graph.add_node("mermaid_diagram_generator", mermaid_diagram_generator)

    graph.set_entry_point("requirement_analyzer")

    # Trunk flow
    graph.add_edge("requirement_analyzer", "entity_extractor")
    graph.add_edge("entity_extractor", "access_pattern_extractor")
    graph.add_edge("access_pattern_extractor", "relationship_validator")
    graph.add_edge("relationship_validator", "db_type_recommender")

    # THE FORK: conditional edge based on recommended_db_type
    graph.add_conditional_edges(
        "db_type_recommender",
        _route_by_db_type,
        {
            "normalization_checker": "normalization_checker",
            "embed_reference_advisor": "embed_reference_advisor",
        },
    )

    # SQL branch flow
    graph.add_edge("normalization_checker", "sql_generator")
    graph.add_edge("sql_generator", "sql_validator")
    graph.add_edge("sql_validator", "mermaid_diagram_generator")

    # NoSQL branch flow
    graph.add_edge("embed_reference_advisor", "partition_key_designer")
    graph.add_edge("partition_key_designer", "document_schema_generator")
    graph.add_edge("document_schema_generator", "nosql_validator")
    graph.add_edge("nosql_validator", "mermaid_diagram_generator")

    graph.add_edge("mermaid_diagram_generator", END)

    return graph.compile()