"""tw_settings.py — Unified Admin Settings (task 4.1 · security settings 4.2 · docs/SYSTEMS_INDEX.md §25g ·
docs/rules/settings.md).

The ONE way the code reads an admin-editable limit / rate and the ONE writer of its value:
  REGISTRY      → explicit allowlist of editable settings (key · type · min · max · default from
                  tw_limits · security · requires_restart · group · twT label / description keys).
                  Only keys listed here are editable — tw_limits keys are never opened wholesale.
  limit(name)   → LIMITS value  (admin value when the key is in the registry, else tw_limits)
  rate(name)    → RATES (hits, window seconds) — same rule
  value(key)    → one registry setting's current value (admin value or the default)
  is_security(key) → a security setting (4.2: login locks · OTP / password reset · OTP send 4.3 · rate store · IP cache ·
                  page sizes · dedup windows · public routes per IP 6 · guest support tickets 7.1 · follow-up code / session 7.4) — own page section + typed-word confirm + audit "<route>_security"
  set_value / reset_value → write path (PUT / POST /admin/settings/{key}); cache updated at once
  reload()      → DB → in-memory cache (startup + every CACHE_TTL_S by server.py's refresh loop).
                  DB failure → defaults + the error logged (the site keeps running, F9).

Reads never touch the DB (memory only) — safe inside `async def` endpoints and under _rate_lock.
A change applies at once in the worker that saved it; any other worker picks it up within
CACHE_TTL_S (30 s) on its next refresh.

Storage: table `app_settings` (changed values only — a value equal to the default is deleted).
Audit: the admin_audit_middleware row of the request (server.py) with old_value / new_value.
❌ a secret / service key in the registry · ❌ reading tw_limits.LIMITS / RATES directly for a
registry key · ❌ a second settings table or cache.
"""
import threading

import tw_limits
from auth import db_conn

CACHE_TTL_S = 30          # other workers see a change within this (refresh loop period)
PERM = "settings.edit"    # admin JWT permission (owner = "*")


def _limit(name, mn, mx, group, unit="chars", security=False):
    return {"key": name, "source": ("LIMITS", name), "min": mn, "max": mx, "group": group, "unit": unit,
            "security": security}


def _rate(name, part, mn, mx, group, security=False):
    key = f"{name}_{'hits' if part == 0 else 'window_s'}"
    return {"key": key, "source": ("RATES", name, part), "min": mn, "max": mx, "group": group,
            "unit": "count" if part == 0 else "seconds", "security": security}


def _sec_limit(name, mn, mx, group, unit):
    return _limit(name, mn, mx, group, unit, security=True)


def _sec_rate(name, part, mn, mx, group):
    return _rate(name, part, mn, mx, group, security=True)


