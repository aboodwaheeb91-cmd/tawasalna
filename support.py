"""support.py — Support Tickets (task 7.1 · 7.2a · docs/rules/support.md · docs/SYSTEMS_INDEX.md §62 ·
ARCHITECTURE.md §81).

The ONE place support tickets are read and written (server.py only validates the request, checks the
limits and calls these).

  support_tickets      public_id (generate_public_id("H")) · user_id (NULL = guest) · guest_email · category ·
                       status · priority · subject · details (JSONB, per-category allowlist) · faq_id ·
                       legacy_category · created_at · updated_at · last_message_at · closed_at (= resolved at)
  support_messages     ticket_id · author_type user | guest | admin · author_id (user id / admin sub; guest NULL) ·
                       body · created_at
  support_guest_otp    guest support code (auth.guest_otp_issue / guest_otp_verify — same OTP rules as KYC)
  support_guest_access guest follow-up link (7.2a): sha256 hex of the token only · expires_at · revoked_at ·
                       last_used_at — issue_guest_link is the only writer
  support_reply_tokens Reply-To token of the support emails (7.3): support+<token>@ — sha256 hex only,
                       newest REPLY_TOKEN_KEEP per ticket — issue_reply_token is the only writer
  support_inbound_events one row per handled inbound email (7.3): svix_id UNIQUE · email_id UNIQUE · outcome ·
                       ticket_id — the same event twice = no effect. No address, no text.

Rules (enforced here, inside one transaction each):
  - an account sees / replies to / resolves its own tickets only — anything else = LookupError (→ 404);
    a guest link reaches its own guest ticket only (same 404 for a wrong / expired / revoked token)
  - statuses new → in_review → awaiting_user → resolved — every change through transition()
  - open tickets per account (status ≠ resolved) ≤ open_max — create AND reopen (row lock on users)
  - a reply on a resolved ticket within REOPEN_DAYS of closed_at reopens it (→ in_review), after that →
    SupportError reopen_expired («افتح طلباً جديداً»)
  - priority only from the admin (default normal) · a guest ticket is always category `account` (DB CHECK)
  - blocks / suspension never filter tickets (no bs.visible_sql here)
  - inbound mail (7.3): a new email to info@ / support@ = a GUEST ticket (source email, category general —
    never linked to an account) · mail to support+<token>@ = a message on that ticket only when From is
    its owner's address (account email or guest_email) — anything else is ignored
Transition 7.2a (until production stage B rewrites the rows): every read goes through normalize_sql()
(open → new / in_review · closed → resolved · other → general); writes store the new values only.
Pure DB — no FastAPI. Texts = twT keys (support.error.*) mapped by server.py.
"""
import datetime as _dt
import hashlib
import json
import re
import secrets
import unicodedata

from auth import db_conn, generate_public_id
import blocks_suspension as bs
import email_service

CATEGORIES = ("account", "verification", "profile", "jobs", "education", "technical", "complaint", "general")
GUEST_CATEGORY = "account"
STATUSES = ("new", "in_review", "awaiting_user", "resolved")
ADMIN_REPLY_STATUSES = ("awaiting_user", "resolved")   # next_status of an admin reply — required
PRIORITIES = ("normal", "high", "urgent")
DEFAULT_PRIORITY = "normal"
REOPEN_DAYS = 14          # a resolved ticket answered within this many days of closed_at reopens
PUBLIC_ID_PREFIX = "H"    # ARCHITECTURE.md → Public ID System prefix table
ADMIN_PAGE_MAX = 50
USER_LIST_MAX = 50
ADMIN_SORTS = ("newest", "oldest_waiting", "priority")
REQUESTERS = ("guest", "user")
SOURCES = ("web", "email")            # where the ticket came from (7.3) — email = inbound mail
INBOUND_CATEGORY = "general"          # a ticket from an inbound email (7.3)

# Values production may still hold until stage B (docs/migrations/7.2a_B_migrate.sql) — read only.
_LEGACY_STATUS_CLOSED = "closed"   # → resolved
_LEGACY_STATUS_OPEN = "open"       # → in_review when an admin message exists, else new
_LEGACY_CATEGORY = {"other": "general"}

# ── details (JSONB) — allowlist per category: an unknown key = 422 ──
SITE_URL_PREFIX = "https://tawasolna.com/"
URL_MAX = 300
DETAILS_MAX = 4000        # characters of the stored JSON text (DB CHECK length(details::text) ≤ 4000)


def _enum(*values):
    return {"type": "enum", "values": list(values)}


def _text(n):
    return {"type": "text", "max": n}


_URL = {"type": "url", "max": URL_MAX}
FIELDS = {
    "account": {"issue": _enum("forgot_password", "no_code", "login_failed", "lost_access", "hacked", "other"),
                "account_name": _text(100), "account_ref": {"type": "tw_id", "max": 32},
                "account_email": {"type": "email", "max": 254}, "account_phone": {"type": "phone", "max": 20}},
    "verification": {"request_type": _enum("personal", "company", "edu"), "submitted_date": {"type": "date"}},
    "profile": {"page_url": _URL},
    "jobs": {"job_url": _URL, "kind": _enum("apply", "post")},
    "education": {"name": _text(120)},
    "technical": {"page_url": _URL, "device": _enum("mobile", "desktop")},
    "complaint": {"content_url": _URL},
    "general": {},
}

