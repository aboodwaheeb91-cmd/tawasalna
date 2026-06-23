# See ARCHITECTURE.md for system architecture rules

"""
تواصلنا - Arabic Employment Platform
"""

import os
from fastapi import FastAPI, HTTPException, Request, Response, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import base64, mimetypes
from typing import List, Optional
from datetime import datetime
import hashlib, secrets, json, os, time, asyncio
try:
    import asyncpg as _asyncpg
except ImportError:
    _asyncpg = None

import urllib.request

# ── IP to country code ──
IP_TO_COUNTRY_CACHE = {}

def get_country_from_ip(ip: str) -> str:
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return 'DEFAULT'
    if ip in IP_TO_COUNTRY_CACHE:
        return IP_TO_COUNTRY_CACHE[ip]
    COUNTRY_MAP = {
        'JO':'JO','SA':'SA','AE':'AE','KW':'KW','QA':'QA',
        'BH':'BH','OM':'OM','EG':'EG','IQ':'IQ','SY':'SY',
        'LB':'LB','PS':'PS','YE':'YE','MA':'MA','DZ':'DZ',
        'TN':'TN','LY':'LY','SD':'SD',
    }
    try:
        url = f'http://ip-api.com/json/{ip}?fields=countryCode'
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
        code = data.get('countryCode','DEFAULT')
        result = COUNTRY_MAP.get(code,'DEFAULT')
        IP_TO_COUNTRY_CACHE[ip] = result
        return result
    except Exception:
        return 'DEFAULT'

def get_client_ip(request) -> str:
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else '127.0.0.1'


from auth import (
    init_db, get_conn,
    create_user, authenticate_user, get_user_by_id,
    get_public_profile, get_full_profile, update_profile,
    get_profile_by_tw_id, get_full_profile_by_tw_id, get_user_id_by_tw_id,
    add_experience, update_experience, reorder_experience, add_education, add_course, update_education, update_course, create_verify_request,
    add_job, get_jobs, get_job, apply_job,
    start_kyc, send_email_code, verify_email_code,
    send_phone_code, verify_phone_code, upload_kyc_docs,
    get_kyc_status, admin_approve_kyc, admin_reject_kyc, get_all_kyc_submissions, ensure_site_settings_table, ensure_reports_table,
    send_message, send_message_pipeline, mark_message_delivered, get_conversations, get_messages, get_unread_count,
    mark_message_read_immediate,
    create_notification, get_notifications, mark_notifications_read, get_unread_notifications,
    get_job_applicants, get_user_applications,
    update_application_status, delete_job,
    get_site_setting, set_site_setting, release_conn,
    _cache_del, get_profile_style,
    get_company_profile_row, get_company_extras,
    follow_company, unfollow_company, rate_company,
    get_company_posts, create_company_post, get_post_owner, delete_company_post,
    follow_profile, unfollow_profile, get_profile_followers_count, is_profile_following,
    get_profile_followers_list, get_profile_following_list,
    record_profile_view, get_profile_views_count,
    save_profile_interest, remove_profile_interest,
    is_profile_interest_active, get_profile_interest_type, get_profile_interest_label
)
from auth import ContentValidationError, validate_professional_text

# ── Config ──
ADMIN_PASSWORD = "tw@admin2025"
ADMIN_URL_TOKEN = "kPuOWhpIYjdLQXmh"
# Stable token derived from password - no server storage needed
ADMIN_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
JWT_SECRET = os.environ.get("JWT_SECRET") or ADMIN_TOKEN[:32]


# ── JWT (stdlib only - no extra deps) ──
import hmac, base64 as _b64

def _jwt_encode(payload: dict) -> str:
    import json, time
    payload['iat'] = int(time.time())
    payload['exp'] = int(time.time()) + 86400 * 7  # 7 days
    header = _b64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    body = _b64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    sig = _b64.urlsafe_b64encode(
        hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), 'sha256').digest()
    ).rstrip(b'=').decode()
    return f"{header}.{body}.{sig}"

def _jwt_decode(token: str) -> dict:
    import json, time
    try:
        parts = token.split('.')
        if len(parts) != 3: return {}
        # Verify signature first
        expected_sig = _b64.urlsafe_b64encode(
            hmac.new(JWT_SECRET.encode(), f"{parts[0]}.{parts[1]}".encode(), 'sha256').digest()
        ).rstrip(b'=').decode()
        if parts[2] != expected_sig: return {}  # Invalid signature
        # Decode payload
        body = parts[1] + '=='
        payload = json.loads(_b64.urlsafe_b64decode(body.encode()))
        if payload.get('exp', 0) < time.time(): return {}  # Expired
        return payload
    except: return {}


def verify_token(request: Request):
    auth = request.headers.get("Authorization","")
    token = auth.replace("Bearer ","") if auth.startswith("Bearer ") else ""
    payload = _jwt_decode(token) if token else {}
    if not payload: raise HTTPException(401, "Token invalid or expired")
    return {"valid": True, "user_id": payload.get("user_id"), "user_type": payload.get("user_type")}


# ── App ──
app = FastAPI(title="تواصلنا API", version="1.0.0")

# Fix [A-4]: Prevent browser HTTP cache from serving stale .html/.js files
# This is the correct architectural fix — works for every page, not just profile
from starlette.middleware.base import BaseHTTPMiddleware
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if any(path.endswith(ext) for ext in ['.html', '.js', '.css']):
            response.headers['Cache-Control'] = 'no-cache, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
        return response
app.add_middleware(NoCacheMiddleware)


# ── Redis-Ready Cache (auto-detects Redis) ──
import os as _os
_redis_client = None
try:
    import redis as _redis
    _redis_url = _os.environ.get("REDIS_URL")
    if _redis_url:
        _redis_client = _redis.from_url(_redis_url, decode_responses=True)
        _redis_client.ping()
        print("[Cache] Redis connected ✅")
    else:
        print("[Cache] No REDIS_URL - using in-memory cache")
except ImportError:
    print("[Cache] redis not installed - using in-memory cache")
except Exception as e:
    print(f"[Cache] Redis failed ({e}) - using in-memory cache")


# ── Global Error Handlers ──
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(status_code=422, content={"error": "بيانات غير صحيحة", "details": str(exc)})

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    print(f"[ERROR] {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"error": "خطأ في السيرفر"})

# ── Security Headers ──
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    try:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    except Exception:
        pass
    return response

# ── Simple Rate Limiting ──
from collections import defaultdict
import time as _time
_rate_store = defaultdict(list)
_RATE_LIMIT = 60  # requests per minute

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Only rate limit auth endpoints
    if request.url.path in ["/auth/login", "/auth/register", "/kyc/email/send", "/kyc/phone/send"]:
        ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
        now = _time.time()
        _rate_store[ip] = [t for t in _rate_store[ip] if now - t < 60]
        if len(_rate_store[ip]) >= _RATE_LIMIT:
            from fastapi.responses import JSONResponse as _JR
            return _JR(status_code=429, content={"error": "طلبات كثيرة جداً، حاول بعد دقيقة"})
        _rate_store[ip].append(now)
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,  # Must be False with allow_origins=["*"]
)

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    from fastapi.responses import Response
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
           '<circle cx="16" cy="16" r="16" fill="#2563ff"/>'
           '<text x="16" y="22" font-size="18" text-anchor="middle" fill="#fff" font-family="sans-serif">ت</text>'
           '</svg>')
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})

# ── asyncpg pool — single-RTT INSERT pipeline ──────────────────────────────
_asyncpg_pool = None  # None until startup; fallback to pg8000 if unavailable


def _asyncpg_dsn() -> str:
    """Return a postgresql:// DSN compatible with asyncpg."""
    raw = os.environ.get("SUPABASE_DB_URL", "")
    # asyncpg requires postgresql:// not postgres://
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    return raw


async def _init_asyncpg_pool():
    global _asyncpg_pool
    if not _asyncpg:
        print("⚠️ asyncpg not installed — using pg8000 fallback")
        return
    try:
        _asyncpg_pool = await _asyncpg.create_pool(
            dsn=_asyncpg_dsn(),
            min_size=1,
            max_size=5,
            statement_cache_size=0,  # safe with Supabase PgBouncer/Transaction Pooler
            command_timeout=10,
        )
        print("✅ asyncpg pool ready (single-RTT INSERT pipeline active)")
    except Exception as e:
        _asyncpg_pool = None
        print(f"⚠️ asyncpg pool init failed ({type(e).__name__}: {e}) — using pg8000 fallback")


def _serialize_asyncpg_row(row) -> dict:
    """Convert asyncpg Record to JSON-serializable dict."""
    result = {}
    for k, v in dict(row).items():
        if hasattr(v, 'isoformat'):
            result[k] = v.isoformat()
        elif v is None:
            result[k] = None
        else:
            result[k] = v
    return result


async def _pipeline_asyncpg(
    sender_id: int, receiver_id: int, content: str, mark_as_read: bool
) -> tuple:
    """Single-RTT INSERT via asyncpg (pipelines Parse+Bind+Execute+Sync in one TCP write).

    Hot  path: 1 query  (INSERT as read) — ~1 RTT.
    Cold path: 2 queries (INSERT unread + COUNT) — ~2 RTTs.
    """
    t0 = time.perf_counter()
    async with _asyncpg_pool.acquire() as conn:
        t_after_conn = time.perf_counter()
        if mark_as_read:
            row = await conn.fetchrow(
                "INSERT INTO messages "
                "(sender_id, receiver_id, content, is_read, delivered_at, read_at) "
                "VALUES ($1, $2, $3, TRUE, NOW(), NOW()) "
                "RETURNING id, sender_id, receiver_id, content, "
                "is_read, delivered_at, read_at, created_at",
                sender_id, receiver_id, content
            )
            t_after_insert = time.perf_counter()
            msg = _serialize_asyncpg_row(row)
            timing = {
                "conn_ms":        round((t_after_conn   - t0)             * 1000),
                "sync_set_ms":    0,
                "insert_exec_ms": round((t_after_insert - t_after_conn)   * 1000),
                "insert_ms":      round((t_after_insert - t_after_conn)   * 1000),
                "update_ms":      0,
                "count_ms":       0,
                "db_ms":          round((t_after_insert - t0)             * 1000),
                "driver":         "asyncpg",
            }
            return msg, None, timing

        else:
            row = await conn.fetchrow(
                "INSERT INTO messages (sender_id, receiver_id, content) "
                "VALUES ($1, $2, $3) "
                "RETURNING id, sender_id, receiver_id, content, "
                "is_read, delivered_at, read_at, created_at",
                sender_id, receiver_id, content
            )
            t_after_insert = time.perf_counter()
            msg = _serialize_asyncpg_row(row)
            unread = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE receiver_id=$1 AND is_read=FALSE",
                receiver_id
            )
            t_after_count = time.perf_counter()
            timing = {
                "conn_ms":        round((t_after_conn   - t0)              * 1000),
                "sync_set_ms":    0,
                "insert_exec_ms": round((t_after_insert - t_after_conn)    * 1000),
                "insert_ms":      round((t_after_insert - t_after_conn)    * 1000),
                "update_ms":      0,
                "count_ms":       round((t_after_count  - t_after_insert)  * 1000),
                "db_ms":          round((t_after_count  - t0)              * 1000),
                "driver":         "asyncpg",
            }
            return msg, int(unread or 0), timing


# ── Startup ──
@app.on_event("startup")
async def on_startup():
    try:
        init_db()
        print("✅ DB initialized")
    except Exception as e:
        print(f"⚠️ DB init failed: {e}")
    try:
        _migrate_news_posts()
        print("✅ news_posts table ready")
    except Exception as e:
        print(f"⚠️ news_posts migration failed: {e}")
    try:
        _migrate_feed_indexes()
        print("✅ feed indexes ready")
    except Exception as e:
        print(f"⚠️ feed indexes migration failed: {e}")
    await _init_asyncpg_pool()

# ── Helpers ──
_html_cache = {}

def read_html(name: str) -> str:
    if name in _html_cache:
        return _html_cache[name]
    try:
        with open(name, "r", encoding="utf-8") as f:
            content = f.read()
        _html_cache[name] = content
        return content
    except FileNotFoundError:
        return f"<h1>الصفحة غير موجودة: {name}</h1>"

