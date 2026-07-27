"""
End-to-end test of the full Phase 1 pipeline: a plain-text requirement
in, a validated MySQL schema + Mermaid diagram out. One graph, one call.
"""

from graph.build_graph import build_graph

app = build_graph()

initial_state = {
    "requirement": "Build a blogging platform where authors write and publish posts, "
                   "readers can comment on posts and follow authors they like, "
                   "posts can have multiple tags for categorization, and authors "
                   "can see analytics on views and likes for each of their posts."
}

final_state = app.invoke(initial_state)

print("=" * 60)
print("DB TYPE RECOMMENDATION")
print("=" * 60)
print(f"{final_state['recommended_db_type'].upper()}")
print(final_state["db_type_reasoning"])

print("\n" + "=" * 60)
print("ENTITIES")
print("=" * 60)
for e in final_state["entities"]:
    print(f"- {e['name']} ({len(e['attributes'])} attributes)")

print("\n" + "=" * 60)
print("NORMALIZATION NOTES")
print("=" * 60)
for note in final_state["normalization_notes"]:
    print(f"- {note}")

print("\n" + "=" * 60)
print(f"SQL VALIDATION: {'PASSED' if final_state['validation_passed'] else 'FAILED'}")
print("=" * 60)
if final_state["validation_errors"]:
    for err in final_state["validation_errors"]:
        print(f"ERROR: {err}")

print("\n" + "=" * 60)
print("GENERATED DDL")
print("=" * 60)
print(final_state["sql_ddl"])

print("\n" + "=" * 60)
print("MERMAID DIAGRAM")
print("=" * 60)
print(final_state["mermaid_diagram"])