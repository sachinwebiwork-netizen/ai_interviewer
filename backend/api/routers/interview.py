from fastapi import APIRouter, HTTPException
from schemas.interview import StartInterviewRequest, StartInterviewResponse, AnswerRequest, AnswerResponse
from services.ai_service import ai_service
from db.supabase_client import get_session, update_session_history, update_session_field, list_sessions, delete_session
from pydantic import BaseModel
from typing import List, Optional

class SessionListItem(BaseModel):
    id: str
    role: Optional[str] = None
    experience: Optional[str] = None
    jd_company: Optional[str] = None
    created_at: Optional[str] = None
    q_count: int = 0

class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]

router = APIRouter(prefix="/interview", tags=["Interview"])

def build_history_string(history_list):
    history_str = ""
    for i, item in enumerate(history_list):
        history_str += f"\nQuestion {i+1}: {item.get('question')}"
        if 'answer' in item:
            history_str += f"\nAnswer {i+1}: {item.get('answer')}"
        if 'action' in item:
            history_str += f"\nAction {i+1}: {item.get('action')}"
        history_str += "\n"
    return history_str

@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(req: StartInterviewRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        update_session_field(req.session_id, "num_questions", req.num_questions)

        question = ai_service.get_question(
            q_num=1,
            num_questions=req.num_questions,
            role=session["role"],
            experience=session["experience"],
            jd_skills=session["jd_skills"],
            jd_company=session["jd_company"],
            resume_skills=session["resume_skills"],
            resume_projects=session["resume_projects"],
            history="",
            last_action=""
        )
        return StartInterviewResponse(
            session_id=req.session_id,
            question=question
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/answer", response_model=AnswerResponse)
async def answer_question(req: AnswerRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        history = session.get("history", [])
        num_questions = session.get("num_questions", 5)
        q_num = len(history) + 1

        feedback_data = ai_service.get_feedback(
            role=session["role"],
            experience=session["experience"],
            jd_company=session["jd_company"],
            jd_skills=session["jd_skills"],
            resume_skills=session["resume_skills"],
            resume_projects=session["resume_projects"],
            question=req.question,
            answer=req.answer
        )

        new_entry = {
            "question": req.question,
            "answer": req.answer,
            "feedback": feedback_data["feedback"],
            "score": feedback_data["score"],
            "action": feedback_data["action"]
        }
        update_session_history(req.session_id, new_entry)

        if q_num >= num_questions:
            qa_summary = ""
            total_score = 0
            updated_history = history + [new_entry]
            for i, item in enumerate(updated_history):
                qa_summary += f"Q{i+1}: {item['question']}\nAnswer: {item.get('answer', '')[:150]}\nScore: {item.get('score', 0)}/10 | Action: {item.get('action', '')}\n\n"
                total_score += item.get('score', 0)
            avg_score = round(total_score / len(updated_history), 1) if updated_history else 0

            report = ai_service.generate_final_report(
                role=session["role"],
                experience=session["experience"],
                jd_company=session["jd_company"],
                jd_skills=session["jd_skills"],
                resume_skills=session["resume_skills"],
                qa_summary=qa_summary,
                avg_score=avg_score
            )
            return AnswerResponse(
                session_id=req.session_id,
                q_num=q_num,
                feedback=feedback_data["feedback"],
                score=feedback_data["score"],
                action=feedback_data["action"],
                final_report=report,
                is_complete=True
            )
        else:
            last_action = feedback_data["action"]
            history_str = build_history_string(history + [new_entry])

            next_question = ai_service.get_question(
                q_num=q_num + 1,
                num_questions=num_questions,
                role=session["role"],
                experience=session["experience"],
                jd_skills=session["jd_skills"],
                jd_company=session["jd_company"],
                resume_skills=session["resume_skills"],
                resume_projects=session["resume_projects"],
                history=history_str,
                last_action=last_action
            )
            return AnswerResponse(
                session_id=req.session_id,
                q_num=q_num,
                feedback=feedback_data["feedback"],
                score=feedback_data["score"],
                action=feedback_data["action"],
                next_question=next_question,
                is_complete=False
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions():
    try:
        rows = list_sessions()
        sessions = []
        for r in rows:
            r["created_at"] = str(r["created_at"]) if r.get("created_at") else None
            sessions.append(SessionListItem(**r))
        return SessionListResponse(sessions=sessions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str):
    try:
        deleted = delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {"message": "Session deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
