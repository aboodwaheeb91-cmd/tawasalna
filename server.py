# See ARCHITECTURE.md for system architecture rules

"""
تواصلنا - Arabic Employment Platform
"""

import os
from fastapi import FastAPI, HTTPException, Request, Response, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict
import base64, mimetypes
from typing import List, Optional
from datetime import datetime
import re, secrets, json, os, time, asyncio
try:
    import asyncpg as _asyncpg
except ImportError:
    _asyncpg = None

import urllib.request
import ipaddress

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

# ── Client IP (PR 1.4) — the ONLY reader of X-Forwarded-For / X-Real-IP ──
# CLIENT_IP_SOURCE: xff_left (default — pre-PR behaviour) · xff_right (+ TRUSTED_PROXY_HOPS,
# default 1) · x_real_ip · peer. Unknown source or an invalid IP → request.client.host
# (warning logged once per kind). Choosing the value: ARCHITECTURE.md → Client IP Resolution.
_CLIENT_IP_SOURCES = ("xff_left", "xff_right", "x_real_ip", "peer")
_client_ip_warned: set = set()


def _client_ip_warn_once(kind: str, msg: str) -> None:
    if kind not in _client_ip_warned:
        _client_ip_warned.add(kind)
        print(f"⚠️ [client-ip] {msg}")


def _valid_ip(value) -> 'str | None':
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def get_client_ip(request) -> str:
    peer = request.client.host if request.client else '127.0.0.1'
    source = (os.environ.get("CLIENT_IP_SOURCE") or "xff_left").strip().lower()
    if source not in _CLIENT_IP_SOURCES:
        _client_ip_warn_once("source", f"CLIENT_IP_SOURCE={source!r} is invalid — using request.client.host")
        return peer
    if source == "peer":
        return peer
    xff = request.headers.get('X-Forwarded-For')
    real_ip = request.headers.get('X-Real-IP')
    if source == "xff_left":
        raw = xff.split(',')[0] if xff else real_ip
    elif source == "x_real_ip":
        raw = real_ip
    else:  # xff_right
        try:
            hops = int(os.environ.get("TRUSTED_PROXY_HOPS") or "1")
        except ValueError:
            hops = 0
        if hops < 1:
            _client_ip_warn_once("hops", "TRUSTED_PROXY_HOPS is invalid — using request.client.host")
            return peer
        parts = [p.strip() for p in xff.split(',')] if xff else []
        raw = parts[-hops] if len(parts) >= hops else None
    if raw is None:
        return peer
    ip = _valid_ip(raw)
    if not ip:
        _client_ip_warn_once("value", f"{source}: header value is not a valid IP — using request.client.host")
        return peer
    return ip


from auth import (
    init_db, get_conn,
    create_appointment, send_appointment, accept_appointment,
    request_reschedule_appointment, reschedule_appointment,
    cancel_appointment, complete_appointment, close_appointment,
    list_appointments, get_appointment_room,
    get_appointment_events, get_appointment_messages,
    create_appointment_message,
    create_user, authenticate_user, get_user_by_id, check_user_password, set_user_password, _migrate_password_changed_at,
    get_public_profile, get_full_profile, update_profile,
    get_profile_by_tw_id, get_full_profile_by_tw_id, get_user_id_by_tw_id, get_user_info_by_tw_id,
    project_public_profile, project_owner_profile, project_owner_kyc_status,
    add_experience, update_experience, reorder_experience, add_education, add_course, update_education, update_course, create_verify_request,
    add_job, get_jobs, get_job, apply_job,
    start_kyc, send_email_code, verify_email_code,
    send_phone_code, verify_phone_code, upload_kyc_docs,
    get_kyc_status, admin_approve_kyc, admin_reject_kyc, get_all_kyc_submissions, ensure_site_settings_table, ensure_reports_table,
    send_message, send_message_pipeline, mark_message_delivered, get_conversations, get_messages, get_unread_count,
    mark_message_read_immediate,
    create_notification, get_notifications, mark_notifications_read, mark_notification_read,
    get_unread_notifications, _migrate_notifications_schema_v2,
    _migrate_notifications_schema_v2_1,
    get_job_applicants, get_user_applications,
    update_application_status, promote_application_to_shortlist, archive_job,
    get_company_jobs_all, set_job_status,
    get_site_setting, set_site_setting, release_conn,
    _cache_del,
    get_company_profile_row, get_company_extras,
    update_company_profile,
    _migrate_company_branches, get_company_branches, save_company_branches,
    _migrate_jobs_v2, _migrate_job_lifecycle, _migrate_kyc_otp_security, _eff_status, _ALLOWED_DURATIONS,
    _migrate_taxonomy_foundation,
    _migrate_job_profession_targets,
    _fetch_accepted_professions_batch,
    _validate_accepted_profession_ids,
    follow_company, unfollow_company, get_company_followers_list, rate_company,
    get_company_ratings_detail,
    get_company_posts, get_company_posts_count, create_company_post, update_company_post, get_post_owner, delete_company_post, record_company_post_view, set_company_post_appreciation, set_company_post_save,
    get_company_post_comments, create_company_post_comment, update_company_post_comment, delete_company_post_comment,
    follow_profile, unfollow_profile, get_profile_followers_count, is_profile_following,
    get_profile_followers_list, get_profile_following_list,
    record_profile_view, get_profile_views_count,
    save_profile_interest, remove_profile_interest,
    is_profile_interest_active, get_profile_interest_type, get_profile_interest_label,
    is_candidate_saved,
    _migrate_company_saved_candidates, _migrate_company_candidate_job_refs,
    _migrate_candidate_status_per_job,
    save_company_candidate, remove_company_candidate,
    get_company_saved_candidates, get_company_saved_candidates_count,
    get_company_saved_candidates_filtered, get_company_saved_candidates_stats,
    update_company_saved_candidate, update_candidate_job_status,
    VALID_CANDIDATE_STATUSES, VALID_CANDIDATE_SORTS,
    get_talent_bank_quota, TALENT_BANK_FREE_LIMIT,
    get_company_candidate_suggestions,
    _migrate_appointments,
    _migrate_scheduler_jobs,
    _migrate_pipeline_schema_v1,
    _migrate_partial_unique_application_id,
    run_pipeline_backfill,
    pipeline_backfill_dry_run,
    LEGACY_APP_STATUS_TO_PIPELINE_STAGE,
    LEGACY_CANDIDATE_STATUS_TO_PIPELINE_STAGE,
    run_due_scheduler_jobs,
    BlockingConflictError,
    TalentBankLimitError,
    _migrate_pr5_pipeline_linking,
    _migrate_applicants_candidates_split,
    _resolve_pipeline_entry,
    PipelineEntryRequiredError,
    PipelineApplicationConflictError,
    create_pipeline_note, list_pipeline_notes,
    update_pipeline_note, delete_pipeline_note,
    get_pipeline_application_index_status,
    _APPLICANT_SORT_MAP,
)
from auth import ContentValidationError, validate_professional_text, JobArchivedError, _norm_name, ProfileValidationError

# ── Secrets from environment — NEVER hardcoded in source ──
# Required Railway Variables:
#   ADMIN_TOKEN      — random 32+ byte hex (e.g. openssl rand -hex 32) — admin LOGIN password only
#   ADMIN_JWT_SECRET — random 32+ byte hex, signs admin session JWTs; INDEPENDENT of JWT_SECRET / ADMIN_TOKEN
#   JWT_SECRET       — random 32+ byte hex, INDEPENDENT of ADMIN_TOKEN
#   ADMIN_URL_TOKEN  — random slug for admin panel URL path
# Rotating JWT_SECRET invalidates all active sessions (users must re-login). This is expected.
# Rotating ADMIN_JWT_SECRET signs every admin out (sessions last ≤ 1h anyway).
ADMIN_TOKEN      = os.environ.get("ADMIN_TOKEN", "").strip()
ADMIN_JWT_SECRET = os.environ.get("ADMIN_JWT_SECRET", "").strip()
JWT_SECRET       = os.environ.get("JWT_SECRET", "").strip()
ADMIN_URL_TOKEN  = os.environ.get("ADMIN_URL_TOKEN", "").strip()
# Scheduler S3: internal cron secret — set in Railway Variables, never in source.
SCHEDULER_SECRET = os.environ.get("SCHEDULER_SECRET", "")


# ── JWT (stdlib only - no extra deps) ──
# One HS256 implementation (_jwt_sign / _jwt_verify) for two independent secrets:
#   user sessions  → JWT_SECRET       (_jwt_encode / _jwt_decode)
#   admin sessions → ADMIN_JWT_SECRET (_admin_jwt_issue / _admin_jwt_claims)
# A token signed with one secret never verifies with the other.
import hmac, base64 as _b64

def _jwt_sign(payload: dict, secret: str) -> str:
    import json
    header = _b64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    body = _b64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()
    sig = _b64.urlsafe_b64encode(
        hmac.new(secret.encode(), f"{header}.{body}".encode(), 'sha256').digest()
    ).rstrip(b'=').decode()
    return f"{header}.{body}.{sig}"

def _jwt_verify(token: str, secret: str) -> dict:
    """Signature + exp check. {} on anything invalid (never raises)."""
    import json, time
    if not secret or len(secret) < 32 or not token:
        return {}
    try:
        parts = token.split('.')
        if len(parts) != 3: return {}
        expected_sig = _b64.urlsafe_b64encode(
            hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), 'sha256').digest()
        ).rstrip(b'=').decode()
        if not hmac.compare_digest(parts[2], expected_sig): return {}
        body = parts[1] + '=='
        payload = json.loads(_b64.urlsafe_b64decode(body.encode()))
        if not isinstance(payload, dict): return {}
        if payload.get('exp', 0) < time.time(): return {}
        return payload
    except Exception:
        return {}

def _jwt_encode(payload: dict) -> str:
    import time
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET is not configured or too short")
    payload['iat'] = int(time.time())
    payload['exp'] = int(time.time()) + 86400 * 7  # 7 days
    return _jwt_sign(payload, JWT_SECRET)

def _jwt_decode(token: str) -> dict:
    """User JWT → claims, or {} when invalid / expired / issued before the user's
    last password change (Session Invalidation — PR 1.8). Every user-JWT reader goes
    through here, so verify_token and the optional-auth endpoints share the check."""
    payload = _jwt_verify(token, JWT_SECRET)
    if payload and _jwt_revoked_by_password_change(payload):
        return {}
    return payload


# ── Session invalidation after password change (PR 1.8) ──
# users.password_changed_at (NULL = never changed). A user JWT whose iat is earlier
# than that second is rejected. Read through a short in-memory cache (no DB query per
# request); PUT /auth/password + admin password reset refresh the entry immediately.
# Other worker processes (if any) pick the change up within _PWD_CHANGED_TTL.
_PWD_CHANGED_TTL = 60.0  # seconds
_pwd_changed_cache: dict = {}   # user_id → (changed_at epoch seconds | None, cached_at monotonic)

def _password_changed_epoch(user_id: int):
    import time
    hit = _pwd_changed_cache.get(user_id)
    now = time.monotonic()
    if hit is not None and now - hit[1] < _PWD_CHANGED_TTL:
        return hit[0]
    from auth import get_password_changed_epoch
    value = get_password_changed_epoch(user_id)   # raises on DB error — not cached
    _pwd_changed_cache[user_id] = (value, now)
    return value

def _password_changed_cache_set(user_id: int, epoch) -> None:
    """Called by the password-change paths — the new value is effective at once in this process."""
    import time
    _pwd_changed_cache[int(user_id)] = (epoch, time.monotonic())

def _jwt_revoked_by_password_change(payload: dict) -> bool:
    uid = payload.get("user_id")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return False
    try:
        changed = _password_changed_epoch(uid)
    except Exception as e:
        # DB unreachable: the request fails at its own DB call anyway; rejecting here
        # would log every user out on a DB blip. Logged, not cached (F9).
        print(f"[session-invalidation] password_changed_at lookup failed user={uid}: {e}")
        return False
    if changed is None:
        return False
    try:
        iat = int(payload.get("iat"))
    except (TypeError, ValueError):
        return True   # no iat → cannot prove it is newer than the change
    return iat < int(changed)


def verify_token(request: Request):
    auth = request.headers.get("Authorization","")
    token = auth.replace("Bearer ","") if auth.startswith("Bearer ") else ""
    payload = _jwt_decode(token) if token else {}
    if not payload: raise HTTPException(401, "Token invalid or expired")
    return {"valid": True, "user_id": payload.get("user_id"), "user_type": payload.get("user_type")}


# ── Admin session JWT (PR 1.5) ──
# /tw-ctrl-login checks the ADMIN_TOKEN password and returns THIS token — the raw
# ADMIN_TOKEN never reaches the browser and is never accepted as a session.
# Claims shape is fixed so plan 5.3 (staff accounts) adds values, not fields:
#   iss "tawasalna" · aud "tw-admin" · sub "owner" (later "staff:<id>")
#   role "admin" (later e.g. "moderator") · perms ["*"] (later e.g. ["reports.read"])
#   iat · exp (iat + _ADMIN_JWT_TTL, ≤ 1h) · jti (random, for a future denylist)
_ADMIN_JWT_TTL = 3600
_ADMIN_JWT_ISS = "tawasalna"
_ADMIN_JWT_AUD = "tw-admin"
_ADMIN_ROLES = {"admin"}   # roles accepted by check_admin; plan 5.3 adds staff roles here

def _admin_jwt_secret_ok() -> bool:
    return (len(ADMIN_JWT_SECRET) >= 32
            and not hmac.compare_digest(ADMIN_JWT_SECRET.encode(), JWT_SECRET.encode())
            and not hmac.compare_digest(ADMIN_JWT_SECRET.encode(), ADMIN_TOKEN.encode()))

def _admin_jwt_issue(sub: str = "owner", role: str = "admin", perms=None) -> str:
    import time, secrets
    if not _admin_jwt_secret_ok():
        raise RuntimeError("ADMIN_JWT_SECRET is not configured")
    now = int(time.time())
    return _jwt_sign({
        "iss": _ADMIN_JWT_ISS, "aud": _ADMIN_JWT_AUD,
        "sub": sub, "role": role, "perms": list(perms) if perms is not None else ["*"],
        "iat": now, "exp": now + _ADMIN_JWT_TTL, "jti": secrets.token_hex(12),
    }, ADMIN_JWT_SECRET)

def _admin_jwt_claims(token: str) -> dict:
    """Admin JWT → claims, or {} (bad signature / expired / wrong iss·aud / no role / lifetime > TTL)."""
    if not _admin_jwt_secret_ok():
        return {}
    c = _jwt_verify(token, ADMIN_JWT_SECRET)
    if not c or c.get("iss") != _ADMIN_JWT_ISS or c.get("aud") != _ADMIN_JWT_AUD:
        return {}
    if not isinstance(c.get("sub"), str) or not c.get("sub") or not isinstance(c.get("perms"), list):
        return {}
    try:
        if int(c["exp"]) - int(c["iat"]) > _ADMIN_JWT_TTL:
            return {}
    except (KeyError, TypeError, ValueError):
        return {}
    return c


def _dev_otp_log(label: str, uid: int) -> None:
    """Log OTP event (not the code) when DEV_OTP_LOG env var is set."""
    if os.environ.get("DEV_OTP_LOG"):
        print(f"[DEV_OTP] {label} triggered for uid={uid}")


def is_email_otp_delivery_available() -> bool:
    """Returns True only when a real email delivery provider is configured.
    No email provider is currently implemented. Enable this function body
    when an actual provider (SendGrid, SES, Resend, etc.) is integrated.
    DEV_OTP_LOG does NOT count as a delivery provider."""
    return False


def is_phone_otp_delivery_available() -> bool:
    """Returns True only when a real SMS delivery provider is configured.
    No SMS provider is currently implemented. Enable this function body
    when an actual provider (Twilio, Vonage, etc.) is integrated.
    DEV_OTP_LOG does NOT count as a delivery provider."""
    return False


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
from collections import defaultdict, deque, OrderedDict
import time as _time
_rate_store = defaultdict(list)
_RATE_LIMIT = 20  # requests per minute per client IP (all _RATE_LIMITED_PATHS together)
_LOGIN_EMAIL_MAX_FAILS = 5      # failed logins per email …
_LOGIN_EMAIL_WINDOW    = 900.0  # … in 15 minutes → that email is locked until the window clears
_LOGIN_LOCKED_MSG = "تم إيقاف تسجيل الدخول لهذا البريد مؤقتاً بسبب محاولات فاشلة متكررة، حاول مرة أخرى بعد 15 دقيقة"

# Per-(user, post) rate limit for appreciation endpoints — guards against auto-clickers
_appr_rate_store: dict = {}   # "{user_id}:{post_id}" -> list[float]
_APPR_RATE_LIMIT  = 10        # max requests
_APPR_RATE_WINDOW = 10.0      # seconds

def _check_appr_rate(user_id: int, post_id: int) -> bool:
    """True = allowed; False = rate-limited. Cleans up old timestamps in-place."""
    key = f"{user_id}:{post_id}"
    now = _time.time()
    if key not in _appr_rate_store:
        _appr_rate_store[key] = []
    _appr_rate_store[key] = [t for t in _appr_rate_store[key] if now - t < _APPR_RATE_WINDOW]
    if len(_appr_rate_store[key]) >= _APPR_RATE_LIMIT:
        return False
    _appr_rate_store[key].append(now)
    return True

# Per-(user, post) rate limit for save endpoint
_save_rate_store: dict = {}
_SAVE_RATE_LIMIT  = 10
_SAVE_RATE_WINDOW = 10.0

def _check_save_rate(user_id: int, post_id: int) -> bool:
    """True = allowed; False = rate-limited."""
    key = f"{user_id}:{post_id}"
    now = _time.time()
    if key not in _save_rate_store:
        _save_rate_store[key] = []
    _save_rate_store[key] = [t for t in _save_rate_store[key] if now - t < _SAVE_RATE_WINDOW]
    if len(_save_rate_store[key]) >= _SAVE_RATE_LIMIT:
        return False
    _save_rate_store[key].append(now)
    return True

# Per-(user, post) rate limit for comment creation
_cmt_create_rate_store: dict = {}
_CMT_CREATE_RATE   = 10
_CMT_CREATE_WINDOW = 60.0

def _check_cmt_create_rate(user_id: int, post_id: int) -> bool:
    key = f"{user_id}:{post_id}"
    now = _time.time()
    if key not in _cmt_create_rate_store:
        _cmt_create_rate_store[key] = []
    _cmt_create_rate_store[key] = [t for t in _cmt_create_rate_store[key] if now - t < _CMT_CREATE_WINDOW]
    if len(_cmt_create_rate_store[key]) >= _CMT_CREATE_RATE:
        return False
    _cmt_create_rate_store[key].append(now)
    return True

# Per-(user, comment) rate limit for comment edits
_cmt_edit_rate_store: dict = {}
_CMT_EDIT_RATE   = 10
_CMT_EDIT_WINDOW = 60.0

def _check_cmt_edit_rate(user_id: int, comment_id: int) -> bool:
    key = f"{user_id}:{comment_id}"
    now = _time.time()
    if key not in _cmt_edit_rate_store:
        _cmt_edit_rate_store[key] = []
    _cmt_edit_rate_store[key] = [t for t in _cmt_edit_rate_store[key] if now - t < _CMT_EDIT_WINDOW]
    if len(_cmt_edit_rate_store[key]) >= _CMT_EDIT_RATE:
        return False
    _cmt_edit_rate_store[key].append(now)
    return True

def _rate_prune(key: str, window: float) -> list:
    now = _time.time()
    hits = [t for t in _rate_store.get(key, ()) if now - t < window]
    if hits:
        _rate_store[key] = hits
    else:
        _rate_store.pop(key, None)
    return hits


def _rate_hit(key: str, limit: int, window: float) -> bool:
    """Sliding window on the shared _rate_store. True = allowed (and counted)."""
    hits = _rate_prune(key, window)
    if len(hits) >= limit:
        return False
    _rate_store[key] = hits + [_time.time()]
    return True


# Per-email login lockout (PR 1.4) — independent of the client IP.
def _login_email_key(email: str) -> str:
    return "login-email:" + (email or "").strip().lower()


def _login_email_locked(email: str) -> bool:
    return len(_rate_prune(_login_email_key(email), _LOGIN_EMAIL_WINDOW)) >= _LOGIN_EMAIL_MAX_FAILS


def _login_email_fail(email: str) -> None:
    _rate_store[_login_email_key(email)].append(_time.time())


def _login_email_reset(email: str) -> None:
    _rate_store.pop(_login_email_key(email), None)


