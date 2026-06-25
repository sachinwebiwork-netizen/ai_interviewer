import io
import re
import logging

import fitz
from docx import Document

logger = logging.getLogger(__name__)


def parse_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text()
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
    return text


def parse_docx(file_bytes: bytes) -> str:
    text = ""
    try:
        doc = Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        logger.error(f"Error parsing DOCX: {e}")
    return text


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    if filename.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return parse_docx(file_bytes)
    elif filename.endswith(".txt"):
        return file_bytes.decode("utf-8")
    else:
        return "Unsupported file format."


SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
    "react", "angular", "vue", "node", "express", "django", "flask", "spring",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "machine learning", "deep learning", "nlp", "computer vision",
    "pytorch", "tensorflow", "transformers", "rag", "llm",
    "rest", "graphql", "grpc", "kafka", "rabbitmq",
    "git", "ci/cd", "jenkins", "github actions",
    "agile", "scrum", "microservices", "system design",
    "pandas", "numpy", "spark", "hadoop", "airflow",
    "pytest", "jest", "selenium", "cypress",
    "oop", "design patterns", "tdd", "solid",
    "linux", "bash", "powershell",
    "data structures", "algorithms", "distributed systems",
]


def _clean_skill(raw: str) -> str:
    raw = raw.strip().lower()
    raw = re.sub(r'^[\d\s\+,\.]+', '', raw)
    raw = raw.strip().strip('*').strip('.')
    if len(raw) < 2 or len(raw) > 35:
        return ""
    if raw in ("to", "and", "the", "for", "with", "using", "of", "in", "on", "a", "an", "is", "are", "be",
               "years", "year", "experience", "working", "mandatory", "required", "preferred",
               "good", "strong", "basic", "advanced", "knowledge", "skill", "skills", "etc",
               "plus", "nice", "like", "including", "related", "solid", "proven", "expert"):
        return ""
    if re.match(r'^[^a-z#]', raw):
        return ""
    return raw


def extract_skills_from_text(text: str) -> list:
    text_lower = text.lower()
    found = set()
    for skill in SKILL_KEYWORDS:
        if skill in text_lower:
            found.add(skill)
    found_multi = re.findall(
        r'(?:skill|experience|knowledge|proficient|expertise|familiar|worked)\s*(?:in|with|on|of)?\s*:?\s*([^.\n]+)',
        text_lower,
    )
    for group in found_multi:
        for word in re.split(r'[,;/\-]', group):
            cleaned = _clean_skill(word)
            if cleaned and cleaned not in found:
                found.add(cleaned)
    found = {s for s in found if s in SKILL_KEYWORDS or (re.match(r'^[a-z][a-z0-9_#+.]*$', s) and len(s) >= 2)}
    return sorted(found)


EXPERIENCE_PATTERNS = [
    (r'\b(?:intern|fresher|entry.level|0[\-\s]?[12]|junior)\b', 'Entry'),
    (r'\b(?:mid.level|(?:2|3)[\-\s]?year|\bmid\b)\b', 'Mid'),
    (r'\b(?:senior|lead|principal|staff|architect|5[\+\-\s]|7[\+\-\s]|10[\+\-\s])\b', 'Senior'),
    (r'\b(?:principal|staff|architect|lead|head|director|vp|10[\+\-\s]|15[\+\-\s])\b', 'Lead'),
]


def extract_experience_level(text: str) -> str:
    text_lower = text.lower()
    for pattern, level in EXPERIENCE_PATTERNS:
        if re.search(pattern, text_lower):
            return level
    years = re.findall(r'(\d+)\s*\+?\s*(?:years?|yrs?)', text_lower)
    if years:
        max_years = max(int(y) for y in years)
        if max_years >= 10:
            return 'Lead'
        elif max_years >= 5:
            return 'Senior'
        elif max_years >= 2:
            return 'Mid'
        else:
            return 'Entry'
    return 'Mid'


ROLE_KEYWORDS = [
    "engineer", "developer", "architect", "scientist", "analyst",
    "manager", "lead", "intern", "internship", "director", "head",
    "consultant", "specialist", "administrator", "designer",
]


