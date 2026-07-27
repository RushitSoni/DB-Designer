"""
Tests the full forked pipeline end-to-end, once with a SQL-leaning
requirement and once with a NoSQL-leaning one, confirming the graph
actually routes to the correct branch on its own.
"""

from graph.build_graph import build_graph

app = build_graph()

test_cases = [
    ("SQL-leaning (food ordering)",
     "Build an online food ordering platform where customers browse "
     "restaurants, place orders, track delivery status, and restaurants "
     "manage their menus and incoming orders."),
    ("NoSQL-leaning (chat app)",
     "Build a real-time chat application where users create channels, "
     "send messages with optional file attachments, react to messages "
     "with emojis, and messages need to load instantly when a channel "
     "is opened, even with long history."),
]

for label, requirement in test_cases:
    print("=" * 70)
    print(label)
    print("=" * 70)

    result = app.invoke({"requirement": requirement})

    print(f"Routed to: {result['recommended_db_type'].upper()}")

    if result["recommended_db_type"] == "sql":
        print(f"Validation passed: {result['validation_passed']}")
        print(f"Tables generated: {result['sql_ddl'].count('CREATE TABLE')}")
    else:
        print(f"Validation passed: {result['validation_passed']}")
        print(f"Collections generated: {list(result['mongo_schema'].keys())}")

    print(f"Diagram generated: {len(result['mermaid_diagram'])} chars\n")