from pydantic import BaseModel
from typing import Optional

class StartInterviewRequest(BaseModel):
    session_id: str
    num_questions: int = 5

class StartInterviewResponse(BaseModel):
    session_id: str
    question: str

class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str

class AnswerResponse(BaseModel):
    session_id: str
    q_num: int
    feedback: str
    score: int
    action: str
    next_question: Optional[str] = None
    final_report: Optional[str] = None
    is_complete: bool
