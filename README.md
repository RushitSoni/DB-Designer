# AI Database Architect

A multi-stage AI pipeline that takes a plain-text requirement and produces a complete, validated database design (MySQL or MongoDB) — entities, relationships, indexes, DDL/document schema, and a Mermaid ER diagram.

Exposed two ways: as an **MCP server** (usable from Claude Desktop, Cursor, Antigravity, or any MCP client) and as a **REST API + React web UI** for demos.

## Why this isn't just an LLM call

SQL and NoSQL design are different disciplines — relational design is driven by normalization, NoSQL by access patterns. The pipeline forks *before* schema generation into genuinely different branches, with mechanical validation (SQLite execution for DDL, jsonschema for MongoDB) at every stage, not just LLM output trusted at face value.

## Architecture