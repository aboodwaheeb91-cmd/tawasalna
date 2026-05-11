"""
Authentication module - User registration & login with Supabase PostgreSQL
"""

import os
import bcrypt
import psycopg2
import psycopg2.extras
from datetime import datetime
from typing import Optional

def get_conn():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    url = url.strip().replace(" ", "")
    without_scheme = url.split("://", 1)[1]
    userinfo, hostinfo = without_scheme.split("@", 1)
    username, password = userinfo.split(":", 1)
    host_port, dbname = hostinfo.split("/", 1)
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    return psycopg2.connect(
        host=host, port=port, user=username,
        password=password, dbname=dbname,
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'emp',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            headline TEXT,
            bio TEXT,
            location TEXT,
            skills TEXT[],
            avatar_url TEXT,
            website TEXT,
            is_verified BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS experience (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            is_current BOOLEAN DEFAULT FALSE,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS education (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            institution TEXT NOT NULL,
            degree TEXT,
            field TEXT,
            start_year INTEGER,
            end_year INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            provider TEXT,
            completion_date TEXT,
            certificate_url TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS verify_requests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            document_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ All tables ready.")

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _serialize(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

# ─────────────────────────────────────────
# Users
# ─────────────────────────────────────────
def create_user(full_name: str, email: str, password: str, user_type: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (full_name, email, password_hash, user_type)
            VALUES (%s, %s, %s, %s)
            RETURNING id, full_name, email, user_type, created_at
            """,
            (full_name, email.lower().strip(), hash_password(password), user_type)
        )
        user = _serialize(dict(cur.fetchone()))
        conn.commit()
        return user
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise ValueError("البريد الإلكتروني مسجل مسبقاً")
    finally:
        cur.close()
        conn.close()

def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, email, password_hash, user_type, created_at FROM users WHERE email = %s",
        (email.lower().strip(),)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    user = dict(row)
    if not verify_password(password, user["password_hash"]):
        return None
    user.pop("password_hash")
    return _serialize(user)

def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, email, user_type, created_at FROM users WHERE id = %s",
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return _serialize(dict(row))

# ─────────────────────────────────────────
# Profiles
# ─────────────────────────────────────────
def _get_profile_extras(cur, user_id: int) -> dict:
    cur.execute(
        "SELECT id, title, company, location, start_date, end_date, is_current, description, created_at FROM experience WHERE user_id = %s ORDER BY id DESC",
        (user_id,)
    )
    experience = [_serialize(dict(r)) for r in cur.fetchall()]

    cur.execute(
        "SELECT id, institution, degree, field, start_year, end_year, description, created_at FROM education WHERE user_id = %s ORDER BY id DESC",
        (user_id,)
    )
    education = [_serialize(dict(r)) for r in cur.fetchall()]

    cur.execute(
        "SELECT id, title, provider, completion_date, certificate_url, description, created_at FROM courses WHERE user_id = %s ORDER BY id DESC",
        (user_id,)
    )
    courses = [_serialize(dict(r)) for r in cur.fetchall()]

    return {"experience": experience, "education": education, "courses": courses}

def get_public_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, user_type, created_at FROM users WHERE id = %s",
        (user_id,)
    )
    user_row = cur.fetchone()
    if not user_row:
        cur.close(); conn.close()
        return None
    user = _serialize(dict(user_row))

    cur.execute(
        "SELECT headline, bio, location, skills, avatar_url, website, is_verified FROM profiles WHERE user_id = %s",
        (user_id,)
    )
    profile_row = cur.fetchone()
    profile = dict(profile_row) if profile_row else {}

    extras = _get_profile_extras(cur, user_id)
    cur.close(); conn.close()

    return {**user, **profile, **extras}

def get_full_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, email, user_type, created_at FROM users WHERE id = %s",
        (user_id,)
    )
    user_row = cur.fetchone()
    if not user_row:
        cur.close(); conn.close()
        return None
    user = _serialize(dict(user_row))

    cur.execute(
        "SELECT headline, bio, location, skills, avatar_url, website, is_verified, updated_at FROM profiles WHERE user_id = %s",
        (user_id,)
    )
    profile_row = cur.fetchone()
    profile = _serialize(dict(profile_row)) if profile_row else {}

    cur.execute(
        "SELECT id, status, created_at FROM verify_requests WHERE user_id = %s ORDER BY id DESC LIMIT 1",
        (user_id,)
    )
    vr = cur.fetchone()
    verify_request = _serialize(dict(vr)) if vr else None

    extras = _get_profile_extras(cur, user_id)
    cur.close(); conn.close()

    return {**user, **profile, **extras, "verify_request": verify_request}

def update_profile(user_id: int, data: dict) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        raise ValueError("المستخدم غير موجود")

    cur.execute("SELECT id FROM profiles WHERE user_id = %s", (user_id,))
    exists = cur.fetchone()

    allowed = ["headline", "bio", "location", "skills", "avatar_url", "website"]
    fields = {k: v for k, v in data.items() if k in allowed and v is not None}

    if exists:
        if fields:
            set_clause = ", ".join(f"{k} = %s" for k in fields)
            values = list(fields.values()) + [user_id]
            cur.execute(
                f"UPDATE profiles SET {set_clause}, updated_at = NOW() WHERE user_id = %s",
                values
            )
    else:
        cols = ["user_id"] + list(fields.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        values = [user_id] + list(fields.values())
        cur.execute(
            f"INSERT INTO profiles ({', '.join(cols)}) VALUES ({placeholders})",
            values
        )

    conn.commit()
    cur.close(); conn.close()
    return get_full_profile(user_id)

# ─────────────────────────────────────────
# Experience
# ─────────────────────────────────────────
def add_experience(user_id: int, data: dict) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO experience (user_id, title, company, location, start_date, end_date, is_current, description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, user_id, title, company, location, start_date, end_date, is_current, description, created_at
        """,
        (user_id, data["title"], data["company"], data.get("location"),
         data.get("start_date"), data.get("end_date"),
         data.get("is_current", False), data.get("description"))
    )
    row = _serialize(dict(cur.fetchone()))
    conn.commit()
    cur.close(); conn.close()
    return row

# ─────────────────────────────────────────
# Education
# ─────────────────────────────────────────
def add_education(user_id: int, data: dict) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO education (user_id, institution, degree, field, start_year, end_year, description)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id, user_id, institution, degree, field, start_year, end_year, description, created_at
        """,
        (user_id, data["institution"], data.get("degree"), data.get("field"),
         data.get("start_year"), data.get("end_year"), data.get("description"))
    )
    row = _serialize(dict(cur.fetchone()))
    conn.commit()
    cur.close(); conn.close()
    return row

# ─────────────────────────────────────────
# Courses
# ─────────────────────────────────────────
def add_course(user_id: int, data: dict) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO courses (user_id, title, provider, completion_date, certificate_url, description)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, user_id, title, provider, completion_date, certificate_url, description, created_at
        """,
        (user_id, data["title"], data.get("provider"),
         data.get("completion_date"), data.get("certificate_url"), data.get("description"))
    )
    row = _serialize(dict(cur.fetchone()))
    conn.commit()
    cur.close(); conn.close()
    return row

# ─────────────────────────────────────────
# Verify Requests
# ─────────────────────────────────────────
def create_verify_request(user_id: int, data: dict) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        raise ValueError("المستخدم غير موجود")

    cur.execute(
        """
        INSERT INTO verify_requests (user_id, document_url, notes, status)
        VALUES (%s, %s, %s, 'pending')
        RETURNING id, user_id, document_url, notes, status, created_at
        """,
        (user_id, data.get("document_url"), data.get("notes"))
    )
    row = _serialize(dict(cur.fetchone()))
    conn.commit()
    cur.close(); conn.close()
    return row