_RATE_LIMITED_PATHS = frozenset({
    "/auth/login", "/auth/register", "/auth/password", "/tw-ctrl-login",
    "/kyc/email/send", "/kyc/phone/send", "/kyc/email/verify", "/kyc/phone/verify",
})


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Only rate limit auth / OTP endpoints — IP from get_client_ip() only
    _p = request.url.path
    if _p in _RATE_LIMITED_PATHS \
            or (_p.startswith("/auth/user/") and _p.endswith("/delete")):  # password-checked account delete
        if not _rate_hit("ip:" + get_client_ip(request), _RATE_LIMIT, 60):
            from fastapi.responses import JSONResponse as _JR
            return _JR(status_code=429, content={"error": "طلبات كثيرة جداً، حاول بعد دقيقة"})
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,  # Must be False with allow_origins=["*"]
)

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
    # ── Secret validation — fail hard if JWT_SECRET missing ──
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError(
            "❌ JWT_SECRET must be set as an environment variable (min 32 chars). "
            "Generate with: openssl rand -hex 32"
        )
    if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 32:
        print("⚠️  ADMIN_TOKEN not configured — admin login will return 503")
    if not _admin_jwt_secret_ok():
        print("⚠️  ADMIN_JWT_SECRET not configured (min 32 chars, must differ from JWT_SECRET / ADMIN_TOKEN) "
              "— admin login + admin endpoints will return 503")
    if not ADMIN_URL_TOKEN:
        print("⚠️  ADMIN_URL_TOKEN not configured — admin panel URL will not be accessible")
    for _line in _supabase_storage_status_lines():
        print(_line)
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
    try:
        _migrate_company_branches()
        print("✅ company_branches table ready")
    except Exception as e:
        print(f"⚠️ company_branches migration failed: {e}")
    try:
        _migrate_company_saved_candidates()
        print("✅ company_saved_candidates table ready")
    except Exception as e:
        print(f"⚠️ company_saved_candidates migration failed: {e}")
    try:
        _migrate_company_candidate_job_refs()
        print("✅ company_candidate_job_refs table ready")
    except Exception as e:
        print(f"⚠️ company_candidate_job_refs migration failed: {e}")
    # Startup-critical: both batch-fetch functions always SELECT candidate_status.
    # A failed migration means every saved-candidates API call returns HTTP 500.
    # Let the exception propagate — FastAPI will refuse to start in a broken schema state.
    _migrate_candidate_status_per_job()
    print("✅ company_candidate_job_refs.candidate_status column ready")
    # Startup-critical: _jwt_decode reads users.password_changed_at (cached).
    _migrate_password_changed_at()
    print("✅ users.password_changed_at column ready")
    try:
        _migrate_kyc_otp_security()
        print("✅ KYC OTP security ready (hashed codes, target/expiry/attempts, legacy codes wiped)")
    except Exception as e:
        print(f"⚠️ KYC OTP security migration failed: {e}")
    try:
        _migrate_jobs_v2()
        print("✅ jobs v2 columns ready")
    except Exception as e:
        print(f"⚠️ jobs v2 migration failed: {e}")
    try:
        _migrate_job_lifecycle()
        print("✅ jobs lifecycle columns ready (closed_at, paused_at, expires_at back-fill)")
    except Exception as e:
        print(f"⚠️ jobs lifecycle migration failed: {e}")
    try:
        _migrate_taxonomy_foundation()
        print("✅ taxonomy foundation ready (skill_catalog + jobs.profession_id)")
    except Exception as e:
        print(f"⚠️ taxonomy foundation migration failed: {e}")
    try:
        _migrate_job_profession_targets()
        print("✅ job_profession_targets table ready")
    except Exception as e:
        print(f"⚠️ job_profession_targets migration failed: {e}")
    try:
        _migrate_notifications_schema_v2()
        print("✅ notifications schema v2 ready (actor_id, entity_id, entity_type, event_key)")
    except Exception as e:
        print(f"⚠️ notifications schema v2 migration failed: {e}")
    try:
        _migrate_notifications_schema_v2_1()
        print("✅ notifications schema v2-1 ready (aggregation_key, aggregation_count, aggregation_kind, last_actor_id, last_event_at, target_type, target_id)")
    except Exception as e:
        print(f"❌ notifications schema v2-1 migration failed: {e}")
        raise
    try:
        _migrate_appointments()
        print("✅ appointments tables ready (appointments, appointment_participants, appointment_events, appointment_messages)")
    except Exception as e:
        print(f"❌ appointments migration failed: {e}")
        raise
    try:
        _migrate_scheduler_jobs()
        print("✅ scheduler_jobs table ready")
    except Exception as e:
        print(f"❌ scheduler_jobs migration failed: {e}")
        raise
    try:
        _migrate_pipeline_schema_v1()
        print("✅ pipeline schema v1 ready (jobs archive, job_pipeline_entries, pipeline_stage_events, pipeline_notes, candidate_bank_notes, company_saved_candidates fields, appointments.pipeline_entry_id)")
    except Exception as e:
        print(f"❌ pipeline schema v1 migration failed: {e}")
        raise
    try:
        _migrate_pr5_pipeline_linking()
        print("✅ PR-5 pipeline linking ready (appointment_type, end_at, applicant_id backfill)")
    except Exception as e:
        print(f"❌ PR-5 pipeline linking migration failed: {e}")
        raise
    try:
        _migrate_applicants_candidates_split()
    except Exception as e:
        print(f"❌ PR-6 (applicants-candidates-split) migration failed: {e}")
        raise
    # NOTE: _migrate_partial_unique_application_id() is NOT called here on startup.
    # The partial UNIQUE index on job_pipeline_entries(application_id) must be created AFTER
    # the backfill + conflict check passes (POST /admin/pipeline/migrate-index).
    # This prevents duplicate application_id conflicts during migration.
    try:
        _idx_status = get_pipeline_application_index_status()
        if _idx_status.get("ready"):
            print("✅ [pipeline] partial UNIQUE index uq_jpe_application_id is ready.")
        else:
            print(
                "⚠️  [pipeline] partial UNIQUE index uq_jpe_application_id is NOT ready "
                f"(exists={_idx_status.get('exists')}, is_unique={_idx_status.get('is_unique')}, "
                f"predicate_valid={_idx_status.get('predicate_valid')}). "
                "Run POST /admin/pipeline/migrate-index?confirm=true after backfill completes."
            )
    except Exception as _idx_exc:
        print(f"⚠️  [pipeline] Could not check index status at startup: {_idx_exc}")
    await _init_asyncpg_pool()

# ── Helpers ──
from page_shell import apply_shell
_html_cache = {}

def read_html(name: str) -> str:
    if name in _html_cache:
        return _html_cache[name]
    try:
        with open(name, "r", encoding="utf-8") as f:
            content = f.read()
        # Page Shell (PR-8 · PAGE-SHELL.md): <!--tw:shell-*--> markers → shared
        # head/scripts partials. A page without markers is returned unchanged.
        content = apply_shell(content, name)
        _html_cache[name] = content
        return content
    except FileNotFoundError:
        # Missing page file → real 404 (never 200 with an error body, never echo the filename).
        print(f"[read_html] page file missing: {name}")
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة")

def check_admin(request: Request, perm: str = None) -> dict:
    """Admin gate — accepts ONLY a valid admin JWT (from /tw-ctrl-login) in X-Admin-Token.
    The raw ADMIN_TOKEN is the login password, never a session token.
    503 = ADMIN_JWT_SECRET not configured · 401 = missing / invalid / expired token
    (admin pages send the admin back to the login screen) · 403 = valid token without
    the role / permission. `perm` is for plan 5.3 staff roles; "*" grants everything."""
    if not _admin_jwt_secret_ok():
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    claims = _admin_jwt_claims(request.headers.get("X-Admin-Token", ""))
    if not claims:
        raise HTTPException(status_code=401, detail="انتهت جلسة الإدارة، سجّل الدخول من جديد")
    perms = claims.get("perms") or []
    if claims.get("role") not in _ADMIN_ROLES or (perm and "*" not in perms and perm not in perms):
        raise HTTPException(status_code=403, detail="Forbidden")
    return claims


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

# ── Taxonomy-aware feed helpers ──────────────────────────────────────────────

_FEED_JOB_POOL = 200  # jobs fetched for scoring; top N returned after sort


def _feed_user_context(conn, user_id, user_type):
    """Return (profession_id, category_group, skills_set) for the current user.
    Always safe: returns (None, None, set()) on any error or for non-emp users.
    Combines skills from user_skills table + profiles.skills legacy array."""
    if user_type != "emp":
        return None, None, set()
    try:
        prof_rows = conn.run(
            "SELECT profession_id, skills FROM profiles WHERE user_id = :uid",
            uid=user_id,
        )
        profession_id = None
        legacy_skills: set = set()
        if prof_rows:
            profession_id = prof_rows[0][0]
            raw = prof_rows[0][1] or []
            legacy_skills = {s.lower().strip() for s in raw if s}

        category_group = None
        if profession_id:
            pg = conn.run(
                "SELECT category_group FROM profession_categories WHERE id = :pid",
                pid=profession_id,
            )
            if pg and pg[0][0]:
                category_group = pg[0][0].strip()

        skill_rows = conn.run(
            "SELECT skill FROM user_skills WHERE user_id = :uid", uid=user_id
        )
        table_skills = {(r[0] or "").lower().strip() for r in (skill_rows or []) if r[0]}

        return profession_id, category_group, (legacy_skills | table_skills)
    except Exception:
        return None, None, set()


def _save_accepted_professions(conn, job_id: int, profession_ids, primary_pid=None):
    """Snapshot-replace accepted professions for a job.

    Validates the full list BEFORE DELETE so a bad request never wipes existing data.
    Raises ValueError (caught by endpoint → HTTP 422) on any rule violation.
    Owner must be verified by the caller before invoking this function.
    """
    if profession_ids is None:
        return
    # Validate first — no mutation if validation fails
    clean = _validate_accepted_profession_ids(conn, primary_pid, profession_ids)
    # Safe to mutate: DELETE old entries, then INSERT validated list
    conn.run("DELETE FROM job_profession_targets WHERE job_id = :jid", jid=job_id)
    for i, pid in enumerate(clean):
        conn.run(
            "INSERT INTO job_profession_targets (job_id, profession_id, display_order) "
            "VALUES (:jid, :pid, :ord)",
            jid=job_id, pid=pid, ord=i
        )


def _taxonomy_score(job, user_pid, user_pgroup, user_skills, accepted_pids=None):
    """Compute taxonomy relevance score for a feed job item.

    Scoring (additive):
      +100  exact profession match (job.profession_id == user.profession_id)
      +80   user's profession is in the job's accepted_profession_ids
      +40   same category_group, different profession (elif — no double-count)
      +10   legacy job: has category string but no profession_id (flat boost)
      +10   per shared skill between user_skills and job.skills
    Returns 0 for non-emp users or missing context (safe default).
    """
    if not user_pid and not user_pgroup and not user_skills:
        return 0  # no user context — feed stays sorted by recency only

    score = 0
    job_pid    = job.get("profession_id")
    job_pgroup = (job.get("profession_category_group") or "").strip()

    if job_pid and user_pid:
        if job_pid == user_pid:
            score += 100
        elif accepted_pids and user_pid in accepted_pids:
            score += 80
        elif job.get("accepts_all_professions") and user_pid:
            score += 60
        elif job_pgroup and user_pgroup and job_pgroup == user_pgroup:
            score += 40
    elif not job_pid and accepted_pids and user_pid and user_pid in accepted_pids:
        score += 80
    elif not job_pid and job.get("accepts_all_professions") and user_pid:
        score += 60
    elif not job_pid and job.get("category"):
        score += 10  # legacy job with category text — tiny boost over uncategorized

    if user_skills:
        job_skills_raw = job.get("skills") or []
        job_skills = {s.lower().strip() for s in job_skills_raw if s}
        if job_skills:
            score += len(user_skills & job_skills) * 10

    return score


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
        # ── User context for taxonomy-aware scoring ────────────────────────────
        u_pid, u_pgroup, u_skills = _feed_user_context(conn, user_id, user_type)

        # ── Opportunities (jobs) — scored by taxonomy relevance ───────────────
        if filter in ("all", "opportunities"):
            opp_lim = lim if filter == "opportunities" else max(1, lim // 3)
            # Fetch a larger pool so scoring can promote the most relevant jobs
            pool = max(opp_lim, _FEED_JOB_POOL)
            rows = conn.run(
                """SELECT j.id, j.title, j.location, j.job_type,
                          j.salary_min, j.salary_max, j.currency,
                          j.skills, j.created_at,
                          j.profession_id, j.category,
                          u.full_name AS company_name,
                          u.tw_id    AS company_tw_id,
                          u.id       AS company_id,
                          COALESCE(p.avatar_url,'')          AS company_logo,
                          COALESCE(pc.name_ar,'')            AS profession_name_ar,
                          COALESCE(pc.name_en,'')            AS profession_name_en,
                          COALESCE(pc.icon,'')               AS profession_icon,
                          COALESCE(pc.category_group,'')     AS profession_category_group
                   FROM jobs j
                   JOIN users u ON j.company_id = u.id
                   LEFT JOIN profiles p ON j.company_id = p.user_id
                   LEFT JOIN profession_categories pc ON j.profession_id = pc.id
                   WHERE j.status IN ('active', 'open')
                     AND j.archived_at IS NULL
                     AND (j.expires_at IS NULL OR j.expires_at > NOW())
                   ORDER BY j.created_at DESC
                   LIMIT :pool""",
                pool=pool,
            )
            cols = [
                "id","title","location","job_type","salary_min","salary_max","currency",
                "skills","created_at","profession_id","category",
                "company_name","company_tw_id","company_id","company_logo",
                "profession_name_ar","profession_name_en","profession_icon",
                "profession_category_group",
            ]
            job_items = []
            for r in (rows or []):
                d = dict(zip(cols, r))
                d["type"] = "opportunity"
                d["opp_type"] = "job"
                if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                if isinstance(d.get("skills"), list):
                    d["skills"] = [str(s) for s in d["skills"]]
                job_items.append(d)

            # Batch-fetch accepted profession IDs — single query, no N+1
            feed_job_ids = [d["id"] for d in job_items if d.get("id")]
            acc_map = _fetch_accepted_professions_batch(conn, feed_job_ids) if feed_job_ids else {}

            for d in job_items:
                acc_entries = acc_map.get(d["id"], [])
                d["accepted_professions"] = acc_entries
                acc_pids = {e["id"] for e in acc_entries}
                d["_score"] = _taxonomy_score(d, u_pid, u_pgroup, u_skills, acc_pids)

            # Sort: recency first (stable), then score (stable tiebreak = recency)
            job_items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
            job_items.sort(key=lambda x: x["_score"], reverse=True)

            for item in job_items[:opp_lim]:
                item.pop("_score", None)
                item.pop("category", None)    # internal field; profession_* is the public form
                items.append(item)

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


# ── Legacy redirect page (single source for every retired page URL) ─────────
# Served by: /profile, /profile.html, /company, /company.html, /edu, /edu.html,
# /home.html, /jobs.html, /company-profile, /company-profile.html.
#   ?id=<numeric user id> of an existing account (any user_type)
#       → server-side 302 → /u/{tw_id} of that account (F7 / F14)
#   no id / id not 1–18 ASCII digits / id not found
#       → _LEGACY_REDIRECT_HTML, which decides from TwAuthSync
#         (twEntryDestination() in tw_shared.js) — never tw_user alone:
#           authenticated → twAccountHref(u) = /u/{tw_id}
#           guest / expired / stale / invalid → /login (stale session invalidated first)
_LEGACY_REDIRECT_HTML = (
    '<!doctype html><html dir="rtl"><head><meta charset="utf-8">'
    '<title>جاري التوجيه…</title></head><body>'
    '<script src="/tw_shared.js"></script>'
    '<script src="/static/shared/auth-sync.js"></script>'
    '<script>(function(){'
    'var d=(typeof twEntryDestination==="function")?twEntryDestination():null;'
    'location.replace(d||"/login");'
    '})();</script></body></html>'
)

def _tw_id_for_user_id(user_id: int):
    """Return the tw_id of any account (emp / co / edu) by numeric id, or None.
    Single lookup for every legacy ?id= redirect."""
    conn = get_conn()
    try:
        rows = conn.run("SELECT tw_id FROM users WHERE id=:id", id=user_id)
        return rows[0][0] if rows and rows[0][0] else None
    finally:
        release_conn(conn)

def _legacy_redirect_page(id: Optional[str] = None):
    """Legacy page URL → 302 /u/{tw_id} when ?id= names an existing account;
    otherwise the shared client-side redirect page."""
    # ASCII digits only (str.isdigit() also accepts "²" / "١٢" → int() 500) and
    # ≤ 18 digits so the value always fits users.id BIGINT (no DB overflow 500).
    if id is not None and id.isascii() and id.isdigit() and len(id) <= 18:
        tw = _tw_id_for_user_id(int(id))
        if tw:
            return RedirectResponse(url=f'/u/{tw}', status_code=302)
    return HTMLResponse(content=_LEGACY_REDIRECT_HTML)

for _legacy_path in ("/profile", "/profile.html", "/company", "/company.html",
                     "/edu", "/edu.html", "/home.html", "/jobs.html",
                     "/company-profile", "/company-profile.html"):
    app.add_api_route(_legacy_path, _legacy_redirect_page, methods=["GET"],
                      response_class=HTMLResponse, include_in_schema=False)

@app.get("/profile-showcase", response_class=HTMLResponse)
def profile_showcase(): return read_html("profile-showcase.html")

@app.get("/profile-showcase.html", response_class=HTMLResponse)
def profile_showcase_html(): return read_html("profile-showcase.html")

@app.get("/u", response_class=HTMLResponse)
def public_profile_no_id():
    """Bare /u without a tw_id — return 404 rather than an empty profile."""
    raise HTTPException(status_code=404, detail="معرف الحساب مفقود")

@app.get("/u/{tw_id}", response_class=HTMLResponse)
def public_profile_smart_router(tw_id: str):
    """Smart Public Router — resolves tw_id via DB (users.user_type is the source
    of truth) and serves the correct page per account type.

    Decision table:
      emp  → profile-showcase.html  (window._scProfileIdFromRoute)
      co   → company-profile.html   (window._companyProfileIdFromRoute, _companyTwIdFromRoute)
      edu  → edu-profile.html       (window._eduProfileIdFromRoute, _eduTwIdFromRoute)

    The prefix (U/C/T) is a hint only; user_type from DB is authoritative.
    The numeric id is never exposed in the public URL.
    """
    info = get_user_info_by_tw_id(tw_id)
    if not info:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")

    uid   = int(info['id'])         # safe: always integer from DB
    utype = info['user_type']
    tw    = json.dumps(info['tw_id'])   # json.dumps handles any string safely

    if utype == 'emp':
        base = read_html("profile-showcase.html")
        snippet = f'<script>window._scProfileIdFromRoute={uid};</script>'
    elif utype == 'co':
        base = read_html("company-profile.html")
        snippet = f'<script>window._companyProfileIdFromRoute={uid};window._companyTwIdFromRoute={tw};</script>'
    elif utype == 'edu':
        base = read_html("edu-profile.html")
        snippet = f'<script>window._eduProfileIdFromRoute={uid};window._eduTwIdFromRoute={tw};</script>'
    else:
        raise HTTPException(status_code=404, detail="نوع الحساب غير معروف")

    injected = base.replace('</head>', snippet + '</head>', 1)
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
        "can_rate":      viewer_type == "public-user" and token_utype == "emp",
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
            "SELECT COUNT(*) FROM jobs WHERE company_id = :cid AND status = 'active' AND archived_at IS NULL",
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
    posts_count = get_company_posts_count(resolved_id)
    views_count = get_profile_views_count(resolved_id)
    stats = {
        "jobs_count":       jobs_count,
        "posts_count":      posts_count,
        "views_count":      views_count,
        "followers_count":  extras["followers_count"],
        "verified_count":   verified_count,
        "rating_avg":       extras["rating_avg"],
        "rating_count":     extras["rating_count"],
    }

    # ── Viewer-specific flags into permissions (Phase 2, in-scope) ──
    permissions["is_following"] = extras["is_following"]
    permissions["my_rating"]    = extras["my_rating"]

    # ── Strip private fields from profile for non-owners ──
    if not is_owner:
        for _private in ("email", "phone", "created_at"):
            profile.pop(_private, None)

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
    cover_url:     Optional[str] = None


class BranchItemInput(BaseModel):
    branch_name: Optional[str] = None
    country:     str
    city:        Optional[str] = None
    district:    Optional[str] = None


class BranchesInput(BaseModel):
    branches: List[BranchItemInput] = Field(default_factory=list)


class UpdateSavedCandidateInput(BaseModel):
    status:           Optional[str]       = None
    notes:            Optional[str]       = None
    job_id:           Optional[int]       = None
    rating:           Optional[int]       = None
    priority:         Optional[str]       = None
    tags:             Optional[List[str]] = None
    follow_up_at:     Optional[str]       = None
    follow_up_status: Optional[str]       = None


class UpdateCandidateJobStatusInput(BaseModel):
    # Field(...) makes this required in both Pydantic v1 and v2 — no implicit None default.
    # Body {} → 422. {"candidate_status": null} → valid (explicit clear). "saved" etc. → valid.
    candidate_status: Optional[str] = Field(...)


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
    if payload.get("cover_url"):
        _validate_stored_image_url(payload["cover_url"], "company-cover", company_id,
                                   get_company_profile_row(company_id).get("cover_url"))
    updated = update_company_profile(company_id, payload)
    if not updated:
        raise HTTPException(400, "لا توجد بيانات للحفظ")
    company = get_company_profile_row(company_id)
    return {"status": "success", "company": company}


class CoverUrlInput(BaseModel):
    cover_url: str


@app.put("/company/cover/{company_id}")
def update_co_cover(company_id: int, data: CoverUrlInput, token=Depends(verify_token)):
    """Update cover photo URL only. Does not require industry. Owner JWT required."""
    tok_uid   = token.get("user_id")
    tok_utype = token.get("user_type")
    if str(tok_uid) != str(company_id) or tok_utype != "co":
        raise HTTPException(403, "غير مصرح")
    if data.cover_url:
        _validate_stored_image_url(data.cover_url, "company-cover", company_id,
                                   get_company_profile_row(company_id).get("cover_url"))
    updated = update_company_profile(company_id, {"cover_url": data.cover_url})
    if not updated:
        raise HTTPException(500, "تعذّر حفظ الغلاف")
    return {"status": "success"}


# ── Company Branches ──────────────────────────────────────────────────────────

@app.get("/company/branches/{company_id}")
def get_branches(company_id: int):
    """Public — returns all branches for a company ordered by display_order."""
    return {"branches": get_company_branches(company_id)}


@app.put("/company/branches/{company_id}")
def put_branches(company_id: int, data: BranchesInput, token=Depends(verify_token)):
    """Replace all branches atomically. Owner only. Max 10 branches.
    Auth: JWT Bearer only — X-User-Id forbidden.
    Ownership: token.user_id == company_id AND user_type == 'co'.
    """
    tok_uid   = token.get("user_id")
    tok_utype = token.get("user_type")
    if str(tok_uid) != str(company_id) or tok_utype != "co":
        raise HTTPException(403, "غير مصرح")
    if len(data.branches) > 10:
        raise HTTPException(400, "لا يمكن إضافة أكثر من 10 فروع")
    branches_dicts = [b.dict() for b in data.branches]
    try:
        saved = save_company_branches(company_id, branches_dicts)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "success", "branches": saved}


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

