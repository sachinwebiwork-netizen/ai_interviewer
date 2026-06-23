import re
from huggingface_hub import InferenceClient
from core.config import settings

class AIInterviewerService:
    def __init__(self):
        self.model_id = "mistralai/Mistral-7B-Instruct-v0.3"
        self.client = InferenceClient(token=settings.HF_TOKEN)

    def build_prompt(self, role, experience, jd_company, jd_skills, resume_skills, resume_projects, user_turn):
        resume_project_str = resume_projects[0] if resume_projects else "N/A"
        system = (
            f"You are a strict technical interviewer.\\n"
            f"Role: {role} | Experience: {experience}\\n"
            f"Company: {jd_company}\\n"
            f"JD Skills: {', '.join(jd_skills)}\\n"
            f"Resume Skills: {', '.join(resume_skills[:6])}\\n"
            f"Resume Project: {resume_project_str}\\n"
        )
        return f"<s>[INST] {system}\\n\\n{user_turn} [/INST]"

    def _call_hf_api(self, model_id, prompt, max_new_tokens=200, temperature=0.8):
        try:
            # text_generation returns the generated string
            response = self.client.text_generation(
                prompt,
                model=model_id,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True if temperature > 0 else False,
                repetition_penalty=1.1,
                return_full_text=False
            )
            return response.strip()
        except Exception as e:
            print(f"Hugging Face API Error: {e}")
            return f"Error: {e}"

    def get_question(self, q_num, num_questions, role, experience, jd_skills, jd_company, resume_skills, resume_projects, history, last_action):
        user_turn = f"""
You are conducting a real technical interview.

Role: {role}
Experience: {experience}
JD Skills: {', '.join(jd_skills)}

Interview History:
{history}

Current Question Number: {q_num}
Previous Action: {last_action}

Rules:
1. Total interview questions = {num_questions}
2. Never ask more than {num_questions} questions.
3. FOLLOW_UP: Ask clarification on SAME topic.
4. DEEP_DIVE: Ask advanced production-level question on SAME topic.
5. NEXT_TOPIC: Move to a DIFFERENT topic.
6. If candidate clearly does not know the topic: Move to NEXT_TOPIC.
7. Never repeat question/topic/skill.
8. Ask only ONE question.
9. No score. No feedback. No action text.

Output: Question only.
"""
        prompt = self.build_prompt(role, experience, jd_company, jd_skills, resume_skills, resume_projects, user_turn)
        return self._call_hf_api(self.model_id, prompt, max_new_tokens=120, temperature=0.8)

    def get_feedback(self, role, experience, jd_company, jd_skills, resume_skills, resume_projects, question, answer):
        user_turn = f"""
Question: {question}
Candidate Answer: {answer}

You are evaluating a technical interview answer.

Rules:
1. If candidate says "I don't know" / "no idea" / "never worked on this" / "not sure" / "skip" / "cannot answer":
   Feedback: Candidate does not know this topic.
   Score: 0/10
   Action: NEXT_TOPIC
2. Weak answer: Score 1-4
3. Partial answer: Score 5-7
4. Strong answer: Score 8-10
5. FOLLOW_UP: partial knowledge shown
6. DEEP_DIVE: strong knowledge shown
7. NEXT_TOPIC: no knowledge OR topic sufficiently covered

Output exactly:
Feedback: <2 sentences>
Score: X/10
Action: FOLLOW_UP or DEEP_DIVE or NEXT_TOPIC
"""
        prompt = self.build_prompt(role, experience, jd_company, jd_skills, resume_skills, resume_projects, user_turn)
        fb_text = self._call_hf_api(self.model_id, prompt, max_new_tokens=150, temperature=0.1)
        
        m_score = re.search(r'Score:\s*(\d+)/10', fb_text, re.IGNORECASE)
        score = int(m_score.group(1)) if m_score else 0
        
        action = "NEXT_TOPIC"
        t_up = fb_text.upper()
        if "DEEP_DIVE" in t_up: action = "DEEP_DIVE"
        elif "FOLLOW_UP" in t_up: action = "FOLLOW_UP"
        
        return {
            "feedback": fb_text,
            "score": score,
            "action": action
        }

    def generate_final_report(self, role, experience, jd_company, jd_skills, resume_skills, qa_summary, avg_score):
        prompt = (
            f"<s>[INST] You are a senior technical recruiter writing a hiring report.\\n\\n"
            f"Role: {role}\\nExperience Required: {experience}\\nCompany: {jd_company}\\n"
            f"JD Skills: {', '.join(jd_skills)}\\nResume Skills: {', '.join(resume_skills[:6])}\\n\\n"
            f"Interview Transcript:\\n{qa_summary}\\nAverage Score: {avg_score}/10\\n\\n"
            f"Write a hiring report in this EXACT format:\\n\\n"
            f"Overall Performance: [Excellent/Good/Average/Below Average/Poor]\\n"
            f"Technical Score: {avg_score}/10\\n"
            f"Communication: [Excellent/Good/Average/Poor]\\n"
            f"Strengths: [2-3 specific strengths]\\n"
            f"Weaknesses: [1-2 specific gaps]\\n"
            f"JD Match: [High/Medium/Low] - [reason]\\n"
            f"Hiring Decision: [Hire/Consider/Reject]\\n"
            f"Reason: [2 sentences]\\n[/INST]"
        )
        return self._call_hf_api(self.model_id, prompt, max_new_tokens=350, temperature=0.7)

ai_service = AIInterviewerService()
