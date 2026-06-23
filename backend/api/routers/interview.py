from fastapi import APIRouter, HTTPException
from schemas.interview import AnswerRequest, FeedbackResponse, FinalReportRequest
from services.ai_service import ai_service
from db.supabase_client import get_session, update_session_history

router = APIRouter(prefix="/interview", tags=["Interview"])

def build_history_string(history_list):
    history_str = ""
    for i, item in enumerate(history_list):
        history_str += f"\\nQuestion {i+1}: {item.get('question')}"
        if 'answer' in item:
            history_str += f"\\nAnswer {i+1}: {item.get('answer')}"
        if 'action' in item:
            history_str += f"\\nAction {i+1}: {item.get('action')}"
        history_str += "\\n"
    return history_str

@router.post("/question")
async def generate_question(req: AnswerRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
            
        history_str = build_history_string(session.get("history", []))

        question = ai_service.get_question(
            q_num=req.q_num,
            num_questions=req.num_questions,
            role=session["role"],
            experience=session["experience"],
            jd_skills=session["jd_skills"],
            jd_company=session["jd_company"],
            resume_skills=session["resume_skills"],
            resume_projects=session["resume_projects"],
            history=history_str,
            last_action=req.last_action
        )
        return {"question": question}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback", response_model=FeedbackResponse)
async def generate_feedback(req: AnswerRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

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
        
        # Save to history
        new_entry = {
            "question": req.question,
            "answer": req.answer,
            "feedback": feedback_data["feedback"],
            "score": feedback_data["score"],
            "action": feedback_data["action"]
        }
        update_session_history(req.session_id, new_entry)

        return FeedbackResponse(
            feedback=feedback_data["feedback"],
            score=feedback_data["score"],
            action=feedback_data["action"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/report")
async def generate_report(req: FinalReportRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
            
        history_list = session.get("history", [])
        qa_summary = ""
        total_score = 0
        for i, item in enumerate(history_list):
            qa_summary += f"Q{i+1}: {item['question']}\\nAnswer: {item.get('answer', '')[:150]}\\nScore: {item.get('score', 0)}/10 | Action: {item.get('action', '')}\\n\\n"
            total_score += item.get('score', 0)
            
        avg_score = round(total_score / len(history_list), 1) if history_list else 0

        report = ai_service.generate_final_report(
            role=session["role"],
            experience=session["experience"],
            jd_company=session["jd_company"],
            jd_skills=session["jd_skills"],
            resume_skills=session["resume_skills"],
            qa_summary=qa_summary,
            avg_score=avg_score
        )
        return {"report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
