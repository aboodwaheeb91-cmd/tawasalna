# See ARCHITECTURE.md for system architecture rules

"""
تواصلنا - Arabic Employment Platform
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Request, Response, Depends, BackgroundTasks, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator
import base64, hashlib, mimetypes
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
# Bounded (task 5.0h-2 — AUD-P2-13): ip → (code, saved_at); entries older than
# ip_country_cache_ttl_s are looked up again; past ip_country_cache_max the oldest entry goes
# (insertion order). Both read per use via tw_settings.limit (admin-editable — task 4.2, at once).
IP_TO_COUNTRY_CACHE = {}

def _ip_country_cache_put(ip: str, code: str) -> None:
    IP_TO_COUNTRY_CACHE.pop(ip, None)
    while len(IP_TO_COUNTRY_CACHE) >= tw_settings.limit("ip_country_cache_max"):
        IP_TO_COUNTRY_CACHE.pop(next(iter(IP_TO_COUNTRY_CACHE)))
    IP_TO_COUNTRY_CACHE[ip] = (code, time.time())

def get_country_from_ip(ip: str) -> str:
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return 'DEFAULT'
    hit = IP_TO_COUNTRY_CACHE.get(ip)
    if hit is not None:
        if time.time() - hit[1] < tw_settings.limit("ip_country_cache_ttl_s"):
            return hit[0]
        IP_TO_COUNTRY_CACHE.pop(ip, None)
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
        _ip_country_cache_put(ip, result)
        return result
    except Exception:
        return 'DEFAULT'

# ── Client IP (PR 1.4) — the ONLY reader of X-Forwarded-For / X-Real-IP ──
# CLIENT_IP_SOURCE: x_real_ip (default — PR 3.9b: Railway sets X-Real-IP to the real client and drops
# the client's own X-Forwarded-For) · xff_left · xff_right (+ TRUSTED_PROXY_HOPS, default 1) · peer.
# Missing header, unknown source or an invalid IP → request.client.host
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
    source = (os.environ.get("CLIENT_IP_SOURCE") or "x_real_ip").strip().lower()
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
    init_db, _migrate_user_unique_indexes, _migrate_profiles_user_unique, EmailTakenError, get_conn,
    create_appointment, send_appointment, accept_appointment,
    request_reschedule_appointment, reschedule_appointment,
    cancel_appointment, complete_appointment, close_appointment,
    list_appointments, get_appointment_room,
    get_appointment_events, get_appointment_messages,
    create_appointment_message,
    AppointmentRuleError, list_jobs_for_scheduling, get_open_appointments,
    search_schedule_people,
    create_user, authenticate_user, get_user_by_id, check_user_password, set_user_password, set_user_type, _migrate_password_changed_at, _migrate_session_version,
    _migrate_password_reset_tokens, get_user_for_password_reset, password_reset_issue, password_reset_consume,
    PASSWORD_RESET_TTL_MINUTES, EMAIL_TOKEN_TTL_MINUTES, email_change_request, email_change_apply,
    _migrate_email_notify, email_notify_reserve, email_log_write, email_send_stats,
    get_email_prefs, set_email_prefs, schedule_message_email,
    _migrate_company_settings, get_company_settings, set_company_settings,
    otp_ttl_minutes,
    get_public_profile, get_full_profile, update_profile,
    get_profile_by_tw_id, get_user_id_by_tw_id, get_user_info_by_tw_id,
    project_public_profile, project_owner_profile, project_owner_kyc_status,
    add_experience, update_experience, reorder_experience, add_education, add_course, update_education, update_course,
    add_job, get_jobs, get_job, apply_job,
    start_kyc, send_email_code, verify_email_code,
    send_phone_code, verify_phone_code, upload_kyc_docs,
    get_kyc_status, admin_approve_kyc, admin_reject_kyc, get_all_kyc_submissions, ensure_site_settings_table,
    set_user_verified, KycStateError, REPORT_TARGET_TYPES, _migrate_reports_targets, _migrate_verified_source, _migrate_experience_sort_order,
    get_current_user_type, _migrate_rls_lockdown,
    send_message_pipeline, mark_message_delivered, get_conversations, get_messages, get_unread_count,
    can_send_message, message_policy_decide, end_conversation, MessagePolicyError, MESSAGE_POLICY_REASONS,
    MESSAGE_POLICY_FACTS_SQL_ASYNCPG, MESSAGE_PAIR_LOCK_SQL_ASYNCPG, MESSAGE_REOPEN_SQL_ASYNCPG,
    _migrate_conversation_endings,
    create_notification, get_notifications, mark_notifications_read, mark_notification_read,
    get_unread_notifications, _migrate_notifications_schema_v2,
    _migrate_notifications_schema_v2_1,
    get_job_applicants, get_user_applications,
    update_application_status, promote_application_to_shortlist, archive_job,
    get_company_jobs_all, set_job_status,
    get_site_setting, set_site_setting, release_conn, db_conn,
    _cache_del,
    get_company_profile_row, get_company_extras,
    update_company_profile,
    _migrate_company_branches, get_company_branches, save_company_branches,
    _migrate_jobs_v2, _migrate_job_lifecycle, _migrate_kyc_otp_security, _migrate_kyc_reject_reason,
    job_active_sql, admin_hard_delete_job,
    admin_set_job_hidden, admin_reactivate_job, admin_extend_job, JobActionError, admin_unarchive_job, JOB_HIDE_REASON_MAX,
    admin_update_job, notify_job_applicants_updated, admin_job_delete_preview,
    _migrate_taxonomy_foundation,
    _migrate_job_profession_targets,
    _fetch_accepted_professions_batch,
    rate_company,
    get_company_ratings_detail,
    get_company_posts, get_company_post_stats, get_company_posts_count, create_company_post, update_company_post, get_post_owner, delete_company_post, record_company_post_view, set_company_post_appreciation, set_company_post_save,
    get_company_post_comments, create_company_post_comment, update_company_post_comment, delete_company_post_comment,
    follow_profile, unfollow_profile, get_profile_followers_count, is_profile_following,
    get_profile_followers_list, get_profile_following_list, get_follow_state,
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
    run_scheduler_cycle,
    scheduler_heartbeat_status,
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
from auth import withdraw_application, ApplicationStateError, ReapplyLimitError   # task 8.2a
from auth import _otp_norm_target   # task 4.3 — the one OTP target normaliser (send limits = stored target)
from auth import guest_otp_issue, guest_otp_verify   # task 7.1 — guest support code (same OTP rules)
from auth import otp_code_valid   # task 8.4c-0b — the one OTP shape check (6 digits)
from auth import email_notify_user   # task 7.2b — support_reply email (name + address from users)
import admin_perms   # task 8.4a — admin permission catalog (docs/rules/admin-staff.md)
from auth import hash_password as _hash_password, verify_password as _verify_password
import admin_staff   # task 8.4b — staff accounts + admin two-step login (docs/rules/admin-staff.md)
import support   # task 7.1 — Support Tickets (docs/rules/support.md · SYSTEMS_INDEX §62)

# ── Secrets from environment — NEVER hardcoded in source ──
# Required Railway Variables:
#   ADMIN_TOKEN      — random 32+ byte hex (e.g. openssl rand -hex 32) — admin LOGIN password only
#   ADMIN_JWT_SECRET — random 32+ byte hex, signs admin session JWTs; INDEPENDENT of JWT_SECRET / ADMIN_TOKEN
#   JWT_SECRET       — random 32+ byte hex, INDEPENDENT of ADMIN_TOKEN
#   ADMIN_URL_TOKEN  — random slug for admin panel URL path
#   ADMIN_MFA_KEY    — ≥ 32 chars, encrypts the admin authenticator secrets at rest (admin_staff.py — task 8.4b)
#   ADMIN_MFA_RESET  — optional, YYYY-MM-DD: owner MFA reset on the first password login of that UTC day
#                      (docs/rules/admin-staff.md → owner recovery) — removed again right after
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


# ── Session invalidation after password change (PR 1.8 · session_version 5.0b) ──
# users.session_version (bumped by set_user_password) + users.password_changed_at.
# A user JWT carrying claim sv is valid only while sv == the current session_version
# (no clock involved — a token issued in the same second as the change dies too).
# Older JWTs without sv kept the PR 1.8 check (iat earlier than the change second → rejected)
# until they expired (issued ≤ 2026-10-15 + 7 days); from _NO_SV_REJECT_FROM a token without sv
# is rejected outright (task 5.0f). A token of an account that no longer exists → rejected.
# Read through a short in-memory cache (no DB query per request); every password-change path
# refreshes the entry immediately. Other worker processes (if any) pick the change up within
# _PWD_CHANGED_TTL.
_PWD_CHANGED_TTL = 60.0  # seconds
_pwd_changed_cache: dict = {}   # user_id → ({changed, sv} | None, cached_at monotonic)
_NO_SV_REJECT_FROM = 1792713600   # 2026-10-23T00:00:00Z — every pre-5.0b token has expired by then

def _session_state(user_id: int):
    import time
    hit = _pwd_changed_cache.get(user_id)
    now = time.monotonic()
    if hit is not None and now - hit[1] < _PWD_CHANGED_TTL:
        return hit[0]
    from auth import get_session_state
    value = get_session_state(user_id)   # raises on DB error — not cached
    if value is not None:                # no such user → not cached: checked in the DB every time (5.0f)
        _pwd_changed_cache[user_id] = (value, now)
    return value

def _password_changed_cache_set(user_id: int, state) -> None:
    """Called by the password-change paths with set_user_password()'s {changed, sv} —
    the new value is effective at once in this process."""
    import time
    _pwd_changed_cache[int(user_id)] = (state, time.monotonic())

def _end_user_sessions(user_id: int, state, reason: str) -> None:
    """After a session_version bump (set_user_password / set_user_type): every older JWT of the
    user → 401 in this process at once + open sockets closed (4008). Admin paths use this one place."""
    if state is None:
        return
    _password_changed_cache_set(user_id, state)
    _ws_revoke_user(user_id, reason)

def _jwt_revoked_by_password_change(payload: dict) -> bool:
    import time
    uid = payload.get("user_id")
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return False
    if "sv" not in payload and time.time() >= _NO_SV_REJECT_FROM:
        return True   # pre-5.0b token — the compatibility path is closed (task 5.0f)
    try:
        state = _session_state(uid)
    except Exception as e:
        # DB unreachable: the request fails at its own DB call anyway; rejecting here
        # would log every user out on a DB blip. Logged, not cached (F9).
        print(f"[session-invalidation] session state lookup failed user={uid}: {e}")
        return False
    if state is None:
        return True   # account deleted — its tokens die with it (task 5.0f); DB down is handled above
    if state.get("deleted"):
        return True   # soft-deleted (task 8.5a) — every request 401; a restore needs a new login (sv bumped)
    if state.get("suspended"):
        return True   # suspended by the admin (task 5.4) — same 401 path as a deleted account, reversible
    if "sv" in payload:
        sv = payload.get("sv")
        if not isinstance(sv, int) or isinstance(sv, bool):
            return True
        return sv != int(state.get("sv") or 0)
    changed = state.get("changed")
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
# The admin login (<panel>/login) checks the ADMIN_TOKEN password and returns THIS token — the raw
# ADMIN_TOKEN never reaches the browser and is never accepted as a session.
# Claims shape is fixed so plan 5.3 (staff accounts) adds values, not fields:
#   iss "tawasalna" · aud "tw-admin" · sub "owner" | "staff:<id>" (task 8.4b)
#   role "admin" (owner, perms ["*"]) | "staff" (perms [] — check_admin reads the real ones from the DB)
#   sv = session_version (owner: admin_owner_mfa · staff: admin_staff) — compared on every request
#   iat · exp (iat + _ADMIN_JWT_TTL, ≤ 1h) · jti (random, for a future denylist)
# Issued ONLY after both login steps (password, then authenticator code) — _admin_ticket_* is the step between.
_ADMIN_JWT_TTL = 3600
_ADMIN_JWT_ISS = "tawasalna"
_ADMIN_JWT_AUD = "tw-admin"
_ADMIN_ROLES = {"admin", "staff"}   # roles accepted by check_admin (staff — task 8.4b)
# Login ticket (task 8.4b): password step → this, never an admin token. Own aud → never verifies as one.
_ADMIN_TICKET_TTL = 300
_ADMIN_TICKET_AUD = "tw-admin-mfa"
# Content screens (phase 5a — strings · theme colors · news): read + write behind this permission,
# same pattern as tw_settings.PERM ("settings.edit"). The owner token ("*") holds both.
CONTENT_PERM = "content.edit"

def _admin_jwt_secret_ok() -> bool:
    return (len(ADMIN_JWT_SECRET) >= 32
            and not hmac.compare_digest(ADMIN_JWT_SECRET.encode(), JWT_SECRET.encode())
            and not hmac.compare_digest(ADMIN_JWT_SECRET.encode(), ADMIN_TOKEN.encode()))

def _admin_jwt_issue(sub: str = "owner", role: str = "admin", perms=None, sv: int = 1) -> str:
    import time, secrets
    if not _admin_jwt_secret_ok():
        raise RuntimeError("ADMIN_JWT_SECRET is not configured")
    now = int(time.time())
    return _jwt_sign({
        "iss": _ADMIN_JWT_ISS, "aud": _ADMIN_JWT_AUD,
        "sub": sub, "role": role, "perms": list(perms) if perms is not None else ["*"], "sv": int(sv),
        "iat": now, "exp": now + _ADMIN_JWT_TTL, "jti": secrets.token_hex(12),
    }, ADMIN_JWT_SECRET)


def _admin_ticket_issue(sub: str, sv: int) -> str:
    """Password step passed (task 8.4b) → 5-minute ticket for the code step. Not an admin token (own aud)."""
    import time, secrets
    now = int(time.time())
    return _jwt_sign({"iss": _ADMIN_JWT_ISS, "aud": _ADMIN_TICKET_AUD, "typ": "mfa_ticket", "sub": sub,
                      "sv": int(sv), "iat": now, "exp": now + _ADMIN_TICKET_TTL, "jti": secrets.token_hex(12)},
                     ADMIN_JWT_SECRET)


def _admin_ticket_claims(token: str) -> dict:
    if not _admin_jwt_secret_ok() or not isinstance(token, str):
        return {}
    c = _jwt_verify(token, ADMIN_JWT_SECRET)
    if (not c or c.get("iss") != _ADMIN_JWT_ISS or c.get("aud") != _ADMIN_TICKET_AUD
            or c.get("typ") != "mfa_ticket" or not isinstance(c.get("sub"), str) or not isinstance(c.get("sv"), int)):
        return {}
    try:
        if int(c["exp"]) - int(c["iat"]) > _ADMIN_TICKET_TTL:
            return {}
    except (KeyError, TypeError, ValueError):
        return {}
    return c

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
    """True only when KYC email codes can really be delivered (task 5.1b): the email
    provider is configured (RESEND_API_KEY) AND the kyc_email_otp type is switched on
    (site_settings[email_settings].types). DEV_OTP_LOG does NOT count as a provider."""
    return email_service.can_send("kyc_email_otp")


def is_phone_otp_delivery_available() -> bool:
    """Returns True only when a real SMS delivery provider is configured.
    No SMS provider is currently implemented. Enable this function body
    when an actual provider (Twilio, Vonage, etc.) is integrated.
    DEV_OTP_LOG does NOT count as a delivery provider."""
    return False


# ── App ──
# strict_content_type=False (task 8.8b): FastAPI ≥ 0.132 rejects a JSON body without a JSON Content-Type by
# default — kept off so every client request is parsed exactly as before the upgrade.
app = FastAPI(title="تواصلنا API", version="1.0.0", strict_content_type=False)

# Fix [A-4]: Prevent browser HTTP cache from serving stale .html/.js files
# This is the correct architectural fix — works for every page, not just profile
from starlette.middleware.base import BaseHTTPMiddleware


def _req_path(request) -> str:
    """The routed path — the ONLY input for a path decision (task 8.8a · GHSA-86qp-5c8j-p5mr / CVE-2026-48710).
    request.url is rebuilt from the Host header, so a broken Host ("a#", "a/x") changes request.url.path while
    routing still uses scope["path"]. ❌ request.url.path / request.url.hostname in any decision or log."""
    return request.scope.get("path") or "/"


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = _req_path(request)
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

# ── Internal Error Responses (PR 1.6 — SYSTEMS_INDEX §54d) ──
# An unexpected exception (DB error, bug) never reaches the client: its text can
# carry table / constraint / column names. Full details go to the log only.
# Usage in an endpoint:  except Exception as e: raise _server_error("endpoint_name", e)
# ❌ HTTPException(500, str(e)) · ❌ detail=f"...{e}" · ❌ {"error": str(e)} in any response.
# Intended errors (ValueError / PermissionError with an Arabic message written in code,
# ContentValidationError …) keep their own 4xx message — this is for the unexpected only.
_SERVER_ERROR_MSG = "خطأ في الخادم، حاول مرة أخرى"

def _server_error(where: str, e: BaseException) -> HTTPException:
    import traceback
    print(f"[server-error] {where}: {type(e).__name__}: {e}")
    traceback.print_exception(type(e), e, e.__traceback__)
    return HTTPException(500, _SERVER_ERROR_MSG)

def _http_error_content(detail) -> dict:
    """HTTPException.detail → response body. str → {"error": str} (unchanged shape).
    dict → real JSON {"error": <message>, "detail": {...}} — never str(dict)."""
    if isinstance(detail, dict):
        msg = detail.get("message") or detail.get("error")
        return {"error": msg if isinstance(msg, str) and msg else "حدث خطأ", "detail": detail}
    return {"error": str(detail)}

# ── API Contract (PR 3A — SYSTEMS_INDEX §45b · ARCHITECTURE §API Contract) ──
# The official response shape for NEW endpoints and for endpoints migrated with their page:
#   success → {"ok": true, "data": ...}          (api_ok)
#   error   → {"ok": false, "error": {"code", "message", "field"?}}   (api_error)
# Existing endpoints keep their current shape until they are migrated (F14) — twApi reads both.
# Unexpected exceptions still go through _server_error (never str(e) in `message`).
from fastapi.encoders import jsonable_encoder

def api_ok(data=None, status: int = 200, **extra):
    """Success body. extra = list meta only (total / page …), next to data."""
    body = {"ok": True, "data": data}
    body.update(extra)
    if status == 200:
        return body
    return JSONResponse(status_code=status, content=jsonable_encoder(body))

def api_error(status: int, code: str, message: str, field: str = None) -> JSONResponse:
    """Error body — message is an Arabic text written in code; field only for a field error."""
    err = {"code": code, "message": message}
    if field:
        err["field"] = field
    return JSONResponse(status_code=status, content={"ok": False, "error": err})

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content=_http_error_content(exc.detail))

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    # Field location + error type only — never the submitted values (str(exc) echoes them).
    details = [{"loc": [p for p in err.get("loc", ()) if isinstance(p, (str, int))],
                "type": str(err.get("type", ""))} for err in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "بيانات غير صحيحة", "details": details})

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    print(f"[ERROR] {_req_path(request)}: {type(exc).__name__}: {exc}")
    return JSONResponse(status_code=500, content={"error": _SERVER_ERROR_MSG})

# ── Search indexing (task 5.0e — SYSTEMS_INDEX §54m) ──
# The ONLY indexable HTML pages: the landing page, public profiles /u/{tw_id}, the public job page.
# Every other HTML response (login, settings, messages, notifications, home, admin panel / admin pages,
# legacy redirects, duplicates like /landing.html) gets X-Robots-Tag: noindex, nofollow.
# /sitemap.xml lists public pages only. ❌ Disallow in robots.txt for these (a crawler must fetch the page
# to see noindex) · ❌ the admin panel path in robots.txt / sitemap (it is a secret).
_INDEXABLE_PAGES = frozenset({"/", "/job-detail", "/privacy", "/terms"})


def _is_indexable_page(path: str) -> bool:
    return path in _INDEXABLE_PAGES or (path.startswith("/u/") and len(path) > 3)


# ── Security Headers ──
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    try:
        response.headers["X-Content-Type-Options"] = "nosniff"
        # task 8.4c-0b — HTTPS only for a year (sub-domains too). No preload; CSP is a separate task.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        # A route that set its own (stricter) policy keeps it — the staff link pages + /staff/* replies set
        # no-referrer (task 8.4c-2b-1 · docs/rules/admin-staff.md rules 14–15); everything else gets the default.
        if "referrer-policy" not in response.headers:
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if response.headers.get("content-type", "").startswith("text/html") \
                and not _is_indexable_page(_req_path(request)):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        _path = _req_path(request)
        if _path == "/support/track" or _path.startswith("/support/track/"):
            # guest follow-up link (task 7.2a — ARCHITECTURE §81): page + API, every status
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Robots-Tag"] = "noindex"
    except Exception as e:
        print(f"[security_headers] {_req_path(request)}: {type(e).__name__}: {e}")
    return response

# ── Simple Rate Limiting ──
from collections import defaultdict, deque, OrderedDict
from collections.abc import MutableMapping
import time as _time
import threading
# Shared in-memory rate store (task 5.0h-2 — AUD-P2-13 · task 5.4d): key "kind:who" → hit times.
# One section per kind (the key prefix — a RATES name, "ip", "log-error" …), each an OrderedDict
# kept oldest-last-hit first, each capped at mem_store_max_keys on its own: a full
# section never evicts another kind's counters. Bounded without a thread and without a sort: on
# use, expired keys are popped from the front of a section (window from RATES by kind, else the
# longest window in RATES) — every section at most every mem_store_sweep_s; a new key
# in a full section evicts that section's oldest key — never a login lock / OTP send key (_RATE_NO_EVICT: only
# its window ends it; a full lock / OTP send section takes the new key over its cap until windows end —
# never fail-open, never lock everyone out). _rate_lock makes check + count one step across
# threadpool requests; nothing inside it touches the DB. Both mem_store_* values via tw_settings.limit
# (memory read — safe under _rate_lock; admin-editable, task 4.2).
class _RateStore(MutableMapping):
    def __init__(self):
        self._kinds = {}

    @staticmethod
    def _kind(key: str) -> str:
        return key.split(":", 1)[0]

    def __getitem__(self, key):
        sec = self._kinds.get(self._kind(key))
        if sec is None:
            raise KeyError(key)
        return sec[key]

    def __setitem__(self, key, hits):
        """A new hit → the key becomes the section's newest."""
        sec = self._kinds.setdefault(self._kind(key), OrderedDict())
        sec[key] = hits
        sec.move_to_end(key)

    def keep(self, key, hits):
        """Old hits dropped, last hit unchanged → same place in its section."""
        self._kinds[self._kind(key)][key] = hits

    def __delitem__(self, key):
        kind = self._kind(key)
        sec = self._kinds.get(kind)
        if sec is None:
            raise KeyError(key)
        del sec[key]
        if not sec:
            del self._kinds[kind]

    def __iter__(self):
        return iter([k for sec in list(self._kinds.values()) for k in sec])

    def __len__(self):
        return sum(len(sec) for sec in self._kinds.values())

    def clear(self):
        self._kinds.clear()

    def section(self, kind: str):
        return self._kinds.get(kind)

    def kinds(self) -> list:
        return list(self._kinds)


_rate_store = _RateStore()
_rate_lock = threading.Lock()
_rate_sweep_at = 0.0
_RATE_LIMIT = 20  # requests per minute per client IP (all _RATE_LIMITED_PATHS together)
_LOG_ERROR_RATE = 30  # POST /log/error per minute per client IP (own bucket — task 5.0e)


def _rate_key_ttl(key: str) -> float:
    kind = key.split(":", 1)[0]   # windows via tw_settings (admin-editable — task 4.1), memory only
    return tw_settings.rate(kind)[1] if kind in tw_limits.RATES else max(tw_settings.rate(n)[1] for n in tw_limits.RATES)


def _rate_expire_locked(kind: str, now: float, full: bool = False) -> None:
    """Caller holds _rate_lock. Drop the kind's expired keys — from the front only (oldest last
    hit first), or every key when full (force)."""
    sec = _rate_store.section(kind)
    if sec is None:
        return
    ttl = _rate_key_ttl(kind)
    if full:
        for key, hits in list(sec.items()):
            if not hits or now - hits[-1] >= ttl:
                del _rate_store[key]
        return
    while sec:
        key, hits = next(iter(sec.items()))
        if hits and now - hits[-1] < ttl:
            break
        del _rate_store[key]
        if _rate_store.section(kind) is None:
            break


def _rate_trim_locked(kind: str, cap: int) -> None:
    """Caller holds _rate_lock. Evict the kind's oldest keys down to cap — never a _RATE_NO_EVICT kind."""
    if kind in _RATE_NO_EVICT:
        return
    sec = _rate_store.section(kind)
    while sec is not None and len(sec) > cap:
        del _rate_store[next(iter(sec))]
        sec = _rate_store.section(kind)


def _rate_sweep_locked(now: float = None, force: bool = False) -> int:
    """Caller holds _rate_lock. Expired keys of every kind (force: full scan + cap). Returns keys removed."""
    global _rate_sweep_at
    now = _time.time() if now is None else now
    if not force and now - _rate_sweep_at < tw_settings.limit("mem_store_sweep_s"):
        return 0
    _rate_sweep_at = now
    before = len(_rate_store)
    for kind in _rate_store.kinds():
        _rate_expire_locked(kind, now, full=force)
        if force:
            _rate_trim_locked(kind, tw_settings.limit("mem_store_max_keys"))
    for uid in [u for u, (_, at) in list(_pwd_changed_cache.items())
                if _time.monotonic() - at >= _PWD_CHANGED_TTL]:
        _pwd_changed_cache.pop(uid, None)
    return before - len(_rate_store)


def _rate_sweep(now: float = None, force: bool = False) -> int:
    with _rate_lock:
        return _rate_sweep_locked(now, force)


def _rate_room_locked(key: str, now: float) -> None:
    """Caller holds _rate_lock. Before a NEW key: its section's expired front, then room under
    the cap (oldest of the same kind first; a lock section never evicts — see above)."""
    if key in _rate_store:
        return
    kind = _RateStore._kind(key)
    _rate_expire_locked(kind, now)
    _rate_trim_locked(kind, tw_settings.limit("mem_store_max_keys") - 1)


def _rate_prune_locked(key: str, window: float) -> list:
    _rate_sweep_locked()
    now = _time.time()
    hits = [t for t in _rate_store.get(key, ()) if now - t < window]
    if hits:
        _rate_store.keep(key, hits)
    else:
        _rate_store.pop(key, None)
    return hits