def check_admin(request: Request):
    """Check admin token from header X-Admin-Token"""
    token = request.headers.get("X-Admin-Token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


def _migrate_feed_indexes():
    """Create feed query indexes (idempotent — CREATE INDEX IF NOT EXISTS).
    These indexes support the /home/feed endpoint for production scale.
    """
    conn = get_conn()
    try:
        conn.run("CREATE INDEX IF NOT EXISTS idx_jobs_status_created     ON jobs(status, created_at DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_cposts_created          ON company_posts(created_at DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_news_status_created     ON news_posts(status, created_at DESC)")
    finally:
        release_conn(conn)


def _migrate_news_posts():
    """Create news_posts table if it doesn't exist (idempotent)."""
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS news_posts (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                body TEXT,
                category TEXT DEFAULT 'general',
                country TEXT,
                source_url TEXT,
                status TEXT DEFAULT 'draft',
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
    finally:
        release_conn(conn)

# ══════════════════════════════════════════
# HTML Pages
# ══════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
def landing():
    content = read_html("landing.html")
    return HTMLResponse(content=content, headers={"Cache-Control": "public, max-age=300"})

@app.get("/landing.html", response_class=HTMLResponse)
def landing_html(): return read_html("landing.html")

@app.get("/index.html", response_class=HTMLResponse)
def index_html(): return read_html("index.html")

@app.get("/login", response_class=HTMLResponse)
def login_page(): return read_html("index.html")

@app.get("/login.html", response_class=HTMLResponse)
def login_html(): return read_html("index.html")

@app.get("/home", response_class=HTMLResponse)
def home(): return read_html("home-v2.html")

@app.get("/home.html", response_class=HTMLResponse)
def home_html(): return read_html("home-v2.html")

@app.get("/home/feed")
def home_feed(filter: str = "all", limit: int = 20, token=Depends(verify_token)):
    user_id   = int(token.get("user_id") or 0)
    user_type = token.get("user_type", "emp")
    if not user_id:
        raise HTTPException(401, "رمز غير صالح")

    allowed_filters = {"all", "opportunities", "posts", "news"}
    if filter not in allowed_filters:
        filter = "all"
    lim = min(max(int(limit), 1), 50)

    items = []
    conn = get_conn()
    try:
        # ── Opportunities (jobs table — opp_type="job" now, extensible later) ──
        if filter in ("all", "opportunities"):
            opp_lim = lim if filter == "opportunities" else max(1, lim // 3)
            rows = conn.run(
                """SELECT j.id, j.title, j.location, j.job_type,
                          j.salary_min, j.salary_max, j.currency,
                          j.skills, j.created_at,
                          u.full_name AS company_name,
                          u.tw_id    AS company_tw_id,
                          u.id       AS company_id,
                          COALESCE(p.avatar_url,'') AS company_logo
                   FROM jobs j
                   JOIN users u ON j.company_id = u.id
                   LEFT JOIN profiles p ON j.company_id = p.user_id
                   WHERE j.status = 'open'
                   ORDER BY j.created_at DESC
                   LIMIT :lim""",
                lim=opp_lim
            )
            cols = ["id","title","location","job_type","salary_min","salary_max","currency",
                    "skills","created_at","company_name","company_tw_id","company_id","company_logo"]
            for r in (rows or []):
                d = dict(zip(cols, r))
                d["type"] = "opportunity"
                d["opp_type"] = "job"
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                if isinstance(d.get("skills"), list):
                    d["skills"] = [str(s) for s in d["skills"]]
                items.append(d)

        # ── Company posts ──
        if filter in ("all", "posts"):
            post_lim = lim if filter == "posts" else max(1, lim // 3)
            rows = conn.run(
                """SELECT cp.id, cp.body, cp.tags, cp.created_at,
                          u.full_name AS author_name,
                          u.tw_id    AS author_tw_id,
                          u.id       AS author_id,
                          COALESCE(p.avatar_url,'') AS author_avatar
                   FROM company_posts cp
                   JOIN users u ON cp.company_id = u.id
                   LEFT JOIN profiles p ON cp.company_id = p.user_id
                   ORDER BY cp.created_at DESC
                   LIMIT :lim""",
                lim=post_lim
            )
            cols = ["id","body","tags","created_at","author_name","author_tw_id","author_id","author_avatar"]
            for r in (rows or []):
                d = dict(zip(cols, r))
                d["type"] = "post"
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                if isinstance(d.get("tags"), list):
                    d["tags"] = [str(t) for t in d["tags"]]
                items.append(d)

        # ── News (admin-published content from news_posts table) ──
        if filter in ("all", "news"):
            news_lim = lim if filter == "news" else max(1, lim // 3)
            rows = conn.run(
                """SELECT id, title, summary, body, category, country, source_url, created_at
                   FROM news_posts
                   WHERE status = 'published'
                   ORDER BY created_at DESC
                   LIMIT :lim""",
                lim=news_lim
            )
            cols = ["id","title","summary","body","category","country","source_url","created_at"]
            for r in (rows or []):
                d = dict(zip(cols, r))
                d["type"] = "news"
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                items.append(d)

    finally:
        release_conn(conn)

    # For "all": interleave by created_at so recent content surfaces first
    if filter == "all" and items:
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return {"items": items, "filter": filter, "total": len(items), "next_cursor": None}


@app.get("/profile", response_class=HTMLResponse)
def profile(id: str = ""):
    """Serve profile.html with SSR theme injection to prevent FOUC.
    read_html() uses cache — we modify after reading (cache stores base HTML).
    """
    html = read_html("profile.html")  # base HTML from cache
    if id:
        style = get_profile_style(id)  # 1 lightweight DB query
        # True fast path: only inject if non-default theme
        # s1 = default, already in base HTML → no replacement needed
        if style not in ("1", "", None):
            html = html.replace(
                'class="profile-loading"',
                f'class="profile-loading s{style}"',
                1
            )
    return html

@app.get("/profile.html", response_class=HTMLResponse)
def profile_html(id: str = ""):
    """Serve profile.html with SSR theme injection to prevent FOUC."""
    html = read_html("profile.html")
    if id:
        style = get_profile_style(id)
        if style not in ("1", "", None):
            html = html.replace(
                'class="profile-loading"',
                f'class="profile-loading s{style}"',
                1
            )
    return html

@app.get("/company", response_class=HTMLResponse)
def company(): return read_html("company.html")

@app.get("/company.html", response_class=HTMLResponse)
def company_html(): return read_html("company.html")

@app.get("/company-profile", response_class=HTMLResponse)
def company_profile(): return read_html("company-profile.html")

@app.get("/company-profile.html", response_class=HTMLResponse)
def company_profile_html(): return read_html("company-profile.html")

@app.get("/profile-showcase", response_class=HTMLResponse)
def profile_showcase(): return read_html("profile-showcase.html")

@app.get("/profile-showcase.html", response_class=HTMLResponse)
def profile_showcase_html(): return read_html("profile-showcase.html")

@app.get("/u/{tw_id}", response_class=HTMLResponse)
def public_profile_short_url(tw_id: str):
    """Public share URL for Profile V2. Serves profile-showcase.html with the
    numeric user id injected so the page can call /profile/{id} API without
    exposing tw_id in the API request."""
    numeric_id = get_user_id_by_tw_id(tw_id)
    if not numeric_id:
        raise HTTPException(status_code=404, detail="الملف الشخصي غير موجود")
    base = read_html("profile-showcase.html")
    # int() call prevents any XSS — numeric_id is always an integer
    injected = base.replace(
        '</head>',
        '<script>window._scProfileIdFromRoute=' + str(int(numeric_id)) + ';</script></head>',
        1
    )
    return HTMLResponse(content=injected)

# ══ Company Profile API — Rule #20 ══
# ══ Phase 2 Step 4: shared company id resolver (refactor — same behavior) ══
def _resolve_company_id(company_id: str) -> int:
    """Resolve tw_id or numeric → numeric users.id. Raises 404 if not found.
    Extracted from GET /company/profile (identical logic, no behavior change)."""
    resolved_id = None
    conn0 = get_conn()
    try:
        if company_id.isdigit():
            resolved_id = int(company_id)
        else:
            rows0 = conn0.run(
                "SELECT id FROM users WHERE tw_id = :tw AND user_type IN ('co','edu')",
                tw=company_id)
            if rows0:
                resolved_id = rows0[0][0]
    finally:
        release_conn(conn0)
    if not resolved_id:
        raise HTTPException(404, "الشركة غير موجودة")
    return resolved_id


@app.get("/company/profile/{company_id}")
def get_company_profile(company_id: str, request: Request):
    """
    GET /company/profile/{id}
    Rule #20: Optional JWT — public read.
    Accepts both numeric id and tw_id (TW-CO-XXXXX).
    Returns: profile + company + stats + viewer_type + is_owner + permissions
    """
    # ── Resolve numeric company id (shared resolver — Step 4 refactor) ──
    resolved_id = _resolve_company_id(company_id)

    # ── Determine viewer_type from JWT (optional) ──
    viewer_type = "guest"
    is_owner    = False
    token_uid   = None
    token_utype = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw = auth_header[7:]
        payload = _jwt_decode(raw) if raw else {}
        if payload:
            token_uid   = payload.get("user_id")
            token_utype = payload.get("user_type")
            if token_uid and int(token_uid) == resolved_id:
                viewer_type = "owner"
                is_owner    = True
            else:
                viewer_type = "public-user"

    # ── Permissions per viewer_type (Rule #20) ──
    permissions = {
        "can_edit":      is_owner,
        "can_post_jobs": is_owner,
        "can_follow":    viewer_type == "public-user",
        "can_rate":      False,  # Phase 3: enabled for ex-employees only
    }

    # ── Fetch company base profile (lightweight — no extras) ──
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT u.id, u.tw_id, u.full_name, u.email, u.user_type, u.created_at, "
            "p.bio, p.location, p.avatar_url, p.website, p.is_verified, p.phone, p.city, p.country "
            "FROM users u "
            "LEFT JOIN profiles p ON p.user_id = u.id "
            "WHERE u.id = :uid AND u.user_type IN ('co','edu')",
            uid=resolved_id
        )
        if not rows:
            raise HTTPException(404, "الشركة غير موجودة")

        cols = [c["name"] if isinstance(c, dict) else c[0] for c in conn.columns]
        profile = dict(zip(cols, rows[0]))

        # ── jobs_count from DB (Rule #19: no hardcoded) ──
        j_rows = conn.run(
            "SELECT COUNT(*) FROM jobs WHERE company_id = :cid AND status = 'active'",
            cid=resolved_id
        )
        jobs_count = j_rows[0][0] if j_rows else 0

        # ── verified_count from DB ──
        v_rows = conn.run(
            "SELECT COUNT(*) FROM verify_requests "
            "WHERE item_company = :name AND status = 'verified'",
            name=profile.get("full_name", "")
        )
        verified_count = v_rows[0][0] if v_rows else 0

    finally:
        release_conn(conn)

    # ── company_profiles fields (Phase 2: from company_profiles table) ──
    company = get_company_profile_row(resolved_id)

    # ── Company extras: followers, rating, viewer flags (Phase 2) ──
    extras = get_company_extras(resolved_id, token_uid)

    # ── Stats (Rule #19: real values from DB) ──
    stats = {
        "jobs_count":       jobs_count,
        "followers_count":  extras["followers_count"],
        "verified_count":   verified_count,
        "rating_avg":       extras["rating_avg"],
        "rating_count":     extras["rating_count"],
    }

    # ── Viewer-specific flags into permissions (Phase 2, in-scope) ──
    permissions["is_following"] = extras["is_following"]
    permissions["my_rating"]    = extras["my_rating"]

    return {
        "status":      "success",
        "profile":     profile,
        "company":     company,
        "stats":       stats,
        "viewer_type": viewer_type,
        "is_owner":    is_owner,
        "permissions": permissions,
    }


class CoProfileInput(BaseModel):
    company_type:  Optional[str] = None
    industry:      Optional[str] = None
    founded_year:  Optional[int] = None
    company_size:  Optional[str] = None
    contact_email: Optional[str] = None
    headquarters:  Optional[str] = None
    description:   Optional[str] = None


@app.put("/company/profile/{company_id}")
def update_co_profile(company_id: int, data: CoProfileInput, token=Depends(verify_token)):
    """
    PUT /company/profile/{id}
    Updates company_profiles row only — never touches profiles table or jobs.
    Auth: JWT Bearer only. Ownership: token.user_id == company_id AND user_type == 'co'.
    Requires industry (classification) to be non-empty.
    """
    tok_uid   = token.get("user_id")
    tok_utype = token.get("user_type")
    if str(tok_uid) != str(company_id) or tok_utype != "co":
        raise HTTPException(403, "غير مصرح")
    payload = data.dict(exclude_none=True)
    if not payload.get("industry"):
        raise HTTPException(400, "يجب تحديد تصنيف الجهة")
    updated = update_company_profile(company_id, payload)
    if not updated:
        raise HTTPException(400, "لا توجد بيانات للحفظ")
    company = get_company_profile_row(company_id)
    return {"status": "success", "company": company}


@app.get("/edu", response_class=HTMLResponse)
def edu(): return read_html("edu.html")

@app.get("/edu.html", response_class=HTMLResponse)
def edu_html(): return read_html("edu.html")

@app.get("/edu-profile", response_class=HTMLResponse)
def edu_profile(): return read_html("edu-profile.html")

@app.get("/edu-profile.html", response_class=HTMLResponse)
def edu_profile_html(): return read_html("edu-profile.html")

@app.get("/notifications", response_class=HTMLResponse)
def notifications(): return read_html("notifications.html")

@app.get("/notifications.html", response_class=HTMLResponse)
def notifications_html(): return read_html("notifications.html")

@app.get("/messages", response_class=HTMLResponse)
def messages(): return read_html("messages.html")

@app.get("/messages.html", response_class=HTMLResponse)
def messages_html(): return read_html("messages.html")

@app.get("/employees-group", response_class=HTMLResponse)
def employees_group(): return read_html("employees-group.html")

@app.get("/employees-group.html", response_class=HTMLResponse)
def employees_group_html(): return read_html("employees-group.html")

@app.get("/jobs.html", response_class=HTMLResponse)
def jobs_page(): return read_html("jobs.html")

@app.get("/job-detail", response_class=HTMLResponse)
def job_detail(): return read_html("job-detail.html")

@app.get("/job-detail.html", response_class=HTMLResponse)
def job_detail_html(): return read_html("job-detail.html")

@app.get("/admin-view", response_class=HTMLResponse)
@app.get("/admin-view.html", response_class=HTMLResponse)
def admin_view(): return read_html("admin-view.html")

@app.get("/settings", response_class=HTMLResponse)
def settings(): return read_html("settings.html")

@app.get("/settings.html", response_class=HTMLResponse)
def settings_html(): return read_html("settings.html")

@app.get("/admin.html", response_class=HTMLResponse)
def admin_html(): return read_html("admin.html")

@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN, response_class=HTMLResponse)
def admin_page(): return read_html("admin.html")

# ══════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════
class RegisterInput(BaseModel):
    full_name: str
    email: str
    password: str
    user_type: Optional[str] = "emp"

class LoginInput(BaseModel):
    email: str
    password: str

class ProfileUpdateInput(BaseModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    short_bio: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[List[str]] = None
    avatar_url: Optional[str] = None
    website: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    sections_order: Optional[str] = None
    custom_sections: Optional[str] = None
    dob: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    avail: Optional[str] = None
    title: Optional[str] = None
    profile_color: Optional[str] = None
    profile_style: Optional[str] = None
    profession_id: Optional[int] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    cover_url: Optional[str] = None

class ExperienceInput(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = False
    description: Optional[str] = None

class ExperienceReorderInput(BaseModel):
    ordered_ids: List[int]

class ExperienceUpdateInput(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None
    description: Optional[str] = None

class EducationInput(BaseModel):
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    is_current: bool = False
    description: Optional[str] = None

class ImageUploadInput(BaseModel):
    user_id: int
    bucket: str
    filename: str
    data_url: str

class ErrorLogInput(BaseModel):
    msg: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    page: Optional[str] = None
    ua: Optional[str] = None
    type: Optional[str] = None
    ts: Optional[str] = None

class MessageInput(BaseModel):
    receiver_id: int
    content: str

class KYCEmailInput(BaseModel):
    user_id: int
    email: str

class KYCCodeInput(BaseModel):
    user_id: int
    code: str

class KYCPhoneInput(BaseModel):
    user_id: int
    phone: str

class KYCDocsInput(BaseModel):
    user_id: int
    id_front_url: str
    selfie_url: Optional[str] = None

class KYCAdminInput(BaseModel):
    note: Optional[str] = ""

class CompanyRateInput(BaseModel):
    score: int
    comment: Optional[str] = None

class CompanyPostInput(BaseModel):
    body: str
    tags: Optional[list] = None

class JobInput(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = "full_time"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = "USD"
    experience_years: Optional[int] = 0
    skills: Optional[List[str]] = None

class JobApplyInput(BaseModel):
    user_id: int
    cover_letter: Optional[str] = ""

class AppStatusInput(BaseModel):
    status: str  # pending, viewed, accepted, rejected

class SkillInput(BaseModel):
    skill: str
    level: Optional[str] = None
    note: Optional[str] = None

class LangInput(BaseModel):
    language: str
    level: Optional[str] = None

class LinkInput(BaseModel):
    link_type: Optional[str] = None
    url: str

class CourseInput(BaseModel):
    title: str
    provider: Optional[str] = None
    completion_date: Optional[str] = None
    certificate_url: Optional[str] = None
    description: Optional[str] = None

class VerifyRequestInput(BaseModel):
    user_id: int
    item_type: Optional[str] = None   # exp / edu / course
    item_id: Optional[int] = None
    item_title: Optional[str] = None
    item_company: Optional[str] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None


    user_id: Optional[str] = None
    top_k: Optional[int] = 5

class FeedbackInput(BaseModel):
    cv_text: str
    job_id: int
    score: float
    action: str
    user_id: Optional[str] = None

class AdminLoginInput(BaseModel):
    password: str

class VerifyUpdateInput(BaseModel):
    status: str

class AdminMessageInput(BaseModel):
    user_id: int
    subject: str
    message: str

# ══════════════════════════════════════════
# Health
# ══════════════════════════════════════════

@app.get("/jobs/match/{user_id}")
def match_jobs_for_user(user_id: int):
    """Match jobs based on user skills"""
    try:
        profile = get_full_profile(user_id)
        if not profile:
            return {"jobs": [], "count": 0}
        user_skills = set(s.lower() for s in (profile.get("skills") or []))
        all_jobs = get_jobs({"status": "active"})
        scored = []
        for job in all_jobs:
            job_skills = set(s.lower() for s in (job.get("skills") or []))
            if not job_skills:
                score = 10
            else:
                common = user_skills & job_skills
                score = int(len(common) / len(job_skills) * 100) if job_skills else 0
            job["match_score"] = score
            scored.append(job)
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return {"jobs": scored[:20], "count": len(scored)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/sitemap.xml")
def sitemap():
    urls = [
        "https://tawasolna.com/",
        "https://tawasolna.com/jobs.html",
        "https://tawasolna.com/index.html",
    ]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    for url in urls:
        xml += f'<url><loc>{url}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>'
    xml += '</urlset>'
    return Response(content=xml, media_type="application/xml")

@app.get("/robots.txt")
def robots():
    return Response(content="User-agent: *\nAllow: /\nSitemap: https://tawasolna.com/sitemap.xml\n",
                   media_type="text/plain")

@app.get("/tw_shared.js")
def tw_shared_js():
    try:
        with open("tw_shared.js","r") as f: content=f.read()
        return Response(content=content, media_type="application/javascript",
                       headers={"Cache-Control":"public, max-age=3600"})
    except:
        return Response(content="", media_type="application/javascript")

@app.get("/company-profile.js")
def company_profile_js():
    """Serve company-profile.js action layer — Rule #21"""
    try:
        with open("company-profile.js","r") as f: content=f.read()
        return Response(content=content, media_type="application/javascript",
                       headers={"Cache-Control":"no-cache, must-revalidate"})
    except:
        return Response(content="// company-profile.js not found", media_type="application/javascript")

@app.get("/sw.js")
def service_worker():
    try:
        with open("sw.js", "r") as f:
            content = f.read()
        return Response(content=content, media_type="application/javascript",
                       headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                                "Service-Worker-Allowed": "/"})
    except:
        return Response(content="", media_type="application/javascript")

@app.get("/manifest.json")
def manifest():
    try:
        with open("manifest.json", "r") as f:
            content = f.read()
        return Response(content=content, media_type="application/json",
                       headers={"Cache-Control": "public, max-age=86400"})
    except:
        return Response(content="{}", media_type="application/json")

@app.get("/icon-192.png")
@app.get("/icon-512.png")
def icon():
    # Return a simple placeholder - replace with real icons
    import base64
    # 1x1 green pixel PNG
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    return Response(content=base64.b64decode(png_b64), media_type="image/png",
                   headers={"Cache-Control": "public, max-age=604800"})


# ── WebSocket Real-time Messages ──
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict

class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, list] = {}
        self.active_conversations: Dict[int, int] = {}
        # Tracks which specific WebSocket connection last set active_conversations
        # so that only the messenger WS — never the badge WS — can clear it on disconnect.
        self._conv_ws_owner: Dict[int, object] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        if user_id not in self.active:
            self.active[user_id] = []
        self.active[user_id].append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        if user_id in self.active:
            self.active[user_id] = [w for w in self.active[user_id] if w != ws]
            # Only clear active_conversation if the WS that OWNS it disconnected,
            # or if there are no connections left at all.
            # This prevents the global badge WS (tw_shared.js) from clearing
            # the messenger conversation state when it briefly disconnects.
            if self._conv_ws_owner.get(user_id) is ws or not self.active[user_id]:
                self.active_conversations.pop(user_id, None)
                self._conv_ws_owner.pop(user_id, None)

    async def send_to_user(self, user_id: int, data: dict) -> bool:
        import json
        if user_id not in self.active or not self.active[user_id]:
            return False
        sent = False
        dead = []
        for ws in self.active[user_id]:
            try:
                await ws.send_text(json.dumps(data))
                sent = True
            except:
                dead.append(ws)
        for d in dead:
            self.active[user_id].remove(d)
        return sent

ws_manager = ConnectionManager()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            import json
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "active_conversation":
                    other_id = msg.get("other_id")
                    if other_id:
                        ws_manager.active_conversations[user_id] = int(other_id)
                        ws_manager._conv_ws_owner[user_id] = websocket

                elif msg_type == "inactive_conversation":
                    if ws_manager._conv_ws_owner.get(user_id) is websocket:
                        ws_manager.active_conversations.pop(user_id, None)
                        ws_manager._conv_ws_owner.pop(user_id, None)

                elif msg_type == "typing":
                    to_id = msg.get("to_user_id")
                    if to_id:
                        await ws_manager.send_to_user(int(to_id), {"type": "typing", "from_user_id": user_id})

                elif msg_type == "typing_stop":
                    to_id = msg.get("to_user_id")
                    if to_id:
                        await ws_manager.send_to_user(int(to_id), {"type": "typing_stop", "from_user_id": user_id})

                else:
                    # Legacy WS send path (HTTP is primary)
                    receiver_id = msg.get("receiver_id")
                    content = msg.get("content", "")
                    if receiver_id and content:
                        receiver_id = int(receiver_id)
                        saved = send_message(user_id, receiver_id, content)
                        msg_id = saved.get("id")
                        receiver_has_conv_open = ws_manager.active_conversations.get(receiver_id) == user_id
                        if receiver_has_conv_open:
                            mark_message_read_immediate(msg_id)
                            await ws_manager.send_to_user(receiver_id, {"type": "message", "from": user_id, "id": msg_id, "content": content, "created_at": saved.get("created_at", ""), "is_read": True})
                            await websocket.send_text(json.dumps({"type": "status_update", "id": msg_id, "status": "read"}))
                        else:
                            was_delivered = await ws_manager.send_to_user(receiver_id, {"type": "message", "from": user_id, "id": msg_id, "content": content, "created_at": saved.get("created_at", "")})
                            if was_delivered:
                                mark_message_delivered(msg_id)
                                await websocket.send_text(json.dumps({"type": "status_update", "id": msg_id, "status": "delivered"}))
                        await websocket.send_text(json.dumps({"type": "sent", "id": msg_id}))
                        unread = get_unread_count(receiver_id)
                        await ws_manager.send_to_user(receiver_id, {"type": "badge_update", "badge": "messages", "count": unread})
            except Exception as e:
                print(f"[WS] Error: {e}")
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)


# In-memory error log (last 100 errors)
_error_log = []


# ══ Reports System ══
class ReportInput(BaseModel):
    reported_id: int
    reported_type: str  # user, job, company
    report_type: str    # sexual, fraud, harassment, spam, other
    reason: str
    target_url: Optional[str] = None


# ══ Phase 2 Step 4: Company social endpoints (follow / rate) ══
@app.post("/company/follow/{company_id}")
def company_follow(company_id: str, token=Depends(verify_token)):
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: POST /company/follow")
        raise HTTPException(401, "رمز غير صالح")
    if user_type != "emp":
        print(f"[SECURITY] FOLLOW_FORBIDDEN: user_type={user_type} tried follow")
        raise HTTPException(403, "الموظفون فقط يمكنهم المتابعة")
    resolved_id = _resolve_company_id(company_id)
    if int(user_id) == resolved_id:
        print(f"[SECURITY] SELF_FOLLOW: user={user_id}")
        raise HTTPException(400, "لا يمكنك متابعة نفسك")
    count = follow_company(int(user_id), resolved_id)
    return {"status": "success", "following": True, "followers_count": count}


@app.delete("/company/follow/{company_id}")
def company_unfollow(company_id: str, token=Depends(verify_token)):
    user_id = token.get("user_id")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: DELETE /company/follow")
        raise HTTPException(401, "رمز غير صالح")
    resolved_id = _resolve_company_id(company_id)
    count = unfollow_company(int(user_id), resolved_id)
    return {"status": "success", "following": False, "followers_count": count}


@app.post("/company/rate/{company_id}")
def company_rate(company_id: str, data: CompanyRateInput, token=Depends(verify_token)):
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: POST /company/rate")
        raise HTTPException(401, "رمز غير صالح")
    if user_type != "emp":
        print(f"[SECURITY] RATE_FORBIDDEN: user_type={user_type} tried rate")
        raise HTTPException(403, "الموظفون فقط يمكنهم التقييم")
    if data.score < 1 or data.score > 5:
        print(f"[SECURITY] INVALID_SCORE: score={data.score}")
        raise HTTPException(400, "التقييم يجب أن يكون بين 1 و 5")
    resolved_id = _resolve_company_id(company_id)
    if int(user_id) == resolved_id:
        print(f"[SECURITY] SELF_RATE: user={user_id}")
        raise HTTPException(400, "لا يمكنك تقييم نفسك")
    result = rate_company(int(user_id), resolved_id, data.score, data.comment)
    return {"status": "success", "rating_avg": result["rating_avg"],
            "rating_count": result["rating_count"], "my_score": data.score}


# ══ Phase 3: Company Posts endpoints ══
@app.get("/company/posts/{company_id}")
def company_posts_list(company_id: str):
    # Public read — lazy loaded when posts tab opened
    resolved_id = _resolve_company_id(company_id)
    posts = get_company_posts(resolved_id)
    return {"status": "success", "posts": posts}


@app.post("/company/posts")
def company_post_create(data: CompanyPostInput, token=Depends(verify_token)):
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: POST /company/posts")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] POST_FORBIDDEN: user_type={user_type} tried create post")
        raise HTTPException(403, "الشركات فقط يمكنها النشر")
    body = (data.body or "").strip()
    if not body:
        raise HTTPException(400, "المنشور فارغ")
    post = create_company_post(int(user_id), body, data.tags)
    return {"status": "success", "post": post}


@app.delete("/company/posts/{post_id}")
def company_post_delete(post_id: int, token=Depends(verify_token)):
    user_id = token.get("user_id")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: DELETE /company/posts")
        raise HTTPException(401, "رمز غير صالح")
    owner = get_post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "المنشور غير موجود")
    if int(user_id) != owner:
        print(f"[SECURITY] POST_DELETE_FORBIDDEN: user={user_id} tried delete post {post_id} owned by {owner}")
        raise HTTPException(403, "غير مصرح بحذف هذا المنشور")
    delete_company_post(post_id)
    return {"status": "success"}

@app.post("/reports/submit")
async def submit_report(data: ReportInput, request: Request, token=Depends(verify_token)):
    """Submit a report against a user or content"""
    try:
        ensure_reports_table()
        # Get reporter from JWT
        auth = request.headers.get("Authorization","")
        token = auth.replace("Bearer ","") if auth.startswith("Bearer ") else ""
        reporter_id = None
        if token:
            payload = _jwt_decode(token)
            reporter_id = payload.get("user_id")
        
        conn = get_conn()
        conn.run("""
            INSERT INTO reports (reporter_id, reported_id, reported_type, report_type, reason, target_url, status)
            VALUES (:rid, :tid, :rtype, :rpt, :reason, :url, 'pending')
        """, rid=reporter_id, tid=data.reported_id, rtype=data.reported_type,
            rpt=data.report_type, reason=data.reason, url=data.target_url)
        release_conn(conn)
        
        # Create notification for admin
        try:
            create_notification(
            data.reported_user_id if hasattr(data,'reported_user_id') else 1,
            f"بلاغ جديد: {data.report_type}", "report"
        )
        except: pass
        
        return {"status": "success", "message": "تم إرسال البلاغ"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/admin/reports")
def admin_get_reports(request: Request):
    """Get all reports"""
    check_admin(request)
    try:
        # Ensure table exists
        ensure_reports_table()
        conn = get_conn()
        try:
            rows = conn.run("""
                SELECT r.id, r.reporter_id, r.reported_id, r.reported_type,
                       r.report_type, r.reason, r.target_url, r.status, r.created_at,
                       u1.full_name as reporter_name,
                       u2.full_name as reported_name
                FROM reports r
                LEFT JOIN users u1 ON r.reporter_id = u1.id
                LEFT JOIN users u2 ON r.reported_id = u2.id
                ORDER BY r.created_at DESC
            """)
            cols = ['id','reporter_id','reported_id','reported_type','report_type',
                    'reason','target_url','status','created_at','reporter_name','reported_name']
            reports = [dict(zip(cols,row)) for row in rows]
            for rep in reports:
                if rep.get('created_at'):
                    rep['created_at'] = str(rep['created_at'])
        finally:
            release_conn(conn)
        return {"reports": reports, "count": len(reports)}
    except Exception as e:
        print(f"[Reports] Error: {e}")
        # Return empty if table doesn't exist yet
        return {"reports": [], "count": 0}

@app.put("/admin/reports/{report_id}/resolve")
def resolve_report(report_id: int, request: Request):
    """Mark report as resolved"""
    check_admin(request)
    try:
        conn = get_conn()
        try:
            conn.run("UPDATE reports SET status='resolved' WHERE id=:id", id=report_id)
        finally:
            release_conn(conn)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/log/error")
async def log_client_error(data: ErrorLogInput):
    err = {"page": data.page, "msg": data.msg, "line": data.line, "ts": data.ts, "type": data.type or "js"}
    _error_log.append(err)
    if len(_error_log) > 100: _error_log.pop(0)
    print(f"[CLIENT ERROR] {data.page} | {data.msg} | line:{data.line}")
    return {"ok": True}

@app.get("/admin/errors")
def admin_errors(request: Request):
    check_admin(request)
    return {"errors": list(reversed(_error_log)), "count": len(_error_log)}

@app.post("/auth/verify-token")

def _calc_profile_score(uid: int, conn) -> dict:
    """Shared scoring helper — used by /score and /metrics (no duplication).
    Returns dict with score, tips, level, and the DB counts used for scoring."""
    rows = conn.run(
        "SELECT headline, bio, avatar_url, location, title, is_verified "
        "FROM profiles WHERE user_id=:uid", uid=uid)
    if not rows:
        return {"score": 0, "tips": [], "level": "يحتاج تحسين",
                "exp_count": 0, "edu_count": 0, "skill_count": 0, "link_count": 0}
    cols = [c["name"] if isinstance(c, dict) else c[0] for c in conn.columns]
    prof = dict(zip(cols, rows[0]))
    exp_count   = (conn.run("SELECT COUNT(*) FROM experience  WHERE user_id=:uid", uid=uid) or [[0]])[0][0]
    edu_count   = (conn.run("SELECT COUNT(*) FROM education   WHERE user_id=:uid", uid=uid) or [[0]])[0][0]
    skill_count = (conn.run("SELECT COUNT(*) FROM user_skills WHERE user_id=:uid", uid=uid) or [[0]])[0][0]
    link_count  = (conn.run("SELECT COUNT(*) FROM user_links  WHERE user_id=:uid", uid=uid) or [[0]])[0][0]
    score = 0
    tips  = []
    checks = [
        (bool(prof.get("avatar_url")),                    10, "أضف صورة شخصية"),
        (bool(prof.get("headline") or prof.get("title")), 10, "أضف مسماك الوظيفي"),
        (bool(prof.get("bio")),                           10, "أضف نبذة عنك"),
        (bool(prof.get("location")),                       5, "أضف موقعك"),
        (exp_count > 0,                                   20, "أضف خبرة عملية"),
        (edu_count > 0,                                   15, "أضف شهاداتك"),
        (skill_count >= 3,                                15, "أضف 3 مهارات على الأقل"),
        (link_count > 0,                                   5, "أضف رابط LinkedIn أو GitHub"),
        (bool(prof.get("is_verified")),                    5, "وثّق هويتك"),
    ]
    for ok, pts, tip in checks:
        if ok: score += pts
        else:  tips.append({"tip": tip, "points": pts})
    tips.sort(key=lambda x: -x["points"])
    return {
        "score":       score,
        "tips":        tips[:3],
        "level":       "ممتاز" if score >= 90 else "جيد" if score >= 70 else "متوسط" if score >= 50 else "يحتاج تحسين",
        "exp_count":   exp_count,
        "edu_count":   edu_count,
        "skill_count": skill_count,
        "link_count":  link_count,
    }


@app.get("/profile/{user_id}/score")
def profile_score(user_id: int):
    """Profile completion score. Uses _calc_profile_score — no algorithm duplication."""
    try:
        conn = get_conn()
        try:
            data = _calc_profile_score(user_id, conn)
        finally:
            release_conn(conn)
        return {"score": data["score"], "tips": data["tips"], "level": data["level"]}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, str(e))


class ResetPasswordInput(BaseModel):
    password: str


@app.post("/admin/logo")
async def upload_logo(data: ImageUploadInput, request: Request):
    """Upload logo - filename: logo_wide or logo_tall"""
    check_admin(request)
    try:
        filename = data.filename or "logo_wide"
        logo_url = data.data_url
        import httpx, base64 as _b64
        s_url = os.environ.get("SUPABASE_URL","")
        s_key = os.environ.get("SUPABASE_SERVICE_KEY","")
        if s_url and s_key and ',' in data.data_url:
            try:
                header, b64data = data.data_url.split(',', 1)
                mime = header.split(':')[1].split(';')[0]
                ext = ".png" if "png" in mime else ".jpg" if "jpg" in mime else ".svg" if "svg" in mime else ".png"
                fname = filename + ext
                file_bytes = _b64.b64decode(b64data)
                async with httpx.AsyncClient(timeout=15) as client:
                    r = await client.post(
                        f"{s_url}/storage/v1/object/site/{fname}",
                        content=file_bytes,
                        headers={"Authorization": f"Bearer {s_key}",
                                "Content-Type": mime, "x-upsert": "true"}
                    )
                    if r.status_code in (200, 201):
                        logo_url = f"{s_url}/storage/v1/object/public/site/{fname}"
                        print(f"[Logo] Saved: {logo_url}")
            except Exception as e:
                print(f"[Logo] Supabase failed: {e}")
        # Always cache in memory
        _html_cache[filename] = logo_url
        # Try save to DB (table may not exist yet)
        try:
            ensure_site_settings_table()
            set_site_setting(filename, logo_url)
        except Exception as db_err:
            print(f"[Logo] DB save failed: {db_err} - cached in memory only")
        return {"status": "success", "url": logo_url}
    except Exception as e:
        print(f"[Logo] Error: {e}")
        raise HTTPException(500, str(e))

@app.get("/admin/logo")
def get_logos():
    """Get both logos - public endpoint"""
    def _get(key):
        v = _html_cache.get(key,'')
        if not v:
            try:
                v = get_site_setting(key)
                if v: _html_cache[key] = v
            except: pass
        return v
    return {"logo_wide": _get("logo_wide"), "logo_tall": _get("logo_tall")}

@app.post("/admin/logo-sizes")
async def save_logo_sizes(data: dict, request: Request):
    check_admin(request)
    return {"status": "ok"}


# ══ Static Files (CSS/JS/Assets) ══
import mimetypes as _mimetypes

@app.get("/static/{filename:path}")
def serve_static(filename: str):
    """Serve static files: CSS, JS, images.
    Lookup order:
      1. {root}/static/{filename}   — organised subdirectories (e.g. static/img/)
      2. {root}/{filename}          — flat root layout (existing files)
    Both locations are traversal-safe via realpath prefix check.
    """
    import os
    allowed = {'.css','.js','.svg','.png','.jpg','.jpeg','.webp','.ico','.woff','.woff2'}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(404, "Not found")

    base_dir   = os.path.realpath(os.path.dirname(__file__))
    static_dir = os.path.join(base_dir, 'static')

    def _safe(candidate_dir: str, rel: str):
        resolved = os.path.realpath(os.path.join(candidate_dir, rel))
        if resolved.startswith(candidate_dir + os.sep) and os.path.isfile(resolved):
            return resolved
        return None

    filepath = _safe(static_dir, filename) or _safe(base_dir, filename)
    if not filepath:
        raise HTTPException(404, f"Static file not found: {filename}")

    mime = _mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
    with open(filepath, 'rb') as f:
        content = f.read()
    return Response(content=content, media_type=mime,
                   headers={"Cache-Control": "public, max-age=86400"})

@app.api_route("/health", methods=["GET","HEAD"])
def health():
    # Test DB connection
    db_ok = False
    try:
        conn = get_conn()
        conn.run("SELECT 1")
        release_conn(conn)
        db_ok = True
    except: pass
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "uptime": "running"
    }

@app.get("/ping")
def ping():
    return "pong"

# ══════════════════════════════════════════
# Auth
# ══════════════════════════════════════════
@app.post("/auth/register")
def register(data: RegisterInput, request: Request):
    if not data.full_name.strip():
        raise HTTPException(400, detail="الاسم الكامل مطلوب")
    if not data.email.strip():
        raise HTTPException(400, detail="البريد الإلكتروني مطلوب")
    if len(data.password) < 6:
        raise HTTPException(400, detail="كلمة المرور يجب أن تكون 6 أحرف على الأقل")
    if data.user_type not in ("emp", "co", "edu"):
        raise HTTPException(400, detail="نوع الحساب غير صحيح")
    try:
        client_ip = get_client_ip(request)
        country_code = get_country_from_ip(client_ip)
        user = create_user(data.full_name, data.email, data.password, data.user_type, country_code)
        token = _jwt_encode({"user_id": user.get("id"), "user_type": user.get("user_type"), "tw_id": user.get("tw_id","")})
        return {"status": "success", "user": user, "token": token}
    except ValueError as e:
        raise HTTPException(409, detail=str(e))
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/auth/login")
def login(data: LoginInput):
    if not data.email.strip() or not data.password:
        raise HTTPException(400, detail="البريد وكلمة المرور مطلوبان")
    user = authenticate_user(data.email, data.password)
    if not user:
        raise HTTPException(401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")
    token = _jwt_encode({"user_id": user.get("id"), "user_type": user.get("user_type"), "tw_id": user.get("tw_id","")})
    return {"status": "success", "user": user, "token": token}

@app.put("/auth/user/{user_id}/name")
async def update_user_name(user_id: int, request: Request, token=Depends(verify_token)):
    # User can only update their own name
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    try:
        data = await request.json()
        full_name = data.get("full_name","").strip()
        if not full_name:
            raise HTTPException(400, "الاسم مطلوب")
        conn = auth.get_conn()
        try:
            conn.run("UPDATE users SET full_name=:name WHERE id=:uid",
                     name=full_name, uid=user_id)
        finally:
            release_conn(conn)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/auth/user/{user_id}")
def get_user(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, detail="المستخدم غير موجود")
    return {"user": user}

@app.get("/user/lookup/{tw_id}")
def lookup_user_by_twid(tw_id: str, token=Depends(verify_token)):
    """Resolve tw_id → basic user info needed to open a direct message thread."""
    uid = get_user_id_by_tw_id(tw_id)
    if not uid:
        raise HTTPException(404, "المستخدم غير موجود")
    user = get_user_by_id(uid)
    if not user:
        raise HTTPException(404, "المستخدم غير موجود")
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "user_type": user["user_type"],
        "tw_id": user["tw_id"]
    }

# ══════════════════════════════════════════
# Profile
# ══════════════════════════════════════════
@app.get("/profile/{user_id}")
def public_profile(user_id: str, request: Request):
    try:
        uid = int(user_id)
        profile = get_public_profile(uid)
    except ValueError:
        profile = get_profile_by_tw_id(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")

    # Optional JWT — determines viewer_type (same pattern as /company/profile)
    viewer_type = "guest"
    is_owner    = False
    token_uid   = None
    payload     = {}

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw     = auth_header[7:]
        payload = _jwt_decode(raw) if raw else {}
        if payload:
            token_uid = payload.get("user_id")
            if token_uid and int(token_uid) == profile["id"]:
                viewer_type = "owner"
                is_owner    = True
            else:
                viewer_type = "public-user"

    # ── Follow data ──
    profile_id      = profile["id"]
    followers_count = get_profile_followers_count(profile_id)
    _is_following   = False
    if viewer_type == "public-user" and token_uid:
        _is_following = is_profile_following(int(token_uid), profile_id)

    # ── Views counter (Step 2) ──
    # Record view only for logged-in non-owner viewers (24h dedup inside record_profile_view)
    if viewer_type == "public-user" and token_uid:
        try:
            record_profile_view(profile_id, int(token_uid))
        except Exception:
            pass
    views_count = get_profile_views_count(profile_id)

    if viewer_type == "owner":
        permissions = {
            "can_edit":    True,
            "can_follow":  False,
            "can_message": False,
            "can_save":    False,
            "can_report":  False,
        }
    elif viewer_type == "public-user":
        permissions = {
            "can_edit":    False,
            "can_follow":  True,
            "can_message": True,
            "can_save":    True,
            "can_report":  True,
        }
    else:
        permissions = {
            "can_edit":    False,
            "can_follow":  False,
            "can_message": False,
            "can_save":    False,
            "can_report":  False,
        }

    # ── Interest (viewer_action) ──
    target_user_type = profile.get("user_type", "emp")
    _interest_active = False
    if viewer_type == "public-user" and token_uid and target_user_type == "emp":
        try:
            _interest_active = is_profile_interest_active(int(token_uid), profile_id)
        except Exception:
            pass

    if viewer_type == "owner" or target_user_type != "emp":
        viewer_action = {"hidden": True,  "can_interact": False, "is_active": False, "label": "", "type": ""}
    elif viewer_type == "guest":
        viewer_action = {"hidden": False, "can_interact": False, "is_active": False,
                         "label": "سجّل للتفاعل", "type": "login_prompt"}
    else:
        actor_user_type = payload.get("user_type", "emp") if payload else "emp"
        viewer_action = {
            "hidden":       False,
            "can_interact": True,
            "is_active":    _interest_active,
            "label":        get_profile_interest_label(actor_user_type, _interest_active),
            "type":         get_profile_interest_type(actor_user_type),
        }

    return {
        "status":          "success",
        "profile":         profile,
        "viewer_type":     viewer_type,
        "is_owner":        is_owner,
        "followers_count": followers_count,
        "is_following":    _is_following,
        "views_count":     views_count,
        "permissions":     permissions,
        "viewer_action":   viewer_action,
    }

@app.get("/profile/{user_id}/metrics")
def profile_metrics(user_id: str, request: Request):
    """Read-only unified metrics endpoint. Does NOT record a view.
    Returns all profile counters + score + viewer.is_following in one request."""
    try:
        uid = int(user_id)
    except ValueError:
        uid = get_user_id_by_tw_id(user_id)
    if not uid:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")

    token_uid   = None
    viewer_type = "guest"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw     = auth_header[7:]
        payload = _jwt_decode(raw) if raw else {}
        if payload:
            token_uid = payload.get("user_id")
            if token_uid and int(token_uid) == uid:
                viewer_type = "owner"
            else:
                viewer_type = "public-user"

    conn = get_conn()
    try:
        def _cnt(table, col="user_id"):
            return ((conn.run(f"SELECT COUNT(*) FROM {table} WHERE {col}=:uid", uid=uid)) or [[0]])[0][0]

        course_count     = _cnt("courses")
        lang_count       = _cnt("user_langs")
        followers_count  = _cnt("profile_follows", "followed_id")
        following_count  = _cnt("profile_follows", "follower_id")
        views_count      = _cnt("profile_views",   "viewed_user_id")

        _is_following = False
        if viewer_type == "public-user" and token_uid:
            f = conn.run(
                "SELECT 1 FROM profile_follows WHERE follower_id=:frid AND followed_id=:fdid",
                frid=int(token_uid), fdid=uid)
            _is_following = bool(f)

        # Score + exp/edu/skill/link counts in same connection (no duplication)
        score_data  = _calc_profile_score(uid, conn)
        exp_count   = score_data["exp_count"]
        edu_count   = score_data["edu_count"]
        skill_count = score_data["skill_count"]
        link_count  = score_data["link_count"]
        score       = score_data["score"]
    finally:
        release_conn(conn)

    return {
        "status": "success",
        "metrics": {
            "views_count":      views_count,
            "followers_count":  followers_count,
            "following_count":  following_count,
            "experience_count": exp_count,
            "education_count":  edu_count,
            "courses_count":    course_count,
            "skills_count":     skill_count,
            "languages_count":  lang_count,
            "links_count":      link_count,
            "score":            score,
        },
        "viewer": {
            "is_following": _is_following,
        }
    }

@app.get("/profile/{user_id}/full")
def full_profile(user_id: str):
    try:
        uid = int(user_id)
        profile = get_full_profile(uid)
    except ValueError:
        profile = get_full_profile_by_tw_id(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": profile}


# ══ Profile Follow Endpoints ══

@app.post("/profile/{user_id}/follow")
def profile_follow(user_id: str, token=Depends(verify_token)):
    viewer_id = token.get("user_id")
    if not viewer_id:
        raise HTTPException(401, "رمز غير صالح")

    try:
        target_id = int(user_id)
    except ValueError:
        raise HTTPException(400, "معرّف غير صالح")

    if int(viewer_id) == target_id:
        raise HTTPException(400, "لا يمكنك متابعة نفسك")

    try:
        count = follow_profile(int(viewer_id), target_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"status": "success", "is_following": True, "followers_count": count}


@app.delete("/profile/{user_id}/follow")
def profile_unfollow(user_id: str, token=Depends(verify_token)):
    viewer_id = token.get("user_id")
    if not viewer_id:
        raise HTTPException(401, "رمز غير صالح")

    try:
        target_id = int(user_id)
    except ValueError:
        raise HTTPException(400, "معرّف غير صالح")

    count = unfollow_profile(int(viewer_id), target_id)
    return {"status": "success", "is_following": False, "followers_count": count}


_VALID_FOLLOW_TYPES = {"all", "emp", "co", "edu"}

@app.get("/profile/{user_id}/followers")
def profile_followers_list(user_id: str, request: Request, limit: int = 20, offset: int = 0, type: str = "all"):
    """Paginated followers list. Public — no auth required. type: all|emp|co|edu"""
    if type not in _VALID_FOLLOW_TYPES:
        raise HTTPException(400, "نوع غير صالح — القيم المسموحة: all, emp, co, edu")
    try:
        profile_id = int(user_id)
    except ValueError:
        profile_id = get_user_id_by_tw_id(user_id)
    if not profile_id:
        raise HTTPException(404, "الملف الشخصي غير موجود")

    limit  = min(max(limit, 1), 50)
    offset = max(offset, 0)

    viewer_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        if payload:
            viewer_id = payload.get("user_id")

    result = get_profile_followers_list(profile_id, viewer_id, limit, offset, type)
    return {"status": "success", **result}


@app.get("/profile/{user_id}/following")
def profile_following_list(user_id: str, request: Request, limit: int = 20, offset: int = 0, type: str = "all"):
    """Paginated following list (accounts this profile follows). Public — no auth required. type: all|emp|co|edu"""
    if type not in _VALID_FOLLOW_TYPES:
        raise HTTPException(400, "نوع غير صالح — القيم المسموحة: all, emp, co, edu")
    try:
        profile_id = int(user_id)
    except ValueError:
        profile_id = get_user_id_by_tw_id(user_id)
    if not profile_id:
        raise HTTPException(404, "الملف الشخصي غير موجود")

    limit  = min(max(limit, 1), 50)
    offset = max(offset, 0)

    viewer_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        if payload:
            viewer_id = payload.get("user_id")

    result = get_profile_following_list(profile_id, viewer_id, limit, offset, type)
    return {"status": "success", **result}


@app.post("/profile/{user_id}/interest")
def profile_interest_save(user_id: str, token=Depends(verify_token)):
    """Save a profile interest. Backend derives interest_type from actor user_type.
    Guests and owners blocked. Target must be an emp profile."""
    actor_id = token.get("user_id")
    if not actor_id:
        raise HTTPException(401, "رمز غير صالح")

    try:
        target_id = int(user_id)
    except ValueError:
        raise HTTPException(400, "معرّف غير صالح")

    if int(actor_id) == target_id:
        raise HTTPException(400, "لا يمكنك حفظ ملفك الشخصي")

    result = save_profile_interest(int(actor_id), target_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "تعذّر الحفظ"))

    actor_type    = token.get("user_type", "emp")
    interest_type = result["interest_type"]
    return {
        "status": "success",
        "viewer_action": {
            "label":        get_profile_interest_label(actor_type, True),
            "type":         interest_type,
            "is_active":    True,
            "can_interact": True,
            "hidden":       False,
        },
    }


@app.delete("/profile/{user_id}/interest")
def profile_interest_remove(user_id: str, token=Depends(verify_token)):
    """Remove a profile interest. Idempotent — no error if not found."""
    actor_id = token.get("user_id")
    if not actor_id:
        raise HTTPException(401, "رمز غير صالح")

    try:
        target_id = int(user_id)
    except ValueError:
        raise HTTPException(400, "معرّف غير صالح")

    remove_profile_interest(int(actor_id), target_id)

    actor_type = token.get("user_type", "emp")
    return {
        "status": "success",
        "viewer_action": {
            "label":        get_profile_interest_label(actor_type, False),
            "type":         get_profile_interest_type(actor_type),
            "is_active":    False,
            "can_interact": True,
            "hidden":       False,
        },
    }


@app.get("/professions")
def list_professions():
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, name_ar, name_en, slug, icon, category_group "
            "FROM profession_categories WHERE is_active = TRUE "
            "ORDER BY category_group, sort_order, name_ar"
        )
        cols = ["id","name_ar","name_en","slug","icon","category_group"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        release_conn(conn)

class ProfessionSuggestionInput(BaseModel):
    suggested_name_ar: str
    suggested_name_en: Optional[str] = None

@app.post("/profession-suggestions")
def suggest_profession(data: ProfessionSuggestionInput, token=Depends(verify_token)):
    name_ar = data.suggested_name_ar.strip()
    if len(name_ar) < 2:
        raise HTTPException(400, detail="الاسم قصير جداً — أدخل اسم تخصص واضح")
    if len(name_ar) > 100:
        raise HTTPException(400, detail="الاسم طويل جداً — 100 حرف كحد أقصى")

    # Normalize: lowercase, collapse spaces (Arabic-safe, no transliteration)
    import unicodedata
    normalized = " ".join(
        unicodedata.normalize("NFKC", name_ar).lower().split()
    )

    user_id = int(token.get("user_id"))
    conn = get_conn()
    try:
        # Return existing pending suggestion if same normalized name for this user
        existing = conn.run(
            "SELECT id, suggested_name_ar, suggested_name_en, normalized_name, status, created_at "
            "FROM profession_suggestions "
            "WHERE user_id = :uid AND normalized_name = :norm AND status = 'pending'",
            uid=user_id, norm=normalized
        )
        if existing:
            cols = ["id","suggested_name_ar","suggested_name_en","normalized_name","status","created_at"]
            return {"status": "exists", "suggestion": dict(zip(cols, existing[0]))}

        name_en = data.suggested_name_en.strip() if data.suggested_name_en else None
        rows = conn.run(
            "INSERT INTO profession_suggestions "
            "(user_id, suggested_name_ar, suggested_name_en, normalized_name, status) "
            "VALUES (:uid, :ar, :en, :norm, 'pending') "
            "RETURNING id, suggested_name_ar, suggested_name_en, normalized_name, status, created_at",
            uid=user_id, ar=name_ar, en=name_en, norm=normalized
        )
        cols = ["id","suggested_name_ar","suggested_name_en","normalized_name","status","created_at"]
        return {"status": "created", "suggestion": dict(zip(cols, rows[0]))}
    finally:
        release_conn(conn)

@app.put("/profile/{user_id}")
def update_user_profile(user_id: int, data: ProfileUpdateInput, token=Depends(verify_token)):
    _t0 = _time.time()
    tok_uid = token.get('user_id')
    if str(tok_uid) != str(user_id):
        print(f"[PUT /profile] MISMATCH: token={tok_uid} url={user_id}")
        raise HTTPException(403, "Unauthorized")
    payload = data.dict(exclude_none=True)
    if "profession_id" in payload:
        conn = get_conn()
        try:
            rows = conn.run("SELECT id FROM profession_categories WHERE id = :pid AND is_active = TRUE", pid=payload["profession_id"])
            if not rows: raise HTTPException(400, detail="التخصص غير موجود أو غير فعال")
        finally:
            release_conn(conn)
    try:
        profile = update_profile(user_id, payload)
        if not profile:
            raise HTTPException(500, "Profile update failed")
        updated_keys = list(payload.keys())
        print(f"[PUT /profile] ✅ user={user_id} fields={updated_keys} — {_time.time()-_t0:.3f}s total")
        return {"status": "success", "profile": profile, "updated_fields": updated_keys}
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        print(f"Profile update error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/experience/{user_id}")
def add_user_experience(user_id: int, data: ExperienceInput, token=Depends(verify_token)):
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    if not data.title.strip() or not data.company.strip():
        raise HTTPException(400, detail="المسمى الوظيفي وجهة العمل مطلوبان")
    try:
        return {"status": "success", "experience": add_experience(user_id, data.dict())}
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except Exception as e:
        print(f"Experience error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.put("/experience/reorder")
def reorder_user_experience(data: ExperienceReorderInput, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid:
        raise HTTPException(401, "Unauthorized")
    if not data.ordered_ids:
        raise HTTPException(400, detail="ordered_ids مطلوب")
    try:
        reorder_experience(uid, data.ordered_ids)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(403, detail=str(e))
    except Exception as e:
        print(f"[reorder_experience] error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.put("/experience/{exp_id}")
def update_user_experience(exp_id: int, data: ExperienceUpdateInput, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid:
        raise HTTPException(401, "Unauthorized")
    try:
        result = update_experience(exp_id, uid, data.dict())
        return {"status": "success", "experience": result}
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        print(f"[update_experience] error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/education/{user_id}")
def add_user_education(user_id: int, data: EducationInput, token=Depends(verify_token)):
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    if not data.institution.strip():
        raise HTTPException(400, detail="اسم المؤسسة التعليمية مطلوب")
    try:
        return {"status": "success", "education": add_education(user_id, data.dict())}
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except Exception as e:
        print(f"Education error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/course/{user_id}")
def add_user_course(user_id: int, data: CourseInput, token=Depends(verify_token)):
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    if not data.title.strip():
        raise HTTPException(400, detail="اسم الدورة مطلوب")
    try:
        return {"status": "success", "course": add_course(user_id, data.dict())}
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except Exception as e:
        print(f"Course error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/skills/{user_id}")
def add_user_skill(user_id: int, data: SkillInput, token=Depends(verify_token)):
    import re as _re
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    skill_clean = (data.skill or '').strip()
    if not skill_clean:
        raise HTTPException(422, detail={"status":"error","message":"اسم المهارة مطلوب"})
    if len(skill_clean) < 2:
        raise HTTPException(422, detail={"status":"error","message":"اسم المهارة قصير جداً"})
    if not _re.search(r'[a-zA-Z؀-ۿ]', skill_clean):
        raise HTTPException(422, detail={"status":"error","message":"اسم المهارة يجب أن يحتوي على حروف"})
    try:
        validate_professional_text(skill_clean, "skill")
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    note_clean = (data.note or '').strip() or None
    if note_clean:
        if len(note_clean) > 160:
            raise HTTPException(422, detail={"status":"error","message":"ملاحظة المهارة طويلة جداً — الحد الأقصى 160 حرف","field":"note"})
        try:
            validate_professional_text(note_clean, "note")
        except ContentValidationError as e:
            raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "INSERT INTO user_skills (user_id, skill, level, note) VALUES (:uid, :skill, :level, :note) "
                "ON CONFLICT (user_id, skill) DO UPDATE SET level=EXCLUDED.level, note=EXCLUDED.note "
                "RETURNING id, user_id, skill, level, note",
                uid=user_id, skill=skill_clean, level=data.level, note=note_clean
            )
            cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
            return {"status": "success", "skill": dict(zip(cols, rows[0]))}
        finally:
            release_conn(conn)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/skills/{skill_id}")
def delete_user_skill(skill_id: int, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        conn = get_conn()
        try:
            # Only delete if belongs to the token user
            conn.run("DELETE FROM user_skills WHERE id = :id AND user_id = :uid",
                    id=skill_id, uid=uid)
            return {"success": True}
        finally:
            release_conn(conn)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/langs/{user_id}")
def add_user_lang(user_id: int, data: LangInput, token=Depends(verify_token)):
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    if not data.language or not data.language.strip():
        raise HTTPException(400, detail="اسم اللغة مطلوب")
    try:
        validate_professional_text(data.language, "language")
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "INSERT INTO user_langs (user_id, language, level) VALUES (:uid, :lang, :level) ON CONFLICT (user_id, language) DO UPDATE SET level=EXCLUDED.level RETURNING id, user_id, language, level",
                uid=user_id, lang=data.language, level=data.level
            )
            cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
            return {"status": "success", "lang": dict(zip(cols, rows[0]))}
        finally:
            release_conn(conn)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/langs/{lang_id}")
def delete_user_lang(lang_id: int, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM user_langs WHERE id = :id AND user_id = :uid",
                    id=lang_id, uid=uid)
            return {"success": True}
        finally:
            release_conn(conn)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/links/{user_id}")
def add_user_link(user_id: int, data: LinkInput, token=Depends(verify_token)):
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    try:
        conn = get_conn()
        try:
            rows = conn.run(
                "INSERT INTO user_links (user_id, link_type, url) VALUES (:uid, :ltype, :url) ON CONFLICT (user_id, link_type) DO UPDATE SET url=EXCLUDED.url RETURNING id, user_id, link_type, url",
                uid=user_id, ltype=data.link_type, url=data.url
            )
            cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
            return {"status": "success", "link": dict(zip(cols, rows[0]))}
        finally:
            release_conn(conn)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.delete("/links/{link_id}")
def delete_user_link(link_id: int, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM user_links WHERE id = :id AND user_id = :uid",
                    id=link_id, uid=uid)
            return {"success": True}
        finally:
            release_conn(conn)
    except Exception as e:
        raise HTTPException(500, str(e))

# ══ Messages & Notifications ══

async def _bg_cold_path_update(receiver_id: int, msg_id: int, was_delivered: bool, unread: int):
    """Background: DB mark-delivered + WS badge_update — off critical path."""
    try:
        if was_delivered:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mark_message_delivered, msg_id)
        await ws_manager.send_to_user(receiver_id, {
            "type": "badge_update", "badge": "messages", "count": unread
        })
    except Exception as e:
        print(f"[bg_cold_path] {e}")


@app.post("/messages/send")
async def send_msg(data: MessageInput, background_tasks: BackgroundTasks, token=Depends(verify_token)):
    _t0 = time.perf_counter()
    try:
        sender_id = int(token.get("user_id") or 0)
        if not sender_id:
            raise HTTPException(401, "غير مصرح")
        if sender_id == data.receiver_id:
            raise HTTPException(400, "لا يمكن إرسال رسالة لنفسك")

        receiver_has_conv_open = ws_manager.active_conversations.get(data.receiver_id) == sender_id

        # Use asyncpg (1 RTT) if pool is up; fall back to pg8000 (3 RTTs) otherwise
        if _asyncpg_pool:
            msg, unread, db_timing = await _pipeline_asyncpg(
                sender_id, data.receiver_id, data.content,
                mark_as_read=receiver_has_conv_open
            )
        else:
            loop = asyncio.get_event_loop()
            msg, unread, db_timing = await loop.run_in_executor(
                None, send_message_pipeline,
                sender_id, data.receiver_id, data.content, receiver_has_conv_open
            )
            db_timing["driver"] = "pg8000"
        msg_id = msg["id"]
        _t_db = time.perf_counter()

        if receiver_has_conv_open:
            # Hot path: 1 DB round-trip, badge unchanged (receiver is reading)
            await ws_manager.send_to_user(data.receiver_id, {
                "type": "message", "from": sender_id, "id": msg_id,
                "content": data.content, "created_at": msg.get("created_at", ""), "is_read": True
            })
            await ws_manager.send_to_user(sender_id, {
                "type": "status_update", "id": msg_id, "status": "read"
            })
        else:
            # Cold path: WS events on critical path; mark_delivered + badge in background
            was_delivered = await ws_manager.send_to_user(data.receiver_id, {
                "type": "message", "from": sender_id, "id": msg_id,
                "content": data.content, "created_at": msg.get("created_at", "")
            })
            if was_delivered:
                msg["delivered_at"] = True
                await ws_manager.send_to_user(sender_id, {
                    "type": "status_update", "id": msg_id, "status": "delivered"
                })
            background_tasks.add_task(
                _bg_cold_path_update, data.receiver_id, msg_id, bool(was_delivered), unread or 0
            )

        _t_end = time.perf_counter()
        _timing = {
            **db_timing,
            "ws_ms":    round((_t_end - _t_db) * 1000),
            "badge_ms": 0,   # deferred to background on cold path; skipped on hot path
            "total_ms": round((_t_end - _t0)   * 1000),
        }
        print(f"[TW-TIMING] send_msg #{msg_id}: {_timing}")

        return {"status": "success", "message": msg, "_timing": _timing}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/messages/conversations/{user_id}")
def get_convs(user_id: int, token=Depends(verify_token)):
    if int(token.get("user_id") or 0) != user_id:
        raise HTTPException(403, "غير مصرح")
    try:
        convs = get_conversations(user_id)
        return {"status": "success", "conversations": convs}
    except Exception as e:
        print(f"[get_convs] user_id={user_id} error={type(e).__name__}: {e}")
        raise HTTPException(500, str(e))

@app.get("/messages/unread/{user_id}")
def unread_msgs(user_id: int, token=Depends(verify_token)):
    if int(token.get("user_id") or 0) != user_id:
        raise HTTPException(403, "غير مصرح")
    try:
        count = get_unread_count(user_id)
        return {"status": "success", "count": count}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/messages/{user_id}/{other_id}")
async def get_msgs(user_id: int, other_id: int, token=Depends(verify_token)):
    if int(token.get("user_id") or 0) != user_id:
        raise HTTPException(403, "غير مصرح")
    try:
        msgs, newly_read_ids = get_messages(user_id, other_id)
        if newly_read_ids:
            await ws_manager.send_to_user(other_id, {
                "type": "status_update",
                "ids": newly_read_ids,
                "status": "read"
            })
        return {"status": "success", "messages": msgs}
    except Exception as e:
        raise HTTPException(500, str(e))



@app.get("/notifications/{user_id}")
def user_notifications(user_id: int):
    try:
        notifs = get_notifications(user_id)
        unread = get_unread_notifications(user_id)
        return {"status": "success", "notifications": notifs, "unread": unread}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/notifications/{user_id}/read")
def read_notifications(user_id: int, token=Depends(verify_token)):
    try:
        mark_notifications_read(user_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ══ Storage Upload ══

@app.post("/upload/image")
async def upload_image(data: ImageUploadInput, token=Depends(verify_token)):
    """Upload image to Supabase Storage and return public URL"""
    import httpx
    try:
        # Parse data URL: "data:image/jpeg;base64,/9j/4AAQ..."
        if ',' not in data.data_url:
            raise HTTPException(400, "Invalid data URL")

        header, b64data = data.data_url.split(',', 1)
        # Get mime type: "data:image/jpeg;base64"
        mime = header.split(':')[1].split(';')[0]
        ext = mimetypes.guess_extension(mime) or '.jpg'
        if ext == '.jpe': ext = '.jpg'

        file_bytes = base64.b64decode(b64data)

        # Check size - max 5MB
        if len(file_bytes) > 5 * 1024 * 1024:
            raise HTTPException(400, "الصورة كبيرة جداً - الحد الأقصى 5MB")

        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            # Fallback: return data URL as-is (dev mode)
            return {"status": "success", "url": data.data_url, "dev_mode": True}

        bucket = data.bucket
        filename = f"{data.user_id}_{data.filename}{ext}"
        storage_url = f"{supabase_url}/storage/v1/object/{bucket}/{filename}"

        async with httpx.AsyncClient() as client:
            r = await client.post(
                storage_url,
                content=file_bytes,
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": mime,
                    "x-upsert": "true"
                }
            )
            if r.status_code not in (200, 201):
                # Fallback to data URL
                return {"status": "success", "url": data.data_url, "dev_mode": True}

        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"
        return {"status": "success", "url": public_url}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {e}")
        # Fallback: return data URL
        return {"status": "success", "url": data.data_url, "dev_mode": True}

# ══ KYC Endpoints ══

@app.post("/kyc/start")
def kyc_start(user_id: int, token=Depends(verify_token)):
    try:
        result = start_kyc(user_id)
        return {"status": "success", "kyc": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/kyc/status/{user_id}")
def kyc_status(user_id: int):
    try:
        result = get_kyc_status(user_id)
        return {"status": "success", "kyc": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/email/send")
def kyc_send_email(data: KYCEmailInput, token=Depends(verify_token)):
    try:
        start_kyc(data.user_id)
        code = send_email_code(data.user_id, data.email)
        print(f"[KYC] Email code for user {data.user_id}: {code}")  # In prod: send via email
        return {"status": "success", "message": "تم إرسال الرمز على بريدك الإلكتروني", "dev_code": code}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/email/verify")
def kyc_verify_email(data: KYCCodeInput, token=Depends(verify_token)):
    try:
        ok = verify_email_code(data.user_id, data.code)
        if not ok:
            raise HTTPException(400, "الرمز غير صحيح أو منتهي الصلاحية")
        return {"status": "success", "message": "تم تأكيد البريد الإلكتروني ✅"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/phone/send")
def kyc_send_phone(data: KYCPhoneInput, token=Depends(verify_token)):
    try:
        code = send_phone_code(data.user_id, data.phone)
        print(f"[KYC] Phone code for user {data.user_id}: {code}")  # In prod: send via SMS
        return {"status": "success", "message": "تم إرسال الرمز على هاتفك", "dev_code": code}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/phone/verify")
def kyc_verify_phone(data: KYCCodeInput, token=Depends(verify_token)):
    try:
        ok = verify_phone_code(data.user_id, data.code)
        if not ok:
            raise HTTPException(400, "الرمز غير صحيح")
        return {"status": "success", "message": "تم تأكيد رقم الهاتف ✅"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/kyc/docs")
def kyc_upload_docs(data: KYCDocsInput, token=Depends(verify_token)):
    try:
        result = upload_kyc_docs(data.user_id, data.id_front_url, data.selfie_url)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/admin/kyc")
def admin_get_kyc(request: Request):
    check_admin(request)
    try:
        submissions = get_all_kyc_submissions()
        return {"status": "success", "submissions": submissions, "count": len(submissions)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/admin/kyc/{user_id}/approve")
def admin_kyc_approve(user_id: int, data: KYCAdminInput, request: Request):
    check_admin(request)
    try:
        result = admin_approve_kyc(user_id, data.note)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/admin/kyc/{user_id}/reject")
def admin_kyc_reject(user_id: int, data: KYCAdminInput, request: Request):
    check_admin(request)
    try:
        result = admin_reject_kyc(user_id, data.note)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/verify-request")
def request_verification(data: VerifyRequestInput, token=Depends(verify_token)):
    try:
        req = create_verify_request(data.user_id, data.dict())
        return {"status": "success", "request": req}
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        print(f"Verify request error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

# ══════════════════════════════════════════
# Jobs & Match
# ══════════════════════════════════════════

@app.get("/jobs")
def list_jobs(search: str = None, location: str = None,
               job_type: str = None, company_id: int = None):
    filters = {"search":search,"location":location,"job_type":job_type,"company_id":company_id}
    jobs = get_jobs({k:v for k,v in filters.items() if v})
    return {"jobs": jobs, "count": len(jobs)}

@app.get("/jobs/{job_id}")
def get_job_detail(job_id: int):
    job = get_job(job_id)
    if not job: raise HTTPException(404, "الوظيفة غير موجودة")
    return {"status": "success", "job": job}

@app.post("/company/jobs")
def post_job(data: JobInput, token=Depends(verify_token)):
    # Rule #1, #20: JWT only — X-User-Id removed
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: POST /company/jobs")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried POST /company/jobs")
        raise HTTPException(403, "شركات وجهات فقط")
    job = add_job(int(user_id), data.dict())
    return {"status": "success", "job": job}

@app.put("/company/jobs/{job_id}")
def update_job_endpoint(job_id: int, data: JobInput, token=Depends(verify_token)):
    # Rule #1, #20: JWT + DB ownership check
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: PUT /company/jobs/{job_id}")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried PUT /company/jobs/{job_id}")
        raise HTTPException(403, "شركات وجهات فقط")
    cid = int(user_id)
    conn = get_conn()
    try:
        fields = {k:v for k,v in data.dict().items() if v is not None}
        if fields:
            set_clause = ", ".join(f"{k}=:{k}" for k in fields)
            # DB ownership check: WHERE company_id=cid ensures only owner can update
            affected = conn.run(
                f"UPDATE jobs SET {set_clause} WHERE id=:id AND company_id=:cid",
                id=job_id, cid=cid, **fields)
            if not affected:
                print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user={cid} tried PUT job={job_id}")
                raise HTTPException(403, "ليست وظيفتك أو غير موجودة")
        return {"status": "success"}
    finally:
        release_conn(conn)

@app.delete("/company/jobs/{job_id}")
def remove_job(job_id: int, token=Depends(verify_token)):
    # Rule #1, #20: JWT + DB ownership via delete_job WHERE
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: DELETE /company/jobs/{job_id}")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried DELETE /company/jobs/{job_id}")
        raise HTTPException(403, "شركات وجهات فقط")
    cid = int(user_id)
    deleted = delete_job(job_id, cid)
    # delete_job uses WHERE id=job_id AND company_id=cid → DB ownership check
    if not deleted:
        print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user={cid} tried DELETE job={job_id}")
        raise HTTPException(403, "ليست وظيفتك أو غير موجودة")
    return {"success": True}

@app.get("/company/jobs")
def get_company_jobs(token=Depends(verify_token)):
    # Rule #1, #20: JWT only — owner sees their own jobs
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: GET /company/jobs")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried GET /company/jobs")
        raise HTTPException(403, "شركات وجهات فقط")
    jobs = get_jobs({"company_id": int(user_id)})
    return {"jobs": jobs, "count": len(jobs)}

@app.post("/jobs/{job_id}/apply")
def apply_to_job(job_id: int, data: JobApplyInput, token=Depends(verify_token)):
    result = apply_job(job_id, data.user_id, data.cover_letter or "")
    return {"status": "success", **result}

@app.get("/jobs/{job_id}/applicants")
def job_applicants(job_id: int, token=Depends(verify_token)):
    user_id = token.get("user_id")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: GET /jobs/{job_id}/applicants")
        raise HTTPException(401, "رمز غير صالح")
    conn = get_conn()
    try:
        rows = conn.run("SELECT company_id FROM jobs WHERE id=:jid", jid=job_id)
        if not rows:
            raise HTTPException(404, "الوظيفة غير موجودة")
        job_company_id = rows[0][0]
    finally:
        release_conn(conn)
    if int(job_company_id) != int(user_id):
        print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user {user_id} tried to access applicants for job {job_id} owned by {job_company_id}")
        raise HTTPException(403, "غير مصرح — هذه الوظيفة ليست لشركتك")
    applicants = get_job_applicants(job_id)
    return {"applicants": applicants, "count": len(applicants)}

@app.get("/my/applications")
def my_applications(token=Depends(verify_token)):
    user_id = token.get("user_id")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: GET /my/applications")
        raise HTTPException(401, "رمز غير صالح")
    apps = get_user_applications(int(user_id))
    return {"applications": apps, "count": len(apps)}

@app.put("/jobs/applications/{app_id}/status")
def update_app_status(app_id: int, data: AppStatusInput, token=Depends(verify_token)):
    user_id = token.get("user_id")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: PUT /jobs/applications/{app_id}/status")
        raise HTTPException(401, "رمز غير صالح")
    allowed_statuses = {"pending", "viewed", "accepted", "rejected"}
    if data.status not in allowed_statuses:
        raise HTTPException(400, f"حالة غير صالحة. المسموح: {', '.join(sorted(allowed_statuses))}")
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT j.company_id FROM job_applications ja JOIN jobs j ON j.id=ja.job_id WHERE ja.id=:aid",
            aid=app_id
        )
        if not rows:
            raise HTTPException(404, "الطلب غير موجود")
        job_company_id = rows[0][0]
    finally:
        release_conn(conn)
    if int(job_company_id) != int(user_id):
        print(f"[SECURITY] APPLICATION_OWNERSHIP_FAILED: user {user_id} tried to update app {app_id} owned by company {job_company_id}")
        raise HTTPException(403, "غير مصرح — هذا الطلب ليس لوظيفة شركتك")
    result = update_application_status(app_id, data.status)
    return result

@app.get("/admin/jobs")
def admin_list_jobs(request: Request):
    check_admin(request)
    jobs = get_jobs({})
    return {"jobs": jobs, "count": len(jobs)}

@app.delete("/admin/jobs/{job_id}")
def admin_delete_job(job_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM jobs WHERE id=:id", id=job_id)
        return {"success": True}
    finally:
        release_conn(conn)


@app.post("/feedback")
def log_feedback(data: FeedbackInput, token=Depends(verify_token)):
    return {"status": "logged"}

@app.get("/stats")
def stats():
    conn = get_conn()
    try:
        users_count = conn.run("SELECT COUNT(*) FROM users")[0][0]
        emp_count = conn.run("SELECT COUNT(*) FROM users WHERE user_type='emp'")[0][0]
        co_count = conn.run("SELECT COUNT(*) FROM users WHERE user_type='co'")[0][0]
        edu_count = conn.run("SELECT COUNT(*) FROM users WHERE user_type='edu'")[0][0]
        return {
            "users_count": users_count,
            "emp_count": emp_count,
            "co_count": co_count,
            "edu_count": edu_count,
            "jobs_count": conn.run("SELECT COUNT(*) FROM jobs WHERE status='active'")[0][0] if True else 0
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

# ══════════════════════════════════════════
# Admin Login - returns token
# ══════════════════════════════════════════
@app.post("/tw-ctrl-login")
def admin_login(data: AdminLoginInput):
    if data.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Return stable token (derived from password - no server storage)
    return {"success": True, "token": ADMIN_TOKEN}

# ══════════════════════════════════════════
# Admin API - all require X-Admin-Token header
# ══════════════════════════════════════════
@app.get("/auth/users")
def get_all_users(request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, full_name, email, user_type, created_at FROM users ORDER BY created_at DESC"
        )
        cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
        users = [dict(zip(cols, r)) for r in rows]
        for u in users:
            if u.get("created_at"):
                u["created_at"] = str(u["created_at"])[:10]
        return {"users": users, "total": len(users)}
    except Exception as e:
        print(f"get_all_users error: {e}")
        raise HTTPException(500, detail=str(e))
    finally:
        release_conn(conn)

@app.get("/admin/verify-requests")
def admin_verify_requests(request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run("""
            SELECT vr.id, vr.user_id, u.full_name AS user_name,
                   vr.item_type, vr.item_id, vr.item_title, vr.item_company,
                   vr.notes, vr.status, vr.created_at
            FROM verify_requests vr
            JOIN users u ON u.id = vr.user_id
            ORDER BY vr.created_at DESC
        """)
        cols = [d["name"] if isinstance(d, dict) else d[0] for d in conn.columns]
        reqs = [dict(zip(cols, r)) for r in rows]
        for r in reqs:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])[:10]
        return {"requests": reqs, "total": len(reqs)}
    except Exception as e:
        print(f"verify_requests error: {e}")
        raise HTTPException(500, detail=str(e))
    finally:
        release_conn(conn)

@app.put("/admin/verify/{req_id}")
def admin_update_verify(req_id: int, data: VerifyUpdateInput, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run(
            "UPDATE verify_requests SET status = :s WHERE id = :id",
            s=data.status, id=req_id
        )
        return {"success": True}
    except Exception as e:
        print(f"update_verify error: {e}")
        raise HTTPException(500, detail=str(e))
    finally:
        release_conn(conn)

@app.get("/admin/profile/{user_id}")
def admin_get_profile(user_id: int, request: Request):
    check_admin(request)
    try:
        profile = get_full_profile(user_id)
        if not profile:
            raise HTTPException(404, "المستخدم غير موجود")
        return {"status": "success", "profile": profile}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"admin_get_profile error: {err}")
        raise HTTPException(500, detail=f"خطأ: {str(e)}")

@app.delete("/auth/user/{user_id}/delete")
def delete_own_account(user_id: int, request: Request, token=Depends(verify_token)):
    """User deletes their own account"""
    conn = get_conn()
    try:
        conn.run("DELETE FROM users WHERE id = :uid", uid=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.delete("/admin/user/{user_id}")
def delete_user(user_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM users WHERE id = :uid", uid=user_id)
        if not rows:
            raise HTTPException(404, "المستخدم غير موجود")
        conn.run("DELETE FROM users WHERE id = :uid", uid=user_id)
        return {"success": True, "message": "تم حذف الحساب"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.put("/admin/user/{user_id}/type")
async def change_user_type(user_id: int, request: Request):
    check_admin(request)
    data = await request.json()
    new_type = data.get("user_type","emp")
    if new_type not in ("emp","co","edu"):
        raise HTTPException(400, "نوع حساب غير صحيح")
    conn = get_conn()
    try:
        conn.run("UPDATE users SET user_type = :utype WHERE id = :uid", utype=new_type, uid=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.put("/admin/user/{user_id}/verify")
async def verify_user(user_id: int, request: Request):
    check_admin(request)
    data = await request.json()
    is_v = data.get("is_verified", True)
    conn = get_conn()
    try:
        rows = conn.run("SELECT id FROM profiles WHERE user_id = :uid", uid=user_id)
        if rows:
            conn.run("UPDATE profiles SET is_verified = :v WHERE user_id = :uid", v=is_v, uid=user_id)
        else:
            conn.run("INSERT INTO profiles (user_id, is_verified) VALUES (:uid, :v)", uid=user_id, v=is_v)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.put("/admin/user/{user_id}/password")
async def admin_reset_password(user_id: int, request: Request):
    check_admin(request)
    data = await request.json()
    pw = data.get("password","").strip()
    if not pw or len(pw) < 6:
        raise HTTPException(400, "كلمة المرور قصيرة جداً")
    from auth import hash_password
    conn = get_conn()
    try:
        conn.run("UPDATE users SET password_hash = :pw WHERE id = :uid",
                 pw=hash_password(pw), uid=user_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.delete("/admin/experience/{exp_id}")
def admin_delete_exp(exp_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM experience WHERE id = :id", id=exp_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.delete("/admin/education/{edu_id}")
def admin_delete_edu(edu_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM education WHERE id = :id", id=edu_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.delete("/admin/course/{course_id}")
def admin_delete_course(course_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM courses WHERE id = :id", id=course_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        release_conn(conn)

@app.post("/admin/message")
def admin_send_message(data: AdminMessageInput, request: Request):
    check_admin(request)
    print(f"[ADMIN MSG] To:{data.user_id} | {data.subject}: {data.message}")
    return {"success": True}

@app.delete("/experience/{exp_id}")
def delete_experience(exp_id: int, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM experience WHERE id = :id AND user_id = :uid",
                    id=exp_id, uid=uid)
            _cache_del('profile:'+str(uid))
            return {"success": True}
        finally:
            release_conn(conn)
    except Exception as e:
        print(f"[delete_experience] error: {e}")
        raise HTTPException(500, detail=str(e))

@app.put("/education/{edu_id}")
def update_education_entry(edu_id: int, data: EducationInput, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        result = update_education(edu_id, uid, data.dict())
        if not result:
            raise HTTPException(404, "لم يتم العثور على الشهادة")
        _cache_del('profile:'+str(uid))
        return {"status": "success", "education": result}
    except HTTPException:
        raise
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except Exception as e:
        print(f"[update_education] error: {e}")
        raise HTTPException(500, "خطأ في الخادم")

@app.delete("/education/{edu_id}")
def delete_education(edu_id: int, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM education WHERE id = :id AND user_id = :uid",
                    id=edu_id, uid=uid)
            _cache_del('profile:'+str(uid))
            return {"success": True}
        finally:
            release_conn(conn)
    except Exception as e:
        print(f"[delete_education] error: {e}")
        raise HTTPException(500, detail=str(e))

@app.put("/course/{course_id}")
def update_course_entry(course_id: int, data: CourseInput, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        result = update_course(course_id, uid, data.dict())
        if not result:
            raise HTTPException(404, "لم يتم العثور على الدورة")
        _cache_del('profile:'+str(uid))
        return {"status": "success", "course": result}
    except HTTPException:
        raise
    except ContentValidationError as e:
        raise HTTPException(422, detail={"status": "error", "message": e.message, "field": e.field})
    except Exception as e:
        print(f"[update_course] error: {e}")
        raise HTTPException(500, "خطأ في الخادم")

@app.delete("/course/{course_id}")
def delete_course(course_id: int, token=Depends(verify_token)):
    uid = token.get('user_id')
    if not uid: raise HTTPException(401, "Unauthorized")
    try:
        conn = get_conn()
        try:
            conn.run("DELETE FROM courses WHERE id = :id AND user_id = :uid",
                    id=course_id, uid=uid)
            _cache_del('profile:'+str(uid))
            return {"success": True}
        finally:
            release_conn(conn)
    except Exception as e:
        print(f"[delete_course] error: {e}")
        raise HTTPException(500, detail=str(e))


# ══ News Posts (admin-managed editorial content) ══

class NewsPostInput(BaseModel):
    title: str
    summary: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = "general"
    country: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = "draft"

@app.get("/admin/news")
def admin_list_news(request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        rows = conn.run(
            """SELECT n.id, n.title, n.summary, n.category, n.country,
                      n.source_url, n.status, n.created_at, n.updated_at,
                      COALESCE(u.full_name,'') AS created_by_name
               FROM news_posts n
               LEFT JOIN users u ON n.created_by = u.id
               ORDER BY n.created_at DESC"""
        )
        cols = ["id","title","summary","category","country","source_url",
                "status","created_at","updated_at","created_by_name"]
        result = []
        for r in (rows or []):
            d = dict(zip(cols, r))
            for f in ("created_at","updated_at"):
                if d.get(f) and hasattr(d[f], "isoformat"):
                    d[f] = d[f].isoformat()
            result.append(d)
        return {"news": result, "total": len(result)}
    finally:
        release_conn(conn)

@app.post("/admin/news")
def admin_create_news(data: NewsPostInput, request: Request):
    check_admin(request)
    allowed_statuses = {"draft", "published", "archived"}
    status = data.status if data.status in allowed_statuses else "draft"
    conn = get_conn()
    try:
        rows = conn.run(
            """INSERT INTO news_posts (title, summary, body, category, country, source_url, status)
               VALUES (:title, :summary, :body, :category, :country, :source_url, :status)
               RETURNING id""",
            title=data.title.strip(), summary=data.summary or "",
            body=data.body or "", category=data.category or "general",
            country=data.country or "", source_url=data.source_url or "",
            status=status
        )
        news_id = rows[0][0] if rows else None
        return {"success": True, "id": news_id}
    finally:
        release_conn(conn)

@app.put("/admin/news/{news_id}")
def admin_update_news(news_id: int, data: NewsPostInput, request: Request):
    check_admin(request)
    allowed_statuses = {"draft", "published", "archived"}
    status = data.status if data.status in allowed_statuses else "draft"
    conn = get_conn()
    try:
        conn.run(
            """UPDATE news_posts
               SET title=:title, summary=:summary, body=:body,
                   category=:category, country=:country, source_url=:source_url,
                   status=:status, updated_at=NOW()
               WHERE id=:id""",
            title=data.title.strip(), summary=data.summary or "",
            body=data.body or "", category=data.category or "general",
            country=data.country or "", source_url=data.source_url or "",
            status=status, id=news_id
        )
        return {"success": True}
    finally:
        release_conn(conn)

@app.delete("/admin/news/{news_id}")
def admin_delete_news(news_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM news_posts WHERE id=:id", id=news_id)
        return {"success": True}
    finally:
        release_conn(conn)
