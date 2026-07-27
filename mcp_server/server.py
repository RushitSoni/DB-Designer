"""
MCP server exposing the database design pipeline as three tools:
design_database, recommend_database_type, migrate_schema.

Run standalone for local testing:
    python mcp_server/server.py

For Claude Desktop / Cursor, this gets registered via their MCP config
(see README instructions after Step 20).
"""
from db.models import init_db, save_run
init_db()

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from graph.build_graph import build_graph
from graph.nodes.migration import run_migration

app = Server("db-architect")
_graph = build_graph()
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="design_database",
            description=(
                "Design a complete MySQL or MongoDB database schema from a "
                "plain-text requirement. Automatically decides SQL vs NoSQL "
                "unless overridden, extracts entities and relationships, "
                "generates validated DDL or MongoDB document schema, and "
                "produces a Mermaid ER diagram."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "requirement": {
                        "type": "string",
                        "description": "Plain-text description of the system to design a database for.",
                    },
                    "db_type": {
                        "type": "string",
                        "enum": ["sql", "nosql", "auto"],
                        "description": "Force sql or nosql, or let the pipeline decide (auto).",
                        "default": "auto",
                    },
                },
                "required": ["requirement"],
            },
        ),
        Tool(
            name="recommend_database_type",
            description=(
                "Analyze a plain-text requirement and recommend SQL vs NoSQL "
                "with clear reasoning, without generating the full schema."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "requirement": {
                        "type": "string",
                        "description": "Plain-text description of the system.",
                    },
                },
                "required": ["requirement"],
            },
        ),
        Tool(
            name="migrate_schema",
            description=(
                "Convert an existing schema between MySQL and MongoDB. "
                "(Not yet implemented -- planned for a later build phase.)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source_schema": {
                        "type": "string",
                        "description": "The existing schema (DDL or MongoDB JSON Schema) to convert.",
                    },
                    "target_type": {
                        "type": "string",
                        "enum": ["sql", "nosql"],
                        "description": "The database type to migrate TO.",
                    },
                },
                "required": ["source_schema", "target_type"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "design_database":
        return await _handle_design_database(arguments)
    elif name == "recommend_database_type":
        return await _handle_recommend_database_type(arguments)
    elif name == "migrate_schema":
        return await _handle_migrate_schema(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_design_database(arguments: dict) -> list[TextContent]:
    requirement = arguments["requirement"]
    db_type_override = arguments.get("db_type", "auto")

    initial_state = {"requirement": requirement}
    if db_type_override in ("sql", "nosql"):
        initial_state["db_type_override"] = db_type_override

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
        output["embed_vs_reference_notes"] = result["embed_vs_reference_notes"]
        output["partition_key_notes"] = result.get("partition_key_notes", [])

    run_id = save_run(requirement, output)
    output["run_id"] = run_id

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def _handle_recommend_database_type(arguments: dict) -> list[TextContent]:
    # Run the graph normally -- db_type_recommender runs early, but we
    # still need entities/relationships computed first since the
    # recommender's prompt depends on them. We invoke the full graph
    # and just report the recommendation, not the full generated schema.
    requirement = arguments["requirement"]
    result = _graph.invoke({"requirement": requirement})

    output = {
        "recommended_db_type": result["recommended_db_type"],
        "reasoning": result["db_type_reasoning"],
    }
    return [TextContent(type="text", text=json.dumps(output, indent=2))]

async def _handle_migrate_schema(arguments: dict) -> list[TextContent]:
    source_schema = arguments["source_schema"]
    target_type = arguments["target_type"]

    result = run_migration(source_schema, target_type)
    return [TextContent(type="text", text=json.dumps(result, indent=2))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())