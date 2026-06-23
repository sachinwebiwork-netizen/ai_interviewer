import psycopg2
import psycopg2.extras
from core.config import settings
import uuid
import datetime
import json

def get_db_connection():
    if not settings.DATABASE_URL:
        raise Exception("DATABASE_URL not set in .env")
    return psycopg2.connect(settings.DATABASE_URL)

def init_db():
    if not settings.DATABASE_URL:
        print("Valid Postgres URL not provided. DB integration will not work.")
        return
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id UUID PRIMARY KEY,
                role TEXT,
                experience TEXT,
                jd_company TEXT,
                jd_skills JSONB,
                resume_skills JSONB,
                resume_projects JSONB,
                history JSONB,
                created_at TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize database: {e}")

def create_session(role: str, experience: str, jd_skills: list, resume_skills: list, resume_projects: list, jd_company: str):
    conn = get_db_connection()
    cur = conn.cursor()
    session_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow()
    
    cur.execute("""
        INSERT INTO sessions (id, role, experience, jd_company, jd_skills, resume_skills, resume_projects, history, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (session_id, role, experience, jd_company, json.dumps(jd_skills), json.dumps(resume_skills), json.dumps(resume_projects), json.dumps([]), created_at))
    
    conn.commit()
    cur.close()
    conn.close()
    return session_id

def get_session(session_id: str):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return dict(row)
    return None

def update_session_history(session_id: str, new_history_entry: dict):
    session = get_session(session_id)
    if not session:
        raise Exception("Session not found.")
        
    current_history = session.get("history", [])
    current_history.append(new_history_entry)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE sessions SET history = %s WHERE id = %s
    """, (json.dumps(current_history), session_id))
    
    conn.commit()
    cur.close()
    conn.close()
    return current_history
