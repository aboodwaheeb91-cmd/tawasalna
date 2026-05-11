"""
Authentication module - User registration & login with Supabase PostgreSQL
"""

import os
import bcrypt
import pg8000.native
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
    if "?" in dbname:
        dbname = dbname.split("?")[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    return pg8000.native.Connection(
        user=username,
        password=password,
        host=host,
        port=port,
        database=dbname,
        ssl_context=True
    )


def init_db():
    conn = get_conn()
    conn.run("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'emp',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ Users table ready.")


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_user(full_name: str, email: str, password: str, user_type: str) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            """
            INSERT INTO users (full_name, email, password_hash, user_type)
            VALUES (:full_name, :email, :password_hash, :user_type)
            RETURNING id, full_name, email, user_type, created_at
            """,
            full_name=full_name,
            email=email.lower().strip(),
            password_hash=hash_password(password),
            user_type=user_type
        )
        row = rows[0]
        user = {
            "id": row[0],
            "full_name": row[1],
            "email": row[2],
            "user_type": row[3],
            "created_at": row[4].isoformat() if row[4] else None
        }
        return user
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise ValueError("البريد الإلكتروني مسجل مسبقاً")
        raise


def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_conn()
    rows = conn.run(
        "SELECT id, full_name, email, password_hash, user_type, created_at FROM users WHERE email = :email",
        email=email.lower().strip()
    )
    if not rows:
        return None
    row = rows[0]
    password_hash = row[3]
    if not verify_password(password, password_hash):
        return None
    return {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "user_type": row[4],
        "created_at": row[5].isoformat() if row[5] else None
    }


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    rows = conn.run(
        "SELECT id, full_name, email, user_type, created_at FROM users WHERE id = :user_id",
        user_id=user_id
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row[0],
        "full_name": row[1],
        "email": row[2],
        "user_type": row[3],
        "created_at": row[4].isoformat() if row[4] else None
    }
    
