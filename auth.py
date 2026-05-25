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
# ── Connection Pool ──
_pool = []
_pool_lock = None
_MAX_POOL = 5
_db_params = {}

def _parse_db_url():
    global _db_params
    if _db_params: return
    url = os.environ.get("SUPABASE_DB_URL","").strip().replace(" ","")
    if not url: raise RuntimeError("SUPABASE_DB_URL is not set")
    without_scheme = url.split("://",1)[1]
    userinfo, hostinfo = without_scheme.split("@",1)
    username, password = userinfo.split(":",1)
    host_port, dbname = hostinfo.split("/",1)
    dbname = dbname.split("?")[0]
    host, port = (host_port.rsplit(":",1) if ":" in host_port else (host_port, "5432"))
    _db_params = dict(host=host, port=int(port), user=username, password=password, database=dbname, ssl_context=True)


# ── Query Cache (Redis-ready) ──
import time as _time_mod, json as _json_mod
_query_cache = {}
_CACHE_TTL = 300  # seconds (5 min)

def _cache_get(key):
    # Try Redis first
    try:
        from server import _redis_client
        if _redis_client:
            val = _redis_client.get(key)
            return _json_mod.loads(val) if val else None
    except: pass
    # Fallback: in-memory
    if key in _query_cache:
        val, ts = _query_cache[key]
        if _time_mod.time() - ts < _CACHE_TTL:
            return val
        del _query_cache[key]
    return None

def _cache_set(key, val):
    # Try Redis first
    try:
        from server import _redis_client
        if _redis_client:
            _redis_client.setex(key, _CACHE_TTL, _json_mod.dumps(val, default=str))
            return
    except: pass
    # Fallback: in-memory
    _query_cache[key] = (val, _time_mod.time())

def _cache_del(prefix):
    # Try Redis first
    try:
        from server import _redis_client
        if _redis_client:
            keys = _redis_client.keys(prefix + '*')
            if keys: _redis_client.delete(*keys)
            return
    except: pass
    # Fallback: in-memory
    for k in list(_query_cache.keys()):
        if k.startswith(prefix):
            del _query_cache[k]

def get_conn():
    _parse_db_url()
    global _pool
    if _pool:
        try:
            conn = _pool.pop()
            conn.run("SELECT 1")
            return conn
        except Exception:
            pass
    return pg8000.native.Connection(**_db_params)

