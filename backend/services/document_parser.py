import io
import fitz  # PyMuPDF
from docx import Document

def parse_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            text += page.get_text()
    except Exception as e:
        print(f"Error parsing PDF: {e}")
    return text

def parse_docx(file_bytes: bytes) -> str:
    text = ""
    try:
        doc = Document(io.BytesIO(file_bytes))
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        print(f"Error parsing DOCX: {e}")
    return text

def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    if filename.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif filename.endswith(".docx"):
        return parse_docx(file_bytes)
    elif filename.endswith(".txt"):
        return file_bytes.decode('utf-8')
    else:
        return "Unsupported file format."
