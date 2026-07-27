"""
Trunk nodes: shared stages that run before the SQL/NoSQL fork.
"""

import json
from graph.state import DesignState
from graph.llm import invoke_llm,invoke_llm_json


def requirement_analyzer(state: DesignState) -> dict:
    """
    Takes the raw requirement text and produces a cleaned, structured
    summary: what the system does, who the users are, and what data
    it needs to track. This summary is what every later stage reads
    instead of re-parsing the raw text each time.
    """
    prompt = f"""You are a database requirements analyst.

Read the following raw project requirement and produce a clear,
structured summary covering:
1. What the system/platform does
2. The main types of users/actors
3. The core things the system needs to store and track
4. Any explicit scale, performance, or query hints mentioned

Requirement:
\"\"\"{state['requirement']}\"\"\"

Respond with plain text only. No JSON, no markdown headers, just a
clear analytical summary in 4-6 sentences.
"""
    summary = invoke_llm(prompt)
    return {"analyzed_requirement": summary.strip()}


def entity_extractor(state: DesignState) -> dict:
    """
    Reads the analyzed requirement and extracts the core entities
    (tables/collections) and their attributes. This is the foundation
    every later stage builds on — relationships, access patterns, and
    the final schema are all derived from this entity list.
    """
    prompt = f"""You are a database design expert.

Based on this system description, identify the core entities (things
that need their own table/collection) and their attributes.

System description:
\"\"\"{state['analyzed_requirement']}\"\"\"

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "entities": [
    {{
      "name": "EntityName",
      "description": "one sentence describing what this entity represents",
      "attributes": [
        {{"name": "attribute_name", "type": "string|integer|float|boolean|date|datetime", "required": true}}
      ]
    }}
  ]
}}

Rules:
- Use PascalCase for entity names (e.g. "Customer", "OrderItem").
- Every entity must have an "id" attribute as its first attribute.
- Only include attributes clearly implied or stated by the description.
- Do not invent unrelated entities.
"""
    result = invoke_llm_json(prompt)
    return {"entities": result["entities"]}

def access_pattern_extractor(state: DesignState) -> dict:
    """
    Identifies the queries/access patterns the application needs to
    support efficiently. The SQL branch uses this to decide indexes.
    The NoSQL branch (Phase 2) uses this to decide what to embed vs
    reference, and how to choose partition/shard keys.
    """
    entity_names = [e["name"] for e in state["entities"]]

    prompt = f"""You are a database design expert analyzing query patterns.

System description:
\"\"\"{state['analyzed_requirement']}\"\"\"

Known entities: {entity_names}

Identify the most important access patterns (queries) this system
needs to support efficiently. Think about what the application does
repeatedly and at scale — not every possible query, just the ones
that matter for schema design.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "access_patterns": [
    {{
      "description": "e.g. Get all orders for a customer, sorted by date",
      "entities_involved": ["Customer", "Order"],
      "frequency": "high|medium|low"
    }}
  ]
}}

Include at least 4 and at most 8 patterns, ordered from highest to
lowest frequency.
"""
    result = invoke_llm_json(prompt)
    return {"access_patterns": result["access_patterns"]}


def db_type_recommender(state: DesignState) -> dict:
    """
    Decides SQL vs NoSQL based on entities, relationships density
    (inferred from FK-like attributes), and access patterns. This is
    the node that closes the trunk and determines which branch
    (SQL or NoSQL) the pipeline forks into next.

    Respects a user override if one was given (db_type_override),
    but still runs the reasoning so the user sees why the automatic
    pick would have differed, if it does.
    """
    entities_summary = json.dumps(state["entities"], indent=2)
    patterns_summary = json.dumps(state["access_patterns"], indent=2)

    prompt = f"""You are a senior database architect choosing between a
relational (SQL/MySQL) and document (NoSQL/MongoDB) design.

Entities and attributes:
{entities_summary}

Access patterns:
{patterns_summary}

Decision guidance:
- Favor SQL when entities have many structured many-to-many or
  deeply interconnected relationships that benefit from joins and
  strong consistency/normalization.
- Favor NoSQL when a small number of high-frequency access patterns
  dominate and the data naturally embeds/denormalizes around those
  patterns (e.g. "get order with all its items in one read").
- Treat "must load instantly even at high/unbounded volume" (e.g. long
  message history, activity feeds, event logs) as a strong NoSQL
  signal on its own -- horizontal scalability and fast reads at
  unbounded scale are exactly what document stores are optimized for,
  even when the entities also have some relational structure.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{
  "recommended_db_type": "sql" or "nosql",
  "reasoning": "2-4 sentences explaining the tradeoff and why this system leans one way"
}}
"""
    result = invoke_llm_json(prompt)

    # Respect an explicit user override, but keep the model's reasoning
    # visible either way so the user can see what the automatic pick was.
    final_choice = state.get("db_type_override")
    if final_choice in ("sql", "nosql"):
        chosen = final_choice
    else:
        chosen = result["recommended_db_type"]

    return {
        "recommended_db_type": chosen,
        "db_type_reasoning": result["reasoning"],
    }