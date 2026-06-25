import json
import logging
import re
import time
import random
from typing import Optional

import requests
from huggingface_hub import InferenceClient
from core.config import settings

logger = logging.getLogger(__name__)

DIFFICULTY_ORDER = ["easy", "medium", "hard", "system_design"]


def parse_json_output(text: str) -> Optional[dict]:
    text = text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class LLMClient:
    def __init__(self):
        self.provider = (settings.INFERENCE_PROVIDER or "hf").lower()
        self.primary_model = settings.HF_MODEL
        self.fallback_model = settings.HF_FALLBACK_MODEL
        self.primary_client = None
        self.fallback_client = None
        self.local_url = settings.LOCAL_INFERENCE_URL
        self.local_token = settings.LOCAL_INFERENCE_TOKEN

        if self.provider == "hf":
            if settings.HF_TOKEN:
                self.primary_client = InferenceClient(token=settings.HF_TOKEN)
            if settings.HF_FALLBACK_TOKEN:
                self.fallback_client = InferenceClient(token=settings.HF_FALLBACK_TOKEN)
            elif settings.HF_TOKEN:
                self.fallback_client = InferenceClient(token=settings.HF_TOKEN)
        elif self.provider == "local":
            if not self.local_url:
                logger.warning("LOCAL_INFERENCE_URL not set; local inference will fail.")
        else:
            logger.warning(f"Unknown INFERENCE_PROVIDER={self.provider}; falling back to HF")
            if settings.HF_TOKEN:
                self.primary_client = InferenceClient(token=settings.HF_TOKEN)
            if settings.HF_FALLBACK_TOKEN:
                self.fallback_client = InferenceClient(token=settings.HF_FALLBACK_TOKEN)
            elif settings.HF_TOKEN:
                self.fallback_client = InferenceClient(token=settings.HF_TOKEN)

    def _call_local(self, messages, max_tokens, temperature):
        if not self.local_url:
            raise RuntimeError("LOCAL_INFERENCE_URL not configured")
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Content-Type": "application/json"}
        if self.local_token:
            headers["Authorization"] = f"Bearer {self.local_token}"

        response = requests.post(
            self.local_url,
            json=payload,
            headers=headers,
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get("choices"):
            return data["choices"][0]["message"]["content"].strip()
        if isinstance(data, dict) and "content" in data:
            return str(data["content"]).strip()
        raise ValueError("Unexpected local inference response format")

    def call(self, messages, max_tokens=300, temperature=0.7, retries=None):
        if retries is None:
            retries = settings.MAX_RETRIES
        last_error = None

        if self.provider == "local":
            for attempt in range(retries):
                try:
                    start = time.time()
                    content = self._call_local(messages, max_tokens, temperature)
                    latency = int((time.time() - start) * 1000)
                    logger.info(
                        "LLM call", extra={
                            "model": "local",
                            "latency_ms": latency,
                            "tokens": 0,
                            "attempt": attempt + 1,
                        }
                    )
                    return {
                        "content": content,
                        "tokens": 0,
                        "latency_ms": latency,
                        "model": "local",
                    }
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Local inference failed (attempt={attempt + 1}): {e}"
                    )
                    if attempt < retries - 1:
                        delay = settings.RETRY_DELAY_MS / 1000 * (2 ** attempt)
                        time.sleep(delay)
                    continue
            logger.warning("Local inference failed after retries.")
            if self.primary_client:
                logger.info("Falling back to Hugging Face inference")
            else:
                logger.error(f"All LLM calls failed: {last_error}")
                return {
                    "content": f"Error: Unable to generate response after {retries} retries.",
                    "tokens": 0,
                    "latency_ms": 0,
                    "model": "none",
                }

        models_to_try = [(self.primary_model, self.primary_client)]
        if self.fallback_client and self.fallback_model != self.primary_model:
            models_to_try.append((self.fallback_model, self.fallback_client))

        for model_id, client in models_to_try:
            if client is None:
                continue
            for attempt in range(retries):
                try:
                    start = time.time()
                    response = client.chat_completion(
                        messages=messages,
                        model=model_id,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    latency = int((time.time() - start) * 1000)
                    content = response.choices[0].message.content.strip()
                    usage = getattr(response, 'usage', None)
                    token_count = usage.total_tokens if usage else 0
                    logger.info(
                        "LLM call", extra={
                            "model": model_id,
                            "latency_ms": latency,
                            "tokens": token_count,
                            "attempt": attempt + 1,
                        }
                    )
                    return {
                        "content": content,
                        "tokens": token_count,
                        "latency_ms": latency,
                        "model": model_id,
                    }
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(
                        f"LLM call failed (model={model_id}, attempt={attempt + 1}): {e}"
                    )
                    if "model_not_supported" in error_str:
                        logger.warning(f"Model {model_id} not supported, skipping fallback")
                        break
                    if attempt < retries - 1:
                        delay = settings.RETRY_DELAY_MS / 1000 * (2 ** attempt)
                        time.sleep(delay)
                    continue
            if last_error and models_to_try.index((model_id, client)) < len(models_to_try) - 1:
                logger.info(f"Falling back to {models_to_try[-1][0]}")
                continue

        logger.error(f"All LLM calls failed: {last_error}")
        return {
            "content": f"Error: Unable to generate response after {retries} retries.",
            "tokens": 0,
            "latency_ms": 0,
            "model": "none",
        }


llm_client = LLMClient()


SKILL_NORMALIZE = re.compile(r'[^a-z0-9_+#.]+')
SKILL_STOP_WORDS = {"years", "year", "experience", "skill", "skills", "working", "knowledge",
                    "strong", "good", "basic", "advanced", "proficient", "expert",
                    "practical", "handson", "hand", "extensive", "solid", "proven",
                    "demonstrated", "including", "related", "using", "mandatory",
                    "required", "preferred", "nice", "plus", "etc", "like"}


def _normalize_skill(skill: str) -> str:
    skill = skill.strip().lower()
    skill = re.sub(r'^[\d\s\+,\.]+', '', skill)
    skill = SKILL_NORMALIZE.sub(' ', skill).strip()
    tokens = skill.split()
    tokens = [t for t in tokens if t not in SKILL_STOP_WORDS and len(t) >= 2]
    skill = '_'.join(tokens) if tokens else ""
    if len(skill) < 2:
        return ""
    return skill


class InterviewState:
    def __init__(self, role, experience, company, jd_skills,
                 jd_required_skills, jd_preferred_skills,
                 jd_responsibilities, jd_years_experience,
                 resume_skills, resume_projects):
        self.role = role
        self.experience = experience
        self.company = company
        self.jd_skills = jd_skills
        self.jd_required_skills = jd_required_skills
        self.jd_preferred_skills = jd_preferred_skills
        self.jd_responsibilities = jd_responsibilities
        self.jd_years_experience = jd_years_experience
        self.resume_skills = resume_skills
        self.resume_projects = resume_projects
        self.tested_skills = []
        self.untested_skills = [_normalize_skill(s) for s in jd_required_skills if _normalize_skill(s)]
        self.coverage_percentage = 0.0
        self.difficulty_level = "easy"
        self._denominator_skills = list(self.untested_skills)
        self.sub_skills_tested = {}
        self.skill_depth_count = {}
        self.skill_evidence = {}
        self.skill_confidence = {}
        self.partially_tested_skills = []
        self.consecutive_topic_count = 0
        self.current_topic = ""
        self.last_topic = ""

    def get_difficulty_for_question(self, q_num, total_q):
        if total_q <= 4:
            if q_num <= 1:
                return "easy"
            elif q_num <= 3:
                return "medium"
            else:
                return "hard"
        ratio = q_num / total_q
        if ratio <= 0.25:
            return "easy"
        elif ratio <= 0.5:
            return "medium"
        elif ratio <= 0.75:
            return "hard"
        else:
            return "system_design"

    def mark_skill_tested(self, skill, sub_skills=None, score=None):
        skill = _normalize_skill(skill)
        if not skill:
            return
        if skill in self.untested_skills:
            self.untested_skills.remove(skill)
        if skill not in self.tested_skills and skill in self._denominator_skills:
            self.tested_skills.append(skill)
        if sub_skills:
            existing = self.sub_skills_tested.setdefault(skill, [])
            for ss in sub_skills:
                ss = _normalize_skill(ss)
                if ss and ss not in existing:
                    existing.append(ss)
        if score is not None:
            evidence = self.skill_evidence.setdefault(skill, {"scores": [], "count": 0})
            evidence["scores"].append(score)
            evidence["count"] += 1
            confidence = self.get_skill_confidence(skill)
            if confidence:
                self.skill_confidence[skill] = confidence
            if confidence in ("low", "medium"):
                if skill not in self.partially_tested_skills:
                    self.partially_tested_skills.append(skill)
            elif confidence == "high":
                if skill in self.partially_tested_skills:
                    self.partially_tested_skills.remove(skill)
        total = len(self._denominator_skills)
        if total > 0:
            raw = (len(self.tested_skills) / total) * 100
            self.coverage_percentage = round(min(raw, 100.0), 1)

    def is_sufficiently_tested(self, skill, min_score=7, min_questions=2):
        evidence = self.skill_evidence.get(_normalize_skill(skill))
        if not evidence or evidence["count"] < min_questions:
            return False
        avg = sum(evidence["scores"]) / evidence["count"]
        return avg >= min_score

    def get_next_untested_skill(self):
        for skill in self.untested_skills:
            return skill
        return None

    def get_skill_confidence(self, skill: str) -> str | None:
        skill = _normalize_skill(skill)
        if not skill or skill not in self.skill_evidence:
            return None
        evidence = self.skill_evidence[skill]
        if evidence["count"] == 0:
            return None
        avg = sum(evidence["scores"]) / evidence["count"]
        if avg >= 7 and evidence["count"] >= 2:
            return "high"
        elif avg >= 4:
            return "medium"
        else:
            return "low"

    def get_remaining_budget(self, q_num: int, total_q: int) -> int:
        return total_q - q_num

    def get_max_depth_for_budget(self, q_num: int, total_q: int, untested_count: int) -> int:
        remaining = self.get_remaining_budget(q_num, total_q)
        if untested_count == 0:
            return 3
        ratio = remaining / untested_count
        if ratio >= 3:
            return 3
        elif ratio >= 1.5:
            return 2
        else:
            return 1

    def get_interview_mode(self, q_num: int, total_q: int) -> str:
        remaining = self.get_remaining_budget(q_num, total_q)
        if total_q >= 15:
            return "DETAILED"
        elif total_q >= 10:
            return "BALANCED"
        else:
            return "BROAD"

    def get_difficulty_for_skill(self, skill: str, q_num: int, total_q: int) -> str:
        confidence = self.get_skill_confidence(skill)
        if confidence == "high":
            return "hard"
        elif confidence == "medium":
            return "medium"
        elif confidence == "low":
            return "easy"
        return self.get_difficulty_for_question(q_num, total_q)


def _normalize_question_text(q: str) -> str:
    """Lowercase + strip punctuation so near-identical questions are detected as duplicates."""
    return re.sub(r'[^a-z0-9 ]', '', (q or "").lower()).strip()


def _is_duplicate_question(question: str, asked_questions: list) -> bool:
    if not question:
        return False
    norm = _normalize_question_text(question)
    if not norm:
        return False
    for prev in asked_questions:
        if _normalize_question_text(prev) == norm:
            return True
    return False


def build_system_prompt(state: InterviewState) -> str:
    skills_str = str(state.jd_required_skills)
    preferred_str = str(state.jd_preferred_skills) if state.jd_preferred_skills else "[]"
    exp = state.experience or "Mid"
    base = f"Role:{state.role},Exp:{exp},Skills:{preferred_str},JD:{skills_str}"
    if state.resume_skills:
        base += f",ResumeSkills:{str(state.resume_skills[:10])}"
    if state.resume_projects:
        base += f",Projects:{str(state.resume_projects[:3])}"
    return base


def generate_next_question(
    state: InterviewState,
    history: list,
    q_num: int,
    total_q: int,
    last_action: str,
    last_feedback: str,
    last_topic: str,
) -> dict:
    untested = state.get_next_untested_skill()
    next_topic_for_difficulty = untested or last_topic
    difficulty = state.get_difficulty_for_skill(next_topic_for_difficulty, q_num, total_q)

    untested_count = len(state.untested_skills)

    # --- Two-phase strategy ---
    # Phase 1 (untested remain): strict round-robin — one question per skill, no deep-dives
    # Phase 2 (all tested): use remaining questions for depth

    if untested_count > 0:
        last_action = "NEXT_TOPIC"
        state.consecutive_topic_count = 0
    else:
        confidence = state.get_skill_confidence(last_topic)
        if confidence == "high" and last_action in ("DEEP_DIVE", "FOLLOW_UP"):
            last_action = "NEXT_TOPIC"
        elif last_action == "DEEP_DIVE" and state.consecutive_topic_count >= 2:
            last_action = "NEXT_TOPIC"

    if last_action == "NEXT_TOPIC":
        state.consecutive_topic_count = 0

    last_answer = ""
    if history:
        last_answer = history[-1].get("answer", "")[:300]

    forced_topic = None
    if untested:
        forced_topic = untested

    # All questions asked so far in this session — used to stop the model (and our
    # fallback templates) from repeating a question that was already asked.
    asked_questions = [h.get("question", "") for h in history if h.get("question")]

    resume_skill_names = ", ".join(state.resume_skills[:5]) if state.resume_skills else ""
    resume_project_desc = "; ".join(state.resume_projects[:2]) if state.resume_projects else ""

    action_desc = {
        "NEXT_TOPIC": f"Ask about '{forced_topic or last_topic}'. Transition naturally.",
        "DEEP_DIVE": f"Stay on '{last_topic}' but go deeper. Ask about tradeoffs or edge cases.",
        "FOLLOW_UP": f"Keep '{last_topic}' but ask a simpler clarifying question.",
        "CLARIFY": f"Ask a very basic question about '{last_topic}'.",
    }.get(last_action, f"Ask about '{forced_topic or last_topic}'.")

    user_content = (
        f"Question #{q_num} of {total_q}.\n"
        f"{action_desc}\n"
        f"Last answer: \"{last_answer}\"\n"
    )
    if asked_questions:
        # Keep only the most recent N to avoid bloating the prompt, but this is
        # almost always enough since repeats happen on consecutive/near turns.
        recent_asked = asked_questions[-8:]
        user_content += "\nQuestions already asked in this interview (DO NOT repeat or rephrase ANY of these):\n"
        for i, q in enumerate(recent_asked, 1):
            user_content += f"{i}. {q}\n"
        user_content += "Your new question must be worded differently and explore a different angle than all of the above.\n"
    if resume_skill_names:
        user_content += f"Resume: {resume_skill_names}\n"
    if resume_project_desc:
        user_content += f"Projects: {resume_project_desc}\n"
    user_content += (
        f"\nOUTPUT FORMAT (JSON only):\n"
        f"{{\n"
        f'  "question": "Your question (max 15 words, conversational)",\n'
        f'  "topic": "{forced_topic or last_topic or "general"}",\n'
        f'  "difficulty": "{difficulty}"\n'
        f"}}\n"
    )

    messages = [
        {"role": "system", "content": build_system_prompt(state)},
        {"role": "user", "content": user_content},
    ]

    result = llm_client.call(messages, max_tokens=250, temperature=0.8)
    content = result["content"]

    parsed = parse_json_output(content)
    final_topic = forced_topic or parsed.get("topic", untested or last_topic or "general") if parsed else (untested or last_topic or "general")

    if parsed and "question" in parsed and not _is_duplicate_question(parsed["question"], asked_questions):
        return {
            "question": parsed["question"],
            "topic": final_topic,
            "difficulty": parsed.get("difficulty", difficulty),
            "tokens": result["tokens"],
            "latency_ms": result["latency_ms"],
        }

    # The model echoed a question we already asked — give it one more explicit
    # chance with a stronger instruction and higher temperature before we fall
    # back to a template.
    if parsed and "question" in parsed and _is_duplicate_question(parsed["question"], asked_questions):
        logger.warning(
            "Duplicate question detected from LLM, retrying",
            extra={"topic": final_topic, "q_num": q_num},
        )
        retry_messages = messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": (
                "That question was already asked earlier in this interview. "
                "Ask a different question — different wording, different angle, same or related topic."
            )},
        ]
        retry_result = llm_client.call(retry_messages, max_tokens=250, temperature=0.9)
        retry_parsed = parse_json_output(retry_result["content"])
        if retry_parsed and "question" in retry_parsed and not _is_duplicate_question(retry_parsed["question"], asked_questions):
            return {
                "question": retry_parsed["question"],
                "topic": forced_topic or retry_parsed.get("topic", final_topic),
                "difficulty": retry_parsed.get("difficulty", difficulty),
                "tokens": result["tokens"] + retry_result["tokens"],
                "latency_ms": result["latency_ms"] + retry_result["latency_ms"],
            }

    question = content
    question = re.sub(r'^["\']+|["\']+$', '', question)
    question = re.sub(r'^(Question|Q):\s*', '', question, flags=re.IGNORECASE)
    topic_for_fallback = forced_topic or untested or last_topic or "general"
    # Filter garbage — error text, too-long content, or a repeat of something
    # already asked (e.g. when the LLM call itself failed and we'd otherwise
    # return the exact same static sentence every time).
    if (
        len(question) > 200
        or question.startswith("Error:")
        or "Unable to generate" in question
        or _is_duplicate_question(question, asked_questions)
    ):
        question = _fallback_question(topic_for_fallback, asked_questions, q_num)
    return {
        "question": question,
        "topic": forced_topic or untested or last_topic or "general",
        "difficulty": difficulty,
        "tokens": result["tokens"],
        "latency_ms": result["latency_ms"],
    }