@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN, response_class=HTMLResponse)
def admin_page(): return read_html("admin.html")

# ══════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════
class RegisterInput(BaseModel):
    # Structured name for emp (G-contract): first_name + last_name required, middle_name optional.
    # For emp: full_name is ignored if first_name/last_name are provided (structured path takes precedence).
    # For co/edu: full_name is used; first_name/last_name are ignored even if sent.
    full_name:   Optional[str] = None
    first_name:  Optional[str] = None
    middle_name: Optional[str] = None
    last_name:   Optional[str] = None
    email:    str
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
    # PR-7a: the client sends `kind` only — bucket + filename are decided by
    # the server (_UPLOAD_KINDS). user_id / bucket / filename are accepted for
    # backward compatibility and ignored (user_id comes from the JWT only).
    kind: Optional[str] = None
    data_url: str
    user_id: Optional[int] = None
    bucket: Optional[str] = None
    filename: Optional[str] = None

class AdminLogoInput(BaseModel):
    # PR-7a: `filename` is the logo slot key (logo_wide | logo_tall), not a
    # storage file name. Other legacy fields (user_id / bucket) are ignored.
    filename: Optional[str] = None
    data_url: str
    user_id: Optional[int] = None
    bucket: Optional[str] = None

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
    model_config = ConfigDict(extra='ignore')
    email: str

class KYCCodeInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    code: str

class KYCPhoneInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    phone: str

class KYCDocsInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id_front_url: str
    selfie_url: Optional[str] = None

class KYCAdminInput(BaseModel):
    note: Optional[str] = ""

class CompanyRateInput(BaseModel):
    score: int
    comment: Optional[str] = None

ALLOWED_POST_COLORS = {"teal", "blue", "purple", "orange", "pink", "red", "gold", "gray"}

class CompanyPostInput(BaseModel):
    body: str
    tags: Optional[list] = None
    theme_color: Optional[str] = None
    comments_enabled: Optional[bool] = True

class CompanyPostUpdateInput(BaseModel):
    body: str
    tags: Optional[list] = None
    theme_color: Optional[str] = None
    comments_enabled: Optional[bool] = True

class PostViewInput(BaseModel):
    visitor_key: Optional[str] = None  # anonymous visitor key (UUID, max 64 chars)

class JobInput(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = "دوام كامل"
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = "USD"
    experience_years: Optional[int] = 0
    skills: Optional[List[str]] = None
    category: Optional[str] = None
    work_mode: Optional[str] = "في الموقع"
    salary_hidden: Optional[bool] = False
    profession_id: Optional[int] = None
    accepted_profession_ids: Optional[List[int]] = None
    accepts_all_professions: Optional[bool] = None
    duration_days: Optional[int] = None

class JobApplyInput(BaseModel):
    user_id: Optional[int] = None  # kept for backward compat — ignored; token user_id is used
    cover_letter: Optional[str] = ""

class AppStatusInput(BaseModel):
    status: str  # pending, viewed, accepted, contacted, interview, hired, rejected

class JobStatusInput(BaseModel):
    status: str  # active, paused

class SkillInput(BaseModel):
    skill: str
    level: Optional[str] = None
    note: Optional[str] = None

class LangInput(BaseModel):
    language: str
    level: Optional[str] = None

# §54 rule 4b — the ONLY server check for a user-entered external link (twin of
# twSafeLinkUrl in tw_shared.js): http:// or https:// + host char, no whitespace /
# control char, ≤ 2048 (value stripped first). Empty → None (optional) or 422 (required).
_EXTERNAL_URL_RE = re.compile(r'^https?://[^/\\]', re.IGNORECASE)
_EXTERNAL_URL_BAD_CHARS_RE = re.compile(r'[\x00-\x20\x7f-\x9f\u2028\u2029]')

class ExternalUrlError(Exception):
    def __init__(self, field: str, message: str):
        self.field, self.message = field, message

@app.exception_handler(ExternalUrlError)
async def external_url_error_handler(request, exc):
    # Field-specific 422 — same shape as PUT /profile field errors (errors[] + detail.message)
    return JSONResponse(status_code=422, content={
        "ok": False, "error": exc.message,
        "errors": [{"field": exc.field, "code": "invalid_url", "message": exc.message}],
        "detail": {"status": "error", "message": exc.message, "field": exc.field},
    })

def _validate_external_url(url, field: str, label: str = "الرابط", required: bool = False):
    if url is not None and not isinstance(url, str):
        raise ExternalUrlError(field, f"{label} غير صالح")
    value = (url or "").strip()
    if not value:
        if required:
            raise ExternalUrlError(field, f"{label} مطلوب")
        return None
    if (len(value) > 2048 or _EXTERNAL_URL_BAD_CHARS_RE.search(value)
            or not _EXTERNAL_URL_RE.match(value)):
        raise ExternalUrlError(field, f"{label} غير صالح — يجب أن يبدأ بـ https:// أو http://")
    return value

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
    user_id: Optional[int] = None   # ignored server-side — owner determined from JWT
    item_type: Optional[str] = None   # exp / edu / course
    item_id: Optional[int] = None
    item_title: Optional[str] = None
    item_company: Optional[str] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None

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

@app.get("/sitemap.xml")
def sitemap():
    urls = [
        "https://tawasolna.com/",
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

# App icons (PWA + favicon) — real files in static/icons/, generated from the
# official logo by scripts/gen_app_icons.py (SYSTEMS_INDEX §32). Fixed allowlist.
_APP_ICON_FILES = {
    "/icon-192.png":          ("icon-192.png",          "image/png"),
    "/icon-512.png":          ("icon-512.png",          "image/png"),
    "/icon-maskable-512.png": ("icon-maskable-512.png", "image/png"),
    "/apple-touch-icon.png":  ("apple-touch-icon.png",  "image/png"),
    "/favicon.ico":           ("favicon.ico",           "image/x-icon"),
}

@app.get("/icon-192.png", include_in_schema=False)
@app.get("/icon-512.png", include_in_schema=False)
@app.get("/icon-maskable-512.png", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
def app_icon(request: Request):
    filename, mime = _APP_ICON_FILES[request.url.path]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "icons", filename)
    try:
        with open(path, "rb") as f:
            content = f.read()
    except OSError as e:
        print(f"[ERROR] app icon missing: {path} ({e})")
        raise HTTPException(404, "Not found")
    return Response(content=content, media_type=mime,
                    headers={"Cache-Control": "public, max-age=604800"})


# ── WebSocket Real-time Messages ──────────────────────────────────────────────
# First-Message JWT Authentication Protocol (security/ws-auth-hardening)
#
# Application Close Codes:
#   4001 — Unauthorized    : missing/invalid/expired JWT, missing/invalid claims
#   4002 — Auth Failed     : oversized frame, malformed JSON, wrong type, auth timeout
#   4003 — Forbidden       : JWT user_id ≠ URL path user_id
#   4004 — Bad Payload     : malformed JSON or non-dict in message loop; oversize frame
#   4005 — Policy          : typing rate limit exceeded; repeated unknown-event violations
#   4006 — Origin Denied   : Origin header not in allowed origins (fail-closed)
#   4007 — Too Many Conns  : user already has _WS_MAX_CONN_PER_USER connections
#
# Identity source: JWT claims only. URL path user_id is routing hint only.
# URL path MUST match JWT; it is never trusted as identity by itself.
# Origin policy: production defaults (tawasolna.com); APP_ENV=development adds localhost.
# WS_ALLOWED_ORIGINS="*" is permanently forbidden; "null" origin is always rejected.
# ──────────────────────────────────────────────────────────────────────────────
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict

_WS_AUTH_TIMEOUT      = 5.0       # seconds to wait for first auth message
_WS_AUTH_FRAME_MAX    = 8_192     # 8 KB hard ceiling for the auth frame specifically
_WS_MAX_PAYLOAD       = 65_536    # 64 KB hard ceiling per frame in the message loop
_WS_MAX_CONN_PER_USER = 10        # max simultaneous WS connections per user (→ 4007)

_WS_TYPING_MAX    = 10
_WS_TYPING_WINDOW = 10.0
_ws_typing_log: Dict[int, deque] = {}

_ws_event_violations: Dict[int, int] = {}
_WS_MAX_VIOLATIONS = 10

_WS_CTRL_MAX    = 30
_WS_CTRL_WINDOW = 10.0
_ws_ctrl_log: Dict[int, deque] = {}

# ── Origin policy — fail closed ───────────────────────────────────────────────
# Production: only tawasolna.com and www.tawasolna.com are allowed.
# Development (APP_ENV=development): localhost variants are also allowed.
# WS_ALLOWED_ORIGINS="*" is forbidden — enforced at startup with RuntimeError.
# No-origin requests (native mobile/desktop clients) are allowed when JWT is valid.
# "null" origin is always rejected (sandboxed iframe / local file protocol).
_APP_ENV = os.environ.get("APP_ENV", "production").lower()
_WS_PROD_ORIGINS = frozenset({"https://tawasolna.com", "https://www.tawasolna.com"})
_WS_DEV_ORIGINS  = frozenset({
    "http://localhost:8000", "http://localhost:3000", "http://localhost:5173",
    "http://127.0.0.1:8000", "http://127.0.0.1:3000", "http://127.0.0.1:5173",
})
_WS_ALLOWED_ORIGINS_RAW = os.environ.get("WS_ALLOWED_ORIGINS", "").strip()
if _WS_ALLOWED_ORIGINS_RAW == "*":
    raise RuntimeError(
        "WS_ALLOWED_ORIGINS='*' is forbidden — WebSocket origin policy must be "
        "a closed list of origins. Unset WS_ALLOWED_ORIGINS to use production defaults."
    )
if _WS_ALLOWED_ORIGINS_RAW:
    _WS_ALLOWED_ORIGINS: frozenset = frozenset(
        o.strip() for o in _WS_ALLOWED_ORIGINS_RAW.split(",") if o.strip()
    )
elif _APP_ENV == "development":
    _WS_ALLOWED_ORIGINS = _WS_PROD_ORIGINS | _WS_DEV_ORIGINS
else:
    _WS_ALLOWED_ORIGINS = _WS_PROD_ORIGINS


# ── Bounded TTL cache for conversation membership ─────────────────────────────
class _BoundedTTLCache:
    """LRU-ish bounded cache with per-entry TTL. Evicts oldest entry on overflow."""
    __slots__ = ("_maxsize", "_pos_ttl", "_neg_ttl", "_store")

    def __init__(self, maxsize: int, pos_ttl: float, neg_ttl: float):
        self._maxsize = maxsize
        self._pos_ttl = pos_ttl
        self._neg_ttl = neg_ttl
        self._store: OrderedDict = OrderedDict()

    def get(self, key) -> "Optional[bool]":
        entry = self._store.get(key)
        if entry is None:
            return None
        value, exp = entry
        if time.time() > exp:
            del self._store[key]
            return None
        return value

    def set(self, key, value: bool) -> None:
        ttl = self._pos_ttl if value else self._neg_ttl
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self._maxsize:
            self._store.popitem(last=False)  # evict oldest entry
        self._store[key] = (value, time.time() + ttl)

    def warm(self, key) -> None:
        self.set(key, True)


_ws_conv_cache = _BoundedTTLCache(maxsize=5000, pos_ttl=300.0, neg_ttl=60.0)
_WS_VALID_USER_TYPES = frozenset({"emp", "co", "edu"})


def _ws_origin_ok(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin", "")
    if origin == "null":
        return False  # sandboxed iframe / local file — always reject
    if not origin:
        return True   # native client (mobile/desktop) — allowed with valid JWT
    return origin in _WS_ALLOWED_ORIGINS


def _ws_typing_rate_ok(user_id: int) -> bool:
    now = time.time()
    q = _ws_typing_log.setdefault(user_id, deque())
    while q and now - q[0] > _WS_TYPING_WINDOW:
        q.popleft()
    if len(q) >= _WS_TYPING_MAX:
        return False
    q.append(now)
    return True


# ORDERING CONTRACT: _ws_ctrl_rate_ok() MUST be called BEFORE _ws_conversation_exists_async().
def _ws_ctrl_rate_ok(user_id: int) -> bool:
    now = time.time()
    q = _ws_ctrl_log.setdefault(user_id, deque())
    while q and now - q[0] > _WS_CTRL_WINDOW:
        q.popleft()
    if len(q) >= _WS_CTRL_MAX:
        return False
    q.append(now)
    return True


def _ws_cleanup_typing_log(user_id: int) -> None:
    """Only clears rate-limit state when no WS connections remain.
    Prevents a Tab-B disconnect from resetting Tab-A's rate-limit counters."""
    if user_id not in ws_manager.active or not ws_manager.active[user_id]:
        _ws_typing_log.pop(user_id, None)
        _ws_ctrl_log.pop(user_id, None)
        _ws_event_violations.pop(user_id, None)


async def _ws_conversation_exists_async(a: int, b: int) -> bool:
    """Async conversation membership check — uses asyncpg pool or asyncio.to_thread fallback."""
    key = (min(a, b), max(a, b))
    cached = _ws_conv_cache.get(key)
    if cached is not None:
        return cached
    result = False
    try:
        if _asyncpg_pool is not None:
            async with _asyncpg_pool.acquire() as pg_conn:
                row = await pg_conn.fetchrow(
                    "SELECT 1 FROM messages "
                    "WHERE (sender_id=$1 AND receiver_id=$2) "
                    "   OR (sender_id=$2 AND receiver_id=$1) "
                    "LIMIT 1",
                    a, b,
                )
                result = row is not None
        else:
            def _sync_check():
                conn = get_conn()
                try:
                    rows = conn.run(
                        "SELECT 1 FROM messages "
                        "WHERE (sender_id=:a AND receiver_id=:b) "
                        "   OR (sender_id=:b AND receiver_id=:a) "
                        "LIMIT 1",
                        a=a, b=b,
                    )
                    return bool(rows)
                finally:
                    release_conn(conn)
            result = await asyncio.to_thread(_sync_check)
    except Exception as exc:
        print(f"[WS-SEC] conv_exists_error pair=({min(a,b)},{max(a,b)}): {type(exc).__name__}")
        return False  # fail closed — do not cache on error
    _ws_conv_cache.set(key, result)
    return result


def _ws_validate_auth_frame(raw: str) -> "tuple":
    """Validate the first WS frame. Returns (auth_uid, 0) on success or (-1, close_code)."""
    if len(raw) > _WS_AUTH_FRAME_MAX:
        return -1, 4002
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return -1, 4002
    if not isinstance(msg, dict):
        return -1, 4002
    if msg.get("type") != "auth":
        return -1, 4002
    token = msg.get("token", "")
    if not isinstance(token, str) or not token:
        return -1, 4001
    payload = _jwt_decode(token)
    if not payload:
        return -1, 4001
    jwt_user_id = payload.get("user_id")
    user_type   = payload.get("user_type")
    if jwt_user_id is None or user_type is None:
        return -1, 4001
    if user_type not in _WS_VALID_USER_TYPES:
        return -1, 4001
    try:
        auth_uid = int(jwt_user_id)
        if auth_uid <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return -1, 4001
    return auth_uid, 0


class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, list] = {}
        self.active_conversations: Dict[int, int] = {}
        self._conv_ws_owner: Dict[int, object] = {}

    def register(self, user_id: int, ws: WebSocket) -> bool:
        """Register a WebSocket AFTER JWT auth succeeds. Returns False if limit exceeded."""
        conns = self.active.get(user_id)
        if conns is None:
            self.active[user_id] = [ws]
            return True
        if ws in conns:
            return True  # duplicate — idempotent
        if len(conns) >= _WS_MAX_CONN_PER_USER:
            return False  # too many connections → caller sends 4007
        conns.append(ws)
        return True

    def disconnect(self, user_id: int, ws: WebSocket):
        if user_id in self.active:
            self.active[user_id] = [w for w in self.active[user_id] if w != ws]
            if not self.active[user_id]:
                del self.active[user_id]
            if self._conv_ws_owner.get(user_id) is ws:
                self.active_conversations.pop(user_id, None)
                self._conv_ws_owner.pop(user_id, None)

    async def send_to_user(self, user_id: int, data: dict) -> bool:
        if user_id not in self.active or not self.active[user_id]:
            return False
        sent, dead = False, []
        for ws in list(self.active[user_id]):   # iterate a snapshot
            try:
                await ws.send_text(json.dumps(data))
                sent = True
            except Exception:
                dead.append(ws)
        for d in dead:
            self.disconnect(user_id, d)         # handles _conv_ws_owner + active_conversations
        if dead and user_id not in self.active: # last conn died — clean rate-limit state
            _ws_cleanup_typing_log(user_id)
        return sent


ws_manager = ConnectionManager()


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    # ── Step 1: Accept HTTP upgrade (no registration yet) ────────────────────
    await websocket.accept()

    # ── Step 2: Origin check — fail closed ───────────────────────────────────
    if not _ws_origin_ok(websocket):
        print(f"[WS-SEC] ORIGIN_DENIED path_uid={user_id} origin={websocket.headers.get('origin','<none>')}")
        await websocket.close(code=4006)
        return

    # ── Step 3: First-message JWT authentication (5-second window) ───────────
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=_WS_AUTH_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"[WS-SEC] AUTH_TIMEOUT path_uid={user_id}")
        await websocket.close(code=4002)
        return
    except Exception:
        return  # connection dropped before auth message

    auth_uid, err_code = _ws_validate_auth_frame(raw)
    if err_code:
        print(f"[WS-SEC] AUTH_FAIL code={err_code} path_uid={user_id}")
        await websocket.close(code=err_code)
        return

    # Identity is ALWAYS from JWT — URL path must match but never overrides JWT
    if auth_uid != user_id:
        print(f"[WS-SEC] AUTH_UID_MISMATCH jwt_uid={auth_uid} path_uid={user_id}")
        await websocket.close(code=4003)
        return

    # ── Step 4: Register only after successful auth ───────────────────────────
    if not ws_manager.register(auth_uid, websocket):
        print(f"[WS-SEC] TOO_MANY_CONN uid={auth_uid}")
        await websocket.close(code=4007)
        return

    print(f"[WS] CONNECTED uid={auth_uid}")
    try:
        await websocket.send_text(json.dumps({"type": "auth_ok", "user_id": auth_uid}))
    except Exception:
        ws_manager.disconnect(auth_uid, websocket)
        return

    # ── Step 5: Authenticated message loop ────────────────────────────────────
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

            if len(raw) > _WS_MAX_PAYLOAD:
                print(f"[WS-SEC] OVERSIZE uid={auth_uid}")
                try:
                    await websocket.close(code=4004)
                except Exception:
                    pass
                break

            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                print(f"[WS-SEC] INVALID_JSON uid={auth_uid}")
                try:
                    await websocket.close(code=4004)
                except Exception:
                    pass
                break

            if not isinstance(msg, dict):
                print(f"[WS-SEC] NON_DICT_MSG uid={auth_uid}")
                try:
                    await websocket.close(code=4004)
                except Exception:
                    pass
                break

            msg_type_raw = msg.get("type")
            if not isinstance(msg_type_raw, str) or not msg_type_raw or len(msg_type_raw) > 80:
                print(f"[WS-SEC] INVALID_TYPE uid={auth_uid}")
                try:
                    await websocket.close(code=4004)
                except Exception:
                    pass
                break
            msg_type = msg_type_raw

            if msg_type == "active_conversation":
                other_id = msg.get("other_id")
                if other_id is not None:
                    try:
                        other_id = int(other_id)
                        if other_id <= 0:
                            raise ValueError()
                    except (ValueError, TypeError):
                        continue
                    # ORDERING CONTRACT: rate limit BEFORE DB lookup — must never be reversed
                    if not _ws_ctrl_rate_ok(auth_uid):
                        print(f"[WS-SEC] CTRL_RATE_LIMIT uid={auth_uid}")
                        try:
                            await websocket.close(code=4005)
                        except Exception:
                            pass
                        break
                    if not await _ws_conversation_exists_async(auth_uid, other_id):
                        print(f"[WS-SEC] ACTIVE_CONV_UNAUTH uid={auth_uid} other={other_id}")
                        continue
                    ws_manager.active_conversations[auth_uid] = other_id
                    ws_manager._conv_ws_owner[auth_uid] = websocket

            elif msg_type == "inactive_conversation":
                if ws_manager._conv_ws_owner.get(auth_uid) is websocket:
                    ws_manager.active_conversations.pop(auth_uid, None)
                    ws_manager._conv_ws_owner.pop(auth_uid, None)

            elif msg_type in ("typing", "typing_stop"):
                to_id = msg.get("to_user_id")
                if to_id is not None:
                    try:
                        to_id = int(to_id)
                        if to_id <= 0:
                            raise ValueError()
                    except (ValueError, TypeError):
                        continue
                    # Rate limit BEFORE DB lookup — drop excess, never close the authenticated socket
                    if not _ws_typing_rate_ok(auth_uid):
                        continue  # drop excess typing event; do not disconnect the authenticated socket
                    # Authorization: conversation must already exist between both users
                    if not await _ws_conversation_exists_async(auth_uid, to_id):
                        print(f"[WS-SEC] TYPING_UNAUTH uid={auth_uid} to={to_id}")
                        continue
                    await ws_manager.send_to_user(to_id, {"type": msg_type, "from_user_id": auth_uid})

            else:
                count = _ws_event_violations.get(auth_uid, 0) + 1
                _ws_event_violations[auth_uid] = count
                logged_type = msg_type[:80]  # already validated ≤ 80 chars
                print(f"[WS-SEC] UNKNOWN_TYPE type={logged_type!r} uid={auth_uid} violation={count}")
                if count >= _WS_MAX_VIOLATIONS:
                    print(f"[WS-SEC] VIOLATION_LIMIT uid={auth_uid}")
                    try:
                        await websocket.close(code=4005)
                    except Exception:
                        pass
                    break

    finally:
        ws_manager.disconnect(auth_uid, websocket)
        _ws_cleanup_typing_log(auth_uid)
        print(f"[WS] DISCONNECTED uid={auth_uid}")


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


@app.get("/company/{company_id}/followers")
def company_followers_list(company_id: str, request: Request, limit: int = 20, offset: int = 0, type: str = "all"):
    """Paginated followers list for a company. Public — no auth required. type: all|emp|co|edu"""
    if type not in _VALID_FOLLOW_TYPES:
        raise HTTPException(400, "نوع غير صالح — القيم المسموحة: all, emp, co, edu")
    resolved_id = _resolve_company_id(company_id)
    if not resolved_id:
        raise HTTPException(404, "الشركة غير موجودة")
    limit  = min(max(limit, 1), 50)
    offset = max(offset, 0)
    viewer_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        if payload:
            viewer_id = payload.get("user_id")
    result = get_company_followers_list(resolved_id, viewer_id, limit, offset, type)
    return {"status": "success", **result}


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


@app.get("/company/{company_id}/ratings")
def company_ratings_detail(company_id: str, request: Request, limit: int = 5):
    """Public read-only ratings detail. Optional JWT for my_rating field."""
    resolved_id = _resolve_company_id(company_id)
    if not resolved_id:
        raise HTTPException(404, "الشركة غير موجودة")
    viewer_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        if payload:
            viewer_id = payload.get("user_id")
    result = get_company_ratings_detail(resolved_id, viewer_id, limit)
    return {"status": "success", **result}


# ══ Phase 3: Company Posts endpoints ══
@app.get("/company/posts/{company_id}")
def company_posts_list(company_id: str, request: Request):
    # Public read. Optional JWT → viewer_appreciated populated per post.
    resolved_id = _resolve_company_id(company_id)
    viewer_uid = None
    auth = request.headers.get("Authorization", "")
    token_str = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if token_str:
        token_data = _jwt_decode(token_str)
        viewer_uid = token_data.get("user_id") if token_data else None
    posts = get_company_posts(resolved_id, viewer_user_id=viewer_uid)
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
    if data.theme_color and data.theme_color not in ALLOWED_POST_COLORS:
        raise HTTPException(400, "لون غير مقبول")
    ce = data.comments_enabled if data.comments_enabled is not None else True
    post = create_company_post(int(user_id), body, data.tags, data.theme_color or None, ce)
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


@app.patch("/company/posts/{post_id}")
def company_post_update(post_id: int, data: CompanyPostUpdateInput, token=Depends(verify_token)):
    """Edit body/tags/theme_color/comments_enabled of own post. Owner-only."""
    user_id = token.get("user_id")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: PATCH /company/posts")
        raise HTTPException(401, "رمز غير صالح")
    owner = get_post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "المنشور غير موجود")
    if int(user_id) != owner:
        print(f"[SECURITY] POST_EDIT_FORBIDDEN: user={user_id} tried edit post {post_id} owned by {owner}")
        raise HTTPException(403, "غير مصرح بتعديل هذا المنشور")
    body = (data.body or "").strip()
    if not body:
        raise HTTPException(400, "المنشور فارغ")
    if data.theme_color and data.theme_color not in ALLOWED_POST_COLORS:
        raise HTTPException(400, "لون غير مقبول")
    ce = data.comments_enabled if data.comments_enabled is not None else True
    post = update_company_post(post_id, body, data.tags, data.theme_color or None, ce)
    return {"status": "success", "post": post}


