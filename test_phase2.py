"""
Tests the NoSQL branch nodes standalone, reusing the trunk from
build_graph() but running NoSQL nodes manually (fork wiring comes
in Phase 3).
"""

from graph.build_graph import build_graph
from graph.nodes.nosql_branch import embed_reference_advisor
import json

# We need a trunk-only run. For now, reuse the full app but note we
# only care about trunk output up through db_type_recommender --
# the SQL branch nodes will also run since the graph isn't forked yet,
# that's fine, we just ignore their output here.
app = build_graph()

initial_state = {
    "requirement": "Build a real-time chat application where users create "
                   "channels, send messages with optional file attachments, "
                   "react to messages with emojis, and messages need to load "
                   "instantly when a channel is opened, even with long history."
}

trunk_result = app.invoke(initial_state)

print(f"DB Type: {trunk_result['recommended_db_type']}")
print(f"Reasoning: {trunk_result['db_type_reasoning']}\n")

print("--- Entities ---")
for e in trunk_result["entities"]:
    print(f"- {e['name']}: {[a['name'] for a in e['attributes']]}")

print("\n--- Relationships ---")
for r in trunk_result["relationships"]:
    print(f"- {r['from_entity']} --{r['type']}--> {r['to_entity']}")

state_with_embed = {**trunk_result, **embed_reference_advisor(trunk_result)}
print("\n--- Embed/Reference Decisions ---")
for note in state_with_embed["embed_vs_reference_notes"]:
    print(f"- {note}")

from graph.nodes.nosql_branch import partition_key_designer

state_with_shard_keys = {**state_with_embed, **partition_key_designer(state_with_embed)}
print("\n--- Shard Key Recommendations ---")
for note in state_with_shard_keys["partition_key_notes"]:
    print(f"- {note}")


from graph.nodes.nosql_branch import document_schema_generator, nosql_validator

state_with_schema = {**state_with_shard_keys, **document_schema_generator(state_with_shard_keys)}
print("\n--- MongoDB Document Schema ---")
print(json.dumps(state_with_schema["mongo_schema"], indent=2))

state_nosql_validated = {**state_with_schema, **nosql_validator(state_with_schema)}
print("\n--- jsonschema Validation ---")
print(f"Passed: {state_nosql_validated['validation_passed']}")
if state_nosql_validated["validation_errors"]:
    for err in state_nosql_validated["validation_errors"]:
        print(f"ERROR: {err}")