def _parse_combined_output(content: str, default_topic: str, default_difficulty: str) -> dict:
    """Parse the model's combined response: feedback, score, action, then blank line, then next question."""
    result = {
        "feedback": "Evaluation completed.",
        "score": 5,
        "action": "NEXT_TOPIC",
        "skills_demonstrated": [default_topic],
        "sub_skills_demonstrated": [],
        "next_question": None,
        "next_topic": default_topic,
        "next_difficulty": default_difficulty,
    }

    # Try JSON first
    parsed = parse_json_output(content)
    if parsed:
        if "feedback" in parsed or "score" in parsed:
            result["feedback"] = parsed.get("feedback", result["feedback"])
            result["score"] = max(0, min(10, int(parsed.get("score", 5))))
            result["action"] = parsed.get("action", "NEXT_TOPIC")
            if "skills_demonstrated" in parsed:
                result["skills_demonstrated"] = parsed["skills_demonstrated"]
            if "sub_skills_demonstrated" in parsed:
                result["sub_skills_demonstrated"] = parsed["sub_skills_demonstrated"]
            if "next_question" in parsed:
                result["next_question"] = parsed["next_question"]
            if "next_topic" in parsed:
                result["next_topic"] = parsed["next_topic"]
            if "next_difficulty" in parsed:
                result["next_difficulty"] = parsed["next_difficulty"]
            return result

    # Non-JSON fallback: trained model format (Feedback/Score/Action then blank line then next question)
    lines = content.strip().split("\n")

    # Extract feedback, score, action from the top part
    feedback_parts = []
    score = 5
    action = "NEXT_TOPIC"
    question_start = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("feedback:"):
            fb = stripped.split(":", 1)[1].strip()
            if fb:
                feedback_parts.append(fb)
        elif lower.startswith("score:"):
            match = re.search(r'(\d+)/?10?', stripped)
            if match:
                score = max(0, min(10, int(match.group(1))))
        elif lower.startswith("action:"):
            action_part = stripped.split(":", 1)[1].strip()
            for a in ("NEXT_TOPIC", "DEEP_DIVE", "FOLLOW_UP", "CLARIFY"):
                if a in action_part.upper():
                    action = a
                    break
        elif stripped == "" and i > 0 and i < len(lines) - 1:
            question_start = i + 1
            break

    feedback = " ".join(feedback_parts).strip() or "Evaluation completed."

    # Get next question
    question_lines = [l.strip() for l in lines[question_start:] if l.strip()]
    next_question = " ".join(question_lines) if question_lines else None

    result["feedback"] = feedback[:500] if feedback != "Evaluation completed." else feedback
    result["score"] = score
    result["action"] = action
    result["next_question"] = next_question

    return result