# Approved list (task 4.1 — the PR table). Minimums never stop a core feature (hits ≥ 1).
_DEFS = (
    _limit("message_max",        500, 10000, "messages"),
    _rate("message_send", 0,       5,   300, "messages"),
    _rate("message_send", 1,      10,   600, "messages"),
    _limit("post_body_max",      500, 10000, "posts"),
    _limit("post_tags_max",        1,    10, "posts", "count"),
    _rate("post_create", 0,        1,    50, "posts"),
    _rate("post_create", 1,       60,  3600, "posts"),
    _rate("post_edit", 0,          1,   100, "posts"),
    _rate("post_edit", 1,         60,  3600, "posts"),
    _rate("post_appreciate", 0,    1,    60, "posts"),
    _rate("post_appreciate", 1,    5,   300, "posts"),
    _rate("post_save", 0,          1,    60, "posts"),
    _rate("post_save", 1,          5,   300, "posts"),
    _rate("comment_create", 0,     1,    60, "comments"),
    _rate("comment_create", 1,    10,   600, "comments"),
    _rate("comment_edit", 0,       1,    60, "comments"),
    _rate("comment_edit", 1,      10,   600, "comments"),
    _rate("mention_search", 0,    10,   120, "comments"),   # 4.1a: max 300 → 120
    _rate("mention_search", 1,    10,   600, "comments"),
    _limit("report_reason_max",  200,  5000, "reports"),
    _limit("report_url_max",     200,  2048, "reports"),
    _rate("report_submit", 0,      1,    50, "reports"),
    _rate("report_submit", 1,    300, 86400, "reports"),
    _rate("block_set", 0,          1,   100, "reports"),
    _rate("block_set", 1,         60, 86400, "reports"),
    _limit("suspend_reason_max", 100,  2000, "admin"),
    _limit("job_reapply_week_max",   1,    20, "jobs", "count"),   # task 8.2a — counted from the DB, not _rate_store
    # ── security = True (task 4.2 — the PR table) — own section on the page, a warning + an explicit
    # confirm before saving, audit action *_security. Minimum: never opens guessing / flooding, never
    # locks normal users out · maximum: memory stays bounded. ❌ password_max_bytes (bcrypt cuts at 72 —
    # fixed, never in the registry). Every one is read per use → applies at once (requires_restart False).
    _sec_rate("login_email", 0,       3,     20, "sec_login"),
    _sec_rate("login_email", 1,     300,   3600, "sec_login"),
    _sec_rate("login_ip", 0,         10,    100, "sec_login"),
    _sec_rate("login_ip", 1,        300,   3600, "sec_login"),
    _sec_rate("login_ip_email", 0,    3,     10, "sec_login"),
    _sec_rate("login_ip_email", 1,  300,   3600, "sec_login"),
    _sec_limit("otp_max_attempts",    3,     10, "sec_otp", "count"),
    _sec_limit("otp_ttl_min",         5,     30, "sec_otp", "minutes"),
    _sec_rate("pwreset_ip", 0,        3,     50, "sec_otp"),
    _sec_rate("pwreset_ip", 1,      600,  86400, "sec_otp"),
    _sec_rate("pwreset_email", 0,     1,     10, "sec_otp"),
    _sec_rate("pwreset_email", 1,   600,  86400, "sec_otp"),
    # KYC OTP send (task 4.3) — per account + channel · per normalised target · per IP. Ranges keep
    # guessing impractical: worst case per target = 10 codes / hour × otp_max_attempts at its max (10)
    # = 2 400 guesses / day of 10^6 codes (≈ 0.24 %); window ≥ 1 hour.
    _sec_rate("otp_send_user", 0,     1,     10, "sec_otp"),
    _sec_rate("otp_send_user", 1,  3600,  86400, "sec_otp"),
    _sec_rate("otp_send_target", 0,   1,     10, "sec_otp"),
    _sec_rate("otp_send_target", 1, 3600, 86400, "sec_otp"),
    _sec_rate("otp_send_ip", 0,       1,     30, "sec_otp"),
    _sec_rate("otp_send_ip", 1,    3600,  86400, "sec_otp"),
    _sec_limit("mem_store_max_keys", 5000, 100000, "sec_capacity", "count"),
    _sec_limit("mem_store_sweep_s",   10,    600, "sec_capacity", "seconds"),
    _sec_limit("ip_country_cache_max", 1000, 100000, "sec_capacity", "count"),
    _sec_limit("ip_country_cache_ttl_s", 3600, 604800, "sec_capacity", "seconds"),
    _sec_limit("comments_page",        5,     50, "sec_pages", "count"),
    _sec_limit("comments_page_max",   10,    100, "sec_pages", "count"),
    _sec_limit("mention_limit_max",    5,     50, "sec_pages", "count"),
    _sec_limit("blocks_page_max",     10,    200, "sec_pages", "count"),
    _sec_rate("view_count", 1,      3600, 604800, "sec_dedup"),      # hits stay 1 (counted once) — window only
    _sec_rate("report_repeat", 1,   3600, 604800, "sec_dedup"),      # same — one report per window
    # Public routes (task 6 — §54o): one bucket per client IP on every route that works for a guest.
    # Minimum keeps a normal page load (≈ 8 calls) working behind a shared IP; maximum keeps it a limit.
    _sec_rate("public_ip", 0,        60,   2000, "sec_public"),
    _sec_rate("public_ip", 1,        10,    600, "sec_public"),
    # Support tickets (task 7.1 — docs/rules/support.md). Signed-in account: open tickets at once + new
    # tickets per window. Guest (login problems only): per email · per IP · all guests together — the
    # email + global caps hold even when the client IP is forged.
    _limit("support_open_max",     1,     20, "support", "count"),
    _rate("support_create", 0,     1,     50, "support"),
    _rate("support_create", 1,   600,  86400, "support"),
    _sec_rate("support_guest_email", 0,   1,     10, "sec_support"),
    _sec_rate("support_guest_email", 1, 600,  86400, "sec_support"),
    _sec_rate("support_guest_ip", 0,      1,     20, "sec_support"),
    _sec_rate("support_guest_ip", 1,    600,  86400, "sec_support"),
    _sec_rate("support_guest_global", 0, 10,   1000, "sec_support"),
    _sec_rate("support_guest_global", 1, 600, 86400, "sec_support"),
    # Guest follow-up link (task 7.2a): resend per email · per IP · replies per ticket (shared — 7.5a) · track calls per IP.
    _sec_rate("support_link_resend_email", 0, 1,    10, "sec_support"),
    _sec_rate("support_link_resend_email", 1, 600, 86400, "sec_support"),
    _sec_rate("support_link_resend_ip", 0,    1,    50, "sec_support"),
    _sec_rate("support_link_resend_ip", 1,  600, 86400, "sec_support"),
    _sec_rate("support_reply_ticket", 0,      1,   100, "sec_support"),   # 7.5a: link + account + email replies
    _sec_rate("support_reply_ticket", 1,    600, 86400, "sec_support"),
    _sec_rate("support_track_ip", 0,         10,   600, "sec_support"),
    _sec_rate("support_track_ip", 1,         10,   600, "sec_support"),
    # Guest follow-up code + session (task 7.4): cooldown per ticket · codes per ticket · per IP · session length.
    _sec_rate("support_track_code_gap", 0,    1,      3, "sec_support"),
    _sec_rate("support_track_code_gap", 1,   30,    600, "sec_support"),
    _sec_rate("support_track_code_ticket", 0, 1,     20, "sec_support"),
    _sec_rate("support_track_code_ticket", 1, 600, 86400, "sec_support"),
    _sec_rate("support_track_code_ip", 0,     1,     50, "sec_support"),
    _sec_rate("support_track_code_ip", 1,   600,  86400, "sec_support"),
    _sec_limit("support_track_session_hours", 1, 24, "sec_support", "hours"),
    # Inbound support mail (task 7.3): new tickets per sender address + every inbound ticket together.
    _sec_rate("support_inbound_sender", 0,   1,    20, "sec_support"),
    _sec_rate("support_inbound_sender", 1, 600, 86400, "sec_support"),
    _sec_rate("support_inbound_global", 0,  10,  1000, "sec_support"),
    _sec_rate("support_inbound_global", 1, 600, 86400, "sec_support"),
)

