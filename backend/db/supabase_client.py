import psycopg2
import psycopg2.extras
import psycopg2.pool
import uuid
import datetime
import json
import logging
from contextlib import contextmanager
from core.config import settings

logger = logging.getLogger(__name__)

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set in .env")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            settings.DB_MIN_CONNECTIONS,
            settings.DB_MAX_CONNECTIONS,
            settings.DATABASE_URL,
        )
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor(cursor_factory=None):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()


def init_db():
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL not set. DB integration disabled.")
        return

    lock_key = 8192012345
    try:
        pool = get_pool()
        conn = pool.getconn()
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
                try:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS sessions (
                            id UUID PRIMARY KEY,
                            role TEXT,
                            company TEXT,
                            experience TEXT,
                            jd_text TEXT,
                            jd_skills JSONB DEFAULT '[]',
                            jd_required_skills JSONB DEFAULT '[]',
                            jd_preferred_skills JSONB DEFAULT '[]',
                            jd_responsibilities JSONB DEFAULT '[]',
                            jd_years_experience TEXT,
                            resume_text TEXT,
                            resume_skills JSONB DEFAULT '[]',
                            resume_projects JSONB DEFAULT '[]',
                            status TEXT DEFAULT 'created',
                            num_questions INTEGER DEFAULT 8,
                            start_time TIMESTAMP,
                            end_time TIMESTAMP,
                            duration_seconds INTEGER,
                            total_questions_asked INTEGER DEFAULT 0,
                            total_answers_given INTEGER DEFAULT 0,
                            current_topic TEXT,
                            tested_skills JSONB DEFAULT '[]',
                            untested_skills JSONB DEFAULT '[]',
                            coverage_percentage REAL DEFAULT 0.0,
                            final_report JSONB,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """)

                    cur.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'sessions' AND column_name IN ('jd_company', 'history')
                    """)
                    old_cols = {row[0] for row in cur.fetchall()}

                    if "jd_company" in old_cols:
                        cur.execute("ALTER TABLE sessions RENAME COLUMN jd_company TO company")

                    needs_add = False
                    for col, col_type in [
                        ("jd_text", "TEXT"),
                        ("jd_required_skills", "JSONB DEFAULT '[]'"),
                        ("jd_preferred_skills", "JSONB DEFAULT '[]'"),
                        ("jd_responsibilities", "JSONB DEFAULT '[]'"),
                        ("jd_years_experience", "TEXT"),
                        ("resume_text", "TEXT"),
                        ("status", "TEXT DEFAULT 'created'"),
                        ("start_time", "TIMESTAMP"),
                        ("end_time", "TIMESTAMP"),
                        ("duration_seconds", "INTEGER"),
                        ("total_questions_asked", "INTEGER DEFAULT 0"),
                        ("total_answers_given", "INTEGER DEFAULT 0"),
                        ("current_topic", "TEXT"),
                        ("tested_skills", "JSONB DEFAULT '[]'"),
                        ("untested_skills", "JSONB DEFAULT '[]'"),
                        ("coverage_percentage", "REAL DEFAULT 0.0"),
                        ("final_report", "JSONB"),
                        ("updated_at", "TIMESTAMP DEFAULT NOW()"),
                    ]:
                        cur.execute(f"""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = 'sessions' AND column_name = '{col}'
                        """)
                        if not cur.fetchone():
                            cur.execute(f"ALTER TABLE sessions ADD COLUMN {col} {col_type}")
                            needs_add = True

                    if "history" in old_cols:
                        cur.execute("""
                            UPDATE sessions SET status = 'completed'
                            WHERE (status IS NULL OR status = 'created')
                              AND history IS NOT NULL AND history != '[]'::jsonb
                        """)
                    cur.execute("""
                        UPDATE sessions SET status = 'created'
                        WHERE status IS NULL
                    """)

                    if "jd_company" in old_cols or needs_add:
                        logger.info("Migrated sessions table from old schema.")

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS interview_exchanges (
                            id SERIAL PRIMARY KEY,
                            session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
                            question_number INTEGER,
                            question TEXT,
                            answer TEXT,
                            feedback TEXT,
                            score INTEGER,
                            action TEXT,
                            topic TEXT,
                            difficulty TEXT,
                            timestamp TIMESTAMP DEFAULT NOW(),
                            token_count INTEGER DEFAULT 0,
                            latency_ms INTEGER DEFAULT 0
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_exchanges_session_id
                        ON interview_exchanges(session_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_sessions_status
                        ON sessions(status)
                    """)
                finally:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
            conn.commit()
        finally:
            pool.putconn(conn)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def create_session(
    role, experience, company, jd_text, jd_skills, jd_required_skills,
    jd_preferred_skills, jd_responsibilities, jd_years_experience,
    resume_text, resume_skills, resume_projects
):
    session_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow()
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO sessions (
                id, role, company, experience,
                jd_text, jd_skills, jd_required_skills, jd_preferred_skills,
                jd_responsibilities, jd_years_experience,
                resume_text, resume_skills, resume_projects,
                untested_skills, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
        """, (
            session_id, role, experience, company,
            jd_text, json.dumps(jd_skills), json.dumps(jd_required_skills),
            json.dumps(jd_preferred_skills), json.dumps(jd_responsibilities),
            jd_years_experience,
            resume_text, json.dumps(resume_skills), json.dumps(resume_projects),
            json.dumps(jd_skills), now, now,
        ))
    return session_id


def get_session(session_id):
    with get_cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
    return None


def update_session(session_id, **kwargs):
    allowed_fields = {
        "role", "company", "experience", "status", "num_questions",
        "start_time", "end_time", "duration_seconds",
        "total_questions_asked", "total_answers_given",
        "current_topic", "tested_skills", "untested_skills",
        "coverage_percentage", "final_report",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return
    updates["updated_at"] = datetime.datetime.utcnow()
    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [session_id]
    with get_cursor() as cur:
        cur.execute(
            f"UPDATE sessions SET {set_clause} WHERE id = %s",
            values,
        )


def get_exchanges(session_id):
    with get_cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            "SELECT * FROM interview_exchanges WHERE session_id = %s ORDER BY question_number ASC",
            (session_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def add_exchange(session_id, question_number, question, answer, feedback,
                 score, action, topic, difficulty, token_count=0, latency_ms=0):
    now = datetime.datetime.utcnow()
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO interview_exchanges
                (session_id, question_number, question, answer, feedback,
                 score, action, topic, difficulty, timestamp, token_count, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session_id, question_number, question, answer, feedback,
            score, action, topic, difficulty, now, token_count, latency_ms,
        ))


def update_session_after_exchange(session_id, tested_skills, untested_skills,
                                   coverage_pct, current_topic=None):
    now = datetime.datetime.utcnow()
    with get_cursor() as cur:
        cur.execute("""
            UPDATE sessions SET
                total_questions_asked = total_questions_asked + 1,
                total_answers_given = total_answers_given + 1,
                tested_skills = %s,
                untested_skills = %s,
                coverage_percentage = %s,
                current_topic = COALESCE(%s, current_topic),
                updated_at = %s
            WHERE id = %s
        """, (
            json.dumps(tested_skills),
            json.dumps(untested_skills),
            coverage_pct,
            current_topic,
            now,
            session_id,
        ))


def list_sessions():
    with get_cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT id, role, company, experience, status,
                   total_questions_asked, total_answers_given,
                   coverage_percentage, start_time, end_time,
                   duration_seconds, created_at
            FROM sessions
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("start_time", "end_time", "created_at"):
                if d.get(key):
                    d[key] = str(d[key])
            result.append(d)
        return result


def delete_session(session_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        return cur.rowcount > 0


def get_session_report_data(session_id):
    session = get_session(session_id)
    if not session:
        return None
    exchanges = get_exchanges(session_id)
    return {"session": session, "exchanges": exchanges}


def complete_session(session_id, final_report):
    now = datetime.datetime.utcnow()
    with get_cursor() as cur:
        cur.execute(
            "SELECT start_time FROM sessions WHERE id = %s", (session_id,)
        )
        row = cur.fetchone()
        duration = None
        if row and row[0]:
            duration = int((now - row[0]).total_seconds())
        cur.execute("""
            UPDATE sessions SET
                status = 'completed',
                end_time = %s,
                duration_seconds = %s,
                final_report = %s,
                updated_at = %s
            WHERE id = %s
        """, (now, duration, json.dumps(final_report), now, session_id))