def extract_company(text: str) -> str:
    head = text[:500]
    match = re.search(
        r'(?:at|@|company[:\s]*)\s*([A-Z][A-Za-z0-9\s.&]+)',
        head,
    )
    if match:
        return match.group(1).strip()[:50]
    match = re.search(
        r'(?:about|join)\s+([A-Z][A-Za-z0-9\s.&]{2,30}?)(?:\s+is|\s+we|\s+our|\.|\n)',
        head,
    )
    if match:
        return match.group(1).strip()[:50]
    match = re.search(
        r'(?:welcome\s+to|^(?:we\s+are|this\s+is))\s+([A-Z][A-Za-z0-9\s.&]{2,30}?)(?:\s+[,.!]|\s+and|\s+is|\s+we|\n|$)',
        head,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()[:50]
    return ""


LEADING_FILLER = {
    "highly", "skilled", "experienced", "talented", "passionate",
    "motivated", "driven", "creative", "innovative", "dynamic",
    "exceptional", "outstanding", "amazing", "excellent", "great",
    "senior", "staff", "principal", "lead", "junior", "entry",
    "the", "a", "an",
}


def _strip_leading_filler(words: list[str]) -> list[str]:
    while words and words[0].lower() in LEADING_FILLER:
        words.pop(0)
    return words


def extract_role(text: str) -> str:
    head = text[:500]
    patterns = [
        r'(?:Role|Position|Job Title|Title)\s*:?\s*(.+?)(?:\n|$)',
        r'Hiring\s*for\s*(.+?)(?:\n|\.|,)',
        r'(?:are looking for|seek(?:ing)? an?\s+)(?:\w+\s+)*?(?:(Senior|Staff|Principal|Lead|Junior|Entry)\s+)?(.+?)(?:\n|\.|,)',
    ]
    for pattern in patterns:
        match = re.search(pattern, head, re.IGNORECASE)
        if match:
            raw = match.lastindex == 2 and match.group(2) or match.group(1)
            raw = raw.strip().strip('*').strip()
            for stop in ("role", "responsibilities", "to", "join", "for"):
                idx = raw.lower().find(stop)
                if idx > 0:
                    raw = raw[:idx].strip()
            words = _strip_leading_filler(raw.split())
            raw = " ".join(words)
            if len(raw) > 3:
                return raw[:50]

    first_line = text.split('\n')[0].strip()
    first_line_lower = first_line.lower()
    for kw in ROLE_KEYWORDS:
        if kw in first_line_lower:
            return first_line[:50]

    return ""


def extract_years_experience(text: str) -> str:
    match = re.search(
        r'(\d+)[\-\s]*to[\-\s]*(\d+)\s*(?:years?|yrs?)',
        text.lower(),
    )
    if match:
        return f"{match.group(1)}-{match.group(2)} years"
    match = re.search(
        r'(\d+)\s*\+?\s*(?:years?|yrs?)',
        text.lower(),
    )
    if match:
        return f"{match.group(1)}+ years"
    return ""


def extract_responsibilities(text: str) -> list:
    lines = text.split('\n')
    responsibilities = []
    capture = False
    for line in lines:
        stripped = line.strip().lower()
        if any(kw in stripped for kw in ['responsibilities', 'what you\'ll do', 'role & responsibilities', 'key responsibilities', 'duties']):
            capture = True
            continue
        if capture:
            if any(kw in stripped for kw in ['requirements', 'qualifications', 'skills', 'about you', 'benefits']):
                break
            if stripped.startswith('-') or stripped.startswith('*') or stripped.startswith('•'):
                responsibilities.append(line.strip().lstrip('-*• '))
            elif stripped and not stripped.startswith('#'):
                responsibilities.append(line.strip())
    if not responsibilities:
        for line in lines:
            stripped = line.strip()
            if stripped and (stripped.startswith('-') or stripped.startswith('•') or stripped.startswith('*')):
                responsibilities.append(stripped.lstrip('-•* '))
    return responsibilities[:15]


def _extract_jd_llm(jd_text: str) -> dict:
    from services.ai_service import LLMClient, parse_json_output

    client = LLMClient()
    prompt = (
        "Extract role, company, and experience level from this job description. "
        "Return ONLY valid JSON with keys: role, company, experience. "
        'experience must be one of: "Entry", "Mid", "Senior", "Lead". '
        'If a field is unclear use "".\n\n'
        f"JD:\n{jd_text[:1500]}"
    )
    try:
        result = client.call(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        data = parse_json_output(result["content"])
        if data:
            role = data.get("role", "").strip()
            for stop in ("responsibilities", "to", "join", "for", "the"):
                idx = role.lower().find(stop)
                if idx > 0:
                    role = role[:idx].strip()
            words = _strip_leading_filler(role.split())
            role = " ".join(words)
            return {
                "role": role[:50],
                "company": data.get("company", "").strip()[:50],
                "experience": data.get("experience", "Mid").strip(),
            }
    except Exception as e:
        logger.warning("LLM extraction failed, falling back to regex: %s", e)
    return {}


def extract_jd_info(text: str) -> dict:
    jd_text = text.strip()
    if not jd_text:
        return {
            "role": "",
            "company": "",
            "experience": "Mid",
            "skills": [],
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "years_experience": "",
        }

    skills = extract_skills_from_text(jd_text)
    required_skills = skills[:]
    preferred_skills = []

    preferred_matches = re.findall(
        r'(?:nice.to.have|preferred|plus|bonus|good.to.have)[^.\n]*',
        jd_text.lower(),
    )
    if preferred_matches:
        preferred_text = ' '.join(preferred_matches)
        preferred_skills = extract_skills_from_text(preferred_text)
        required_skills = [s for s in skills if s not in preferred_skills]

    llm_info = _extract_jd_llm(jd_text)

    return {
        "role": llm_info.get("role") or extract_role(jd_text),
        "company": llm_info.get("company") or extract_company(jd_text),
        "experience": llm_info.get("experience") or extract_experience_level(jd_text),
        "skills": skills,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "responsibilities": extract_responsibilities(jd_text),
        "years_experience": extract_years_experience(jd_text),
    }


def extract_resume_info(text: str) -> dict:
    skills = extract_skills_from_text(text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    projects = []
    capture = False
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in ['projects', 'experience', 'work experience']):
            capture = True
            continue
        if capture:
            if any(kw in lower for kw in ['education', 'certification', 'skills', 'summary']):
                break
            projects.append(line[:200])
    if not projects:
        projects = [lines[i] for i in range(min(5, len(lines)))]
    return {
        "skills": skills,
        "projects": projects[:5],
    }