def release_conn(conn):
    global _pool
    if len(_pool) < _MAX_POOL:
        try:
            _pool.append(conn)
            return
        except Exception:
            pass
    try: conn.close()
    except: pass


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
            CREATE TABLE IF NOT EXISTS user_skills (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                skill TEXT NOT NULL,
                level TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS user_langs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                language TEXT NOT NULL,
                level TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS user_links (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                link_type TEXT,
                url TEXT NOT NULL,
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
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                job_type TEXT DEFAULT 'full_time',
                salary_min INTEGER,
                salary_max INTEGER,
                currency TEXT DEFAULT 'USD',
                experience_years INTEGER DEFAULT 0,
                skills TEXT[],
                status TEXT DEFAULT 'active',
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP
            )
        """)
        conn.run("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT DEFAULT 'pending',
                cover_letter TEXT,
                applied_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(job_id, user_id)
            )
        """)
        # KYC table
        conn.run("""
            CREATE TABLE IF NOT EXISTS kyc_submissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                step TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                email_code TEXT,
                email_verified BOOLEAN DEFAULT FALSE,
                phone TEXT,
                phone_code TEXT,
                phone_verified BOOLEAN DEFAULT FALSE,
                id_front_url TEXT,
                selfie_url TEXT,
                admin_note TEXT,
                submitted_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP,
                UNIQUE(user_id)
            )
        """)
        # Add KYC fields to users if not exist
        for col in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS kyc_step TEXT DEFAULT 'none'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE",
        ]:
            try: conn.run(col)
            except: pass

        # Messages table
        conn.run("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Notifications table
        conn.run("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                title TEXT,
                body TEXT,
                link TEXT,
                is_read BOOLEAN DEFAULT FALSE,
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
        release_conn(conn)


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
        release_conn(conn)


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
        release_conn(conn)


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
        release_conn(conn)


# ══ الملفات الشخصية ══
def _get_extras(conn, user_id: int) -> dict:
    # Experience
    rows = conn.run(
        "SELECT id, title, company, location, start_date, end_date, is_current, description, created_at "
        "FROM experience WHERE user_id = :uid ORDER BY id DESC", uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    experience = [_serialize(_row_to_dict(cols, r)) for r in rows]

    # Education
    rows = conn.run(
        "SELECT id, institution, degree, field, start_year, end_year, description, created_at "
        "FROM education WHERE user_id = :uid ORDER BY id DESC", uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    education = [_serialize(_row_to_dict(cols, r)) for r in rows]

    # Courses
    rows = conn.run(
        "SELECT id, title, provider, completion_date, certificate_url, description, created_at "
        "FROM courses WHERE user_id = :uid ORDER BY id DESC", uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    courses = [_serialize(_row_to_dict(cols, r)) for r in rows]

    # Skills
    rows = conn.run(
        "SELECT id, skill, level FROM user_skills WHERE user_id = :uid ORDER BY id",
        uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    skills = [_serialize(_row_to_dict(cols, r)) for r in rows]

    # Langs
    rows = conn.run(
        "SELECT id, language, level FROM user_langs WHERE user_id = :uid ORDER BY id",
        uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    langs = [_serialize(_row_to_dict(cols, r)) for r in rows]

    # Links
    rows = conn.run(
        "SELECT id, link_type, url FROM user_links WHERE user_id = :uid ORDER BY id",
        uid=user_id
    )
    cols = [c["name"] for c in conn.columns]
    links = [_serialize(_row_to_dict(cols, r)) for r in rows]

    return {
        "experience": experience,
        "education": education,
        "courses": courses,
        "skills": skills,
        "langs": langs,
        "links": links,
    }


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
        release_conn(conn)


def get_full_profile(user_id: int) -> Optional[dict]:
    cached = _cache_get('profile:'+str(user_id))
    if cached is not None: return cached
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
            "SELECT headline, bio, location, skills, avatar_url, website, is_verified, "
            "updated_at, dob, phone, country, city, avail, title, sections_order, custom_sections, "
            "profile_color, profile_style "
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

        # Get skills, langs, links
        rows = conn.run("SELECT id, skill, level FROM user_skills WHERE user_id=:uid ORDER BY id", uid=user_id)
        cols = [c["name"] for c in conn.columns]
        skills = [_row_to_dict(cols, r) for r in rows]

        rows = conn.run("SELECT id, language, level FROM user_langs WHERE user_id=:uid ORDER BY id", uid=user_id)
        cols = [c["name"] for c in conn.columns]
        langs = [_row_to_dict(cols, r) for r in rows]

        rows = conn.run("SELECT id, link_type, url FROM user_links WHERE user_id=:uid ORDER BY id", uid=user_id)
        cols = [c["name"] for c in conn.columns]
        links = [_row_to_dict(cols, r) for r in rows]

        return {**user, **profile, **_get_extras(conn, user_id),
                "skills": skills, "langs": langs, "links": links,
                "verify_request": verify_req}
    finally:
        release_conn(conn)


def update_profile(user_id: int, data: dict) -> dict:
    _cache_del('profile:'+str(user_id))
    conn = get_conn()
    try:
        # Update full_name in users table if provided
        if data.get("full_name"):
            conn.run(
                "UPDATE users SET full_name = :name WHERE id = :uid",
                name=data["full_name"], uid=user_id
            )

        allowed = ["headline", "bio", "location", "skills", "avatar_url", "website", "phone", "sections_order", "custom_sections", "dob", "country", "city", "avail", "profile_color", "profile_style"]
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
        release_conn(conn)
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
        release_conn(conn)


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
        release_conn(conn)


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
        release_conn(conn)


# ══ طلبات التحقق ══
def create_verify_request(user_id: int, data: dict) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO verify_requests (user_id, document_url, notes, status) "
            "VALUES (:uid, :doc_url, :notes, 'pending') "
            "RETURNING id, user_id, document_url, notes, status, created_at",
            uid=user_id, doc_url=data.get("document_url"), notes=data.get("notes")
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)


def get_user_id_by_tw_id(tw_id: str) -> Optional[int]:
    """يرجع الـ id الرقمي من الـ tw_id."""
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE tw_id = :tw_id", tw_id=tw_id)
        return rows[0][0] if rows else None
    finally:
        release_conn(conn)


def get_profile_by_tw_id(tw_id: str) -> Optional[dict]:
    """يجيب الملف الشخصي العام بالـ tw_id."""
    uid = get_user_id_by_tw_id(tw_id)
    return get_public_profile(uid) if uid else None


def get_full_profile_by_tw_id(tw_id: str) -> Optional[dict]:
    """يجيب الملف الشخصي الكامل بالـ tw_id."""
    uid = get_user_id_by_tw_id(tw_id)
    return get_full_profile(uid) if uid else None


# ══ الوظائف ══

def add_job(company_id: int, data: dict) -> dict:
    _cache_del('jobs:')
    conn = get_conn()
    try:
        skills = data.get("skills") or []
        rows = conn.run(
            "INSERT INTO jobs (company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status) "
            "VALUES (:cid, :title, :desc, :loc, :jtype, :smin, :smax, :cur, :exp, :skills, 'active') "
            "RETURNING id, company_id, title, description, location, job_type, "
            "salary_min, salary_max, currency, experience_years, skills, status, created_at",
            cid=company_id, title=data.get("title",""),
            desc=data.get("description",""), loc=data.get("location",""),
            jtype=data.get("job_type","full_time"),
            smin=data.get("salary_min"), smax=data.get("salary_max"),
            cur=data.get("currency","USD"),
            exp=data.get("experience_years",0),
            skills=skills if skills else None
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def get_jobs(filters: dict = None) -> list:
    cache_key = 'jobs:' + str(sorted((filters or {}).items()))
    cached = _cache_get(cache_key)
    if cached is not None: return cached
    conn = get_conn()
    try:
        where = "WHERE j.status='active'"
        params = {}
        if filters:
            if filters.get("search"):
                where += " AND (j.title ILIKE :search OR j.description ILIKE :search)"
                params["search"] = f"%{filters['search']}%"
            if filters.get("location"):
                where += " AND j.location ILIKE :loc"
                params["loc"] = f"%{filters['location']}%"
            if filters.get("job_type"):
                where += " AND j.job_type = :jtype"
                params["jtype"] = filters["job_type"]
            if filters.get("company_id"):
                where += " AND j.company_id = :cid"
                params["cid"] = filters["company_id"]
        rows = conn.run(
            f"SELECT j.id, j.company_id, j.title, j.description, j.location, "
            f"j.job_type, j.salary_min, j.salary_max, j.currency, "
            f"j.experience_years, j.skills, j.status, j.views, j.created_at, "
            f"u.full_name AS company_name "
            f"FROM jobs j JOIN users u ON u.id=j.company_id "
            f"{where} ORDER BY j.created_at DESC LIMIT 50",
            **params
        )
        cols = [c["name"] for c in conn.columns]
        result = [_serialize(_row_to_dict(cols, r)) for r in rows]
        _cache_set(cache_key, result)
        return result
    finally:
        release_conn(conn)

def get_job(job_id: int) -> dict:
    conn = get_conn()
    try:
        conn.run("UPDATE jobs SET views=views+1 WHERE id=:id", id=job_id)
        rows = conn.run(
            "SELECT j.*, u.full_name AS company_name "
            "FROM jobs j JOIN users u ON u.id=j.company_id "
            "WHERE j.id=:id", id=job_id
        )
        if not rows: return None
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def apply_job(job_id: int, user_id: int, cover_letter: str = "") -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO job_applications (job_id, user_id, cover_letter) "
            "VALUES (:jid, :uid, :cl) "
            "ON CONFLICT (job_id, user_id) DO NOTHING "
            "RETURNING id, job_id, user_id, status, applied_at",
            jid=job_id, uid=user_id, cl=cover_letter
        )
        if not rows:
            return {"already_applied": True}
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def get_job_applicants(job_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.id, ja.job_id, ja.user_id, ja.status, ja.cover_letter, ja.applied_at, "
            "u.full_name, u.email, u.user_type "
            "FROM job_applications ja JOIN users u ON u.id=ja.user_id "
            "WHERE ja.job_id=:jid ORDER BY ja.applied_at DESC",
            jid=job_id
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def get_user_applications(user_id: int) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ja.id, ja.job_id, ja.status, ja.applied_at, "
            "j.title, j.location, j.company_id, u.full_name AS company_name "
            "FROM job_applications ja "
            "JOIN jobs j ON j.id=ja.job_id "
            "JOIN users u ON u.id=j.company_id "
            "WHERE ja.user_id=:uid ORDER BY ja.applied_at DESC",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def update_application_status(app_id: int, status: str) -> dict:
    conn = get_conn()
    try:
        conn.run("UPDATE job_applications SET status=:s WHERE id=:id", s=status, id=app_id)
        return {"success": True}
    finally:
        release_conn(conn)

def delete_job(job_id: int, company_id: int) -> bool:
    conn = get_conn()
    try:
        conn.run("DELETE FROM jobs WHERE id=:id AND company_id=:cid", id=job_id, cid=company_id)
        return True
    finally:
        release_conn(conn)


# ══ KYC System ══
import random, string

def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def start_kyc(user_id: int) -> dict:
    """Start or get KYC submission"""
    conn = get_conn()
    try:
        rows = conn.run("SELECT * FROM kyc_submissions WHERE user_id=:uid", uid=user_id)
        if rows:
            cols = [c["name"] for c in conn.columns]
            return _serialize(_row_to_dict(cols, rows[0]))
        # Create new
        rows = conn.run(
            "INSERT INTO kyc_submissions (user_id, step) VALUES (:uid, 'email') RETURNING *",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def send_email_code(user_id: int, email: str) -> str:
    """Generate email verification code"""
    code = generate_code()
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET email_code=:code WHERE user_id=:uid",
            code=code, uid=user_id
        )
        return code  # In production: send via email API
    finally:
        release_conn(conn)

def verify_email_code(user_id: int, code: str) -> bool:
    """Verify email code"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT email_code FROM kyc_submissions WHERE user_id=:uid",
            uid=user_id
        )
        if not rows or rows[0][0] != code:
            return False
        conn.run(
            "UPDATE kyc_submissions SET email_verified=TRUE, step='phone' WHERE user_id=:uid",
            uid=user_id
        )
        conn.run("UPDATE users SET email_verified=TRUE WHERE id=:uid", uid=user_id)
        return True
    finally:
        release_conn(conn)

def send_phone_code(user_id: int, phone: str) -> str:
    """Generate phone verification code"""
    code = generate_code()
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET phone=:phone, phone_code=:code WHERE user_id=:uid",
            phone=phone, code=code, uid=user_id
        )
        return code  # In production: send via SMS API
    finally:
        release_conn(conn)

def verify_phone_code(user_id: int, code: str) -> bool:
    """Verify phone code"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT phone_code FROM kyc_submissions WHERE user_id=:uid",
            uid=user_id
        )
        if not rows or rows[0][0] != code:
            return False
        conn.run(
            "UPDATE kyc_submissions SET phone_verified=TRUE, step='id_upload' WHERE user_id=:uid",
            uid=user_id
        )
        conn.run("UPDATE users SET phone_verified=TRUE WHERE id=:uid", uid=user_id)
        return True
    finally:
        release_conn(conn)

def upload_kyc_docs(user_id: int, id_url: str, selfie_url: str = None) -> dict:
    """Save uploaded ID and selfie"""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET id_front_url=:id_url, selfie_url=:selfie, step='review', submitted_at=NOW() WHERE user_id=:uid",
            id_url=id_url, selfie=selfie_url, uid=user_id
        )
        # Create admin review request
        rows = conn.run(
            "SELECT u.full_name FROM users u WHERE u.id=:uid",
            uid=user_id
        )
        return {"status": "submitted", "step": "review"}
    finally:
        release_conn(conn)

def get_kyc_status(user_id: int) -> dict:
    """Get current KYC status"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ks.*, u.is_verified, u.email_verified, u.phone_verified "
            "FROM kyc_submissions ks JOIN users u ON u.id=ks.user_id WHERE ks.user_id=:uid",
            uid=user_id
        )
        if not rows:
            return {"step": "none", "status": "not_started"}
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def admin_approve_kyc(user_id: int, note: str = "") -> dict:
    """Admin approves KYC"""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET status='approved', admin_note=:note, reviewed_at=NOW() WHERE user_id=:uid",
            note=note, uid=user_id
        )
        conn.run("UPDATE users SET is_verified=TRUE WHERE id=:uid", uid=user_id)
        return {"success": True}
    finally:
        release_conn(conn)

def admin_reject_kyc(user_id: int, note: str = "") -> dict:
    """Admin rejects KYC"""
    conn = get_conn()
    try:
        conn.run(
            "UPDATE kyc_submissions SET status='rejected', step='rejected', admin_note=:note, reviewed_at=NOW() WHERE user_id=:uid",
            note=note, uid=user_id
        )
        return {"success": True}
    finally:
        release_conn(conn)

def get_all_kyc_submissions() -> list:
    """Get all KYC submissions for admin"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT ks.*, u.full_name, u.email, u.user_type "
            "FROM kyc_submissions ks JOIN users u ON u.id=ks.user_id "
            "ORDER BY ks.submitted_at DESC"
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)


# ══ Messages System ══

def send_message(sender_id: int, receiver_id: int, content: str) -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO messages (sender_id, receiver_id, content) "
            "VALUES (:sid, :rid, :content) RETURNING id, sender_id, receiver_id, content, is_read, created_at",
            sid=sender_id, rid=receiver_id, content=content
        )
        cols = [c["name"] for c in conn.columns]
        msg = _serialize(_row_to_dict(cols, rows[0]))
        # Create notification for receiver
        create_notification(receiver_id, 'message', 'رسالة جديدة', content[:60], '/messages.html')
        return msg
    finally:
        release_conn(conn)

def get_conversations(user_id: int) -> list:
    """Get all unique conversations for a user"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT DISTINCT ON (other_id) "
            "CASE WHEN sender_id=:uid THEN receiver_id ELSE sender_id END AS other_id, "
            "content, created_at, is_read, sender_id, "
            "u.full_name, u.user_type "
            "FROM messages m "
            "JOIN users u ON u.id = CASE WHEN m.sender_id=:uid THEN m.receiver_id ELSE m.sender_id END "
            "WHERE sender_id=:uid OR receiver_id=:uid "
            "ORDER BY other_id, created_at DESC",
            uid=user_id
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def get_messages(user_id: int, other_id: int) -> list:
    """Get messages between two users"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT m.*, u.full_name as sender_name "
            "FROM messages m JOIN users u ON u.id=m.sender_id "
            "WHERE (sender_id=:uid AND receiver_id=:oid) "
            "OR (sender_id=:oid AND receiver_id=:uid) "
            "ORDER BY created_at ASC LIMIT 100",
            uid=user_id, oid=other_id
        )
        cols = [c["name"] for c in conn.columns]
        # Mark as read
        conn.run(
            "UPDATE messages SET is_read=TRUE "
            "WHERE receiver_id=:uid AND sender_id=:oid AND is_read=FALSE",
            uid=user_id, oid=other_id
        )
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def get_unread_count(user_id: int) -> int:
    """Get count of unread messages"""
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM messages WHERE receiver_id=:uid AND is_read=FALSE",
            uid=user_id
        )
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)

