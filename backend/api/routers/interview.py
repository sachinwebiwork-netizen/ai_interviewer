import logging
import datetime

from fastapi import APIRouter, HTTPException
from core.config import settings

from schemas.interview import (
    StartInterviewRequest, StartInterviewResponse,
    AnswerRequest, AnswerResponse,
    SessionListResponse, SessionListItem,
    SessionDetailResponse, ExchangeItem,
    InterviewReportResponse,
)
from db.supabase_client import (
    get_session, update_session, get_exchanges, add_exchange,
    update_session_after_exchange, list_sessions, delete_session,
    get_session_report_data, complete_session,
)
from services.ai_service import (
    InterviewState, generate_first_question, generate_next_question,
    evaluate_answer, generate_final_report, should_end_interview,
    _normalize_skill,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["Interview"])


def _build_state(session: dict) -> InterviewState:
    return InterviewState(
        role=session["role"],
        experience=session["experience"],
        company=session.get("company") or session.get("jd_company") or "",
        jd_skills=session.get("jd_skills", []),
        jd_required_skills=session.get("jd_required_skills", session.get("jd_skills", [])),
        jd_preferred_skills=session.get("jd_preferred_skills", []),
        jd_responsibilities=session.get("jd_responsibilities", []),
        jd_years_experience=session.get("jd_years_experience", ""),
        resume_skills=session.get("resume_skills", []),
        resume_projects=session.get("resume_projects", []),
    )


def _recover_state_from_history(session: dict, state: InterviewState):
    exchanges = get_exchanges(session["id"])
    state.tested_skills = session.get("tested_skills") or []
    state.untested_skills = session.get("untested_skills") or list(state.jd_skills)
    state.coverage_percentage = session.get("coverage_percentage") or 0.0
    prev_topic = ""
    for ex in exchanges:
        topic = ex.get("topic", "")
        if topic:
            state.skill_depth_count[topic] = state.skill_depth_count.get(topic, 0) + 1
            if topic == prev_topic:
                state.consecutive_topic_count += 1
            else:
                state.consecutive_topic_count = 1
                prev_topic = topic
        score = ex.get("score")
        if score is not None and topic:
            state.mark_skill_tested(topic, score=score)
    if exchanges:
        state.last_topic = exchanges[-1].get("topic", "")
        state.current_topic = state.last_topic
    return exchanges