def _rate_hit_retry(key: str, limit: int, window: float) -> int:
    """Sliding window on the shared _rate_store — one locked step. Allowed → counted, 0. Over the
    limit → seconds (≥ 1) until enough old hits leave the window for the next one to pass (Retry-After)."""
    with _rate_lock:
        hits = _rate_prune_locked(key, window)
        now = _time.time()
        if len(hits) >= limit:
            return max(1, int(-(-(hits[len(hits) - limit] + window - now) // 1)))
        _rate_room_locked(key, now)
        _rate_store[key] = hits + [now]
        return 0


def _rate_hit(key: str, limit: int, window: float) -> bool:
    """Sliding window on the shared _rate_store. True = allowed (and counted) — one locked step."""
    return _rate_hit_retry(key, limit, window) == 0


def _rate_reserve(checks):
    """[(rate_name, who), …] — every bucket checked first, then one hit added to every one, in one locked
    step: one full bucket → None and nothing counted; else the reservation [(key, t), …] — the hits stay
    (a failure counted before the slow check runs — task 8.4c-0) unless _rate_release takes them back.
    Rates via tw_settings.rate. The ONE check-and-count of several buckets (_rate_ok_all = this)."""
    return _rate_reserve_window(checks)[0]


def _rate_reserve_window(checks):
    """_rate_reserve + the window (s) of the first full bucket: (reservation, None) or (None, window)."""
    with _rate_lock:
        buckets = []
        for rate_name, who in checks:
            max_hits, window = tw_settings.rate(rate_name)
            key = f"{rate_name}:{who}"
            hits = _rate_prune_locked(key, window)
            if len(hits) >= max_hits:
                return None, window
            buckets.append((key, hits))
        now = _time.time()
        for key, hits in buckets:
            _rate_room_locked(key, now)
            _rate_store[key] = hits + [now]
        return [(key, now) for key, _ in buckets], None


def _rate_release(held) -> None:
    """Take back the hits of a _rate_reserve reservation (the attempt succeeded)."""
    with _rate_lock:
        for key, t in held or ():
            hits = list(_rate_store.get(key, ()))
            if t in hits:
                hits.remove(t)
                if hits:
                    _rate_store.keep(key, hits)
                else:
                    _rate_store.pop(key, None)


def _rate_ok_all(checks) -> bool:
    """Every bucket checked, then every one counted — one locked step (task 4.3)."""
    return _rate_reserve(checks) is not None


# Per-(user, post / comment) toggles + comments — RATES on the shared store (task 5.0h-2;
# they had one dict each). Guards against auto-clickers.
def _check_appr_rate(user_id: int, post_id: int) -> bool:
    return _rate_ok("post_appreciate", f"{user_id}:{post_id}")


def _check_save_rate(user_id: int, post_id: int) -> bool:
    return _rate_ok("post_save", f"{user_id}:{post_id}")


def _check_cmt_create_rate(user_id: int, post_id: int) -> bool:
    return _rate_ok("comment_create", f"{user_id}:{post_id}")


def _check_cmt_edit_rate(user_id: int, comment_id: int) -> bool:
    return _rate_ok("comment_edit", f"{user_id}:{comment_id}")


# Login lock (PR 1.4 per email · task 5.0h-2 — AUD-P2-16 + per IP + per IP and email pair).
# Failed logins only; tw_settings.rate login_email / login_ip / login_ip_email (admin-editable,
# task 4.2 — read on every check, so a new count / window applies at once). Every email (existing or
# not) is counted and locked the same way, and the locked reply is one text — it never says
# whether the address has an account. Success clears the email + pair buckets, never the IP one.
_LOGIN_LOCKS = ("login_email", "login_ip", "login_ip_email")
# KYC OTP send (task 4.3): per account + channel · per normalised target (any account) · per client IP.
_OTP_SEND_RATES = ("otp_send_user", "otp_send_target", "otp_send_ip")
# Security buckets a full section never evicts — only their window ends them (task 5.4d · 4.3).
# Admin login locks (task 8.4c-0): a flood of other accounts must never evict the owner's counter.
_ADMIN_LOGIN_LOCKS = ("admin_login_ip", "admin_login_acct", "admin_mfa_ip", "admin_mfa_acct")
_RATE_NO_EVICT = frozenset(_LOGIN_LOCKS + _OTP_SEND_RATES + _ADMIN_LOGIN_LOCKS)


def _login_lock_who(email: str, ip: str) -> dict:
    e = (email or "").strip().lower()
    return {"login_email": e, "login_ip": ip, "login_ip_email": f"{ip}|{e}"}


def _login_reserve(email: str, ip: str):
    """task 8.4c-0b — the three locks checked + counted in ONE locked step BEFORE bcrypt (_rate_reserve):
    (reservation, None) or, one lock full, (None, its window s) with nothing counted. The hits stay on a
    failure (= the failure count) and _rate_release takes them back on success — parallel wrong passwords
    can never pass the limit."""
    return _rate_reserve_window(list(_login_lock_who(email, ip).items()))


def _login_email_reset(email: str, ip: str = None, every_ip: bool = False) -> None:
    """Clears the email bucket + the pair bucket of ip. every_ip (password reset — task 7.5b) → the pair
    bucket of this email from EVERY IP too. The IP bucket (login_ip) is never cleared here."""
    who = _login_lock_who(email, ip or "")
    with _rate_lock:
        _rate_store.pop("login_email:" + who["login_email"], None)
        if ip:
            _rate_store.pop("login_ip_email:" + who["login_ip_email"], None)
        if every_ip:
            sec = _rate_store.section("login_ip_email")
            for key in [k for k in (sec or ()) if k.split(":", 1)[1].partition("|")[2] == who["login_email"]]:
                del _rate_store[key]


_RATE_LIMITED_PATHS = frozenset({
    "/auth/login", "/auth/register", "/auth/password",
    "/tw-ctrl-" + ADMIN_URL_TOKEN + "/login",   # admin login, under the panel path (task 5.3a; old /tw-ctrl-login removed 5.3b)
    "/auth/password-reset/request", "/auth/password-reset/confirm",
    "/auth/email-change/request", "/auth/email-change/confirm",
    "/kyc/email/send", "/kyc/phone/send", "/kyc/email/verify", "/kyc/phone/verify",
})


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    # Only rate limit auth / OTP endpoints — IP from get_client_ip() only
    _p = _req_path(request)
    if _p == "/log/error":   # client error reports — own per-IP bucket, never eats the auth budget (task 5.0e)
        if not _rate_hit("log-error:" + get_client_ip(request), _LOG_ERROR_RATE, 60):
            from fastapi.responses import JSONResponse as _JR
            return _JR(status_code=429, content={"error": "طلبات كثيرة جداً، حاول بعد دقيقة"})
    elif _p in _RATE_LIMITED_PATHS \
            or (_p.startswith("/auth/user/") and _p.endswith("/delete")):  # account delete (closed — always 403, task 5.0e)
        if not _rate_hit("ip:" + get_client_ip(request), _RATE_LIMIT, 60):
            from fastapi.responses import JSONResponse as _JR
            return _JR(status_code=429, content={"error": "طلبات كثيرة جداً، حاول بعد دقيقة"})
    return await call_next(request)


# ── Admin Audit Log (task 5.3a2 · SYSTEMS_INDEX §25b) — the ONE place admin actions are recorded ──
# Every admin write (POST / PUT / PATCH / DELETE under /admin/) + the admin login (success, wrong
# password, rate limited). Stored: actor (admin JWT sub) · route name · path params · result · IP
# (get_client_ip). Never the body, the password, the token or any message text.
import admin_insights
import blocks_suspension as bs   # task 5.4 — Account Suspension + User Blocks (SYSTEMS_INDEX §25f)
import account_deletion as ad    # task 8.5a — soft account delete + restore (SYSTEMS_INDEX §25i)
import account_purge             # task 8.5c — final purge after account_purge_days (SYSTEMS_INDEX §25i)
import tw_terms
_ADMIN_LOGIN_PATHS = frozenset({"/tw-ctrl-" + ADMIN_URL_TOKEN + "/login"})
_STAFF_PUBLIC_PATHS = frozenset({"/staff/invite/start", "/staff/invite/complete", "/staff/mfa-reset/start",
                                 "/staff/mfa-reset/complete", "/staff/password-reset/complete",
                                 "/tw-ctrl-" + ADMIN_URL_TOKEN + "/forgot"})
_AUDIT_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Reads that are still recorded (task 5.3a3): data leaving the site — route names under /admin/.
AUDIT_READ_ROUTES = frozenset({"admin_users_export"})
# Settings writes (task 4.2): a security key (tw_settings.is_security) → action "<route>_security"
# on every row of that request (200 / 401 / 403 / 422) — the audit list filters on it.
_AUDIT_SETTINGS_ROUTES = frozenset({"admin_settings_update", "admin_settings_reset"})


def _admin_audit_entry(request, status: int):
    """The audit row for this request, or None when it is not an admin write / login."""
    path = _req_path(request)
    if path in _ADMIN_LOGIN_PATHS and request.method == "POST":
        # task 8.4b — the account the login named (owner / staff:<id>, "-" = unknown); step 2 = admin_login_mfa
        return {"actor": str(getattr(request.state, "audit_actor", "-")),
                "action": str(getattr(request.state, "audit_action", "admin_login")), "target": None,
                "status": status, "ip": get_client_ip(request)}
    if path in _STAFF_PUBLIC_PATHS and request.method == "POST":
        # task 8.4c-2a2 — the staff member the link belongs to (staff:<id>, "-" = bad link / forgot — never which
        # email exists); never the token, the code or the password
        route = request.scope.get("route")
        return {"actor": str(getattr(request.state, "audit_actor", "-")), "action": getattr(route, "name", "-") or "-",
                "target": None, "status": status, "ip": get_client_ip(request)}
    if not path.startswith("/admin/"):
        return None
    route = request.scope.get("route")
    if route is None:            # no matching endpoint (404 / 405) — nothing ran
        return None
    if request.method not in _AUDIT_WRITE_METHODS and getattr(route, "name", "") not in AUDIT_READ_ROUTES:
        return None
    claims = _admin_jwt_claims(request.headers.get("X-Admin-Token", ""))
    params = request.scope.get("path_params") or {}
    target = ",".join(f"{k}={params[k]}" for k in sorted(params)) or None
    # content writes (phase 5a) name their own target (string keys · token names · news id) — never the text
    target = getattr(request.state, "audit_target", None) or target
    action = getattr(route, "name", "") or "-"
    if action in _AUDIT_SETTINGS_ROUTES and tw_settings.is_security(str(params.get("key", ""))):
        action += "_security"
    entry = {"actor": str(claims.get("sub") or "-") if claims else "-", "action": action,
             "target": target, "status": status, "ip": get_client_ip(request)}
    # old / new value — set by the settings endpoints only (task 4.1), numbers, never a secret
    change = getattr(request.state, "audit_change", None)
    if change:
        entry["old_value"], entry["new_value"] = change
    return entry


@app.middleware("http")
async def admin_audit_middleware(request, call_next):
    response = await call_next(request)
    entry = _admin_audit_entry(request, response.status_code)
    if entry:
        await asyncio.to_thread(admin_insights.audit_record, **entry)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,  # Must be False with allow_origins=["*"]
)


# ── Canonical host (task 7.7 · ARCHITECTURE §34) — www.tawasolna.com → tawasolna.com ──
# Added last = outermost: runs before every other middleware and rate limit. HTTP only (WebSocket
# untouched — _WS_PROD_ORIGINS keeps www). Location is built from a constant + the request path,
# never from Host / X-Forwarded-Host. GET / HEAD → 301 · anything else → 308 (method + body kept).
_CANONICAL_ORIGIN = "https://tawasolna.com"
_WWW_HOST = "www.tawasolna.com"


class CanonicalHostMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            host = ""
            for k, v in scope.get("headers") or ():
                if k == b"host":
                    host = v.decode("latin-1")
                    break
            if host.strip().lower().rsplit(":", 1)[0] == _WWW_HOST:
                raw = scope.get("raw_path") or scope.get("path", "/").encode("utf-8")
                path = raw.decode("latin-1")
                if not path.startswith("/"):
                    path = "/" + path
                qs = (scope.get("query_string") or b"").decode("latin-1")
                url = _CANONICAL_ORIGIN + path + ("?" + qs if qs else "")
                code = 301 if scope.get("method") in ("GET", "HEAD") else 308
                await RedirectResponse(url, status_code=code)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(CanonicalHostMiddleware)

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
    """asyncpg send — one transaction: pair lock + can_send_message facts (task 5.0g —
    message_policy_decide, the same rule as auth.can_send_message) + INSERT.
    Refused → MessagePolicyError, nothing written.

    Hot  path: INSERT as read.
    Cold path: INSERT unread + COUNT.
    """
    t0 = time.perf_counter()
    async with _asyncpg_pool.acquire() as conn:
        t_after_conn = time.perf_counter()
        if mark_as_read:
            insert_sql = (
                "INSERT INTO messages "
                "(sender_id, receiver_id, content, is_read, delivered_at, read_at) "
                "VALUES ($1, $2, $3, TRUE, NOW(), NOW()) "
                "RETURNING id, sender_id, receiver_id, content, "
                "is_read, delivered_at, read_at, created_at")
        else:
            insert_sql = (
                "INSERT INTO messages (sender_id, receiver_id, content) "
                "VALUES ($1, $2, $3) "
                "RETURNING id, sender_id, receiver_id, content, "
                "is_read, delivered_at, read_at, created_at")
        async with conn.transaction():
            await conn.execute(MESSAGE_PAIR_LOCK_SQL_ASYNCPG, sender_id, receiver_id)
            facts = await conn.fetchrow(MESSAGE_POLICY_FACTS_SQL_ASYNCPG, sender_id, receiver_id)
            policy = message_policy_decide(sender_id, facts)
            if not policy["allowed"]:
                raise MessagePolicyError(policy["reason"], 404 if policy["reason"] == "not_found" else 403)
            if policy["reopen"]:
                await conn.execute(MESSAGE_REOPEN_SQL_ASYNCPG, sender_id, receiver_id)
            t_after_policy = time.perf_counter()
            row = await conn.fetchrow(insert_sql, sender_id, receiver_id, content)
        t_after_insert = time.perf_counter()
        msg = _serialize_asyncpg_row(row)
        if mark_as_read:
            timing = {
                "conn_ms":        round((t_after_conn   - t0)             * 1000),
                "sync_set_ms":    0,
                "policy_ms":      round((t_after_policy - t_after_conn)   * 1000),
                "insert_exec_ms": round((t_after_insert - t_after_policy) * 1000),
                "insert_ms":      round((t_after_insert - t_after_conn)   * 1000),
                "update_ms":      0,
                "count_ms":       0,
                "db_ms":          round((t_after_insert - t0)             * 1000),
                "driver":         "asyncpg",
            }
            return msg, None, timing

        unread = await conn.fetchval(
            "SELECT COUNT(*) FROM messages WHERE receiver_id=$1 AND is_read=FALSE",
            receiver_id
        )
        t_after_count = time.perf_counter()
        timing = {
            "conn_ms":        round((t_after_conn   - t0)              * 1000),
            "sync_set_ms":    0,
            "policy_ms":      round((t_after_policy - t_after_conn)    * 1000),
            "insert_exec_ms": round((t_after_insert - t_after_policy)  * 1000),
            "insert_ms":      round((t_after_insert - t_after_conn)    * 1000),
            "update_ms":      0,
            "count_ms":       round((t_after_count  - t_after_insert)  * 1000),
            "db_ms":          round((t_after_count  - t0)              * 1000),
            "driver":         "asyncpg",
        }
        return msg, int(unread or 0), timing


# ── Startup migrations — one policy (PR 2B · CLAUDE.md → Startup Migration Policy) ──
# critical = the app reads this schema on core paths (auth / profiles / jobs /
#            applications / pipeline / appointments / notifications / scheduler), or a
#            later critical migration depends on it → failure stops startup.
# optional = one feature or performance only → failure is logged, reported on /health
#            (name + ok/failed, no error details) and the rest of the site keeps working.
# Order matters (dependencies run first).
def _startup_migrations():
    return (
        ("init_db",                           init_db,                             True),
        ("profiles_user_unique",              _migrate_profiles_user_unique,       True),
        ("user_unique_indexes",               _migrate_user_unique_indexes,        False),
        ("news_posts",                        _migrate_news_posts,                 True),    # 7.6 — read by /home/feed (filter=all)
        ("feed_indexes",                      _migrate_feed_indexes,               False),
        ("feed_snapshots",                    _migrate_feed_snapshots,             False),  # 8.6d-1 — failure → feed first page only (next_cursor null)
        ("company_branches",                  _migrate_company_branches,           False),
        ("company_saved_candidates",          _migrate_company_saved_candidates,   True),
        ("company_candidate_job_refs",        _migrate_company_candidate_job_refs, True),
        ("candidate_status_per_job",          _migrate_candidate_status_per_job,   True),
        ("password_changed_at",               _migrate_password_changed_at,        True),
        ("session_version",                   _migrate_session_version,            True),
        ("password_reset_tokens",             _migrate_password_reset_tokens,      True),
        ("email_notify",                      _migrate_email_notify,               True),
        ("company_settings",                  _migrate_company_settings,           False),
        ("kyc_otp_security",                  _migrate_kyc_otp_security,           True),
        ("kyc_reject_reason",                 _migrate_kyc_reject_reason,          True),   # 8.1 — read by every KYC status / review / docs upload
        ("jobs_v2",                           _migrate_jobs_v2,                    True),
        ("job_lifecycle",                     _migrate_job_lifecycle,              True),
        ("taxonomy_foundation",               _migrate_taxonomy_foundation,        True),
        ("job_profession_targets",            _migrate_job_profession_targets,     True),    # 7.6 — written by add_job after the job row
        ("notifications_schema_v2",           _migrate_notifications_schema_v2,    True),
        ("notifications_schema_v2_1",         _migrate_notifications_schema_v2_1,  True),
        ("appointments",                      _migrate_appointments,               True),
        ("scheduler_jobs",                    _migrate_scheduler_jobs,             True),
        ("pipeline_schema_v1",                _migrate_pipeline_schema_v1,         True),
        ("pr5_pipeline_linking",              _migrate_pr5_pipeline_linking,       True),
        ("applicants_candidates_split",       _migrate_applicants_candidates_split, True),
        ("admin_audit_log",                   admin_insights.migrate_admin_audit_log, True),
        ("reports_targets",                   _migrate_reports_targets,            False),
        ("verified_source",                   _migrate_verified_source,            False),
        ("experience_sort_order",             _migrate_experience_sort_order,      True),   # AUD-P2-49 — read by every profile
        ("conversation_endings",              _migrate_conversation_endings,       True),   # 5.0g — read by every message send
        ("blocks_suspension",                 bs.migrate_blocks_suspension,        True),   # 5.4 — read by the session check + every visibility query
        ("account_deletion",                  ad.migrate_account_deletion,         True),   # 8.5a — read by the session check + every visibility query
        ("account_purge",                     account_purge.migrate_account_purge, True),   # 8.5c — read by every restore (409 once a purge started)
        ("terms_acceptance",                  tw_terms.migrate_terms_acceptance,   True),   # terms — written by every registration
        ("app_settings",                      tw_settings.migrate_app_settings,    False),  # 4.1 — after admin_audit_log; failure → defaults
        ("support_tickets",                   support.migrate_support,             False),  # 7.1 — support only; failure → its routes 500
        ("admin_staff",                       admin_staff.migrate_admin_staff,     True),   # 8.4b — check_admin + the admin login read it
        ("admin_roles_seed",                  admin_staff.seed_default_roles,      False),  # 8.4c-2a1 — the 4 ready roles, once ever
        ("rls_lockdown",                      _migrate_rls_lockdown,               True),   # last — after every table exists
    )


_MIGRATION_STATUS: dict = {}   # name → "ok" | "failed" — exposed by /health


def _run_startup_migrations(migrations=None) -> dict:
    """Run every startup migration in order. Optional failure → logged + "failed";
    critical failure → logged + RuntimeError (FastAPI refuses to start)."""
    for name, fn, critical in (migrations if migrations is not None else _startup_migrations()):
        try:
            fn()
        except Exception as e:
            _MIGRATION_STATUS[name] = "failed"
            kind = "critical" if critical else "optional"
            print(f"❌ [migration] {name} failed ({kind}): {type(e).__name__}: {e}")
            if critical:
                raise RuntimeError(f"critical startup migration failed: {name}") from e
            continue
        _MIGRATION_STATUS[name] = "ok"
        print(f"✅ [migration] {name}")
    return dict(_MIGRATION_STATUS)


# ── Single instance (task 4.3 — ARCHITECTURE §76) ──
# _rate_store (rates · login locks · OTP send limits) lives in this process's memory: correct
# only with ONE process (Procfile: one uvicorn process · Railway replicas = 1). More workers =
# each keeps its own counters → every limit multiplied. Startup only warns, never stops.
def _worker_count(env=None, argv=None) -> int:
    env = os.environ if env is None else env
    argv = sys.argv if argv is None else argv
    counts = []
    raw = (env.get("WEB_CONCURRENCY") or "").strip()
    if raw.isdigit():
        counts.append(int(raw))
    for i, a in enumerate(argv):
        val = a.split("=", 1)[1] if a.startswith(("--workers=", "-w=")) else (
            argv[i + 1] if a in ("--workers", "-w") and i + 1 < len(argv) else None)
        if val and val.strip().isdigit():
            counts.append(int(val))
    return max(counts or [1])


def _single_instance_warning(env=None, argv=None):
    n = _worker_count(env, argv)
    if n <= 1:
        return None
    return (f"⚠️  [rate-store] {n} workers detected (WEB_CONCURRENCY / --workers) — the in-memory "
            "rate store is per process: rate limits, login locks and OTP send limits are NOT shared "
            "and each one is multiplied by the worker count. Run one process (Procfile) + Railway replicas = 1.")


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
    if not admin_staff.mfa_key_ok():
        print("⚠️  ADMIN_MFA_KEY not configured (min 32 chars) — admin login will return 503")
    if not ADMIN_URL_TOKEN:
        print("⚠️  ADMIN_URL_TOKEN not configured — admin panel URL will not be accessible")
    for _line in _supabase_storage_status_lines():
        print(_line)
    _warn = _single_instance_warning()
    if _warn:
        print(_warn)
    _run_startup_migrations()
    await asyncio.to_thread(_strings_load_overrides)
    await asyncio.to_thread(_actions_load_overrides)
    await asyncio.to_thread(_email_load_settings)
    await asyncio.to_thread(tw_settings.reload)   # task 4.1 — admin settings → cache (failure → defaults)
    _settings_loop_start()
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
    _scheduler_loop_start()


# ── Internal scheduler loop (task 6.3 — SYSTEMS_INDEX §37) ──
# Every SCHEDULER_INTERVAL_SECONDS: auth.run_scheduler_cycle() in a worker thread (sync DB).
# The cycle's advisory lock makes several workers / instances safe (one runs, the rest skip).
# A failed cycle is logged and the loop goes on. SCHEDULER_LOOP=0 turns it off (tests);
# the GitHub cron (scheduler-cron.yml → POST /internal/run-due-jobs) stays as the backup.
SCHEDULER_INTERVAL_SECONDS = 60
_scheduler_task = None


async def _scheduler_loop():
    while True:
        try:
            res = await asyncio.to_thread(run_scheduler_cycle)
            if res.get("picked") or res.get("stale_reset") or not res.get("ok"):
                print(f"[scheduler-loop] picked={res.get('picked')} done={res.get('done')} "
                      f"retried={res.get('retried')} failed={res.get('failed')} "
                      f"stale_reset={res.get('stale_reset')} ok={res.get('ok')}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[scheduler-loop] cycle failed: {type(e).__name__}: {e}")
        await asyncio.sleep(SCHEDULER_INTERVAL_SECONDS)


def _scheduler_loop_start():
    global _scheduler_task
    if os.environ.get("SCHEDULER_LOOP", "1") == "0":
        print("⚠️  [scheduler-loop] off (SCHEDULER_LOOP=0) — only the external cron runs jobs")
        return
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.get_running_loop().create_task(_scheduler_loop())
        print(f"✅ [scheduler-loop] started — every {SCHEDULER_INTERVAL_SECONDS}s")


# ── Admin settings refresh (task 4.1 — SYSTEMS_INDEX §25g) ──
# Every tw_settings.CACHE_TTL_S (30 s): app_settings → cache in a worker thread, so a value saved by
# another worker / instance applies here within 30 s. Reads stay memory only. reload() never raises.
_settings_task = None


async def _settings_loop():
    while True:
        await asyncio.sleep(tw_settings.CACHE_TTL_S)
        await asyncio.to_thread(tw_settings.reload)


def _settings_loop_start():
    global _settings_task
    if _settings_task is None or _settings_task.done():
        _settings_task = asyncio.get_running_loop().create_task(_settings_loop())


@app.on_event("shutdown")
async def on_shutdown():
    global _scheduler_task, _settings_task
    task, _scheduler_task = _scheduler_task, None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        print("[scheduler-loop] stopped")
    st, _settings_task = _settings_task, None
    if st is not None and not st.done():
        st.cancel()

# ── Helpers ──
from page_shell import apply_shell
import tw_strings
import tw_actions
import tw_limits
import tw_settings   # task 4.1 — admin-editable limits / rates (SYSTEMS_INDEX §25g); reads = memory only
_html_cache = {}

# Strings System (PR 3.6 · SYSTEMS_INDEX §59): admin overrides live in site_settings, loaded
# at startup + on admin save (never a DB call while serving a page). The inline block is
# rebuilt only when the overrides change.
# Actions Registry (PR 3.7 · SYSTEMS_INDEX §60) rides the same marker: its window.TW_ACTIONS
# block (registry + admin overrides) is appended to the strings block, before tw_shared.js.
_STRINGS_OVERRIDES: dict = {}
_ACTIONS_OVERRIDES: dict = {}
_STRINGS_BLOCK = tw_strings.page_block({}) + tw_actions.page_block({}) + tw_limits.page_block(tw_settings.limit)


def _strings_set_overrides(overrides: dict) -> None:
    global _STRINGS_OVERRIDES, _STRINGS_BLOCK
    _STRINGS_OVERRIDES = dict(overrides)
    _STRINGS_BLOCK = (tw_strings.page_block(_STRINGS_OVERRIDES) + tw_actions.page_block(_ACTIONS_OVERRIDES)
                      + tw_limits.page_block(tw_settings.limit))   # Input Limits (5.0h) — admin values (4.1)


# a settings change (this worker's save or the refresh loop) → window.TW_LIMITS rebuilt (task 4.1)
tw_settings.on_change(lambda: _strings_set_overrides(_STRINGS_OVERRIDES))


def _actions_set_overrides(overrides: dict) -> None:
    global _ACTIONS_OVERRIDES
    _ACTIONS_OVERRIDES = dict(overrides)
    _strings_set_overrides(_STRINGS_OVERRIDES)   # rebuild the shared page block


def _actions_load_overrides() -> None:
    """site_settings → in-memory action overrides. Failure → registry defaults (logged, F9)."""
    try:
        _actions_set_overrides(tw_actions.parse_stored(get_site_setting(tw_actions.SETTING_KEY)))
    except Exception as e:
        print(f"[actions] override load failed — defaults in use: {type(e).__name__}: {e}")


def _strings_load_overrides() -> None:
    """site_settings → in-memory overrides. Failure → defaults stay (logged, F9)."""
    try:
        _strings_set_overrides(tw_strings.parse_stored(get_site_setting(tw_strings.setting_key())))
    except Exception as e:
        print(f"[strings] override load failed — defaults in use: {type(e).__name__}: {e}")


def _tw_text(key: str, **vars) -> str:
    """Server-side twT: the Strings System text (admin override wins) with {vars} filled."""
    text = tw_strings.merged(_STRINGS_OVERRIDES).get(key) or key
    for k, v in vars.items():
        text = text.replace("{" + k + "}", str(v))
    return text


# ── Input Limits (task 5.0h — SYSTEMS_INDEX §54n) — values in tw_limits.py only ──
# Too long / bad value → 422 · flood → 429, both {ok:false, error:{code, message, field?}}
# with the message from twT `limits.*`. Rate buckets live on the shared _rate_store (_rate_hit).
def _limit_error(status: int, code: str, key: str, field: str = None, **vars) -> JSONResponse:
    return api_error(status, code, _tw_text(key, **vars), field)


def _too_long(value, limit_name: str, field: str):
    """None when value fits the limit (tw_settings.limit — admin value or LIMITS), else the 422 response."""
    max_len = tw_settings.limit(limit_name)
    if value is not None and len(value) > max_len:
        return _limit_error(422, "too_long", "limits.too_long", field, max=_fmt_number(max_len))
    return None


def _rate_ok(rate_name: str, who) -> bool:
    """Sliding window from tw_settings.rate(rate_name) (admin value or RATES) on _rate_store, key '{rate_name}:{who}'."""
    max_hits, window = tw_settings.rate(rate_name)
    return _rate_hit(f"{rate_name}:{who}", max_hits, window)


def _rate_limited() -> JSONResponse:
    return _limit_error(429, "rate_limited", "limits.rate_limited")


# ── Public Rate Limit (task 6 — SYSTEMS_INDEX §54o · ARCHITECTURE.md §80) ──
# Every route that works for a guest (no auth, or optional auth) carries
# dependencies=[Depends(_public_rate)] — or is listed in PUBLIC_RATE_EXEMPT with its reason
# (tests/test_public_rate_limit.py walks app.routes). One bucket per client IP (get_client_ip only)
# on the shared _rate_store, value tw_settings.rate("public_ip") (admin-editable, sec_public).
# Over it → 429 + Retry-After: API → {ok:false, error:{code:"rate_limited"}} · HTML route → a small page.
from html import escape as _html_escape, unescape as _html_unescape


class PublicRateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after


def _public_rate(request: Request):
    max_hits, window = tw_settings.rate("public_ip")
    retry = _rate_hit_retry("public_ip:" + get_client_ip(request), max_hits, window)
    if retry:
        raise PublicRateLimited(retry)


_PUBLIC_RATE_HTML = ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
                     '<meta name="viewport" content="width=device-width,initial-scale=1">'
                     '<meta name="robots" content="noindex"><title>{text}</title></head>'
                     '<body><p>{text}</p></body></html>')


@app.exception_handler(PublicRateLimited)
async def public_rate_limited_handler(request, exc):
    rc = getattr(request.scope.get("route"), "response_class", None)
    if isinstance(rc, type) and issubclass(rc, HTMLResponse):
        resp = HTMLResponse(_PUBLIC_RATE_HTML.format(text=_html_escape(_tw_text("limits.rate_limited"))), status_code=429)
    else:
        resp = _rate_limited()
    resp.headers["Retry-After"] = str(exc.retry_after)
    return resp


_EXEMPT_STATIC = "static file / page from memory — no DB"
_EXEMPT_AUTH_RATE = "already limited per IP: _RATE_LIMITED_PATHS (+ login locks / pwreset / sec_otp)"
PUBLIC_RATE_EXEMPT = {
    **{p: _EXEMPT_STATIC for p in (
        "/", "/landing.html", "/index.html", "/login", "/login.html", "/home",
        "/profile-showcase", "/profile-showcase.html", "/edu-profile", "/edu-profile.html",
        "/notifications", "/notifications.html", "/messages", "/messages.html",
        "/job-detail", "/job-detail.html", "/admin-job", "/admin-job.html", "/admin-view", "/admin-view.html",
        "/settings", "/settings.html", "/reset-password", "/privacy", "/terms", "/confirm-email",
        "/staff/invite", "/staff/mfa-reset", "/staff/password-reset",
        "/appointments", "/appointment-room",
        "/tw-ctrl-" + ADMIN_URL_TOKEN, "/tw-ctrl-" + ADMIN_URL_TOKEN + "/email",
        "/tw-ctrl-" + ADMIN_URL_TOKEN + "/settings", "/tw-ctrl-" + ADMIN_URL_TOKEN + "/content",
        "/support", "/support/track", "/tw-ctrl-" + ADMIN_URL_TOKEN + "/support",
        "/tw-ctrl-" + ADMIN_URL_TOKEN + "/staff",
        "/sitemap.xml", "/robots.txt", "/tw_shared.js", "/sw.js", "/manifest.json", "/theme.css",
        "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png", "/favicon.ico",
        "/static/{filename:path}")},
    "/u": "always 404 — no DB",
    "/health": "health check (Railway) — must never be refused",
    "/ping": "health check — must never be refused",
    "/log/error": "own per-IP bucket log-error (rate_limit_middleware)",
    **{p: _EXEMPT_AUTH_RATE for p in (
        "/auth/register", "/auth/login", "/auth/password-reset/request", "/auth/password-reset/confirm",
        "/auth/email-change/confirm", "/tw-ctrl-" + ADMIN_URL_TOKEN + "/login")},
    **{p: "own atomic per-IP + per-link / per-email reservation (RATES staff_link_* / staff_forgot_*) — task 8.4c-2a2"
       for p in ("/staff/invite/start", "/staff/invite/complete", "/staff/mfa-reset/start",
                 "/staff/mfa-reset/complete", "/staff/password-reset/complete",
                 "/tw-ctrl-" + ADMIN_URL_TOKEN + "/forgot")},
}


def _fmt_number(n: int) -> str:
    """Thousands separator like twFormatNumber (task 5.3a3) — for numbers inside server texts."""
    return f"{int(n):,}"


# Unified Email System (task 5.1a · SYSTEMS_INDEX §54j): email_service.send_email is the only
# sender. Its texts are Strings System keys (email.*) — same merged dict as the pages — and its
# settings (sender, site URL, per-type on/off) live in site_settings, loaded at startup + on save.
import email_service
email_service.set_strings_provider(lambda: tw_strings.merged(_STRINGS_OVERRIDES))
ad.set_strings_provider(lambda: tw_strings.merged(_STRINGS_OVERRIDES))   # «حساب محذوف» + the deletion notice
# 5.1c — every attempt → email_send_log; notification emails pass the gate (prefs · throttle · caps).
email_service.set_send_hooks(reserve=email_notify_reserve, log=email_log_write)


def _email_load_settings() -> None:
    """site_settings → email settings. Failure → defaults stay (logged, F9)."""
    try:
        email_service.set_settings(email_service.parse_stored(get_site_setting(email_service.SETTING_KEY)))
    except Exception as e:
        print(f"[email] settings load failed — defaults in use: {type(e).__name__}")


def read_html(name: str) -> str:
    return _read_html_cached(name).replace(tw_strings.MARKER, _STRINGS_BLOCK, 1)


def _read_html_cached(name: str) -> str:
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

def check_admin_session(request: Request) -> dict:
    """The admin session gate WITHOUT a perm (task 8.4c-1) — the same checks check_admin runs: a valid admin JWT
    in X-Admin-Token + the session re-read from the DB (owner sv · staff row active + MFA bound + sv), → the claims
    with the effective perms (owner ["*"] · staff from the DB). 503 / 401 / 403 exactly as check_admin.
    ONLY admin_me and admin_step_up call it (admin_perms.UNGUARDED_ROUTES "session-only") — every other admin
    route goes through check_admin(request, perm)."""
    if not _admin_jwt_secret_ok():
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    claims = _admin_jwt_claims(request.headers.get("X-Admin-Token", ""))
    if not claims:
        raise HTTPException(status_code=401, detail=_ADMIN_SESSION_OVER)
    role = claims.get("role")
    if role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Forbidden")
    live = _admin_live_session(claims)
    if live is None or not isinstance(claims.get("sv"), int) or live["sv"] != claims["sv"]:
        raise HTTPException(status_code=401, detail=_ADMIN_SESSION_OVER)
    if live["perms"] is not None:
        claims = dict(claims, perms=sorted(live["perms"]), name=live.get("name") or "")
    return claims


def check_admin(request: Request, perm: str) -> dict:
    """Admin gate — accepts ONLY a valid admin JWT (from the admin login, <panel>/login) in X-Admin-Token.
    The raw ADMIN_TOKEN is the login password, never a session token.
    503 = ADMIN_JWT_SECRET not configured · 401 = missing / invalid / expired token
    (admin pages send the admin back to the login screen) · 403 = valid token without
    the role / permission. `perm` is required and must be in admin_perms.ALL (task 8.4a — else
    RuntimeError = programming error); an admin_perms.OWNER_ONLY perm passes only with "*".
    Task 8.4b — the session is re-read on EVERY request: owner → token sv = admin_owner_mfa.session_version ·
    staff ("staff:<id>") → admin_staff row active + MFA bound + sv equal, and the perms are the effective
    ones from the DB (admin_staff.staff_session), never the token's. No match → 401. The returned claims
    carry those perms (so _admin_contacts decides on the same set) — check_admin_session does all of that.
    Task 8.4c-1 — an OWNER_ONLY perm on a write (POST/PUT/PATCH/DELETE) or a route in _STEP_UP_READ_ROUTES
    (the CSV export) also needs a valid X-Admin-Stepup grant for this token + sv → else 428 step_up_required."""
    admin_perms.require_known(perm)
    claims = check_admin_session(request)
    if not admin_perms.allows(claims.get("perms") or [], perm):
        raise HTTPException(status_code=403, detail="Forbidden")
    if _step_up_needed(request, perm) and not _admin_step_up_ok(request, claims):
        raise HTTPException(status_code=428, detail="step_up_required")
    return claims


# ── Step-up (task 8.4c-1 · docs/rules/admin-staff.md rule 11) ──
# POST /admin/step-up (owner, a fresh authenticator / recovery code) → a 5-minute grant sent as X-Admin-Stepup.
# Signed with ADMIN_JWT_SECRET, own aud → never an admin token / ticket (and they are never a grant). Bound to the
# admin token it was asked with (tok = SHA-256 of it) + sv. Accepted for any number of requests until exp.
_ADMIN_STEPUP_AUD = "tw-admin-stepup"
_ADMIN_STEPUP_TTL = 300
_STEP_UP_READ_ROUTES = frozenset({"admin_users_export"})   # reads that still need it (data leaving the site)


def _step_up_needed(request: Request, perm: str) -> bool:
    if perm not in admin_perms.OWNER_ONLY:
        return False
    if request.method in _AUDIT_WRITE_METHODS:
        return True
    route = request.scope.get("route") if isinstance(getattr(request, "scope", None), dict) else None
    return getattr(route, "name", "") in _STEP_UP_READ_ROUTES


def _admin_token_digest(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _admin_step_up_issue(sub: str, sv: int, admin_token: str) -> str:
    import time, secrets
    now = int(time.time())
    return _jwt_sign({"iss": _ADMIN_JWT_ISS, "aud": _ADMIN_STEPUP_AUD, "typ": "step_up", "sub": sub, "sv": int(sv),
                      "tok": _admin_token_digest(admin_token), "iat": now, "exp": now + _ADMIN_STEPUP_TTL,
                      "jti": secrets.token_hex(12)}, ADMIN_JWT_SECRET)


def _admin_step_up_ok(request: Request, claims: dict) -> bool:
    """X-Admin-Stepup is a live grant for THIS admin token (tok) + subject + sv."""
    grant = request.headers.get("X-Admin-Stepup", "")
    if not grant or not isinstance(grant, str):
        return False
    c = _jwt_verify(grant, ADMIN_JWT_SECRET)
    if (not c or c.get("iss") != _ADMIN_JWT_ISS or c.get("aud") != _ADMIN_STEPUP_AUD or c.get("typ") != "step_up"
            or c.get("sub") != claims.get("sub") or not isinstance(c.get("sv"), int) or c["sv"] != claims.get("sv")
            or not isinstance(c.get("tok"), str)):
        return False
    try:
        if int(c["exp"]) - int(c["iat"]) > _ADMIN_STEPUP_TTL:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return hmac.compare_digest(c["tok"], _admin_token_digest(request.headers.get("X-Admin-Token", "")))


_ADMIN_SESSION_OVER = "انتهت جلسة الإدارة، سجّل الدخول من جديد"


def _admin_live_session(claims: dict):
    """{sv, perms} from the DB for this admin token (perms None = keep the token's — the owner), or None.
    role "staff" → sub must be "staff:<id>" · role "admin" → the owner's session_version. DB down → 503."""
    try:
        if claims.get("role") == "staff":
            sid = admin_staff.staff_id(claims.get("sub"))
            return admin_staff.staff_session(sid) if sid is not None else None
        return {"sv": admin_staff.owner_session_version(), "perms": None}
    except Exception as e:
        print(f"[admin-auth] session read failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


def _admin_email_view(claims: dict) -> bool:
    """users.email.view (task 8.4a) — without it no admin response carries a user email and no search matches one."""
    return admin_perms.allows(claims.get("perms"), admin_perms.EMAIL_VIEW)


def _admin_contacts(claims: dict, data):
    """Every admin reply that can carry a user's email / phone goes through here (task 8.4a / 8.4a2):
    email keys need users.email.view, phone keys users.phone.view — independent ("*" = both)."""
    perms = claims.get("perms")
    return admin_perms.strip_contacts(data, admin_perms.allows(perms, admin_perms.EMAIL_VIEW),
                                      admin_perms.allows(perms, admin_perms.PHONE_VIEW))


def _migrate_feed_indexes():
    """Create feed query indexes (idempotent — CREATE INDEX IF NOT EXISTS).
    These indexes support the /home/feed endpoint for production scale.
    """
    conn = get_conn()
    try:
        conn.run("CREATE INDEX IF NOT EXISTS idx_jobs_status_created     ON jobs(status, created_at DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_cposts_created          ON company_posts(created_at DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_news_status_created     ON news_posts(status, created_at DESC)")
        # task 8.6d-1 — keyset paging (created_at, id) ↓
        conn.run("CREATE INDEX IF NOT EXISTS idx_cposts_created_id       ON company_posts(created_at DESC, id DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_news_created_id         ON news_posts(created_at DESC, id DESC)")
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
        # phase 5a — display window (docs/migrations/5a_news_schedule.sql, applied by hand first)
        conn.run("ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ NULL")
        conn.run("ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ NULL")
        conn.run("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint
                               WHERE conname = 'news_posts_window_chk'
                                 AND conrelid = 'news_posts'::regclass) THEN
                    ALTER TABLE news_posts ADD CONSTRAINT news_posts_window_chk
                        CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at);
                END IF;
            END $$
        """)
    finally:
        release_conn(conn)


# Active news (phase 5a) — the ONE rule, used by /home/feed and /news/banner.
NEWS_ACTIVE_SQL = ("status = 'published' AND (starts_at IS NULL OR starts_at <= NOW()) "
                   "AND (ends_at IS NULL OR ends_at > NOW())")

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


# ── Feed pagination (task 8.6d-1 — SYSTEMS_INDEX §12 · docs/rules/home-v2.md) ─────────────────────────
#   jobs  → match score ↓ · created_at ↓ · id ↓ over EVERY active job, ranked once on the first page and saved
#           as a list (feed_snapshots.job_ids); later pages walk the list by offset and re-check each batch
#           (job_active_sql + bs.active_sql) — removed jobs drop out, nothing repeats, nothing is skipped.
#   posts / news → keyset (created_at, id) ↓ with created_at <= as_of (new content waits for a refresh).
#   «all" → one fixed pattern per page (job, post, news, …); an exhausted type's slot goes to the others.
#   cursor → base64url(JSON) + HMAC-SHA256 (key derived from JWT_SECRET, label feed_cursor) — 422 invalid_cursor ·
#           a missing / expired list or a changed match profile (fp) → 409 feed_reset.
_FEED_TYPES = {"all": ("opportunity", "post", "news"), "opportunities": ("opportunity",),
               "posts": ("post",), "news": ("news",)}
_FEED_JOB_COLS = [
    "id","title","location","job_type","salary_min","salary_max","currency",
    "skills","created_at","profession_id","category",
    "salary_hidden","accepts_all_professions",
    "company_name","company_tw_id","company_id","company_logo",
    "profession_name_ar","profession_name_en","profession_icon",
    "profession_category_group",
]
_FEED_JOB_WHERE = job_active_sql("j") + " AND " + bs.active_sql("j.company_id")


class _FeedError(Exception):
    """422 invalid_cursor · 409 feed_reset → api_error."""
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status, self.code = status, code


def _migrate_feed_snapshots():
    """Saved job order of a feed session (task 8.6d-1) — optional: failure → first page only (next_cursor null)."""
    conn = get_conn()
    try:
        conn.run("""
            CREATE TABLE IF NOT EXISTS feed_snapshots (
                id         TEXT PRIMARY KEY,
                user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filter     TEXT NOT NULL,
                job_ids    BIGINT[] NOT NULL DEFAULT '{}',
                fp         TEXT NOT NULL,
                as_of      TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.run("CREATE INDEX IF NOT EXISTS idx_feed_snapshots_user ON feed_snapshots(user_id, created_at DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS idx_feed_snapshots_created ON feed_snapshots(created_at)")
    finally:
        release_conn(conn)


def _feed_fp(u_pid, u_pgroup, u_skills) -> str:
    """Fingerprint of the user data the match score reads (profession · category group · skills)."""
    raw = json.dumps([u_pid, u_pgroup or None, sorted(u_skills or ())], ensure_ascii=False, separators=(",", ":"))
    return hmac.new(b"tw:feed_fp", raw.encode(), "sha256").hexdigest()[:32]


def _feed_b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _feed_cursor_sig(body: str) -> str:
    key = hmac.new(JWT_SECRET.encode(), b"tw:feed_cursor", "sha256").digest()
    return _feed_b64e(hmac.new(key, body.encode(), "sha256").digest())


def _feed_cursor_encode(payload: dict) -> str:
    body = _feed_b64e(json.dumps(payload, separators=(",", ":")).encode())
    return body + "." + _feed_cursor_sig(body)


def _feed_key_ok(k) -> bool:
    return k is None or (isinstance(k, list) and len(k) == 2 and isinstance(k[0], str)
                         and isinstance(k[1], int) and not isinstance(k[1], bool) and k[1] > 0)


def _feed_cursor_decode(cursor: str, uid: int, filter: str) -> dict:
    import binascii
    """Signed, same account, same filter, not expired, right shape — else 422 invalid_cursor."""
    try:
        body, sig = cursor.split(".")
        if len(cursor) > 4096 or not hmac.compare_digest(sig, _feed_cursor_sig(body)):
            raise ValueError("signature")
        c = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        needs_jobs = "opportunity" in _FEED_TYPES[filter]
        ok = (isinstance(c, dict) and c.get("v") == 1 and c.get("uid") == uid and c.get("f") == filter
              and isinstance(c.get("exp"), int) and c["exp"] > int(time.time())
              and isinstance(c.get("jo"), int) and c["jo"] >= 0
              and _feed_key_ok(c.get("pk")) and _feed_key_ok(c.get("nk"))
              and isinstance(c.get("fp"), str) and isinstance(c.get("as_of"), str)
              and (isinstance(c.get("sid"), str) if needs_jobs else c.get("sid") is None))
        if not ok:
            raise ValueError("shape")
        datetime.fromisoformat(c["as_of"])
        for k in (c["pk"], c["nk"]):
            if k:
                datetime.fromisoformat(k[0])
        return c
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error):
        raise _FeedError(422, "invalid_cursor")


def _feed_rank_jobs(conn, u_pid, u_pgroup, u_skills) -> list:
    """Every active job → ids by match ↓ · created_at ↓ · id ↓ (_taxonomy_score, unchanged)."""
    rows = conn.run(
        """SELECT j.id, j.created_at, j.profession_id, j.category, j.skills,
                  COALESCE(j.accepts_all_professions, false),
                  COALESCE(pc.category_group, ''),
                  ARRAY(SELECT jpt.profession_id FROM job_profession_targets jpt WHERE jpt.job_id = j.id)
           FROM jobs j
           JOIN users u ON j.company_id = u.id
           LEFT JOIN profession_categories pc ON j.profession_id = pc.id
           WHERE """ + _FEED_JOB_WHERE)
    ranked = []
    for jid, created, pid, cat, skills, acc_all, pgroup, acc in (rows or []):
        job = {"profession_id": pid, "category": cat, "skills": skills or [],
               "accepts_all_professions": acc_all, "profession_category_group": pgroup}
        score = _taxonomy_score(job, u_pid, u_pgroup, u_skills, set(acc or ()))
        ranked.append((score, created or datetime.min, int(jid)))
    ranked.sort(reverse=True)
    return [r[2] for r in ranked]


def _feed_save_snapshot(conn, user_id, filter, job_ids, fp, as_of):
    """Insert the list (cleanup first: expired rows + this user's oldest past the cap). Failure → None + log."""
    try:
        ttl = tw_settings.limit("feed_snapshot_ttl_min")
        keep = tw_settings.limit("feed_snapshots_per_user") - 1
        conn.run("DELETE FROM feed_snapshots WHERE created_at < NOW() - make_interval(mins => :ttl)", ttl=ttl)
        conn.run("DELETE FROM feed_snapshots WHERE id IN (SELECT id FROM feed_snapshots WHERE user_id = :u "
                 "ORDER BY created_at DESC, id OFFSET :keep)", u=user_id, keep=keep)
        sid = secrets.token_urlsafe(24)
        conn.run("INSERT INTO feed_snapshots (id, user_id, filter, job_ids, fp, as_of) "
                 "VALUES (:id, :u, :f, CAST(:ids AS BIGINT[]), :fp, CAST(:as_of AS TIMESTAMPTZ))",
                 id=sid, u=user_id, f=filter, ids=job_ids, fp=fp, as_of=as_of)
        return sid
    except Exception as e:
        print(f"[home_feed] snapshot insert failed (first page only, no cursor): {type(e).__name__}: {e}")
        return None


def _feed_load_snapshot(conn, sid, user_id, filter, fp) -> list:
    rows = conn.run("SELECT user_id, filter, fp, job_ids, "
                    "created_at >= NOW() - make_interval(mins => :ttl) FROM feed_snapshots WHERE id = :sid",
                    sid=sid, ttl=tw_settings.limit("feed_snapshot_ttl_min"))
    if not rows:
        raise _FeedError(409, "feed_reset")
    owner, f, saved_fp, job_ids, fresh = rows[0]
    if int(owner) != user_id or f != filter:
        raise _FeedError(422, "invalid_cursor")
    if not fresh or saved_fp != fp:
        raise _FeedError(409, "feed_reset")
    return [int(j) for j in (job_ids or [])]


def _feed_job_items(conn, ids) -> dict:
    """Jobs by id that are still active (re-checked now) → {id: item}."""
    rows = conn.run(
        """SELECT j.id, j.title, j.location, j.job_type,
                  j.salary_min, j.salary_max, j.currency,
                  j.skills, j.created_at,
                  j.profession_id, j.category,
                  COALESCE(j.salary_hidden, false)           AS salary_hidden,
                  COALESCE(j.accepts_all_professions, false) AS accepts_all_professions,
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
           WHERE j.id = ANY(CAST(:ids AS BIGINT[])) AND """ + _FEED_JOB_WHERE,
        ids=ids,
    )
    out = {}
    for r in (rows or []):
        d = dict(zip(_FEED_JOB_COLS, r))
        d["type"] = "opportunity"
        d["opp_type"] = "job"
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        if isinstance(d.get("skills"), list):
            d["skills"] = [str(s) for s in d["skills"]]
        if d["salary_hidden"]:   # hidden salary never leaves the server (old rows may still hold numbers)
            d["salary_min"] = d["salary_max"] = d["currency"] = None
        d.pop("category", None)    # internal field; profession_* is the public form
        out[int(d["id"])] = d
    return out


def _feed_take_jobs(conn, ids, offset, n) -> list:
    """Walk the saved list from offset: still-active jobs in list order until n found or the list ends →
    [(list index, item)]. Batches re-checked against the DB; removed ones are skipped."""
    out, pos = [], offset
    while len(out) < n and pos < len(ids):
        chunk = ids[pos:pos + max(n - len(out), 20)]
        found = _feed_job_items(conn, chunk)
        for i, jid in enumerate(chunk):
            if jid in found and len(out) < n:
                out.append((pos + i, found[jid]))
        pos += len(chunk)
    return out


def _feed_posts(conn, user_id, as_of, key, n) -> list:
    where, params = "", {}
    if key:
        where = " AND (cp.created_at, cp.id) < (CAST(:k_at AS TIMESTAMPTZ), :k_id)"
        params = {"k_at": key[0], "k_id": key[1]}
    rows = conn.run(
        """SELECT cp.id, cp.body, cp.tags, cp.created_at,
                  cp.theme_color, cp.comments_enabled,
                  u.full_name AS author_name,
                  u.tw_id    AS author_tw_id,
                  u.id       AS author_id,
                  COALESCE(p.avatar_url,'') AS author_avatar
           FROM company_posts cp
           JOIN users u ON cp.company_id = u.id
           LEFT JOIN profiles p ON cp.company_id = p.user_id
           WHERE """ + bs.visible_sql("cp.company_id") + """
             AND cp.created_at <= CAST(:as_of AS TIMESTAMPTZ)""" + where + """
           ORDER BY cp.created_at DESC, cp.id DESC
           LIMIT :n""",
        bs_viewer=user_id, as_of=as_of, n=n, **params)
    cols = ["id","body","tags","created_at","theme_color","comments_enabled",
            "author_name","author_tw_id","author_id","author_avatar"]
    out = []
    for r in (rows or []):
        d = dict(zip(cols, r))
        d["type"] = "post"
        d["author_type"] = "co"   # company_posts are company posts only (avatar shape)
        d["_key"] = [d["created_at"].isoformat(), int(d["id"])]
        d["created_at"] = d["created_at"].isoformat()
        if isinstance(d.get("tags"), list):
            d["tags"] = [str(t) for t in d["tags"]]
        out.append(d)
    return out


def _feed_news(conn, as_of, key, n) -> list:
    # NEWS_ACTIVE_SQL + nothing that started after as_of (a scheduled item is «new" when it starts)
    where, params = "", {}
    if key:
        where = " AND (created_at, id) < (CAST(:k_at AS TIMESTAMP), :k_id)"
        params = {"k_at": key[0], "k_id": key[1]}
    rows = conn.run(
        """SELECT id, title, summary, body, category, country, source_url, created_at
           FROM news_posts
           WHERE """ + NEWS_ACTIVE_SQL + """
             AND created_at <= CAST(:as_of AS TIMESTAMPTZ)
             AND (starts_at IS NULL OR starts_at <= CAST(:as_of AS TIMESTAMPTZ))""" + where + """
           ORDER BY created_at DESC, id DESC
           LIMIT :n""",
        as_of=as_of, n=n, **params)
    cols = ["id","title","summary","body","category","country","source_url","created_at"]
    out = []
    for r in (rows or []):
        d = dict(zip(cols, r))
        d["type"] = "news"
        d["_key"] = [d["created_at"].isoformat(), int(d["id"])]
        d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


@app.get("/home/feed")
def home_feed(filter: str = "all", limit: int = 20, cursor: Optional[str] = None, token=Depends(verify_token)):
    user_id   = int(token.get("user_id") or 0)
    user_type = token.get("user_type", "emp")
    if not user_id:
        raise HTTPException(401, "رمز غير صالح")

    if filter not in _FEED_TYPES:
        filter = "all"
    lim = min(max(int(limit), 1), tw_settings.limit("feed_page_max"))
    types = _FEED_TYPES[filter]
    try:
        c = _feed_cursor_decode(cursor, user_id, filter) if cursor else None
    except _FeedError as e:
        return api_error(e.status, e.code, _tw_text("feed.err." + e.code))

    conn = get_conn()
    try:
        # ── User context for taxonomy-aware scoring ────────────────────────────
        u_pid, u_pgroup, u_skills = _feed_user_context(conn, user_id, user_type)
        fp = _feed_fp(u_pid, u_pgroup, u_skills)
        job_ids, sid = [], None
        if c is None:
            as_of = conn.run("SELECT NOW()")[0][0].isoformat()
            exp = int(time.time()) + tw_settings.limit("feed_snapshot_ttl_min") * 60
            c = {"jo": 0, "pk": None, "nk": None}
            if "opportunity" in types:
                job_ids = _feed_rank_jobs(conn, u_pid, u_pgroup, u_skills)
                sid = _feed_save_snapshot(conn, user_id, filter, job_ids, fp, as_of)
            pageable = sid is not None or "opportunity" not in types
        else:
            as_of, exp, sid = c["as_of"], c["exp"], c["sid"]
            if sid is not None:
                try:
                    job_ids = _feed_load_snapshot(conn, sid, user_id, filter, fp)
                except _FeedError as e:
                    return api_error(e.status, e.code, _tw_text("feed.err." + e.code))
            pageable = True

        # n = lim + 1 per type: a leftover after the page = that type has more
        n = lim + 1
        buf = {}
        if "opportunity" in types:
            buf["opportunity"] = _feed_take_jobs(conn, job_ids, c["jo"], n)
        if "post" in types:
            buf["post"] = [(None, d) for d in _feed_posts(conn, user_id, as_of, c["pk"], n)]
        if "news" in types:
            buf["news"] = [(None, d) for d in _feed_news(conn, as_of, c["nk"], n)]

        # Fixed pattern (job, post, news, …) — an exhausted type's slot goes to the next type
        page, nxt, i = [], {t: 0 for t in types}, 0
        while len(page) < lim and any(nxt[t] < len(buf[t]) for t in types):
            t = types[i % len(types)]
            i += 1
            if nxt[t] < len(buf[t]):
                page.append(buf[t][nxt[t]])
                nxt[t] += 1

        items = [d for _, d in page]
        posts = [d for d in items if d["type"] == "post"]
        if posts:   # card fields for TwPostCard (task 8.6b-2) — one batched query, same source as /company/posts
            stats = get_company_post_stats(conn, [d["id"] for d in posts], user_id)
            for d in posts:
                d.update(stats[int(d["id"])])
        jobs = [d for d in items if d["type"] == "opportunity"]
        if jobs:    # batch-fetch accepted professions — single query, no N+1
            acc_map = _fetch_accepted_professions_batch(conn, [d["id"] for d in jobs])
            for d in jobs:
                d["accepted_professions"] = acc_map.get(d["id"], [])
    finally:
        release_conn(conn)

    more = any(nxt[t] < len(buf[t]) for t in types)
    next_cursor = None
    if more and pageable:
        jo, pk, nk = c["jo"], c["pk"], c["nk"]
        for idx, d in page:
            if d["type"] == "opportunity":
                jo = idx + 1
            elif d["type"] == "post":
                pk = d["_key"]
            else:
                nk = d["_key"]
        next_cursor = _feed_cursor_encode({"v": 1, "uid": user_id, "f": filter, "sid": sid, "jo": jo,
                                           "pk": pk, "nk": nk, "as_of": as_of, "fp": fp, "exp": exp})
    for d in items:
        d.pop("_key", None)
    return {"items": items, "filter": filter, "total": len(items), "next_cursor": next_cursor}


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
                      response_class=HTMLResponse, include_in_schema=False,
                      dependencies=[Depends(_public_rate)])   # ?id= → DB lookup (task 6 — §54o)

@app.get("/profile-showcase", response_class=HTMLResponse)
def profile_showcase(): return read_html("profile-showcase.html")

@app.get("/profile-showcase.html", response_class=HTMLResponse)
def profile_showcase_html(): return read_html("profile-showcase.html")

@app.get("/u", response_class=HTMLResponse)
def public_profile_no_id():
    """Bare /u without a tw_id — return 404 rather than an empty profile."""
    raise HTTPException(status_code=404, detail="معرف الحساب مفقود")

@app.get("/u/{tw_id}", response_class=HTMLResponse, dependencies=[Depends(_public_rate)])
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
    if not info or bs.is_suspended(int(info['id'])):   # suspended (task 5.4) = not found
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


@app.get("/company/profile/{company_id}", dependencies=[Depends(_public_rate)])
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
    _404_if_hidden(token_uid, resolved_id, "الشركة غير موجودة")

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
            "SELECT COUNT(*) FROM jobs j WHERE j.company_id = :cid AND " + job_active_sql("j"),
            cid=resolved_id
        )
        jobs_count = j_rows[0][0] if j_rows else 0

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