GROUPS = ("messages", "posts", "comments", "reports", "admin", "jobs", "support",
          "sec_login", "sec_otp", "sec_capacity", "sec_pages", "sec_dedup", "sec_public", "sec_support")


def _build(defs) -> dict:
    out = {}
    for d in defs:
        src = d["source"]
        default = tw_limits.LIMITS[src[1]] if src[0] == "LIMITS" else tw_limits.RATES[src[1]][src[2]]
        if not (d["min"] <= default <= d["max"]):
            raise ValueError(f"[settings] default of {d['key']} outside its range")   # fails at start (F9)
        out[d["key"]] = dict(d, type="int", default=default, requires_restart=False,
                             label_key=f"settings.item.{d['key']}", desc_key=f"settings.item.{d['key']}.desc")
    return out


REGISTRY = _build(_DEFS)
SECURITY_KEYS = frozenset(k for k, d in REGISTRY.items() if d["security"])
# source → registry key, for limit() / rate()
_BY_LIMIT = {d["source"][1]: k for k, d in REGISTRY.items() if d["source"][0] == "LIMITS"}
_BY_RATE = {(d["source"][1], d["source"][2]): k for k, d in REGISTRY.items() if d["source"][0] == "RATES"}

_lock = threading.Lock()
_overrides: dict = {}      # key → int (changed values only)
_hooks: list = []          # called after the values change (server.py rebuilds window.TW_LIMITS)


class SettingError(Exception):
    """Bad request on the write path → server maps to api_error(status, code, twT(text_key, vars))."""
    def __init__(self, status: int, code: str, text_key: str, **vars):
        super().__init__(code)
        self.status, self.code, self.text_key, self.vars = status, code, text_key, vars


def on_change(fn) -> None:
    _hooks.append(fn)


