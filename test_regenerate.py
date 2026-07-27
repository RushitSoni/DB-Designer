"""
Tests the /regenerate endpoint's underlying logic directly (not via
HTTP), simulating a user editing an entity's attributes after an
initial design run.
"""


from graph.nodes.docs import mermaid_diagram_generator
from graph.nodes.sql_branch import relationship_validator, normalization_checker, sql_generator
# Simulate: user got these entities from an earlier /design call,
# then manually added a "loyalty_points" attribute to Customer.
edited_entities = [
    {
        "name": "Customer",
        "description": "A user who places orders",
        "attributes": [
            {"name": "id", "type": "integer", "required": True},
            {"name": "name", "type": "string", "required": True},
            {"name": "loyalty_points", "type": "integer", "required": False},
        ],
    },
    {
        "name": "Order",
        "description": "A customer's order",
        "attributes": [
            {"name": "id", "type": "integer", "required": True},
            {"name": "customerId", "type": "integer", "required": True},
            {"name": "total", "type": "float", "required": True},
        ],
    },
]

access_patterns = [
    {"description": "Get all orders for a customer", "entities_involved": ["Customer", "Order"], "frequency": "high"},
]

state = {"entities": edited_entities, "access_patterns": access_patterns}
state.update(relationship_validator(state))
state.update(normalization_checker(state))
state.update(sql_generator(state))
state.update(mermaid_diagram_generator(state))

print(f"Validation passed: {state['validation_passed']}")
print(f"\nDDL:\n{state['sql_ddl']}")