@app.post("/company/posts/{post_id}/view")
def company_post_record_view(post_id: int, data: PostViewInput, request: Request):
    """Record a post view. Auth is optional — logged-in users are deduplicated by user_id,
    anonymous visitors by visitor_key. Post owner views are silently ignored."""
    # Verify post exists
    owner = get_post_owner(post_id)
    if owner is None:
        raise HTTPException(404, "المنشور غير موجود")

    # Try to extract user from JWT (optional auth — no error if missing/invalid)
    auth = request.headers.get("Authorization", "")
    token_str = auth[7:] if auth.startswith("Bearer ") else ""
    payload = _jwt_decode(token_str) if token_str else {}
    user_id = payload.get("user_id")

    # Don't count the post owner's own views
    if user_id and int(user_id) == owner:
        return {"status": "skipped", "reason": "owner"}

    if user_id:
        recorded = record_company_post_view(post_id, viewer_user_id=int(user_id))
    else:
        vk = (data.visitor_key or "").strip()[:64]
        if not vk:
            return {"status": "skipped", "reason": "no_key"}
        recorded = record_company_post_view(post_id, visitor_key=vk)

    return {"status": "success", "recorded": recorded}


class AppreciationStateInput(BaseModel):
    appreciated: bool


@app.put("/company/posts/{post_id}/appreciation")
def company_post_set_appreciation(post_id: int, body: AppreciationStateInput, token=Depends(verify_token)):
    """Idempotent — sets exact appreciation state. No toggle ambiguity, no unique-constraint errors.
    Body: {appreciated: bool}. Auth required. Owner gets 403."""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول لتقدير المنشور")
    if not _check_appr_rate(int(user_id), post_id):
        raise HTTPException(status_code=429, detail="الرجاء التمهّل قليلاً")
    owner_id = get_post_owner(post_id)
    if not owner_id:
        raise HTTPException(status_code=404, detail="المنشور غير موجود")
    if int(owner_id) == int(user_id):
        raise HTTPException(status_code=403, detail="لا يمكنك تقدير منشورك")
    result = set_company_post_appreciation(post_id, int(user_id), body.appreciated)
    return {"status": "success", **result}


class SaveStateInput(BaseModel):
    saved: bool


@app.put("/company/posts/{post_id}/save")
def company_post_set_save(post_id: int, body: SaveStateInput, token=Depends(verify_token)):
    """Idempotent — sets exact save state for the authenticated user.
    Body: {saved: bool}. Auth required. No owner restriction — anyone can save."""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول لحفظ المنشور")
    if not _check_save_rate(int(user_id), post_id):
        raise HTTPException(status_code=429, detail="الرجاء التمهّل قليلاً")
    owner_id = get_post_owner(post_id)
    if not owner_id:
        raise HTTPException(status_code=404, detail="المنشور غير موجود")
    result = set_company_post_save(post_id, int(user_id), body.saved)
    return {"status": "success", **result}


# ── Post Comments System ──────────────────────────────────────────────────

class CommentInput(BaseModel):
    body: str
    reply_to_comment_id: Optional[int] = None
    mentioned_tw_ids: Optional[List[str]] = None

class CommentUpdateInput(BaseModel):
    body: str


@app.get("/company/posts/{post_id}/comments")
def company_get_post_comments(post_id: int, request: Request):
    """Public with optional JWT — returns active comments + viewer flags if authenticated."""
    auth_header = request.headers.get("Authorization", "")
    viewer_id = None
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        viewer_id = payload.get("user_id")
    comments = get_company_post_comments(post_id, viewer_id)
    return {"status": "success", "comments": comments}


@app.post("/company/posts/{post_id}/comments")
def company_create_post_comment(post_id: int, body: CommentInput, token=Depends(verify_token)):
    """Create a comment. JWT required. Validates body, comments_enabled, rate limit."""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول للتعليق")
    if not _check_cmt_create_rate(int(user_id), post_id):
        raise HTTPException(status_code=429, detail="الرجاء التمهّل قليلاً")
    try:
        comment = create_company_post_comment(post_id, int(user_id), body.body, body.reply_to_comment_id, body.mentioned_tw_ids or [])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "غير موجود" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)  # mentioned_tw_ids mismatch or invalid
    return {"status": "success", "comment": comment}


@app.patch("/company/posts/comments/{comment_id}")
def company_update_post_comment(comment_id: int, body: CommentUpdateInput, token=Depends(verify_token)):
    """Edit a comment body. JWT required. Only comment author may edit."""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول")
    if not _check_cmt_edit_rate(int(user_id), comment_id):
        raise HTTPException(status_code=429, detail="الرجاء التمهّل قليلاً")
    try:
        comment = update_company_post_comment(comment_id, int(user_id), body.body)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "غير موجود" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=422, detail=msg)
    return {"status": "success", "comment": comment}


@app.delete("/company/posts/comments/{comment_id}")
def company_delete_post_comment(comment_id: int, token=Depends(verify_token)):
    """Soft-delete a comment. Allowed for: comment author OR company page owner."""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول")
    try:
        delete_company_post_comment(comment_id, int(user_id))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "success"}


@app.get("/mention/search")
def mention_search(q: str = "", limit: int = 8, token=Depends(verify_token)):
    """
    Search users to @mention in comments.

    Results are sourced by viewer account type:
    - emp / edu / other: profile_follows both directions + companies viewer follows + any user (if q)
    - co (company):      people who follow this company + any user (if q)

    Returns up to `limit` candidates [{tw_id, name, avatar, user_type}].

    Perf:
    - Employee path: single UNION ALL (1 DB roundtrip, unique param names per branch).
    - Company path: single indexed scan on company_follows.company_id.
    - When q is empty: pure FK-indexed scan, no ILIKE, no Priority 4.
    - When q is provided: ILIKE per branch; Priority 4 (any user) fills remaining slots.
    - Errors are logged and returned as {"ok": False} — never swallowed silently.
    """
    viewer_id   = int(token["user_id"])
    viewer_type = token.get("user_type", "emp")
    seen:    set  = set()
    results: list = []

    def _add(rows):
        for r in (rows or []):
            tw_id, name, avatar, utype = r[0], r[1], r[2], r[3]
            if tw_id and tw_id not in seen and len(results) < limit:
                seen.add(tw_id)
                results.append({"tw_id": tw_id, "name": name or "",
                                 "avatar": avatar or None, "user_type": utype or ""})

    try:
        conn = get_conn()

        if viewer_type == "co":
            # Company viewer: return people who follow this company.
            # company_follows.company_id = the company (viewer)
            # company_follows.follower_id = the person who follows
            if q:
                q_like = f"%{q}%"
                _add(conn.run(
                    "SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                    " FROM company_follows cf"
                    " JOIN users u ON u.id = cf.follower_id"
                    " LEFT JOIN profiles p ON p.user_id = u.id"
                    " WHERE cf.company_id = :vid AND u.full_name ILIKE :q LIMIT :lim",
                    vid=viewer_id, q=q_like, lim=limit))
                # Priority 4 — any matching user (fills remaining slots)
                if len(results) < limit:
                    _add(conn.run(
                        "SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                        " FROM users u"
                        " LEFT JOIN profiles p ON p.user_id = u.id"
                        " WHERE u.id != :vid AND u.full_name ILIKE :q LIMIT :lim",
                        vid=viewer_id, q=q_like, lim=limit))
            else:
                # No q: pure FK-indexed scan on company_id (idx_follows_company)
                _add(conn.run(
                    "SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                    " FROM company_follows cf"
                    " JOIN users u ON u.id = cf.follower_id"
                    " LEFT JOIN profiles p ON p.user_id = u.id"
                    " WHERE cf.company_id = :vid LIMIT :lim",
                    vid=viewer_id, lim=limit))

        else:
            # Employee / edu / other viewer:
            # Branch A: profiles I follow (profile_follows.follower_id = me → followed_id)
            # Branch B: profiles who follow me (profile_follows.followed_id = me → follower_id)
            # Branch C: companies I follow (company_follows.follower_id = me → company_id)
            # Merged in a single UNION ALL (1 DB roundtrip).
            # Unique param names per branch (:vid_a/b/c, :lim_a/b/c, :q_a/b/c) guarantee
            # unambiguous pg8000 $N positional mapping across UNION branches.
            if q:
                q_like = f"%{q}%"
                _add(conn.run(
                    "(SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                    " FROM profile_follows pf"
                    " JOIN users u ON u.id = pf.followed_id"
                    " LEFT JOIN profiles p ON p.user_id = u.id"
                    " WHERE pf.follower_id = :vid_a AND u.full_name ILIKE :q_a LIMIT :lim_a)"
                    " UNION ALL"
                    " (SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                    " FROM profile_follows pf"
                    " JOIN users u ON u.id = pf.follower_id"
                    " LEFT JOIN profiles p ON p.user_id = u.id"
                    " WHERE pf.followed_id = :vid_b AND u.id != :vid_b2 AND u.full_name ILIKE :q_b LIMIT :lim_b)"
                    " UNION ALL"
                    " (SELECT u.tw_id, u.full_name, cp.avatar_url, u.user_type"
                    " FROM company_follows cf"
                    " JOIN users u ON u.id = cf.company_id"
                    " LEFT JOIN company_profiles cp ON cp.user_id = u.id"
                    " WHERE cf.follower_id = :vid_c AND u.full_name ILIKE :q_c LIMIT :lim_c)",
                    vid_a=viewer_id, q_a=q_like, lim_a=limit,
                    vid_b=viewer_id, vid_b2=viewer_id, q_b=q_like, lim_b=limit,
                    vid_c=viewer_id, q_c=q_like, lim_c=limit))
                # Priority 4 — any matching user (only when q provided + space left)
                if len(results) < limit:
                    _add(conn.run(
                        "SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                        " FROM users u"
                        " LEFT JOIN profiles p ON p.user_id = u.id"
                        " WHERE u.id != :vid AND u.full_name ILIKE :q LIMIT :lim",
                        vid=viewer_id, q=q_like, lim=limit))
            else:
                # No q: pure FK-indexed scan — no ILIKE, no ORDER BY, no Priority 4
                _add(conn.run(
                    "(SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                    " FROM profile_follows pf"
                    " JOIN users u ON u.id = pf.followed_id"
                    " LEFT JOIN profiles p ON p.user_id = u.id"
                    " WHERE pf.follower_id = :vid_a LIMIT :lim_a)"
                    " UNION ALL"
                    " (SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                    " FROM profile_follows pf"
                    " JOIN users u ON u.id = pf.follower_id"
                    " LEFT JOIN profiles p ON p.user_id = u.id"
                    " WHERE pf.followed_id = :vid_b AND u.id != :vid_b2 LIMIT :lim_b)"
                    " UNION ALL"
                    " (SELECT u.tw_id, u.full_name, cp.avatar_url, u.user_type"
                    " FROM company_follows cf"
                    " JOIN users u ON u.id = cf.company_id"
                    " LEFT JOIN company_profiles cp ON cp.user_id = u.id"
                    " WHERE cf.follower_id = :vid_c LIMIT :lim_c)",
                    vid_a=viewer_id, lim_a=limit,
                    vid_b=viewer_id, vid_b2=viewer_id, lim_b=limit,
                    vid_c=viewer_id, lim_c=limit))

    except Exception as _exc:
        print(f"[mention_search] ERROR viewer={viewer_id} type={viewer_type} q={q!r}: {_exc}")
        return {"ok": False, "candidates": []}

    return {"ok": True, "candidates": results}


# ── Saved Candidates (Phase 3 — company-owner only, JWT required) ──────────

def _require_company_owner(token: dict) -> int:
    """Extract and validate company owner from JWT. Returns company_id (int)."""
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: saved-candidates")
        raise HTTPException(401, "رمز غير صالح")
    if user_type != "co":
        print(f"[SECURITY] SAVED_CANDS_FORBIDDEN: user_type={user_type}")
        raise HTTPException(403, "الشركات فقط يمكنها الوصول للمرشحين المحفوظين")
    return int(user_id)


@app.get("/company/saved-candidates")
def company_saved_candidates_list(
    token=Depends(verify_token),
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    job_id: Optional[int] = None,
    unlinked: bool = False,
    q: Optional[str] = None,
    sort: str = "updated_desc",
    priority: Optional[str] = None,
    min_rating: Optional[int] = None,
    tag: Optional[str] = None,
    save_source_filter: Optional[str] = None,
):
    """
    GET /company/saved-candidates
    Private — company owner only. Returns filtered + paginated saved candidates.
    Auth: JWT Bearer (user_type='co').

    Optional query params (all backward-compatible — omitting all = original behavior):
      status             — pipeline status filter (saved|shortlisted|contacted|interview|hired|rejected)
      job_id             — filter by linked job (must belong to this company)
      unlinked           — true: only candidates with no job_id (mutually exclusive with job_id)
      q                  — search full_name / tw_id / profession / city / country (max 80 chars)
      sort               — updated_desc|updated_asc|created_desc|created_asc|name_asc|status_asc|rating_desc|priority_asc
      limit              — 1–50, default 20
      offset             — default 0
      priority           — low|medium|high (Talent Bank V2)
      min_rating         — 1–5 (Talent Bank V2)
      tag                — exact tag string (Talent Bank V2)
      save_source_filter — manual|applicant|suggestion|legacy_unknown (Talent Bank V2)

    Response: { status, count (filtered total), items, pagination, filters }
    count == pagination.total. Badge uses /count endpoint for unfiltered total.
    """
    company_id = _require_company_owner(token)
    limit  = min(max(limit, 1), 50)
    offset = max(offset, 0)

    if status is not None and status not in VALID_CANDIDATE_STATUSES:
        raise HTTPException(
            400,
            "status غير صالح. القيم المسموحة: " + ", ".join(sorted(VALID_CANDIDATE_STATUSES))
        )

    if sort not in VALID_CANDIDATE_SORTS:
        raise HTTPException(
            400,
            "sort غير صالح. القيم المسموحة: " + ", ".join(sorted(VALID_CANDIDATE_SORTS))
        )

    if job_id is not None and unlinked:
        raise HTTPException(400, "لا يمكن استخدام job_id و unlinked=true معاً")

    if q is not None:
        q = q.strip()
        if len(q) > 80:
            raise HTTPException(400, "q يجب ألا يتجاوز 80 حرفاً")
        if not q:
            q = None

    if tag is not None:
        tag = tag.strip()
        if len(tag) > 50:
            raise HTTPException(400, "tag يجب ألا يتجاوز 50 حرفاً")
        if not tag:
            tag = None

    if priority is not None and priority not in ('low', 'medium', 'high'):
        raise HTTPException(400, "priority غير صالح. القيم المسموحة: low, medium, high")

    if min_rating is not None and (min_rating < 1 or min_rating > 5):
        raise HTTPException(400, "min_rating يجب أن يكون بين 1 و 5")

    _VALID_SAVE_SOURCES = {'manual', 'applicant', 'suggestion', 'legacy_unknown'}
    if save_source_filter is not None and save_source_filter not in _VALID_SAVE_SOURCES:
        raise HTTPException(400, "save_source_filter غير صالح")

    try:
        result = get_company_saved_candidates_filtered(
            company_id=company_id,
            limit=limit,
            offset=offset,
            status=status,
            job_id=job_id,
            unlinked=unlinked,
            q=q,
            sort=sort,
            priority=priority,
            min_rating=min_rating,
            tag=tag,
            save_source_filter=save_source_filter,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"status": "success", **result}