@app.get("/company/branches/{company_id}", dependencies=[Depends(_public_rate)])
def get_branches(company_id: int, request: Request):
    """Public — returns all branches for a company ordered by display_order.
    Hidden account (suspended / block either way) → 404 (task 5.4 rule)."""
    _404_if_hidden(_optional_viewer_id(request), company_id, "الشركة غير موجودة")
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

@app.get("/admin-job", response_class=HTMLResponse)
@app.get("/admin-job.html", response_class=HTMLResponse)
def admin_job_page(): return read_html("admin-job.html")   # one job for the admin (task 5.3j phase 4)

@app.get("/admin-view", response_class=HTMLResponse)
@app.get("/admin-view.html", response_class=HTMLResponse)
def admin_view(): return read_html("admin-view.html")


# Staff link pages (task 8.4c-2b-1 · docs/rules/admin-staff.md rule 15) — one HTML shell for the three one-time links
# of the emails (invite · authenticator reset · password reset). The token is in the URL fragment (#t=…) and never
# reaches the server here; the page sends it in the body of /staff/*/start|complete. No token / panel path in the HTML.
def _staff_link_page() -> HTMLResponse:
    resp = HTMLResponse(read_html("staff-link.html"))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.get("/staff/invite", response_class=HTMLResponse)
def staff_invite_page(): return _staff_link_page()


@app.get("/staff/mfa-reset", response_class=HTMLResponse)
def staff_mfa_reset_page(): return _staff_link_page()


@app.get("/staff/password-reset", response_class=HTMLResponse)
def staff_password_reset_page(): return _staff_link_page()

@app.get("/settings", response_class=HTMLResponse)
def settings(): return read_html("settings.html")

@app.get("/settings.html", response_class=HTMLResponse)
def settings_html(): return read_html("settings.html")

# Forgot password (task 5.1a) — request form; with #token=… (fragment: never sent to the
# server / logs / Referer) the new-password form.
@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(): return read_html("reset-password.html")

# Privacy policy + terms of use (task terms — SYSTEMS_INDEX §1d) — public, the version shown on
# the page is the one POST /auth/register stores (tw_terms.TERMS_VERSION).
def _legal_page(name: str) -> str:
    return (read_html(name)
            .replace("{{terms_version}}", tw_terms.TERMS_VERSION)
            .replace("{{contact_email}}", tw_terms.CONTACT_EMAIL))

@app.get("/privacy", response_class=HTMLResponse)
def privacy_page(): return _legal_page("privacy.html")

@app.get("/terms", response_class=HTMLResponse)
def terms_page(): return _legal_page("terms.html")

@app.get("/confirm-email", response_class=HTMLResponse)
def confirm_email_page(): return read_html("confirm-email.html")

@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN, response_class=HTMLResponse)
def admin_page(): return read_html("admin.html")

# Admin — email settings + usage (task 5.1c). Same secret path; data via check_admin endpoints.
@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN + "/email", response_class=HTMLResponse)
def admin_email_page(): return read_html("admin-email.html")

# Admin — unified settings (task 4.1). Same secret path; data via GET / PUT / POST /admin/settings.
@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN + "/settings", response_class=HTMLResponse)
def admin_settings_page(): return read_html("admin-settings.html")

# Admin — content screens (phase 5b): strings · colors · news. Data via /admin/strings ·
# /admin/theme/colors · /admin/news (content.edit — docs/rules/content-admin.md).
@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN + "/content", response_class=HTMLResponse)
def admin_content_page(): return read_html("admin-content.html")

# Admin — the owner's staff screen (task 8.4c-2b-2 · docs/rules/admin-staff.md rule 16). HTML only; data via
# GET /admin/staff · /admin/roles and the writes of rules 10 + 14 (staff.manage + step-up).
@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN + "/staff", response_class=HTMLResponse)
def admin_staff_page(): return read_html("admin-staff.html")

# Support tickets (task 7.1 — docs/rules/support.md): the account's page + the admin inbox.
@app.get("/support", response_class=HTMLResponse)
def support_page(): return read_html("support.html")

# Guest follow-up page (task 7.2a) — placeholder until its UI task; headers = security_headers (/support/track).
@app.get("/support/track", response_class=HTMLResponse)
def support_track_page(): return read_html("support-track.html")

@app.get("/tw-ctrl-" + ADMIN_URL_TOKEN + "/support", response_class=HTMLResponse)
def admin_support_page(): return read_html("admin-support.html")

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
    # Terms + privacy consent (task terms — SYSTEMS_INDEX §1d): must be exactly true; the
    # version stored is the server's tw_terms.TERMS_VERSION, never a value from the client.
    terms_accepted: Optional[bool] = None

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
    # Hard size limits (task 5.0e) — anything longer → 422, never stored or printed.
    msg: Optional[str] = Field(None, max_length=2000)
    file: Optional[str] = Field(None, max_length=500)
    line: Optional[int] = Field(None, ge=0, le=10_000_000)
    page: Optional[str] = Field(None, max_length=500)
    ua: Optional[str] = Field(None, max_length=300)
    type: Optional[str] = Field(None, max_length=20)
    ts: Optional[str] = Field(None, max_length=40)

class MessageInput(BaseModel):
    receiver_id: int
    content: str

class KYCEmailInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    email: str

class KYCCodeInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    code: str

    @field_validator("code")
    @classmethod
    def _six_digits(cls, v: str) -> str:
        # task 8.4c-0b — not exactly 6 digits (after strip) → 422 (form error shape); no attempt is used
        if not otp_code_valid(v):
            raise ValueError("invalid_code")
        return v.strip()

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
    status: str  # active, paused, closed (reopening a closed job = admin only — task 5.3j4)

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

class AdminLoginInput(BaseModel):
    # task 8.4b — step 1: {password} = owner · {email, password} = staff · step 2: {ticket, code}
    password: Optional[str] = Field(None, max_length=256)
    email: Optional[str] = Field(None, max_length=254)
    ticket: Optional[str] = Field(None, max_length=2048)
    code: Optional[str] = Field(None, max_length=64)

class AdminMessageInput(BaseModel):
    user_id: int
    subject: str
    message: str

# ══════════════════════════════════════════
# Health
# ══════════════════════════════════════════

@app.get("/sitemap.xml")
def sitemap():
    urls = [   # public pages only (task 5.0e — §54m); the login page is noindex
        "https://tawasolna.com/",
        "https://tawasolna.com/privacy",
        "https://tawasolna.com/terms",
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

# ── DS-COLOR admin override (PR 3.8 · COLOR-SYSTEM.md CLR-36 · SYSTEMS_INDEX §50) ──
# site_settings[theme_color_tokens] (JSON {token: color}) → one :root{} block served at
# /theme.css, loaded by the shell head right after tw_shared.css. No override → empty body.
# Per-process cache (60s) so a page view never hits the DB; a save clears this process's
# cache, other workers pick it up within the TTL. ETag → 304 (NoCacheMiddleware forces
# revalidation on every .css).
import theme_tokens as _theme
_THEME_CSS_TTL = 60
_theme_css_cache = {"css": None, "etag": "", "at": 0.0}

def _theme_css() -> tuple:
    c = _theme_css_cache
    now = time.monotonic()
    if c["css"] is not None and now - c["at"] < _THEME_CSS_TTL:
        return c["css"], c["etag"]
    css = ""
    try:
        css = _theme.render_css(_theme.parse_stored(get_site_setting(_theme.THEME_SETTING_KEY)))
    except Exception as e:
        print(f"[theme] stored color overrides unreadable — serving defaults: {e!r}")
    etag = _theme.css_etag(css)
    c.update(css=css, etag=etag, at=now)
    return css, etag

@app.get("/theme.css", include_in_schema=False)
def theme_css(request: Request):
    css, etag = _theme_css()
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=css, media_type="text/css", headers=headers)

@app.get("/admin/theme/colors")
def admin_theme_colors_get(request: Request):
    """Admin: saved color overrides + the editable token names (CLR-36 · phase 5a: EDITABLE only)."""
    check_admin(request, CONTENT_PERM)
    try:
        overrides = _theme.parse_stored(get_site_setting(_theme.THEME_SETTING_KEY))
    except Exception as e:
        raise _server_error("admin_theme_colors_get", e)
    return api_ok({"overrides": overrides, "tokens": list(_theme.EDITABLE),
                   "defaults": _theme.editable_defaults()})   # phase 5b — the screen's «رجّع للافتراضي» preview

@app.put("/admin/theme/colors")
def admin_theme_colors_put(request: Request, data: dict = Body(...)):
    """Admin: set the EDITABLE tokens — body {"overrides": {token: "#rrggbb"}}; an EDITABLE token
    left out = back to its default. Any other token / not #RRGGBB → 400 (all-or-nothing).
    Older stored overrides of other tokens are kept as they are (phase 5a — no data deleted)."""
    claims = check_admin(request, CONTENT_PERM)
    clean, errors = _theme.validate_editable(data.get("overrides"))
    if errors:
        e = errors[0]
        return api_error(400, e["code"], e["message"], e["field"])
    try:
        stored = _theme.parse_stored(get_site_setting(_theme.THEME_SETTING_KEY))
    except Exception as e:
        raise _server_error("admin_theme_colors_put", e)
    merged = {k: v for k, v in stored.items() if k not in _theme.EDITABLE}
    merged.update(clean)
    changed = sorted(k for k in _theme.EDITABLE if stored.get(k) != clean.get(k))
    request.state.audit_target = "tokens=" + (",".join(changed) or "-")
    ensure_site_settings_table()
    if not set_site_setting(_theme.THEME_SETTING_KEY, json.dumps(merged, sort_keys=True)):
        return api_error(500, "save_failed", "تعذّر حفظ الألوان، حاول مرة أخرى")
    _theme_css_cache["css"] = None
    print(f"[theme] color overrides saved by admin sub={claims.get('sub')!r} tokens={changed}")
    return api_ok({"overrides": merged})

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
    filename, mime = _APP_ICON_FILES[_req_path(request)]
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


async def _ws_peer_hidden_async(a: int, b: int) -> bool:
    """task 5.4c — a block either way (or a suspended peer) between a and b: the same rule as sending a
    message (bs.visible_sql via bs.is_hidden). Never cached — a block applies at once. Error → hidden."""
    try:
        return await asyncio.to_thread(bs.is_hidden, a, b)
    except Exception as exc:
        print(f"[WS-SEC] peer_hidden_error pair=({min(a,b)},{max(a,b)}): {type(exc).__name__}")
        return True  # fail closed


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
        self._loop = None   # the event loop the sockets live on (set by register)

    def register(self, user_id: int, ws: WebSocket) -> bool:
        """Register a WebSocket AFTER JWT auth succeeds. Returns False if limit exceeded."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass   # called outside the loop (sync caller) — keep the last known loop
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

    async def close_user(self, user_id: int, code: int) -> int:
        """Session revoked → close every socket of user_id. Detached first, so nothing
        reaches them after this call. Returns how many sockets were closed."""
        conns = self.active.pop(user_id, None) or []
        self.active_conversations.pop(user_id, None)
        self._conv_ws_owner.pop(user_id, None)
        _ws_cleanup_typing_log(user_id)
        for ws in conns:
            try:
                await ws.close(code=code)
            except Exception as e:
                print(f"[WS] close_user uid={user_id} close failed: {type(e).__name__}")
        return len(conns)

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

# ── WS Session Revocation (PR 4.0) ──
# Whatever ends a user's sessions (password change · admin password reset · account
# deleted) also closes that user's open /ws/{uid} sockets at once with 4008. 4008 is
# NOT in the 4001–4007 no-reconnect range: the client reconnects and re-authenticates —
# the device that holds the fresh JWT gets back in, older JWTs get 4001 and stop.
_WS_CLOSE_SESSION_REVOKED = 4008

def _ws_revoke_user(user_id: int, reason: str) -> int:
    """Close every open WS of user_id (this process — Procfile runs one worker).
    Callable from sync endpoints (threadpool) and from the event loop itself."""
    uid = int(user_id)
    loop = ws_manager._loop
    if loop is None or uid not in ws_manager.active:
        return 0
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:   # already on the loop — cannot block on it
        loop.create_task(ws_manager.close_user(uid, _WS_CLOSE_SESSION_REVOKED))
        print(f"[WS] REVOKE uid={uid} reason={reason} (scheduled)")
        return 0
    try:
        n = asyncio.run_coroutine_threadsafe(
            ws_manager.close_user(uid, _WS_CLOSE_SESSION_REVOKED), loop).result(timeout=5)
    except Exception as e:
        print(f"[WS] REVOKE uid={uid} reason={reason} failed: {type(e).__name__}: {e}")
        return 0
    print(f"[WS] REVOKE uid={uid} reason={reason} closed={n}")
    return n


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
                    if await _ws_peer_hidden_async(auth_uid, other_id):
                        continue  # block either way → dropped silently (task 5.4c)
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
                    if await _ws_peer_hidden_async(auth_uid, to_id):
                        continue  # block either way → dropped silently (task 5.4c)
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


# ══ Phase 2 Step 4: Company social endpoints (rate) ══
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


@app.get("/company/{company_id}/ratings", dependencies=[Depends(_public_rate)])
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
    # Suspended company or a block either way → 404 (task 5.4g); the company always sees its own.
    _404_if_hidden(_optional_viewer_id(request), resolved_id, "الشركة غير موجودة")
    result = get_company_ratings_detail(resolved_id, viewer_id, limit)
    return {"status": "success", **result}


# ══ Phase 3: Company Posts endpoints ══
@app.get("/company/posts/{company_id}", dependencies=[Depends(_public_rate)])
def company_posts_list(company_id: str, request: Request):
    # Public read. Optional JWT → viewer_appreciated populated per post.
    resolved_id = _resolve_company_id(company_id)
    viewer_uid = None
    auth = request.headers.get("Authorization", "")
    token_str = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if token_str:
        token_data = _jwt_decode(token_str)
        viewer_uid = token_data.get("user_id") if token_data else None
    _404_if_hidden(viewer_uid, resolved_id, "الشركة غير موجودة")
    posts = get_company_posts(resolved_id, viewer_user_id=viewer_uid)
    return {"status": "success", "posts": posts}


def _post_input_check(body: str, tags):
    """Body length + tags from TW.POST_TAGS only, ≤ post_tags_max (task 5.0h — AUD-P2-12 / P2-36).
    → (clean tags list | None, None) or (None, 422 response)."""
    too_long = _too_long(body, "post_body_max", "body")
    if too_long:
        return None, too_long
    if not tags:
        return None, None
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return None, _limit_error(422, "invalid_tags", "limits.post_tags_invalid", "tags")
    clean = list(dict.fromkeys(t.strip() for t in tags))
    if any(t not in tw_limits.POST_TAGS for t in clean):
        return None, _limit_error(422, "invalid_tags", "limits.post_tags_invalid", "tags")
    max_tags = tw_settings.limit("post_tags_max")
    if len(clean) > max_tags:
        return None, _limit_error(422, "too_many_tags", "limits.post_tags_max", "tags", max=max_tags)
    return clean, None


@app.post("/company/posts")
def company_post_create(data: CompanyPostInput, token=Depends(verify_token)):
    user_id   = token.get("user_id")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: POST /company/posts")
        raise HTTPException(401, "رمز غير صالح")
    _require_org_account(token, message="الشركات فقط يمكنها النشر")
    body = (data.body or "").strip()
    if not body:
        raise HTTPException(400, "المنشور فارغ")
    if data.theme_color and data.theme_color not in ALLOWED_POST_COLORS:
        raise HTTPException(400, "لون غير مقبول")
    tags, bad = _post_input_check(body, data.tags)
    if bad:
        return bad
    if not _rate_ok("post_create", int(user_id)):
        return _rate_limited()
    ce = data.comments_enabled if data.comments_enabled is not None else True
    post = create_company_post(int(user_id), body, tags, data.theme_color or None, ce)
    return {"status": "success", "post": post}


@app.delete("/company/posts/{post_id}")
def company_post_delete(post_id: int, token=Depends(verify_token)):
    user_id = token.get("user_id")
    if not user_id:
        print("[SECURITY] INVALID_TOKEN: DELETE /company/posts")
        raise HTTPException(401, "رمز غير صالح")
    _require_org_account(token)
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
    _require_org_account(token)
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
    tags, bad = _post_input_check(body, data.tags)
    if bad:
        return bad
    if not _rate_ok("post_edit", int(user_id)):
        return _rate_limited()
    ce = data.comments_enabled if data.comments_enabled is not None else True
    post = update_company_post(post_id, body, tags, data.theme_color or None, ce)
    return {"status": "success", "post": post}


@app.post("/company/posts/{post_id}/view", dependencies=[Depends(_public_rate)])
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
    _404_if_hidden(user_id, owner, "المنشور غير موجود")

    # Don't count the post owner's own views
    if user_id and int(user_id) == owner:
        return {"status": "skipped", "reason": "owner"}

    vk = "" if user_id else (data.visitor_key or "").strip()[:64]
    if not user_id and not vk:
        return {"status": "skipped", "reason": "no_key"}
    # Same viewer (account, else client IP — a fresh visitor_key per request does not count again)
    # + same post → once per RATES["view_count"] window, before any DB write (task 5.0h-2).
    viewer = f"u{int(user_id)}" if user_id else "ip" + get_client_ip(request)
    if not _rate_ok("view_count", f"post{post_id}:{viewer}"):
        return {"status": "skipped", "reason": "duplicate"}
    if user_id:
        recorded = record_company_post_view(post_id, viewer_user_id=int(user_id))
    else:
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
    _404_if_hidden(user_id, owner_id, "المنشور غير موجود")
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
    _404_if_hidden(user_id, owner_id, "المنشور غير موجود")
    result = set_company_post_save(post_id, int(user_id), body.saved)
    return {"status": "success", **result}


# ── Post Comments System ──────────────────────────────────────────────────

class CommentInput(BaseModel):
    body: str
    reply_to_comment_id: Optional[int] = None
    mentioned_tw_ids: Optional[List[str]] = None

class CommentUpdateInput(BaseModel):
    body: str


@app.get("/company/posts/{post_id}/comments", dependencies=[Depends(_public_rate)])
def company_get_post_comments(post_id: int, request: Request, limit: Optional[int] = None,
                              cursor: Optional[int] = None):
    """Public with optional JWT — returns active comments + viewer flags if authenticated.
    Paged by thread (task 5.0h — AUD-P2-35): `limit` threads (root + its replies, default
    comments_page, max comments_page_max) after thread id `cursor`; next_cursor = null on the last page."""
    auth_header = request.headers.get("Authorization", "")
    viewer_id = None
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        viewer_id = payload.get("user_id")
    lim = tw_settings.limit("comments_page") if limit is None else limit
    lim = max(1, min(int(lim), tw_settings.limit("comments_page_max")))
    owner_id = get_post_owner(post_id)
    if owner_id:
        _404_if_hidden(viewer_id, owner_id, "المنشور غير موجود")
    comments, next_cursor = get_company_post_comments(post_id, viewer_id, limit=lim, cursor=cursor)
    return {"status": "success", "comments": comments, "next_cursor": next_cursor}


@app.post("/company/posts/{post_id}/comments")
def company_create_post_comment(post_id: int, body: CommentInput, token=Depends(verify_token)):
    """Create a comment. JWT required. Validates body, comments_enabled, rate limit."""
    user_id = token.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول للتعليق")
    if not _check_cmt_create_rate(int(user_id), post_id):
        raise HTTPException(status_code=429, detail="الرجاء التمهّل قليلاً")
    owner_id = get_post_owner(post_id)
    if owner_id:
        _404_if_hidden(user_id, owner_id, "المنشور غير موجود")
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
    - every account type: profile_follows both directions + any user (if q)

    Returns up to `limit` candidates [{tw_id, name, avatar, user_type}].

    Perf:
    - Single UNION ALL (1 DB roundtrip, unique param names per branch).
    - When q is empty: pure FK-indexed scan, no ILIKE, no Priority 4.
    - When q is provided: ILIKE per branch; Priority 4 (any user) fills remaining slots.
    - Errors are logged and returned as {"ok": False} — never swallowed silently.
    """
    viewer_id   = int(token["user_id"])
    viewer_type = token.get("user_type", "emp")
    # task 5.0h (AUD-P2-33): ?limit= clamped to 1..mention_limit_max · per-account rate before the DB
    limit = max(1, min(int(limit), tw_settings.limit("mention_limit_max")))
    if not _rate_ok("mention_search", viewer_id):
        return _rate_limited()
    seen:    set  = set()
    results: list = []

    def _add(rows):
        for r in (rows or []):
            tw_id, name, avatar, utype = r[0], r[1], r[2], r[3]
            if tw_id and tw_id not in seen and len(results) < limit:
                seen.add(tw_id)
                results.append({"tw_id": tw_id, "name": name or "",
                                 "avatar": avatar or None, "user_type": utype or ""})

    conn = None
    try:
        conn = get_conn()

        # Every account type (Follow System PR 3.5 — profile_follows is the only follow table):
        # Branch A: accounts I follow (profile_follows.follower_id = me → followed_id)
        # Branch B: accounts who follow me (profile_follows.followed_id = me → follower_id)
        # Merged in a single UNION ALL (1 DB roundtrip).
        # Unique param names per branch (:vid_a/b, :lim_a/b, :q_a/b) guarantee
        # unambiguous pg8000 $N positional mapping across UNION branches.
        # Avatar: profiles.avatar_url — the one image source for every account type (company logo included).
        q_like = f"%{q}%" if q else None
        q_a = " AND u.full_name ILIKE :q_a" if q else ""
        q_b = " AND u.full_name ILIKE :q_b" if q else ""
        params = {"vid_a": viewer_id, "lim_a": limit,
                  "vid_b": viewer_id, "vid_b2": viewer_id, "lim_b": limit}
        if q:
            params.update(q_a=q_like, q_b=q_like)
        _add(conn.run(
            "(SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
            " FROM profile_follows pf"
            " JOIN users u ON u.id = pf.followed_id"
            " LEFT JOIN profiles p ON p.user_id = u.id"
            " WHERE pf.follower_id = :vid_a AND " + bs.visible_sql("u.id", ":vid_a") + q_a + " LIMIT :lim_a)"
            " UNION ALL"
            " (SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
            " FROM profile_follows pf"
            " JOIN users u ON u.id = pf.follower_id"
            " LEFT JOIN profiles p ON p.user_id = u.id"
            " WHERE pf.followed_id = :vid_b AND u.id != :vid_b2 AND " + bs.visible_sql("u.id", ":vid_b") + q_b + " LIMIT :lim_b)",
            **params))
        # Priority 4 — any matching user (only when q provided + space left)
        if q and len(results) < limit:
            _add(conn.run(
                "SELECT u.tw_id, u.full_name, p.avatar_url, u.user_type"
                " FROM users u"
                " LEFT JOIN profiles p ON p.user_id = u.id"
                " WHERE u.id != :vid AND " + bs.visible_sql("u.id", ":vid") + " AND u.full_name ILIKE :q LIMIT :lim",
                vid=viewer_id, q=q_like, lim=limit))

    except Exception as _exc:
        print(f"[mention_search] ERROR viewer={viewer_id} type={viewer_type} q={q!r}: {_exc}")
        return {"ok": False, "candidates": []}
    finally:
        if conn is not None:
            release_conn(conn)

    return {"ok": True, "candidates": results}


