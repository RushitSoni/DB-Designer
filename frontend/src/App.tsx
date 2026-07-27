import { useState } from "react";
import axios from "axios";
import MermaidDiagram from "./MermaidDiagram";
import HistoryPanel from "./HistoryPanel";
import MigratePanel from "./MigratePanel";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

interface Attribute {
  name: string;
  type: string;
  required: boolean;
}

interface Entity {
  name: string;
  description: string;
  attributes: Attribute[];
}

interface DesignResult {
  recommended_db_type: "sql" | "nosql";
  reasoning: string;
  entities: Entity[];
  validation_passed: boolean;
  validation_errors: string[];
  mermaid_diagram: string;
  sql_ddl?: string;
  mongo_schema?: Record<string, unknown>;
  normalization_notes?: string[];
  embed_vs_reference_notes?: string[];
  partition_key_notes?: string[];
  run_id?: string;
}



function App() {
  const [requirement, setRequirement] = useState("");
  const [dbType, setDbType] = useState<"auto" | "sql" | "nosql">("auto");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DesignResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editedEntities, setEditedEntities] = useState<Entity[]>([]);
  const [regenerating, setRegenerating] = useState(false);

  async function handleGenerate() {
    if (!requirement.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post<DesignResult>(`${API_BASE}/design`, {
        requirement,
        db_type: dbType,
      });
      setResult(response.data);
      setEditedEntities(response.data.entities);
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

  function updateAttribute(
    entityIndex: number,
    attrIndex: number,
    field: "name" | "type",
    value: string
  ) {
    setEditedEntities((prev) => {
      const updated = [...prev];
      const entity = { ...updated[entityIndex] };
      const attrs = [...entity.attributes];
      attrs[attrIndex] = { ...attrs[attrIndex], [field]: value };
      entity.attributes = attrs;
      updated[entityIndex] = entity;
      return updated;
    });
  }

  function addAttribute(entityIndex: number) {
    setEditedEntities((prev) => {
      const updated = [...prev];
      const entity = { ...updated[entityIndex] };
      entity.attributes = [
        ...entity.attributes,
        { name: "new_field", type: "string", required: false },
      ];
      updated[entityIndex] = entity;
      return updated;
    });
  }

  function removeAttribute(entityIndex: number, attrIndex: number) {
    setEditedEntities((prev) => {
      const updated = [...prev];
      const entity = { ...updated[entityIndex] };
      entity.attributes = entity.attributes.filter((_, i) => i !== attrIndex);
      updated[entityIndex] = entity;
      return updated;
    });
  }

  async function handleRegenerate() {
    if (!result) return;

    setRegenerating(true);
    setError(null);

    try {
      const response = await axios.post(`${API_BASE}/regenerate`, {
        entities: editedEntities,
        // Original access patterns aren't threaded into the edit UI yet,
        // so index/embed decisions on regeneration rely only on
        // relationships (FKs), not access-pattern frequency. Acceptable
        // simplification for now -- see project notes.
        access_patterns: [],
        db_type: result.recommended_db_type,
      });

      setResult({ ...result, ...response.data });

      // Keep the edit form in sync with whatever the backend actually
      // settled on (e.g. normalization_checker may have removed a
      // genuinely redundant field) -- otherwise the form would keep
      // showing stale entities that no longer match the real schema.
      if (response.data.entities) {
        setEditedEntities(response.data.entities);
      }
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail ?? err.message);
      } else {
        setError("Unknown error occurred.");
      }
    } finally {
      setRegenerating(false);
    }
  }


  async function handleSelectRun(runId: string) {
  setLoading(true);
  setError(null);
  try {
    const response = await axios.get(`${API_BASE}/runs/${runId}`);
    const savedResult: DesignResult = response.data.result_json;
    setResult(savedResult);
    setEditedEntities(savedResult.entities);
    setRequirement(response.data.requirement);
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
    <div className="container">
      <h1>AI Database Architect</h1>
      <p>Describe your system in plain text. Get a validated schema back.</p>

      <textarea
        placeholder="e.g. Build an online food ordering platform where customers browse restaurants, place orders, and track delivery status..."
        value={requirement}
        onChange={(e) => setRequirement(e.target.value)}
      />

      <div style={{ marginTop: "0.75rem" }}>
        <label>
          DB type:{" "}
          <select
            value={dbType}
            onChange={(e) => setDbType(e.target.value as "auto" | "sql" | "nosql")}
          >
            <option value="auto">Auto-detect</option>
            <option value="sql">Force SQL</option>
            <option value="nosql">Force NoSQL</option>
          </select>
        </label>
      </div>

      <button onClick={handleGenerate} disabled={loading || !requirement.trim()}>
        {loading ? "Designing... (this takes a bit)" : "Generate Design"}
      </button>

      <HistoryPanel onSelectRun={handleSelectRun} />
      <MigratePanel />


      {error && (
        <div className="section">
          <p className="error">Error: {error}</p>
        </div>
      )}

      {result && (
        <>
          <div className="section">
            <h2>
              Recommendation{" "}
              <span className={`badge ${result.recommended_db_type}`}>
                {result.recommended_db_type.toUpperCase()}
              </span>
            </h2>
            <p>{result.reasoning}</p>
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
            {result.run_id && (
              <p style={{ fontSize: "0.8rem", opacity: 0.6 }}>Run ID: {result.run_id}</p>
            )}
          </div>

          <div className="section">
            <h2>Entities (editable)</h2>
            {editedEntities.map((entity, ei) => (
              <div key={entity.name} style={{ marginBottom: "1.5rem" }}>
                <strong>{entity.name}</strong> — {entity.description}
                <ul style={{ listStyle: "none", paddingLeft: 0 }}>
                  {entity.attributes.map((attr, ai) => (
                    <li
                      key={ai}
                      style={{
                        marginBottom: "0.3rem",
                        display: "flex",
                        alignItems: "center",
                        gap: "0.4rem",
                      }}
                    >
                      <input
                        value={attr.name}
                        onChange={(e) => updateAttribute(ei, ai, "name", e.target.value)}
                        style={{ width: "140px" }}
                      />
                      <select
                        value={attr.type}
                        onChange={(e) => updateAttribute(ei, ai, "type", e.target.value)}
                      >
                        <option value="string">string</option>
                        <option value="integer">integer</option>
                        <option value="float">float</option>
                        <option value="boolean">boolean</option>
                        <option value="date">date</option>
                        <option value="datetime">datetime</option>
                      </select>
                      <button
                        onClick={() => removeAttribute(ei, ai)}
                        title="Remove field"
                        style={{
                          padding: "0.2rem 0.6rem",
                          fontSize: "0.8rem",
                          background: "#5f1e1e",
                          margin: 0,
                        }}
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => addAttribute(ei)}
                  style={{ fontSize: "0.8rem", padding: "0.3rem 0.8rem" }}
                >
                  + Add field
                </button>
              </div>
            ))}
            <button onClick={handleRegenerate} disabled={regenerating}>
              {regenerating ? "Regenerating..." : "Regenerate Schema from Edits"}
            </button>
           
          </div>

          {result.sql_ddl && (
            <div className="section">
              <h2>Generated MySQL DDL</h2>
              <pre>{result.sql_ddl}</pre>
            </div>
          )}

          {result.mongo_schema && (
            <div className="section">
              <h2>Generated MongoDB Schema</h2>
              <pre>{JSON.stringify(result.mongo_schema, null, 2)}</pre>
            </div>
          )}

          {result.embed_vs_reference_notes && (
            <div className="section">
              <h2>Embed vs Reference Decisions</h2>
              <ul>
                {result.embed_vs_reference_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="section">
            <h2>ER Diagram</h2>
            <MermaidDiagram chart={result.mermaid_diagram} />
          </div>
        </>
      )}
    </div>
  );
}

export default App;