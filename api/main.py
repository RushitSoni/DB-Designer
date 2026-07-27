"""
FastAPI backend wrapping the design graph. This is the shared layer
the Next.js frontend calls -- same underlying pipeline the MCP server
uses, just exposed over HTTP instead of stdio.
"""
from db.models import init_db, save_run, list_runs, get_run

init_db()
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal

from graph.build_graph import build_graph

app = FastAPI(title="DB Architect API")

# Allow the Next.js dev server (localhost:3000) to call this API.
# Tighten this to a specific origin before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_graph = build_graph()


class DesignRequest(BaseModel):
    requirement: str
    db_type: Optional[Literal["sql", "nosql", "auto"]] = "auto"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/design")
def design_database(request: DesignRequest):
    """
    Runs the full pipeline: requirement text in, validated schema +
    diagram out. Mirrors the MCP design_database tool's logic exactly.
    """
    initial_state = {"requirement": request.requirement}
    if request.db_type in ("sql", "nosql"):
        initial_state["db_type_override"] = request.db_type

    try:
        result = _graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        output["normalization_notes"] = result.get("normalization_notes", [])
    else:
        output["mongo_schema"] = result["mongo_schema"]
        output["embed_vs_reference_notes"] = result.get("embed_vs_reference_notes", [])
        output["partition_key_notes"] = result.get("partition_key_notes", [])

    run_id = save_run(request.requirement, output)
    output["run_id"] = run_id

    return output

class RecommendRequest(BaseModel):
    requirement: str


@app.post("/recommend")
def recommend_database_type(request: RecommendRequest):
    """
    Runs the pipeline and returns just the SQL/NoSQL recommendation.
    Note: currently runs the full graph (same known inefficiency as
    the MCP tool version) -- fine for now, worth optimizing later
    with a trunk-only compiled graph if this becomes a bottleneck.
    """
    try:
        result = _graph.invoke({"requirement": request.requirement})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "recommended_db_type": result["recommended_db_type"],
        "reasoning": result["db_type_reasoning"],
    }


from graph.nodes.migration import run_migration


class MigrateRequest(BaseModel):
    source_schema: str
    target_type: Literal["sql", "nosql"]


@app.post("/migrate")
def migrate_schema(request: MigrateRequest):
    try:
        return run_migration(request.source_schema, request.target_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs")
def get_all_runs():
    """Lists past runs (summary only, not full results)."""
    return list_runs()


@app.get("/runs/{run_id}")
def get_single_run(run_id: str):
    """Retrieves the full saved result for one past run."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


from typing import List
# from graph.nodes.trunk import relationship_validator as _unused  # not used directly here, but documents where relationship_validator lives
from graph.nodes.sql_branch import relationship_validator

class Attribute(BaseModel):
    name: str
    type: str
    required: bool


class EntityInput(BaseModel):
    name: str
    description: str
    attributes: List[Attribute]


class RegenerateRequest(BaseModel):
    entities: List[EntityInput]
    access_patterns: List[dict]
    db_type: Literal["sql", "nosql"]


@app.post("/regenerate")
def regenerate_from_entities(request: RegenerateRequest):
    """
    Re-runs only the downstream branch (not the trunk) from a
    user-edited entity list. This is the "mid-pipeline edit" flow:
    the user already got a design once, tweaked the entities in the
    UI, and wants DDL/schema regenerated from their edited version
    without re-analyzing the original requirement text from scratch.
    """
    from graph.nodes.sql_branch import relationship_validator
    from graph.nodes.docs import mermaid_diagram_generator

    entities = [e.dict() for e in request.entities]
    state = {
        "entities": entities,
        "access_patterns": request.access_patterns,
    }

    try:
        state.update(relationship_validator(state))

        if request.db_type == "sql":
            from graph.nodes.sql_branch import normalization_checker, sql_generator

            state.update(normalization_checker(state))
            state.update(sql_generator(state))
        else:
            from graph.nodes.nosql_branch import (
                embed_reference_advisor,
                partition_key_designer,
                document_schema_generator,
            )

            state.update(embed_reference_advisor(state))
            state.update(partition_key_designer(state))
            state.update(document_schema_generator(state))

        state.update(mermaid_diagram_generator(state))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    output = {
        "recommended_db_type": request.db_type,
        "entities": state["entities"],
        "relationships": state["relationships"],
        "mermaid_diagram": state["mermaid_diagram"],
    }

    if request.db_type == "sql":
        output["sql_ddl"] = state["sql_ddl"]
        output["validation_passed"] = state.get("validation_passed", False)
        output["validation_errors"] = state.get("validation_errors", [])
        output["normalization_notes"] = state.get("normalization_notes", [])
    else:
        output["mongo_schema"] = state["mongo_schema"]
        output["embed_vs_reference_notes"] = state.get("embed_vs_reference_notes", [])

    return output