def evaluate_answer(
    state: InterviewState,
    question: str,
    answer: str,
    topic: str,
    difficulty: str,
    q_num: int = None,
    total_q: int = None,
    history: list = None,
) -> dict:
    untested = state.get_next_untested_skill()

    skill_difficulty = state.get_difficulty_for_skill(topic, q_num or 0, total_q or 10)

    user_content = (
        f"Question: {question}\n"
        f"Candidate Answer: {answer}\n"
        f"Topic: {topic}\n"
        f"Expected Difficulty: {skill_difficulty}\n"
    )
    if untested:
        user_content += f"\nTransition naturally to '{untested}'.\n"
    elif len(state.jd_required_skills) > len(state.tested_skills):
        user_content += "\nAll uncovered skills: " + ", ".join(s for s in state.jd_required_skills if s not in state.tested_skills) + "\n"
    else:
        user_content += "\nAll skills covered.\n"

    messages = [
        {"role": "system", "content": build_system_prompt(state)},
        {"role": "user", "content": user_content},
    ]

    result = llm_client.call(messages, max_tokens=350, temperature=0.4)
    content = result["content"]
    logger.info("evaluate_answer raw output: %s", content[:300])

    parsed = _parse_combined_output(content, topic, difficulty)

    # Code enforcement: force topic if untested remain
    if untested:
        parsed["action"] = "NEXT_TOPIC"
        parsed["next_topic"] = untested

    # Alignment bonus: skill on resume + good score → small bump
    raw_score = parsed["score"]
    topic_normalized = _normalize_skill(topic)
    resume_normalized = {_normalize_skill(s) for s in state.resume_skills if _normalize_skill(s)}
    if topic_normalized in resume_normalized and raw_score >= 7:
        parsed["score"] = min(10, raw_score + 1)
    elif topic_normalized not in resume_normalized and raw_score >= 8:
        parsed["score"] = min(10, raw_score + 0.5)

    if not parsed.get("next_question") or _is_duplicate_question(parsed.get("next_question"), [h.get("question", "") for h in (history or []) if h.get("question")]):
        nq = generate_next_question(state, history or [], q_num or 0, total_q or 10, parsed["action"], parsed["feedback"], parsed.get("next_topic", topic))
        parsed["next_question"] = nq.get("question")
        parsed["next_topic"] = nq.get("topic", parsed.get("next_topic", topic))
        parsed["next_difficulty"] = nq.get("difficulty", difficulty)
    else:
        # Filter garbage next_question — error texts or too-long content
        nq_text = parsed["next_question"]
        if len(nq_text) > 200 or nq_text.startswith("Error:") or "Unable to generate" in nq_text:
            nq = generate_next_question(state, history or [], q_num or 0, total_q or 10, parsed["action"], parsed["feedback"], parsed.get("next_topic", topic))
            parsed["next_question"] = nq.get("question")
            parsed["next_topic"] = nq.get("topic", parsed.get("next_topic", topic))
            parsed["next_difficulty"] = nq.get("difficulty", difficulty)

    return {
        "feedback": parsed.get("feedback", "Evaluation completed."),
        "score": max(0, min(10, int(parsed.get("score", 5)))),
        "action": parsed.get("action", "NEXT_TOPIC"),
        "skills_demonstrated": parsed.get("skills_demonstrated", [topic]),
        "sub_skills_demonstrated": parsed.get("sub_skills_demonstrated", []),
        "next_question": parsed.get("next_question"),
        "next_topic": parsed.get("next_topic", topic),
        "next_difficulty": parsed.get("next_difficulty", skill_difficulty),
        "tokens": result["tokens"],
        "latency_ms": result["latency_ms"],
    }