@app.get("/company/saved-candidates/count")
def company_saved_candidates_count(token=Depends(verify_token)):
    """
    GET /company/saved-candidates/count
    Private — company owner only. Returns TOTAL candidate count (unfiltered) for badge.
    Auth: JWT Bearer (user_type='co').
    """
    company_id = _require_company_owner(token)
    count = get_company_saved_candidates_count(company_id)
    return {"status": "success", "count": count}


@app.get("/company/saved-candidates/stats")
def company_saved_candidates_stats(token=Depends(verify_token)):
    """
    GET /company/saved-candidates/stats
    Private — company owner only. Returns pipeline statistics (no candidate data).
    Auth: JWT Bearer (user_type='co').

    Response:
      { status, total, by_status: { saved, shortlisted, contacted, interview, hired, rejected },
        with_job, unlinked }
    All 6 pipeline statuses are always present (zero-filled if none exist).
    """
    company_id = _require_company_owner(token)
    stats = get_company_saved_candidates_stats(company_id)
    return {"status": "success", **stats}


@app.get("/company/saved-candidates/quota")
def company_talent_bank_quota(token=Depends(verify_token)):
    """
    GET /company/saved-candidates/quota
    Returns the current Talent Bank usage and quota for the authenticated company.
    Auth: JWT Bearer (user_type='co').
    Returns: { used, limit, can_save }
    """
    company_id = _require_company_owner(token)
    return get_talent_bank_quota(company_id)


@app.post("/company/saved-candidates/{candidate_id}")
def company_save_candidate(candidate_id: int, job_id: Optional[int] = None,
                           token=Depends(verify_token)):
    """
    POST /company/saved-candidates/{candidate_id}
    Save an employee to the company's Talent Bank (quota-enforced, idempotent).

    Auth: JWT Bearer (user_type='co'). company_id is always from the token — never from the client.
    Optional query param: job_id — must belong to this company AND the candidate must have applied;
    used to set save_source='applicant'. Omit for a general save (save_source='manual').

    Quota: TALENT_BANK_FREE_LIMIT (25) unique saved candidates per company.
    - Already-saved candidates always succeed idempotently regardless of quota.
    - New candidates over the limit return HTTP 409 with a structured top-level body.

    Returns: { status, saved, already_saved, count, used, limit, can_save }
    409 body (top-level, not wrapped): { code, limit, used, can_save }
    """
    company_id = _require_company_owner(token)
    if candidate_id == company_id:
        raise HTTPException(400, "لا يمكن حفظ الشركة نفسها كمرشح")

    # Determine save_source server-side — never trust client input for this field.
    save_source = 'manual'
    if job_id is not None:
        conn = get_conn()
        try:
            job_rows = conn.run(
                "SELECT id FROM jobs WHERE id=:jid AND company_id=:cid",
                jid=job_id, cid=company_id)
            if not job_rows:
                raise HTTPException(400, "الوظيفة غير موجودة أو لا تتبع شركتك")
            app_rows = conn.run(
                "SELECT 1 FROM job_applications WHERE job_id=:jid AND user_id=:uid",
                jid=job_id, uid=candidate_id)
            if not app_rows:
                raise HTTPException(400, "لا يمكن ربط المرشح بوظيفة لم يتقدم عليها")
            save_source = 'applicant'
        finally:
            release_conn(conn)

    try:
        result = save_company_candidate(
            company_id=company_id,
            candidate_id=candidate_id,
            saved_by=company_id,
            save_source=save_source)
    except TalentBankLimitError as e:
        return JSONResponse(status_code=409, content={
            "code":     "talent_bank_limit_reached",
            "limit":    e.limit,
            "used":     e.used,
            "can_save": False,
        })
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


@app.delete("/company/saved-candidates/{candidate_id}")
def company_remove_candidate(candidate_id: int, token=Depends(verify_token)):
    """
    DELETE /company/saved-candidates/{candidate_id}
    Remove a candidate from the saved list.
    Auth: JWT Bearer (user_type='co').
    Returns: { status, saved: false, count }
    """
    company_id = _require_company_owner(token)
    count = remove_company_candidate(company_id=company_id, candidate_id=candidate_id)
    return {"status": "success", "saved": False, "count": count}


