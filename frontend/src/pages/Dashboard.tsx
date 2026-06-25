import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { deleteSession, listSessions, uploadDocuments, type SessionItem } from "../api";

export default function Dashboard() {
  const nav = useNavigate();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [resume, setResume] = useState<File | null>(null);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [numQuestions, setNumQuestions] = useState(8);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const loadSessions = useCallback(() => {
    setLoading(true);
    listSessions()
      .then((r) => setSessions(r.sessions))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(loadSessions, [loadSessions]);

  async function handleUpload(e: FormEvent) {
    e.preventDefault();
    if (!resume) return setError("Resume is required");
    if (!jdFile && !jdText.trim()) return setError("Provide JD as file or paste text");
    setUploading(true);
    setError("");
    try {
      const result = await uploadDocuments(resume, jdFile, jdText.trim() || null);
      nav(`/interview/${result.session_id}?num=${numQuestions}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this session?")) return;
    try {
      await deleteSession(id);
      setSessions((s) => s.filter((x) => x.id !== id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  const completed = sessions.filter((s) => s.status === "completed");
  const inProgress = sessions.filter((s) => s.status === "in_progress");
  const created = sessions.filter((s) => s.status === "created");

  return (
    <div className="page">
      <h1>AI Interviewer</h1>
      <p className="subtitle">Upload resume + JD to start a screening interview</p>

      {error && <p className="error">{error}</p>}

      <form onSubmit={handleUpload} className="card">
        <h3>New Interview</h3>
        <div className="form-row">
          <div className="form-group">
            <label>Resume (PDF/DOCX)</label>
            <input type="file" accept=".pdf,.docx,.doc" onChange={(e) => setResume(e.target.files?.[0] ?? null)} required />
          </div>
          <div className="form-group">
            <label>JD file</label>
            <input type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => setJdFile(e.target.files?.[0] ?? null)} />
          </div>
        </div>
        <div className="form-group">
          <label>Or paste JD text</label>
          <textarea rows={3} value={jdText} onChange={(e) => setJdText(e.target.value)} placeholder="Paste job description..." />
        </div>
        <div className="form-row">
          <div className="form-group" style={{ maxWidth: 200 }}>
            <label>Questions ({numQuestions})</label>
            <input type="range" min={3} max={20} value={numQuestions} onChange={(e) => setNumQuestions(Number(e.target.value))} />
          </div>
        </div>
        <button type="submit" disabled={uploading}>
          {uploading ? "Uploading..." : "Start Interview"}
        </button>
      </form>

      <div className="dashboard-stats">
        <div className="stat-card"><span className="stat-num">{sessions.length}</span> Total</div>
        <div className="stat-card"><span className="stat-num">{inProgress.length + created.length}</span> Active</div>
        <div className="stat-card"><span className="stat-num">{completed.length}</span> Completed</div>
      </div>

      {loading ? (
        <p className="loading">Loading sessions...</p>
      ) : sessions.length === 0 ? (
        <div className="card" style={{ textAlign: "center" }}>
          <p className="empty">No sessions yet. Upload resume + JD above to start.</p>
        </div>
      ) : (
        <>
          {renderSection("In Progress", inProgress, nav, handleDelete)}
          {renderSection("Awaiting Start", created, nav, handleDelete)}
          {renderSection("Completed", completed, nav, handleDelete)}
        </>
      )}
    </div>
  );
}

function renderSection(
  title: string,
  items: SessionItem[],
  nav: (path: string) => void,
  handleDelete: (id: string) => void
) {
  if (items.length === 0) return null;
  return (
    <div className="card">
      <h3>{title} ({items.length})</h3>
      {items.map((s) => (
        <div key={s.id} className="session-row">
          <div className="session-row-left">
            <strong>{s.role || "Untitled"}</strong>
            <span className="session-row-meta">
              Q{s.total_questions_asked} &middot; {s.coverage_percentage}% &middot;
              {s.duration_seconds ? ` ${Math.floor(s.duration_seconds / 60)}m` : ""}
              {s.created_at ? ` ${new Date(s.created_at).toLocaleDateString()}` : ""}
            </span>
          </div>
          <div className="session-row-actions">
            {s.status === "completed" ? (
              <button className="sm" onClick={() => nav(`/report/${s.id}`)}>Report</button>
            ) : (
              <button className="sm" onClick={() => nav(`/interview/${s.id}?num=${Math.max(s.total_questions_asked + 3, 8)}`)}>
                {s.total_questions_asked > 0 ? "Continue" : "Start"}
              </button>
            )}
            {s.status === "completed" && (
              <button
                className="sm secondary"
                onClick={() => nav(`/interview/${s.id}?num=${Math.max(s.total_questions_asked + 3, 8)}&mode=review`)}
              >
                Review
              </button>
            )}
            <button className="sm danger" onClick={() => handleDelete(s.id)}>Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}