# ── Organisation-account gate (task 5.0f — AUD-P1-07) ──────────────────────
# Every company action (applicants, application status, promote, appointments, Talent Bank,
# company posts) checks the account type as it is NOW in users — not the JWT claim, not job
# ownership alone. A company turned personal account → 403 on all of them.
_ORG_TYPES = ("co", "edu")

def _require_org_account(token: dict, allowed=_ORG_TYPES,
                         message: str = "هذه العملية متاحة لحسابات الشركات والجهات التعليمية فقط") -> int:
    """JWT user_id → int after checking users.user_type ∈ allowed. No user → 401 · other type → 403."""
    try:
        user_id = int(token.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(401, "رمز غير صالح")
    try:
        current = get_current_user_type(user_id)
    except Exception as e:
        raise _server_error("require_org_account", e)
    if current is None:
        raise HTTPException(401, "رمز غير صالح")
    if current not in allowed:
        print(f"[SECURITY] ORG_ACCOUNT_REQUIRED: user={user_id} type={current} allowed={allowed}")
        raise HTTPException(403, message)
    return user_id

def _require_org_account_api(token: dict, allowed, message: str):
    """Same gate for {ok, error} endpoints (API Contract) → (user_id, None) | (None, api_error response)."""
    try:
        return _require_org_account(token, allowed, message), None
    except HTTPException as e:
        if e.status_code >= 500:
            raise
        code = "forbidden" if e.status_code == 403 else "unauthorized"
        return None, api_error(e.status_code, code, e.detail)


# ── Saved Candidates (Phase 3 — company-owner only, JWT required) ──────────

def _require_company_owner(token: dict) -> int:
    """Talent Bank / suggestions gate — company accounts only (current type from the DB). Returns company_id."""
    return _require_org_account(token, ("co",), "الشركات فقط يمكنها الوصول للمرشحين المحفوظين")


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
def submit_report(data: ReportInput, token=Depends(verify_token)):
    """Submit a report — the target is stored by type (task 5.0c): user / company → reported_id
    (users) · job → job_id (jobs). Unknown type → 422 · missing target → 404."""
    rtype = (data.reported_type or "").strip()
    if rtype not in REPORT_TARGET_TYPES:
        return api_error(422, "invalid_target_type", "نوع البلاغ غير صحيح", "reported_type")
    # task 5.0h (AUD-P2-11): reason type from tw_limits.REPORT_TYPES · length limits · per-account
    # rate · one report per reporter + target per day (checked in the DB — survives a restart).
    if data.report_type not in tw_limits.REPORT_TYPES:
        return _limit_error(422, "invalid_report_type", "limits.report_type_invalid", "report_type")
    reason = (data.reason or "").strip()
    if not reason:
        return _limit_error(422, "reason_required", "report.reason_required", "reason")
    bad = _too_long(reason, "report_reason_max", "reason") or _too_long(data.target_url, "report_url_max", "target_url")
    if bad:
        return bad
    reporter_id = token.get("user_id")
    if not _rate_ok("report_submit", reporter_id):
        return _rate_limited()
    target_col = "job_id" if rtype == "job" else "reported_id"
    try:
        with db_conn() as conn:
            if rtype == "job":
                exists = conn.run("SELECT 1 FROM jobs WHERE id = :id", id=data.reported_id)
            else:
                exists = conn.run("SELECT 1 FROM users WHERE id = :id", id=data.reported_id)
            if not exists:
                return api_error(404, "target_not_found",
                                 "الوظيفة غير موجودة" if rtype == "job" else "الحساب غير موجود")
            if conn.run(f"SELECT 1 FROM reports WHERE reporter_id = :rid AND {target_col} = :tid "
                        "AND created_at > NOW() - :win * INTERVAL '1 second' LIMIT 1",
                        rid=reporter_id, tid=data.reported_id, win=tw_settings.rate("report_repeat")[1]):
                return _limit_error(429, "duplicate_report", "limits.report_duplicate")
            conn.run(
                "INSERT INTO reports (reporter_id, reported_id, job_id, reported_type, report_type, "
                "reason, target_url, status) "
                "VALUES (:rid, :uid, :jid, :rtype, :rpt, :reason, :url, 'pending')",
                rid=reporter_id,
                uid=None if rtype == "job" else data.reported_id,
                jid=data.reported_id if rtype == "job" else None,
                rtype=rtype, rpt=data.report_type, reason=reason, url=data.target_url)
        # No user notification: admins are not user accounts. The report stays in
        # `reports` (status 'pending') and appears in the admin panel → البلاغات tab
        # (GET /admin/reports + pending badge).
        return {"status": "success", "message": "تم إرسال البلاغ"}
    except Exception as e:
        raise _server_error("submit_report", e)


def _report_target(rep: dict) -> dict:
    """The report's target for the admin list — {kind, id, name, href, deleted} (task 5.0c)."""
    if rep.get("reported_type") == "job":
        jid = rep.get("job_id")
        return {"kind": "job", "id": jid, "name": rep.get("job_title"),
                "href": f"/job-detail?id={int(jid)}" if jid else None, "deleted": jid is None}
    uid, tw = rep.get("reported_id"), rep.get("reported_tw_id")
    gone = uid is None or bool(rep.get("reported_deleted"))   # task 8.5a — soft-deleted = «حساب محذوف», no link
    return {"kind": "user", "id": uid, "name": None if gone else rep.get("reported_name"),
            "href": f"/u/{tw}" if uid and tw and not gone else None, "deleted": gone}


@app.get("/admin/reports")
def admin_get_reports(request: Request):
    """All reports with their resolved target. A DB error → 500 (never an empty list — F9)."""
    check_admin(request, "reports.manage")
    try:
        with db_conn() as conn:
            rows = conn.run("""
                SELECT r.id, r.reporter_id, r.reported_id, r.job_id, r.reported_type,
                       r.report_type, r.reason, r.target_url, r.status, r.created_at,
                       u1.full_name AS reporter_name,
                       u2.full_name AS reported_name, u2.tw_id AS reported_tw_id,
                       u2.deleted_at IS NOT NULL AS reported_deleted,
                       j.title AS job_title
                FROM reports r
                LEFT JOIN users u1 ON r.reporter_id = u1.id
                LEFT JOIN users u2 ON r.reported_id = u2.id
                LEFT JOIN jobs j ON r.job_id = j.id
                ORDER BY r.created_at DESC
            """)
            cols = [c["name"] for c in conn.columns]
        reports = [dict(zip(cols, row)) for row in rows]
        for rep in reports:
            if rep.get('created_at'):
                rep['created_at'] = str(rep['created_at'])
            rep["target"] = _report_target(rep)
        return {"reports": reports, "count": len(reports)}
    except Exception as e:
        raise _server_error("admin_get_reports", e)

@app.put("/admin/reports/{report_id}/resolve")
def resolve_report(report_id: int, request: Request):
    """Mark report as resolved"""
    check_admin(request, "reports.manage")
    try:
        conn = get_conn()
        try:
            conn.run("UPDATE reports SET status='resolved' WHERE id=:id", id=report_id)
        finally:
            release_conn(conn)
        return {"status": "success"}
    except Exception as e:
        raise _server_error("resolve_report", e)


# Client error reports (task 5.0e): rate limited per IP in rate_limit_middleware (own bucket), size-limited by
# ErrorLogInput, and every text field passes _redact_client_log before it is stored or printed — no JWT /
# bearer / token= / password= value and no email address ever reaches the log or GET /admin/errors.
_LOG_REDACTIONS = (
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), "[token]"),
    (re.compile(r"(?i)\bbearer\s+\S+"), "Bearer [token]"),
    (re.compile(r"(?i)\b(token|jwt|access_token|password|secret|code|key)=[^&\s\"']+"), r"\1=[redacted]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
)


def _redact_client_log(text):
    if text is None:
        return None
    text = str(text)
    for rx, rep in _LOG_REDACTIONS:
        text = rx.sub(rep, text)
    return text


@app.post("/log/error")
def log_client_error(data: ErrorLogInput):
    err = {"page": _redact_client_log(data.page), "msg": _redact_client_log(data.msg),
           "file": _redact_client_log(data.file), "line": data.line,
           "ts": _redact_client_log(data.ts), "type": _redact_client_log(data.type) or "js"}
    _error_log.append(err)
    if len(_error_log) > 100: _error_log.pop(0)
    print(f"[CLIENT ERROR] {err['page']} | {err['msg']} | line:{data.line}")
    return {"ok": True}

@app.get("/admin/errors")
def admin_errors(request: Request):
    check_admin(request, "system.manage")
    return {"errors": list(reversed(_error_log)), "count": len(_error_log)}


# ── Admin Stats + Audit Log reads (task 5.3a2 · SYSTEMS_INDEX §25b / §25c) — read-only, admin JWT ──
@app.get("/admin/stats/summary")
def admin_stats_summary(request: Request):
    check_admin(request, "stats.view")
    try:
        return api_ok(admin_insights.stats_summary())
    except Exception as e:
        raise _server_error("admin_stats_summary", e)


@app.get("/admin/stats/timeseries")
def admin_stats_timeseries(request: Request, metric: str = "", days: str = "30"):
    check_admin(request, "stats.view")
    if metric not in admin_insights.TIMESERIES_METRICS:
        return api_error(422, "invalid_metric", "المؤشر غير معروف", field="metric")
    if not (days.isascii() and days.isdigit() and 1 <= int(days) <= admin_insights.TIMESERIES_DAYS_MAX):
        return api_error(422, "invalid_days", f"عدد الأيام من 1 إلى {admin_insights.TIMESERIES_DAYS_MAX}", field="days")
    try:
        return api_ok(admin_insights.stats_timeseries(metric, int(days)))
    except Exception as e:
        raise _server_error("admin_stats_timeseries", e)


def _admin_int(v: str, lo: int, hi: int) -> bool:
    return v.isascii() and v.isdigit() and lo <= int(v) <= hi


@app.get("/admin/activity")
def admin_activity(request: Request, page: str = "1", limit: str = str(admin_insights.ACTIVITY_LIMIT)):
    check_admin(request, "stats.view")
    if not _admin_int(page, 1, 100000):
        return api_error(422, "invalid_page", "رقم الصفحة غير صالح", field="page")
    if not _admin_int(limit, 1, admin_insights.ACTIVITY_PAGE_MAX):
        return api_error(422, "invalid_limit", "عدد العناصر غير صالح", field="limit")
    try:
        return api_ok(admin_insights.activity(int(page), int(limit)))
    except Exception as e:
        raise _server_error("admin_activity", e)


# ── Admin users table (task 5.3a3 · SYSTEMS_INDEX §25d) — replaces the old unpaged GET /auth/users ──
def _admin_users_filters(q: str, type: str, status: str, sort: str):
    """Validated filters → dict, or an api_error response (422). Allowlists only."""
    if len(q) > admin_insights.USERS_Q_MAX:
        return api_error(422, "invalid_q", "نص البحث طويل", field="q")
    if type and type not in admin_insights.USER_TYPES:
        return api_error(422, "invalid_type", "نوع الحساب غير معروف", field="type")
    if status and status not in admin_insights.USER_VERIFICATION:
        return api_error(422, "invalid_status", "حالة التوثيق غير معروفة", field="status")
    if sort not in admin_insights.USER_SORTS:
        return api_error(422, "invalid_sort", "الترتيب غير معروف", field="sort")
    return {"q": q, "user_type": type, "verification": status, "sort": sort}


@app.get("/admin/users")
def admin_users(request: Request, q: str = "", type: str = "", status: str = "", sort: str = "newest",
                page: str = "1", limit: str = "20"):
    claims = check_admin(request, "users.view")
    f = _admin_users_filters(q, type, status, sort)
    if isinstance(f, JSONResponse):
        return f
    if not _admin_int(page, 1, 100000):
        return api_error(422, "invalid_page", "رقم الصفحة غير صالح", field="page")
    if not _admin_int(limit, 1, admin_insights.USERS_PAGE_MAX):
        return api_error(422, "invalid_limit", "عدد العناصر غير صالح", field="limit")
    try:
        view = _admin_email_view(claims)   # without it: no email column, q never matches an email (8.4a)
        return api_ok(_admin_contacts(claims, admin_insights.users_list(page=int(page), limit=int(limit),
                                                                     with_email=view, **f)))
    except Exception as e:
        raise _server_error("admin_users", e)


@app.get("/admin/users/export")
def admin_users_export(request: Request, q: str = "", type: str = "", status: str = "", sort: str = "newest"):
    """Same filters as GET /admin/users → CSV (UTF-8 + BOM). Recorded in the audit log (AUDIT_READ_ROUTES)."""
    check_admin(request, "users.export")
    f = _admin_users_filters(q, type, status, sort)
    if isinstance(f, JSONResponse):
        return f
    try:
        body = admin_insights.users_csv(**f)
    except Exception as e:
        raise _server_error("admin_users_export", e)
    return Response(content=body.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="users.csv"', "Cache-Control": "no-store"})


@app.get("/admin/audit")
def admin_audit(request: Request, page: str = "1", limit: str = "20", action: str = ""):
    check_admin(request, "audit.view")
    if not (page.isascii() and page.isdigit() and 1 <= int(page) <= 100000):
        return api_error(422, "invalid_page", "رقم الصفحة غير صالح", field="page")
    if not (limit.isascii() and limit.isdigit() and 1 <= int(limit) <= admin_insights.AUDIT_PAGE_MAX):
        return api_error(422, "invalid_limit", "عدد العناصر غير صالح", field="limit")
    if len(action) > 80:
        return api_error(422, "invalid_action", "الإجراء غير صالح", field="action")
    try:
        return api_ok(admin_insights.audit_list(int(page), int(limit), action))
    except Exception as e:
        raise _server_error("admin_audit", e)

@app.post("/auth/verify-token")
def verify_token_endpoint(token=Depends(verify_token)):
    return {"valid": True, "user_id": token["user_id"], "user_type": token["user_type"]}

# Profile completion checklist (PR 4.2a · F29) — the ONE definition of "profile completion".
# Home (home.nav.js), the profile stats tile and the owner completion card (profile-v2.completion.js)
# all read it through GET /profile/{id}/score; the browser never recomputes it.
# (id, points, tip) — points sum to 100. Labels / UI actions per id live in the frontend (twT keys).
PROFILE_SCORE_ITEMS = (
    ("avatar",     10, "أضف صورة شخصية"),
    ("profession", 10, "أضف مسماك الوظيفي"),
    ("bio",        10, "أضف نبذة عنك"),
    ("short_bio",   5, "أضف نبذة قصيرة"),
    ("location",    5, "أضف موقعك"),
    ("avail",       5, "حدّد حالة التوظيف"),
    ("exp",        15, "أضف خبرة عملية"),
    ("edu",        10, "أضف شهاداتك"),
    ("skills",     10, "أضف 3 مهارات على الأقل"),
    ("courses",     5, "أضف دورة تدريبية"),
    ("langs",       5, "أضف لغة"),
    ("links",       5, "أضف رابط LinkedIn أو GitHub"),
    ("verified",    5, "وثّق هويتك"),
)


def _calc_profile_score(uid: int, conn) -> dict:
    """Shared scoring helper — used by /score and /metrics (no duplication).
    Returns dict with score, tips, level, items (per-checklist-item done flags)
    and the DB counts used for scoring."""
    rows = conn.run(
        "SELECT headline, title, bio, short_bio, avatar_url, location, city, country, "
        "avail, profession_id, is_verified "
        "FROM profiles WHERE user_id=:uid", uid=uid)
    prof = {}
    if rows:
        cols = [c["name"] if isinstance(c, dict) else c[0] for c in conn.columns]
        prof = dict(zip(cols, rows[0]))

    def _count(table):
        return (conn.run(f"SELECT COUNT(*) FROM {table} WHERE user_id=:uid", uid=uid) or [[0]])[0][0]

    def _txt(*keys):
        return any(str(prof.get(k) or "").strip() for k in keys)

    exp_count    = _count("experience")
    edu_count    = _count("education")
    skill_count  = _count("user_skills")
    link_count   = _count("user_links")
    course_count = _count("courses")
    lang_count   = _count("user_langs")
    done = {
        "avatar":     _txt("avatar_url"),
        "profession": bool(prof.get("profession_id")) or _txt("headline", "title"),
        "bio":        _txt("bio"),
        "short_bio":  _txt("short_bio"),
        "location":   _txt("city", "country", "location"),
        "avail":      _txt("avail"),
        "exp":        exp_count > 0,
        "edu":        edu_count > 0,
        "skills":     skill_count >= 3,
        "courses":    course_count > 0,
        "langs":      lang_count > 0,
        "links":      link_count > 0,
        "verified":   bool(prof.get("is_verified")),
    }
    score = 0
    tips  = []
    items = []
    for item_id, pts, tip in PROFILE_SCORE_ITEMS:
        ok = bool(rows) and done[item_id]
        items.append({"id": item_id, "done": ok, "points": pts})
        if ok: score += pts
        else:  tips.append({"tip": tip, "points": pts})
    tips.sort(key=lambda x: -x["points"])
    return {
        "score":       score,
        "tips":        tips[:3],
        "level":       "ممتاز" if score >= 90 else "جيد" if score >= 70 else "متوسط" if score >= 50 else "يحتاج تحسين",
        "items":       items,
        "exp_count":   exp_count,
        "edu_count":   edu_count,
        "skill_count": skill_count,
        "link_count":  link_count,
    }


def _score_detail_allowed(request: Request, uid: int) -> bool:
    """Who may see the completion checklist (items + tips) of profile `uid` — PR 4.2a,
    PROFILE-DATA-VISIBILITY.md "Completion score": the owner (Bearer JWT user_id == uid) or an
    admin (valid admin JWT in X-Admin-Token). Everyone else gets the score only."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:]:
        payload = _jwt_decode(auth_header[7:]) or {}
        tok_uid = payload.get("user_id")
        if tok_uid is not None and str(tok_uid) == str(uid):
            return True
    if request.headers.get("X-Admin-Token"):
        try:
            check_admin(request, "users.view")
            return True
        except HTTPException:
            return False
    return False


@app.get("/profile/{user_id}/score", dependencies=[Depends(_public_rate)])
def profile_score(user_id: int, request: Request):
    """Profile completion score. Uses _calc_profile_score — no algorithm duplication.
    Public: {score, level} (the profile page shows the score to visitors — stats tile).
    Owner / admin only: + tips + items — which items are missing is the owner's business
    (PR 4.2a · docs/security/PROFILE-DATA-VISIBILITY.md → Completion score).
    Hidden account (suspended / block either way) → 404 (task 5.4 rule)."""
    _404_if_hidden(_optional_viewer_id(request), user_id, "الملف الشخصي غير موجود")
    try:
        conn = get_conn()
        try:
            data = _calc_profile_score(user_id, conn)
        finally:
            release_conn(conn)
        out = {"score": data["score"], "level": data["level"]}
        if _score_detail_allowed(request, user_id):
            out["tips"]  = data["tips"]
            out["items"] = data["items"]
        return out
    except HTTPException: raise
    except Exception as e: raise _server_error("profile_score", e)


class ResetPasswordInput(BaseModel):
    password: str


@app.post("/admin/logo")
async def upload_logo(data: AdminLogoInput, request: Request):
    """Upload site logo (admin only) — slot: logo_wide | logo_tall.
    Same image validation as /upload/image (PR-7a): JPEG/PNG/WebP only, no SVG."""
    check_admin(request, CONTENT_PERM)
    slot = data.filename or "logo_wide"
    if slot not in _LOGO_SLOTS:
        raise HTTPException(400, "نوع الشعار غير معروف")
    mime, ext, file_bytes = _validate_image_data_url(data.data_url)
    logo_url = await _store_image("site", f"{slot}_{secrets.token_hex(6)}{ext}",
                                  file_bytes, mime, data.data_url, "[Logo]")
    # Always cache in memory
    _html_cache[slot] = logo_url
    try:
        await asyncio.to_thread(ensure_site_settings_table)
        await asyncio.to_thread(set_site_setting, slot, logo_url)
    except Exception as db_err:
        print(f"[Logo] DB save failed: {db_err} - cached in memory only")
    return {"status": "success", "url": logo_url}

@app.get("/admin/logo", dependencies=[Depends(_public_rate)])
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

# ══ Strings System — admin overrides (PR 3.6 · SYSTEMS_INDEX §59) ══
@app.get("/admin/strings")
def admin_get_strings(request: Request):
    """Defaults + current overrides (lang = ar for now)."""
    check_admin(request, CONTENT_PERM)
    lang = tw_strings.DEFAULT_LANG
    return api_ok({"lang": lang, "defaults": tw_strings.DEFAULTS[lang],
                   "overrides": dict(_STRINGS_OVERRIDES), "max_len": tw_strings.MAX_LEN})


@app.put("/admin/strings")
def admin_put_strings(request: Request, data: dict = Body(...)):
    """Replace the whole override map: {"overrides": {key: text}}. Empty text = default.
    Known keys only · ≤ MAX_LEN · no HTML · only the default's {placeholders}."""
    check_admin(request, CONTENT_PERM)
    try:
        clean = tw_strings.validate_overrides(data.get("overrides"))
    except tw_strings.StringsError as e:
        return api_error(422, e.code, e.message, e.field)
    old = dict(_STRINGS_OVERRIDES)
    changed = sorted(k for k in set(old) | set(clean) if old.get(k) != clean.get(k))
    request.state.audit_target = "keys=" + (",".join(changed) or "-")
    ensure_site_settings_table()
    if not set_site_setting(tw_strings.setting_key(), json.dumps(clean, ensure_ascii=False)):
        return api_error(500, "save_failed", "تعذّر حفظ النصوص، حاول مرة أخرى")
    _strings_set_overrides(clean)
    print(f"[strings] admin saved {len(clean)} override(s)")
    return api_ok({"overrides": clean})


# ══ Actions Registry — admin overrides (PR 3.7 · SYSTEMS_INDEX §60 · BUTTONS.md BTN-19) ══
@app.get("/admin/actions")
def admin_get_actions(request: Request):
    """Registry + current overrides + the audience / type vocabularies."""
    check_admin(request, "settings.edit")
    return api_ok({"actions": tw_actions.REGISTRY, "overrides": dict(_ACTIONS_OVERRIDES),
                   "audiences": list(tw_actions.AUDIENCES), "types": list(tw_actions.TYPES)})


@app.put("/admin/actions")
def admin_put_actions(request: Request, data: dict = Body(...)):
    """Replace the whole override map: {"overrides": {id: {"enabled": false|true, "visibleTo": [...]}}}
    (true turns on a registry default-off action — tw_actions.json "enabled": false).
    Known ids + known fields + known audiences only (all-or-nothing). {} = registry defaults."""
    claims = check_admin(request, "settings.edit")
    try:
        clean = tw_actions.validate_overrides(data.get("overrides"))
    except tw_actions.ActionsError as e:
        return api_error(422, e.code, e.message, e.field)
    ensure_site_settings_table()
    if not set_site_setting(tw_actions.SETTING_KEY, json.dumps(clean, sort_keys=True)):
        return api_error(500, "save_failed", "تعذّر حفظ إعدادات الأزرار، حاول مرة أخرى")
    _actions_set_overrides(clean)
    print(f"[actions] overrides saved by admin sub={claims.get('sub')!r} "
          f"values={json.dumps(clean, sort_keys=True)}")
    return api_ok({"overrides": clean})


# ══ Unified Email System — admin (task 5.1a · SYSTEMS_INDEX §54j) ══
_EMAIL_UNAVAILABLE_MSG = "خدمة البريد الإلكتروني غير متاحة حالياً، حاول لاحقاً"


@app.get("/admin/email")
def admin_get_email(request: Request):
    """Provider status (configured | missing — never the key) + settings + template string keys."""
    check_admin(request, "settings.edit")
    try:
        stats = email_send_stats()
    except Exception as e:   # the counter must never hide the settings (F9: logged)
        print(f"[email] stats unavailable: {type(e).__name__}")
        stats = None
    return api_ok({"status": email_service.status(), "settings": email_service.get_settings(),
                   "defaults": email_service.DEFAULTS, "types": list(email_service.TYPES),
                   "categories": {k: v["category"] for k, v in email_service.TEMPLATES.items()},
                   "notify_types": list(email_service.NOTIFY_TYPES),
                   "inbound_switch": email_service.INBOUND_SWITCH,
                   "notify_limits": {k: list(v) for k, v in email_service.NOTIFY_LIMITS.items()},
                   "stats": stats,
                   "templates": {k: [f"email.{k}.{p}" for p in v["parts"]]
                                 for k, v in email_service.TEMPLATES.items()}})


@app.put("/admin/email")
def admin_put_email(request: Request, data: dict = Body(...)):
    """Partial update: {from_address?, from_name?, site_url?, types?: {key: bool},
    notify?: {daily_cap?, monthly_cap?, message_delay_minutes?, message_throttle_hours?}} (all-or-nothing)."""
    claims = check_admin(request, "settings.security")   # site_url / from_address = the source of reset / verify links → owner only (8.4a)
    try:
        clean = email_service.validate_settings(data, email_service.get_settings())
    except email_service.EmailSettingsError as e:
        return api_error(422, e.code, e.message, e.field)
    ensure_site_settings_table()
    if not set_site_setting(email_service.SETTING_KEY, json.dumps(clean, ensure_ascii=False, sort_keys=True)):
        return api_error(500, "save_failed", "تعذّر حفظ إعدادات البريد، حاول مرة أخرى")
    email_service.set_settings(clean)
    print(f"[email] settings saved by admin sub={claims.get('sub')!r} types={json.dumps(clean['types'], sort_keys=True)} "
          f"notify={json.dumps(clean['notify'], sort_keys=True)}")
    return api_ok({"settings": clean})


# ══ Unified Admin Settings (task 4.1 · SYSTEMS_INDEX §25g · docs/rules/settings.md) ══
# Permission settings.edit (owner token = "*") on all three: no / bad token → 401 · admin token
# without it → 403. Keys outside tw_settings.REGISTRY → 404 · wrong type / out of range → 422.
# The audit row (admin_audit_middleware) carries old / new via request.state.audit_change.
def _setting_out(it: dict) -> dict:
    return dict(it, label=_tw_text(it["label_key"]), description=_tw_text(it["desc_key"]))


def _setting_error(e: "tw_settings.SettingError") -> JSONResponse:
    vars = {k: _fmt_number(v) for k, v in e.vars.items()}
    return api_error(e.status, e.code, _tw_text(e.text_key, **vars), "value" if e.status == 422 else None)


@app.get("/admin/settings")
def admin_settings_list(request: Request):
    check_admin(request, tw_settings.PERM)
    return api_ok({"items": [_setting_out(it) for it in tw_settings.listing()],
                   "groups": list(tw_settings.GROUPS), "cache_ttl_s": tw_settings.CACHE_TTL_S})


def _settings_write(request: Request, key: str, fn):
    # 401 / 403 before the key is read or written; a security key needs the owner-only perm (task 8.4a)
    claims = check_admin(request, tw_settings.SECURITY_PERM if tw_settings.is_security(key) else tw_settings.PERM)
    try:
        old, new = fn(str(claims.get("sub") or "-"))
    except tw_settings.SettingError as e:
        return _setting_error(e)
    except Exception as e:
        raise _server_error("admin_settings_write", e)
    request.state.audit_change = (old, new)
    return api_ok({"setting": _setting_out(tw_settings.item(key)), "old": old, "changed": old != new})


@app.put("/admin/settings/{key}")
def admin_settings_update(request: Request, key: str, data: dict = Body(...)):
    """{value: int} → stored (a value equal to the default removes the row). Applies at once."""
    return _settings_write(request, key, lambda actor: tw_settings.set_value(key, data.get("value"), actor))


@app.post("/admin/settings/{key}/reset")
def admin_settings_reset(request: Request, key: str):
    """Back to the tw_limits default (the row deleted)."""
    return _settings_write(request, key, lambda actor: tw_settings.reset_value(key, actor))


# ══ Support Tickets (task 7.1 · 7.2a · docs/rules/support.md · SYSTEMS_INDEX §62 · ARCHITECTURE §81) ══
# Every rule lives in support.py (statuses = support.transition · details = support.clean_details); here: input
# check (text only, subject ≤ support_subject_max, message ≤ support_body_max, empty → 422), limits
# (tw_settings), the gate. Priority is the admin's only — `priority` in a user / guest body → 422.
# Account: verify_token, own tickets only (any other → 404). Guest (login problems only): _public_rate +
# the OTP send limits (otp_send_target / otp_send_ip) + support_guest_email / _ip / _global after the code.
# Admin: check_admin(request, SUPPORT_PERM) first in every endpoint (owner token "*" holds it) — no / bad
# token → 401 · admin token without it → 403. Audit = admin_audit_middleware (audit_target + audit_change).
SUPPORT_PERM = "support.manage"


def _support_reply_allow(public_id: str) -> bool:
    """The ONE per-ticket requester reply rate (7.5a): guest link + account + inbound email share the bucket
    support_reply_ticket:{public_id}. support._requester_reply asks it last, right before the write — a reply
    refused earlier (session / owner / reopen / open_max) never spends it. Admin replies never count."""
    return _rate_ok("support_reply_ticket", public_id)


def _support_err(e: "support.SupportError") -> JSONResponse:
    return api_error(e.status, e.code, _tw_text(e.text_key), e.field)


def _support_extra(category: str, data: dict):
    """(details, faq_id) checked by support.clean_details / clean_faq — SupportError → 422."""
    return support.clean_details(category, data.get("details")), support.clean_faq(data.get("faq_id"))


def _support_text(data: dict, field: str, limit_name: str):
    """(clean text, None) or (None, 422 response) — str only, trimmed, not empty, within the limit."""
    v = data.get(field)
    if v is None:
        v = ""
    if not isinstance(v, str):
        return None, api_error(422, "invalid_value", _tw_text("support.error.invalid_value"), field)
    v = v.strip()
    if not v:
        return None, api_error(422, "required", _tw_text("support.error.required"), field)
    return v, _too_long(v, limit_name, field)


def _support_no_priority(data: dict):
    if "priority" in data:
        return api_error(422, "priority_forbidden", _tw_text("support.error.priority_forbidden"), "priority")
    return None


def _support_uid(token) -> int:
    uid = int(token.get("user_id") or 0)
    if not uid:
        raise HTTPException(401, "غير مصرح")
    return uid


def _support_not_found() -> JSONResponse:
    return api_error(404, "not_found", _tw_text("support.error.not_found"))


@app.get("/support/meta", dependencies=[Depends(_public_rate)])
def support_meta():
    """Categories · allowed details fields per category · FAQ ids — lists only (texts = tw_strings)."""
    return api_ok(support.meta())


@app.get("/support/tickets")
def support_my_tickets(token=Depends(verify_token)):
    uid = _support_uid(token)
    try:
        return api_ok({"items": support.list_user_tickets(uid), "categories": list(support.CATEGORIES),
                       "open_max": tw_settings.limit("support_open_max")})
    except Exception as e:
        raise _server_error("support_my_tickets", e)


@app.post("/support/tickets")
def support_create_ticket(data: dict = Body(...), token=Depends(verify_token)):
    uid = _support_uid(token)
    bad = _support_no_priority(data)
    if bad:
        return bad
    category = data.get("category")
    if category not in support.CATEGORIES:
        return api_error(422, "invalid_category", _tw_text("support.error.category"), "category")
    subject, bad = _support_text(data, "subject", "support_subject_max")
    if bad:
        return bad
    body, bad = _support_text(data, "body", "support_body_max")
    if bad:
        return bad
    try:
        details, faq_id = _support_extra(category, data)
    except support.SupportError as e:
        return _support_err(e)
    if not _rate_ok("support_create", uid):
        return _rate_limited()
    try:
        return api_ok(support.create_user_ticket(uid, category, subject, body,
                                                 tw_settings.limit("support_open_max"), details, faq_id), status=201)
    except support.SupportError as e:
        return _support_err(e)
    except Exception as e:
        raise _server_error("support_create_ticket", e)


@app.get("/support/tickets/{public_id}")
def support_my_ticket(public_id: str, token=Depends(verify_token)):
    uid = _support_uid(token)
    try:
        return api_ok(support.get_user_ticket(public_id, uid))
    except LookupError:
        return _support_not_found()
    except Exception as e:
        raise _server_error("support_my_ticket", e)


@app.post("/support/tickets/{public_id}/messages")
def support_reply(public_id: str, data: dict = Body(...), token=Depends(verify_token)):
    uid = _support_uid(token)
    body, bad = _support_text(data, "body", "support_body_max")
    if bad:
        return bad
    try:
        return api_ok(support.user_reply(public_id, uid, body, tw_settings.limit("support_open_max"),
                                         allow=_support_reply_allow))
    except LookupError:
        return _support_not_found()
    except support.SupportError as e:
        return _support_err(e)
    except Exception as e:
        raise _server_error("support_reply", e)


@app.post("/support/tickets/{public_id}/close")
def support_close(public_id: str, token=Depends(verify_token)):
    """«انحلّت» → resolved (path kept from 7.1)."""
    uid = _support_uid(token)
    try:
        return api_ok(support.user_resolve(public_id, uid))
    except LookupError:
        return _support_not_found()
    except Exception as e:
        raise _server_error("support_close", e)


# ── guest (login problems) — step 1: a code to the email · step 2: the code + the ticket ──
def _support_guest_email(data: dict):
    email = data.get("email")
    email = email.strip().lower() if isinstance(email, str) else ""
    if not email_service.valid_address(email):
        return None, api_error(422, "invalid_email", _tw_text("support.error.email"), "email")
    return email, None


@app.post("/support/guest/code", dependencies=[Depends(_public_rate)])
def support_guest_code(request: Request, data: dict = Body(...)):
    email, bad = _support_guest_email(data)
    if bad:
        return bad
    # fail closed — no code without delivery, and no code when the follow-up link could not be sent (7.2a)
    if not (email_service.can_send("support_guest_otp") and email_service.can_send("support_guest_link")):
        return api_error(503, "otp_delivery_unavailable", _tw_text("support.error.code_unavailable"))
    # Same send limits as the KYC email code: per normalised address (any account) · per client IP.
    if not _rate_ok_all([("otp_send_target", f"email:{_otp_norm_target('email', email)}"),
                         ("otp_send_ip", get_client_ip(request))]):
        return _otp_rate_limited()
    try:
        code = guest_otp_issue(email)
        res = email_service.send_email(email, "support_guest_otp", {"code": code, "minutes": otp_ttl_minutes()})
        code = None
    except Exception as e:
        raise _server_error("support_guest_code", e)
    if not res.get("ok"):
        return api_error(503, "otp_delivery_unavailable", _tw_text("support.error.code_unavailable"))
    return api_ok({"sent": True, "minutes": otp_ttl_minutes()})


@app.post("/support/guest/tickets", dependencies=[Depends(_public_rate)])
def support_guest_ticket(request: Request, data: dict = Body(...)):
    bad = _support_no_priority(data)
    if bad:
        return bad
    category = data.get("category", support.GUEST_CATEGORY)
    if category != support.GUEST_CATEGORY:      # the server decides — a guest writes about login only
        return api_error(422, "guest_category", _tw_text("support.error.guest_category"), "category")
    email, bad = _support_guest_email(data)
    if bad:
        return bad
    subject, bad = _support_text(data, "subject", "support_subject_max")
    if bad:
        return bad
    body, bad = _support_text(data, "body", "support_body_max")
    if bad:
        return bad
    try:
        details, faq_id = _support_extra(support.GUEST_CATEGORY, data)
    except support.SupportError as e:
        return _support_err(e)
    if not email_service.can_send("support_guest_link"):   # fail closed — a guest ticket without its link = lost
        return api_error(503, "otp_delivery_unavailable", _tw_text("support.error.code_unavailable"))
    code = data.get("code")
    if not otp_code_valid(code):   # task 8.4c-0b — wrong shape → 422, no attempt used
        return api_error(422, "invalid_code", _tw_text("support.error.code_invalid"), "code")
    try:
        verified = guest_otp_verify(email, code)
    except Exception as e:
        raise _server_error("support_guest_ticket", e)
    if not verified:
        return api_error(400, "invalid_code", _tw_text("support.error.code_invalid"), "code")
    # Per email · per IP · every guest together — one locked step; the email + global caps hold even
    # when the IP is forged.
    if not _rate_ok_all([("support_guest_email", email), ("support_guest_ip", get_client_ip(request)),
                         ("support_guest_global", "all")]):
        return _rate_limited()
    try:
        out = support.create_guest_ticket(email, subject, body, details, faq_id)
    except Exception as e:
        raise _server_error("support_guest_ticket", e)
    # The follow-up link goes by email only — the reply carries the H number, never the link.
    _support_send_links(email, [(out["public_id"], out.pop("token"))])
    return api_ok({"public_id": out["public_id"]}, status=201)


# ── guest follow-up link (task 7.2a · 7.4 — ARCHITECTURE §81 → guest link security) ──
# Token in the body only (POST, never a query string) · wrong / expired / revoked / not a guest ticket →
# one 404 · support_track_ip on every call + _public_rate · reply: support_reply_ticket per ticket (shared — 7.5a).
# 7.4: the link names the ticket only — view / reply / resolve need the session from /support/track/verify.
# Headers (no-store · no-referrer · noindex) = security_headers on every /support/track path.
def _support_reply_to(ticket_id=None, public_id=None):
    """Reply-To of a support email (7.3): support+<new token>@ — a reply lands on the same ticket.
    Failure → None (the email still goes, without Reply-To) + one log line (type only)."""
    try:
        tid = ticket_id if ticket_id is not None else support.ticket_id_of(public_id)
        return support.reply_address(support.issue_reply_token(int(tid))) if tid else None
    except Exception as e:
        print(f"[support] reply token failed: {type(e).__name__}")
        return None


def _support_send_links(email: str, links) -> None:
    """One support_guest_link email per ticket (H number + link). Never logs the token or the address."""
    site = email_service.get_settings()["site_url"]
    for public_id, token in links:
        email_service.send_email(email, "support_guest_link",
                                 {"ticket": public_id, "link": support.track_link(site, token)},
                                 reply_to=_support_reply_to(public_id=public_id))


def _support_resend_send(email: str) -> None:
    try:
        _support_send_links(email, support.guest_resend(email))
    except Exception as e:
        print(f"[support] link resend failed: {type(e).__name__}")


def _support_track_not_found() -> JSONResponse:
    return api_error(404, "not_found", _tw_text("support.error.track_not_found"))


def _support_track(request: Request, fn):
    if not _rate_ok("support_track_ip", get_client_ip(request)):
        return _rate_limited()
    try:
        return api_ok(fn())
    except LookupError:
        return _support_track_not_found()
    except support.GuestSessionError:
        return api_error(401, "session_required", _tw_text("support.error.track_session"))
    except support.SupportError as e:
        return _support_err(e)


# 7.4 — the link only NAMES the ticket; the conversation needs {session} (code to guest_email → verify).
# A link token is never accepted as a session (another table) — missing / wrong / expired / revoked → one 401.
@app.post("/support/track/view", dependencies=[Depends(_public_rate)])
def support_track_view(request: Request, data: dict = Body(...)):
    """{session} → the conversation · {token} only → H number + masked address · both (7.5b) → the
    conversation only when the session's ticket = the link's ticket, else 401 (no fallback to the link)."""
    try:
        if "session" in data:
            return _support_track(request, lambda: support.guest_view(data.get("session"), data.get("token")))
        return _support_track(request, lambda: support.guest_link_info(data.get("token")))
    except Exception as e:
        raise _server_error("support_track_view", e)


def _support_track_code_send(token) -> None:
    """After the reply: valid link + per-ticket cooldown / hourly cap → a new code to the STORED guest_email.
    Never logs the address, the token or the code."""
    try:
        target = support.guest_link_target(token)
        if not target:
            return
        tid, email = target
        if not _rate_ok_all([("support_track_code_gap", tid), ("support_track_code_ticket", tid)]):
            return
        code = support.track_otp_issue(tid, email)
        res = email_service.send_email(email, "support_guest_otp", {"code": code, "minutes": otp_ttl_minutes()})
        code = None
        if not res.get("ok"):
            print(f"[support] track code not sent: {res.get('code')}")
    except Exception as e:
        print(f"[support] track code failed: {type(e).__name__}")


@app.post("/support/track/code", dependencies=[Depends(_public_rate)])
def support_track_code(request: Request, background_tasks: BackgroundTasks, data: dict = Body(...)):
    """{token} → always the same reply (+ the cooldown for the page). The address comes from the ticket,
    never from the request; lookup + send run after the reply."""
    if not _rate_ok("support_track_code_ip", get_client_ip(request)):
        return _rate_limited()
    if email_service.can_send("support_guest_otp"):
        background_tasks.add_task(_support_track_code_send, data.get("token"))
    return api_ok({"sent": True, "cooldown_s": int(tw_settings.rate("support_track_code_gap")[1]),
                   "minutes": otp_ttl_minutes()})


@app.post("/support/track/verify", dependencies=[Depends(_public_rate)])
def support_track_verify(request: Request, data: dict = Body(...)):
    """{token, code} → {session} (24 h max, never extended) · wrong / expired / used code → 422 (general text)."""
    def fn():
        session = support.guest_verify(data.get("token"), data.get("code"),
                                       tw_settings.limit("support_track_session_hours"))
        if not session:
            raise support.SupportError(422, "invalid_code", "support.error.code_invalid", "code")
        return {"session": session}
    try:
        return _support_track(request, fn)
    except Exception as e:
        raise _server_error("support_track_verify", e)


@app.post("/support/track/reply", dependencies=[Depends(_public_rate)])
def support_track_reply(request: Request, data: dict = Body(...)):
    bad = _support_no_priority(data)
    if bad:
        return bad
    body, bad = _support_text(data, "body", "support_body_max")
    if bad:
        return bad
    try:
        return _support_track(request, lambda: support.guest_reply(
            data.get("session"), body, allow=_support_reply_allow))
    except Exception as e:
        raise _server_error("support_track_reply", e)


@app.post("/support/track/resolve", dependencies=[Depends(_public_rate)])
def support_track_resolve(request: Request, data: dict = Body(...)):
    try:
        return _support_track(request, lambda: support.guest_resolve(data.get("session")))
    except Exception as e:
        raise _server_error("support_track_resolve", e)


@app.post("/support/track/resend", dependencies=[Depends(_public_rate)])
def support_track_resend(request: Request, background_tasks: BackgroundTasks, data: dict = Body(...)):
    """{email} → always the same reply. Lookup + new links + emails run after the reply (timing says
    nothing). Over the per-email rate → same reply, no email (like pwreset_email)."""
    if not _rate_ok("support_link_resend_ip", get_client_ip(request)):
        return _rate_limited()
    email = data.get("email") if isinstance(data, dict) else None
    email = email.strip().lower() if isinstance(email, str) else ""
    # Type switched off → same reply, nothing sent (and no link revoked / issued).
    if email_service.valid_address(email) and email_service.can_send("support_guest_link") \
            and _rate_ok("support_link_resend_email", email):
        background_tasks.add_task(_support_resend_send, email)
    return api_ok({"sent": True})


# ── inbound mail (task 7.3 — docs/rules/support.md → البريد الوارد · Resend Receiving) ──
# POST /webhooks/resend/inbound — email.received only. RESEND_WEBHOOK_SECRET missing → 503 · body over
# support_inbound_request_max → 413 · Svix signature wrong / timestamp off by > 5 min → 401 (before any DB) ·
# switch types.support_inbound off → 200, nothing. Everything after the check answers 200 (ignored or done) —
# except a failed fetch of the email from Resend → 503 so Resend retries (no event row written).
# Never logs an address, a subject, a body or a token — the outcome code only. Never replies to an email.
_INBOUND_AUTO_FROM = ("mailer-daemon", "postmaster")
# 7.5a — a reply (support+<token>@) is accepted only when Resend's own check says authentication.dmarc == pass
# (computed by the receiving server — never a header). Anything else → its outcome, no message written.
_INBOUND_DMARC = {"fail": "ignored_auth_fail", "processing_failed": "ignored_auth_error"}   # else → ignored_auth_none
# 7.5a — reply text: a follow-up link (/support/track … t=) and a support+<token>@ address are always redacted;
# the quoted original is cut at the FIRST known separator only (nothing else is ever removed).
_INBOUND_LINK_RE = re.compile(r"""[^\s<>"'()\[\]]*/support/track[^\s<>"'()\[\]]*""", re.I)
_INBOUND_ADDR_RE = re.compile(r"""support\+[^\s@<>"'()\[\]]+@[A-Za-z0-9.-]+""", re.I)
_INBOUND_BIDI_RE = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_INBOUND_SEP_RES = (
    re.compile(r"^On\s.+\swrote:$", re.I),                                   # Gmail / Apple Mail (English)
    re.compile(r"^في\s.+\s(كتب|تمت كتابة ما يلي بواسطة)\s.*<[^<>\s]+@[^<>\s]+>.*:$"),   # Gmail (Arabic) — with <address>
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}$", re.I),                    # Outlook
)


