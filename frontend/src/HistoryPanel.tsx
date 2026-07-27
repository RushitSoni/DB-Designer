import { useEffect, useState } from "react";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

interface RunSummary {
  id: string;
  requirement: string;
  db_type: string;
  created_at: string;
}

interface Props {
  onSelectRun: (runId: string) => void;
}

export default function HistoryPanel({ onSelectRun }: Props) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
  if (!open) return;

  async function loadRuns() {
    setLoading(true);
    try {
      const response = await axios.get<RunSummary[]>(`${API_BASE}/runs`);
      setRuns(response.data);
    } catch {
      // Silently ignore -- history is a convenience feature, not
      // critical path, so a failed fetch shouldn't block the main UI.
    } finally {
      setLoading(false);
    }
  }

  loadRuns();
}, [open]);

  return (
    <div className="section">
      <h2 onClick={() => setOpen(!open)} style={{ cursor: "pointer" }}>
        Past Runs {open ? "▲" : "▼"}
      </h2>
      {open && (
        <>
          {loading && <p>Loading...</p>}
          {!loading && runs.length === 0 && <p>No past runs yet.</p>}
          <ul style={{ listStyle: "none", paddingLeft: 0 }}>
            {runs.map((run) => (
              <li
                key={run.id}
                onClick={() => onSelectRun(run.id)}
                style={{
                  padding: "0.6rem",
                  marginBottom: "0.4rem",
                  background: "#0f1117",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                <span className={`badge ${run.db_type}`}>{run.db_type.toUpperCase()}</span>{" "}
                <span style={{ fontSize: "0.85rem" }}>
                  {run.requirement.length > 100
                    ? run.requirement.slice(0, 100) + "..."
                    : run.requirement}
                </span>
                <div style={{ fontSize: "0.7rem", opacity: 0.6 }}>
                  {new Date(run.created_at).toLocaleString()}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}