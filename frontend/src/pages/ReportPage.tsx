import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getSessionReport, type InterviewReportResponse } from "../api";

export default function ReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const nav = useNavigate();
  const [data, setData] = useState<InterviewReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    getSessionReport(sessionId)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [sessionId]);

  if (loading) return <div className="page"><p className="loading">Loading report...</p></div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!data) return <div className="page"><p className="empty">No report available.</p></div>;

  const report = data.report || {};

  function Badge({ label, variant }: { label: string; variant: string }) {
    return <span className={`badge ${variant}`}>{label}</span>;
  }

  const level: string = (report.candidate_level as string) || data.experience || "N/A";
  const levelColor = ["Lead", "Senior"].includes(level) ? "green" : level === "Mid" ? "yellow" : "red";
  const hire: string = (report.hire_recommendation as string) || "N/A";
  const hireColor = hire === "HIRE" ? "green" : hire === "CONSIDER" ? "yellow" : "red";

  return (
    <div className="page">
      <div className="report-header">
        <h1>Interview Report</h1>
        <button onClick={() => nav("/")} className="link-btn">&larr; Sessions</button>
      </div>
      <p className="subtitle"><code>{data.role || "Untitled"}</code> &middot; {data.company || "—"}</p>

      <div className="report-grid">
        <div className="card report-card">
          <h3>Candidate Level</h3>
          <Badge label={level} variant={levelColor} />
        </div>
        <div className="card report-card">
          <h3>Recommendation</h3>
          <Badge label={hire} variant={hireColor} />
        </div>
        <div className="card report-card">
          <h3>Coverage</h3>
          <span className="big-num">{report.coverage_percentage as string}</span>
        </div>
      </div>

      <div className="report-grid">
        <div className="card report-card">
          <h3>Questions</h3>
          <span className="big-num">{data.total_questions}</span>
        </div>
        <div className="card report-card">
          <h3>Status</h3>
          <Badge label={data.status} variant={data.status === "completed" ? "green" : "yellow"} />
        </div>
        <div className="card report-card">
          <h3>Duration</h3>
          <span className="big-num">
            {data.duration_seconds ? `${Math.floor(data.duration_seconds / 60)}m` : "—"}
          </span>
        </div>
      </div>

      {!!report.interview_summary && (
        <div className="card">
          <h3>Summary</h3>
          <p>{report.interview_summary as string}</p>
        </div>
      )}

      <div className="card">
        <h3>Strengths</h3>
        {Array.isArray(report.strengths) && report.strengths.length ? (
          <ul>{(report.strengths as string[]).map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>
        ) : <p className="empty">None listed</p>}
      </div>

      <div className="card">
        <h3>Weaknesses</h3>
        {Array.isArray(report.weaknesses) && report.weaknesses.length ? (
          <ul>{(report.weaknesses as string[]).map((w: string, i: number) => <li key={i}>{w}</li>)}</ul>
        ) : <p className="empty">None listed</p>}
      </div>

      <div className="card">
        <h3>Knowledge Gaps</h3>
        {renderGapList(report, "complete_knowledge_gaps", "Complete gaps (scored 0-3)", "red")}
        {renderGapList(report, "partial_knowledge_areas", "Partial knowledge (scored 4-6)", "yellow")}
        {renderGapList(report, "advanced_topics_not_covered", "Advanced topics not covered", "blue")}
        {!report.complete_knowledge_gaps && !report.partial_knowledge_areas && !report.advanced_topics_not_covered && (
          <p className="empty">No gaps identified</p>
        )}
      </div>

      <div className="card">
        <h3>Skills</h3>
        <div className="skill-chips">
          {(data.skills_tested || []).map((s: string) => (
            <span key={s} className="chip tested">{s} ✓</span>
          ))}
          {(data.skills_not_tested || []).map((s: string) => (
            <span key={s} className="chip untested">{s}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function renderGapList(report: Record<string, unknown>, key: string, title: string, color: string) {
  const items = report[key];
  if (!Array.isArray(items) || items.length === 0) return null;
  return (
    <>
      <h4 style={{ color: color === "red" ? "#f87171" : color === "yellow" ? "#fbbf24" : "#60a5fa" }}>{title}</h4>
      <ul>{(items as string[]).map((g: string, i: number) => <li key={i}>{g}</li>)}</ul>
    </>
  );
}
