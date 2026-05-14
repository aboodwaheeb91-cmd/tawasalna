"""
Authentication module - Supabase PostgreSQL
Using pg8000 (pure Python, no system dependencies)
"""

import os
import bcrypt
import pg8000.native
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────
# Connection
# ─────────────────────────────────────────
def get_conn():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    url = url.strip().replace(" ", "")
    without_scheme = url.split("://", 1)[1]
    userinfo, hostinfo = without_scheme.split("@", 1)
    username, password = userinfo.split(":", 1)
    host_port, dbname = hostinfo.split("/", 1)
    dbname = dbname.split("?")[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    return pg8000.native.Connection(
        host=host, port=port, user=username,
        password=password, database=dbname,
        ssl_context=True
    )


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _row_to_dict(columns, row):
    return dict(zip(columns, row))


def _serialize(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─────────────────────────────────────────
# Init DB
# ─────────────────────────────────────────
def init_db():
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                user_type TEXT NOT NULL DEFAULT 'emp',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
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
            )
        """)
        conn.run("""
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
            )
        """)
        conn.run("""
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
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS courses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                provider TEXT,
                completion_date TEXT,
                certificate_url TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Set ID sequence to start from large random-looking number
        try:
            conn.run("SELECT setval('users_id_seq', 48000, false) WHERE NOT EXISTS (SELECT 1 FROM users)")
        except Exception:
            pass
        conn.run("""
            CREATE TABLE IF NOT EXISTS verify_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                document_url TEXT,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        print("✅ All tables ready.")
    finally:
        conn.close()


# ─────────────────────────────────────────
# Users
# ─────────────────────────────────────────
def create_user(full_name: str, email: str, password: str, user_type: str) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO users (full_name, email, password_hash, user_type) "
            "VALUES (:name, :email, :pw, :utype) "
            "RETURNING id, full_name, email, user_type, created_at",
            name=full_name, email=email.lower().strip(),
            pw=hash_password(password), utype=user_type
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise ValueError("البريد الإلكتروني مسجل مسبقاً")
        raise
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, email, password_hash, user_type, created_at "
            "FROM users WHERE email = :email",
            email=email.lower().strip()
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _row_to_dict(cols, rows[0])
        if not verify_password(password, user["password_hash"]):
            return None
        user.pop("password_hash")
        return _serialize(user)
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, email, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()


# ─────────────────────────────────────────
# Profile Extras
# ─────────────────────────────────────────
def _get_profile_extras(conn, user_id: int) -> dict:
    rows = conn.run(
        "SELECT id, title, company, location, start_date, end_date, is_current, description, created_at "
        "FROM experience WHERE user_id = :uid ORDER BY id DESC",
        uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    experience = [_serialize(_row_to_dict(cols, r)) for r in rows]

    rows = conn.run(
        "SELECT id, institution, degree, field, start_year, end_year, description, created_at "
        "FROM education WHERE user_id = :uid ORDER BY id DESC",
        uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    education = [_serialize(_row_to_dict(cols, r)) for r in rows]

    rows = conn.run(
        "SELECT id, title, provider, completion_date, certificate_url, description, created_at "
        "FROM courses WHERE user_id = :uid ORDER BY id DESC",
        uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    courses = [_serialize(_row_to_dict(cols, r)) for r in rows]

    return {"experience": experience, "education": education, "courses": courses}


# ─────────────────────────────────────────
# Profiles
# ─────────────────────────────────────────
def get_public_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _serialize(_row_to_dict(cols, rows[0]))

        rows = conn.run(
            "SELECT headline, bio, location, skills, avatar_url, website, is_verified "
            "FROM profiles WHERE user_id = :uid",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        profile = _serialize(_row_to_dict(cols, rows[0])) if rows else {}

        extras = _get_profile_extras(conn, user_id)
        return {**user, **profile, **extras}
    finally:
        conn.close()


def get_full_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, email, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _serialize(_row_to_dict(cols, rows[0]))

        rows = conn.run(
            "SELECT headline, bio, location, skills, avatar_url, website, is_verified, updated_at "
            "FROM profiles WHERE user_id = :uid",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        profile = _serialize(_row_to_dict(cols, rows[0])) if rows else {}

        rows = conn.run(
            "SELECT id, status, created_at FROM verify_requests "
            "WHERE user_id = :uid ORDER BY id DESC LIMIT 1",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        verify_request = _serialize(_row_to_dict(cols, rows[0])) if rows else None

        extras = _get_profile_extras(conn, user_id)
        return {**user, **profile, **extras, "verify_request": verify_request}
    finally:
        conn.close()


def update_profile(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE id = :uid", uid=user_id)
        if not rows:
            raise ValueError("المستخدم غير موجود")

        rows = conn.run("SELECT id FROM profiles WHERE user_id = :uid", uid=user_id)
        exists = bool(rows)

        allowed = ["headline", "bio", "location", "skills", "avatar_url", "website"]
        fields = {k: v for k, v in data.items() if k in allowed and v is not None}

        if exists:
            if fields:
                set_clause = ", ".join(f"{k} = :{k}" for k in fields)
                conn.run(
                    f"UPDATE profiles SET {set_clause}, updated_at = NOW() WHERE user_id = :uid",
                    uid=user_id, **fields
                )
        else:
            cols_list = ["user_id"] + list(fields.keys())
            placeholders = ", ".join(f":{c}" for c in cols_list)
            conn.run(
                f"INSERT INTO profiles ({', '.join(cols_list)}) VALUES ({placeholders})",
                user_id=user_id, **fields
            )
    finally:
        conn.close()
    return get_full_profile(user_id)


# ─────────────────────────────────────────
# Experience
# ─────────────────────────────────────────
def add_experience(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO experience (user_id, title, company, location, start_date, end_date, is_current, description) "
            "VALUES (:uid, :title, :company, :location, :start_date, :end_date, :is_current, :description) "
            "RETURNING id, user_id, title, company, location, start_date, end_date, is_current, description, created_at",
            uid=user_id, title=data["title"], company=data["company"],
            location=data.get("location"), start_date=data.get("start_date"),
            end_date=data.get("end_date"), is_current=data.get("is_current", False),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()


# ─────────────────────────────────────────
# Education
# ─────────────────────────────────────────
def add_education(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO education (user_id, institution, degree, field, start_year, end_year, description) "
            "VALUES (:uid, :institution, :degree, :field, :start_year, :end_year, :description) "
            "RETURNING id, user_id, institution, degree, field, start_year, end_year, description, created_at",
            uid=user_id, institution=data["institution"],
            degree=data.get("degree"), field=data.get("field"),
            start_year=data.get("start_year"), end_year=data.get("end_year"),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()


# ─────────────────────────────────────────
# Courses
# ─────────────────────────────────────────
def add_course(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO courses (user_id, title, provider, completion_date, certificate_url, description) "
            "VALUES (:uid, :title, :provider, :completion_date, :certificate_url, :description) "
            "RETURNING id, user_id, title, provider, completion_date, certificate_url, description, created_at",
            uid=user_id, title=data["title"],
            provider=data.get("provider"),
            completion_date=data.get("completion_date"),
            certificate_url=data.get("certificate_url"),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()


# ─────────────────────────────────────────
# Verify Requests
# ─────────────────────────────────────────
def create_verify_request(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE id = :uid", uid=user_id)
        if not rows:
            raise ValueError("المستخدم غير موجود")
        rows = conn.run(
            "INSERT INTO verify_requests (user_id, document_url, notes, status) "
            "VALUES (:uid, :doc_url, :notes, 'pending') "
            "RETURNING id, user_id, document_url, notes, status, created_at",
            uid=user_id,
            doc_url=data.get("document_url"),
            notes=data.get("notes")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()
