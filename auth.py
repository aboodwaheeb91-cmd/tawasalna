"""
Authentication module - Supabase PostgreSQL
تواصلنا - نظام المصادقة وقاعدة البيانات
"""

import os
import uuid
import bcrypt
import pg8000.native
from datetime import datetime
from typing import Optional


# ══ نظام الـ IDs ══
# الشكل: {PREFIX}{COUNTRY_CODE}{UUID_10_CHARS}
# مثال: U96204a8f3c9b2e (موظف أردني)

TYPE_PREFIX = {
    'emp': 'U',   # User (موظف)
    'co':  'C',   # Company (شركة)
    'edu': 'T',   # Training/Education (مؤسسة تعليمية)
}

COUNTRY_CODES = {
    'JO': '9620', 'SA': '9660', 'AE': '9710', 'KW': '9650',
    'QA': '9740', 'BH': '9730', 'OM': '9680', 'EG': '2000',
    'IQ': '9640', 'SY': '9630', 'LB': '9610', 'PS': '9720',
    'YE': '9670', 'MA': '2120', 'DZ': '2130', 'TN': '2160',
    'LY': '2180', 'SD': '2490', 'DEFAULT': '0000',
}


def generate_tw_id(user_type: str, country_code: str = 'DEFAULT') -> str:
    """
    يولّد معرف احترافي فريد للحساب.
    الشكل: {U/C/T}{كود_الدولة}{10_أحرف_عشوائية}
    مثال: U9620ec95e9c5ca
    """
    prefix = TYPE_PREFIX.get(user_type, 'U')
    cc = COUNTRY_CODES.get(country_code, COUNTRY_CODES['DEFAULT'])
    rand = uuid.uuid4().hex[:10]
    return f"{prefix}{cc}{rand}"


# ══ الاتصال بقاعدة البيانات ══
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
        password=password, database=dbname, ssl_context=True
    )


# ══ مساعدات ══
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


