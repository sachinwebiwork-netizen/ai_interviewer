from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from schemas.document import DocumentUploadResponse
from services.document_parser import extract_text_from_file
from db.supabase_client import create_session

router = APIRouter(prefix="/document", tags=["Document"])

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    resume: UploadFile = File(...),
    jd: UploadFile = File(...),
    role: str = Form("Unknown Role"),
    experience: str = Form("Mid"),
    jd_company: str = Form("Unknown Company")
):
    try:
        resume_bytes = await resume.read()
        jd_bytes = await jd.read()
        
        resume_text = extract_text_from_file(resume.filename, resume_bytes)
        jd_text = extract_text_from_file(jd.filename, jd_bytes)
        
        if not resume_text or not jd_text:
            raise HTTPException(status_code=400, detail="Could not extract text from files.")
        
        # In a full production system, we would use an LLM here to extract exact skills.
        # For now, we will pass the raw chunked text as the 'skills' list to satisfy the prompt builder.
        # We take the first 1000 chars as context.
        jd_skills_extracted = [jd_text[:1000]]
        resume_skills_extracted = [resume_text[:1000]]
        resume_projects_extracted = [resume_text[1000:2000]] if len(resume_text) > 1000 else ["N/A"]

        # Create session in Supabase
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
            extracted_text_preview=f"Resume ({len(resume_text)} chars), JD ({len(jd_text)} chars)"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