def _set_overrides(new: dict) -> None:
    global _overrides
    with _lock:
        changed = new != _overrides
        _overrides = new
    if changed:
        for fn in _hooks:
            try:
                fn()
            except Exception as e:
                print(f"[settings] change hook failed: {type(e).__name__}: {e}")


# ── reads (memory only) ──
def value(key: str) -> int:
    v = _overrides.get(key)
    return REGISTRY[key]["default"] if v is None else v


def limit(name: str) -> int:
    k = _BY_LIMIT.get(name)
    return value(k) if k else tw_limits.LIMITS[name]


def rate(name: str) -> tuple:
    hits, window = tw_limits.RATES[name]
    kh, kw = _BY_RATE.get((name, 0)), _BY_RATE.get((name, 1))
    return (value(kh) if kh else hits, value(kw) if kw else window)


def item(key: str) -> dict:
    d = REGISTRY[key]
    return {"key": key, "group": d["group"], "type": d["type"], "unit": d["unit"],
            "value": value(key), "default": d["default"], "min": d["min"], "max": d["max"],
            "changed": key in _overrides, "security": d["security"],
            "requires_restart": d["requires_restart"], "label_key": d["label_key"], "desc_key": d["desc_key"]}


def listing() -> list:
    return [item(k) for k in REGISTRY]


def is_security(key: str) -> bool:
    """A security setting (task 4.2) — the page's warning section + the audit action *_security."""
    return key in SECURITY_KEYS


# ── DB ──
def migrate_app_settings():
    """Idempotent (task 4.1) — app_settings (the audit old/new columns: admin_insights.migrate_admin_audit_log).
    Optional: a failure leaves every setting on its default (reads fall back) and the write path 500s.
    Same SQL as docs/migrations/4.1_app_settings.sql (applied by hand on production)."""
    with db_conn() as conn:
        conn.run("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key        TEXT PRIMARY KEY,
                value      BIGINT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_by TEXT
            )""")


def _clean(rows) -> dict:
    out = {}
    for k, v in rows:
        d = REGISTRY.get(k)
        if d is None or v is None or not (d["min"] <= int(v) <= d["max"]):
            print(f"[settings] stored value ignored: {k!r}")   # not in the allowlist / out of range
            continue
        if int(v) != d["default"]:
            out[k] = int(v)
    return out


def reload() -> bool:
    """DB → cache. Failure → defaults (logged) — never raises."""
    try:
        with db_conn() as conn:
            rows = conn.run("SELECT key, value FROM app_settings")
        _set_overrides(_clean(rows))
        return True
    except Exception as e:
        print(f"[settings] load failed — defaults in use: {type(e).__name__}: {e}")
        _set_overrides({})
        return False


def validate(key: str, raw) -> int:
    d = REGISTRY.get(key)
    if d is None:
        raise SettingError(404, "unknown_setting", "settings.error.unknown")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise SettingError(422, "invalid_type", "settings.error.type")
    if not (d["min"] <= raw <= d["max"]):
        raise SettingError(422, "out_of_range", "settings.error.range", min=d["min"], max=d["max"])
    return raw


def _write(key: str, new, actor: str) -> tuple:
    """One transaction: the row locked, old value read, new stored (or deleted when = default).
    → (old, new) effective values. Cache updated after the commit."""
    d = REGISTRY[key]
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run("SELECT value FROM app_settings WHERE key = :k FOR UPDATE", k=key)
            old = int(rows[0][0]) if rows else d["default"]
            if new is None or new == d["default"]:
                conn.run("DELETE FROM app_settings WHERE key = :k", k=key)
                new = d["default"]
            else:
                conn.run("INSERT INTO app_settings (key, value, updated_by) VALUES (:k, :v, :by) "
                         "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW(), "
                         "updated_by = EXCLUDED.updated_by", k=key, v=new, by=str(actor)[:100])
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    with _lock:
        nxt = dict(_overrides)
    if new == d["default"]:
        nxt.pop(key, None)
    else:
        nxt[key] = new
    _set_overrides(nxt)
    return old, new


def set_value(key: str, raw, actor: str) -> tuple:
    return _write(key, validate(key, raw), actor)


def reset_value(key: str, actor: str) -> tuple:
    if key not in REGISTRY:
        raise SettingError(404, "unknown_setting", "settings.error.unknown")
    return _write(key, None, actor)
