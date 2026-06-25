const BASE = "http://localhost:8000";

export interface UploadResponse {
  message: string;
  session_id: string;
  extracted_text_preview: string;
  role: string;
  experience: string;
  company: string;
  skills_found: string[];
}

export interface StartResponse {
  session_id: string;
  question: string;
  topic: string;
  difficulty: string;
  question_number: number;
}

export interface AnswerResponse {
  session_id: string;
  question_number: number;
  question: string;
  topic: string;
  difficulty: string;
  feedback: string;
  score: number;
  action: string;
  next_question: string | null;
  next_topic: string | null;
  next_difficulty: string | null;
  final_report: Record<string, unknown> | null;
  is_complete: boolean;
  skills_tested: string[];
  coverage_percentage: number;
}

export interface SessionItem {
  id: string;
  role: string | null;
  company: string | null;
  experience: string | null;
  status: string;
  total_questions_asked: number;
  total_answers_given: number;
  coverage_percentage: number;
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
  created_at: string | null;
}

export interface SessionListResponse {
  sessions: SessionItem[];
}

export interface ExchangeItem {
  id: number;
  session_id: string;
  question_number: number;
  question: string;
  answer: string | null;
  feedback: string | null;
  score: number | null;
  action: string | null;
  topic: string | null;
  difficulty: string | null;
  timestamp: string | null;
  token_count: number;
  latency_ms: number;
}

export interface SessionDetailResponse {
  session: Record<string, unknown>;
  exchanges: ExchangeItem[];
}

export interface InterviewReportResponse {
  session_id: string;
  role: string;
  company: string;
  experience: string;
  status: string;
  total_questions: number;
  total_answers: number;
  duration_seconds: number | null;
  skills_tested: string[];
  skills_not_tested: string[];
  coverage_percentage: number;
  report: Record<string, unknown>;
}

export async function uploadDocuments(
  resume: File,
  jd: File | null,
  jdText: string | null
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("resume", resume);
  if (jd) form.append("jd", jd);
  if (jdText) form.append("jd_text", jdText);
  const res = await fetch(`${BASE}/document/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function startInterview(
  sessionId: string,
  numQuestions = 8
): Promise<StartResponse> {
  const res = await fetch(`${BASE}/interview/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, num_questions: numQuestions }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Start failed");
  }
  return res.json();
}

export async function answerQuestion(
  sessionId: string,
  question: string,
  answer: string,
  topic?: string,
  difficulty?: string
): Promise<AnswerResponse> {
  const res = await fetch(`${BASE}/interview/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      question,
      answer,
      topic: topic || undefined,
      difficulty: difficulty || undefined,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Answer failed");
  }
  return res.json();
}

export async function listSessions(): Promise<SessionListResponse> {
  const res = await fetch(`${BASE}/interview/sessions`);
  if (!res.ok) throw new Error("Failed to list sessions");
  return res.json();
}

export async function getSessionDetail(
  sessionId: string
): Promise<SessionDetailResponse> {
  const res = await fetch(`${BASE}/interview/sessions/${sessionId}`);
  if (!res.ok) throw new Error("Failed to get session detail");
  return res.json();
}

export async function getSessionReport(
  sessionId: string
): Promise<InterviewReportResponse> {
  const res = await fetch(`${BASE}/interview/sessions/${sessionId}/report`);
  if (!res.ok) throw new Error("Failed to get report");
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE}/interview/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete session");
}
