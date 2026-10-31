"""tw_limits.py — Input Limits (task 5.0h · docs/SYSTEMS_INDEX.md §54n · ARCHITECTURE.md §76).

The ONE place for input size / flood limits — the DEFAULTS (nothing else in the code may repeat a
value). The keys in tw_settings.REGISTRY (task 4.1) are admin-editable: code reads them through
tw_settings.limit() / tw_settings.rate() only, never LIMITS[…] / RATES[…] directly.
  LIMITS        → max lengths / counts / page sizes, checked by server.py before any DB write
  RATES         → {name: (max hits, window seconds)} on server._rate_hit (per account / IP)
  REPORT_TYPES  → the report reason types the server accepts (twReportDialog shows exactly these)
  POST_TAGS     → the post tags allowlist, read from TW.POST_TAGS in static/shared/tw-options-data.js
                  (the tags' single source — never copied here)
  page_block()  → `<script>window.TW_LIMITS=…</script>`, appended to the Strings block at
                  <!--tw:strings--> so twLimit(name) / twReportTypes() in tw_shared.js read the same
                  values (textarea maxlength, tag count, report reasons).

Pure — no DB, no FastAPI. Rejection texts are twT keys (`limits.*` in tw_strings.json).
"""
import json
import os
import re

_ROOT = os.path.dirname(os.path.abspath(__file__))

LIMITS = {
    "message_max": 4000,          # POST /messages/send content (chars)
    "post_body_max": 3000,        # POST / PATCH /company/posts body (chars)
    "post_tags_max": 5,           # tags per post
    "report_reason_max": 1000,    # POST /reports/submit reason (chars)
    "report_url_max": 500,        # POST /reports/submit target_url (chars)
    "mention_limit_max": 20,      # GET /mention/search ?limit= ceiling
    "comments_page": 20,          # GET /company/posts/{id}/comments threads per page (default)
    "comments_page_max": 50,      # … ?limit= ceiling
    "password_max_bytes": 72,     # register / password reset / password change — UTF-8 bytes (bcrypt cuts at 72)
    "mem_store_max_keys": 20000,  # in-memory rate store (_rate_store) — key cap PER KIND (key prefix, task 5.4d); oldest of that kind evicted past it, never a login lock
    "mem_store_sweep_s": 60,      # … expired keys swept at most this often, on use (no thread)
    "ip_country_cache_max": 10000,  # IP_TO_COUNTRY_CACHE — entries cap
    "ip_country_cache_ttl_s": 86400,  # … one lookup per IP per day
    "blocks_page_max": 50,        # GET /blocks ?limit= ceiling (task 5.4)
    "suspend_reason_max": 500,    # PUT /admin/user/{id}/suspension reason (chars — admin only)
    "account_reason_max": 500,    # DELETE /admin/user/{id} reason (optional) + POST …/restore reason (task 8.5a — admin only)
    "otp_ttl_min": 10,            # KYC OTP (email / phone) — code lifetime in minutes (auth._otp_issue · task 4.2)
    "otp_max_attempts": 5,        # … wrong tries before the code dies (auth._otp_verify)
    "support_subject_max": 120,   # support ticket subject (chars — task 7.1)
    "support_body_max": 5000,     # support ticket message (chars)
    "support_open_max": 5,        # open tickets (open + awaiting_user) per account at once
    "support_inbound_request_max": 262144,  # POST /webhooks/resend/inbound body (bytes — the event is metadata only, task 7.3)
    "support_inbound_fetch_max": 2097152,   # the received email fetched from Resend (bytes) — larger = ignored
    "support_track_session_hours": 24,      # guest follow-up session after the code (task 7.4) — fixed, never extended
    "kyc_reject_reason_max": 500, # PUT /admin/kyc/{id}/reject reason shown to the user (chars — fixed, task 8.1)
    "job_reapply_week_max": 3,    # re-applies after a withdrawal per (applicant + job) in 7 days — counted from pipeline_stage_events (task 8.2a)
    "feed_page_max": 50,          # GET /home/feed ?limit= ceiling (task 8.6d-1)
    "feed_snapshot_ttl_min": 60,  # … saved job list (feed_snapshots) lifetime in minutes — older = 409 feed_reset
    "feed_snapshots_per_user": 5, # … saved lists kept per account (oldest deleted on insert)
    "admin_role_name_max": 60,    # POST / PUT /admin/roles name (chars — owner only, task 8.4c-2a1)
    "admin_staff_name_max": 80,   # POST /admin/staff/invite name (chars — owner only, task 8.4c-2a2)
    "staff_password_min": 12,     # admin staff password (chars — invite / password reset, task 8.4c-2a2; max = password_max_bytes)
    "data_export_kyc_url_ttl_s": 300,  # POST /me/export/kyc-docs — signed link lifetime in seconds (task 8.5b — fixed, not admin-editable)
}

