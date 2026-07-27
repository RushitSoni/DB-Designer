import { useState } from "react";
import axios from "axios";
// import MermaidDiagram from "./MermaidDiagram";

const API_BASE = "http://127.0.0.1:8000";

interface MigrateResult {
  source_type: string;
  target_type: string;
  sql_ddl?: string;
  mongo_schema?: Record<string, unknown>;
  validation_passed: boolean;
  validation_errors: string[];
  normalization_notes?: string[];
  embed_vs_reference_notes?: string[];
  inferred_access_patterns_note?: string;
}

export default function MigratePanel() {
  const [open, setOpen] = useState(false);
  const [sourceSchema, setSourceSchema] = useState("");
  const [targetType, setTargetType] = useState<"sql" | "nosql">("nosql");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MigrateResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleMigrate() {
    if (!sourceSchema.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post<MigrateResult>(`${API_BASE}/migrate`, {
        source_schema: sourceSchema,
        target_type: targetType,
      });
      setResult(response.data);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError("Unknown error occurred.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="section">
      <h2 onClick={() => setOpen(!open)} style={{ cursor: "pointer" }}>
        Migrate Existing Schema {open ? "▲" : "▼"}
      </h2>
      {open && (
        <>
          <p style={{ fontSize: "0.85rem", opacity: 0.8 }}>
            Paste an existing MySQL DDL or MongoDB JSON Schema below, pick the
            target type, and convert it.
          </p>
          <textarea
            placeholder="Paste MySQL CREATE TABLE statements or a MongoDB JSON Schema here..."
            value={sourceSchema}
            onChange={(e) => setSourceSchema(e.target.value)}
            style={{ minHeight: "160px", fontFamily: "monospace", fontSize: "0.85rem" }}
          />
          <div style={{ marginTop: "0.75rem" }}>
            <label>
              Convert to:{" "}
              <select
                value={targetType}
                onChange={(e) => setTargetType(e.target.value as "sql" | "nosql")}
              >
                <option value="nosql">MongoDB (NoSQL)</option>
                <option value="sql">MySQL (SQL)</option>
              </select>
            </label>
          </div>
          <button onClick={handleMigrate} disabled={loading || !sourceSchema.trim()}>
            {loading ? "Migrating..." : "Migrate Schema"}
          </button>

          {error && <p className="error">Error: {error}</p>}

          {result && (
            <div style={{ marginTop: "1.5rem" }}>
              <p>
                {result.source_type.toUpperCase()} → {result.target_type.toUpperCase()}
              </p>
              <p>
                Validation:{" "}
                {result.validation_passed ? (
                  <strong style={{ color: "#6fdb8f" }}>Passed ✓</strong>
                ) : (
                  <strong className="error">Failed</strong>
                )}
              </p>
              {result.validation_errors.length > 0 && (
                <ul className="error">
                  {result.validation_errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
              {result.inferred_access_patterns_note && (
                <p style={{ fontSize: "0.8rem", opacity: 0.7, fontStyle: "italic" }}>
                  Note: {result.inferred_access_patterns_note}
                </p>
              )}

              {result.sql_ddl && (
                <>
                  <h3>Generated DDL</h3>
                  <pre>{result.sql_ddl}</pre>
                </>
              )}

              {result.mongo_schema && (
                <>
                  <h3>Generated MongoDB Schema</h3>
                  <pre>{JSON.stringify(result.mongo_schema, null, 2)}</pre>
                </>
              )}

              {result.embed_vs_reference_notes && (
                <>
                  <h3>Embed vs Reference Decisions</h3>
                  <ul>
                    {result.embed_vs_reference_notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}