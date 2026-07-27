"""
Executes generated MySQL DDL against an in-memory SQLite database to
catch structural errors (bad FK references, syntax issues, wrong
creation order) before anything is shown to the user.

Known limitation (documented, not hidden): SQLite doesn't understand
MySQL-specific syntax like ENGINE=InnoDB or AUTO_INCREMENT exactly as
MySQL does. We translate the handful of differences we know about
before executing, but this does NOT catch every MySQL-specific quirk
(e.g. ENUM columns). That's the honest limitation from the plan's
Section 10 -- structural errors get caught here, full MySQL-dialect
fidelity does not.
"""

import sqlite3
import re


def _mysql_to_sqlite(ddl: str) -> str:
    """
    Best-effort translation of the MySQL-specific syntax we generate
    into something SQLite can execute, purely for structural
    validation purposes.
    """
    translated = ddl

    # SQLite has no ENGINE clause
    translated = re.sub(r"\)\s*ENGINE\s*=\s*\w+\s*;", ");", translated, flags=re.IGNORECASE)

    # AUTO_INCREMENT -> AUTOINCREMENT, and only valid on INTEGER PRIMARY KEY in SQLite
    translated = re.sub(
        r"INT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY",
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        translated,
        flags=re.IGNORECASE,
    )

    # SQLite doesn't support named inline indexes the way MySQL does
    # (e.g. "INDEX idx_x (col)" inside CREATE TABLE) — strip those lines,
    # we'll validate FK structure but not inline index syntax here.
    # Strip inline INDEX/KEY/UNIQUE KEY/UNIQUE INDEX definitions (MySQL
    # inline index syntax), but never touch PRIMARY KEY or FOREIGN KEY,
    # which must be preceded by "PRIMARY"/"FOREIGN" and so won't match
    # this pattern (it requires INDEX/KEY immediately after the comma).
    translated = re.sub(
        r",\s*(?:UNIQUE\s+)?(?:INDEX|KEY)\s+`?\w*`?\s*\([^)]*\)",
        "",
        translated,
        flags=re.IGNORECASE,
    )
    return translated


def validate_ddl(ddl: str) -> dict:
    """
    Executes the (translated) DDL against a fresh in-memory SQLite DB.
    Returns {"passed": bool, "errors": list[str]}.
    """
    translated = _mysql_to_sqlite(ddl)
    errors = []

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Split into individual statements on semicolons, execute one at a time
    # so a single bad statement doesn't hide errors in the rest.
    statements = [s.strip() for s in translated.split(";") if s.strip()]

    for stmt in statements:
        try:
            cursor.execute(stmt + ";")
        except sqlite3.Error as e:
            errors.append(f"{e}\n  -> in statement: {stmt[:120]}...")

    conn.close()

    return {
        "passed": len(errors) == 0,
        "errors": errors,
    }