RATES = {
    "post_create": (5, 600),      # company post create — per account
    "post_edit": (20, 600),       # company post edit — per account
    "report_submit": (10, 3600),  # reports — per account
    "report_repeat": (1, 86400),  # same reporter + same target — one report per day
    "mention_search": (60, 60),   # @mention search — per account
    "message_send": (30, 60),     # POST /messages/send — per account
    "view_count": (1, 86400),     # post / profile view — same viewer + same target counted once a day
    "login_email": (5, 900),      # failed logins per email (PR 1.4) → that email locked …
    "login_ip": (20, 900),        # … per client IP (many emails from one IP)
    "login_ip_email": (3, 900),   # … per IP + email pair
    "post_appreciate": (10, 10),  # أقدّر toggle — per account + post
    "post_save": (10, 10),        # save toggle — per account + post
    "comment_create": (10, 60),   # new comment — per account + post
    "comment_edit": (10, 60),     # comment edit — per account + comment
    "otp_send_user": (5, 3600),   # KYC OTP send (/kyc/email|phone/send) — per account + channel (task 4.3)
    "otp_send_target": (5, 3600), # … per normalised email / phone, from any account
    "otp_send_ip": (10, 3600),    # … per client IP, both channels together
    "block_set": (20, 3600),      # block / unblock (PUT + DELETE /blocks/{id}) — per account (task 5.4)
    "pwreset_ip": (10, 3600),     # POST /auth/password-reset/request — per client IP (task 5.1a → 4.2)
    "pwreset_email": (3, 3600),   # … per email address (over it: same reply, no email)
    "public_ip": (240, 60),       # every public route (works for a guest) — per client IP, one bucket (task 6 — §54o)
    "support_create": (10, 3600),        # new support ticket — per account (task 7.1)
    "support_guest_email": (2, 3600),    # guest ticket (login problems) — per email address
    "support_guest_ip": (2, 3600),       # … per client IP
    "support_guest_global": (60, 3600),  # … every guest ticket together (holds even when the IP is forged)
    "support_link_resend_email": (3, 3600),   # guest follow-up link resend — per email (over it: same reply, no email — 7.2a)
    "support_link_resend_ip": (10, 3600),     # … per client IP
    "support_reply_ticket": (20, 3600),       # requester replies per ticket — link + account + email together (7.5a)
    "support_track_ip": (60, 60),             # every /support/track API call — per client IP
    "support_track_code_gap": (1, 60),        # follow-up code send — cooldown per ticket (the page counts it down — 7.4)
    "support_track_code_ticket": (5, 3600),   # … per ticket per hour (over it: same reply, no email)
    "support_track_code_ip": (10, 3600),      # … per client IP → 429
    "support_inbound_sender": (3, 3600),      # new ticket from an inbound email — per sender address (over it: ignored, 7.3)
    "support_inbound_global": (100, 3600),    # … every inbound ticket together
    "admin_login_ip": (10, 900),      # admin login step 1 (password) — failures per client IP (task 8.4b)
    "admin_login_acct": (5, 900),     # … per account (owner / staff email)
    "admin_mfa_ip": (10, 900),        # admin login step 2 (authenticator / recovery code) — failures per client IP
    "admin_mfa_acct": (5, 900),       # … per account (owner / staff:<id>)
    "staff_link_ip": (20, 900),       # /staff/invite|mfa-reset|password-reset/* — every call per client IP (task 8.4c-2a2)
    "staff_link_token": (10, 900),    # … per link (SHA-256 of the token — wrong codes count here)
    "staff_forgot_ip": (10, 3600),    # <panel>/forgot — per client IP (task 8.4c-2a2)
    "staff_forgot_email": (3, 3600),  # … per email address (counted for unknown addresses too — same reply)
    "data_export": (3, 3600),         # POST /me/export — per account, reserved before bcrypt, every attempt counts (task 8.5b)
    "data_export_kyc": (3, 3600),     # POST /me/export/kyc-docs — per account, same rule, own bucket
}

REPORT_TYPES = ("fraud", "spam", "misleading", "harassment", "other")


def _load_post_tags(path: str = os.path.join(_ROOT, "static", "shared", "tw-options-data.js")) -> frozenset:
    """TW.POST_TAGS = [ … ]; → frozenset. Fails loudly at server start (F9) — never an empty allowlist."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"TW\.POST_TAGS\s*=\s*\[(.*?)\];", src, re.S)
    if not m:
        raise ValueError("[limits] TW.POST_TAGS not found in tw-options-data.js")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    tags = frozenset(re.findall(r"'([^'\\]+)'", body))
    if not tags:
        raise ValueError("[limits] TW.POST_TAGS is empty")
    return tags


POST_TAGS = _load_post_tags()

# What the pages need (window.TW_LIMITS) — limits only, no rates.
_CLIENT_LIMITS = ("message_max", "post_body_max", "post_tags_max", "report_reason_max",
                  "support_subject_max", "support_body_max",
                  "staff_password_min", "password_max_bytes",   # task 8.4c-2b-1 — staff link page hint only
                  "data_export_kyc_url_ttl_s")                  # task 8.5b — /settings KYC links warning (minutes)


def page_block(limit=None) -> str:
    """limit = the reader (server passes tw_settings.limit — admin values); default = LIMITS."""
    get = limit or LIMITS.__getitem__
    payload = json.dumps({"limits": {k: get(k) for k in _CLIENT_LIMITS},
                          "report_types": list(REPORT_TYPES)}, separators=(",", ":"))
    return "<script>window.TW_LIMITS=" + payload + ";</script>"