# ══ Notifications System ══

def create_notification(user_id: int, type_: str, title: str, body: str, link: str = "") -> dict:
    conn = get_conn()
    try:
        rows = conn.run(
            "INSERT INTO notifications (user_id, type, title, body, link) "
            "VALUES (:uid, :type, :title, :body, :link) RETURNING id, user_id, type, title, body, link, is_read, created_at",
            uid=user_id, type=type_, title=title, body=body, link=link
        )
        cols = [c["name"] for c in conn.columns]
        return _serialize(_row_to_dict(cols, rows[0]))
    finally:
        release_conn(conn)

def get_notifications(user_id: int, limit: int = 50) -> list:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT * FROM notifications WHERE user_id=:uid "
            "ORDER BY created_at DESC LIMIT :lim",
            uid=user_id, lim=limit
        )
        cols = [c["name"] for c in conn.columns]
        return [_serialize(_row_to_dict(cols, r)) for r in rows]
    finally:
        release_conn(conn)

def mark_notifications_read(user_id: int) -> bool:
    conn = get_conn()
    try:
        conn.run("UPDATE notifications SET is_read=TRUE WHERE user_id=:uid", uid=user_id)
        return True
    finally:
        release_conn(conn)

def get_unread_notifications(user_id: int) -> int:
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT COUNT(*) FROM notifications WHERE user_id=:uid AND is_read=FALSE",
            uid=user_id
        )
        return rows[0][0] if rows else 0
    finally:
        release_conn(conn)

# ── Site Settings (logos, sizes) ──
def get_site_setting(key: str) -> str:
    try:
        conn = get_conn()
        rows = conn.run("SELECT value FROM site_settings WHERE key=:k LIMIT 1", k=key)
        release_conn(conn)
        return rows[0][0] if rows else ''
    except: return ''

def set_site_setting(key: str, value: str):
    try:
        conn = get_conn()
        conn.run("""
            INSERT INTO site_settings(key,value) VALUES(:k,:v)
            ON CONFLICT(key) DO UPDATE SET value=:v, updated_at=NOW()
        """, k=key, v=value)
        release_conn(conn)
        return True
    except Exception as e:
        print(f"[Settings] Error: {e}")
        return False

def ensure_site_settings_table():
    try:
        conn = get_conn()
        conn.run('''
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        release_conn(conn)
    except Exception as e:
        print(f"[DB] site_settings: {e}")

def ensure_reports_table():
    try:
        conn = get_conn()
        conn.run('''
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                reporter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                reported_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                reported_type TEXT DEFAULT 'user',
                report_type TEXT NOT NULL,
                reason TEXT,
                target_url TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        release_conn(conn)
    except Exception as e:
        print(f"[DB] reports table: {e}")