def generate_first_question(state: InterviewState) -> dict:
    untested = state.get_next_untested_skill()
    topic = untested or state.jd_skills[0] if state.jd_skills else "general"

    user_content = (
        f"Start the interview for the {state.role} position.\n"
        f"Ask exactly ONE question about '{topic}'.\n"
        f"The candidate has {', '.join(state.resume_skills[:5])} on their resume.\n"
        f"Reference something from their background to sound natural.\n"
        f"OUTPUT FORMAT (JSON only):\n"
        f"{{\n"
        f'  "question": "Your short conversational question (max 15 words)",\n'
        f'  "topic": "{topic}",\n'
        f'  "difficulty": "easy"\n'
        f"}}\n"
    )
    messages = [
        {"role": "system", "content": build_system_prompt(state)},
        {"role": "user", "content": user_content},
    ]
    result = llm_client.call(messages, max_tokens=200, temperature=0.7)
    content = result["content"]
    parsed = parse_json_output(content)
    if parsed and "question" in parsed:
        return {
            "question": parsed["question"],
            "topic": topic,
            "difficulty": "easy",
            "tokens": result["tokens"],
            "latency_ms": result["latency_ms"],
        }
    question = re.sub(r'^["\']+|["\']+$', '', content)
    question = re.sub(r'^(Question|Q):\s*', '', question, flags=re.IGNORECASE)
    if len(question) > 200 or "Error:" in question or "Unable to generate" in question:
        question = f"Tell me about your experience with {topic}."
    return {
        "question": question,
        "topic": topic,
        "difficulty": "easy",
        "tokens": result["tokens"],
        "latency_ms": result["latency_ms"],
    }


