"""tw_limits.py — Input Limits (task 5.0h · docs/SYSTEMS_INDEX.md §54n · ARCHITECTURE.md §76).

The ONE place for input size / flood limits (server constants now — they move to the settings
system when it is built; nothing else in the code may repeat a value):
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
    "block_set": (20, 3600),      # block / unblock (PUT + DELETE /blocks/{id}) — per account (task 5.4)
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
_CLIENT_LIMITS = ("message_max", "post_body_max", "post_tags_max", "report_reason_max")


def page_block() -> str:
    payload = json.dumps({"limits": {k: LIMITS[k] for k in _CLIENT_LIMITS},
                          "report_types": list(REPORT_TYPES)}, separators=(",", ":"))
    return "<script>window.TW_LIMITS=" + payload + ";</script>"