@app.patch("/company/saved-candidates/{candidate_id}")
def company_update_saved_candidate(
    candidate_id: int,
    data: UpdateSavedCandidateInput,
    token: dict = Depends(verify_token)
):
    """
    PATCH /company/saved-candidates/{candidate_id}
    Partial update of pipeline status, notes, and/or job_id for a saved candidate.
    Auth: JWT Bearer (user_type='co'). company_id from token only.

    Body (all fields optional — only sent fields are updated):
      { "status": "shortlisted", "notes": "...", "job_id": 12 }

    Valid status values: saved | shortlisted | contacted | interview | hired | rejected
    Returns: { status: "success", item: { ...safe candidate fields... } }
    """
    company_id = _require_company_owner(token)

    # Collect only the fields explicitly sent in the request body
    try:
        sent = data.model_fields_set        # Pydantic v2
    except AttributeError:
        sent = data.__fields_set__          # Pydantic v1

    if not sent:
        raise HTTPException(400, "لا توجد حقول للتحديث")

    updates = {k: getattr(data, k) for k in sent}

    # status must be a valid non-null string if sent
    if 'status' in updates:
        if updates['status'] is None:
            raise HTTPException(400, "قيمة status لا يمكن أن تكون فارغة")
        if updates['status'] not in VALID_CANDIDATE_STATUSES:
            raise HTTPException(
                400,
                "قيمة status غير مسموحة. القيم المسموحة: "
                + ", ".join(sorted(VALID_CANDIDATE_STATUSES))
            )

    # rating: 1–5 or null (clear)
    if 'rating' in updates:
        r_val = updates['rating']
        if r_val is not None and (not isinstance(r_val, int) or r_val < 1 or r_val > 5):
            raise HTTPException(400, "rating يجب أن يكون رقماً بين 1 و 5 أو null")

    # priority: low|medium|high or null (clear)
    if 'priority' in updates:
        p_val = updates['priority']
        if p_val is not None and p_val not in ('low', 'medium', 'high'):
            raise HTTPException(400, "priority يجب أن يكون 'low' أو 'medium' أو 'high' أو null")

    # follow_up_status: none|pending|done or null (clear)
    if 'follow_up_status' in updates:
        fs_val = updates['follow_up_status']
        if fs_val is not None and fs_val not in ('none', 'pending', 'done'):
            raise HTTPException(400, "follow_up_status يجب أن يكون 'none' أو 'pending' أو 'done' أو null")

    try:
        result = update_company_saved_candidate(
            company_id=company_id,
            candidate_id=candidate_id,
            updates=updates
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if result is None:
        raise HTTPException(404, "المرشح غير موجود في قائمة المحفوظين")

    return {"status": "success", "item": result}


@app.patch("/company/saved-candidates/{candidate_id}/jobs/{job_id}")
def company_update_candidate_job_status(
    candidate_id: int,
    job_id: int,
    data: UpdateCandidateJobStatusInput,
    token: dict = Depends(verify_token)
):
    """
    PATCH /company/saved-candidates/{candidate_id}/jobs/{job_id}
    Update the per-job candidate_status in company_candidate_job_refs.

    Auth: JWT Bearer only. company_id is always derived from token — never accepted from client.

    Body: { "candidate_status": "shortlisted" | "contacted" | ... | null }

    Three independent sources of truth:
      - job_applications.status           → applicant's application status (NEVER touched here)
      - company_saved_candidates.status   → general pipeline status (NEVER touched here)
      - company_candidate_job_refs.candidate_status → this endpoint only

    Valid values: saved | shortlisted | contacted | interview | hired | rejected | null (clears)
    Returns: { status: "success", candidate_id, job_id, candidate_status }
    """
    company_id = _require_company_owner(token)

    cs = data.candidate_status
    if cs is not None and cs not in VALID_CANDIDATE_STATUSES:
        raise HTTPException(
            400,
            "قيمة candidate_status غير مسموحة. القيم المسموحة: "
            + ", ".join(sorted(VALID_CANDIDATE_STATUSES))
        )

    try:
        found = update_candidate_job_status(
            company_id=company_id,
            candidate_id=candidate_id,
            job_id=job_id,
            candidate_status=cs,
            actor_id=company_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not found:
        raise HTTPException(404, "الربط بين المرشح والوظيفة غير موجود أو لا تملك صلاحية تعديله")

    return {
        "status":           "success",
        "candidate_id":     candidate_id,
        "job_id":           job_id,
        "candidate_status": cs,
    }


@app.get("/company/candidate-suggestions")
def company_candidate_suggestions(
    limit: int = 20,
    offset: int = 0,
    include_saved: bool = False,
    token: dict = Depends(verify_token)
):
    """
    GET /company/candidate-suggestions
    Scored employee suggestions for this company based on active job postings.
    Auth: JWT Bearer (user_type='co'). company_id derived from token — no query param.
    Returns: { status, count, items, pagination }
    Empty + message if company has no active jobs.
    Phase 5A Backend only — Frontend tab comes in Phase 5B.
    """
    company_id = _require_company_owner(token)
    if limit < 1:  limit = 1
    if limit > 50: limit = 50
    if offset < 0: offset = 0
    return get_company_candidate_suggestions(
        company_id=company_id,
        limit=limit,
        offset=offset,
        include_saved=include_saved
    )


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
        
        # No user notification: admins are not user accounts. The report stays in
        # `reports` (status 'pending') and appears in the admin panel → البلاغات tab
        # (GET /admin/reports + pending badge).
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
def verify_token_endpoint(token=Depends(verify_token)):
    return {"valid": True, "user_id": token["user_id"], "user_type": token["user_type"]}

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
async def upload_logo(data: AdminLogoInput, request: Request):
    """Upload site logo (admin only) — slot: logo_wide | logo_tall.
    Same image validation as /upload/image (PR-7a): JPEG/PNG/WebP only, no SVG."""
    check_admin(request)
    slot = data.filename or "logo_wide"
    if slot not in _LOGO_SLOTS:
        raise HTTPException(400, "نوع الشعار غير معروف")
    mime, ext, file_bytes = _validate_image_data_url(data.data_url)
    logo_url = await _store_image("site", f"{slot}_{secrets.token_hex(6)}{ext}",
                                  file_bytes, mime, data.data_url, "[Logo]")
    # Always cache in memory
    _html_cache[slot] = logo_url
    try:
        ensure_site_settings_table()
        set_site_setting(slot, logo_url)
    except Exception as db_err:
        print(f"[Logo] DB save failed: {db_err} - cached in memory only")
    return {"status": "success", "url": logo_url}

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
_PASSWORD_MIN_LEN = 6

def _password_policy_error(password) -> Optional[str]:
    """The one password rule — POST /auth/register + PUT /auth/password. None = acceptable."""
    if not isinstance(password, str) or len(password) < _PASSWORD_MIN_LEN:
        return f"كلمة المرور يجب أن تكون {_PASSWORD_MIN_LEN} أحرف على الأقل"
    return None

class AccountFieldError(Exception):
    """Field-specific 422 for account security forms (password change / account delete)."""
    def __init__(self, field: str, code: str, message: str):
        self.field, self.code, self.message = field, code, message

@app.exception_handler(AccountFieldError)
async def account_field_error_handler(request, exc):
    # Same shape as ExternalUrlError / PUT /profile field errors (errors[] + detail.message)
    return JSONResponse(status_code=422, content={
        "ok": False, "error": exc.message,
        "errors": [{"field": exc.field, "code": exc.code, "message": exc.message}],
        "detail": {"status": "error", "message": exc.message, "field": exc.field},
    })

class PasswordChangeInput(BaseModel):
    current_password: str = ""
    new_password: str = ""

class AccountDeleteInput(BaseModel):
    password: str = ""

@app.post("/auth/register")
def register(data: RegisterInput, request: Request):
    if data.user_type not in ("emp", "co", "edu"):
        raise HTTPException(400, detail="نوع الحساب غير صحيح")
    if not data.email.strip():
        raise HTTPException(400, detail="البريد الإلكتروني مطلوب")
    _pw_err = _password_policy_error(data.password)
    if _pw_err:
        raise HTTPException(400, detail=_pw_err)

    # G-contract: emp uses structured name; co/edu use full_name.
    # _norm_name: trim + collapse internal whitespace (e.g. "محمد   أحمد" → "محمد أحمد").
    first_name_val = middle_name_val = last_name_val = None
    if data.user_type == "emp":
        first  = _norm_name(data.first_name)
        last   = _norm_name(data.last_name)
        middle = _norm_name(data.middle_name)
        if not first or not last:
            raise HTTPException(400, detail="الاسم الأول واسم العائلة مطلوبان")
        full_name      = " ".join(p for p in [first, middle, last] if p)
        first_name_val = first
        middle_name_val = middle or None
        last_name_val  = last
    else:
        full_name = (data.full_name or "").strip()
        if not full_name:
            raise HTTPException(400, detail="الاسم الكامل مطلوب")

    try:
        client_ip = get_client_ip(request)
        country_code = get_country_from_ip(client_ip)
        user = create_user(
            full_name, data.email, data.password, data.user_type, country_code,
            first_name=first_name_val, middle_name=middle_name_val, last_name=last_name_val
        )
        token = _jwt_encode({"user_id": user.get("id"), "user_type": user.get("user_type"), "tw_id": user.get("tw_id","")})
        return {"status": "success", "user": user, "token": token}
    except ValueError as e:
        raise HTTPException(409, detail=str(e))
    except Exception as e:
        print(f"Register error: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")

@app.post("/auth/login")
def login(data: LoginInput, request: Request):
    if os.environ.get("LOG_CLIENT_IP") == "1":
        # Measurement only (ARCHITECTURE.md → Client IP Resolution) — headers + chosen IP, never body/email/password
        print(f"[client-ip] /auth/login xff={request.headers.get('X-Forwarded-For')!r} "
              f"x_real_ip={request.headers.get('X-Real-IP')!r} "
              f"peer={(request.client.host if request.client else None)!r} chosen={get_client_ip(request)!r}")
    if not data.email.strip() or not data.password:
        raise HTTPException(400, detail="البريد وكلمة المرور مطلوبان")
    if _login_email_locked(data.email):
        return JSONResponse(status_code=429, content={
            "error": _LOGIN_LOCKED_MSG,
            "detail": {"code": "login_email_locked", "message": _LOGIN_LOCKED_MSG}})
    user = authenticate_user(data.email, data.password)
    if not user:
        _login_email_fail(data.email)
        raise HTTPException(401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")
    _login_email_reset(data.email)
    token = _jwt_encode({"user_id": user.get("id"), "user_type": user.get("user_type"), "tw_id": user.get("tw_id","")})
    return {"status": "success", "user": user, "token": token}

@app.put("/auth/password")
def change_password(data: PasswordChangeInput, token=Depends(verify_token)):
    """Signed-in password change — JWT owner only, current password checked with bcrypt,
    new password through _password_policy_error (same rule as register). Rate limited."""
    uid = int(token["user_id"])
    if not data.current_password:
        raise AccountFieldError("current_password", "required", "أدخل كلمة المرور الحالية")
    pw_err = _password_policy_error(data.new_password)
    if pw_err:
        raise AccountFieldError("new_password", "weak_password", pw_err)
    if data.new_password == data.current_password:
        raise AccountFieldError("new_password", "same_password",
                                "كلمة المرور الجديدة يجب أن تختلف عن الحالية")
    try:
        ok = check_user_password(uid, data.current_password)
        if ok is None:
            raise HTTPException(404, detail="المستخدم غير موجود")
        if not ok:
            raise AccountFieldError("current_password", "wrong_password",
                                    "كلمة المرور الحالية غير صحيحة")
        changed_epoch = set_user_password(uid, data.new_password)
        _password_changed_cache_set(uid, changed_epoch)
        # Fresh token for THIS device — its iat is ≥ password_changed_at, so it survives
        # the invalidation; every older JWT of this user is rejected from now on.
        new_token = _jwt_encode({"user_id": uid, "user_type": token.get("user_type"),
                                 "tw_id": token.get("tw_id") or ""})
    except (HTTPException, AccountFieldError):
        raise
    except Exception as e:
        print(f"[PUT /auth/password] ERROR user={uid}: {e}")
        raise HTTPException(500, detail="تعذّر تغيير كلمة المرور، حاول لاحقاً")
    print(f"[PUT /auth/password] changed user={uid} — older sessions invalidated")
    return {"ok": True, "status": "success", "token": new_token}

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
def get_user(user_id: int, token=Depends(verify_token)):
    if str(token.get("user_id")) != str(user_id):
        raise HTTPException(403, detail="غير مصرح")
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
            _actor_utype = payload.get("user_type", "emp") if payload else "emp"
            if _actor_utype == "co":
                _interest_active = is_candidate_saved(int(token_uid), profile_id)
            else:
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
def full_profile(user_id: str, token=Depends(verify_token)):
    try:
        uid = int(user_id)
    except ValueError:
        uid = get_user_id_by_tw_id(user_id)
        if uid is None:
            raise HTTPException(404, detail="الملف الشخصي غير موجود")
    if str(token.get("user_id")) != str(uid):
        raise HTTPException(403, detail="غير مصرح")
    profile = get_full_profile(uid)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    return {"status": "success", "profile": project_owner_profile(profile)}


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

_skill_catalog_cache: Optional[list] = None
_skill_catalog_cache_ts: float = 0.0
_SKILL_CATALOG_TTL = 3600  # 1 hour

@app.get("/skills/catalog")
def get_skills_catalog():
    import time
    global _skill_catalog_cache, _skill_catalog_cache_ts
    now = time.time()
    if _skill_catalog_cache is not None and (now - _skill_catalog_cache_ts) < _SKILL_CATALOG_TTL:
        return _skill_catalog_cache
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id, slug, name_en, name_ar, keywords, icon, category_group, sort_order "
            "FROM skill_catalog WHERE is_active = TRUE "
            "ORDER BY category_group, sort_order, name_ar"
        )
        cols = ["id","slug","name_en","name_ar","keywords","icon","category_group","sort_order"]
        result = [dict(zip(cols, r)) for r in rows]
        _skill_catalog_cache = result
        _skill_catalog_cache_ts = now
        return result
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
    # exclude_unset=True preserves explicit null (field=null = CLEAR) vs omitted (no change)
    payload = data.dict(exclude_unset=True)
    user_type = token.get('user_type')
    if "website" in payload:   # §54 rule 4b — empty / null = clear
        payload["website"] = _validate_external_url(payload["website"], "website", "الموقع الإلكتروني")
    # PR-7a: image URLs must come from /upload/image for this user (company logo = avatar_url of a co)
    _img_kinds = {"avatar_url": "company-logo" if user_type == "co" else "employee-avatar",
                  "cover_url": "employee-cover"}
    _img_pending = {f: k for f, k in _img_kinds.items() if payload.get(f)}
    if _img_pending:
        _cur = _current_image_urls(
            "SELECT avatar_url, cover_url FROM profiles WHERE user_id = :uid", user_id)
        for _f, _k in _img_pending.items():
            _validate_stored_image_url(payload[_f], _k, user_id, _cur.get(_f))
    try:
        # Validate profession_id only when it is explicitly set to a non-null value
        if payload.get("profession_id") is not None:
            conn = get_conn()
            try:
                rows = conn.run("SELECT id FROM profession_categories WHERE id = :pid AND is_active = TRUE", pid=payload["profession_id"])
                if not rows:
                    raise ProfileValidationError(field='profession_id', code='profession_invalid',
                        message='التخصص غير موجود أو غير فعال')
            finally:
                release_conn(conn)
        profile = update_profile(user_id, payload, user_type=user_type)
        if not profile:
            raise HTTPException(500, "Profile update failed")
        updated_keys = list(payload.keys())
        print(f"[PUT /profile] ✅ user={user_id} fields={updated_keys} — {_time.time()-_t0:.3f}s total")
        return {"status": "success", "profile": profile, "updated_fields": updated_keys}
    except ProfileValidationError as e:
        # Field-specific: errors[] is the official shape; no top-level error{} (API-MUT)
        return JSONResponse(status_code=422, content={
            "errors": [{"field": e.field, "code": e.code, "message": e.message}],
            "detail": {"ok": False, "field": e.field, "code": e.code, "error": e.message}
        })
    except ContentValidationError as e:
        if e.field:
            # Field-specific content violation: errors[] only
            return JSONResponse(status_code=422, content={
                "errors": [{"field": e.field, "code": "content_violation", "message": e.message}],
                "detail": {"status": "error", "message": e.message, "field": e.field}
            })
        else:
            # General content violation: error{} only
            return JSONResponse(status_code=422, content={
                "error": {"code": "content_violation", "message": e.message},
                "detail": {"status": "error", "message": e.message}
            })
    except ValueError as e:
        # no_profile_row or other internal data errors — not a client validation error
        print(f"[PUT /profile] ValueError user={user_id}: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")
    except Exception as e:
        print(f"[PUT /profile] ERROR user={user_id}: {e}")
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
    data.certificate_url = _validate_external_url(data.certificate_url, "certificate_url", "رابط الشهادة")
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
            rows = conn.run("SELECT user_id FROM user_skills WHERE id = :id", id=skill_id)
            if not rows:
                raise HTTPException(404, "Skill not found")
            if str(rows[0][0]) != str(uid):
                raise HTTPException(403, "Forbidden")
            conn.run("DELETE FROM user_skills WHERE id = :id", id=skill_id)
            return {"success": True}
        finally:
            release_conn(conn)
    except HTTPException:
        raise
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
            rows = conn.run("SELECT user_id FROM user_langs WHERE id = :id", id=lang_id)
            if not rows:
                raise HTTPException(404, "Language not found")
            if str(rows[0][0]) != str(uid):
                raise HTTPException(403, "Forbidden")
            conn.run("DELETE FROM user_langs WHERE id = :id", id=lang_id)
            return {"success": True}
        finally:
            release_conn(conn)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/links/{user_id}")
def add_user_link(user_id: int, data: LinkInput, token=Depends(verify_token)):
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    data.url = _validate_external_url(data.url, "url", "الرابط", required=True)
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
            rows = conn.run("SELECT user_id FROM user_links WHERE id = :id", id=link_id)
            if not rows:
                raise HTTPException(404, "Link not found")
            if str(rows[0][0]) != str(uid):
                raise HTTPException(403, "Forbidden")
            conn.run("DELETE FROM user_links WHERE id = :id", id=link_id)
            return {"success": True}
        finally:
            release_conn(conn)
    except HTTPException:
        raise
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



@app.get("/notifications/{user_id}/unread-count")
def notifications_unread_count(user_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    try:
        count = get_unread_notifications(user_id)
        return {"ok": True, "data": {"count": count}}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/notifications/{user_id}")
def user_notifications(user_id: int, token=Depends(verify_token),
                       page: int = 1, per_page: int = 20):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    per_page = max(1, min(per_page, 100))
    page = max(1, page)
    offset = (page - 1) * per_page
    try:
        notifs = get_notifications(user_id, limit=per_page, offset=offset)
        unread = get_unread_notifications(user_id)
        return {"status": "success", "notifications": notifs, "unread": unread,
                "page": page, "per_page": per_page}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/notifications/{user_id}/read")
def read_notifications(user_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    try:
        mark_notifications_read(user_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.put("/notifications/{user_id}/read/{notif_id}")
def read_single_notification(user_id: int, notif_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    try:
        mark_notification_read(user_id, notif_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(500, str(e))

# ══ Storage Upload ══
# PR-7a — Upload security (SYSTEMS_INDEX §29a · docs/rules/upload.md).
# kind → bucket is a fixed server-side map; the client never chooses a bucket
# or a file name. Stored name: {user_id}_{kind}_{random}.{ext}.
_UPLOAD_KINDS = {
    "employee-avatar": "avatars",
    "employee-cover":  "avatars",
    "company-logo":    "avatars",
    "company-cover":   "avatars",
    "kyc-id-front":    "kyc-docs",
    "kyc-selfie":      "kyc-docs",
}
# Private buckets: no public URL exists — the server returns / stores the object
# path "{bucket}/{name}" only (admin viewing via signed URL: GET /admin/kyc/{id}/docs — PR-7c).
_PRIVATE_BUCKETS = frozenset({"kyc-docs"})
_LOGO_SLOTS = ("logo_wide", "logo_tall")
_UPLOAD_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_UPLOAD_MAX_BYTES = 5 * 1024 * 1024        # decoded image
_UPLOAD_MAX_DATA_URL = 7 * 1024 * 1024     # data URL text, checked before decode
_DATA_URL_RE = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,")


def _image_magic_mime(b: bytes):
    """Real content type from magic bytes — None when not JPEG/PNG/WebP."""
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_image_data_url(data_url: str):
    """Validate a base64 image data URL → (mime, ext, bytes). Raises 400/413.
    Only JPEG/PNG/WebP; declared mime must match the magic bytes (no SVG/HTML)."""
    if not isinstance(data_url, str) or not data_url:
        raise HTTPException(400, "صورة غير صالحة")
    if len(data_url) > _UPLOAD_MAX_DATA_URL:
        raise HTTPException(413, "الصورة كبيرة جداً - الحد الأقصى 5MB")
    m = _DATA_URL_RE.match(data_url)
    if not m:
        raise HTTPException(400, "نوع الصورة غير مدعوم — يُقبل فقط JPEG أو PNG أو WebP")
    mime = m.group(1)
    try:
        file_bytes = base64.b64decode(data_url[m.end():], validate=True)
    except Exception:
        raise HTTPException(400, "صورة غير صالحة")
    if not file_bytes:
        raise HTTPException(400, "صورة غير صالحة")
    if len(file_bytes) > _UPLOAD_MAX_BYTES:
        raise HTTPException(413, "الصورة كبيرة جداً - الحد الأقصى 5MB")
    if _image_magic_mime(file_bytes) != mime:
        raise HTTPException(400, "محتوى الصورة لا يطابق نوعها")
    return mime, _UPLOAD_EXT[mime], file_bytes


_STORED_IMAGE_TAIL_RE = re.compile(r"[0-9a-f]{12}\.(?:jpg|png|webp)")


# ── Supabase Storage settings (§29a) — the ONLY readers of SUPABASE_URL /
# SUPABASE_SERVICE_KEY and the ONLY builder of Storage auth headers.
# Values pasted into Railway may carry invisible characters (bidi marks, BOM,
# zero-width), surrounding quotes or whitespace → cleaned once here.
# URL: https://<project>.supabase.co only (custom domains not allowed —
# documented decision). Key: sb_secret_… (new, apikey header only) or a legacy
# service_role JWT (apikey + Bearer). anon / publishable / anything else = not
# configured. Values are never logged — reasons only.
_ENV_QUOTES = "\"'`\u201c\u201d\u2018\u2019"


def _clean_supabase_env(name: str) -> str:
    """Env value without Unicode Cf chars (bidi U+200E/F, U+202A–E, U+2066–9,
    BOM U+FEFF, zero-width), without any whitespace, without surrounding quotes."""
    import unicodedata
    raw = os.environ.get(name) or ""
    s = "".join(ch for ch in raw if unicodedata.category(ch) != "Cf" and not ch.isspace())
    while len(s) >= 2 and s[0] in _ENV_QUOTES and s[-1] in _ENV_QUOTES:
        s = s[1:-1]
    return s


def _supabase_url_status():
    """→ (base, None) when valid, else ("", reason). base has no trailing "/"."""
    from urllib.parse import urlsplit
    s = _clean_supabase_env("SUPABASE_URL").rstrip("/")
    if not s:
        return "", "SUPABASE_URL is not set"
    if not s.lower().startswith("https://"):
        return "", "SUPABASE_URL must start with https://"
    try:
        u = urlsplit(s)
        host, port = (u.hostname or ""), u.port
    except ValueError:
        return "", "SUPABASE_URL is not a valid URL"
    if (u.path or u.query or u.fragment or u.username or u.password or port is not None
            or not re.fullmatch(r"[a-z0-9-]+\.supabase\.co", host)):
        return "", "SUPABASE_URL must be https://<project>.supabase.co"
    return f"https://{host}", None


def _supabase_base_url() -> str:
    """Cleaned SUPABASE_URL ("" when missing/invalid). The only reader of
    SUPABASE_URL for storage: _store_image builds the URL it returns and
    _validate_stored_image_url checks it against the same base — a raw
    "https://x.supabase.co/" would make them disagree ("//storage") and every
    saved image URL would be rejected with 400."""
    return _supabase_url_status()[0]


def _supabase_key_status():
    """→ (key, "secret" | "legacy", None) when it is a service key, else
    ("", None, reason). Legacy JWT: payload decoded only (no signature check)."""
    key = _clean_supabase_env("SUPABASE_SERVICE_KEY")
    if not key:
        return "", None, "SUPABASE_SERVICE_KEY is not set"
    if key.startswith("sb_secret_") and len(key) > len("sb_secret_"):
        return key, "secret", None
    if key.startswith("sb_publishable_"):
        return "", None, "SUPABASE_SERVICE_KEY is a publishable key, not a secret key"
    parts = key.split(".")
    if key.startswith("eyJ") and len(parts) == 3 and all(parts):
        try:
            seg = parts[1] + "=" * (-len(parts[1]) % 4)
            role = (json.loads(_b64.urlsafe_b64decode(seg)) or {}).get("role")
        except Exception:
            role = None
        if role == "service_role":
            return key, "legacy", None
        if role == "anon":
            return "", None, "SUPABASE_SERVICE_KEY is an anon key, not service_role"
    return "", None, "SUPABASE_SERVICE_KEY is not a service key"


def _supabase_service_key() -> str:
    """Cleaned service key ("" when missing or not a service key)."""
    return _supabase_key_status()[0]


def _supabase_auth_headers() -> dict:
    """The only builder of Supabase Storage auth headers ({} when not configured).
    sb_secret_… → apikey only (not a JWT — never Bearer); legacy service_role
    JWT → apikey + Bearer."""
    key, kind, _ = _supabase_key_status()
    if kind == "secret":
        return {"apikey": key}
    if kind == "legacy":
        return {"apikey": key, "Authorization": "Bearer " + key}
    return {}


def _supabase_storage_status_lines() -> list:
    """Startup log lines — never the key or the URL, reasons only."""
    _, url_reason = _supabase_url_status()
    _, kind, key_reason = _supabase_key_status()
    reason = url_reason or key_reason
    if reason:
        return [f"⚠️ Supabase storage: NOT CONFIGURED — {reason}"]
    lines = [f"✅ Supabase storage: OK (key type: {'secret' if kind == 'secret' else 'legacy JWT'})"]
    if kind == "legacy":
        lines.append("⚠️ Supabase storage: legacy key — Supabase deprecates these by end of 2026, "
                     "switch to sb_secret_…")
    return lines


def _validate_stored_image_url(url, kind, uid: int, current=None):
    """PR-7a — gate for every endpoint that SAVES an image URL (avatar / cover /
    logo / KYC). Raises 400 unless the value is:
      • None or ""  (clear — existing behaviour), or
      • exactly the currently stored value (legacy values keep saving), or
      • {SUPABASE_URL}/storage/v1/object/public/{bucket of kind}/{uid}_{kind}_{12 hex}.{jpg|png|webp}
        — i.e. a name /upload/image generated for this user (no ../, no query);
        for a private bucket (kyc-docs) the object path {bucket}/{uid}_{kind}_{12 hex}.{ext}
        instead — never a public URL, or
      • a valid image data URL only when TW_DEV_UPLOAD=1.
    `kind` is one key of _UPLOAD_KINDS."""
    if url is None or url == "":
        return url
    if not isinstance(url, str):
        raise HTTPException(400, "رابط الصورة غير صالح")
    if current is not None and url == current:
        return url
    if url.startswith("data:"):
        if os.environ.get("TW_DEV_UPLOAD") == "1":
            _validate_image_data_url(url)
            return url
        raise HTTPException(400, "رابط الصورة غير صالح")
    base = _supabase_base_url()
    bucket = _UPLOAD_KINDS.get(kind)
    if bucket in _PRIVATE_BUCKETS:
        prefix = f"{bucket}/{int(uid)}_{kind}_"
        if url.startswith(prefix) and _STORED_IMAGE_TAIL_RE.fullmatch(url[len(prefix):]):
            return url
    elif base and bucket:
        prefix = f"{base}/storage/v1/object/public/{bucket}/{int(uid)}_{kind}_"
        if url.startswith(prefix) and _STORED_IMAGE_TAIL_RE.fullmatch(url[len(prefix):]):
            return url
    print(f"[ImageURL] rejected kind={kind} uid={uid} base_set={bool(base)} url={url[:160]!r}")
    raise HTTPException(400, "رابط الصورة غير صالح")


def _current_image_urls(sql: str, uid: int) -> dict:
    """Currently stored image URL columns for one row (constant SQL from callers)."""
    conn = get_conn()
    try:
        rows = conn.run(sql, uid=uid)
        if not rows:
            return {}
        cols = [c["name"] for c in conn.columns]
        return dict(zip(cols, rows[0]))
    finally:
        release_conn(conn)


async def _store_image(bucket: str, name: str, file_bytes: bytes, mime: str,
                       data_url: str, log_tag: str) -> str:
    """Upload to Supabase Storage → public URL, or "{bucket}/{name}" for a private
    bucket (_PRIVATE_BUCKETS). Never falls back to a data URL
    in production: missing config → 503, storage failure → 502 (details logged).
    Dev only: TW_DEV_UPLOAD=1 + missing Supabase keys → returns the data URL."""
    import httpx
    supabase_url = _supabase_base_url()
    auth_headers = _supabase_auth_headers()
    if not supabase_url or not auth_headers:
        if os.environ.get("TW_DEV_UPLOAD") == "1":
            print(f"{log_tag} TW_DEV_UPLOAD=1 — storage not configured, returning data URL (dev only)")
            return data_url
        print(f"{log_tag} storage not configured (SUPABASE_URL / SUPABASE_SERVICE_KEY missing or invalid)")
        raise HTTPException(503, "خدمة رفع الصور غير متاحة حالياً")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{supabase_url}/storage/v1/object/{bucket}/{name}",
                content=file_bytes,
                headers={**auth_headers, "Content-Type": mime},
            )
    except Exception as e:
        print(f"{log_tag} storage error bucket={bucket} name={name}: {e!r}")
        raise HTTPException(502, "تعذّر رفع الصورة، حاول مرة أخرى")
    if r.status_code not in (200, 201):
        print(f"{log_tag} storage rejected bucket={bucket} name={name} status={r.status_code} body={r.text[:300]!r}")
        raise HTTPException(502, "تعذّر رفع الصورة، حاول مرة أخرى")
    print(f"{log_tag} stored bucket={bucket} name={name} bytes={len(file_bytes)}")
    if bucket in _PRIVATE_BUCKETS:
        return f"{bucket}/{name}"
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{name}"


@app.post("/upload/image")
async def upload_image(data: ImageUploadInput, token=Depends(verify_token)):
    """Upload an image for the JWT user → {status, url} (public bucket) or
    {status, path} (private bucket — kyc-docs). kind decides the bucket."""
    try:
        uid = int(token.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(401, "Token invalid or expired")
    bucket = _UPLOAD_KINDS.get(data.kind or "")
    if not bucket:
        raise HTTPException(400, "نوع الرفع غير معروف")
    mime, ext, file_bytes = _validate_image_data_url(data.data_url)
    name = f"{uid}_{data.kind}_{secrets.token_hex(6)}{ext}"
    url = await _store_image(bucket, name, file_bytes, mime, data.data_url, "[Upload]")
    key = "path" if bucket in _PRIVATE_BUCKETS else "url"
    if url == data.data_url:
        return {"status": "success", key: url, "dev_mode": True}
    return {"status": "success", key: url}

# ══ KYC Endpoints ══

_KYC_ERR_MSG = "تعذّر إتمام طلب التحقق حالياً، حاول مرة أخرى لاحقاً"
_OTP_UNAVAILABLE = {"detail": {"code": "otp_delivery_unavailable", "message": "خدمة إرسال رمز التحقق غير متاحة حالياً"}}


@app.post("/kyc/start")
def kyc_start(token=Depends(verify_token)):
    try:
        uid = int(token.get("user_id"))
        result = start_kyc(uid)
        # Tier 3 allowlist — start_kyc() row holds OTP hash/target columns (Tier 4)
        return {"status": "success", "kyc": project_owner_kyc_status(result)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KYC] start error uid={token.get('user_id')}: {type(e).__name__}: {e}")
        raise HTTPException(500, _KYC_ERR_MSG)

@app.get("/kyc/status/{user_id}")
def kyc_status(user_id: int, token=Depends(verify_token)):
    if str(token.get("user_id")) != str(user_id):
        raise HTTPException(403, detail="غير مصرح")
    try:
        result = get_kyc_status(user_id)
        return {"status": "success", "kyc": project_owner_kyc_status(result)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KYC] status error uid={user_id}: {type(e).__name__}")
        raise HTTPException(500, _KYC_ERR_MSG)

@app.post("/kyc/email/send")
def kyc_send_email(data: KYCEmailInput, token=Depends(verify_token)):
    # Fail Closed: no OTP generated or stored until a real provider is available.
    if not is_email_otp_delivery_available():
        return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
    try:
        uid = int(token.get("user_id"))
        start_kyc(uid)
        code = send_email_code(uid, data.email)
        _dev_otp_log("KYC Email", uid)
        return {"status": "success", "message": "تم إرسال الرمز على بريدك الإلكتروني"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KYC] email send error uid={token.get('user_id')}: {type(e).__name__}")
        raise HTTPException(500, _KYC_ERR_MSG)

@app.post("/kyc/email/verify")
def kyc_verify_email(data: KYCCodeInput, token=Depends(verify_token)):
    # Fail Closed: no code can have been delivered → nothing can be verified.
    if not is_email_otp_delivery_available():
        return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
    try:
        uid = int(token.get("user_id"))
        ok = verify_email_code(uid, data.code)
        if not ok:
            raise HTTPException(400, "الرمز غير صحيح أو منتهي الصلاحية")
        return {"status": "success", "message": "تم تأكيد البريد الإلكتروني ✅"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KYC] email verify error uid={token.get('user_id')}: {type(e).__name__}")
        raise HTTPException(500, _KYC_ERR_MSG)

@app.post("/kyc/phone/send")
def kyc_send_phone(data: KYCPhoneInput, token=Depends(verify_token)):
    # Fail Closed: no OTP generated or stored until a real provider is available.
    if not is_phone_otp_delivery_available():
        return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
    try:
        uid = int(token.get("user_id"))
        code = send_phone_code(uid, data.phone)
        _dev_otp_log("KYC Phone", uid)
        return {"status": "success", "message": "تم إرسال الرمز على هاتفك"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KYC] phone send error uid={token.get('user_id')}: {type(e).__name__}")
        raise HTTPException(500, _KYC_ERR_MSG)

@app.post("/kyc/phone/verify")
def kyc_verify_phone(data: KYCCodeInput, token=Depends(verify_token)):
    # Fail Closed: no code can have been delivered → nothing can be verified.
    if not is_phone_otp_delivery_available():
        return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
    try:
        uid = int(token.get("user_id"))
        ok = verify_phone_code(uid, data.code)
        if not ok:
            raise HTTPException(400, "الرمز غير صحيح أو منتهي الصلاحية")
        return {"status": "success", "message": "تم تأكيد رقم الهاتف ✅"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KYC] phone verify error uid={token.get('user_id')}: {type(e).__name__}")
        raise HTTPException(500, _KYC_ERR_MSG)

@app.post("/kyc/docs")
def kyc_upload_docs(data: KYCDocsInput, token=Depends(verify_token)):
    try:
        uid = int(token.get("user_id"))
        if data.id_front_url or data.selfie_url:
            _cur = _current_image_urls(
                "SELECT id_front_url, selfie_url FROM kyc_submissions WHERE user_id = :uid", uid)
            _validate_stored_image_url(data.id_front_url, "kyc-id-front", uid, _cur.get("id_front_url"))
            _validate_stored_image_url(data.selfie_url, "kyc-selfie", uid, _cur.get("selfie_url"))
        result = upload_kyc_docs(uid, data.id_front_url, data.selfie_url)
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/admin/kyc")
def admin_get_kyc(request: Request):
    check_admin(request)
    try:
        # PR-7c: allowlisted fields only (auth._ADMIN_KYC_LIST_COLUMNS) — no OTP
        # codes, no document paths (those → GET /admin/kyc/{submission_id}/docs).
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

# ══ PR-7c — Admin KYC document viewing (signed URLs) ══
# kyc-docs is private (_PRIVATE_BUCKETS): kyc_submissions stores the object path
# only. The admin gets a short-lived Supabase signed URL per document — never a
# public URL, never logged, never cached (Cache-Control: no-store).
_KYC_DOC_FIELDS = (("id_front", "id_front_url", "kyc-id-front"),
                   ("selfie", "selfie_url", "kyc-selfie"))
_KYC_SIGN_EXPIRES = 300


def _kyc_doc_path_reason(value, uid: int, kind: str):
    """→ (object name, None) when value is exactly kyc-docs/{uid}_{kind}_{12hex}.{ext}
    for this submission's user, else (None, reason)."""
    if not value:
        return None, "missing"
    if not isinstance(value, str):
        return None, "invalid_path"
    if value.startswith("data:"):
        return None, "legacy_data_url"
    if value.startswith(("http://", "https://")):
        return None, "legacy_url"
    prefix = f"kyc-docs/{int(uid)}_{kind}_"
    if value.startswith(prefix) and _STORED_IMAGE_TAIL_RE.fullmatch(value[len(prefix):]):
        return value[len("kyc-docs/"):], None
    return None, "invalid_path"


async def _sign_kyc_doc(name: str):
    """Supabase signed URL for kyc-docs/{name} → (url, None) or (None, reason).
    Base via _supabase_base_url() (same as _store_image). Logs never contain
    the signed URL / token."""
    import httpx
    base, auth_headers = _supabase_base_url(), _supabase_auth_headers()
    if not base or not auth_headers:
        return None, "storage_unavailable"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{base}/storage/v1/object/sign/kyc-docs/{name}",
                json={"expiresIn": _KYC_SIGN_EXPIRES},
                headers=auth_headers,
            )
    except Exception as e:
        print(f"[KYC docs] sign error name={name}: {type(e).__name__}")
        return None, "sign_failed"
    if r.status_code != 200:
        print(f"[KYC docs] sign rejected name={name} status={r.status_code}")
        return None, "sign_failed"
    try:
        signed = (r.json() or {}).get("signedURL") or ""
    except Exception:
        signed = ""
    url = f"{base}/storage/v1{signed}" if signed.startswith("/") else ""
    if not url.startswith(f"{base}/storage/v1/object/sign/kyc-docs/{name}?"):
        print(f"[KYC docs] sign response unexpected shape name={name}")
        return None, "sign_failed"
    return url, None


@app.get("/admin/kyc/{submission_id}/docs")
async def admin_kyc_docs(submission_id: int, request: Request):
    """Admin only — short-lived signed URLs for one KYC submission's documents.
    Only paths matching kyc-docs/{user_id}_{kind}_{12hex}.{ext} of the same
    submission's user are signed; anything else → url null + reason."""
    check_admin(request)
    row = _current_image_urls(
        "SELECT user_id, id_front_url, selfie_url FROM kyc_submissions WHERE id = :uid",
        submission_id)
    if not row:
        raise HTTPException(404, "الطلب غير موجود")
    uid = int(row["user_id"])
    base = _supabase_base_url()
    docs = {}
    for label, col, kind in _KYC_DOC_FIELDS:
        name, reason = _kyc_doc_path_reason(row.get(col), uid, kind)
        url = None
        if name:
            url, reason = await _sign_kyc_doc(name)
        docs[label] = {"url": url, "reason": reason}
    print(f"[KYC docs] admin viewed submission={submission_id} user={uid}")
    return JSONResponse(
        {"status": "success", "submission_id": submission_id, "user_id": uid,
         "storage_base": base, "expires_in": _KYC_SIGN_EXPIRES, "docs": docs},
        headers={"Cache-Control": "no-store"})


# ══ PR-7c — Migrate legacy data: images to Storage (admin maintenance) ══
# Each target: (report key, SELECT returning (row_key, value, user_type|None),
# UPDATE with :new / :old / :k RETURNING 1, kind resolver).
# The UPDATE is conditional on the column still holding the old value, so a
# newer change made meanwhile is never overwritten. Constant SQL only.
def _mig_avatar_kind(user_type):
    return "company-logo" if user_type == "co" else "employee-avatar"


_DATA_IMAGE_TARGETS = (
    ("profiles.avatar_url",
     "SELECT p.user_id, p.avatar_url, u.user_type FROM profiles p JOIN users u ON u.id = p.user_id "
     "WHERE p.avatar_url LIKE 'data:%' ORDER BY p.user_id",
     "UPDATE profiles SET avatar_url = :new WHERE user_id = :k AND avatar_url = :old RETURNING 1",
     _mig_avatar_kind),
    ("profiles.cover_url",
     "SELECT user_id, cover_url, NULL FROM profiles WHERE cover_url LIKE 'data:%' ORDER BY user_id",
     "UPDATE profiles SET cover_url = :new WHERE user_id = :k AND cover_url = :old RETURNING 1",
     lambda _t: "employee-cover"),
    ("company_profiles.cover_url",
     "SELECT user_id, cover_url, NULL FROM company_profiles WHERE cover_url LIKE 'data:%' ORDER BY user_id",
     "UPDATE company_profiles SET cover_url = :new WHERE user_id = :k AND cover_url = :old RETURNING 1",
     lambda _t: "company-cover"),
    ("kyc_submissions.id_front_url",
     "SELECT user_id, id_front_url, NULL FROM kyc_submissions WHERE id_front_url LIKE 'data:%' ORDER BY user_id",
     "UPDATE kyc_submissions SET id_front_url = :new WHERE user_id = :k AND id_front_url = :old RETURNING 1",
     lambda _t: "kyc-id-front"),
    ("kyc_submissions.selfie_url",
     "SELECT user_id, selfie_url, NULL FROM kyc_submissions WHERE selfie_url LIKE 'data:%' ORDER BY user_id",
     "UPDATE kyc_submissions SET selfie_url = :new WHERE user_id = :k AND selfie_url = :old RETURNING 1",
     lambda _t: "kyc-selfie"),
    ("site_settings.logo",
     "SELECT key, value, NULL FROM site_settings WHERE key IN ('logo_wide', 'logo_tall') "
     "AND value LIKE 'data:%' ORDER BY key",
     "UPDATE site_settings SET value = :new, updated_at = NOW() WHERE key = :k AND value = :old RETURNING 1",
     None),  # slot = key → bucket "site", name {slot}_{hex}{ext} (same as POST /admin/logo)
)


def _mig_run(sql: str, **params):
    conn = get_conn()
    try:
        return conn.run(sql, **params)
    finally:
        release_conn(conn)


@app.post("/admin/maintenance/migrate-data-images")
async def admin_migrate_data_images(request: Request, dry_run: int = 1):
    """Admin only. Moves legacy base64 data: images from the DB to Supabase
    Storage with the PR-7a rules (_validate_image_data_url → _store_image).
    dry_run=1 (default) only counts. Invalid values are left untouched and
    reported. Idempotent: a second run finds nothing to migrate.
    Response never contains image content or URLs — counts + reasons only."""
    check_admin(request)
    dry = dry_run != 0
    if not dry and not (_supabase_base_url() and _supabase_auth_headers()):
        raise HTTPException(503, "خدمة رفع الصور غير متاحة حالياً")
    report = {}
    for col, select_sql, update_sql, kind_of in _DATA_IMAGE_TARGETS:
        try:
            rows = _mig_run(select_sql)
        except Exception as e:
            print(f"[Migrate images] select failed {col}: {type(e).__name__}")
            report[col] = {"found": 0, "migrated": 0, "would_migrate": 0, "skipped": 0,
                           "reasons": {"select_failed": 1}}
            continue
        stat = {"found": len(rows), "migrated": 0, "would_migrate": 0, "skipped": 0, "reasons": {}}

        def _skip(reason):
            stat["skipped"] += 1
            stat["reasons"][reason] = stat["reasons"].get(reason, 0) + 1

        for row_key, old, user_type in rows:
            try:
                mime, ext, file_bytes = _validate_image_data_url(old)
            except HTTPException as he:
                _skip("too_large" if he.status_code == 413 else "invalid_image")
                continue
            if dry:
                stat["would_migrate"] += 1
                continue
            if kind_of is None:
                bucket, name = "site", f"{row_key}_{secrets.token_hex(6)}{ext}"
            else:
                kind = kind_of(user_type)
                bucket = _UPLOAD_KINDS[kind]
                name = f"{int(row_key)}_{kind}_{secrets.token_hex(6)}{ext}"
            try:
                new = await _store_image(bucket, name, file_bytes, mime, old, "[Migrate images]")
            except HTTPException:
                _skip("storage_failed")
                continue
            if not new or new == old:
                _skip("storage_failed")
                continue
            try:
                updated = _mig_run(update_sql, new=new, k=row_key, old=old)
            except Exception as e:
                print(f"[Migrate images] update failed {col} key={row_key}: {type(e).__name__}")
                _skip("update_failed")
                continue
            if not updated:
                # Value changed since SELECT — keep the newer value (uploaded object = orphan).
                _skip("changed_concurrently")
                continue
            stat["migrated"] += 1
            if kind_of is None:
                _html_cache[row_key] = new
        report[col] = stat
    print(f"[Migrate images] dry_run={dry} " + ", ".join(
        f"{c}: found={v['found']} migrated={v['migrated']} skipped={v['skipped']}" for c, v in report.items()))
    return {"status": "success", "dry_run": dry, "report": report}


@app.post("/verify-request")
def request_verification(data: VerifyRequestInput, token=Depends(verify_token)):
    try:
        payload = data.dict(exclude={"user_id"})
        req = create_verify_request(int(token["user_id"]), payload)
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
    return get_jobs({k:v for k,v in filters.items() if v})

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
    try:
        job = add_job(int(user_id), data.dict())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
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
        raw_fields = data.dict()
        # Extract non-column fields before building SQL SET clause
        accepted_pids  = raw_fields.pop("accepted_profession_ids", None)
        accepts_all    = raw_fields.get("accepts_all_professions")
        # duration_days needs special handling (also updates expires_at)
        duration_days  = raw_fields.pop("duration_days", None)
        fields = {k: v for k, v in raw_fields.items() if v is not None}

        # ── Step 1: ownership check + lifecycle guard (SELECT only — no mutation yet) ──
        current_rows = conn.run(
            "SELECT id, profession_id, status, closed_at, expires_at "
            "FROM jobs WHERE id=:id AND company_id=:cid",
            id=job_id, cid=cid
        )
        if not current_rows:
            print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user={cid} tried PUT job={job_id}")
            raise HTTPException(403, "ليست وظيفتك أو غير موجودة")
        # Block editing an expired job (30 days after closure)
        eff = _eff_status(current_rows[0][2], current_rows[0][3], current_rows[0][4])
        if eff == 'expired':
            raise HTTPException(403, "لا يمكن تعديل إعلان انتهت صلاحيته")
        # Block duration change on closed/expired jobs
        if duration_days is not None and eff in ('closed', 'expired'):
            raise HTTPException(403, "لا يمكن تعديل مدة إعلان منتهٍ")

        # ── Step 2: validate accepted_profession_ids BEFORE any mutation ─────
        # When accepts_all_professions=True, targets are cleared (empty list)
        if accepts_all:
            accepted_pids = []
        if accepted_pids is not None:
            effective_primary = raw_fields.get("profession_id") or current_rows[0][1]
            try:
                accepted_pids = _validate_accepted_profession_ids(
                    conn, effective_primary, accepted_pids
                )
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

        # ── Step 3: mutate only after all validation passed ───────────────────
        if fields:
            set_clause = ", ".join(f"{k}=:{k}" for k in fields)
            conn.run(
                f"UPDATE jobs SET {set_clause} WHERE id=:id AND company_id=:cid",
                id=job_id, cid=cid, **fields
            )

        # ── Step 3b: duration change — validate + reset clock ────────────────
        if duration_days is not None:
            dur = int(duration_days)
            if dur not in _ALLOWED_DURATIONS:
                raise HTTPException(422, "مدة استقبال الطلبات يجب أن تكون: 3، 7، 14، أو 30 يوماً")
            conn.run(
                f"UPDATE jobs SET duration_days={dur}, "
                f"expires_at=NOW() + INTERVAL '{dur} days' "
                "WHERE id=:id AND company_id=:cid",
                id=job_id, cid=cid
            )

        # ── Step 4: snapshot-replace accepted professions ─────────────────────
        if accepted_pids is not None:
            conn.run("DELETE FROM job_profession_targets WHERE job_id = :jid", jid=job_id)
            for i, pid in enumerate(accepted_pids):
                conn.run(
                    "INSERT INTO job_profession_targets (job_id, profession_id, display_order) "
                    "VALUES (:jid, :pid, :ord)",
                    jid=job_id, pid=pid, ord=i
                )

        return {"status": "success"}
    finally:
        release_conn(conn)

@app.delete("/company/jobs/{job_id}")
def remove_job(job_id: int, token=Depends(verify_token)):
    # Soft archive — never hard-deletes the row; archived_by comes from JWT only.
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: DELETE /company/jobs/{job_id}")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried DELETE /company/jobs/{job_id}")
        raise HTTPException(403, "شركات وجهات فقط")
    cid = int(user_id)
    try:
        result = archive_job(job_id, cid, cid)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user={cid} tried archive job={job_id}")
        raise HTTPException(403, str(e))
    return {"success": True, **result}

@app.patch("/company/jobs/{job_id}/status")
def set_job_status_endpoint(job_id: int, data: JobStatusInput, token=Depends(verify_token)):
    # JWT + DB ownership check before mutating
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: PATCH /company/jobs/{job_id}/status")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried PATCH /company/jobs/{job_id}/status")
        raise HTTPException(403, "شركات وجهات فقط")
    cid = int(user_id)
    conn = get_conn()
    try:
        rows = conn.run(
            "SELECT id FROM jobs WHERE id=:id AND company_id=:cid",
            id=job_id, cid=cid
        )
        if not rows:
            print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user={cid} tried PATCH job={job_id}/status")
            raise HTTPException(403, "ليست وظيفتك أو غير موجودة")
    finally:
        release_conn(conn)
    try:
        set_job_status(job_id, cid, data.status)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"status": "success"}

@app.get("/company/jobs")
def get_company_jobs(view: str = Query("active"), token=Depends(verify_token)):
    # Rule #1, #20: JWT only — owner sees their jobs filtered by view param.
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: GET /company/jobs")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried GET /company/jobs")
        raise HTTPException(403, "شركات وجهات فقط")
    if view not in ("active", "archived"):
        raise HTTPException(422, "view must be 'active' or 'archived'")
    jobs = get_company_jobs_all(int(user_id), view=view)
    return {"jobs": jobs, "count": len(jobs), "view": view}

@app.post("/jobs/{job_id}/apply")
def apply_to_job(job_id: int, data: JobApplyInput, token=Depends(verify_token)):
    token_uid  = token.get("user_id")
    token_type = token.get("user_type", "")
    if not token_uid:
        raise HTTPException(401, "رمز غير صالح")
    if token_type != "emp":
        raise HTTPException(403, "التقديم على الوظائف متاح للموظفين فقط")
    try:
        result = apply_job(job_id, int(token_uid), data.cover_letter or "")
    except JobArchivedError:
        return JSONResponse(status_code=409, content={"code": "job_archived", "message": "هذه الوظيفة مؤرشفة ولا تستقبل طلبات جديدة"})
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "success", **result}

@app.get("/jobs/{job_id}/applicants")
def job_applicants(
    job_id:         int,
    view:           str = "",
    page:           int = 1,
    limit:          int = 50,
    sort:           str = "applied_desc",
    city:           str = "",
    country:        str = "",
    applied_after:  str = "",
    applied_before: str = "",
    q:              str = "",
    min_match:      str = "",
    token=Depends(verify_token),
):
    """
    GET /jobs/{job_id}/applicants

    Query params (all optional):
      view=applicants|candidates  membership filter (no view → legacy response)
      page=N           1-based page (paginated views only)
      limit=N          1-100, default 50
      sort=applied_desc|applied_asc|match_desc|match_asc  (default applied_desc)
      city=...         case-insensitive filter on profiles.city
      country=...      case-insensitive filter on profiles.country
      applied_after=YYYY-MM-DD   inclusive lower bound on applied_at
      applied_before=YYYY-MM-DD  inclusive upper bound on applied_at
      q=...            substring search on full_name or headline
      min_match=N      returns HTTP 400 — activates when match_score schema is added

    No view → legacy: {applicants:[...], count:N} unchanged.
    """
    user_id = token.get("user_id")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: GET /jobs/{job_id}/applicants")
        raise HTTPException(401, "رمز غير صالح")

    # ── Validation ────────────────────────────────────────────────────────────
    if view not in ("", "applicants", "candidates"):
        raise HTTPException(400, "view يجب أن يكون: applicants أو candidates")

    if sort in {"match_desc", "match_asc"}:
        raise HTTPException(400,
            "sort=match_desc/match_asc غير متاح بعد — يُفعَّل عند إضافة match_score schema")
    if sort not in _APPLICANT_SORT_MAP:
        raise HTTPException(400,
            "sort يجب أن يكون: applied_desc | applied_asc")

    def _parse_date(val: str, param: str) -> None:
        try:
            datetime.strptime(val, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, f"{param} تاريخ غير صالح — يجب أن يكون بصيغة YYYY-MM-DD")

    if applied_after:
        _parse_date(applied_after, "applied_after")
    if applied_before:
        _parse_date(applied_before, "applied_before")

    if min_match:
        raise HTTPException(400,
            "min_match غير متاح بعد — يُفعَّل عند إضافة match_score schema")

    if page < 1:
        raise HTTPException(400, "page يجب أن يكون 1 أو أكثر")

    # ── Ownership check ───────────────────────────────────────────────────────
    conn = get_conn()
    try:
        rows = conn.run("SELECT company_id FROM jobs WHERE id=:jid", jid=job_id)
        if not rows:
            raise HTTPException(404, "الوظيفة غير موجودة")
        job_company_id = rows[0][0]
    finally:
        release_conn(conn)

    if int(job_company_id) != int(user_id):
        print(f"[SECURITY] JOB_OWNERSHIP_FAILED: user {user_id} tried to access applicants "
              f"for job {job_id} owned by {job_company_id}")
        raise HTTPException(403, "غير مصرح — هذه الوظيفة ليست لشركتك")

    result = get_job_applicants(
        job_id, int(job_company_id),
        view=view, page=page, limit=limit, sort=sort,
        city=city, country=country,
        applied_after=applied_after, applied_before=applied_before,
        q=q,
    )
    if not view:
        # Legacy response format — backward compatible with existing frontend
        return {"applicants": result["applicants"], "count": result["total"]}
    return result

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
    """
    Atomic applicant classification: updates job_applications.status AND
    company_candidate_job_refs.candidate_status in a single transaction.
    Ownership is verified inside the transaction (FOR UPDATE lock).
    Returns: {application_id, candidate_id, job_id, application_status, candidate_status, general_status}
    """
    user_id = token.get("user_id")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: PUT /jobs/applications/{app_id}/status")
        raise HTTPException(401, "رمز غير صالح")
    allowed_statuses = {"pending", "viewed", "accepted", "contacted", "interview", "hired", "rejected"}
    if data.status not in allowed_statuses:
        raise HTTPException(400, f"حالة غير صالحة. المسموح: {', '.join(sorted(allowed_statuses))}")
    try:
        result = update_application_status(app_id, data.status, actor_id=int(user_id))
        return result
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        print(f"[SECURITY] APPLICATION_OWNERSHIP_FAILED: user {user_id} → app {app_id}: {e}")
        raise HTTPException(403, str(e))
    except RuntimeError as e:
        print(f"[ERROR] update_application_status app {app_id}: {e}")
        raise HTTPException(500, str(e))


@app.post("/jobs/applications/{app_id}/promote")
def promote_applicant(app_id: int, token=Depends(verify_token)):
    """
    Atomic business operation: mark application 'accepted' + UPSERT candidate to 'shortlisted'.
    Replaces the old 'قبول مبدئي' single-system action with a dual-system atomic one.

    Returns: { application: {id, status}, candidate: {candidate_id, status, status_label, job_id, action} }
    """
    user_id = token.get("user_id")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: POST /jobs/applications/{app_id}/promote")
        raise HTTPException(401, "رمز غير صالح")
    try:
        return promote_application_to_shortlist(app_id, int(user_id))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        print(f"[SECURITY] PROMOTE_OWNERSHIP_FAILED: user {user_id} → app {app_id}: {e}")
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    except RuntimeError as e:
        print(f"[ERROR] promote_application_to_shortlist app {app_id}: {e}")
        raise HTTPException(500, str(e))


@app.get("/admin/jobs")
def admin_list_jobs(request: Request):
    check_admin(request)
    return get_jobs({})

@app.delete("/admin/jobs/{job_id}")
def admin_delete_job(job_id: int, request: Request):
    check_admin(request)
    conn = get_conn()
    try:
        conn.run("DELETE FROM jobs WHERE id=:id", id=job_id)
        return {"success": True}
    finally:
        release_conn(conn)


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
            "jobs_count": conn.run("SELECT COUNT(*) FROM jobs WHERE status='active' AND archived_at IS NULL")[0][0] if True else 0
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
    if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 32:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    if not _admin_jwt_secret_ok():
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    if not hmac.compare_digest(data.password.encode(), ADMIN_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
    print("[admin-auth] admin session issued sub=owner")
    return {"success": True, "token": _admin_jwt_issue(), "expires_in": _ADMIN_JWT_TTL}

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
        # Fetch request owner before update (needed for notification)
        vr_rows = conn.run("SELECT user_id FROM verify_requests WHERE id = :id", id=req_id)
        conn.run(
            "UPDATE verify_requests SET status = :s WHERE id = :id",
            s=data.status, id=req_id
        )
        # Phase 8: notify request owner on verification decision (non-fatal)
        try:
            if vr_rows:
                req_owner_id = int(vr_rows[0][0])
                approved = data.status == "approved"
                create_notification(
                    user_id=req_owner_id,
                    type_="verify",
                    title="تم مراجعة طلب توثيقك" if approved else "طلب توثيقك يحتاج مراجعة",
                    body="تمت الموافقة على طلب التوثيق ✅" if approved else "تم رفض طلب التوثيق",
                    link="/settings",
                    entity_id=req_id,
                    entity_type="verify_request",
                    event_key=f"verify_{data.status}:verify_request:{req_id}:admin"
                )
        except Exception as _ne:
            print(f"[TW-WARN] verify notification (req {req_id}) failed: {_ne}")
        return {"success": True}
    except HTTPException:
        raise
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
def delete_own_account(user_id: int, data: AccountDeleteInput, token=Depends(verify_token)):
    """User deletes their own account — JWT owner only + current password (bcrypt).
    Hard delete — FK audit: ARCHITECTURE.md → Account Security Operations. UI hidden until soft delete (F27)."""
    if token["user_id"] != user_id:
        raise HTTPException(403, "لا يمكنك حذف حساب شخص آخر")
    if not data.password:
        raise AccountFieldError("password", "required", "أدخل كلمة المرور للتأكيد")
    try:
        ok = check_user_password(user_id, data.password)
    except Exception as e:
        print(f"[DELETE account] password check ERROR user={user_id}: {e}")
        raise HTTPException(500, detail="تعذّر حذف الحساب، حاول لاحقاً")
    if ok is None:
        raise HTTPException(404, detail="المستخدم غير موجود")
    if not ok:
        raise AccountFieldError("password", "wrong_password", "كلمة المرور غير صحيحة")
    conn = get_conn()
    try:
        conn.run("DELETE FROM users WHERE id = :uid", uid=user_id)
    except Exception as e:
        print(f"[DELETE account] ERROR user={user_id}: {e}")
        raise HTTPException(500, detail="تعذّر حذف الحساب، حاول لاحقاً")
    finally:
        release_conn(conn)
    _cache_del('profile:' + str(user_id))
    print(f"[DELETE account] deleted user={user_id}")
    return {"ok": True, "success": True}

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
    try:
        # Same helper as PUT /auth/password → bumps password_changed_at (user's sessions end).
        _password_changed_cache_set(user_id, set_user_password(user_id, pw))
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))

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
    data.certificate_url = _validate_external_url(data.certificate_url, "certificate_url", "رابط الشهادة")
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
    data.source_url = _validate_external_url(data.source_url, "source_url", "رابط المصدر")   # §54 rule 4b
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
    data.source_url = _validate_external_url(data.source_url, "source_url", "رابط المصدر")   # §54 rule 4b
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


