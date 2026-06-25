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
  const answerRef = useRef("");
  const [autoMode, setAutoMode] = useState(true);
  const autoModeRef = useRef(true);
  const [skills, setSkills] = useState<string[]>([]);
  const [coverage, setCoverage] = useState(0);
  const [role, setRole] = useState("");
  const isReview = (searchParams.get("mode") || "") === "review";

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
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onresult = (event: any) => {
        // append interim/final transcript
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript + (event.results[i].isFinal ? "" : "");
        }
        setAnswer((prev) => {
          const next = `${prev} ${transcript}`.trim();
          answerRef.current = next;
          return next;
        });
      };

      recognition.onend = () => {
        setListening(false);
        // Auto-submit when in autoMode and we've captured an answer
        if (autoModeRef.current) {
          const a = (answerRef.current || "").trim();
          if (a) {
            setTimeout(() => {
              handleSubmit();
            }, 200);
            return;
          }
          // No answer captured — try listening again once
          setTimeout(() => {
            try {
              recognition.start();
              setListening(true);
            } catch (e) {
              // ignore
            }
          }, 400);
        }
      };

      recognition.onerror = (event: any) => {
        setListening(false);
        setError(`Speech recognition error: ${event.error}`);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  useEffect(() => {
    autoModeRef.current = autoMode;
  }, [autoMode]);

  // When a new question arrives, auto-speak and start recording if autoMode
  useEffect(() => {
    if (!currentQ) return;
    if (!autoMode) return;
    const text = currentQ.question || "";
    if (!text) return;
    // speak then start recognition
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      const utt = new SpeechSynthesisUtterance(text);
      utt.lang = "en-US";
      utt.onend = () => {
        // start recognition after speaking
        try {
          recognitionRef.current?.start();
          setListening(true);
        } catch (e) {
          // ignore
        }
      };
      window.speechSynthesis.speak(utt);
    } else {
      try {
        recognitionRef.current?.start();
        setListening(true);
      } catch (e) {
        // ignore
      }
    }
  }, [currentQ, autoMode]);

  useEffect(() => {
    if (!sessionId) return;

    getSessionDetail(sessionId)
      .then((detail) => {
        const exchanges = detail.exchanges || [];
        setSkills((detail.session?.tested_skills as string[]) || []);
        setCoverage((detail.session?.coverage_percentage as number) || 0);
        setRole((detail.session?.role as string) || "");

        if (isReview) {
          setPastExchanges(exchanges);
          setLoading(false);
          return;
        }

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
    const localAnswer = (answerRef.current && answerRef.current.trim()) || answer.trim();
    if (!currentQ || !localAnswer || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await answerQuestion(
        sessionId!,
        currentQ.question,
        localAnswer,
        currentQ.topic,
        currentQ.difficulty
      );
      setHistory((h) => [...h, { ...res, userAnswer: localAnswer }]);
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
      answerRef.current = "";
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
  if (isReview) return (
    <div className="page">
      <h2>Session Review</h2>
      <p>Coverage: <strong>{coverage}%</strong> — Skills tested: {skills.join(", ") || "none"}</p>
      <p>Session: <code>{sessionId}</code></p>

      {pastExchanges.length === 0 ? (
        <div className="card"><p className="empty">No exchanges recorded for this session.</p></div>
      ) : (
        <div className="card">
          {pastExchanges.map((e) => (
            <div key={e.id} className="exchange">
              <div className="exchange-q"><strong>Q{e.question_number}:</strong> {e.question}</div>
              <div className="exchange-a"><strong>You:</strong> {e.answer}</div>
              {e.feedback && <div className="exchange-feedback"><strong>Feedback:</strong> {e.feedback}</div>}
              {e.score != null && <div className="exchange-score">Score: {e.score}/10</div>}
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
        <button onClick={() => nav(`/report/${sessionId}`)}>View Full Report</button>
        <button onClick={() => nav("/")} className="secondary">Back</button>
      </div>
    </div>
  );
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
                <label style={{ marginLeft: "0.75rem" }}>
                  <input
                    type="checkbox"
                    checked={autoMode}
                    onChange={(e) => setAutoMode(e.target.checked)}
                  />
                  Auto interview (voice-driven)
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
