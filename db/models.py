"""
App's own persistence: saves each design run so it can be revisited
later. Uses SQLite for zero-setup simplicity (per the plan's fallback
option), storing the full state as JSON rather than modeling every
field as its own column -- simplest thing that works for a save/list/
retrieve use case.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone

DB_PATH = "runs.db"


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            requirement TEXT NOT NULL,
            db_type TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_run(requirement: str, result: dict) -> str:
    """Saves a completed design run, returns the generated run id."""
    run_id = str(uuid.uuid4())
    conn = _get_connection()
    conn.execute(
        "INSERT INTO runs (id, requirement, db_type, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            run_id,
            requirement,
            result.get("recommended_db_type", "unknown"),
            json.dumps(result),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return run_id


def list_runs() -> list[dict]:
    """Returns a summary (no full result) of all past runs, newest first."""
    conn = _get_connection()
    rows = conn.execute(
        "SELECT id, requirement, db_type, created_at FROM runs ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_run(run_id: str) -> dict | None:
    """Returns the full saved result for one run, or None if not found."""
    conn = _get_connection()
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    result["result_json"] = json.loads(result["result_json"])
    return result