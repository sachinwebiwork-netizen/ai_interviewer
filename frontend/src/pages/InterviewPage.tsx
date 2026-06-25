import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  answerQuestion,
  getSessionDetail,
  startInterview,
  type AnswerResponse,
  type ExchangeItem,
  type StartResponse,
} from "../api";

interface HistoryItem extends AnswerResponse {
  userAnswer: string;
}

const SpeechRecognition =
  (window as any).SpeechRecognition ||
  (window as any).webkitSpeechRecognition ||
  null;

export default function InterviewPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const nav = useNavigate();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  const numQuestions = Number(searchParams.get("num")) || 8;

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(false);

  const [currentQ, setCurrentQ] = useState<StartResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [pastExchanges, setPastExchanges] = useState<ExchangeItem[]>([]);
  const [answer, setAnswer] = useState("");
  const [completed, setCompleted] = useState(false);
  const [skills, setSkills] = useState<string[]>([]);
  const [coverage, setCoverage] = useState(0);
  const [role, setRole] = useState("");

  const resumeFromHistory = useCallback(
    async (exchanges: ExchangeItem[], session: Record<string, unknown>) => {
      setPastExchanges(exchanges);
      setSkills((session.tested_skills as string[]) || []);
      setCoverage((session.coverage_percentage as number) || 0);
      setRole((session.role as string) || "");

      const qNum = exchanges.length + 1;

      if (qNum > numQuestions) {
        setCompleted(true);
        setLoading(false);
        return;
      }

      const res = await startInterview(sessionId!, numQuestions);
      setCurrentQ(res);
      setLoading(false);
    },
    [sessionId, numQuestions]
  );

  useEffect(() => {
    if (SpeechRecognition) {
      setSpeechSupported(true);
      const recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setAnswer((prev) => `${prev} ${transcript}`.trim());
      };

      recognition.onend = () => {
        setListening(false);
      };

      recognition.onerror = (event: any) => {
        setListening(false);
        setError(`Speech recognition error: ${event.error}`);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    getSessionDetail(sessionId)
      .then((detail) => {
        const exchanges = detail.exchanges || [];
        if (exchanges.length > 0) {
          return resumeFromHistory(exchanges, detail.session);
        }
        return startInterview(sessionId, numQuestions).then((r) => {
          setCurrentQ(r);
          setRole(r.question ? "Interview" : "");
          setLoading(false);
        });
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [sessionId, numQuestions, resumeFromHistory]);

  async function handleSubmit() {
    if (!currentQ || !answer.trim() || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await answerQuestion(
        sessionId!,
        currentQ.question,
        answer,
        currentQ.topic,
        currentQ.difficulty
      );
      setHistory((h) => [...h, { ...res, userAnswer: answer }]);
      setSkills(res.skills_tested);
      setCoverage(res.coverage_percentage);

      if (res.is_complete) {
        setCompleted(true);
      } else {
        setCurrentQ({
          session_id: sessionId!,
          question: res.next_question!,
          topic: res.next_topic || currentQ.topic,
          difficulty: res.next_difficulty || currentQ.difficulty,
          question_number: res.question_number + 1,
        });
      }
      setAnswer("");
      inputRef.current?.focus();
      if (speechEnabled) {
        speakText(res.feedback || "Answer received.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  }

  function speakText(text: string) {
    if (!window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }

  function toggleListening() {
    if (!recognitionRef.current) return;
    if (listening) {
      recognitionRef.current.stop();
      setListening(false);
      return;
    }
    setError("");
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not start speech recognition.");
      setListening(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  if (loading) return <div className="page"><p className="loading">Starting interview...</p></div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (completed) return (
    <div className="page">
      <div className="card" style={{ textAlign: "center" }}>
        <h2>Interview Complete</h2>
        <p>Coverage: <strong>{coverage}%</strong> — Skills tested: {skills.join(", ") || "none"}</p>
        <p>Session: <code>{sessionId}</code></p>
        <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", justifyContent: "center" }}>
          <button onClick={() => nav(`/report/${sessionId}`)}>View Full Report</button>
          <button onClick={() => nav("/")} className="secondary">New Interview</button>
        </div>
      </div>
    </div>
  );

  const qNum = currentQ?.question_number || 0;
  const action = history.length > 0 ? history[history.length - 1].action : "";
  const lastScore = history.length > 0 ? history[history.length - 1].score : null;

  return (
    <div className="page">
      <div className="interview-header">
        <span className="interview-role">{role || "Interview"}</span>
        <span className="interview-progress">Question {qNum} of {numQuestions}</span>
      </div>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${Math.min(100, (qNum / numQuestions) * 100)}%` }} />
        <span className="progress-label">
          {coverage}% skills covered &middot; {skills.length} tested
        </span>
      </div>

      <div className="card question-card">
        <div className="q-meta">
          <span className="tag topic">{currentQ?.topic}</span>
          <span className="tag diff">{currentQ?.difficulty}</span>
          <span className="tag num">Q{qNum}/{numQuestions}</span>
        </div>
        <p className="question-text">{currentQ?.question}</p>
      </div>

      {pastExchanges.length > 0 && (
        <details className="card past-sessions">
          <summary>Previous answers ({pastExchanges.length})</summary>
          {pastExchanges.map((e) => (
            <div key={e.id} className="exchange">
              <div className="exchange-q"><strong>Q{e.question_number}:</strong> {e.question}</div>
              <div className="exchange-a"><strong>You:</strong> {e.answer}</div>
              {e.feedback && <div className="exchange-feedback"><strong>Feedback:</strong> {e.feedback}</div>}
              {e.score != null && <div className="exchange-score">Score: {e.score}/10</div>}
            </div>
          ))}
        </details>
      )}

      {action && (
        <div className={`action-banner ${action.toLowerCase()}`}>
          Last action: <strong>{action.replace(/_/g, " ")}</strong>
          {lastScore != null && <> &middot; Score: {lastScore}/10</>}
        </div>
      )}

      <div className="history">
        {history.map((h, i) => (
          <div key={i} className="exchange">
            <div className="exchange-q">
              <strong>Q{h.question_number}:</strong> {h.question}
            </div>
            <div className="exchange-a">
              <strong>You:</strong> {h.userAnswer}
            </div>
            <div className="exchange-feedback">
              <strong>Feedback:</strong> {h.feedback}
            </div>
            <div className="exchange-score">
              Score: {h.score}/10 &middot; Action: {h.action.replace(/_/g, " ")}
            </div>
          </div>
        ))}
      </div>

      <div className="card answer-card">
        <label htmlFor="answer">Your answer:</label>
        <textarea
          ref={inputRef}
          id="answer"
          rows={4}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your answer here... (Enter to submit, Shift+Enter for newline)"
          disabled={submitting}
          autoFocus
        />
        <div className="voice-controls">
          {speechSupported ? (
            <>
              <button type="button" onClick={toggleListening} className={listening ? "active" : "secondary"}>
                {listening ? "Stop Listening" : "Speak Answer"}
              </button>
              <label>
                <input
                  type="checkbox"
                  checked={speechEnabled}
                  onChange={(e) => setSpeechEnabled(e.target.checked)}
                />
                Read feedback aloud
              </label>
            </>
          ) : (
            <p className="small-text">Voice recognition not supported in this browser.</p>
          )}
        </div>
        {error && <p className="error">{error}</p>}
        <button onClick={handleSubmit} disabled={submitting || !answer.trim()}>
          {submitting ? "Submitting..." : "Submit Answer"}
        </button>
      </div>
    </div>
  );
}
