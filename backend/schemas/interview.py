from pydantic import BaseModel
from typing import Optional


class StartInterviewRequest(BaseModel):
    session_id: str
    num_questions: int = 8


class StartInterviewResponse(BaseModel):
    session_id: str
    question: str
    topic: str
    difficulty: str
    question_number: int


class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str
    topic: Optional[str] = None
    difficulty: Optional[str] = None


class AnswerResponse(BaseModel):
    session_id: str
    question_number: int
    question: str
    topic: str
    difficulty: str
    feedback: str
    score: int
    action: str
    next_question: Optional[str] = None
    next_topic: Optional[str] = None
    next_difficulty: Optional[str] = None
    final_report: Optional[dict] = None
    is_complete: bool
    skills_tested: list = []
    coverage_percentage: float = 0.0


class SessionListItem(BaseModel):
    id: str
    role: Optional[str] = None
    company: Optional[str] = None
    experience: Optional[str] = None
    status: str = "created"
    total_questions_asked: int = 0
    total_answers_given: int = 0
    coverage_percentage: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem]


class ExchangeItem(BaseModel):
    id: int
    session_id: str
    question_number: int
    question: str
    answer: Optional[str] = None
    feedback: Optional[str] = None
    score: Optional[int] = None
    action: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    timestamp: Optional[str] = None
    token_count: int = 0
    latency_ms: int = 0


class SessionDetailResponse(BaseModel):
    session: dict
    exchanges: list[ExchangeItem]


class InterviewReportResponse(BaseModel):
    session_id: str
    role: str
    company: str
    experience: str
    status: str
    total_questions: int
    total_answers: int
    duration_seconds: Optional[int] = None
    skills_tested: list = []
    skills_not_tested: list = []
    coverage_percentage: float = 0.0
    report: dict