# ══════════════════════════════════════════════════════════════════════════
# Appointments & Interview Rooms — API Endpoints (Phase 2–6)
# JWT Bearer only — X-User-Id permanently forbidden
# ══════════════════════════════════════════════════════════════════════════

# ── HTML pages ────────────────────────────────────────────────────────────

@app.get("/appointments", response_class=HTMLResponse)
def page_appointments():
    return HTMLResponse(read_html("appointments.html"))

@app.get("/appointment-room", response_class=HTMLResponse)
def page_appointment_room():
    return HTMLResponse(read_html("appointment-room.html"))


# ── Pydantic models ───────────────────────────────────────────────────────

class AppointmentCreateInput(BaseModel):
    # Path A (backward-compat): supply application_id only
    application_id: Optional[int] = None
    # Path B (pipeline): supply candidate_id + job_id (pipeline entry must exist)
    candidate_id: Optional[int] = None
    job_id: Optional[int] = None
    appointment_type: Optional[str] = None
    mode: Optional[str] = "online"
    notes: Optional[str] = None
    online_url: Optional[str] = None
    location_text: Optional[str] = None
    representative_name: Optional[str] = None

class AppointmentSendInput(BaseModel):
    scheduled_at: str          # ISO 8601
    deadline_hours: Optional[int] = 48
    online_url: Optional[str] = None
    location_text: Optional[str] = None
    notes: Optional[str] = None
    representative_name: Optional[str] = None