# Help articles a ticket may point at (texts = twT on the page) — ordered by category.
FAQ_IDS = {
    "account": ("forgot", "no_code", "login_failed", "lost_access", "change_email", "security"),
    "verification": ("how", "result"),
    "profile": ("edit", "not_visible"),
    "jobs": ("track", "no_reply", "withdraw", "edit_job"),
    "education": ("where",),
    "technical": ("page_broken", "still_broken"),
    "complaint": ("report_account", "report_post", "report_status", "general"),
    "general": ("idea", "messaging", "track_ticket"),
}
_FAQ_ALL = frozenset(f for ids in FAQ_IDS.values() for f in ids)

# ── guest follow-up link ──
GUEST_LINK_DAYS = 90      # a new link lives this long; each guest reply extends the used one again
GUEST_LINK_KEEP = 3       # active links per ticket (the newest ones) after a new one is issued
GUEST_RESEND_MAX = 5      # tickets in one resend (newest first)
TRACK_PATH = "/support/track"
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


class SupportError(Exception):
    """Refused by a ticket rule → server maps to api_error(status, code, twT(text_key), field)."""
    def __init__(self, status: int, code: str, text_key: str, field: str = None):
        super().__init__(code)
        self.status, self.code, self.text_key, self.field = status, code, text_key, field


def _in(values) -> str:
    return ", ".join("'" + v + "'" for v in values)   # fixed tuples above only — never caller input