def _inbound_dmarc(msg: dict):
    """None = pass · else the outcome code (fail / processing_failed / anything else incl. missing)."""
    a = msg.get("authentication")
    d = a.get("dmarc") if isinstance(a, dict) else None
    if d == "pass":
        return None
    return _INBOUND_DMARC.get(d, "ignored_auth_none") if isinstance(d, str) else "ignored_auth_none"


def _inbound_reply_text(text: str) -> str:
    """Reply body: redact the follow-up link + support+<token>@ (support.inbound.redacted), then cut the quote at
    the first «On … wrote:» / Arabic Gmail line / «-----Original Message-----» / a «>» block that runs to the
    end. Nothing left above the cut → the whole (redacted) text."""
    mark = _tw_text("support.inbound.redacted")
    text = _INBOUND_LINK_RE.sub(lambda m: mark if "t=" in m.group(0).lower() else m.group(0), text or "")
    text = _INBOUND_ADDR_RE.sub(mark, text)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cut = None
    for i, line in enumerate(lines):
        s = _INBOUND_BIDI_RE.sub("", line).strip()
        two = (s + " " + _INBOUND_BIDI_RE.sub("", lines[i + 1]).strip()) if i + 1 < len(lines) else s
        if any(r.match(s) or r.match(two) for r in _INBOUND_SEP_RES) \
                or (s.startswith(">") and all(not x.strip() or x.lstrip().startswith(">") for x in lines[i:])):
            cut = i
            break
    if cut is None:
        return text
    head = "\n".join(lines[:cut])
    return head if head.strip() else text