@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(req: StartInterviewRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        if session.get("status") not in ("created", "in_progress"):
            raise HTTPException(
                status_code=400,
                detail=f"Session is already {session['status']}.",
            )

        state = _build_state(session)
        exchanges = _recover_state_from_history(session, state)

        if exchanges:
            last = exchanges[-1]
            q_num = len(exchanges) + 1
            result = generate_next_question(
                state=state,
                history=exchanges,
                q_num=q_num,
                total_q=req.num_questions,
                last_action=last.get("action", "NEXT_TOPIC"),
                last_feedback=last.get("feedback", ""),
                last_topic=last.get("topic", "general"),
            )
        else:
            q_num = 1
            result = generate_first_question(state=state, total_q=req.num_questions)
            update_session(
                req.session_id,
                status="in_progress",
                start_time=datetime.datetime.utcnow(),
                num_questions=req.num_questions,
            )

        logger.info(
            "Interview started", extra={
                "session_id": req.session_id,
                "q_num": q_num,
                "topic": result.get("topic", "general"),
            }
        )

        return StartInterviewResponse(
            session_id=req.session_id,
            question=result["question"],
            topic=result.get("topic", "general"),
            difficulty=result.get("difficulty", "easy"),
            question_number=q_num,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Start interview failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer", response_model=AnswerResponse)
async def answer_question(req: AnswerRequest):
    try:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        if session.get("status") == "completed":
            raise HTTPException(status_code=400, detail="Interview is already completed.")

        state = _build_state(session)
        exchanges = _recover_state_from_history(session, state)

        q_num = len(exchanges) + 1
        topic = req.topic or "general"
        difficulty = req.difficulty or "medium"
        num_questions = session.get("num_questions", settings.MAX_QUESTIONS_DEFAULT)

        eval_result = evaluate_answer(
            state=state,
            question=req.question,
            answer=req.answer,
            topic=topic,
            difficulty=difficulty,
            q_num=q_num,
            total_q=num_questions,
            history=exchanges,
        )

        skills_demonstrated = eval_result.get("skills_demonstrated", [])
        if topic not in skills_demonstrated:
            skills_demonstrated.append(topic)
        sub_skills = eval_result.get("sub_skills_demonstrated", [])
        required = set(state._denominator_skills)
        for skill in skills_demonstrated:
            normalized = _normalize_skill(skill)
            if normalized in required:
                state.mark_skill_tested(normalized, sub_skills=sub_skills, score=eval_result["score"])
        depth_topic = state.last_topic or topic
        state.skill_depth_count[depth_topic] = state.skill_depth_count.get(depth_topic, 0) + 1

        if topic == state.current_topic:
            state.consecutive_topic_count += 1
        else:
            state.consecutive_topic_count = 1
        state.current_topic = topic

        add_exchange(
            session_id=req.session_id,
            question_number=q_num,
            question=req.question,
            answer=req.answer,
            feedback=eval_result["feedback"],
            score=eval_result["score"],
            action=eval_result["action"],
            topic=topic,
            difficulty=difficulty,
            token_count=eval_result.get("tokens", 0),
            latency_ms=eval_result.get("latency_ms", 0),
        )

        update_session_after_exchange(
            session_id=req.session_id,
            tested_skills=state.tested_skills,
            untested_skills=state.untested_skills,
            coverage_pct=state.coverage_percentage,
            current_topic=topic,
        )

        exchanges = get_exchanges(req.session_id)

        should_end, end_reason = should_end_interview(
            state=state,
            q_num=q_num,
            total_q=num_questions,
            last_action=eval_result["action"],
            history=exchanges,
        )

        if should_end:
            report = generate_final_report(state=state, history=exchanges)
            complete_session(req.session_id, final_report=report)

            logger.info(
                "Interview completed", extra={
                    "session_id": req.session_id,
                    "q_num": q_num,
                    "coverage": state.coverage_percentage,
                    "reason": end_reason,
                }
            )

            return AnswerResponse(
                session_id=req.session_id,
                question_number=q_num,
                question=req.question,
                topic=topic,
                difficulty=difficulty,
                feedback=eval_result["feedback"],
                score=eval_result["score"],
                action=eval_result["action"],
                final_report=report,
                is_complete=True,
                skills_tested=state.tested_skills,
                coverage_percentage=state.coverage_percentage,
            )

        return AnswerResponse(
            session_id=req.session_id,
            question_number=q_num,
            question=req.question,
            topic=topic,
            difficulty=difficulty,
            feedback=eval_result["feedback"],
            score=eval_result["score"],
            action=eval_result["action"],
            next_question=eval_result.get("next_question"),
            next_topic=eval_result.get("next_topic", "general"),
            next_difficulty=eval_result.get("next_difficulty", "medium"),
            is_complete=False,
            skills_tested=state.tested_skills,
            coverage_percentage=state.coverage_percentage,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Answer processing failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions():
    try:
        rows = list_sessions()
        sessions = [SessionListItem(**r) for r in rows]
        return SessionListResponse(sessions=sessions)
    except Exception as e:
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str):
    try:
        data = get_session_report_data(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found.")
        exchanges = []
        for ex in data["exchanges"]:
            ex["timestamp"] = str(ex["timestamp"]) if ex.get("timestamp") else None
            exchanges.append(ExchangeItem(**ex))
        return SessionDetailResponse(session=data["session"], exchanges=exchanges)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get session detail")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/report", response_model=InterviewReportResponse)
async def get_session_report(session_id: str):
    try:
        data = get_session_report_data(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found.")
        session = data["session"]
        report = session.get("final_report")
        if not report:
            return InterviewReportResponse(
                session_id=session_id,
                role=session.get("role", ""),
                company=session.get("company", ""),
                experience=session.get("experience", ""),
                status=session.get("status", "created"),
                total_questions=session.get("total_questions_asked", 0),
                total_answers=session.get("total_answers_given", 0),
                duration_seconds=session.get("duration_seconds"),
                skills_tested=session.get("tested_skills", []),
                skills_not_tested=session.get("untested_skills", []),
                coverage_percentage=session.get("coverage_percentage", 0.0),
                report={
                    "candidate_level": session.get("experience", ""),
                    "hire_recommendation": "N/A",
                    "strengths": [],
                    "weaknesses": [],
                    "skills_tested": session.get("tested_skills", []),
                    "skills_not_tested": session.get("untested_skills", []),
                    "knowledge_gaps": [],
                    "coverage_percentage": f"{session.get('coverage_percentage', 0)}%",
                    "interview_summary": "Interview not yet completed.",
                },
            )
        return InterviewReportResponse(
            session_id=session_id,
            role=session.get("role", ""),
            company=session.get("company", ""),
            experience=session.get("experience", ""),
            status=session.get("status", "created"),
            total_questions=session.get("total_questions_asked", 0),
            total_answers=session.get("total_answers_given", 0),
            duration_seconds=session.get("duration_seconds"),
            skills_tested=report.get("skills_tested", session.get("tested_skills", [])),
            skills_not_tested=report.get("skills_not_tested", session.get("untested_skills", [])),
            coverage_percentage=session.get("coverage_percentage", 0.0),
            report=report,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get session report")
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
        logger.exception("Failed to delete session")
        raise HTTPException(status_code=500, detail=str(e))