def _fallback_question(topic: str, asked_questions: list, q_num: int) -> str:
    """
    Used only when the LLM call/parse fails (e.g. HF token invalid, rate limited,
    model down). Previously this returned ONE fixed sentence every time, which is
    exactly what made a question look like it was "repeating" — if the LLM kept
    failing, the candidate saw the identical line on every turn. Now we rotate
    through several phrasings and skip any that were already asked.
    """
    templates = [
        f"Can you walk me through your experience with {topic}?",
        f"Tell me about a project where you used {topic} in depth.",
        f"What's a challenging problem you solved using {topic}?",
        f"How would you explain {topic} to a junior developer?",
        f"What best practices do you follow when working with {topic}?",
        f"What's something tricky you learned while working with {topic}?",
    ]
    for t in templates:
        if not _is_duplicate_question(t, asked_questions):
            return t
    # Every template already used (very long interview on one topic) — make it unique.
    return f"Let's go deeper on {topic} — what else can you tell me about it? (q{q_num})"


def generate_final_report(state: InterviewState, history: list) -> dict:
    if not history:
        return {
            "candidate_level": "",
            "hire_recommendation": "",
            "strengths": [],
            "weaknesses": [],
            "skills_tested": [],
            "skills_not_tested": [],
            "skills_partially_demonstrated": [],
            "knowledge_gaps": [],
            "complete_knowledge_gaps": [],
            "partial_knowledge_areas": [],
            "advanced_topics_not_covered": [],
            "coverage_percentage": "0%",
            "interview_summary": "No interview data available.",
        }

    transcript = ""
    total_score = 0
    low_scores = 0
    high_scores = 0
    mid_scores = 0
    topic_scores = {}
    for h in history:
        transcript += (
            f"Q{h['question_number']} ({h['difficulty']}, topic: {h.get('topic', 'general')}): "
            f"{h['question']}\n"
            f"Answer: {h['answer']}\n"
            f"Feedback: {h.get('feedback', '')[:200]}\n"
            f"Score: {h.get('score', 0)}/10\n\n"
        )
        score = h.get('score', 0)
        total_score += score
        if score <= 3:
            low_scores += 1
        elif score >= 7:
            high_scores += 1
        else:
            mid_scores += 1
        topic = h.get('topic', 'general')
        topic_scores.setdefault(topic, []).append(score)

    avg_score = round(total_score / len(history), 1) if history else 0

    topic_summary = []
    for topic, scores in sorted(topic_scores.items()):
        t_avg = round(sum(scores) / len(scores), 1)
        topic_summary.append(f"{topic}: avg {t_avg}/10 over {len(scores)} questions")

    skills_tested_str = ", ".join(state.tested_skills) if state.tested_skills else "(none)"
    skills_untested_str = ", ".join(state.untested_skills) if state.untested_skills else "(none)"
    skills_partial_str = ", ".join(state.partially_tested_skills) if state.partially_tested_skills else "(none)"

    confidence_summary = []
    for skill in state.tested_skills:
        c = state.get_skill_confidence(skill)
        confidence_summary.append(f"{skill}: {c or 'unknown'} confidence")
    for skill in state.partially_tested_skills:
        if skill not in state.tested_skills:
            c = state.get_skill_confidence(skill)
            confidence_summary.append(f"{skill}: {c or 'unknown'} confidence (partial)")

    user_content = (
        f"Generate a comprehensive hiring report for the {state.role} position at {state.company}.\n\n"
        f"Required Skills: {', '.join(state.jd_required_skills)}\n"
        f"Preferred Skills: {', '.join(state.jd_preferred_skills)}\n"
        f"Skills Tested (high confidence): {skills_tested_str}\n"
        f"Skills Partially Demonstrated: {skills_partial_str}\n"
        f"Skills Not Yet Asked About: {skills_untested_str}\n"
        f"Skill Confidence:\n" + "\n".join(f"- {s}" for s in confidence_summary) +
        f"\nSkill Coverage: {state.coverage_percentage}% "
        f"({len(state.tested_skills)}/{len(state._denominator_skills)} required skills tested)\n"
        f"Average Score: {avg_score}/10\n"
        f"Score Distribution: {high_scores} high (7-10), {mid_scores} mid (4-6), {low_scores} low (0-3)\n"
        f"Per-Topic Averages:\n" + "\n".join(f"- {s}" for s in topic_summary) +
        f"\n\nFull Interview Transcript:\n{transcript}\n\n"
        f"RULES:\n"
        f"- Determine candidate_level (Entry/Mid/Senior/Lead) from interview performance, NOT from the provided fields.\n"
        f"  GUIDELINE: avg 0-3 = Entry, 4-6 = Mid, 7-8 = Senior, 9-10 = Lead.\n"
        f"- strengths and weaknesses must be based ONLY on actual interview evidence from the transcript.\n"
        f"- Skills are categorized into FOUR groups:\n"
        f"  1. skills_tested: Skills asked about where candidate scored 7+ (high confidence, demonstrated well)\n"
        f"  2. skills_partially_demonstrated: Skills asked about where candidate scored 4-6 (showed some knowledge)\n"
        f"  3. skills_not_tested: Required skills NEVER asked about — these are NOT gaps, just untested\n"
        f"  4. knowledge_gaps: Specific concepts ASKED about where candidate scored 0-3 (genuinely didn't know)\n"
        f"- Never list a skill_not_tested as a knowledge gap, weakness, or anything negative. "
        f"These skills were simply never covered.\n"
        f"- complete_knowledge_gaps = specific concepts asked about with score 0-3.\n"
        f"- partial_knowledge_areas = specific concepts asked about with score 4-6.\n"
        f"- advanced_topics_not_covered = advanced concepts never asked about (usually advanced/nice-to-have).\n"
        f"- hire_recommendation must be consistent with avg_score and the feedback in the transcript.\n"
        f"- Candidate level must reflect demonstrated performance: if most answers are 7+, level should be Senior or Lead.\n\n"
        f"OUTPUT FORMAT (JSON only):\n"
        f"{{\n"
        f'  "candidate_level": "Entry" or "Mid" or "Senior" or "Lead",\n'
        f'  "hire_recommendation": "HIRE" or "CONSIDER" or "REJECT" or "N/A",\n'
        f'  "strengths": ["specific strength with evidence from transcript", ...],\n'
        f'  "weaknesses": ["specific weakness with evidence from transcript", ...],\n'
        f'  "skills_tested": {json.dumps(state.tested_skills)},\n'
        f'  "skills_not_tested": {json.dumps(state.untested_skills)},\n'
        f'  "skills_partially_demonstrated": {json.dumps(state.partially_tested_skills)},\n'
        f'  "knowledge_gaps": ["concept asked about but scored 0-3 (genuine gap)", ...],\n'
        f'  "complete_knowledge_gaps": ["specific concept asked, scored 0-3", ...],\n'
        f'  "partial_knowledge_areas": ["specific concept asked, scored 4-6", ...],\n'
        f'  "advanced_topics_not_covered": ["advanced topic not asked", ...],\n'
        f'  "coverage_percentage": "{state.coverage_percentage}%",\n'
        f'  "interview_summary": "A detailed 4-5 sentence overall assessment of the candidate."\n'
        f"}}\n"
    )

    messages = [
        {"role": "system", "content": "You are a senior technical recruiter producing a final hiring report."},
        {"role": "user", "content": user_content},
    ]

    result = llm_client.call(messages, max_tokens=700, temperature=0.4)
    content = result["content"]

    parsed = parse_json_output(content)
    if parsed and "hire_recommendation" in parsed:
        return {
            "candidate_level": parsed.get("candidate_level", state.experience),
            "hire_recommendation": parsed.get("hire_recommendation", "CONSIDER"),
            "strengths": parsed.get("strengths", []),
            "weaknesses": parsed.get("weaknesses", []),
            "skills_tested": parsed.get("skills_tested", state.tested_skills),
            "skills_not_tested": parsed.get("skills_not_tested", state.untested_skills),
            "skills_partially_demonstrated": parsed.get("skills_partially_demonstrated", state.partially_tested_skills),
            "knowledge_gaps": parsed.get("knowledge_gaps", []),
            "complete_knowledge_gaps": parsed.get("complete_knowledge_gaps", []),
            "partial_knowledge_areas": parsed.get("partial_knowledge_areas", []),
            "advanced_topics_not_covered": parsed.get("advanced_topics_not_covered", []),
            "coverage_percentage": parsed.get("coverage_percentage", f"{state.coverage_percentage}%"),
            "interview_summary": parsed.get("interview_summary", content[:500]),
        }

    return {
        "candidate_level": state.experience,
        "hire_recommendation": "CONSIDER",
        "strengths": [],
        "weaknesses": [],
        "skills_tested": state.tested_skills,
        "skills_not_tested": state.untested_skills,
        "skills_partially_demonstrated": state.partially_tested_skills,
        "knowledge_gaps": [],
        "complete_knowledge_gaps": [],
        "partial_knowledge_areas": [],
        "advanced_topics_not_covered": [],
        "coverage_percentage": f"{state.coverage_percentage}%",
        "interview_summary": content[:500],
    }


