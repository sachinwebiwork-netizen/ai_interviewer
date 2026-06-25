from pydantic import BaseModel
from typing import Optional


class DocumentUploadResponse(BaseModel):
    message: str
    session_id: Optional[str] = None
    extracted_text_preview: str
    role: str
    experience: str
    company: str
    skills_found: list = []
