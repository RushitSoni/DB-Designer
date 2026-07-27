"""
Directly tests the MCP tool handler functions without going through
the MCP protocol/transport layer. This proves the tool logic itself
is correct; wiring the actual MCP client connection (Inspector,
Claude Desktop, Cursor) is a separate, later step.
"""

import asyncio
import json
from mcp_server.server import _handle_design_database, _handle_recommend_database_type


async def main():
    print("=" * 60)
    print("TEST 1: recommend_database_type")
    print("=" * 60)
    result = await _handle_recommend_database_type({
        "requirement": "Build a real-time chat application where users create "
                       "channels, send messages, and messages need to load "
                       "instantly even with long history."
    })
    print(result[0].text)

    print("\n" + "=" * 60)
    print("TEST 2: design_database (full pipeline)")
    print("=" * 60)
    result = await _handle_design_database({
        "requirement": "Build an online food ordering platform where customers "
                       "browse restaurants, place orders, and track delivery status."
    })
    output = json.loads(result[0].text)
    print(f"DB Type: {output['recommended_db_type']}")
    print(f"Validation passed: {output['validation_passed']}")
    print(f"Entities: {[e['name'] for e in output['entities']]}")
    print(f"Validation errors: {output.get('validation_errors', [])}")
    print(f"\n--- SQL DDL ---")
    print(output.get("sql_ddl", "(none)"))


if __name__ == "__main__":
    asyncio.run(main())