def should_end_interview(state: InterviewState, q_num: int, total_q: int, last_action: str, history: list) -> tuple:
    reasons = []

    if q_num >= total_q:
        reasons.append(f"Reached target of {total_q} questions")

    if state.coverage_percentage >= 90:
        all_tested = len(state.tested_skills) >= len(state._denominator_skills) if state._denominator_skills else True
        if all_tested:
            reasons.append(f"Tested {state.coverage_percentage}% of required skills")

    if len(history) >= 3:
        recent = history[-3:]
        all_low = all(h.get('score', 0) < 3 for h in recent)
        if all_low:
            reasons.append("Candidate struggling across multiple topics")
            return True, "; ".join(reasons)

    no_untested = not state.get_next_untested_skill()
    enough_depth = state.tested_skills and all(
        state.get_skill_confidence(skill) == "high"
        for skill in state.tested_skills
    ) if state.tested_skills else False

    if no_untested and q_num >= max(5, total_q // 2):
        reasons.append("All required skills tested with sufficient depth")
    elif no_untested and enough_depth and q_num >= total_q - 2:
        reasons.append("All required skills tested with good depth")
    elif no_untested and q_num >= total_q - 1:
        reasons.append("All required skills covered, last question")

    if len(reasons) > 0:
        return True, "; ".join(reasons)

    return False, ""
