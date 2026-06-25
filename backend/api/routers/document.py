import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional

from schemas.document import DocumentUploadResponse
from services.document_parser import extract_text_from_file, extract_jd_info, extract_resume_info
from db.supabase_client import create_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document", tags=["Document"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    resume: UploadFile = File(...),
    jd: Optional[UploadFile] = File(None),
    jd_text: Optional[str] = Form(None),
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

        jd_info = extract_jd_info(jd_content)
        resume_info = extract_resume_info(resume_text)

        session_id = create_session(
            role=jd_info["role"],
            experience=jd_info["experience"],
            company=jd_info["company"],
            jd_text=jd_content,
            jd_skills=jd_info["skills"],
            jd_required_skills=jd_info["required_skills"],
            jd_preferred_skills=jd_info["preferred_skills"],
            jd_responsibilities=jd_info["responsibilities"],
            jd_years_experience=jd_info["years_experience"],
            resume_text=resume_text,
            resume_skills=resume_info["skills"],
            resume_projects=resume_info["projects"],
        )

        logger.info(
            "Session created", extra={
                "session_id": session_id,
                "role": jd_info["role"],
                "company": jd_info["company"],
                "skills": len(jd_info["skills"]),
            }
        )

        return DocumentUploadResponse(
            message="Documents uploaded and session created successfully.",
            session_id=session_id,
            extracted_text_preview=f"Resume ({len(resume_text)} chars), JD ({len(jd_content)} chars)",
            role=jd_info["role"],
            experience=jd_info["experience"],
            company=jd_info["company"],
            skills_found=jd_info["skills"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=str(e))
