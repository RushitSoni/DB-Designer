"""
Documentation/diagram nodes. These are deterministic — no LLM calls —
because we already have fully structured entities/relationships in
state by this point, and Mermaid ER syntax is simple enough to emit
directly and reliably in code.
"""

from graph.state import DesignState

# Mermaid ER diagram relationship symbols
_REL_SYMBOLS = {
    "one-to-one": "||--||",
    "one-to-many": "||--o{",
    "many-to-one": "}o--||",
    "many-to-many": "}o--o{",
}


def _mermaid_type(attr_type: str) -> str:
    """Map our internal type names to Mermaid-friendly type labels."""
    mapping = {
        "string": "string",
        "integer": "int",
        "float": "float",
        "boolean": "boolean",
        "date": "date",
        "datetime": "datetime",
    }
    return mapping.get(attr_type, "string")


def mermaid_diagram_generator(state: DesignState) -> dict:
    """
    Builds a Mermaid erDiagram block from state["entities"] and
    state["relationships"]. Deterministic — same input always
    produces the same diagram, no LLM variance.
    """
    lines = ["erDiagram"]

    # Entity blocks with attributes
    for entity in state["entities"]:
        lines.append(f"    {entity['name']} {{")
        for attr in entity["attributes"]:
            mtype = _mermaid_type(attr["type"])
            marker = "PK" if attr["name"] == "id" else ("FK" if attr["name"].endswith("Id") else "")
            lines.append(f"        {mtype} {attr['name']} {marker}".rstrip())
        lines.append("    }")

    # Relationship lines
    for rel in state.get("relationships", []):
        symbol = _REL_SYMBOLS.get(rel["type"], "||--o{")
        label = rel["description"].replace('"', "'")
        lines.append(f'    {rel["from_entity"]} {symbol} {rel["to_entity"]} : "{label}"')

    diagram = "\n".join(lines)
    return {"mermaid_diagram": diagram}