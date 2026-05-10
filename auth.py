"""
Authentication module - User registration & login with Supabase PostgreSQL
"""

import os
import psycopg2
import psycopg2.extras
from passlib.context import CryptContext
from datetime import datetime
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_conn():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    # Parse manually to handle special chars like # in password
    # Format: postgresql://user:password@host:port/dbname
    try:
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
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception:
        return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)

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
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Users table ready.")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

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
        user = dict(cur.fetchone())
        conn.commit()
        if user.get("created_at"):
            user["created_at"] = user["created_at"].isoformat()
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
    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()
    return user

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
    user = dict(row)
    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()
    return user
