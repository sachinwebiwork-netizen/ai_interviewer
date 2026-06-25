import os
import json
import litserve as ls
from services.ai_service import InterviewState, generate_first_question, generate_next_question, evaluate_answer, generate_final_report


class InterviewLitAPI(ls.LitAPI):
    def setup(self, device):
        pass

    def decode_request(self, request):
        return request

    def predict(self, req):
        action = req.get("action")

        if action == "start":
            state = InterviewState(
                role=req["role"],
                experience=req["experience"],
                company=req.get("company", ""),
                jd_skills=req.get("jd_skills", []),
                jd_required_skills=req.get("jd_required_skills", req.get("jd_skills", [])),
                jd_preferred_skills=req.get("jd_preferred_skills", []),
                jd_responsibilities=req.get("jd_responsibilities", []),
                jd_years_experience=req.get("jd_years_experience", ""),
                resume_skills=req.get("resume_skills", []),
                resume_projects=req.get("resume_projects", []),
            )
            total_q = req.get("num_questions") or req.get("total_q") or 1
            result = generate_first_question(state, total_q=total_q)
            return result

        elif action == "question":
            state = InterviewState(
                role=req["role"],
                experience=req["experience"],
                company=req.get("company", ""),
                jd_skills=req.get("jd_skills", []),
                jd_required_skills=req.get("jd_required_skills", req.get("jd_skills", [])),
                jd_preferred_skills=req.get("jd_preferred_skills", []),
                jd_responsibilities=req.get("jd_responsibilities", []),
                jd_years_experience=req.get("jd_years_experience", ""),
                resume_skills=req.get("resume_skills", []),
                resume_projects=req.get("resume_projects", []),
            )
            result = generate_next_question(
                state=state,
                history=req.get("history", []),
                q_num=req["q_num"],
                total_q=req["total_q"],
                last_action=req.get("last_action", ""),
                last_feedback=req.get("last_feedback", ""),
                last_topic=req.get("last_topic", "general"),
            )
            return result

        elif action == "feedback":
            state = InterviewState(
                role=req["role"],
                experience=req["experience"],
                company=req.get("company", ""),
                jd_skills=req.get("jd_skills", []),
                jd_required_skills=req.get("jd_required_skills", req.get("jd_skills", [])),
                jd_preferred_skills=req.get("jd_preferred_skills", []),
                jd_responsibilities=req.get("jd_responsibilities", []),
                jd_years_experience=req.get("jd_years_experience", ""),
                resume_skills=req.get("resume_skills", []),
                resume_projects=req.get("resume_projects", []),
            )
            return evaluate_answer(
                state=state,
                question=req["question"],
                answer=req["answer"],
                topic=req.get("topic", "general"),
                difficulty=req.get("difficulty", "medium"),
            )

        elif action == "report":
            state = InterviewState(
                role=req["role"],
                experience=req["experience"],
                company=req.get("company", ""),
                jd_skills=req.get("jd_skills", []),
                jd_required_skills=req.get("jd_required_skills", req.get("jd_skills", [])),
                jd_preferred_skills=req.get("jd_preferred_skills", []),
                jd_responsibilities=req.get("jd_responsibilities", []),
                jd_years_experience=req.get("jd_years_experience", ""),
                resume_skills=req.get("resume_skills", []),
                resume_projects=req.get("resume_projects", []),
            )
            for s in req.get("skills_tested", []):
                state.mark_skill_tested(s)
            return generate_final_report(state=state, history=req.get("history", []))

        return {"error": f"Unknown action: {action}"}


if __name__ == "__main__":
    api = InterviewLitAPI()
    # Use GPU by default on Lightning; allow override via env var
    accelerator = os.getenv("LIGHTNING_ACCELERATOR", "gpu")
    port = int(os.getenv("PORT", 8000))
    server = ls.LitServer(api, accelerator=accelerator)
    server.run(port=port)