def _inbound_text(msg: dict) -> str:
    """Plain text only: text, else the HTML with every tag removed (script / style content too)."""
    text = msg.get("text")
    if isinstance(text, str) and text.strip():
        return text
    h = msg.get("html")
    if not isinstance(h, str):
        return ""
    h = re.sub(r"(?is)<(script|style|head)\b.*?</\1\s*>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6])\s*>", "\n", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    h = re.sub(r"<[^>]*>", " ", h)
    return _html_unescape(h)


def _inbound_clean(text: str, limit_name: str) -> str:
    """Control chars out (newlines kept) · spaces folded · trimmed · cut at the tw_limits limit."""
    text = re.sub(r"[^\S\n]+", " ", re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", " ", text or "").replace("\r", ""))
    text = re.sub(r"\n[ ]*(\n[ ]*)+", "\n\n", text).strip()
    return text[:tw_settings.limit(limit_name)].strip()


def _inbound_auto(headers) -> bool:
    """Auto-Submitted ≠ no (RFC 3834) → an automatic email (never answered, never a ticket)."""
    if isinstance(headers, dict):
        pairs = headers.items()
    elif isinstance(headers, list):   # [{name, value}, …]
        pairs = [(h.get("name"), h.get("value")) for h in headers if isinstance(h, dict)]
    else:
        return False
    for k, v in pairs:
        if isinstance(k, str) and k.lower() == "auto-submitted":
            return str(v).strip().lower() not in ("", "no")
    return False


def _inbound_handle(raw: bytes, svix_id: str) -> JSONResponse:
    try:
        event = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return api_ok({"handled": False})
    if not isinstance(event, dict) or event.get("type") != "email.received" or not isinstance(event.get("data"), dict):
        return api_ok({"handled": False})
    email_id = event["data"].get("email_id")
    if not isinstance(email_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", email_id):
        return api_ok({"handled": False})
    if support.inbound_seen(svix_id, email_id):
        return api_ok({"handled": False})

    def ignore(reason):
        out = support.inbound_ignore(svix_id, email_id, reason)
        print(f"[support] inbound {out}")
        return api_ok({"handled": False})

    kind, token = support.inbound_target(event["data"].get("to"))
    if kind is None:
        return ignore("ignored_recipient")
    msg, err = email_service.fetch_received(email_id, tw_settings.limit("support_inbound_fetch_max"))
    if msg is None:
        if err == "http 413":
            return ignore("ignored_size")
        print(f"[support] inbound fetch failed: {err}")
        return api_error(503, "fetch_failed", _tw_text("support.inbound.unavailable"))
    sender = support.bare_address(msg.get("from"))
    if not sender or sender.split("@", 1)[0] in _INBOUND_AUTO_FROM:
        return ignore("ignored_sender")
    if _inbound_auto(msg.get("headers")):
        return ignore("ignored_auto")
    if kind == "reply":
        auth_fail = _inbound_dmarc(msg)
        if auth_fail:
            return ignore(auth_fail)
        body = _inbound_clean(_inbound_reply_text(_inbound_text(msg)), "support_body_max")
    else:
        body = _inbound_clean(_inbound_text(msg), "support_body_max")
    if not body:
        return ignore("ignored_empty")
    if kind == "reply":
        out = support.inbound_reply(svix_id, email_id, token, sender, body, tw_settings.limit("support_open_max"),
                                    allow=_support_reply_allow)
    else:
        if not _rate_ok_all([("support_inbound_sender", sender), ("support_inbound_global", "all")]):
            return ignore("ignored_rate")
        subject = _inbound_clean(msg.get("subject") if isinstance(msg.get("subject"), str) else "",
                                 "support_subject_max").replace("\n", " ") or _tw_text("support.inbound.no_subject")
        out = support.inbound_new_ticket(svix_id, email_id, sender, subject, body)
    print(f"[support] inbound {out}")
    return api_ok({"handled": out in ("ticket", "message")})


@app.post("/webhooks/resend/inbound", dependencies=[Depends(_public_rate)])
async def resend_inbound_webhook(request: Request):
    secret = email_service.webhook_secret()
    if not secret:
        return api_error(503, "unavailable", _tw_text("support.inbound.unavailable"))
    max_bytes = tw_settings.limit("support_inbound_request_max")
    declared = request.headers.get("content-length") or ""
    if declared.isdigit() and int(declared) > max_bytes:
        return api_error(413, "too_large", _tw_text("limits.too_long", max=_fmt_number(max_bytes)))
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > max_bytes:
            return api_error(413, "too_large", _tw_text("limits.too_long", max=_fmt_number(max_bytes)))
    if not email_service.verify_webhook(secret, request.headers, raw):
        return api_error(401, "invalid_signature", _tw_text("support.inbound.unauthorized"))
    if not email_service.inbound_enabled():
        return api_ok({"handled": False})
    try:
        return await asyncio.to_thread(_inbound_handle, raw, request.headers.get("svix-id"))
    except Exception as e:
        raise _server_error("resend_inbound_webhook", e)


# ── admin inbox (support.manage) ──
def _support_audit(request: Request, public_id: str, old, new) -> None:
    def fmt(v):
        return ";".join(f"{k}={v[k]}" for k in sorted(v)) if isinstance(v, dict) else f"status={v}"
    request.state.audit_target = f"ticket={public_id}"
    request.state.audit_change = (fmt(old), fmt(new))


@app.get("/admin/support/tickets")
def admin_support_list(request: Request, status: str = "", category: str = "", priority: str = "",
                       page: int = 1, limit: int = 20, requester: str = "", q: str = "", sort: str = ""):
    claims = check_admin(request, SUPPORT_PERM)
    try:
        out = support.admin_list(status, category, priority, page, limit, requester, q, sort,
                                 email_search=_admin_email_view(claims))
    except support.SupportError as e:
        return _support_err(e)
    except Exception as e:
        raise _server_error("admin_support_list", e)
    out.update(statuses=list(support.STATUSES), categories=list(support.CATEGORIES),
               priorities=list(support.PRIORITIES), sorts=list(support.ADMIN_SORTS),
               requesters=list(support.REQUESTERS), next_statuses=list(support.ADMIN_REPLY_STATUSES))
    return api_ok(_admin_contacts(claims, out))


@app.get("/admin/support/counts")
def admin_support_counts(request: Request):
    """{new} — tickets nobody has answered yet (status new)."""
    check_admin(request, SUPPORT_PERM)
    try:
        return api_ok({"new": support.admin_count_new()})
    except Exception as e:
        raise _server_error("admin_support_counts", e)


@app.get("/admin/support/tickets/{public_id}")
def admin_support_get(request: Request, public_id: str):
    claims = check_admin(request, SUPPORT_PERM)
    try:
        return api_ok(_admin_contacts(claims, support.admin_get(public_id)))
    except LookupError:
        return _support_not_found()
    except Exception as e:
        raise _server_error("admin_support_get", e)


# ── reply notice (task 7.2b) — after the commit, in the background; the reply text never leaves the thread ──
# Guest: a new link (issue_guest_link keep=3) + support_guest_reply · account: bell support_reply (event_key per
# message — not in NOTIFICATION_EMAIL_TEMPLATES, so no second email) + its own support_reply email. Both emails
# are SECURITY (preferences / notification caps never apply). A failure = one log line (type only, never the
# address / token / link) — the reply stays 200.
def _support_reply_notice(n: dict) -> None:
    try:
        if n["user_id"] is None:
            # the link email itself (support_guest_link) or this notice switched off → no new link, no email
            if not (email_service.can_send("support_guest_link") and email_service.can_send("support_guest_reply")):
                print("[support] guest reply notice skipped: email type off or unavailable")
                return
            token = support.issue_guest_link(n["ticket_id"], keep=support.GUEST_LINK_KEEP)
            res = email_service.send_email(n["guest_email"], "support_guest_reply", {
                "ticket": n["public_id"],
                "link": support.track_link(email_service.get_settings()["site_url"], token)},
                reply_to=_support_reply_to(ticket_id=n["ticket_id"]))
            token = None
        else:
            link = support.ticket_path(n["public_id"])
            create_notification(int(n["user_id"]), "support_reply",
                                _tw_text("notif.support_reply.title", ticket=n["public_id"]),
                                _tw_text("notif.support_reply.body"), link, entity_type="support_ticket",
                                entity_id=n["ticket_id"],
                                event_key=f"support_reply:support_ticket:{n['ticket_id']}:{n['message_id']}")
            res = email_notify_user(int(n["user_id"]), "support_reply", {"ticket": n["public_id"], "link": link},
                                    reply_to=_support_reply_to(ticket_id=n["ticket_id"]))
        if not res.get("ok"):
            print(f"[support] reply notice email not sent: {res.get('code')}")
    except Exception as e:
        print(f"[support] reply notice failed: {type(e).__name__}")


@app.post("/admin/support/tickets/{public_id}/messages")
def admin_support_reply(request: Request, public_id: str, background_tasks: BackgroundTasks,
                        data: dict = Body(...)):
    request.state.audit_target = f"ticket={public_id}"   # a refused request (401 / 403) names the ticket too
    claims = check_admin(request, SUPPORT_PERM)
    body, bad = _support_text(data, "body", "support_body_max")
    if bad:
        return bad
    try:
        old, new, notice = support.admin_reply(public_id, str(claims.get("sub") or "-"), body,
                                               data.get("next_status"))
    except LookupError:
        return _support_not_found()
    except support.SupportError as e:
        return _support_err(e)
    except Exception as e:
        raise _server_error("admin_support_reply", e)
    _support_audit(request, public_id, old, new)
    background_tasks.add_task(_support_reply_notice, notice)   # after the commit + the reply (7.2b)
    return api_ok({"public_id": public_id, "status": new})


@app.put("/admin/support/tickets/{public_id}")
def admin_support_update(request: Request, public_id: str, data: dict = Body(...)):
    """{status?, priority?, category?} — the only writer of priority and of a category change."""
    request.state.audit_target = f"ticket={public_id}"
    check_admin(request, SUPPORT_PERM)
    try:
        old, new = support.admin_update(public_id, data.get("status"), data.get("priority"), data.get("category"))
    except LookupError:
        return _support_not_found()
    except support.SupportError as e:
        return _support_err(e)
    except Exception as e:
        raise _server_error("admin_support_update", e)
    _support_audit(request, public_id, old, new)
    return api_ok({"public_id": public_id, **new})


# ── Notification email preferences — the signed-in user's own (task 5.1c) ──
def _email_prefs_payload(uid: int) -> dict:
    """One switch per preference key — a key may cover several types (PREF_GROUPS, 5.1d)."""
    prefs = get_email_prefs(uid, email_service.PREF_TYPES)
    return {"types": [{"key": k, "enabled": prefs[k],
                       "available": any(email_service.can_send(m) for m in email_service.pref_members(k))}
                      for k in email_service.PREF_TYPES]}


@app.get("/my/email-notifications")
def my_email_prefs(token=Depends(verify_token)):
    uid = int(token.get("user_id") or 0)
    if not uid:
        return api_error(401, "unauthorized", "غير مصرح")
    try:
        return api_ok(_email_prefs_payload(uid))
    except Exception as e:
        raise _server_error("my_email_prefs", e)


@app.put("/my/email-notifications")
def my_email_prefs_save(data: dict = Body(...), token=Depends(verify_token)):
    """{types: {notify_*: bool}} — security emails are not a choice (always sent)."""
    uid = int(token.get("user_id") or 0)
    if not uid:
        return api_error(401, "unauthorized", "غير مصرح")
    t = data.get("types") if isinstance(data, dict) else None
    if not isinstance(t, dict) or not t:
        return api_error(422, "invalid_body", "صيغة الإعدادات غير صحيحة", "types")
    for k, v in t.items():
        if k not in email_service.PREF_TYPES:
            return api_error(422, "unknown_type", "نوع إشعار غير معروف", k)
        if not isinstance(v, bool):
            return api_error(422, "invalid_value", "القيمة لازم تكون تشغيل / إيقاف", k)
    try:
        set_email_prefs(uid, t)
        return api_ok(_email_prefs_payload(uid))
    except Exception as e:
        raise _server_error("my_email_prefs_save", e)


# ── Company settings — the signed-in company's own (task 5.1d) ──
@app.get("/company/settings")
def company_settings_get(token=Depends(verify_token)):
    """{notify_applicant_result} — company accounts only (403 otherwise)."""
    if token.get("user_type") != "co":
        return api_error(403, "forbidden", "هذا الإعداد لحسابات الشركات فقط")
    try:
        return api_ok(get_company_settings(int(token.get("user_id") or 0)))
    except Exception as e:
        raise _server_error("company_settings_get", e)


@app.put("/company/settings")
def company_settings_put(data: dict = Body(...), token=Depends(verify_token)):
    """{notify_applicant_result: bool} — «إبلاغ المتقدمين بالنتيجة النهائية» (default on)."""
    if token.get("user_type") != "co":
        return api_error(403, "forbidden", "هذا الإعداد لحسابات الشركات فقط")
    v = data.get("notify_applicant_result") if isinstance(data, dict) else None
    if not isinstance(v, bool) or set(data) - {"notify_applicant_result"}:
        return api_error(422, "invalid_body", "صيغة الإعدادات غير صحيحة", "notify_applicant_result")
    try:
        return api_ok(set_company_settings(int(token.get("user_id") or 0), {"notify_applicant_result": v}))
    except Exception as e:
        raise _server_error("company_settings_put", e)


@app.post("/admin/email/test")
def admin_test_email(request: Request, data: dict = Body(...)):
    """Send the admin_test template to an address the admin chooses."""
    claims = check_admin(request, "settings.edit")
    to = (data.get("to") or "").strip() if isinstance(data.get("to"), str) else ""
    if not email_service.valid_address(to):
        return api_error(422, "invalid_email", "عنوان البريد غير صحيح", "to")
    res = email_service.send_email(to, "admin_test", {})
    print(f"[email] test email requested by admin sub={claims.get('sub')!r} result={res['code']}")
    if res["ok"]:
        return api_ok({"sent": True})
    if res["code"] == "unavailable":
        return api_error(503, "email_unavailable", _EMAIL_UNAVAILABLE_MSG)
    return api_error(502, "email_failed", "تعذّر إرسال الرسالة، راجع سجل الخادم")


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
        with db_conn() as conn:
            conn.run("SELECT 1")
        db_ok = True
    except Exception as e:
        print(f"[health] DB check failed: {e!r}")
    migrations = dict(_MIGRATION_STATUS)   # name → ok | failed (never error details)
    status = "ok" if db_ok and "failed" not in migrations.values() else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "migrations": migrations,
        "email": email_service.status(),   # configured | missing — never the key
        "storage": _storage_status(),      # configured | missing — never the URL / key (5.3a2)
        "scheduler": scheduler_heartbeat_status(),   # ok | stale — last successful cycle ≤ 10 min (6.3)
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

def _password_too_long(password, field: str):
    """None, or the 422 when the password is over LIMITS["password_max_bytes"] UTF-8 bytes
    (bcrypt ignores the rest — task 5.0h-2 · AUD-P2-17). Register / reset / change only — never login."""
    max_bytes = tw_limits.LIMITS["password_max_bytes"]
    if isinstance(password, str) and len(password.encode("utf-8")) > max_bytes:
        return _limit_error(422, "password_too_long", "limits.password_too_long", field, max=max_bytes)
    return None

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

@app.post("/auth/register")
def register(data: RegisterInput, request: Request):
    if data.terms_accepted is not True:
        return api_error(422, "terms_required", _tw_text("register.err.terms_required"), "terms_accepted")
    if data.user_type not in ("emp", "co", "edu"):
        raise HTTPException(400, detail="نوع الحساب غير صحيح")
    if not data.email.strip():
        raise HTTPException(400, detail="البريد الإلكتروني مطلوب")
    _pw_err = _password_policy_error(data.password)
    if _pw_err:
        raise HTTPException(400, detail=_pw_err)
    _pw_long = _password_too_long(data.password, "password")
    if _pw_long:
        return _pw_long

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
            first_name=first_name_val, middle_name=middle_name_val, last_name=last_name_val,
            terms_version=tw_terms.TERMS_VERSION,
        )
        token = _jwt_encode({"user_id": user.get("id"), "user_type": user.get("user_type"),
                             "tw_id": user.get("tw_id",""), "sv": 0})   # new account → session_version 0
        return {"status": "success", "user": user, "token": token}
    except EmailTakenError as e:
        raise HTTPException(409, detail=str(e))
    except Exception as e:
        raise _server_error("register", e)

@app.post("/auth/login")
def login(data: LoginInput, request: Request):
    if os.environ.get("LOG_CLIENT_IP") == "1":
        # Measurement only (ARCHITECTURE.md → Client IP Resolution) — headers + chosen IP, never body/email/password
        print(f"[client-ip] /auth/login xff={request.headers.get('X-Forwarded-For')!r} "
              f"x_real_ip={request.headers.get('X-Real-IP')!r} "
              f"peer={(request.client.host if request.client else None)!r} chosen={get_client_ip(request)!r}")
    if not data.email.strip() or not data.password:
        raise HTTPException(400, detail="البريد وكلمة المرور مطلوبان")
    ip = get_client_ip(request)
    held, locked = _login_reserve(data.email, ip)   # email · IP · IP + email (task 5.0h-2) — one text for all
    if held is None:
        return _limit_error(429, "login_locked", "limits.login_locked", minutes=_fmt_number(-(-locked // 60)))
    user = authenticate_user(data.email, data.password)
    if not user:   # the reservation stays — it is the failure count
        raise HTTPException(401, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة")
    _rate_release(held)
    _login_email_reset(data.email, ip)
    if user.pop("deleted", False):     # task 8.5a — right password only (a wrong one got the normal 401 above)
        return api_error(401, "account_deleted", _tw_text("auth.account_unavailable"))
    if user.pop("suspended", False):   # task 5.4 — a suspended account never gets a token
        return api_error(401, "account_suspended", "الحساب معلّق")
    sv = int(user.pop("session_version", 0) or 0)   # read with the password check — never sent to the client
    token = _jwt_encode({"user_id": user.get("id"), "user_type": user.get("user_type"),
                         "tw_id": user.get("tw_id",""), "sv": sv})
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
    pw_long = _password_too_long(data.new_password, "new_password")
    if pw_long:
        return pw_long
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
        state = set_user_password(uid, data.new_password)
        if state is None:
            raise HTTPException(404, detail="المستخدم غير موجود")
        _password_changed_cache_set(uid, state)
        _ws_revoke_user(uid, "password_changed")
        # Fresh token for THIS device — carries the new session_version, so it survives
        # the invalidation; every older JWT of this user is rejected from now on.
        new_token = _jwt_encode({"user_id": uid, "user_type": token.get("user_type"),
                                 "tw_id": token.get("tw_id") or "", "sv": state["sv"]})
    except (HTTPException, AccountFieldError):
        raise
    except Exception as e:
        print(f"[PUT /auth/password] ERROR user={uid}: {e}")
        raise HTTPException(500, detail="تعذّر تغيير كلمة المرور، حاول لاحقاً")
    print(f"[PUT /auth/password] changed user={uid} — older sessions invalidated")
    return {"ok": True, "status": "success", "token": new_token}

# ── Forgot password (task 5.1a · SYSTEMS_INDEX §1b) ──
# request: same reply for every address (never says whether it exists); lookup + token +
# email run AFTER the reply (BackgroundTasks) so the response time does not tell either.
# Limits on the shared _rate_store via _rate_ok: RATES pwreset_ip (per client IP — get_client_ip) +
# pwreset_email (per address) — admin-editable through tw_settings (task 4.2).
_PWRESET_INVALID_MSG = "رابط إعادة التعيين غير صالح أو انتهت صلاحيته، اطلب رابطاً جديداً"
_PWRESET_TOKEN_MAX = 200

class PasswordResetRequestInput(BaseModel):
    email: str = ""

class PasswordResetConfirmInput(BaseModel):
    token: str = ""
    new_password: str = ""

def _password_reset_send(email: str) -> None:
    """Background: existing account → new token (older ones die) + email. Logs never carry
    the address or the token."""
    try:
        user = get_user_for_password_reset(email)
        if not user:
            return
        token = password_reset_issue(user["id"])
        link = email_service.get_settings()["site_url"] + "/reset-password#token=" + token
        email_service.send_email(user["email"], "password_reset",
                                 {"name": user["full_name"], "link": link,
                                  "minutes": PASSWORD_RESET_TTL_MINUTES})
    except Exception as e:
        print(f"[password-reset] request failed: {type(e).__name__}")

@app.post("/auth/password-reset/request")
def password_reset_request(data: PasswordResetRequestInput, request: Request,
                           background_tasks: BackgroundTasks):
    email = (data.email or "").strip().lower()
    if not email:
        raise AccountFieldError("email", "required", "أدخل بريدك الإلكتروني")
    if not email_service.can_send("password_reset"):
        return api_error(503, "email_unavailable", _EMAIL_UNAVAILABLE_MSG)
    if not _rate_ok("pwreset_ip", get_client_ip(request)):
        return api_error(429, "rate_limited", "طلبات كثيرة، حاول مرة أخرى لاحقاً")
    # Per-email limit → silently no email (a 429 here would be the same for any address,
    # but the identical reply keeps one simple rule).
    if _rate_ok("pwreset_email", email) \
            and email_service.valid_address(email):
        background_tasks.add_task(_password_reset_send, email)
    return api_ok({"sent": True})

@app.post("/auth/password-reset/confirm")
def password_reset_confirm(data: PasswordResetConfirmInput, background_tasks: BackgroundTasks):
    pw_err = _password_policy_error(data.new_password)
    if pw_err:
        raise AccountFieldError("new_password", "weak_password", pw_err)
    pw_long = _password_too_long(data.new_password, "new_password")
    if pw_long:
        return pw_long
    token = (data.token or "").strip()
    if not token or len(token) > _PWRESET_TOKEN_MAX:
        return api_error(400, "invalid_token", _PWRESET_INVALID_MSG)
    try:
        user = password_reset_consume(token)   # single use — deleted even if expired
    except Exception as e:
        raise _server_error("password_reset_confirm", e)
    if not user:
        return api_error(400, "invalid_token", _PWRESET_INVALID_MSG)
    uid = int(user["id"])
    try:
        state = set_user_password(uid, data.new_password)   # also deletes every pending email token
    except Exception as e:
        raise _server_error("password_reset_confirm", e)
    _password_changed_cache_set(uid, state)   # every older JWT of this user → 401
    _ws_revoke_user(uid, "password_reset")
    _login_email_reset(user["email"], every_ip=True)   # the owner proved the inbox → every IP's pair lock
    background_tasks.add_task(email_service.send_email, user["email"], "password_changed",
                              {"name": user["full_name"]})
    print(f"[password-reset] password reset user={uid} — all sessions invalidated")
    return api_ok({"reset": True})

# ── Email change (task 5.1b · SYSTEMS_INDEX §1c) ──
# request (JWT owner): new address + current password → link to the NEW address (one-time
# token, same table / code as the password reset — auth.email_token_*). users.email changes
# only on confirm; then the OLD address gets an «email changed» notice. "Taken" → EmailTakenError
# at request time and again at confirm time (race — UNIQUE index).
_EMAILCHANGE_USER_LIMIT, _EMAILCHANGE_USER_WINDOW = 5, 3600.0
_EMAILCHANGE_INVALID_MSG = "رابط تأكيد البريد الإلكتروني غير صالح أو انتهت صلاحيته، اطلب تغيير البريد من جديد"
_EMAILCHANGE_TAKEN_MSG = "البريد الإلكتروني مستخدم لحساب آخر"

class EmailChangeRequestInput(BaseModel):
    new_email: str = ""
    current_password: str = ""

class EmailChangeConfirmInput(BaseModel):
    token: str = ""

@app.post("/auth/email-change/request")
def email_change_request_ep(data: EmailChangeRequestInput, token=Depends(verify_token)):
    uid = int(token["user_id"])
    new_email = (data.new_email or "").strip().lower()
    if not new_email:
        raise AccountFieldError("new_email", "required", "أدخل البريد الإلكتروني الجديد")
    if not email_service.valid_address(new_email):
        raise AccountFieldError("new_email", "invalid_email", "صيغة البريد الإلكتروني غير صحيحة")
    if not data.current_password:
        raise AccountFieldError("current_password", "required", "أدخل كلمة المرور الحالية")
    if not email_service.can_send("email_change"):
        return api_error(503, "email_unavailable", _EMAIL_UNAVAILABLE_MSG)
    # Counted before the password check — also caps password guessing through this form.
    if not _rate_hit(f"email-change-user:{uid}", _EMAILCHANGE_USER_LIMIT, _EMAILCHANGE_USER_WINDOW):
        return api_error(429, "rate_limited", "طلبات كثيرة، حاول مرة أخرى لاحقاً")
    try:
        ok = check_user_password(uid, data.current_password)
        if ok is None:
            raise HTTPException(404, detail="المستخدم غير موجود")
        if not ok:
            raise AccountFieldError("current_password", "wrong_password", "كلمة المرور الحالية غير صحيحة")
        user = get_user_by_id(uid) or {}
        if (user.get("email") or "").strip().lower() == new_email:
            raise AccountFieldError("new_email", "same_email", "هذا هو بريدك الإلكتروني الحالي")
        link_token = email_change_request(uid, new_email)
    except EmailTakenError:
        raise AccountFieldError("new_email", "email_taken", _EMAILCHANGE_TAKEN_MSG)
    except (HTTPException, AccountFieldError):
        raise
    except Exception as e:
        raise _server_error("email_change_request", e)
    link = email_service.get_settings()["site_url"] + "/confirm-email#token=" + link_token
    res = email_service.send_email(new_email, "email_change",
                                   {"name": user.get("full_name") or "", "link": link,
                                    "minutes": EMAIL_TOKEN_TTL_MINUTES})
    if not res.get("ok"):
        return api_error(502, "email_failed", "تعذّر إرسال رابط التأكيد، حاول مرة أخرى لاحقاً")
    print(f"[email-change] link sent user={uid}")
    return api_ok({"sent": True})

@app.post("/auth/email-change/confirm")
def email_change_confirm(data: EmailChangeConfirmInput, background_tasks: BackgroundTasks):
    """No JWT: the link may be opened on another device. The token is the proof (it reached
    the new inbox). Single use — consumed even when the address turns out taken."""
    tok = (data.token or "").strip()
    if not tok or len(tok) > _PWRESET_TOKEN_MAX:
        return api_error(400, "invalid_token", _EMAILCHANGE_INVALID_MSG)
    try:
        changed = email_change_apply(tok)
    except EmailTakenError:
        return api_error(409, "email_taken", _EMAILCHANGE_TAKEN_MSG)
    except Exception as e:
        raise _server_error("email_change_confirm", e)
    if not changed:
        return api_error(400, "invalid_token", _EMAILCHANGE_INVALID_MSG)
    uid = int(changed["id"])
    by_admin = bool(changed.get("by_admin"))
    if by_admin:   # task 8.3 — session_version bumped with the email: every older JWT → 401 now
        _end_user_sessions(uid, changed.get("state"), "admin_email_change")
    _cache_del('profile:' + str(uid))
    _login_email_reset(changed["old_email"])
    background_tasks.add_task(email_service.send_email, changed["old_email"],
                              "email_changed_admin" if by_admin else "email_changed",
                              {"name": changed["full_name"]})
    print(f"[email-change] email changed user={uid}" + (" by admin — sessions ended" if by_admin else ""))
    return api_ok({"changed": True, "signed_out": by_admin})

# Display-name length cap — same 100-char limit as the other name input (/profession-suggestions).
_FULL_NAME_MAX = 100

@app.put("/auth/user/{user_id}/name")
def update_user_name(user_id: int, data: dict = Body(...), token=Depends(verify_token)):
    """co / edu display-name change. emp names go through first/last (G-contract,
    docs/rules/profile-v2.md) → same 422 emp_name_mutation_forbidden as PUT /profile."""
    # User can only update their own name
    if str(token.get('user_id','')) != str(user_id):
        raise HTTPException(403, "Unauthorized")
    if token.get('user_type') == 'emp':
        return JSONResponse(status_code=422, content={
            "errors": [{"field": "full_name", "code": "emp_name_mutation_forbidden",
                        "message": "لتغيير الاسم استخدم حقول الاسم الأول والعائلة"}],
            "detail": {"ok": False, "field": "full_name", "code": "emp_name_mutation_forbidden",
                       "error": "لتغيير الاسم استخدم حقول الاسم الأول والعائلة"}})
    full_name = _norm_name(data.get("full_name") if isinstance(data.get("full_name"), str) else "")
    if not full_name:
        raise HTTPException(400, "الاسم مطلوب")
    if len(full_name) > _FULL_NAME_MAX:
        raise HTTPException(400, f"الاسم طويل جداً — {_FULL_NAME_MAX} حرف كحد أقصى")
    try:
        validate_professional_text(full_name, "full_name")
    except ContentValidationError as e:
        return JSONResponse(status_code=422, content={
            "errors": [{"field": "full_name", "code": "content_violation", "message": e.message}],
            "detail": {"status": "error", "message": e.message, "field": "full_name"}})
    try:
        with db_conn() as conn:
            conn.run("UPDATE users SET full_name=:name WHERE id=:uid",
                     name=full_name, uid=user_id)
        return {"success": True}
    except Exception as e:
        raise _server_error("update_user_name", e)

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
    _404_if_hidden(token.get("user_id"), uid, "المستخدم غير موجود")
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "user_type": user["user_type"],
        "tw_id": user["tw_id"]
    }

# ══════════════════════════════════════════
# Profile
# ══════════════════════════════════════════
@app.get("/profile/{user_id}", dependencies=[Depends(_public_rate)])
def public_profile(user_id: str, request: Request):
    try:
        uid = int(user_id)
        profile = get_public_profile(uid)
    except ValueError:
        profile = get_profile_by_tw_id(user_id)
    if not profile:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    _404_if_hidden(_optional_viewer_id(request), profile["id"], "الملف الشخصي غير موجود")

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
    # Record view only for logged-in non-owner viewers (dedup window = RATES["view_count"], in record_profile_view)
    if viewer_type == "public-user" and token_uid:
        try:
            record_profile_view(profile_id, int(token_uid), tw_settings.rate("view_count")[1])
        except Exception as e:   # a side effect — the page still loads, the failure is logged (task 5.0e)
            print(f"[profile_view] record FAILED viewed={profile_id} viewer={token_uid}: {type(e).__name__}: {e}")
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
            "can_message": can_send_message(int(token_uid), profile_id)["allowed"],   # 5.0g — the one rule
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
    _interest_unknown = False   # read failed — never reported as «not interested» (task 5.0e)
    if viewer_type == "public-user" and token_uid and target_user_type == "emp":
        try:
            _actor_utype = payload.get("user_type", "emp") if payload else "emp"
            if _actor_utype == "co":
                _interest_active = is_candidate_saved(int(token_uid), profile_id)
            else:
                _interest_active = is_profile_interest_active(int(token_uid), profile_id)
        except Exception as e:
            _interest_unknown = True
            print(f"[profile_interest] read FAILED actor={token_uid} target={profile_id}: {type(e).__name__}: {e}")

    if viewer_type == "owner" or target_user_type != "emp":
        viewer_action = {"hidden": True,  "can_interact": False, "is_active": False, "label": "", "type": ""}
    elif _interest_unknown:
        # State unknown → no button (a toggle from a wrong state would save / remove the opposite).
        viewer_action = {"hidden": True, "can_interact": False, "is_active": None, "label": "", "type": "",
                         "error": "interest_unavailable"}
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

@app.get("/profile/{user_id}/metrics", dependencies=[Depends(_public_rate)])
def profile_metrics(user_id: str, request: Request):
    """Read-only unified metrics endpoint. Does NOT record a view.
    Returns all profile counters + score + viewer.is_following in one request."""
    try:
        uid = int(user_id)
    except ValueError:
        uid = get_user_id_by_tw_id(user_id)
    if not uid:
        raise HTTPException(404, detail="الملف الشخصي غير موجود")
    _404_if_hidden(_optional_viewer_id(request), uid, "الملف الشخصي غير موجود")

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
        # task 8.5a — the counters = the followers / following lists (bs.active_sql: no suspended / deleted account)
        followers_count  = conn.run("SELECT COUNT(*) FROM profile_follows pf WHERE pf.followed_id=:uid AND "
                                    + bs.active_sql("pf.follower_id"), uid=uid)[0][0]
        following_count  = conn.run("SELECT COUNT(*) FROM profile_follows pf WHERE pf.follower_id=:uid AND "
                                    + bs.active_sql("pf.followed_id"), uid=uid)[0][0]
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


# ══ Blocks + Suspension — visibility guard (task 5.4 · blocks_suspension.py · SYSTEMS_INDEX §25f) ══
# A hidden account (suspended, or a block either way) answers exactly like a missing one: 404 with the
# endpoint's own «غير موجود» text — never a «blocked» message (the blocked side is never told).

def _optional_viewer_id(request: Request) -> int:
    """Signed-in viewer of a public read (0 = guest / invalid token)."""
    auth_header = request.headers.get("Authorization", "")
    payload = _jwt_decode(auth_header[7:]) if auth_header.startswith("Bearer ") else {}
    try:
        return int((payload or {}).get("user_id") or 0)
    except (TypeError, ValueError):
        return 0

def _404_if_hidden(viewer_id, target_id, detail: str) -> None:
    try:
        hidden = bs.is_hidden(viewer_id, target_id)
    except Exception as e:
        raise _server_error("account_visibility", e)
    if hidden:
        raise HTTPException(404, detail)


# ══ Follow System (SYSTEMS_INDEX §20 · PR 3.5) ══
# ONE rule: any signed-in account (emp / co / edu) follows any other account, never
# itself. Guest → 401 (verify_token) → the page sends them to login. One table:
# profile_follows. The /company/follow/* aliases were removed in PR 3.9.

def _resolve_account_id(raw: str) -> int:
    """Numeric users.id or tw_id → users.id. 404 when unknown."""
    raw = (raw or "").strip()
    if raw.isascii() and raw.isdigit() and len(raw) <= 18:
        with db_conn() as conn:
            rows = conn.run("SELECT id FROM users WHERE id = :uid", uid=int(raw))
        uid = rows[0][0] if rows else None
    else:
        uid = get_user_id_by_tw_id(raw)
    if not uid:
        raise HTTPException(404, "الحساب غير موجود")
    return int(uid)


def _follow_set(token: dict, target_raw: str, follow: bool) -> dict:
    """The only follow / unfollow action → {is_following, followers_count}."""
    viewer_id = token.get("user_id")
    if not viewer_id:
        raise HTTPException(401, "رمز غير صالح")
    target_id = _resolve_account_id(target_raw)
    if not follow:
        return {"is_following": False, "followers_count": unfollow_profile(int(viewer_id), target_id)}
    if int(viewer_id) == target_id:
        raise HTTPException(400, "لا يمكنك متابعة نفسك")
    _404_if_hidden(viewer_id, target_id, "الحساب غير موجود")
    try:
        count = follow_profile(int(viewer_id), target_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    print(f"[follow] user={viewer_id} → {target_id} followers={count}")
    return {"is_following": True, "followers_count": count}


@app.post("/profile/{user_id}/follow")
def profile_follow(user_id: str, token=Depends(verify_token)):
    return {"status": "success", **_follow_set(token, user_id, True)}


@app.delete("/profile/{user_id}/follow")
def profile_unfollow(user_id: str, token=Depends(verify_token)):
    return {"status": "success", **_follow_set(token, user_id, False)}


@app.get("/profile/{user_id}/follow", dependencies=[Depends(_public_rate)])
def profile_follow_state(user_id: str, request: Request):
    """Follow state of any account: counters + viewer.is_following. Public (guest → false)."""
    target_id = _resolve_account_id(user_id)
    viewer_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _jwt_decode(auth_header[7:])
        if payload:
            viewer_id = payload.get("user_id")
    _404_if_hidden(viewer_id, target_id, "الحساب غير موجود")
    return api_ok(get_follow_state(target_id, viewer_id))


_VALID_FOLLOW_TYPES = {"all", "emp", "co", "edu"}

@app.get("/profile/{user_id}/followers", dependencies=[Depends(_public_rate)])
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
    _404_if_hidden(viewer_id, profile_id, "الملف الشخصي غير موجود")

    result = get_profile_followers_list(profile_id, viewer_id, limit, offset, type)
    return {"status": "success", **result}


@app.get("/profile/{user_id}/following", dependencies=[Depends(_public_rate)])
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
    _404_if_hidden(viewer_id, profile_id, "الملف الشخصي غير موجود")

    result = get_profile_following_list(profile_id, viewer_id, limit, offset, type)
    return {"status": "success", **result}


# ══ User Blocks (task 5.4 · blocks_suspension.py · SYSTEMS_INDEX §25f) ══
# JWT required. Every read / write is the caller's own blocks (blocker_id = JWT user). Blocking is silent:
# no notification, no message to the blocked side; follows of both directions are removed; job applications
# are untouched. The list lives in /settings («المحظورون»).

def _block_target(token: dict, target_raw: str):
    """→ (me, target id) after the per-account rate (RATES["block_set"]) — or (None, error response)."""
    try:
        me = int(token.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(401, "رمز غير صالح")
    if not _rate_ok("block_set", me):
        return None, _rate_limited()
    return me, _resolve_account_id(target_raw)


@app.get("/blocks")
def blocks_list(limit: int = 20, offset: int = 0, token=Depends(verify_token)):
    try:
        me = int(token.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(401, "رمز غير صالح")
    limit = max(1, min(int(limit), tw_settings.limit("blocks_page_max")))
    try:
        return api_ok(bs.list_blocked(me, limit, max(0, int(offset))))
    except Exception as e:
        raise _server_error("blocks_list", e)


@app.put("/blocks/{user_id}")
def block_user(user_id: str, token=Depends(verify_token)):
    me, target = _block_target(token, user_id)
    if me is None:
        return target
    try:
        return api_ok(bs.block(me, target))
    except bs.BlockError as e:
        return api_error(e.status, e.code, _tw_text("block.err." + e.code))
    except Exception as e:
        raise _server_error("block_user", e)


@app.delete("/blocks/{user_id}")
def unblock_user(user_id: str, token=Depends(verify_token)):
    me, target = _block_target(token, user_id)
    if me is None:
        return target
    try:
        return api_ok(bs.unblock(me, target))
    except Exception as e:
        raise _server_error("unblock_user", e)


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

    result = remove_profile_interest(int(actor_id), target_id)   # DB error → logged + success False
    if not result.get("success"):   # never «success» when the row was not deleted (task 5.0e)
        raise HTTPException(500, _SERVER_ERROR_MSG)

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


@app.get("/professions", dependencies=[Depends(_public_rate)])
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

@app.get("/skills/catalog", dependencies=[Depends(_public_rate)])
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
    return _apply_profile_update(user_id, data.dict(exclude_unset=True),
                                 token.get('user_type'), "PUT /profile", _t0)


def _apply_profile_update(user_id: int, payload: dict, user_type: str, tag: str, _t0: float):
    """The one profile-update path (validation + save + error shapes) — PUT /profile/{id}
    (owner JWT) and PUT /admin/profile/{id} (check_admin, PR 2B). `user_type` is the
    TARGET account's type; the caller has already authorised the write."""
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
        print(f"[{tag}] ✅ user={user_id} fields={updated_keys} — {_time.time()-_t0:.3f}s total")
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
        print(f"[{tag}] ValueError user={user_id}: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")
    except Exception as e:
        print(f"[{tag}] ERROR user={user_id}: {e}")
        raise HTTPException(500, detail="خطأ في الخادم")


@app.put("/admin/profile/{user_id}")
def admin_update_profile(user_id: int, data: ProfileUpdateInput, request: Request):
    """Admin edits a user's profile (admin-view.html). Admin JWT only (check_admin) —
    same validation as PUT /profile/{id} via _apply_profile_update (no admin-only rules);
    the rules follow the TARGET account's user_type (e.g. emp → no full_name)."""
    _t0 = _time.time()
    claims = check_admin(request, "users.edit")
    try:
        with db_conn() as conn:
            rows = conn.run("SELECT user_type FROM users WHERE id = :uid", uid=user_id)
    except Exception as e:
        raise _server_error("admin_update_profile", e)
    if not rows:
        raise HTTPException(404, "المستخدم غير موجود")
    payload = data.dict(exclude_unset=True)
    print(f"[ADMIN] profile edit by {claims.get('sub')} → user={user_id} fields={list(payload.keys())}")
    out = _apply_profile_update(user_id, payload, rows[0][0], "PUT /admin/profile", _t0)
    return _admin_contacts(claims, out) if isinstance(out, dict) else out   # 422 JSONResponse unchanged


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
        raise _server_error("add_user_skill", e)

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
        raise _server_error("delete_user_skill", e)

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
        raise _server_error("add_user_lang", e)

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
        raise _server_error("delete_user_lang", e)

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
        raise _server_error("add_user_link", e)

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
        raise _server_error("delete_user_link", e)

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
        too_long = _too_long(data.content, "message_max", "content")   # task 5.0h — before any DB work
        if too_long:
            return too_long
        if not _rate_ok("message_send", sender_id):   # task 5.0h-2 — after the length check, before the DB
            return _rate_limited()

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
            # 5.1c — still unread after N minutes → one email (scheduler job; sync DB → threadpool)
            background_tasks.add_task(schedule_message_email, data.receiver_id, sender_id, msg_id)

        _t_end = time.perf_counter()
        _timing = {
            **db_timing,
            "ws_ms":    round((_t_end - _t_db) * 1000),
            "badge_ms": 0,   # deferred to background on cold path; skipped on hot path
            "total_ms": round((_t_end - _t0)   * 1000),
        }
        print(f"[TW-TIMING] send_msg #{msg_id}: {_timing}")

        return {"status": "success", "message": msg}
    except MessagePolicyError as e:
        return _message_policy_error(e)
    except HTTPException:
        raise
    except Exception as e:
        raise _server_error("send_msg", e)


# ── Conversation Policy (task 5.0g — auth.can_send_message · docs/rules/messenger.md) ──
def _message_policy_error(e: MessagePolicyError) -> JSONResponse:
    """Refused send / end → {ok:false, error:{code, message}} — message = the twT text (admin override wins)."""
    return api_error(e.status, e.code, _tw_text(MESSAGE_POLICY_REASONS.get(e.code, "msg.policy.forbidden")))


@app.get("/messages/can-send/{other_id}")
def message_can_send(other_id: int, token=Depends(verify_token)):
    """The «مراسلة» button + composer state — the same can_send_message() the send runs."""
    me = int(token.get("user_id") or 0)
    if not me:
        raise HTTPException(401, "غير مصرح")
    try:
        p = can_send_message(me, other_id)
    except Exception as e:
        raise _server_error("message_can_send", e)
    return api_ok({"can_message": p["allowed"], "reason": p["reason"],
                   "reason_key": MESSAGE_POLICY_REASONS.get(p["reason"]) if p["reason"] else None,
                   "ended": p["ended"], "can_end": p["can_end"]})


@app.post("/messages/conversations/{other_id}/end")
def message_end_conversation(other_id: int, token=Depends(verify_token)):
    """A company ends its conversation with an emp (account types from the DB). No notification."""
    me = int(token.get("user_id") or 0)
    if not me:
        raise HTTPException(401, "غير مصرح")
    try:
        return api_ok(end_conversation(me, other_id))
    except MessagePolicyError as e:
        return _message_policy_error(e)
    except Exception as e:
        raise _server_error("message_end_conversation", e)

@app.get("/messages/conversations/{user_id}")
def get_convs(user_id: int, token=Depends(verify_token)):
    if int(token.get("user_id") or 0) != user_id:
        raise HTTPException(403, "غير مصرح")
    try:
        convs = get_conversations(user_id)
        return {"status": "success", "conversations": convs}
    except Exception as e:
        print(f"[get_convs] user_id={user_id} error={type(e).__name__}: {e}")
        raise _server_error("get_convs", e)

@app.get("/messages/unread/{user_id}")
def unread_msgs(user_id: int, token=Depends(verify_token)):
    if int(token.get("user_id") or 0) != user_id:
        raise HTTPException(403, "غير مصرح")
    try:
        count = get_unread_count(user_id)
        return {"status": "success", "count": count}
    except Exception as e:
        raise _server_error("unread_msgs", e)

@app.get("/messages/{user_id}/{other_id}")
async def get_msgs(user_id: int, other_id: int, token=Depends(verify_token)):
    if int(token.get("user_id") or 0) != user_id:
        raise HTTPException(403, "غير مصرح")
    try:
        # Hidden / missing peer → MessagePolicyError not_found (404) before any read mark or WS event (8.4c-0b)
        msgs, newly_read_ids = await asyncio.to_thread(get_messages, user_id, other_id)
        if newly_read_ids:
            await ws_manager.send_to_user(other_id, {
                "type": "status_update",
                "ids": newly_read_ids,
                "status": "read"
            })
        return {"status": "success", "messages": msgs}
    except MessagePolicyError as e:
        return _message_policy_error(e)
    except Exception as e:
        raise _server_error("get_msgs", e)



@app.get("/notifications/{user_id}/unread-count")
def notifications_unread_count(user_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    try:
        count = get_unread_notifications(user_id)
        return {"ok": True, "data": {"count": count}}
    except Exception as e:
        raise _server_error("notifications_unread_count", e)

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
        raise _server_error("user_notifications", e)

@app.put("/notifications/{user_id}/read")
def read_notifications(user_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    try:
        mark_notifications_read(user_id)
        return {"status": "success"}
    except Exception as e:
        raise _server_error("read_notifications", e)

@app.put("/notifications/{user_id}/read/{notif_id}")
def read_single_notification(user_id: int, notif_id: int, token=Depends(verify_token)):
    tok_uid = int(token.get("user_id"))
    if tok_uid != user_id:
        raise HTTPException(403, "Forbidden")
    try:
        mark_notification_read(user_id, notif_id)
        return {"status": "success"}
    except Exception as e:
        raise _server_error("read_single_notification", e)

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


def _storage_status() -> str:
    """/health → storage: configured | missing (reasons stay in the startup log, never the values)."""
    try:
        return "missing" if (_supabase_url_status()[1] or _supabase_key_status()[2]) else "configured"
    except Exception as e:
        print(f"[health] storage status failed: {type(e).__name__}")
        return "missing"


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


# ── Storage delete (task 8.5c — docs/rules/upload.md rule 11) ──
# The ONE delete of a storage object (+ its companion list), same settings as the uploads (_supabase_base_url /
# _supabase_auth_headers). Sync (the scheduler's account purge runs in a worker thread). 404 = already gone =
# success · anything else = failure, logged with bucket + status only (never the key, a signed URL or a body).
_STORAGE_TIMEOUT_S = 15
_STORAGE_LIST_PAGE = 100
_STORAGE_LIST_MAX_PAGES = 50


def _storage_not_found(r) -> bool:
    """404 — or the older Supabase shape: 400 with {"statusCode": "404"} in the body."""
    if r.status_code == 404:
        return True
    if r.status_code == 400:
        try:
            return str((r.json() or {}).get("statusCode")) == "404"
        except Exception:
            return False
    return False


def storage_delete(bucket: str, name: str) -> dict:
    """DELETE {base}/storage/v1/object/{bucket}/{name} → {ok, status, reason}. ok = deleted or not there (404)."""
    import httpx
    base, auth_headers = _supabase_base_url(), _supabase_auth_headers()
    if not base or not auth_headers:
        print(f"[storage] delete bucket={bucket}: storage not configured")
        return {"ok": False, "status": None, "reason": "storage_unavailable"}
    try:
        with httpx.Client(timeout=_STORAGE_TIMEOUT_S) as client:
            r = client.delete(f"{base}/storage/v1/object/{bucket}/{name}", headers=auth_headers)
    except Exception as e:
        print(f"[storage] delete bucket={bucket} error: {type(e).__name__}")
        return {"ok": False, "status": None, "reason": "network"}
    if r.status_code in (200, 204) or _storage_not_found(r):
        return {"ok": True, "status": r.status_code, "reason": None}
    print(f"[storage] delete bucket={bucket} rejected status={r.status_code}")
    return {"ok": False, "status": r.status_code, "reason": "rejected"}


def storage_list(bucket: str, prefix: str):
    """Object names in `bucket` that start with `prefix` (flat bucket — PR-7a names) → list | None (failure)."""
    import httpx
    base, auth_headers = _supabase_base_url(), _supabase_auth_headers()
    if not base or not auth_headers:
        print(f"[storage] list bucket={bucket}: storage not configured")
        return None
    names = []
    try:
        with httpx.Client(timeout=_STORAGE_TIMEOUT_S) as client:
            for page in range(_STORAGE_LIST_MAX_PAGES):
                r = client.post(f"{base}/storage/v1/object/list/{bucket}", headers=auth_headers,
                                json={"prefix": "", "search": prefix, "limit": _STORAGE_LIST_PAGE,
                                      "offset": page * _STORAGE_LIST_PAGE,
                                      "sortBy": {"column": "name", "order": "asc"}})
                if r.status_code != 200:
                    print(f"[storage] list bucket={bucket} rejected status={r.status_code}")
                    return None
                items = r.json() or []
                names.extend(str(i.get("name") or "") for i in items if isinstance(i, dict))
                if len(items) < _STORAGE_LIST_PAGE:
                    return [n for n in names if n.startswith(prefix)]
    except Exception as e:
        print(f"[storage] list bucket={bucket} error: {type(e).__name__}")
        return None
    print(f"[storage] list bucket={bucket} more than {_STORAGE_LIST_MAX_PAGES} pages")
    return None


account_purge.set_storage(storage_delete, storage_list)


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
_KYC_EMAIL_MISMATCH_MSG = "رمز التحقق يُرسل إلى بريد حسابك فقط — لتغييره استخدم «تغيير البريد الإلكتروني» في الإعدادات"
_OTP_UNAVAILABLE = {"detail": {"code": "otp_delivery_unavailable", "message": "خدمة إرسال رمز التحقق غير متاحة حالياً"}}


def _otp_send_allowed(uid: int, channel: str, target: str, request: Request) -> bool:
    """Task 4.3 — KYC OTP send limits on top of the per-IP /kyc/* limit (_RATE_LIMITED_PATHS):
    RATES otp_send_user (account + channel) · otp_send_target (normalised email / phone, any
    account) · otp_send_ip (client IP, both channels). Called BEFORE any code is generated or
    stored and before delivery — refused → no new code and the current code + attempts stay."""
    tgt = _otp_norm_target(channel, target)
    return _rate_ok_all([("otp_send_user", f"{channel}:{int(uid)}"),
                         ("otp_send_target", f"{channel}:{tgt}"),
                         ("otp_send_ip", get_client_ip(request))])


def _otp_rate_limited() -> JSONResponse:
    return _limit_error(429, "otp_rate_limited", "limits.otp_rate_limited")


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
def kyc_send_email(data: KYCEmailInput, request: Request, token=Depends(verify_token)):
    # Fail Closed: no OTP generated or stored until a real provider is available.
    if not is_email_otp_delivery_available():
        return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
    try:
        uid = int(token.get("user_id"))
        user = get_user_by_id(uid)
        if not user:
            raise HTTPException(404, detail="المستخدم غير موجود")
        # The code goes to the account's own address only (verify checks users.email) —
        # never to an address typed in the request.
        account_email = (user.get("email") or "").strip().lower()
        if (data.email or "").strip().lower() != account_email:
            raise HTTPException(400, detail=_KYC_EMAIL_MISMATCH_MSG)
        if not _otp_send_allowed(uid, "email", account_email, request):
            return _otp_rate_limited()
        start_kyc(uid)
        code = send_email_code(uid, account_email)
        res = email_service.send_email(account_email, "kyc_email_otp",
                                       {"name": user.get("full_name") or "", "code": code,
                                        "minutes": otp_ttl_minutes()})
        code = None
        if not res.get("ok"):
            return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
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
def kyc_send_phone(data: KYCPhoneInput, request: Request, token=Depends(verify_token)):
    # Fail Closed: no OTP generated or stored until a real provider is available.
    if not is_phone_otp_delivery_available():
        return JSONResponse(status_code=503, content=_OTP_UNAVAILABLE)
    try:
        uid = int(token.get("user_id"))
        if not _otp_send_allowed(uid, "phone", data.phone, request):
            return _otp_rate_limited()
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
    except KycStateError as e:
        return api_error(409, "kyc_step", str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise _server_error("kyc_upload_docs", e)

@app.get("/admin/kyc")
def admin_get_kyc(request: Request):
    claims = check_admin(request, "kyc.review")
    try:
        # PR-7c: allowlisted fields only (auth._ADMIN_KYC_LIST_COLUMNS) — no OTP
        # codes, no document paths (those → GET /admin/kyc/{submission_id}/docs).
        submissions = _admin_contacts(claims, get_all_kyc_submissions())
        return {"status": "success", "submissions": submissions, "count": len(submissions)}
    except Exception as e:
        raise _server_error("admin_get_kyc", e)

@app.put("/admin/kyc/{user_id}/approve")
def admin_kyc_approve(user_id: int, data: KYCAdminInput, request: Request):
    check_admin(request, "kyc.review")
    try:
        result = admin_approve_kyc(user_id, data.note)
        return {"status": "success", **result}
    except KycStateError as e:
        return api_error(409, "kyc_not_in_review", str(e))
    except Exception as e:
        raise _server_error("admin_kyc_approve", e)

@app.put("/admin/kyc/{user_id}/reject")
def admin_kyc_reject(user_id: int, request: Request, data: dict = Body(...)):
    """Reject — body {reason: text for the user (required, trimmed, ≤ kyc_reject_reason_max),
    note?: internal admin note} (task 8.1). The user sees the reason on /settings only."""
    check_admin(request, "kyc.review")
    reason, note = data.get("reason"), data.get("note")
    if reason is not None and not isinstance(reason, str):
        return api_error(422, "invalid_value", _tw_text("admin.kyc.reject.err.reason"), "reason")
    if note is not None and not isinstance(note, str):
        return api_error(422, "invalid_value", _tw_text("admin.kyc.reject.err.note"), "note")
    reason = (reason or "").strip()
    if not reason:
        return api_error(422, "required", _tw_text("admin.kyc.reject.err.reason"), "reason")
    too_long = _too_long(reason, "kyc_reject_reason_max", "reason")
    if too_long:
        return too_long
    try:
        result = admin_reject_kyc(user_id, reason, (note or "").strip())
        return {"status": "success", **result}
    except KycStateError as e:
        return api_error(409, "kyc_not_in_review", str(e))
    except Exception as e:
        raise _server_error("admin_kyc_reject", e)

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
    check_admin(request, "kyc.review")
    row = await asyncio.to_thread(
        _current_image_urls,
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
    check_admin(request, "system.manage")
    dry = dry_run != 0
    if not dry and not (_supabase_base_url() and _supabase_auth_headers()):
        raise HTTPException(503, "خدمة رفع الصور غير متاحة حالياً")
    report = {}
    for col, select_sql, update_sql, kind_of in _DATA_IMAGE_TARGETS:
        try:
            rows = await asyncio.to_thread(_mig_run, select_sql)
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
                updated = await asyncio.to_thread(_mig_run, update_sql, new=new, k=row_key, old=old)
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


# ══════════════════════════════════════════
# Jobs & Match
# ══════════════════════════════════════════

@app.get("/jobs", dependencies=[Depends(_public_rate)])
def list_jobs(search: str = None, location: str = None,
               job_type: str = None, company_id: int = None):
    filters = {"search":search,"location":location,"job_type":job_type,"company_id":company_id}
    return get_jobs({k:v for k,v in filters.items() if v})

@app.get("/jobs/{job_id}", dependencies=[Depends(_public_rate)])
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
    # Owner decision (task 5.3j5): once published, a job cannot be edited by the company — the
    # applicants applied to what they saw. Status changes (pause / resume / close) and archive stay
    # (PATCH …/status · DELETE). Editing a published job = admin only (planned admin job page).
    user_id   = token.get("user_id")
    user_type = token.get("user_type")
    if not user_id:
        print(f"[SECURITY] INVALID_TOKEN: PUT /company/jobs/{job_id}")
        raise HTTPException(401, "رمز غير صالح")
    if user_type not in ("co", "edu"):
        print(f"[SECURITY] COMPANY_OWNERSHIP_FAILED: user_type={user_type} tried PUT /company/jobs/{job_id}")
        raise HTTPException(403, "شركات وجهات فقط")
    raise HTTPException(403, "لا يمكن تعديل الوظيفة بعد نشرها")

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
    except ReapplyLimitError as e:   # task 8.2a — re-applies per (applicant + job) in 7 days
        return _limit_error(429, "reapply_limit", "jobs.reapply.limit", max=_fmt_number(e.limit))
    except ApplicationStateError as e:   # task 8.2a — re-apply refused: a result (hired / rejected) exists
        return api_error(409, e.code, _tw_text(f"jobs.app_state.{e.code}"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "success", **result}


@app.post("/jobs/applications/{app_id}/withdraw")
def withdraw_job_application(app_id: int, token=Depends(verify_token)):
    """task 8.2a — the applicant withdraws their own application (identity from the JWT only).
    Not theirs / missing → 404 · hired / rejected / already withdrawn / job not open → 409.
    Cancels their upcoming appointments on this job; no notification to the company."""
    token_uid = token.get("user_id")
    if not token_uid:
        raise HTTPException(401, "رمز غير صالح")
    try:
        return api_ok(withdraw_application(app_id, int(token_uid)))
    except KeyError:
        return api_error(404, "not_found", _tw_text("jobs.withdraw.not_found"))
    except ApplicationStateError as e:
        return api_error(409, e.code, _tw_text(f"jobs.app_state.{e.code}"))
    except Exception as e:
        raise _server_error("withdraw_job_application", e)

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
    _require_org_account(token)

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
    _require_org_account(token)
    allowed_statuses = {"pending", "viewed", "accepted", "contacted", "interview", "hired", "rejected"}
    if data.status not in allowed_statuses:
        raise HTTPException(400, f"حالة غير صالحة. المسموح: {', '.join(sorted(allowed_statuses))}")
    try:
        result = update_application_status(app_id, data.status, actor_id=int(user_id))
        return result
    except ApplicationStateError as e:   # task 8.2a — withdrawn by the applicant
        return api_error(409, e.code, _tw_text(f"jobs.app_state.{e.code}"))
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        print(f"[SECURITY] APPLICATION_OWNERSHIP_FAILED: user {user_id} → app {app_id}: {e}")
        raise HTTPException(403, str(e))
    except RuntimeError as e:
        print(f"[ERROR] update_application_status app {app_id}: {e}")
        raise _server_error("update_app_status", e)


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
    _require_org_account(token)
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
        raise _server_error("promote_applicant", e)


@app.get("/admin/jobs")
def admin_list_jobs(request: Request, q: str = "", status: str = "", page: str = "1", limit: str = "20"):
    """Every job in every state (task 5.3j — #8: was the public feed). SYSTEMS_INDEX §25e."""
    check_admin(request, "jobs.manage")
    if status and status not in admin_insights.JOB_ADMIN_STATUSES:
        return api_error(422, "invalid_status", "حالة الوظيفة غير معروفة", field="status")
    if len(q) > admin_insights.USERS_Q_MAX:
        return api_error(422, "invalid_q", "نص البحث طويل", field="q")
    if not _admin_int(page, 1, 100000):
        return api_error(422, "invalid_page", "رقم الصفحة غير صالح", field="page")
    if not _admin_int(limit, 1, admin_insights.JOBS_PAGE_MAX):
        return api_error(422, "invalid_limit", "عدد العناصر غير صالح", field="limit")
    try:
        return api_ok(admin_insights.jobs_list(q=q, status=status, page=int(page), limit=int(limit)))
    except Exception as e:
        raise _server_error("admin_list_jobs", e)

# ── admin job actions (task 5.3j phase 2 — SYSTEMS_INDEX §25e). Each one tells the company (in-app
#    notification type job_admin). Audit rows come from admin_audit_middleware (writes under /admin/). ──
_JOB_ADMIN_NOTICE = {
    "hidden":      ("أخفت الإدارة وظيفتك", "«{title}» لم تعد تظهر للزوار. السبب: {reason}"),
    "unhidden":    ("أعادت الإدارة إظهار وظيفتك", "«{title}» تظهر في الموقع من جديد."),
    "reactivated": ("أعادت الإدارة تفعيل وظيفتك", "«{title}» نشطة الآن لمدة {days} يوماً."),
    "extended":    ("مدّدت الإدارة مدة وظيفتك", "أُضيف {days} يوماً إلى مدة «{title}»."),
    "paused":      ("أوقفت الإدارة التقديم على وظيفتك", "«{title}» موقوفة الآن، ومدتها محفوظة."),
    "resumed":     ("استأنفت الإدارة التقديم على وظيفتك", "«{title}» تستقبل الطلبات من جديد."),
    "closed":      ("أغلقت الإدارة وظيفتك", "«{title}» أُغلقت. السبب: {reason}"),
    "unarchived":  ("ألغت الإدارة أرشفة وظيفتك", "«{title}» رجعت إلى قائمة وظائفك."),
    "edited":      ("عدّلت الإدارة وظيفتك", "تم تعديل «{title}». السبب: {reason}"),
}
_ADMIN_JOB_STATUS = {"paused": "paused", "active": "resumed", "closed": "closed"}   # body status → notice


def _notify_company_job_admin(info: dict, kind: str, days: int = 0) -> bool:
    """In-app notification to the job's company — non-fatal (the action already happened)."""
    title, body = _JOB_ADMIN_NOTICE[kind]
    try:
        tw = _tw_id_for_user_id(info["company_id"])
        create_notification(
            user_id=info["company_id"], type_="job_admin", title=title,
            body=body.format(title=str(info.get("title") or "")[:80], reason=info.get("reason") or "", days=days),
            link=("/u/" + tw) if tw else "", entity_id=info["id"], entity_type="job")
        return True
    except Exception as e:
        print(f"[admin job] notify {kind} job={info.get('id')} failed: {type(e).__name__}: {e}")
        return False


def _admin_job_action(name: str, fn):
    try:
        return fn()
    except LookupError as e:
        return api_error(404, "not_found", str(e))
    except JobActionError as e:
        return api_error(409, "invalid_state", str(e))
    except ValueError as e:
        return api_error(422, "invalid_input", str(e))
    except Exception as e:
        raise _server_error(name, e)


def _job_out(info: dict) -> dict:
    exp = info.get("expires_at")
    return {"id": info["id"], "expires_at": exp.isoformat() if hasattr(exp, "isoformat") else exp}


@app.post("/admin/jobs/{job_id}/hide")
def admin_hide_job(job_id: int, request: Request, data: Optional[dict] = Body(default={})):
    check_admin(request, "jobs.manage")
    def run():
        info = admin_set_job_hidden(job_id, True, str((data or {}).get("reason") or ""))
        return api_ok({"id": info["id"], "hidden": True,
                       "notified": _notify_company_job_admin(info, "hidden")})
    return _admin_job_action("admin_hide_job", run)


@app.post("/admin/jobs/{job_id}/unhide")
def admin_unhide_job(job_id: int, request: Request):
    check_admin(request, "jobs.manage")
    def run():
        info = admin_set_job_hidden(job_id, False)
        return api_ok({"id": info["id"], "hidden": False,
                       "notified": _notify_company_job_admin(info, "unhidden")})
    return _admin_job_action("admin_unhide_job", run)


@app.post("/admin/jobs/{job_id}/reactivate")
def admin_reactivate_job_endpoint(job_id: int, request: Request, data: Optional[dict] = Body(default={})):
    check_admin(request, "jobs.manage")
    def run():
        info = admin_reactivate_job(job_id, (data or {}).get("duration_days"))
        return api_ok({**_job_out(info), "status": "active",
                       "notified": _notify_company_job_admin(info, "reactivated", info["duration_days"])})
    return _admin_job_action("admin_reactivate_job", run)


@app.post("/admin/jobs/{job_id}/extend")
def admin_extend_job_endpoint(job_id: int, request: Request, data: Optional[dict] = Body(default={})):
    check_admin(request, "jobs.manage")
    def run():
        days = (data or {}).get("duration_days")
        info = admin_extend_job(job_id, days)
        return api_ok({**_job_out(info), "notified": _notify_company_job_admin(info, "extended", int(days))})
    return _admin_job_action("admin_extend_job", run)


@app.post("/admin/jobs/{job_id}/status")
def admin_job_status(job_id: int, request: Request, data: Optional[dict] = Body(default={})):
    """Pause / resume / close from the admin — the same auth.set_job_status as the company (task 5.3j).
    Closing needs a reason (sent to the company). Reopening a closed job = /reactivate."""
    check_admin(request, "jobs.manage")
    def run():
        st = str((data or {}).get("status") or "")
        if st not in _ADMIN_JOB_STATUS:
            raise ValueError("الحالة يجب أن تكون: paused أو active أو closed")
        reason = str((data or {}).get("reason") or "").strip()
        if st == "closed" and not reason:
            raise ValueError("اكتب سبب الإغلاق")
        if len(reason) > JOB_HIDE_REASON_MAX:
            raise ValueError(f"السبب أطول من {JOB_HIDE_REASON_MAX} حرف")
        info = set_job_status(job_id, None, st)   # closed → active without a duration = 409 (use /reactivate)
        info["reason"] = reason
        return api_ok({**_job_out(info), "status": st,
                       "notified": _notify_company_job_admin(info, _ADMIN_JOB_STATUS[st])})
    return _admin_job_action("admin_job_status", run)


@app.get("/admin/jobs/{job_id}")
def admin_job_detail(job_id: int, request: Request):
    """One job for the admin job page (task 5.3j phase 4): every field + state + applicants (read only)."""
    check_admin(request, "jobs.manage")
    try:
        d = admin_insights.job_detail(job_id)
    except Exception as e:
        raise _server_error("admin_job_detail", e)
    if d is None:
        return api_error(404, "not_found", "الوظيفة غير موجودة")
    return api_ok(d)


@app.put("/admin/jobs/{job_id}")
def admin_update_job_endpoint(job_id: int, request: Request, data: Optional[dict] = Body(default={})):
    """Admin edit (owner decision 5.3j: after publishing only the admin edits). Body = the publish fields
    (JobInput — same model) + reason (required, sent to the company). Every applicant gets one notice per edit
    (without the reason). The duration is not edited here (/extend · /reactivate)."""
    check_admin(request, "jobs.manage")
    def run():
        body = dict(data or {})
        reason = str(body.pop("reason", "") or "")
        body.pop("duration_days", None)
        try:
            fields = JobInput(**body).dict()
        except ValidationError as e:
            loc = (e.errors() or [{}])[0].get("loc") or ["body"]
            raise ValueError("قيمة غير صالحة: " + str(loc[-1]))
        info = admin_update_job(job_id, fields, reason)
        return api_ok({"id": info["id"], "changed": info["changed"],
                       "notified": _notify_company_job_admin(info, "edited"),
                       "applicants_notified": notify_job_applicants_updated(info["id"], info["title"], info["edit_key"])})
    return _admin_job_action("admin_update_job", run)


@app.get("/admin/jobs/{job_id}/delete-preview")
def admin_job_delete_preview_endpoint(job_id: int, request: Request):
    """What DELETE /admin/jobs/{id} removes / detaches — shown in the delete confirm (task 5.3j phase 4)."""
    check_admin(request, "jobs.manage")
    return _admin_job_action("admin_job_delete_preview", lambda: api_ok(admin_job_delete_preview(job_id)))


@app.post("/admin/jobs/{job_id}/unarchive")
def admin_unarchive_job_endpoint(job_id: int, request: Request):
    check_admin(request, "jobs.manage")
    def run():
        info = admin_unarchive_job(job_id)
        return api_ok({"id": info["id"], "archived": False,
                       "notified": _notify_company_job_admin(info, "unarchived")})
    return _admin_job_action("admin_unarchive_job", run)


@app.delete("/admin/jobs/{job_id}")
def admin_delete_job(job_id: int, request: Request):
    # Hard delete (task 5.3j — #1): pipeline entries go in the same transaction (their FK is RESTRICT).
    check_admin(request, "jobs.manage")
    try:
        removed = admin_hard_delete_job(job_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise _server_error("admin_delete_job", e)
    return {"success": True, "removed": removed}


@app.get("/stats", dependencies=[Depends(_public_rate)])
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
            "jobs_count": conn.run("SELECT COUNT(*) FROM jobs j WHERE " + job_active_sql("j"))[0][0]
        }
    except Exception as e:
        raise _server_error("stats", e)
    finally:
        release_conn(conn)

# ══════════════════════════════════════════
# Admin Login - returns token
# ══════════════════════════════════════════
# Task 5.3a: the login answers under the panel path (<panel>/login) so no served file carries the
# panel prefix (the page posts relative to its own path — docs/rules/admin-shell.md). In _RATE_LIMITED_PATHS.
# Task 5.3b: the old fixed /tw-ctrl-login route is deleted (no page used it any more) → 404.
# Task 8.4b — two steps on the same route (docs/rules/admin-staff.md → Admin Login):
#   1) {password} (owner = ADMIN_TOKEN) · {email, password} (staff) → {step: "mfa", ticket}
#      owner without a bound app → {step: "enroll", ticket, secret, otpauth_uri}
#   2) {ticket, code} → {token} (code = authenticator or recovery code — recovery_remaining in the reply)
#      enroll → the first app code binds it → {token, recovery_codes} (shown once)
#   Every failure of a step = the same 401 (no hint whether the email exists / the staff member is active).
#   Lock per IP + per account on each step (RATES admin_login_* / admin_mfa_*) → 429, reserved atomically before
#   the check (task 8.4c-0 — _admin_reserve) · a ticket gives one token (jti burnt — _admin_ticket_take). The audit row names
#   the account (owner / staff:<id>) through request.state.audit_actor.
_ADMIN_LOGIN_FAIL = "Unauthorized"
# bcrypt hash of a random throwaway — an unknown email costs the same time as a wrong password
_ADMIN_DUMMY_HASH = None


def _admin_dummy_hash() -> str:
    global _ADMIN_DUMMY_HASH
    if _ADMIN_DUMMY_HASH is None:
        _ADMIN_DUMMY_HASH = _hash_password(secrets.token_hex(16))
    return _ADMIN_DUMMY_HASH


def _admin_lock_keys(step: str, ip: str, account: str) -> list:
    return [(f"admin_{step}_ip", ip), (f"admin_{step}_acct", account)]


def _admin_reserve(request: Request, step: str, ip: str, account: str, actor: str) -> list:
    """Task 8.4c-0 — check + count of every lock of the step in ONE locked step, BEFORE the slow check
    (bcrypt / DB): a full lock → 429, nothing counted. The hit stays when the attempt fails (that is the
    failure count) and is taken back on success (_rate_release) — parallel requests can never pass the limit."""
    held = _rate_reserve(_admin_lock_keys(step, ip, account))
    if held is None:
        request.state.audit_actor = actor
        raise HTTPException(status_code=429, detail=_tw_text("limits.rate_limited"))
    return held


def _admin_fail(request: Request, actor: str):
    """The same 401 for every failure — the reservation stays (counted)."""
    request.state.audit_actor = actor
    raise HTTPException(status_code=401, detail=_ADMIN_LOGIN_FAIL)


# Single-use tickets (task 8.4c-0): jti → [expires_at, used]. Taken for the time of one code check (a parallel
# request with the same ticket → 401), burnt after the first token, freed again when the code is wrong (the lock
# limits the tries). Memory under _rate_lock, expired entries dropped on use, at most mem_store_max_keys
# (full → refused, never an eviction) — one replica, like the rate limits (docs/rules/admin-staff.md rule 6).
_admin_tickets = {}


def _admin_ticket_take(claims: dict) -> bool:
    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti:
        return False
    now = _time.time()
    with _rate_lock:
        for k in [k for k, (exp, _) in _admin_tickets.items() if exp <= now]:
            del _admin_tickets[k]
        if jti in _admin_tickets or len(_admin_tickets) >= tw_settings.limit("mem_store_max_keys"):
            return False
        _admin_tickets[jti] = [float(claims.get("exp") or now + _ADMIN_TICKET_TTL), False]
        return True


def _admin_ticket_done(claims: dict, used: bool) -> None:
    with _rate_lock:
        entry = _admin_tickets.get(claims.get("jti"))
        if entry is not None and used:
            entry[1] = True
        elif entry is not None:
            del _admin_tickets[claims["jti"]]


def _admin_mfa_reset_today() -> bool:
    """ADMIN_MFA_RESET=YYYY-MM-DD equal to today (UTC) — anything else does nothing."""
    from datetime import datetime, timezone
    want = os.environ.get("ADMIN_MFA_RESET", "").strip()
    return bool(want) and want == datetime.now(timezone.utc).date().isoformat()


def _admin_login_password(data: AdminLoginInput, request: Request, ip: str) -> dict:
    password = data.password or ""
    email = (data.email or "").strip().lower()
    account = ("email:" + email) if email else admin_staff.OWNER
    held = _admin_reserve(request, "login", ip, account, admin_staff.OWNER if not email else "-")
    if not email:
        if not password or not hmac.compare_digest(password.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")):
            _admin_fail(request, admin_staff.OWNER)
        _rate_release(held)
        request.state.audit_actor = admin_staff.OWNER
        if _admin_mfa_reset_today():
            from datetime import datetime, timezone
            if admin_staff.owner_reset(datetime.now(timezone.utc).date().isoformat()):
                print("[admin-auth] ADMIN_MFA_RESET applied — owner MFA + recovery codes cleared, owner sessions ended")
                admin_insights.audit_record(actor=admin_staff.OWNER, action="admin_mfa_reset", target=None,
                                            status=200, ip=ip)
        st = admin_staff.owner_state()
        if st["enabled"]:
            return {"success": True, "step": "mfa", "ticket": _admin_ticket_issue(admin_staff.OWNER, st["sv"]),
                    "expires_in": _ADMIN_TICKET_TTL}
        pending = admin_staff.owner_begin_enroll()
        if not pending:   # bound between the two reads — ask for the code
            return {"success": True, "step": "mfa", "ticket": _admin_ticket_issue(admin_staff.OWNER, st["sv"]),
                    "expires_in": _ADMIN_TICKET_TTL}
        secret, sv = pending
        return {"success": True, "step": "enroll", "ticket": _admin_ticket_issue(admin_staff.OWNER, sv),
                "expires_in": _ADMIN_TICKET_TTL, "secret": secret,
                "otpauth_uri": admin_staff.otpauth_uri(secret, admin_staff.OWNER)}
    staff = admin_staff.staff_for_login(email)
    ok_pw = bool(password) and len(password.encode("utf-8")) <= 72 and _verify_password(
        password, (staff or {}).get("password_hash") or _admin_dummy_hash())
    actor = admin_staff.STAFF_PREFIX + str(staff["id"]) if staff else "-"
    if not (staff and ok_pw and staff["password_hash"] and staff["status"] == "active" and staff["mfa"]):
        _admin_fail(request, actor)
    _rate_release(held)
    request.state.audit_actor = actor
    return {"success": True, "step": "mfa", "ticket": _admin_ticket_issue(actor, staff["sv"]),
            "expires_in": _ADMIN_TICKET_TTL}


def _admin_login_code(data: AdminLoginInput, request: Request, ip: str) -> dict:
    claims = _admin_ticket_claims(data.ticket or "")
    sub = claims.get("sub") or ""
    request.state.audit_action = "admin_login_mfa"
    held = _admin_reserve(request, "mfa", ip, sub or "-", sub or "-")
    if not claims or (sub != admin_staff.OWNER and admin_staff.staff_id(sub) is None):
        _admin_fail(request, "-")
    if not _admin_ticket_take(claims):   # used already / in use by a parallel request
        _admin_fail(request, sub)
    out = None
    try:
        out = _admin_second_factor(request, sub, claims, data.code or "")
    finally:
        _admin_ticket_done(claims, used=out is not None)
    if out is None:
        _admin_fail(request, sub)
    _rate_release(held)
    return out


def _admin_second_factor(request: Request, sub: str, claims: dict, code: str):
    """The code of a held ticket → the token reply, or None (wrong code)."""
    if sub == admin_staff.OWNER and not admin_staff.owner_state()["enabled"]:
        codes = admin_staff.owner_confirm_enroll(code, claims["sv"])
        if not codes:
            return None
        request.state.audit_actor = sub
        print("[admin-auth] owner authenticator bound + recovery codes issued")
        return {"success": True, "token": _admin_jwt_issue(sv=claims["sv"]), "expires_in": _ADMIN_JWT_TTL,
                "recovery_codes": codes}
    res = admin_staff.verify_second_factor(sub, code, claims["sv"])
    if not res:
        return None
    request.state.audit_actor = sub
    if sub == admin_staff.OWNER:
        token = _admin_jwt_issue(sv=claims["sv"])
    else:
        sid = admin_staff.staff_id(sub)
        token = _admin_jwt_issue(sub=sub, role="staff", perms=[], sv=claims["sv"])
        admin_staff.staff_mark_login(sid)
    print(f"[admin-auth] admin session issued sub={sub} via={res['method']}")
    out = {"success": True, "token": token, "expires_in": _ADMIN_JWT_TTL}
    if res["method"] == "recovery":
        out["recovery_remaining"] = res["remaining"]
    return out


@app.post("/tw-ctrl-" + ADMIN_URL_TOKEN + "/login")
def admin_login(data: AdminLoginInput, request: Request):
    if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 32:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    if not _admin_jwt_secret_ok() or not admin_staff.mfa_key_ok():
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    ip = get_client_ip(request)
    try:
        if data.ticket is not None:
            return _admin_login_code(data, request, ip)
        return _admin_login_password(data, request, ip)
    except HTTPException:
        raise
    except Exception as e:
        raise _server_error("admin_login", e)

# ── Admin session endpoints (task 8.4c-1 · docs/rules/admin-staff.md rules 11–13) ──
@app.get("/admin/me")
def admin_me(request: Request):
    """Who is signed in + the effective perms (the menu hides what they cannot open — the server still checks
    every route). Never an email / phone / sv / secret."""
    claims = check_admin_session(request)
    owner = claims.get("role") == "admin"
    return {"kind": "owner" if owner else "staff", "name": None if owner else (claims.get("name") or ""),
            "perms": [admin_perms.OWNER] if owner else list(claims.get("perms") or []),
            "owner_only": sorted(admin_perms.OWNER_ONLY)}   # for the menu's allows() twin — the catalog stays in admin_perms.py


@app.post("/admin/step-up")
def admin_step_up(request: Request, data: dict = Body(...)):
    """Owner only: a fresh authenticator code or a recovery code → {grant, expires_in} (a 5-minute X-Admin-Stepup
    grant for THIS token). Same mfa locks as the login code step (_admin_reserve — reserved before the check,
    released on success). Wrong code → 401 · lock full → 429 · staff → 403. Audit row admin_step_up (middleware,
    never the code)."""
    claims = check_admin_session(request)
    if claims.get("role") != "admin" or claims.get("sub") != admin_staff.OWNER:
        raise HTTPException(status_code=403, detail="Forbidden")
    code = data.get("code") if isinstance(data, dict) else None
    code = code if isinstance(code, str) else ""
    held = _admin_reserve(request, "mfa", get_client_ip(request), admin_staff.OWNER, admin_staff.OWNER)
    try:
        res = admin_staff.verify_second_factor(admin_staff.OWNER, code, claims["sv"])
    except Exception as e:
        raise _server_error("admin_step_up", e)
    if not res:
        raise HTTPException(status_code=401, detail=_ADMIN_LOGIN_FAIL)
    _rate_release(held)
    print(f"[admin-auth] step-up granted sub={admin_staff.OWNER} via={res['method']}")
    out = {"grant": _admin_step_up_issue(admin_staff.OWNER, claims["sv"], request.headers.get("X-Admin-Token", "")),
           "expires_in": _ADMIN_STEPUP_TTL}
    if res["method"] == "recovery":
        out["recovery_remaining"] = res["remaining"]
    return out


@app.post("/admin/owner/recovery-codes")
def admin_owner_recovery_codes(request: Request, response: Response):
    """New owner recovery codes (settings.security → owner + step-up): the old ones are void at once, the 10 new
    ones are returned this one time (stored as SHA-256 only)."""
    claims = check_admin(request, "settings.security")
    try:
        codes = admin_staff.owner_new_recovery_codes(claims["sv"])
    except Exception as e:
        raise _server_error("admin_owner_recovery_codes", e)
    if codes is None:
        raise HTTPException(status_code=401, detail=_ADMIN_SESSION_OVER)
    response.headers["Cache-Control"] = "no-store"
    print("[admin-auth] owner recovery codes replaced")
    return {"recovery_codes": codes}


# ── Roles + staff (task 8.4c-2a1 · docs/rules/admin-staff.md rule 10) ──
# staff.manage = OWNER_ONLY → the owner only, and every write needs the step-up (428 without — check_admin).
# The logic + SQL live in admin_staff.py; the audit row comes from admin_audit_middleware (actor owner, route name,
# ids only). Staff emails (staff_suspended · staff_restored · staff_perms_changed — name only) go AFTER the commit;
# a failed email never undoes the write.
STAFF_PERM = "staff.manage"


def _staff_error(e: "admin_staff.StaffError") -> JSONResponse:
    return api_error(e.status, e.code, _tw_text("admin.staff.error." + e.code), e.field)


def _staff_email(to: str, template: str, name: str) -> None:
    try:
        email_service.send_email(to, template, {"name": name or ""})
    except Exception as e:   # send_email never raises — belt and braces: the write is already committed
        print(f"[admin-staff] email failed template={template}: {type(e).__name__}")


def _staff_body(data) -> dict:
    return data if isinstance(data, dict) else {}


@app.get("/admin/roles")
def admin_roles_list(request: Request):
    check_admin(request, STAFF_PERM)
    try:
        roles = admin_staff.list_roles()
    except Exception as e:
        raise _server_error("admin_roles_list", e)
    return api_ok({"roles": roles,
                   "grantable": [{"perm": k, "label": v} for k, v in admin_perms.GRANTABLE.items()]})


@app.post("/admin/roles")
def admin_roles_create(request: Request, data: dict = Body(...)):
    check_admin(request, STAFF_PERM)
    data = _staff_body(data)
    try:
        name = admin_staff.clean_role_name(data.get("name"), tw_settings.limit("admin_role_name_max"))
        perms = admin_staff.clean_perms(data.get("perms"), "perms")
        role = admin_staff.create_role(name, perms)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_roles_create", e)
    request.state.audit_target = f"role_id={role['id']}"
    return api_ok(role)


@app.put("/admin/roles/{role_id}")
def admin_roles_update(role_id: int, request: Request, data: dict = Body(...)):
    check_admin(request, STAFF_PERM)
    data = _staff_body(data)
    try:
        name = (admin_staff.clean_role_name(data.get("name"), tw_settings.limit("admin_role_name_max"))
                if "name" in data else None)
        perms = admin_staff.clean_perms(data.get("perms"), "perms") if "perms" in data else None
        role, notify = admin_staff.update_role(role_id, name, perms)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_roles_update", e)
    for st in notify:   # only the active staff whose effective perms really changed
        _staff_email(st["email"], "staff_perms_changed", st["name"])
    return api_ok(role)


@app.delete("/admin/roles/{role_id}")
def admin_roles_delete(role_id: int, request: Request):
    check_admin(request, STAFF_PERM)
    try:
        admin_staff.delete_role(role_id)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_roles_delete", e)
    return api_ok({"id": role_id})


@app.get("/admin/staff")
def admin_staff_list(request: Request):
    claims = check_admin(request, STAFF_PERM)
    try:
        staff = admin_staff.list_staff()
    except Exception as e:
        raise _server_error("admin_staff_list", e)
    return api_ok(_admin_contacts(claims, {"staff": staff}))


@app.put("/admin/staff/{staff_id}/access")
def admin_staff_access(staff_id: int, request: Request, data: dict = Body(...)):
    claims = check_admin(request, STAFF_PERM)
    data = _staff_body(data)
    role_id = data.get("role_id")
    if role_id is not None and (isinstance(role_id, bool) or not isinstance(role_id, int) or role_id < 1):
        return _staff_error(admin_staff.StaffError(422, "invalid_role", "role_id"))
    try:
        allow = admin_staff.clean_perms(data.get("allow"), "allow")
        deny = admin_staff.clean_perms(data.get("deny"), "deny")
        st, notify = admin_staff.set_access(staff_id, role_id, allow, deny)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_staff_access", e)
    if notify:
        _staff_email(st["email"], "staff_perms_changed", st["name"])
    return api_ok(_admin_contacts(claims, st))


def _staff_status(claims: dict, staff_id: int, suspended: bool, name: str):
    try:
        st, changed = admin_staff.set_suspended(staff_id, suspended)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error(name, e)
    if changed:
        _staff_email(st["email"], "staff_suspended" if suspended else "staff_restored", st["name"])
    return api_ok(_admin_contacts(claims, st))


@app.post("/admin/staff/{staff_id}/suspend")
def admin_staff_suspend(staff_id: int, request: Request):
    """status suspended + session_version + 1 → every token of this staff member fails on its next request."""
    claims = check_admin(request, STAFF_PERM)
    return _staff_status(claims, staff_id, True, "admin_staff_suspend")


@app.post("/admin/staff/{staff_id}/restore")
def admin_staff_restore(staff_id: int, request: Request):
    """From suspended only → active (password + authenticator bound) else invited, + session_version + 1 — an old
    token never comes back."""
    claims = check_admin(request, STAFF_PERM)
    return _staff_status(claims, staff_id, False, "admin_staff_restore")


# ── Staff invite · authenticator reset · password reset (task 8.4c-2a2 · docs/rules/admin-staff.md rule 14) ──
# Owner routes (staff.manage + step-up — check_admin first line) create the link; the public /staff/* routes use it
# (the token comes in the body — the page reads it from the email link's #t= fragment). The logic + SQL live in
# admin_staff.py; the plain token only ever goes into the email link — never a reply, a log or an audit row.
# Every public route: an atomic reservation per client IP + per link / email (RATES staff_link_* / staff_forgot_*)
# BEFORE the slow check → 429; the hits stay (a wrong code counts). A bad code shape → 422 before anything counts.
# The panel path is never in an email — only in the reply of a completed invite.
def _staff_link_email(to: str, template: str, name: str, kind: str, token: str) -> bool:
    try:
        link = admin_staff.link_url(email_service.get_settings()["site_url"], kind, token)
        ttl = admin_staff.LINK_TTL_S[kind]
        vars_ = {"name": name or "", "link": link}
        vars_.update({"minutes": ttl // 60} if template == "staff_password_reset" else {"hours": ttl // 3600})
        return email_service.send_email(to, template, vars_).get("ok") is True
    except Exception as e:   # send_email never raises — the write is committed; the owner can resend
        print(f"[admin-staff] email failed template={template}: {type(e).__name__}")
        return False


@app.post("/admin/staff/invite")
def admin_staff_invite(request: Request, data: dict = Body(...)):
    """New staff member (invited) + a 24 h one-time invite link by email (staff_invite). 409 already_invited /
    email_taken · 422 invalid perms / role / name / email."""
    claims = check_admin(request, STAFF_PERM)
    data = _staff_body(data)
    role_id = data.get("role_id")
    if role_id is not None and (isinstance(role_id, bool) or not isinstance(role_id, int) or role_id < 1):
        return _staff_error(admin_staff.StaffError(422, "invalid_role", "role_id"))
    email = data.get("email").strip().lower() if isinstance(data.get("email"), str) else ""
    try:
        name = admin_staff.clean_staff_name(data.get("name"), tw_settings.limit("admin_staff_name_max"))
        if not email_service.valid_address(email):
            raise admin_staff.StaffError(422, "invalid_email", "email")
        allow = admin_staff.clean_perms(data.get("allow"), "allow")
        deny = admin_staff.clean_perms(data.get("deny"), "deny")
        st, token = admin_staff.invite_staff(name, email, role_id, allow, deny)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_staff_invite", e)
    request.state.audit_target = f"staff_id={st['id']}"
    sent = _staff_link_email(st["email"], "staff_invite", st["name"], "invite", token)
    return api_ok(_admin_contacts(claims, dict(st, email_sent=sent)))


@app.post("/admin/staff/{staff_id}/invite/resend")
def admin_staff_invite_resend(staff_id: int, request: Request):
    """Invited only (409 not_invited) — a new invite link; the old one dies in the same transaction."""
    claims = check_admin(request, STAFF_PERM)
    try:
        st, token = admin_staff.resend_invite(staff_id)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_staff_invite_resend", e)
    sent = _staff_link_email(st["email"], "staff_invite", st["name"], "invite", token)
    return api_ok(_admin_contacts(claims, dict(st, email_sent=sent)))


@app.delete("/admin/staff/{staff_id}")
def admin_staff_delete(staff_id: int, request: Request):
    """Cancel an invite that was never accepted (the row + its links go). active / suspended → 409 staff_active."""
    check_admin(request, STAFF_PERM)
    try:
        admin_staff.delete_invited(staff_id)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_staff_delete", e)
    return api_ok({"id": staff_id})


@app.post("/admin/staff/{staff_id}/mfa-reset")
def admin_staff_mfa_reset(staff_id: int, request: Request):
    """Lost device (the owner checked who it is outside the system): active only (409 not_active). Authenticator +
    recovery codes cleared + every session ends + a 24 h re-bind link by email (staff_mfa_reset). Password kept."""
    claims = check_admin(request, STAFF_PERM)
    try:
        st, token = admin_staff.mfa_reset(staff_id)
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except Exception as e:
        raise _server_error("admin_staff_mfa_reset", e)
    print(f"[admin-staff] authenticator reset staff={staff_id} — sessions ended")
    sent = _staff_link_email(st["email"], "staff_mfa_reset", st["name"], "mfa_reset", token)
    return api_ok(_admin_contacts(claims, dict(st, email_sent=sent)))


def _staff_link_reserve(request: Request, token) -> None:
    """Per client IP + per link (SHA-256 of the token — never the token) in one locked step → else 429."""
    who = admin_staff.link_hash(token if isinstance(token, str) else "")[:32]
    if _rate_reserve([("staff_link_ip", get_client_ip(request)), ("staff_link_token", who)]) is None:
        raise HTTPException(status_code=429, detail=_tw_text("limits.rate_limited"))


def _staff_public_reply(request: Request, payload: dict, actor=None) -> JSONResponse:
    if actor is not None:
        request.state.audit_actor = admin_staff.STAFF_PREFIX + str(int(actor))
    resp = JSONResponse(api_ok(payload))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def _staff_code(data: dict):
    """The authenticator code → the cleaned code, or None (wrong shape — 422, nothing counted / used)."""
    code = data.get("code")
    return code.strip() if otp_code_valid(code) else None


def _staff_password_check(data: dict):
    """The cheap shape check of the new password — None, or the 422. No bcrypt here: the hash runs only AFTER
    _staff_link_reserve (these routes are outside the public limit — a bcrypt before the reservation would be an
    unlimited CPU cost for anyone)."""
    err = admin_staff.staff_password_error(data.get("password"), tw_limits.LIMITS["staff_password_min"],
                                           tw_limits.LIMITS["password_max_bytes"])
    if err:
        return api_error(422, err, _tw_text("admin.staff.error." + err,
                                            min=tw_limits.LIMITS["staff_password_min"],
                                            max=tw_limits.LIMITS["password_max_bytes"]), "password")
    return None


def _staff_link_call(request: Request, name: str, fn):
    try:
        return fn()
    except admin_staff.StaffError as e:
        return _staff_error(e)
    except HTTPException:
        raise
    except Exception as e:
        raise _server_error(name, e)


def _staff_start(request: Request, data: dict, kind: str, name: str):
    data = _staff_body(data)
    token = data.get("token")
    _staff_link_reserve(request, token)

    def run():
        out = admin_staff.link_start(token, kind)
        return _staff_public_reply(request, {"secret": out["secret"], "otpauth_uri": out["otpauth_uri"],
                                             "name": out["name"]}, out["staff_id"])
    return _staff_link_call(request, name, run)


def _staff_complete(request: Request, data: dict, kind: str, name: str):
    data = _staff_body(data)
    code = _staff_code(data)
    if code is None:
        return _staff_error(admin_staff.StaffError(422, "invalid_code_format", "code"))
    if kind == "invite":
        err = _staff_password_check(data)
        if err:
            return err
    token = data.get("token")
    _staff_link_reserve(request, token)   # 429 before any bcrypt

    def run():
        pw_hash = _hash_password(data["password"]) if kind == "invite" else None
        out = admin_staff.link_complete(token, kind, code, pw_hash)
        print(f"[admin-staff] {kind} completed staff={out['staff_id']} — authenticator bound, recovery codes issued")
        payload = {"recovery_codes": out["recovery_codes"], "name": out["name"]}
        if kind == "invite":   # the ONLY place the panel path leaves the server for a staff member
            payload["panel"] = "/tw-ctrl-" + ADMIN_URL_TOKEN
        return _staff_public_reply(request, payload, out["staff_id"])
    return _staff_link_call(request, name, run)


@app.post("/staff/invite/start")
def staff_invite_start(request: Request, data: dict = Body(...)):
    return _staff_start(request, data, "invite", "staff_invite_start")


@app.post("/staff/invite/complete")
def staff_invite_complete(request: Request, data: dict = Body(...)):
    """{token, password, code} → password + authenticator bound + active + 10 recovery codes + the panel path."""
    return _staff_complete(request, data, "invite", "staff_invite_complete")


@app.post("/staff/mfa-reset/start")
def staff_mfa_reset_start(request: Request, data: dict = Body(...)):
    return _staff_start(request, data, "mfa_reset", "staff_mfa_reset_start")


@app.post("/staff/mfa-reset/complete")
def staff_mfa_reset_complete(request: Request, data: dict = Body(...)):
    """{token, code} → the new authenticator bound + 10 new recovery codes (password unchanged)."""
    return _staff_complete(request, data, "mfa_reset", "staff_mfa_reset_complete")


def _staff_forgot_send(email: str) -> None:
    """Background: an active staff member with password + authenticator → a 30-minute link. Logs: no email / token."""
    try:
        out = admin_staff.forgot_issue(email)
        if out:
            _staff_link_email(out["email"], "staff_password_reset", out["name"], "password_reset", out["token"])
            print(f"[admin-staff] password reset link sent staff={out['staff_id']}")
    except Exception as e:
        print(f"[admin-staff] forgot failed: {type(e).__name__}")


@app.post("/tw-ctrl-" + ADMIN_URL_TOKEN + "/forgot")
def admin_forgot(request: Request, background_tasks: BackgroundTasks, data: dict = Body(...)):
    """Staff forgot the password: always the same 200 (exists or not, any status). The lookup + link + email run
    AFTER the reply (BackgroundTasks) so the time does not tell either. 429 per IP / per email (reserved first)."""
    data = _staff_body(data)
    email = data.get("email").strip().lower() if isinstance(data.get("email"), str) else ""
    email = email[:254]
    if _rate_reserve([("staff_forgot_ip", get_client_ip(request)), ("staff_forgot_email", email or "-")]) is None:
        raise HTTPException(status_code=429, detail=_tw_text("limits.rate_limited"))
    if email_service.valid_address(email):
        background_tasks.add_task(_staff_forgot_send, email)
    resp = JSONResponse(api_ok({"sent": True}))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.post("/staff/password-reset/complete")
def staff_password_reset_complete(request: Request, background_tasks: BackgroundTasks, data: dict = Body(...)):
    """{token, password} → new password + every session ends (the authenticator stays — the login still asks for
    it) + staff_password_changed. A suspended staff member → invalid_link (never re-activated)."""
    data = _staff_body(data)
    err = _staff_password_check(data)
    if err:
        return err
    token = data.get("token")
    _staff_link_reserve(request, token)   # 429 before any bcrypt

    def run():
        out = admin_staff.password_reset_complete(token, _hash_password(data["password"]))
        print(f"[admin-staff] password reset staff={out['staff_id']} — sessions ended")
        background_tasks.add_task(email_service.send_email, out["email"], "staff_password_changed",
                                  {"name": out["name"]})
        return _staff_public_reply(request, {"reset": True}, out["staff_id"])
    return _staff_link_call(request, "staff_password_reset_complete", run)


# ══════════════════════════════════════════
# Admin API - all require X-Admin-Token header
# ══════════════════════════════════════════
@app.get("/admin/profile/{user_id}")
def admin_get_profile(user_id: int, request: Request):
    claims = check_admin(request, "users.view")
    try:
        profile = get_full_profile(user_id)
        if not profile:
            raise HTTPException(404, "المستخدم غير موجود")
        profile["suspension"] = bs.get_suspension(user_id)   # task 5.4 — admin-only (reason / by)
        profile["deletion"] = ad.get_deletion(user_id)        # task 8.5a — admin-only (kind / reason / by)
        return {"status": "success", "profile": _admin_contacts(claims, profile)}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"admin_get_profile error: {err}")
        raise _server_error("admin_get_profile", e)

@app.delete("/auth/user/{user_id}/delete")
def delete_own_account(user_id: int, token=Depends(verify_token)):
    """Self-service account delete — CLOSED (task 5.0e): always 403, nothing is deleted from this path
    until soft delete (F27) is built (ADMIN_ENTITY_MAP §1). The old path hard-deleted users with every
    CASCADE row. The user's own soft delete comes in task 8.5d (account_deletion.soft_delete kind 'self')."""
    raise HTTPException(403, "حذف الحساب غير متاح حالياً")

def _account_reason(data: dict, required: bool):
    """→ (reason | None, None) or (None, 422 response). ≤ LIMITS account_reason_max."""
    reason = data.get("reason") if isinstance(data, dict) else None
    if reason is not None and not isinstance(reason, str):
        return None, api_error(422, "invalid_value", _tw_text("admin.account.err.reason"), "reason")
    reason = (reason or "").strip() or None
    if required and not reason:
        return None, api_error(422, "reason_required", _tw_text("admin.account.err.reason"), "reason")
    too_long = _too_long(reason, "account_reason_max", "reason")
    return (None, too_long) if too_long else (reason, None)


@app.delete("/admin/user/{user_id}")
def delete_user(user_id: int, request: Request, data: Optional[dict] = Body(None)):
    """Soft delete (task 8.5a · F27 — no hard delete on any path; 8.5c). Body {reason?} (admin-only text).
    The account: every request 401 at once (session_version + 1 · cache · sockets 4008) · content hidden by the
    one visibility rule · shared records stay as «حساب محذوف». Company: open jobs closed + one notice per affected
    applicant · upcoming interviews cancelled (account_deletion.apply_effects — by the call that changed the state).
    users.delete is OWNER_ONLY → the step-up grant is required (428 step_up_required)."""
    claims = check_admin(request, "users.delete")
    reason, err = _account_reason(data or {}, required=False)
    if err:
        return err
    try:
        out = ad.soft_delete(user_id, str(claims.get("sub") or "admin"), "admin", reason)
        if out is None:
            return api_error(404, "not_found", "الحساب غير موجود")
        _password_changed_cache_set(user_id, out["state"])   # effective at once in this process
    except Exception as e:
        raise _server_error("delete_user", e)
    _ws_revoke_user(user_id, "admin_deleted")
    request.state.audit_change = ("active" if out["changed"] else "deleted", "deleted")
    if out["changed"]:
        try:
            ad.apply_effects(user_id)
        except Exception as e:   # the account is deleted either way — logged (F9)
            print(f"[delete_user] effects user={user_id} failed: {type(e).__name__}: {e}")
    _cache_del("jobs:")
    return api_ok({"deleted": True, "deleted_at": out["deleted_at"], "changed": out["changed"]})


@app.post("/admin/user/{user_id}/restore")
def restore_user(user_id: int, request: Request, data: Optional[dict] = Body(None)):
    """Restore a soft-deleted account (task 8.5a) — body {reason} (required, ≤ account_reason_max; kept in the
    admin audit log). Content shows again · jobs stay closed · cancelled interviews stay cancelled · old tokens
    stay 401 (a new login). users.delete + step-up (428). A final purge started → 409 purging / already_purged
    (task 8.5c)."""
    claims = check_admin(request, "users.delete")
    reason, err = _account_reason(data or {}, required=True)
    if err:
        return err
    try:
        out = ad.restore(user_id, str(claims.get("sub") or "admin"), reason)
        if out is None:
            return api_error(404, "not_found", "الحساب غير موجود")
        _password_changed_cache_set(user_id, out["state"])
    except ad.DeletionError as e:   # task 8.5c — the final purge started / finished → never restored
        return api_error(e.status, e.code, _tw_text("admin.account.err." + e.code))
    except Exception as e:
        raise _server_error("restore_user", e)
    request.state.audit_change = ("deleted" if out["changed"] else "active", reason)
    _cache_del("jobs:")
    return api_ok({"deleted": False, "changed": out["changed"]})

@app.put("/admin/user/{user_id}/type")
def change_user_type(user_id: int, request: Request, data: dict = Body(...)):
    check_admin(request, "users.type")
    new_type = data.get("user_type","emp")
    if new_type not in ("emp","co","edu"):
        raise HTTPException(400, "نوع حساب غير صحيح")
    try:
        state = set_user_type(user_id, new_type)   # also bumps session_version (type lives in the JWT)
    except Exception as e:
        raise _server_error("change_user_type", e)
    if state is None:
        raise HTTPException(404, "المستخدم غير موجود")
    _end_user_sessions(user_id, state, "admin_type_change")
    return {"success": True}

@app.put("/admin/user/{user_id}/verify")
def verify_user(user_id: int, request: Request, data: dict = Body(...)):
    """Manual badge on / off — body {is_verified: true|false} (required boolean, no default — task 5.0c)."""
    check_admin(request, "kyc.review")
    is_v = data.get("is_verified")
    if not isinstance(is_v, bool):
        return api_error(422, "invalid_value", "قيمة التوثيق مطلوبة (true / false)", "is_verified")
    try:
        with db_conn() as conn:
            if not conn.run("SELECT 1 FROM users WHERE id = :uid", uid=user_id):
                return api_error(404, "not_found", "الحساب غير موجود")
            set_user_verified(user_id, is_v, conn)
        return {"success": True}
    except Exception as e:
        raise _server_error("verify_user", e)

@app.put("/admin/user/{user_id}/suspension")
def admin_set_suspension(user_id: int, request: Request, data: dict = Body(...)):
    """Suspend / lift — body {suspended: true|false, reason?: text (admin-only, ≤ suspend_reason_max)} (task 5.4).
    Suspended → every request of the account 401 at once (session cache refreshed + sockets closed) and its
    content hidden by the queries. Lifted → the same account and content come back. Nothing is deleted."""
    claims = check_admin(request, "users.suspend")   # owner "*" passes; a staff token without it → 403
    sus = data.get("suspended")
    if not isinstance(sus, bool):
        return api_error(422, "invalid_value", _tw_text("admin.suspend.err.value"), "suspended")
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        return api_error(422, "invalid_value", _tw_text("admin.suspend.err.value"), "reason")
    reason = (reason or "").strip() or None
    too_long = _too_long(reason, "suspend_reason_max", "reason")
    if too_long:
        return too_long
    try:
        out = bs.set_suspension(user_id, sus, reason if sus else None, str(claims.get("sub") or "admin"))
        if out is None:
            return api_error(404, "not_found", "الحساب غير موجود")
        from auth import get_session_state
        _password_changed_cache_set(user_id, get_session_state(user_id))   # effective at once in this process
    except Exception as e:
        raise _server_error("admin_set_suspension", e)
    if sus:
        _ws_revoke_user(user_id, "admin_suspend")
    _cache_del("jobs:")   # cached public job lists — a suspended company's jobs leave / come back now
    return api_ok(out)

@app.put("/admin/user/{user_id}/password")
def admin_reset_password(user_id: int, request: Request, data: dict = Body(...)):
    check_admin(request, "users.password")
    pw = data.get("password")
    err = _password_policy_error(pw)            # the one password rule (task 5.0c — #10)
    if err:
        return api_error(422, "weak_password", err, "password")
    try:
        # Same helper as PUT /auth/password → bumps session_version (user's sessions end)
        # and deletes the user's pending email tokens.
        _end_user_sessions(user_id, set_user_password(user_id, pw), "admin_password_reset")
        return {"success": True}
    except Exception as e:
        raise _server_error("admin_reset_password", e)

# ── Admin email change (task 8.3 · SYSTEMS_INDEX §1c) — the same token / page / confirm as 5.1b:
# the admin only REQUESTS (purpose email_change_admin); the link goes to the new address and users.email
# changes only when it is opened (POST /auth/email-change/confirm → every session of the user ends +
# email_changed_admin to the old address). No address in audit / log.
_ADMIN_EMAILCHANGE_LIMIT, _ADMIN_EMAILCHANGE_WINDOW = 5, 3600.0

@app.put("/admin/user/{user_id}/email")
def admin_email_change(user_id: int, request: Request, data: dict = Body(...)):
    claims = check_admin(request, "users.email")   # owner "*" passes; a staff token without it → 403
    request.state.audit_target = f"user_id={user_id}"
    raw = data.get("new_email")
    if raw is not None and not isinstance(raw, str):
        return api_error(422, "invalid_email", "صيغة البريد الإلكتروني غير صحيحة", "new_email")
    new_email = (raw or "").strip().lower()
    if not new_email:
        return api_error(422, "required", "أدخل البريد الإلكتروني الجديد", "new_email")
    if not email_service.valid_address(new_email):
        return api_error(422, "invalid_email", "صيغة البريد الإلكتروني غير صحيحة", "new_email")
    try:
        user = get_user_by_id(user_id)
    except Exception as e:
        raise _server_error("admin_email_change", e)
    if not user:
        return api_error(404, "not_found", "الحساب غير موجود")
    if (user.get("email") or "").strip().lower() == new_email:
        return api_error(422, "same_email", "هذا هو البريد الإلكتروني الحالي للحساب", "new_email")
    if not email_service.can_send("email_change"):
        return api_error(503, "email_unavailable", _EMAIL_UNAVAILABLE_MSG)
    if not _rate_hit(f"admin-email-change:{user_id}", _ADMIN_EMAILCHANGE_LIMIT, _ADMIN_EMAILCHANGE_WINDOW):
        return api_error(429, "rate_limited", "طلبات كثيرة، حاول مرة أخرى لاحقاً")
    try:
        link_token = email_change_request(user_id, new_email, by_admin=True)   # newest only — any older link dies
    except EmailTakenError:
        return api_error(422, "email_taken", _EMAILCHANGE_TAKEN_MSG, "new_email")
    except Exception as e:
        raise _server_error("admin_email_change", e)
    link = email_service.get_settings()["site_url"] + "/confirm-email#token=" + link_token
    res = email_service.send_email(new_email, "email_change",
                                   {"name": user.get("full_name") or "", "link": link,
                                    "minutes": EMAIL_TOKEN_TTL_MINUTES})
    if not res.get("ok"):
        return api_error(502, "email_failed", "تعذّر إرسال رابط التأكيد، حاول مرة أخرى لاحقاً")
    print(f"[email-change] admin link sent user={user_id} admin={claims.get('sub') or 'admin'}")
    return api_ok({"sent": True})

@app.delete("/admin/experience/{exp_id}")
def admin_delete_exp(exp_id: int, request: Request):
    check_admin(request, "users.edit")
    conn = get_conn()
    try:
        conn.run("DELETE FROM experience WHERE id = :id", id=exp_id)
        return {"success": True}
    except Exception as e:
        raise _server_error("admin_delete_exp", e)
    finally:
        release_conn(conn)

@app.delete("/admin/education/{edu_id}")
def admin_delete_edu(edu_id: int, request: Request):
    check_admin(request, "users.edit")
    conn = get_conn()
    try:
        conn.run("DELETE FROM education WHERE id = :id", id=edu_id)
        return {"success": True}
    except Exception as e:
        raise _server_error("admin_delete_edu", e)
    finally:
        release_conn(conn)

@app.delete("/admin/course/{course_id}")
def admin_delete_course(course_id: int, request: Request):
    check_admin(request, "users.edit")
    conn = get_conn()
    try:
        conn.run("DELETE FROM courses WHERE id = :id", id=course_id)
        return {"success": True}
    except Exception as e:
        raise _server_error("admin_delete_course", e)
    finally:
        release_conn(conn)

ADMIN_MESSAGE_SUBJECT_MAX = 120
ADMIN_MESSAGE_MAX = 2000

@app.post("/admin/message")
def admin_send_message(data: AdminMessageInput, request: Request):
    """Message from the admin to one user (task 5.3b2): an in-site notification of type
    admin_message (create_notification) — its mapped email (admin_message, category notification)
    goes through the same hook → user preference + caps. ok only when the notification exists.
    The text is stored as written; every renderer escapes it (textContent / email esc)."""
    check_admin(request, "message.send")
    subject = (data.subject or "").strip()[:ADMIN_MESSAGE_SUBJECT_MAX]
    message = (data.message or "").strip()
    if not message:
        return api_error(422, "empty", "نص الرسالة مطلوب", field="message")
    if len(message) > ADMIN_MESSAGE_MAX:
        return api_error(422, "too_long", f"الرسالة أطول من {ADMIN_MESSAGE_MAX} حرف", field="message")
    try:
        if not get_user_by_id(data.user_id):
            return api_error(404, "not_found", "المستخدم غير موجود")
        created = create_notification(data.user_id, "admin_message", subject or "رسالة من الإدارة",
                                      message, "/notifications", entity_type="admin_message")
    except Exception as e:
        raise _server_error("admin_send_message", e)
    if not created or not created.get("id"):
        print(f"[ADMIN MSG] notification not created user={data.user_id}")
        return api_error(500, "not_delivered", "ما انبعتت الرسالة، حاول مرة أخرى")
    print(f"[ADMIN MSG] user={data.user_id} notification={created['id']}")
    return api_ok({"notification_id": created["id"]})

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
        raise _server_error("delete_experience", e)

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
        raise _server_error("delete_education", e)

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
        raise _server_error("delete_course", e)


# ══ News Posts (admin-managed editorial content) ══

class NewsPostInput(BaseModel):
    title: str
    summary: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = "general"
    country: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = "draft"
    starts_at: Optional[datetime] = None   # phase 5a — display window (NULL = no bound)
    ends_at: Optional[datetime] = None

def _news_window(data: NewsPostInput):
    """Naive times are UTC. ends_at must be after starts_at → else the 400 response."""
    from datetime import timezone
    for f in ("starts_at", "ends_at"):
        v = getattr(data, f)
        if v is not None and v.tzinfo is None:
            setattr(data, f, v.replace(tzinfo=timezone.utc))
    if data.starts_at and data.ends_at and data.ends_at <= data.starts_at:
        return api_error(400, "invalid_window", "تاريخ الانتهاء لازم يكون بعد تاريخ البداية", "ends_at")
    return None

def _iso(v):
    return v.isoformat() if v is not None and hasattr(v, "isoformat") else v

@app.get("/admin/news")
def admin_list_news(request: Request):
    check_admin(request, CONTENT_PERM)
    conn = get_conn()
    try:
        rows = conn.run(
            # phase 5b: body (the edit form sends it back — PUT replaces every field) +
            # active_now from NEWS_ACTIVE_SQL itself (no second "active" rule in the page)
            """SELECT n.id, n.title, n.summary, n.category, n.country,
                      n.source_url, n.status, n.created_at, n.updated_at,
                      COALESCE(u.full_name,'') AS created_by_name, n.starts_at, n.ends_at,
                      n.body, n.active_now
               FROM (SELECT *, (""" + NEWS_ACTIVE_SQL + """) AS active_now FROM news_posts) n
               LEFT JOIN users u ON n.created_by = u.id
               ORDER BY n.created_at DESC"""
        )
        cols = ["id","title","summary","category","country","source_url",
                "status","created_at","updated_at","created_by_name","starts_at","ends_at",
                "body","active_now"]
        result = []
        for r in (rows or []):
            d = dict(zip(cols, r))
            for f in ("created_at","updated_at","starts_at","ends_at"):
                if d.get(f) and hasattr(d[f], "isoformat"):
                    d[f] = d[f].isoformat()
            result.append(d)
        return {"news": result, "total": len(result)}
    finally:
        release_conn(conn)

@app.post("/admin/news")
def admin_create_news(data: NewsPostInput, request: Request):
    check_admin(request, CONTENT_PERM)
    data.source_url = _validate_external_url(data.source_url, "source_url", "رابط المصدر")   # §54 rule 4b
    bad = _news_window(data)
    if bad:
        return bad
    allowed_statuses = {"draft", "published", "archived"}
    status = data.status if data.status in allowed_statuses else "draft"
    conn = get_conn()
    try:
        rows = conn.run(
            """INSERT INTO news_posts (title, summary, body, category, country, source_url, status,
                                       starts_at, ends_at)
               VALUES (:title, :summary, :body, :category, :country, :source_url, :status,
                       :starts_at, :ends_at)
               RETURNING id""",
            title=data.title.strip(), summary=data.summary or "",
            body=data.body or "", category=data.category or "general",
            country=data.country or "", source_url=data.source_url or "",
            status=status, starts_at=data.starts_at, ends_at=data.ends_at
        )
        news_id = rows[0][0] if rows else None
        request.state.audit_target = f"news_id={news_id}"
        return {"success": True, "id": news_id,
                "starts_at": _iso(data.starts_at), "ends_at": _iso(data.ends_at)}
    finally:
        release_conn(conn)

@app.put("/admin/news/{news_id}")
def admin_update_news(news_id: int, data: NewsPostInput, request: Request):
    check_admin(request, CONTENT_PERM)
    data.source_url = _validate_external_url(data.source_url, "source_url", "رابط المصدر")   # §54 rule 4b
    bad = _news_window(data)
    if bad:
        return bad
    allowed_statuses = {"draft", "published", "archived"}
    status = data.status if data.status in allowed_statuses else "draft"
    conn = get_conn()
    try:
        conn.run(
            """UPDATE news_posts
               SET title=:title, summary=:summary, body=:body,
                   category=:category, country=:country, source_url=:source_url,
                   status=:status, starts_at=:starts_at, ends_at=:ends_at, updated_at=NOW()
               WHERE id=:id""",
            title=data.title.strip(), summary=data.summary or "",
            body=data.body or "", category=data.category or "general",
            country=data.country or "", source_url=data.source_url or "",
            status=status, starts_at=data.starts_at, ends_at=data.ends_at, id=news_id
        )
        return {"success": True, "starts_at": _iso(data.starts_at), "ends_at": _iso(data.ends_at)}
    finally:
        release_conn(conn)

@app.delete("/admin/news/{news_id}")
def admin_delete_news(news_id: int, request: Request):
    check_admin(request, CONTENT_PERM)
    conn = get_conn()
    try:
        conn.run("DELETE FROM news_posts WHERE id=:id", id=news_id)
        return {"success": True}
    finally:
        release_conn(conn)


@app.get("/news/banner", dependencies=[Depends(_public_rate)])
def news_banner():
    """Public (no login): the newest ACTIVE news item (NEWS_ACTIVE_SQL) or null.
    Safe fields only — id · title · summary · source_url (not http/https → null)."""
    try:
        with db_conn() as conn:
            rows = conn.run("SELECT id, title, summary, source_url FROM news_posts WHERE "
                            + NEWS_ACTIVE_SQL + " ORDER BY created_at DESC, id DESC LIMIT 1")
    except Exception as e:
        raise _server_error("news_banner", e)
    if not rows:
        return api_ok(None)
    nid, title, summary, url = rows[0]
    try:
        url = _validate_external_url(url, "source_url")   # §54 rule 4b — same rule as the save
    except ExternalUrlError:
        url = None
    return api_ok({"id": nid, "title": title, "summary": summary or "", "source_url": url})


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
    mode: Optional[str] = None     # 'online' | 'onsite' — None keeps the draft's mode
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
    POST /api/appointments — Schedule Interview System (PR 3.10 · SYSTEMS_INDEX §23b)

    Path A (backward-compat): { application_id }
    Path B (pipeline):        { candidate_id, job_id, appointment_type }
      Not yet a candidate on this job → added to its pipeline in the same transaction
      (a new link needs an active job of this company). Rejected / withdrawn → 409.

    company_id always derived from JWT. Contract (PR 3.10): {ok, data} /
    {ok:false, error:{code, message}} — every caller goes through twApi (tw-schedule.js).
    """
    user_id, denied = _require_org_account_api(token, ("co",), "فقط حسابات الشركات يمكنها إنشاء مواعيد")
    if denied:
        return denied

    # Path A: application_id only · Path B: candidate_id + job_id only
    _app_set  = body.application_id is not None
    _cand_set = body.candidate_id is not None
    _job_set  = body.job_id is not None

    if _app_set and (_cand_set or _job_set):
        return api_error(400, "ambiguous_appointment_context",
                         "Payload غير واضح: أرسل application_id فقط (Path A) "
                         "أو candidate_id + job_id فقط (Path B) — وليس كليهما معاً.")
    if _cand_set and not _job_set:
        return api_error(400, "invalid_appointment_context",
                         "اختر الوظيفة التي يرتبط بها الموعد", field="job_id")
    if _job_set and not _cand_set:
        return api_error(400, "invalid_appointment_context",
                         "اختر الشخص الذي تريد تحديد موعد معه", field="candidate_id")
    if not _app_set and not (_cand_set and _job_set):
        return api_error(400, "invalid_appointment_context",
                         "يجب إرسال application_id (Path A) أو candidate_id + job_id (Path B).")

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
        return api_ok(appt)
    except AppointmentRuleError as e:
        return api_error(409, e.code, e.message)
    except PipelineApplicationConflictError as e:
        return api_error(409, "pipeline_application_conflict", str(e))
    except PipelineEntryRequiredError as e:
        return api_error(409, "pipeline_entry_required", str(e))
    except PermissionError as e:
        return api_error(403, "forbidden", str(e))
    except ValueError as e:
        return api_error(400, "invalid", str(e))
    except Exception as e:
        print(f"[api_create_appointment] {e}")
        raise _server_error("api_create_appointment", e)


# ── Schedule Interview System — read endpoints (PR 3.10 · SYSTEMS_INDEX §23b) ──
# Company JWT only (co) — everything scoped to the JWT company (F6/F21).

@app.get("/api/schedule/jobs")
def api_jobs_for_scheduling(token=Depends(verify_token)):
    """The company's active jobs for the scheduling job picker → {ok, data:[{id, title}]}."""
    _, denied = _require_org_account_api(token, ("co",), "فقط حسابات الشركات يمكنها تحديد المواعيد")
    if denied:
        return denied
    try:
        return api_ok(list_jobs_for_scheduling(int(token["user_id"])))
    except Exception as e:
        raise _server_error("api_jobs_for_scheduling", e)


@app.get("/api/schedule/open")
def api_schedule_open(candidate_ids: str = Query("", max_length=600),
                      job_id: Optional[int] = Query(None, ge=1),
                      token=Depends(verify_token)):
    """Open appointment per person (for «فتح الموعد») → {ok, data:{"<uid>": appt | null}}.
    candidate_ids = comma-separated ids (max 50); job_id → that job only."""
    _, denied = _require_org_account_api(token, ("co",), "فقط حسابات الشركات يمكنها تحديد المواعيد")
    if denied:
        return denied
    parts = [p.strip() for p in candidate_ids.split(",") if p.strip()]
    if not parts or len(parts) > 50 or not all(p.isascii() and p.isdigit() and len(p) <= 18 for p in parts):
        return api_error(400, "invalid", "قائمة الأشخاص غير صالحة", field="candidate_ids")
    try:
        found = get_open_appointments(int(token["user_id"]), [int(p) for p in parts], job_id)
        return api_ok({str(k): v for k, v in found.items()})
    except Exception as e:
        raise _server_error("api_schedule_open", e)


@app.get("/api/schedule/people")
def api_schedule_people(q: str = Query("", max_length=100),
                        token=Depends(verify_token)):
    """Name search among the company's applicants, candidates and Talent Bank (emp only)
    → {ok, data:[{id, full_name, tw_id, avatar_url, sources}]}."""
    _, denied = _require_org_account_api(token, ("co",), "فقط حسابات الشركات يمكنها تحديد المواعيد")
    if denied:
        return denied
    try:
        return api_ok(search_schedule_people(int(token["user_id"]), q))
    except Exception as e:
        raise _server_error("api_schedule_people", e)


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
        raise _server_error("api_list_appointments", e)


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
        raise _server_error("api_get_appointment_room", e)


@app.post("/api/appointments/{appointment_id}/send")
def api_send_appointment(appointment_id: int, body: AppointmentSendInput,
                          token=Depends(verify_token)):
    user_id = _require_org_account(token, ("co",), "فقط حسابات الشركات يمكنها إرسال دعوات المقابلة")
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
            mode=body.mode,
        )
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_send_appointment] {e}")
        raise _server_error("api_send_appointment", e)


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
        raise _server_error("api_accept_appointment", e)


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
        raise _server_error("api_request_reschedule", e)


@app.post("/api/appointments/{appointment_id}/reschedule")
def api_reschedule_appointment(appointment_id: int, body: RescheduleInput,
                                token=Depends(verify_token)):
    user_id = _require_org_account(token, ("co",), "فقط حسابات الشركات يمكنها إدارة المقابلة")
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
        raise _server_error("api_reschedule_appointment", e)


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
        raise _server_error("api_cancel_appointment", e)


@app.post("/api/appointments/{appointment_id}/complete")
def api_complete_appointment(appointment_id: int, token=Depends(verify_token)):
    user_id = _require_org_account(token, ("co",), "فقط حسابات الشركات يمكنها إدارة المقابلة")
    try:
        appt = complete_appointment(appointment_id, user_id)
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_complete_appointment] {e}")
        raise _server_error("api_complete_appointment", e)


@app.post("/api/appointments/{appointment_id}/close")
def api_close_appointment(appointment_id: int, token=Depends(verify_token)):
    user_id = _require_org_account(token, ("co",), "فقط حسابات الشركات يمكنها إدارة المقابلة")
    try:
        appt = close_appointment(appointment_id, user_id)
        return {"ok": True, "data": appt}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[api_close_appointment] {e}")
        raise _server_error("api_close_appointment", e)


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
        raise _server_error("api_get_appointment_events", e)


@app.get("/api/appointments/{appointment_id}/messages")
def api_get_appointment_messages(appointment_id: int,
                                  limit: int = 50, offset: int = 0,
                                  before_id: Optional[int] = None,
                                  token=Depends(verify_token)):
    """Newest `limit` messages, oldest → newest. ?before_id= loads the page before that id."""
    user_id = int(token["user_id"])
    try:
        msgs = get_appointment_messages(appointment_id, user_id,
                                         limit=limit, offset=offset, before_id=before_id)
        return {"ok": True, "data": msgs}
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        print(f"[api_get_appointment_messages] {e}")
        raise _server_error("api_get_appointment_messages", e)


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
        raise _server_error("api_create_appointment_message", e)


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
      {"ok": true, "picked": N, "done": N, "failed": N, "retried": N,
       "stale_reset": N, "runner_id": str, "jobs": [...]}
      + "skipped": "locked" when another worker's cycle holds the lock (nothing ran).
    """
    if not SCHEDULER_SECRET:
        raise HTTPException(503, "Scheduler not configured (SCHEDULER_SECRET env var not set)")

    incoming = request.headers.get("X-Scheduler-Secret", "")
    if not incoming or not hmac.compare_digest(incoming, SCHEDULER_SECRET):
        raise HTTPException(403, "Forbidden")

    try:
        # Same cycle as the internal loop (advisory lock · stale reset · heartbeat) — task 6.3
        return run_scheduler_cycle(limit=limit)
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
    check_admin(request, "system.manage")
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
        raise _server_error("admin_pipeline_backfill", e)


@app.get("/admin/pipeline/backfill/dry-run")
def admin_pipeline_backfill_dry_run(request: Request):
    """
    GET /admin/pipeline/backfill/dry-run
    Read-only analysis of legacy data eligible for backfill. No writes.
    Requires X-Admin-Token header.
    """
    check_admin(request, "system.manage")
    try:
        return pipeline_backfill_dry_run()
    except Exception as e:
        raise _server_error("admin_pipeline_backfill_dry_run", e)


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
    check_admin(request, "system.manage")
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
        raise _server_error("admin_pipeline_migrate_index", e)


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
        raise _server_error("api_list_pipeline_notes", e)


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
        raise _server_error("api_create_pipeline_note", e)


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
        raise _server_error("api_update_pipeline_note", e)


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
        raise _server_error("api_delete_pipeline_note", e)