class RescheduleInput(BaseModel):
    new_scheduled_at: str      # ISO 8601
    deadline_hours: Optional[int] = 48
    online_url: Optional[str] = None
    location_text: Optional[str] = None
    notes: Optional[str] = None

class CancelInput(BaseModel):
    reason: Optional[str] = ""

class AppointmentMessageInput(BaseModel):
    body: str


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/appointments")
def api_create_appointment(body: AppointmentCreateInput,
                            token=Depends(verify_token)):
    """
    POST /api/appointments

    Path A (backward-compat): { application_id }
    Path B (pipeline):        { candidate_id, job_id, appointment_type }

    company_id always derived from JWT.
    Returns 409 with code=pipeline_entry_required when no pipeline entry exists (Path B).
    Returns 409 with code=pipeline_application_conflict on application_id mismatch.
    """
    user_id = int(token["user_id"])
    if token.get("user_type") != "co":
        raise HTTPException(403, "فقط حسابات الشركات يمكنها إنشاء مواعيد")

    # Complete payload contract enforcement:
    # Path A: application_id only (candidate_id and job_id must be absent)
    # Path B: candidate_id + job_id only (application_id must be absent)
    # All other combinations are rejected with structured 400 errors.
    from fastapi.responses import JSONResponse as _JR
    _app_set  = body.application_id is not None
    _cand_set = body.candidate_id is not None
    _job_set  = body.job_id is not None

    if _app_set and (_cand_set or _job_set):
        # application_id mixed with any Path B field — ambiguous context
        return _JR(
            status_code=400,
            content={
                "ok": False,
                "code": "ambiguous_appointment_context",
                "message": (
                    "Payload غير واضح: أرسل application_id فقط (Path A) "
                    "أو candidate_id + job_id فقط (Path B) — وليس كليهما معاً."
                ),
            }
        )
    if _cand_set and not _job_set:
        # candidate_id without job_id — incomplete Path B
        return _JR(
            status_code=400,
            content={
                "ok": False,
                "code": "invalid_appointment_context",
                "message": "candidate_id يتطلب job_id (Path B غير مكتمل).",
            }
        )
    if _job_set and not _cand_set:
        # job_id without candidate_id — incomplete Path B
        return _JR(
            status_code=400,
            content={
                "ok": False,
                "code": "invalid_appointment_context",
                "message": "job_id يتطلب candidate_id (Path B غير مكتمل).",
            }
        )
    if not _app_set and not (_cand_set and _job_set):
        # Neither path provided
        return _JR(
            status_code=400,
            content={
                "ok": False,
                "code": "invalid_appointment_context",
                "message": "يجب إرسال application_id (Path A) أو candidate_id + job_id (Path B).",
            }
        )

    try:
        appt = create_appointment(
            company_user_id=user_id,
            application_id=body.application_id,
            candidate_id=body.candidate_id,
            job_id=body.job_id,
            appointment_type=body.appointment_type,
            mode=body.mode or "online",
            notes=body.notes,
            online_url=body.online_url,
            location_text=body.location_text,
            representative_name=body.representative_name,
        )
        return {"ok": True, "data": appt}
    except PipelineApplicationConflictError as e:
        from fastapi.responses import JSONResponse as _JR
        return _JR(
            status_code=409,
            content={
                "ok": False,
                "code": "pipeline_application_conflict",
                "message": str(e),
            }
        )
    except PipelineEntryRequiredError as e:
        from fastapi.responses import JSONResponse as _JR
        return _JR(
            status_code=409,
            content={
                "ok": False,
                "code": "pipeline_entry_required",
                "message": str(e),
            }
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_create_appointment] {e}")
        raise HTTPException(500, str(e))


@app.get("/api/appointments")
def api_list_appointments(status: Optional[str] = None,
                           limit: int = 20, offset: int = 0,
                           token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        result = list_appointments(user_id, status_filter=status,
                                    limit=limit, offset=offset)
        return {"ok": True, "data": result, "count": len(result)}
    except Exception as e:
        print(f"[api_list_appointments] {e}")
        raise HTTPException(500, str(e))


@app.get("/api/appointments/{appointment_id}")
def api_get_appointment_room(appointment_id: int, token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        room = get_appointment_room(appointment_id, user_id)
        return {"ok": True, "data": room}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        print(f"[api_get_appointment_room] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/send")
def api_send_appointment(appointment_id: int, body: AppointmentSendInput,
                          token=Depends(verify_token)):
    user_id = int(token["user_id"])
    if token.get("user_type") != "co":
        raise HTTPException(403, "فقط حسابات الشركات يمكنها إرسال دعوات المقابلة")
    try:
        appt = send_appointment(
            appointment_id=appointment_id,
            user_id=user_id,
            scheduled_at_iso=body.scheduled_at,
            deadline_hours=body.deadline_hours or 48,
            online_url=body.online_url,
            location_text=body.location_text,
            notes=body.notes,
            representative_name=body.representative_name,
        )
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_send_appointment] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/accept")
def api_accept_appointment(appointment_id: int, token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        appt = accept_appointment(appointment_id, user_id)
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_accept_appointment] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/request-reschedule")
def api_request_reschedule(appointment_id: int, body: CancelInput,
                             token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        appt = request_reschedule_appointment(appointment_id, user_id,
                                               reason=body.reason or "")
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_request_reschedule] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/reschedule")
def api_reschedule_appointment(appointment_id: int, body: RescheduleInput,
                                token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        appt = reschedule_appointment(
            appointment_id=appointment_id,
            user_id=user_id,
            new_scheduled_at_iso=body.new_scheduled_at,
            deadline_hours=body.deadline_hours or 48,
            online_url=body.online_url,
            location_text=body.location_text,
            notes=body.notes,
        )
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_reschedule_appointment] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/cancel")
def api_cancel_appointment(appointment_id: int, body: CancelInput,
                             token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        appt = cancel_appointment(appointment_id, user_id, reason=body.reason or "")
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_cancel_appointment] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/complete")
def api_complete_appointment(appointment_id: int, token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        appt = complete_appointment(appointment_id, user_id)
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_complete_appointment] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/close")
def api_close_appointment(appointment_id: int, token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        appt = close_appointment(appointment_id, user_id)
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_close_appointment] {e}")
        raise HTTPException(500, str(e))


@app.get("/api/appointments/{appointment_id}/events")
def api_get_appointment_events(appointment_id: int, token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        events = get_appointment_events(appointment_id, user_id)
        return {"ok": True, "data": events}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        print(f"[api_get_appointment_events] {e}")
        raise HTTPException(500, str(e))


@app.get("/api/appointments/{appointment_id}/messages")
def api_get_appointment_messages(appointment_id: int,
                                  limit: int = 50, offset: int = 0,
                                  token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        msgs = get_appointment_messages(appointment_id, user_id,
                                         limit=limit, offset=offset)
        return {"ok": True, "data": msgs}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        print(f"[api_get_appointment_messages] {e}")
        raise HTTPException(500, str(e))


@app.post("/api/appointments/{appointment_id}/messages")
def api_create_appointment_message(appointment_id: int,
                                    body: AppointmentMessageInput,
                                    token=Depends(verify_token)):
    user_id = int(token["user_id"])
    try:
        msg = create_appointment_message(appointment_id, user_id, body.body)
        return {"ok": True, "data": msg}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_create_appointment_message] {e}")
        raise HTTPException(500, str(e))


# ── Scheduler Internal Endpoint — S3 ─────────────────────────────────────────
# Machine-to-machine only. No JWT, no user session, no X-User-Id.
# Auth: X-Scheduler-Secret header verified with hmac.compare_digest.
# Secret: SCHEDULER_SECRET env var (Railway Variables — never in source).
# Caller: external cron (GitHub Actions / cron-job.org) per S0 decision.

@app.post("/internal/run-due-jobs")
def internal_run_due_jobs(request: Request, limit: int = 20):
    """
    Trigger the scheduler runner from an external cron.

    Security:
      - No JWT required (machine-to-machine, no user context).
      - X-Scheduler-Secret header must match SCHEDULER_SECRET env var.
      - Verification uses hmac.compare_digest (timing-attack safe).
      - Returns 503 if SCHEDULER_SECRET is not configured on this server.
      - Returns 403 on missing or wrong secret.
      - Secret is never logged or returned in any response field.

    Args (query):
      limit: jobs to pick per call, clamped to [1, 50], default 20.

    Returns:
      {"ok": true, "picked": N, "done": N, "failed": N,
       "retried": N, "runner_id": str, "jobs": [...]}
    """
    if not SCHEDULER_SECRET:
        raise HTTPException(503, "Scheduler not configured (SCHEDULER_SECRET env var not set)")

    incoming = request.headers.get("X-Scheduler-Secret", "")
    if not incoming or not hmac.compare_digest(incoming, SCHEDULER_SECRET):
        raise HTTPException(403, "Forbidden")

    try:
        result = run_due_scheduler_jobs(limit=limit)
        return result
    except Exception as e:
        print(f"[internal_run_due_jobs] ERROR: {e}")
        raise HTTPException(500, "Runner error")


# ── Pipeline Backfill — Admin endpoints ──────────────────────────────────────

@app.post("/admin/pipeline/backfill")
def admin_pipeline_backfill(
    request: Request,
    dry_run: bool = False,
    confirm: bool = False,
):
    """
    POST /admin/pipeline/backfill[?dry_run=true][&confirm=true]
    Trigger Pipeline Backfill (PR-2).

    dry_run=true  → read-only analysis, no writes.
    dry_run=false → executes backfill in a single atomic transaction.
                    confirm=true is REQUIRED for dry_run=false.

    HTTP 400 — confirm=false when dry_run=false (safety guard).
    HTTP 409 — blocking conflicts detected (application_id mismatches); resolve first.

    Requires X-Admin-Token header.
    """
    check_admin(request)
    if not dry_run and not confirm:
        raise HTTPException(
            400,
            "يجب تمرير confirm=true للتنفيذ الفعلي. شغّل dry_run=true أولاً للتحقق."
        )
    try:
        result = run_pipeline_backfill(dry_run=dry_run)
        return result
    except BlockingConflictError as e:
        # Atomic conflict check ran inside the advisory lock → return structured 409
        return JSONResponse(status_code=409, content=e.report)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.get("/admin/pipeline/backfill/dry-run")
def admin_pipeline_backfill_dry_run(request: Request):
    """
    GET /admin/pipeline/backfill/dry-run
    Read-only analysis of legacy data eligible for backfill. No writes.
    Requires X-Admin-Token header.
    """
    check_admin(request)
    try:
        return pipeline_backfill_dry_run()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/admin/pipeline/migrate-index")
def admin_pipeline_migrate_index(
    request: Request,
    confirm: bool = False,
):
    """
    POST /admin/pipeline/migrate-index[?confirm=true]
    Create the partial UNIQUE index on job_pipeline_entries(application_id).

    MUST be called AFTER backfill + conflict check — not at startup.
    confirm=true required for safety.

    Response:
      200 {"status":"ok", "action":"created"|"already_exists", "index_status":{...}}
      400 if confirm not passed
      409 BlockingConflictError (conflicts block index creation)
      500 if index not ready after creation attempt

    Requires X-Admin-Token header.
    """
    check_admin(request)
    if not confirm:
        raise HTTPException(
            400,
            "يجب تمرير confirm=true. تأكد أن الـ backfill اكتمل بدون blocking_conflicts أولاً."
        )
    try:
        # Check status before to determine action label
        pre_status = get_pipeline_application_index_status()
        already_ready = pre_status.get("ready", False)

        _migrate_partial_unique_application_id()

        # Verify index is genuinely ready after creation
        idx_status = get_pipeline_application_index_status()
        if not idx_status.get("ready") or "error" in idx_status:
            return JSONResponse(
                status_code=500,
                content={
                    "code":         "pipeline_index_not_ready",
                    "index_status": idx_status,
                },
            )

        return {
            "status":       "ok",
            "action":       "already_exists" if already_ready else "created",
            "index_status": idx_status,
        }
    except BlockingConflictError as e:
        return JSONResponse(status_code=409, content=e.report)
    except Exception as e:
        raise HTTPException(500, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# PR-5: Pipeline Notes + Pipeline Appointment endpoints
# ══════════════════════════════════════════════════════════════════════════════

# ── Input models ─────────────────────────────────────────────────────────────

class PipelineNoteCreateInput(BaseModel):
    body: str

class PipelineNoteUpdateInput(BaseModel):
    body: str

# ── Pipeline Notes endpoints ──────────────────────────────────────────────────

@app.get("/company/pipeline/{entry_id}/notes")
def api_list_pipeline_notes(entry_id: int, token=Depends(verify_token)):
    """GET /company/pipeline/{entry_id}/notes — list active notes for a pipeline entry."""
    company_id = int(token["user_id"])
    if token.get("user_type") != "co":
        raise HTTPException(403, "فقط حسابات الشركات يمكنها قراءة ملاحظات Pipeline")
    try:
        notes = list_pipeline_notes(entry_id, company_id)
        return {"ok": True, "data": {"notes": notes, "count": len(notes)}}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        print(f"[api_list_pipeline_notes] {e}")
        raise HTTPException(500, str(e))


@app.post("/company/pipeline/{entry_id}/notes")
def api_create_pipeline_note(entry_id: int, body: PipelineNoteCreateInput,
                              token=Depends(verify_token)):
    """POST /company/pipeline/{entry_id}/notes — create a note on a pipeline entry."""
    company_id = int(token["user_id"])
    if token.get("user_type") != "co":
        raise HTTPException(403, "فقط حسابات الشركات يمكنها إضافة ملاحظات Pipeline")
    try:
        note = create_pipeline_note(entry_id, body.body, company_id, company_id)
        return {"ok": True, "data": {"note": note}}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_create_pipeline_note] {e}")
        raise HTTPException(500, str(e))


@app.patch("/company/pipeline/notes/{note_id}")
def api_update_pipeline_note(note_id: int, body: PipelineNoteUpdateInput,
                              token=Depends(verify_token)):
    """PATCH /company/pipeline/notes/{note_id} — edit a pipeline note."""
    company_id = int(token["user_id"])
    if token.get("user_type") != "co":
        raise HTTPException(403, "فقط حسابات الشركات يمكنها تعديل ملاحظات Pipeline")
    try:
        note = update_pipeline_note(note_id, company_id, body.body)
        return {"ok": True, "data": {"note": note}}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_update_pipeline_note] {e}")
        raise HTTPException(500, str(e))


@app.delete("/company/pipeline/notes/{note_id}")
def api_delete_pipeline_note(note_id: int, token=Depends(verify_token)):
    """DELETE /company/pipeline/notes/{note_id} — soft-delete a pipeline note."""
    company_id = int(token["user_id"])
    if token.get("user_type") != "co":
        raise HTTPException(403, "فقط حسابات الشركات يمكنها حذف ملاحظات Pipeline")
    try:
        delete_pipeline_note(note_id, company_id)
        return {"ok": True}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        print(f"[api_delete_pipeline_note] {e}")
        raise HTTPException(500, str(e))