# ══ تهيئة قاعدة البيانات ══
def init_db():
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                tw_id TEXT UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                user_type TEXT NOT NULL DEFAULT 'emp',
                country_code TEXT DEFAULT 'DEFAULT',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Migration: أضف الأعمدة الجديدة لو ما موجودة
        for col_sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS tw_id TEXT UNIQUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS country_code TEXT DEFAULT 'DEFAULT'",
        ]:
            try:
                conn.run(col_sql)
            except Exception:
                pass

        # Migration: ولّد tw_id للحسابات القديمة
        try:
            old_users = conn.run(
                "SELECT id, user_type, country_code FROM users WHERE tw_id IS NULL"
            )
            for row in (old_users or []):
                uid, utype, cc = row[0], row[1] or 'emp', row[2] or 'DEFAULT'
                tw_id = _unique_tw_id(conn, utype, cc)
                conn.run(
                    "UPDATE users SET tw_id = :tw_id WHERE id = :uid",
                    tw_id=tw_id, uid=uid
                )
        except Exception as e:
            print(f"Migration note: {e}")

        conn.run("""
            CREATE TABLE IF NOT EXISTS profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                headline TEXT, bio TEXT, location TEXT,
                skills TEXT[], avatar_url TEXT, website TEXT,
                is_verified BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS experience (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL, company TEXT NOT NULL,
                location TEXT, start_date TEXT, end_date TEXT,
                is_current BOOLEAN DEFAULT FALSE, description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS education (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                institution TEXT NOT NULL, degree TEXT, field TEXT,
                start_year INTEGER, end_year INTEGER, description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS courses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL, provider TEXT,
                completion_date TEXT, certificate_url TEXT, description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS verify_requests (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                item_type TEXT,
                item_id INTEGER,
                item_title TEXT,
                item_company TEXT,
                document_url TEXT, notes TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Migration: add new columns if not exist
        for col in [
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_type TEXT",
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_id INTEGER",
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_title TEXT",
            "ALTER TABLE verify_requests ADD COLUMN IF NOT EXISTS item_company TEXT",
        ]:
            try: conn.run(col)
            except: pass
        print("✅ Database ready.")
    finally:
        conn.close()


def _unique_tw_id(conn, user_type: str, country_code: str) -> str:
    """يولّد tw_id فريد مع التحقق من عدم التكرار."""
    while True:
        tw_id = generate_tw_id(user_type, country_code)
        existing = conn.run(
            "SELECT id FROM users WHERE tw_id = :tw_id", tw_id=tw_id
        )
        if not existing:
            return tw_id


# ══ المستخدمون ══
def create_user(
    full_name: str, email: str, password: str,
    user_type: str, country_code: str = 'DEFAULT'
) -> dict:
    conn = get_conn()
    try:
        tw_id = _unique_tw_id(conn, user_type, country_code)
        rows = conn.run(
            "INSERT INTO users (tw_id, full_name, email, password_hash, user_type, country_code) "
            "VALUES (:tw_id, :name, :email, :pw, :utype, :cc) "
            "RETURNING id, tw_id, full_name, email, user_type, created_at",
            tw_id=tw_id, name=full_name,
            email=email.lower().strip(),
            pw=hash_password(password),
            utype=user_type, cc=country_code
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
            "SELECT id, tw_id, full_name, email, password_hash, user_type, country_code, created_at "
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
        # ولّد tw_id لو ما عنده (حسابات قديمة)
        if not user.get("tw_id"):
            tw_id = _unique_tw_id(conn, user.get("user_type", "emp"), user.get("country_code", "DEFAULT"))
            conn.run("UPDATE users SET tw_id = :tw_id WHERE id = :uid", tw_id=tw_id, uid=user["id"])
            user["tw_id"] = tw_id
        return _serialize(user)
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, email, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()


# ══ الملفات الشخصية ══
def _get_extras(conn, user_id: int) -> dict:
    rows = conn.run(
        "SELECT id, title, company, location, start_date, end_date, is_current, description, created_at "
        "FROM experience WHERE user_id = :uid ORDER BY id DESC", uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    experience = [_serialize(_row_to_dict(cols, r)) for r in rows]

    rows = conn.run(
        "SELECT id, institution, degree, field, start_year, end_year, description, created_at "
        "FROM education WHERE user_id = :uid ORDER BY id DESC", uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    education = [_serialize(_row_to_dict(cols, r)) for r in rows]

    rows = conn.run(
        "SELECT id, title, provider, completion_date, certificate_url, description, created_at "
        "FROM courses WHERE user_id = :uid ORDER BY id DESC", uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    courses = [_serialize(_row_to_dict(cols, r)) for r in rows]

    return {"experience": experience, "education": education, "courses": courses}


def get_public_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _serialize(_row_to_dict(cols, rows[0]))

        rows = conn.run(
            "SELECT headline, bio, location, skills, avatar_url, website, is_verified "
            "FROM profiles WHERE user_id = :uid", uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        profile = _serialize(_row_to_dict(cols, rows[0])) if rows else {}

        return {**user, **profile, **_get_extras(conn, user_id)}
    finally:
        conn.close()


def get_full_profile(user_id: int) -> Optional[dict]:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, tw_id, full_name, email, user_type, created_at FROM users WHERE id = :uid",
            uid=user_id
        )
        if not rows:
            return None
        cols = [c["name"] for c in conn.columns]
        user = _serialize(_row_to_dict(cols, rows[0]))

        rows = conn.run(
            "SELECT headline, bio, location, skills, avatar_url, website, is_verified, updated_at "
            "FROM profiles WHERE user_id = :uid", uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        profile = _serialize(_row_to_dict(cols, rows[0])) if rows else {}

        rows = conn.run(
            "SELECT id, status, created_at FROM verify_requests "
            "WHERE user_id = :uid ORDER BY id DESC LIMIT 1", uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        verify_req = _serialize(_row_to_dict(cols, rows[0])) if rows else None

        return {**user, **profile, **_get_extras(conn, user_id), "verify_request": verify_req}
    finally:
        conn.close()


def update_profile(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        # Update full_name in users table if provided
        if data.get("full_name"):
            conn.run(
                "UPDATE users SET full_name = :name WHERE id = :uid",
                name=data["full_name"], uid=user_id
            )

        allowed = ["headline", "bio", "location", "skills", "avatar_url", "website"]
        fields = {k: v for k, v in data.items() if k in allowed and v is not None}

        rows = conn.run("SELECT id FROM profiles WHERE user_id = :uid", uid=user_id)
        if rows:
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


# ══ الخبرات ══
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


# ══ الشهادات ══
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


# ══ الدورات ══
def add_course(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO courses (user_id, title, provider, completion_date, certificate_url, description) "
            "VALUES (:uid, :title, :provider, :completion_date, :certificate_url, :description) "
            "RETURNING id, user_id, title, provider, completion_date, certificate_url, description, created_at",
            uid=user_id, title=data["title"], provider=data.get("provider"),
            completion_date=data.get("completion_date"),
            certificate_url=data.get("certificate_url"),
            description=data.get("description")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        conn.close()


# ══ طلبات التحقق ══
def upsert_verify_request(user_id: int, item_type: str, item_id: int, item_title: str, item_company: str = None) -> dict:
    """
    Creates or updates a pending verify request.
    Deduplication by: user_id + item_type + item_title (handles timestamp ids)
    """
    conn = get_conn()
    try:
        # Search by title (more reliable than id which might be timestamp)
        existing = conn.run(
            "SELECT id FROM verify_requests "
            "WHERE user_id=:uid AND item_type=:itype AND item_title=:ititle AND status='pending'",
            uid=user_id, itype=item_type, ititle=item_title
        )
        if existing:
            # Update existing
            conn.run(
                "UPDATE verify_requests SET item_id=:iid, item_company=:icompany, created_at=NOW() WHERE id=:rid",
                iid=item_id, icompany=item_company or '', rid=existing[0][0]
            )
            return {"id": existing[0][0], "action": "updated"}
        else:
            # Create new
            rows = conn.run(
                "INSERT INTO verify_requests (user_id, item_type, item_id, item_title, item_company, status) "
                "VALUES (:uid, :itype, :iid, :ititle, :icompany, 'pending') "
                "RETURNING id",
                uid=user_id, itype=item_type, iid=item_id,
                ititle=item_title, icompany=item_company or ''
            )
            return {"id": rows[0][0], "action": "created"}
    finally:
        conn.close()

# Keep old name as alias for compatibility
def create_verify_request(user_id: int, data: dict) -> dict:
    return upsert_verify_request(
        user_id=user_id,
        item_type=data.get("item_type", ""),
        item_id=data.get("item_id", 0),
        item_title=data.get("item_title", ""),
        item_company=data.get("item_company", "")
    )


def get_user_id_by_tw_id(tw_id: str) -> Optional[int]:
    """يرجع الـ id الرقمي من الـ tw_id."""
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE tw_id = :tw_id", tw_id=tw_id)
        return rows[0][0] if rows else None
    finally:
        conn.close()


def get_profile_by_tw_id(tw_id: str) -> Optional[dict]:
    """يجيب الملف الشخصي العام بالـ tw_id."""
    uid = get_user_id_by_tw_id(tw_id)
    return get_public_profile(uid) if uid else None


def get_full_profile_by_tw_id(tw_id: str) -> Optional[dict]:
    """يجيب الملف الشخصي الكامل بالـ tw_id."""
    uid = get_user_id_by_tw_id(tw_id)
    return get_full_profile(uid) if uid else None
