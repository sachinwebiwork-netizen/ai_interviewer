from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from schemas.document import DocumentUploadResponse
from services.document_parser import extract_text_from_file
from db.supabase_client import create_session
from typing import Optional
import re

router = APIRouter(prefix="/document", tags=["Document"])

def extract_from_jd(text: str):
    role = "Unknown Role"
    company = "Unknown Company"
    experience = "Mid"
    
    lines = text.strip().split("\n")
    first_lines = [l for l in lines[:10] if l.strip()]
    
    for line in first_lines:
        lower = line.lower().strip()
        if any(kw in lower for kw in ["intern", "fresher", "entry", "0-1", "0 - 1", "junior"]):
            experience = "Entry"
        elif any(kw in lower for kw in ["senior", "lead", "principal", "staff", "5+", "5 -", "7+", "10+"]):
            experience = "Senior"
        elif any(kw in lower for kw in ["3+", "3 -", "mid", "2+", "2 -"]):
            experience = "Mid"
    
    company_match = re.search(r'(?:at|@|company[:\s]*)\s*([A-Z][A-Za-z0-9\s.]+)', text[:500])
    if company_match:
        company = company_match.group(1).strip()[:50]
    
    role_match = re.search(r'(?:Role[:\s]*|Position[:\s]*|Title[:\s]*|Hiring[:\s]*for[:\s]*)\s*(.+?)(?:\n|$)', text[:500])
    if role_match:
        role = role_match.group(1).strip()[:50]
    
    return role, experience, company

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    resume: UploadFile = File(...),
    jd: Optional[UploadFile] = File(None),
    jd_text: Optional[str] = Form(None)
):
    try:
        resume_bytes = await resume.read()
        resume_text = extract_text_from_file(resume.filename, resume_bytes)
        if not resume_text:
            raise HTTPException(status_code=400, detail="Could not extract text from resume.")
        
        if jd:
            jd_bytes = await jd.read()
            jd_content = extract_text_from_file(jd.filename, jd_bytes)
        elif jd_text:
            jd_content = jd_text
        else:
            raise HTTPException(status_code=400, detail="Provide JD as file or text.")
        
        if not jd_content:
            raise HTTPException(status_code=400, detail="Could not extract JD content.")
        
        role, experience, jd_company = extract_from_jd(jd_content)
        
        jd_skills_extracted = [jd_content[:1000]]
        resume_skills_extracted = [resume_text[:1000]]
        resume_projects_extracted = [resume_text[1000:2000]] if len(resume_text) > 1000 else ["N/A"]

        session_id = create_session(
            role=role,
            experience=experience,
            jd_skills=jd_skills_extracted,
            resume_skills=resume_skills_extracted,
            resume_projects=resume_projects_extracted,
            jd_company=jd_company
        )
        
        return DocumentUploadResponse(
            message="Documents uploaded and session created successfully.",
            session_id=session_id,
            extracted_text_preview=f"Resume ({len(resume_text)} chars), JD ({len(jd_content)} chars)"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
