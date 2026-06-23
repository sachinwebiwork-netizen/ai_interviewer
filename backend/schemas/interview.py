from pydantic import BaseModel
from typing import List, Optional

class InterviewStartRequest(BaseModel):
    num_questions: int = 5
    session_id: str

class AnswerRequest(BaseModel):
    session_id: str
    q_num: int
    num_questions: int
    answer: str
    question: str
    last_action: str

class FeedbackResponse(BaseModel):
    feedback: str
    score: int
    action: str

class FinalReportRequest(BaseModel):
    session_id: str
