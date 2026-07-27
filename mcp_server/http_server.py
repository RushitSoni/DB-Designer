"""
HTTP/SSE transport version of the MCP server, for remote/cloud
deployment. Uses the same underlying tool logic as server.py
(stdio version) -- only the transport layer differs.

Run locally: python mcp_server/http_server.py
Deployed: this is what gets pointed at by uvicorn on Render/Railway/etc.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from mcp.server.fastmcp import FastMCP

from graph.build_graph import build_graph
from graph.nodes.migration import run_migration
from db.models import init_db, save_run

mcp = FastMCP("db-architect")
_graph = build_graph()
init_db()


@mcp.tool()
def design_database(requirement: str, db_type: str = "auto") -> str:
    """
    Design a complete MySQL or MongoDB database schema from a
    plain-text requirement. Automatically decides SQL vs NoSQL unless
    overridden, extracts entities and relationships, generates
    validated DDL or MongoDB document schema, and produces a Mermaid
    ER diagram.
    """
    initial_state = {"requirement": requirement}
    if db_type in ("sql", "nosql"):
        initial_state["db_type_override"] = db_type

    result = _graph.invoke(initial_state)

    output = {
        "recommended_db_type": result["recommended_db_type"],
        "reasoning": result["db_type_reasoning"],
        "entities": result["entities"],
        "relationships": result["relationships"],
        "validation_passed": result["validation_passed"],
        "validation_errors": result.get("validation_errors", []),
        "mermaid_diagram": result["mermaid_diagram"],
    }

    if result["recommended_db_type"] == "sql":
        output["sql_ddl"] = result["sql_ddl"]
    else:
        output["mongo_schema"] = result["mongo_schema"]
        output["embed_vs_reference_notes"] = result.get("embed_vs_reference_notes", [])

    run_id = save_run(requirement, output)
    output["run_id"] = run_id

    return json.dumps(output, indent=2)


@mcp.tool()
def recommend_database_type(requirement: str) -> str:
    """
    Analyze a plain-text requirement and recommend SQL vs NoSQL with
    clear reasoning, without generating the full schema.
    """
    result = _graph.invoke({"requirement": requirement})
    output = {
        "recommended_db_type": result["recommended_db_type"],
        "reasoning": result["db_type_reasoning"],
    }
    return json.dumps(output, indent=2)


@mcp.tool()
def migrate_schema(source_schema: str, target_type: str) -> str:
    """
    Convert an existing schema between MySQL and MongoDB.
    target_type must be "sql" or "nosql".
    """
    result = run_migration(source_schema, target_type)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="sse")