# ── schema — the FINAL shape (new DBs + CI). Production: docs/migrations/7.2a_A_expand.sql (before the
# merge) + 7.2a_B_migrate.sql (after). ❌ altering production constraints from here (startup). ──
SCHEMA_SQL = (
    f"""CREATE TABLE IF NOT EXISTS support_tickets (
        id              SERIAL PRIMARY KEY,
        public_id       TEXT NOT NULL UNIQUE,
        user_id         INTEGER NULL REFERENCES users(id) ON DELETE CASCADE,
        guest_email     TEXT NULL,
        category        TEXT NOT NULL CONSTRAINT support_tickets_category_chk CHECK (category IN ({_in(CATEGORIES)})),
        status          TEXT NOT NULL DEFAULT 'new' CONSTRAINT support_tickets_status_chk CHECK (status IN ({_in(STATUSES)})),
        priority        TEXT NOT NULL DEFAULT 'normal' CONSTRAINT support_tickets_priority_chk CHECK (priority IN ({_in(PRIORITIES)})),
        subject         TEXT NOT NULL CONSTRAINT support_tickets_subject_chk CHECK (length(btrim(subject)) > 0),
        details         JSONB NOT NULL DEFAULT '{{}}'::jsonb CONSTRAINT support_tickets_details_chk
                        CHECK (jsonb_typeof(details) = 'object' AND length(details::text) <= {DETAILS_MAX}),
        faq_id          TEXT NULL CONSTRAINT support_tickets_faq_chk CHECK (faq_id ~ '^[a-z0-9_]{{1,64}}$'),
        legacy_category TEXT NULL,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        closed_at       TIMESTAMPTZ NULL,
        source          TEXT NOT NULL DEFAULT 'web' CONSTRAINT support_tickets_source_chk CHECK (source IN ({_in(SOURCES)})),
        CONSTRAINT support_tickets_owner_chk CHECK (user_id IS NOT NULL OR guest_email IS NOT NULL),
        CONSTRAINT support_tickets_guest_category_chk
            CHECK (user_id IS NOT NULL OR category = '{GUEST_CATEGORY}' OR source = 'email')
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets (user_id, last_message_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_inbox ON support_tickets (status, last_message_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_guest_email ON support_tickets (guest_email) WHERE user_id IS NULL",
    """CREATE TABLE IF NOT EXISTS support_messages (
        id          SERIAL PRIMARY KEY,
        ticket_id   INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
        author_type TEXT NOT NULL CONSTRAINT support_messages_author_chk CHECK (author_type IN ('user', 'guest', 'admin')),
        author_id   TEXT NULL,
        body        TEXT NOT NULL CONSTRAINT support_messages_body_chk CHECK (length(btrim(body)) > 0),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages (ticket_id, created_at)",
    """CREATE TABLE IF NOT EXISTS support_guest_otp (
        email      TEXT PRIMARY KEY,
        code_hash  TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        attempts   INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS support_guest_access (
        id           SERIAL PRIMARY KEY,
        ticket_id    INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
        token_hash   TEXT NOT NULL UNIQUE CONSTRAINT support_guest_access_hash_chk CHECK (token_hash ~ '^[0-9a-f]{64}$'),
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at   TIMESTAMPTZ NOT NULL,
        revoked_at   TIMESTAMPTZ NULL,
        last_used_at TIMESTAMPTZ NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_guest_access_ticket ON support_guest_access (ticket_id, created_at DESC)",
    # 7.3 — new tables only (production: docs/migrations/7.3_inbound.sql adds the source column + constraint).
    """CREATE TABLE IF NOT EXISTS support_reply_tokens (
        id         SERIAL PRIMARY KEY,
        ticket_id  INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE CONSTRAINT support_reply_tokens_hash_chk CHECK (token_hash ~ '^[0-9a-f]{64}$'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_reply_tokens_ticket ON support_reply_tokens (ticket_id, created_at DESC)",
    """CREATE TABLE IF NOT EXISTS support_inbound_events (
        id         SERIAL PRIMARY KEY,
        svix_id    TEXT NOT NULL UNIQUE,
        email_id   TEXT NOT NULL UNIQUE,
        outcome    TEXT NOT NULL CONSTRAINT support_inbound_events_outcome_chk CHECK (outcome ~ '^[a-z_]{1,32}$'),
        ticket_id  INTEGER NULL REFERENCES support_tickets(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
)


def migrate_support():
    """Idempotent (task 7.1 · 7.2a). Optional startup migration: a failure only stops support (its routes 500).
    CREATE … IF NOT EXISTS only — an existing table is never altered here (production = the SQL files)."""
    with db_conn() as conn:
        for sql in SCHEMA_SQL:
            conn.run(sql)


# ── the ONE legacy-value normaliser (transition 7.2a, until stage B) ──
def normalize_sql(t: str = "t") -> tuple:
    """(category expr, status expr) for table alias t — every read, filter, sort and count uses these:
    status open → in_review when an admin message exists, else new · closed → resolved ·
    category other → general · anything else unchanged. Writes store the new values only."""
    admin_msg = (f"EXISTS (SELECT 1 FROM support_messages m WHERE m.ticket_id = {t}.id "
                 f"AND m.author_type = 'admin')")
    status = (f"(CASE {t}.status WHEN '{_LEGACY_STATUS_OPEN}' THEN (CASE WHEN {admin_msg} THEN 'in_review' "
              f"ELSE 'new' END) WHEN '{_LEGACY_STATUS_CLOSED}' THEN 'resolved' ELSE {t}.status END)")
    category = ("(CASE " + " ".join(f"WHEN {t}.category = '{old}' THEN '{new}'" for old, new in _LEGACY_CATEGORY.items())
                + f" ELSE {t}.category END)")
    return category, status


_CAT_SQL, _STATUS_SQL = normalize_sql()


# ── status transitions — the ONE rule ──
def transition(current: str, event: str, target: str = None, reopen_ok: bool = False) -> str:
    """→ the new status.
      open               → new
      admin_reply        → target ∈ ADMIN_REPLY_STATUSES (required, else 422)
      admin_set          → target ∈ STATUSES (any — 422 otherwise)
      requester_reply    → in_review (new / in_review / awaiting_user); resolved → in_review only when
                           reopen_ok (within REOPEN_DAYS of closed_at), else 409 reopen_expired
      requester_resolve  → resolved"""
    if event == "open":
        return "new"
    if event == "admin_reply":
        if target not in ADMIN_REPLY_STATUSES:
            raise SupportError(422, "invalid_next_status", "support.error.next_status", "next_status")
        return target
    if event == "admin_set":
        if target not in STATUSES:
            raise SupportError(422, "invalid_status", "support.error.invalid_value", "status")
        return target
    if event == "requester_reply":
        if current == "resolved" and not reopen_ok:
            raise SupportError(409, "reopen_expired", "support.error.reopen_expired")
        return "in_review"
    if event == "requester_resolve":
        return "resolved"
    raise ValueError("unknown support event")


def _closed_sql(old: str, new: str) -> str:
    """closed_at = the time it was resolved: set on → resolved, cleared on reopen, kept otherwise."""
    if new == "resolved":
        return "" if old == "resolved" else ", closed_at = NOW()"
    return ", closed_at = NULL"


# ── input checks (server.py calls these before any write) ──
def _no_control(v: str) -> bool:
    return not any(unicodedata.category(ch) == "Cc" for ch in v)


def _check_value(spec: dict, v: str) -> bool:
    kind = spec["type"]
    if len(v) > spec.get("max", URL_MAX):
        return False
    if kind == "enum":
        return v in spec["values"]
    if kind == "text":
        return True
    if kind == "url":
        return v.startswith(SITE_URL_PREFIX) and not re.search(r"[\s\"'<>\\]", v)
    if kind == "tw_id":
        return re.fullmatch(r"[UCT][A-Za-z0-9]{4,31}", v) is not None
    if kind == "email":
        return email_service.valid_address(v)
    if kind == "phone":
        return re.fullmatch(r"[0-9+]{1,20}", v) is not None
    if kind == "date":
        try:
            d = _dt.date.fromisoformat(v) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None
        except ValueError:
            d = None
        # not in the future — the latest calendar date anywhere on earth (UTC+14) is still "today"
        latest = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=14)).date()
        return d is not None and d <= latest
    return False


def _dumps(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, separators=(", ", ": "))   # ≈ PostgreSQL jsonb text


def clean_details(category: str, raw) -> dict:
    """The ticket's details for its category → clean dict, else SupportError 422 (field details.<key>).
    None → {} · not an object / too big / unknown key / not text / control char / bad value → 422."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SupportError(422, "invalid_details", "support.error.details", "details")
    try:
        if len(_dumps(raw)) > DETAILS_MAX:
            raise SupportError(422, "details_too_large", "support.error.details", "details")
    except (TypeError, ValueError):
        raise SupportError(422, "invalid_details", "support.error.details", "details")
    allowed = FIELDS.get(category, {})
    out = {}
    for k, v in raw.items():
        if k not in allowed:
            raise SupportError(422, "unknown_detail", "support.error.details", "details." + str(k)[:64])
        if not isinstance(v, str) or not _no_control(v):
            raise SupportError(422, "invalid_detail", "support.error.details", "details." + k)
        v = v.strip()
        if not v:
            continue
        if not _check_value(allowed[k], v):
            raise SupportError(422, "invalid_detail", "support.error.details", "details." + k)
        out[k] = v
    if len(_dumps(out)) > DETAILS_MAX:
        raise SupportError(422, "details_too_large", "support.error.details", "details")
    return out


def clean_faq(raw):
    """None / "" → None · an id of FAQ_IDS → it · anything else → 422."""
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str) or raw not in _FAQ_ALL:
        raise SupportError(422, "invalid_faq", "support.error.faq", "faq_id")
    return raw


def meta() -> dict:
    """GET /support/meta — lists only (texts are twT keys on the page)."""
    return {"categories": list(CATEGORIES), "guest_category": GUEST_CATEGORY,
            "fields": {c: [dict(spec, key=k) for k, spec in FIELDS[c].items()] for c in CATEGORIES},
            "faq": {c: list(FAQ_IDS[c]) for c in CATEGORIES}}


# ── helpers ──
_TICKET_COLS = ("id", "public_id", "user_id", "guest_email", "category", "status", "priority", "subject",
                "details", "faq_id", "legacy_category", "created_at", "updated_at", "last_message_at",
                "closed_at", "source", "within_reopen")
_TICKET_EXPR = {"category": _CAT_SQL, "status": _STATUS_SQL,
                "within_reopen": f"(t.closed_at IS NULL OR t.closed_at > NOW() - {int(REOPEN_DAYS)} * INTERVAL '1 day')"}
_TICKET_FIELDS = ", ".join(_TICKET_EXPR.get(c, "t." + c) for c in _TICKET_COLS)
_TICKET_SELECT = "SELECT " + _TICKET_FIELDS + " FROM support_tickets t"


def _ticket(row) -> dict:
    t = dict(zip(_TICKET_COLS, row))
    if isinstance(t["details"], str):
        t["details"] = json.loads(t["details"] or "{}")
    t["details"] = t["details"] or {}
    return t


def _messages(conn, ticket_id: int, admin: bool) -> list:
    rows = conn.run("SELECT id, author_type, author_id, body, created_at FROM support_messages "
                    "WHERE ticket_id = :t ORDER BY created_at, id", t=ticket_id)
    out = []
    for mid, atype, aid, body, created in rows:
        m = {"id": int(mid), "author_type": atype, "body": body, "created_at": created}
        if admin:
            m["author_id"] = aid
        out.append(m)
    return out


def _requester_view(t: dict) -> dict:
    """What the account / the guest sees of its own ticket — no priority, no internal id, no legacy value."""
    out = {k: t[k] for k in ("public_id", "category", "status", "subject", "details", "faq_id", "created_at",
                             "last_message_at", "closed_at")}
    out["can_reopen"] = t["status"] != "resolved" or bool(t["within_reopen"])
    return out


def _lock_user_open(conn, user_id: int, open_max: int, exclude_id: int = None) -> None:
    """Row lock on the account (serialises its creates / reopens) → refuse past open_max (status ≠ resolved)."""
    conn.run("SELECT id FROM users WHERE id = :u FOR UPDATE", u=user_id)
    n = conn.run(f"SELECT COUNT(*) FROM support_tickets t WHERE t.user_id = :u AND {_STATUS_SQL} <> 'resolved' "
                 "AND t.id <> :x", u=user_id, x=exclude_id or 0)[0][0]
    if int(n) >= int(open_max):
        raise SupportError(409, "too_many_open", "support.error.too_many_open")


def _tx(fn):
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            out = fn(conn)
            conn.run("COMMIT")
            return out
        except Exception:
            conn.run("ROLLBACK")
            raise


def _insert_ticket(conn, user_id, guest_email, category, subject, details, faq_id, source="web") -> tuple:
    status = transition(None, "open")   # written explicitly — production's default stays 'open' until stage B
    for _ in range(3):   # 36^10 ids — a clash is practically impossible, retried anyway
        rows = conn.run(
            "INSERT INTO support_tickets (public_id, user_id, guest_email, category, status, subject, details, faq_id, "
            "source) VALUES (:p, :u, :g, :c, :st, :s, CAST(:d AS jsonb), :f, :src) ON CONFLICT (public_id) DO NOTHING "
            "RETURNING id, public_id",
            p=generate_public_id(PUBLIC_ID_PREFIX), u=user_id, g=guest_email, c=category, st=status, s=subject,
            d=_dumps(details or {}), f=faq_id, src=source)
        if rows:
            return int(rows[0][0]), rows[0][1]
    raise RuntimeError("support public_id clash")


def _insert_message(conn, ticket_id: int, author_type: str, author_id, body: str) -> int:
    rows = conn.run("INSERT INTO support_messages (ticket_id, author_type, author_id, body) "
                    "VALUES (:t, :a, :i, :b) RETURNING id",
                    t=ticket_id, a=author_type, i=None if author_id is None else str(author_id), b=body)
    return int(rows[0][0])


def _set_status(conn, t: dict, new: str, message: bool) -> None:
    conn.run("UPDATE support_tickets SET status = :s, updated_at = NOW()"
             + (", last_message_at = NOW()" if message else "") + _closed_sql(t["status"], new)
             + " WHERE id = :t", s=new, t=t["id"])


def _requester_reply(conn, t: dict, author_type: str, author_id, body: str, open_max=None) -> dict:
    """Account / guest reply → in_review; on a resolved ticket within REOPEN_DAYS it reopens (open_max for
    an account), later → 409."""
    reopened = t["status"] == "resolved"
    new = transition(t["status"], "requester_reply", reopen_ok=bool(t["within_reopen"]))
    if reopened and t["user_id"] and open_max is not None:
        _lock_user_open(conn, t["user_id"], open_max, exclude_id=t["id"])
    _insert_message(conn, t["id"], author_type, author_id, body)
    _set_status(conn, t, new, message=True)
    return {"public_id": t["public_id"], "status": new, "reopened": reopened}


def _requester_resolve(conn, t: dict) -> dict:
    new = transition(t["status"], "requester_resolve")
    if t["status"] != new:
        _set_status(conn, t, new, message=False)
    return {"public_id": t["public_id"], "status": new}


# ── account ──
def create_user_ticket(user_id: int, category: str, subject: str, body: str, open_max: int,
                       details: dict = None, faq_id: str = None) -> dict:
    def fn(conn):
        _lock_user_open(conn, user_id, open_max)
        tid, pid = _insert_ticket(conn, user_id, None, category, subject, details, faq_id)
        _insert_message(conn, tid, "user", user_id, body)
        return {"public_id": pid}
    return _tx(fn)


def list_user_tickets(user_id: int, limit: int = USER_LIST_MAX) -> list:
    with db_conn() as conn:
        rows = conn.run(_TICKET_SELECT + " WHERE t.user_id = :u ORDER BY t.last_message_at DESC, t.id DESC LIMIT :l",
                        u=user_id, l=max(1, min(USER_LIST_MAX, int(limit))))
    return [_requester_view(_ticket(r)) for r in rows]


def get_user_ticket(public_id: str, user_id: int) -> dict:
    with db_conn() as conn:
        rows = conn.run(_TICKET_SELECT + " WHERE t.public_id = :p AND t.user_id = :u", p=public_id, u=user_id)
        if not rows:
            raise LookupError("ticket")
        t = _ticket(rows[0])
        out = _requester_view(t)
        out["messages"] = _messages(conn, t["id"], admin=False)
        return out


def _locked_user_ticket(conn, public_id: str, user_id: int) -> dict:
    rows = conn.run(_TICKET_SELECT + " WHERE t.public_id = :p AND t.user_id = :u FOR UPDATE OF t",
                    p=public_id, u=user_id)
    if not rows:
        raise LookupError("ticket")
    return _ticket(rows[0])


def user_reply(public_id: str, user_id: int, body: str, open_max: int) -> dict:
    return _tx(lambda conn: _requester_reply(conn, _locked_user_ticket(conn, public_id, user_id),
                                             "user", user_id, body, open_max))


def user_resolve(public_id: str, user_id: int) -> dict:
    """«انحلّت» → resolved (closed_at = now)."""
    return _tx(lambda conn: _requester_resolve(conn, _locked_user_ticket(conn, public_id, user_id)))


# ── guest follow-up link ──
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ticket_path(public_id: str) -> str:
    """The account's ticket on /support (7.2b — bell + support_reply email); support.js opens it."""
    return "/support?ticket=" + public_id


def track_link(site_url: str, token: str) -> str:
    """{site_url}/support/track#t=<token> — the fragment never reaches a server log or a Referer."""
    return site_url.rstrip("/") + TRACK_PATH + "#t=" + token


def issue_guest_link(ticket_id: int, keep: int = GUEST_LINK_KEEP, conn=None) -> str:
    """The ONLY writer of support_guest_access. Revokes every active link of the ticket except the newest
    keep - 1, then a new one (GUEST_LINK_DAYS) → at most `keep` active (keep=0 / 1 → only the new one).
    Returns the plain token (for the email only — only its sha256 hex is stored)."""
    def fn(c):
        c.run("SELECT id FROM support_tickets WHERE id = :t FOR UPDATE", t=ticket_id)
        c.run("UPDATE support_guest_access SET revoked_at = NOW() WHERE ticket_id = :t AND revoked_at IS NULL "
              "AND id NOT IN (SELECT id FROM support_guest_access WHERE ticket_id = :t AND revoked_at IS NULL "
              "AND expires_at > NOW() ORDER BY created_at DESC, id DESC LIMIT :k)",
              t=ticket_id, k=max(0, int(keep) - 1))
        token = secrets.token_urlsafe(32)
        c.run("INSERT INTO support_guest_access (ticket_id, token_hash, expires_at) "
              "VALUES (:t, :h, NOW() + :d * INTERVAL '1 day')", t=ticket_id, h=_token_hash(token), d=GUEST_LINK_DAYS)
        return token
    return fn(conn) if conn is not None else _tx(fn)


def _guest_access(conn, token) -> tuple:
    """(access id, locked guest ticket) — wrong / expired / revoked / not a guest ticket → LookupError (one 404)."""
    if not isinstance(token, str) or not _TOKEN_RE.match(token):
        raise LookupError("link")
    rows = conn.run("SELECT a.id, " + _TICKET_FIELDS + " FROM support_guest_access a "
                    "JOIN support_tickets t ON t.id = a.ticket_id WHERE a.token_hash = :h AND a.revoked_at IS NULL "
                    "AND a.expires_at > NOW() AND t.user_id IS NULL FOR UPDATE OF a, t", h=_token_hash(token))
    if not rows:
        raise LookupError("link")
    conn.run("UPDATE support_guest_access SET last_used_at = NOW() WHERE id = :a", a=rows[0][0])
    return int(rows[0][0]), _ticket(rows[0][1:])


def create_guest_ticket(email: str, subject: str, body: str, details: dict = None, faq_id: str = None) -> dict:
    """→ {public_id, token} — the token goes into the support_guest_link email only, never into a reply."""
    def fn(conn):
        tid, pid = _insert_ticket(conn, None, email, GUEST_CATEGORY, subject, details, faq_id)
        _insert_message(conn, tid, "guest", None, body)
        return {"public_id": pid, "token": issue_guest_link(tid, conn=conn)}
    return _tx(fn)


def guest_view(token) -> dict:
    def fn(conn):
        _, t = _guest_access(conn, token)
        out = _requester_view(t)
        out["messages"] = _messages(conn, t["id"], admin=False)
        return out
    return _tx(fn)


def guest_reply(token, body: str, allow=None) -> dict:
    """allow(public_id) → False = the per-ticket rate is full → 429 (nothing written). The used link lives
    GUEST_LINK_DAYS from now."""
    def fn(conn):
        aid, t = _guest_access(conn, token)
        if allow is not None and not allow(t["public_id"]):
            raise SupportError(429, "rate_limited", "limits.rate_limited")
        out = _requester_reply(conn, t, "guest", None, body)
        conn.run("UPDATE support_guest_access SET expires_at = NOW() + :d * INTERVAL '1 day' WHERE id = :a",
                 a=aid, d=GUEST_LINK_DAYS)
        return out
    return _tx(fn)


def guest_resolve(token) -> dict:
    return _tx(lambda conn: _requester_resolve(conn, _guest_access(conn, token)[1]))


def guest_resend(email: str) -> list:
    """The guest's tickets for this address (not resolved, or resolved < REOPEN_DAYS ago — newest
    GUEST_RESEND_MAX): every link revoked + a new one each → [(public_id, token)]. [] → no email."""
    def fn(conn):
        rows = conn.run(f"SELECT t.id, t.public_id FROM support_tickets t WHERE t.user_id IS NULL "
                        f"AND t.guest_email = :e AND ({_STATUS_SQL} <> 'resolved' OR t.closed_at IS NULL "
                        f"OR t.closed_at > NOW() - {int(REOPEN_DAYS)} * INTERVAL '1 day') "
                        "ORDER BY t.last_message_at DESC, t.id DESC LIMIT :n", e=email, n=GUEST_RESEND_MAX)
        return [(pid, issue_guest_link(int(tid), keep=0, conn=conn)) for tid, pid in rows]
    return _tx(fn)


# ── admin (support.manage) ──
_REQUESTER_SQL = "LEFT JOIN users u ON u.id = t.user_id"
# guest_match (7.3): a guest ticket whose address is an account's email — a hint only, never a link.
_REQUESTER_COLS = (", u.tw_id, u.full_name, u.email, u.user_type, (t.user_id IS NULL AND EXISTS (SELECT 1 FROM users ux "
                   "WHERE lower(ux.email) = lower(t.guest_email)))")
_ADMIN_SELECT = "SELECT " + _TICKET_FIELDS + _REQUESTER_COLS + " FROM support_tickets t " + _REQUESTER_SQL
_ORDER = {"newest": "t.created_at DESC, t.id DESC",
          "oldest_waiting": "t.last_message_at ASC, t.id ASC",
          "priority": "CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, t.last_message_at DESC, t.id DESC"}


def _admin_row(row) -> dict:
    t = _ticket(row[:len(_TICKET_COLS)])
    tw_id, name, email, utype, guest_match = row[len(_TICKET_COLS):]
    t["requester"] = ({"kind": "user", "tw_id": tw_id, "name": name or "", "email": email or "", "user_type": utype}
                      if t["user_id"] else {"kind": "guest", "email": t["guest_email"] or "",
                                            "matches_account": bool(guest_match)})
    for k in ("id", "user_id", "within_reopen"):
        t.pop(k)
    return t


def _bad_filter(field: str):
    return SupportError(422, "invalid_filter", "support.error.invalid_value", field)


def admin_list(status: str = "", category: str = "", priority: str = "", page: int = 1, limit: int = 20,
               requester: str = "", q: str = "", sort: str = "") -> dict:
    """Filters status · category · priority · requester (guest | user) · q (an H id exactly, or an email —
    the guest's or the account's) · sort newest (created) | oldest_waiting (last message first) | priority."""
    where, params = [], {}
    for col, expr, val, allowed in (("status", _STATUS_SQL, status, STATUSES), ("category", _CAT_SQL, category, CATEGORIES),
                                    ("priority", "t.priority", priority, PRIORITIES)):
        if val:
            if val not in allowed:
                raise _bad_filter(col)
            where.append(f"{expr} = :{col}")
            params[col] = val
    if requester:
        if requester not in REQUESTERS:
            raise _bad_filter("requester")
        where.append("t.user_id IS NULL" if requester == "guest" else "t.user_id IS NOT NULL")
    q = (q or "").strip()
    if q:
        if re.fullmatch(r"[Hh][A-Za-z0-9]{10}", q):
            where.append("t.public_id = :q")
            params["q"] = q.upper()
        elif "@" in q and len(q) <= 254:
            where.append("(lower(t.guest_email) = :q OR lower(u.email) = :q)")
            params["q"] = q.lower()
        else:
            raise _bad_filter("q")
    sort = sort or "newest"
    if sort not in _ORDER:
        raise _bad_filter("sort")
    page = max(1, int(page))
    limit = max(1, min(ADMIN_PAGE_MAX, int(limit)))
    w = (" WHERE " + " AND ".join(where)) if where else ""
    with db_conn() as conn:
        total = int(conn.run("SELECT COUNT(*) FROM support_tickets t " + _REQUESTER_SQL + w, **params)[0][0])
        rows = conn.run(_ADMIN_SELECT + w + " ORDER BY " + _ORDER[sort] + " LIMIT :lim OFFSET :off",
                        lim=limit, off=(page - 1) * limit, **params)
    return {"items": [_admin_row(r) for r in rows], "total": total, "page": page, "limit": limit, "sort": sort}


def admin_count_new() -> int:
    with db_conn() as conn:
        return int(conn.run(f"SELECT COUNT(*) FROM support_tickets t WHERE {_STATUS_SQL} = 'new'")[0][0])


def admin_get(public_id: str) -> dict:
    """The ticket for the admin — requester · details · faq_id · legacy_category · messages (+ author_id)."""
    with db_conn() as conn:
        rows = conn.run(_ADMIN_SELECT + " WHERE t.public_id = :p", p=public_id)
        if not rows:
            raise LookupError("ticket")
        tid = int(rows[0][0])
        out = _admin_row(rows[0])
        out["messages"] = _messages(conn, tid, admin=True)
        return out


def _locked_ticket(conn, public_id: str) -> dict:
    rows = conn.run(_TICKET_SELECT + " WHERE t.public_id = :p FOR UPDATE OF t", p=public_id)
    if not rows:
        raise LookupError("ticket")
    return _ticket(rows[0])


def admin_reply(public_id: str, admin_sub: str, body: str, next_status) -> tuple:
    """Admin reply + next_status ∈ ADMIN_REPLY_STATUSES (required). → (old status, new status, notify) —
    notify = {ticket_id, public_id, message_id, user_id, guest_email} for the reply notice (7.2b), sent by
    the caller after the commit; never the reply text."""
    new = transition(None, "admin_reply", target=next_status)   # 422 before any read

    def fn(conn):
        t = _locked_ticket(conn, public_id)
        mid = _insert_message(conn, t["id"], "admin", admin_sub, body)
        _set_status(conn, t, new, message=True)
        return t["status"], new, {"ticket_id": t["id"], "public_id": t["public_id"], "message_id": mid,
                                  "user_id": t["user_id"], "guest_email": t["guest_email"]}
    return _tx(fn)


def admin_update(public_id: str, status: str = None, priority: str = None, category: str = None) -> tuple:
    """Status (any) · priority · category. → (old {field: value}, new {field: value}) of the fields sent.
    A category change keeps the first stored value in legacy_category (when it is still NULL)."""
    if status is None and priority is None and category is None:
        raise SupportError(422, "nothing_to_change", "support.error.invalid_value")
    if status is not None:
        transition(None, "admin_set", target=status)
    if priority is not None and priority not in PRIORITIES:
        raise SupportError(422, "invalid_priority", "support.error.invalid_value", "priority")
    if category is not None and category not in CATEGORIES:
        raise SupportError(422, "invalid_category", "support.error.category", "category")

    def fn(conn):
        t = _locked_ticket(conn, public_id)
        # a web guest ticket stays account; an inbound-email ticket (7.3) may take any category
        if category is not None and t["user_id"] is None and t["source"] != "email" and category != GUEST_CATEGORY:
            raise SupportError(422, "guest_category", "support.error.guest_category", "category")
        old, new = {}, {}
        for field, val in (("status", status), ("priority", priority), ("category", category)):
            if val is not None:
                old[field], new[field] = t[field], val
        sets, params = ["updated_at = NOW()"], {"t": t["id"]}
        if status is not None:
            sets.append("status = :s")
            params["s"] = status
        if priority is not None:
            sets.append("priority = :p")
            params["p"] = priority
        if category is not None:   # right-hand sides read the old row → the first stored value is kept
            sets.append("legacy_category = CASE WHEN category <> :c THEN COALESCE(legacy_category, category) "
                        "ELSE legacy_category END, category = :c")
            params["c"] = category
        closed = _closed_sql(t["status"], status) if status is not None and status != t["status"] else ""
        conn.run("UPDATE support_tickets SET " + ", ".join(sets) + closed + " WHERE id = :t", **params)
        return old, new
    return _tx(fn)


# ── inbound mail (task 7.3 — docs/rules/support.md → البريد الوارد) ──
INBOUND_DOMAIN = "tawasolna.com"
INBOUND_LOCALS = ("info", "support")   # a new email here = a new guest ticket
REPLY_LOCAL = "support"                # support+<token>@ = a message on the token's ticket
REPLY_TOKEN_KEEP = 5                   # Reply-To tokens kept per ticket (the newest) — older replies are ignored
_REPLY_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_ADDR_RE = re.compile(r"<([^<>\s]+)>\s*$")


def reply_address(token: str) -> str:
    return f"{REPLY_LOCAL}+{token}@{INBOUND_DOMAIN}"


def issue_reply_token(ticket_id: int, conn=None) -> str:
    """The ONLY writer of support_reply_tokens: a new random token for the ticket (sha256 hex stored),
    keeps the newest REPLY_TOKEN_KEEP. → the plain token (into the Reply-To address only)."""
    def fn(c):
        token = secrets.token_hex(16)
        c.run("INSERT INTO support_reply_tokens (ticket_id, token_hash) VALUES (:t, :h)",
              t=ticket_id, h=_token_hash(token))
        c.run("DELETE FROM support_reply_tokens WHERE ticket_id = :t AND id NOT IN (SELECT id FROM "
              "support_reply_tokens WHERE ticket_id = :t ORDER BY created_at DESC, id DESC LIMIT :k)",
              t=ticket_id, k=REPLY_TOKEN_KEEP)
        return token
    return fn(conn) if conn is not None else _tx(fn)


def ticket_id_of(public_id: str):
    with db_conn() as conn:
        rows = conn.run("SELECT id FROM support_tickets WHERE public_id = :p", p=public_id)
    return int(rows[0][0]) if rows else None


def bare_address(value) -> str:
    """'Name <a@b.c>' / 'a@b.c' → 'a@b.c' (lower) · anything else → ''."""
    if not isinstance(value, str):
        return ""
    v = value.strip()
    m = _ADDR_RE.search(v)
    addr = (m.group(1) if m else v).strip().lower()
    return addr if email_service.valid_address(addr) else ""


def inbound_target(recipients) -> tuple:
    """Recipient list → ("reply", token) for support+<token>@ · ("new", None) for info@ / support@ ·
    (None, None) otherwise. A reply address wins over a plain one in the same email."""
    new = False
    for r in recipients if isinstance(recipients, list) else []:
        addr = bare_address(r)
        local, _, domain = addr.partition("@")
        if domain != INBOUND_DOMAIN:
            continue
        base, plus, tag = local.partition("+")
        if base == REPLY_LOCAL and plus:
            if _REPLY_TOKEN_RE.match(tag):
                return "reply", tag
            continue
        if local in INBOUND_LOCALS:
            new = True
    return ("new", None) if new else (None, None)


def inbound_seen(svix_id: str, email_id: str) -> bool:
    with db_conn() as conn:
        return bool(conn.run("SELECT 1 FROM support_inbound_events WHERE svix_id = :s OR email_id = :e",
                             s=svix_id, e=email_id))


def _inbound_claim(conn, svix_id: str, email_id: str, outcome: str) -> int:
    """The event row (dedupe) — None when this svix_id / email_id is already handled."""
    rows = conn.run("INSERT INTO support_inbound_events (svix_id, email_id, outcome) VALUES (:s, :e, :o) "
                    "ON CONFLICT DO NOTHING RETURNING id", s=svix_id, e=email_id, o=outcome)
    return int(rows[0][0]) if rows else None


def _inbound_done(conn, eid: int, outcome: str, ticket_id=None) -> str:
    conn.run("UPDATE support_inbound_events SET outcome = :o, ticket_id = :t WHERE id = :i",
             o=outcome, t=ticket_id, i=eid)
    return outcome


def inbound_ignore(svix_id: str, email_id: str, reason: str) -> str:
    """Record an ignored email (so a retry is a no-op). → 'duplicate' when already recorded."""
    def fn(conn):
        return reason if _inbound_claim(conn, svix_id, email_id, reason) else "duplicate"
    return _tx(fn)


def inbound_new_ticket(svix_id: str, email_id: str, sender: str, subject: str, body: str) -> str:
    """New email → a guest ticket (guest_email = sender, category general, source email). Never linked
    to an account. → 'ticket' · 'duplicate'."""
    def fn(conn):
        eid = _inbound_claim(conn, svix_id, email_id, "processing")
        if eid is None:
            return "duplicate"
        tid, _ = _insert_ticket(conn, None, sender, INBOUND_CATEGORY, subject, {}, None, source="email")
        _insert_message(conn, tid, "guest", None, body)
        return _inbound_done(conn, eid, "ticket", tid)
    return _tx(fn)


def inbound_reply(svix_id: str, email_id: str, token: str, sender: str, body: str, open_max: int) -> str:
    """Email to support+<token>@ → a message on that ticket when sender = its owner (account email or
    guest_email); same rules as a web reply (_requester_reply: reopen within REOPEN_DAYS, open_max).
    → 'message' · 'duplicate' · 'ignored_token' · 'ignored_owner' · 'ignored_suspended' (account suspended) ·
    'ignored_<SupportError code>'."""
    def fn(conn):
        eid = _inbound_claim(conn, svix_id, email_id, "processing")
        if eid is None:
            return "duplicate"
        rows = conn.run("SELECT " + _TICKET_FIELDS + ", lower(u.email) FROM support_reply_tokens r "
                        "JOIN support_tickets t ON t.id = r.ticket_id LEFT JOIN users u ON u.id = t.user_id "
                        "WHERE r.token_hash = :h FOR UPDATE OF t", h=_token_hash(token))
        if not rows:
            return _inbound_done(conn, eid, "ignored_token")
        t = _ticket(rows[0][:len(_TICKET_COLS)])
        owner = rows[0][len(_TICKET_COLS)] if t["user_id"] else (t["guest_email"] or "").lower()
        if not owner or sender != owner:
            return _inbound_done(conn, eid, "ignored_owner", t["id"])
        # a suspended account gets 401 on the site — its email must not add a message either (blocks-suspension)
        if t["user_id"] and bs.is_suspended(t["user_id"], conn):
            return _inbound_done(conn, eid, "ignored_suspended", t["id"])
        try:
            if t["user_id"]:
                _requester_reply(conn, t, "user", t["user_id"], body, open_max)
            else:
                _requester_reply(conn, t, "guest", None, body)
        except SupportError as e:   # reopen_expired / too_many_open — nothing written, the email is dropped
            return _inbound_done(conn, eid, "ignored_" + e.code[:24], t["id"])
        return _inbound_done(conn, eid, "message", t["id"])
    return _tx(fn)
