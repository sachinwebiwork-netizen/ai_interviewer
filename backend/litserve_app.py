import litserve as ls
from services.ai_service import ai_service

class InterviewLitAPI(ls.LitAPI):
    def setup(self, device):
        self.service = ai_service

    def decode_request(self, request):
        return request

    def predict(self, req):
        if req.get("action") == "question":
            return self.service.get_question(
                q_num=req["q_num"],
                num_questions=req["num_questions"],
                role=req["role"],
                experience=req["experience"],
                jd_skills=req["jd_skills"],
                jd_company=req["jd_company"],
                resume_skills=req["resume_skills"],
                resume_projects=req["resume_projects"],
                history=req.get("history", ""),
                last_action=req.get("last_action", "")
            )
        elif req.get("action") == "feedback":
            result = self.service.get_feedback(
                role=req["role"],
                experience=req["experience"],
                jd_company=req["jd_company"],
                jd_skills=req["jd_skills"],
                resume_skills=req["resume_skills"],
                resume_projects=req.get("resume_projects", []),
                question=req["question"],
                answer=req["answer"]
            )
            return result
        elif req.get("action") == "report":
            return self.service.generate_final_report(
                role=req["role"],
                experience=req["experience"],
                jd_company=req["jd_company"],
                jd_skills=req["jd_skills"],
                resume_skills=req["resume_skills"],
                qa_summary=req["qa_summary"],
                avg_score=req["avg_score"]
            )
        return {"error": "Unknown action"}

if __name__ == "__main__":
    api = InterviewLitAPI()
    server = ls.LitServer(api, accelerator="cpu")
    server.run(port=8000)
