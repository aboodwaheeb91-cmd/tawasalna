"""support.py — Support Tickets (task 7.1 · docs/rules/support.md · docs/SYSTEMS_INDEX.md §62 · ARCHITECTURE.md §81).

The ONE place support tickets are read and written (server.py only validates the request, checks the
limits and calls these). Not complete until 7.2 (reply by email to the guest) and 7.3.

  support_tickets   public_id (generate_public_id("H")) · user_id (NULL = guest) · guest_email · category ·
                    status · priority · subject · created_at · updated_at · last_message_at · closed_at
  support_messages  ticket_id · author_type user | guest | admin · author_id (user id / admin sub; guest NULL) ·
                    body · created_at
  support_guest_otp guest support code (auth.guest_otp_issue / guest_otp_verify — same OTP rules as KYC)

Rules (enforced here, inside one transaction each):
  - an account sees / replies to / closes its own tickets only — anything else = LookupError (→ 404)
  - open tickets per account (open + awaiting_user) ≤ open_max — create AND reopen (row lock on users)
  - the user's reply → status open · on a closed ticket within REOPEN_DAYS of closed_at it reopens it,
    after that → SupportError reopen_expired («افتح تذكرة جديدة»)
  - the admin's reply → awaiting_user · priority only from the admin (default normal)
  - a guest ticket is always category `account` (also a DB CHECK)
  - blocks / suspension never filter tickets (no bs.visible_sql here)
Pure DB — no FastAPI. Texts = twT keys (support.error.*) mapped by server.py.
"""
from auth import db_conn, generate_public_id

CATEGORIES = ("account", "profile", "jobs", "technical", "complaint", "other")
GUEST_CATEGORY = "account"
STATUSES = ("open", "awaiting_user", "closed")
PRIORITIES = ("normal", "high", "urgent")
DEFAULT_PRIORITY = "normal"
REOPEN_DAYS = 14          # a closed ticket the user answers within this many days of closed_at reopens
PUBLIC_ID_PREFIX = "H"    # ARCHITECTURE.md → Public ID System prefix table
ADMIN_PAGE_MAX = 50
USER_LIST_MAX = 50


class SupportError(Exception):
    """Refused by a ticket rule → server maps to api_error(status, code, twT(text_key))."""
    def __init__(self, status: int, code: str, text_key: str):
        super().__init__(code)
        self.status, self.code, self.text_key = status, code, text_key


def _in(values) -> str:
    return ", ".join("'" + v + "'" for v in values)   # fixed tuples above only — never caller input


# ── schema (same SQL as docs/migrations/7.1_support_tickets.sql) ──
SCHEMA_SQL = (
    f"""CREATE TABLE IF NOT EXISTS support_tickets (
        id              SERIAL PRIMARY KEY,
        public_id       TEXT NOT NULL UNIQUE,
        user_id         INTEGER NULL REFERENCES users(id) ON DELETE CASCADE,
        guest_email     TEXT NULL,
        category        TEXT NOT NULL CONSTRAINT support_tickets_category_chk CHECK (category IN ({_in(CATEGORIES)})),
        status          TEXT NOT NULL DEFAULT 'open' CONSTRAINT support_tickets_status_chk CHECK (status IN ({_in(STATUSES)})),
        priority        TEXT NOT NULL DEFAULT 'normal' CONSTRAINT support_tickets_priority_chk CHECK (priority IN ({_in(PRIORITIES)})),
        subject         TEXT NOT NULL CONSTRAINT support_tickets_subject_chk CHECK (length(btrim(subject)) > 0),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        closed_at       TIMESTAMPTZ NULL,
        CONSTRAINT support_tickets_owner_chk CHECK (user_id IS NOT NULL OR guest_email IS NOT NULL),
        CONSTRAINT support_tickets_guest_category_chk CHECK (user_id IS NOT NULL OR category = '{GUEST_CATEGORY}')
    )""",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets (user_id, last_message_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_inbox ON support_tickets (status, last_message_at DESC)",
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
)


def migrate_support():
    """Idempotent (task 7.1). Optional startup migration: a failure only stops support (its routes 500)."""
    with db_conn() as conn:
        for sql in SCHEMA_SQL:
            conn.run(sql)


# ── helpers ──
_TICKET_COLS = ("id", "public_id", "user_id", "guest_email", "category", "status", "priority", "subject",
                "created_at", "updated_at", "last_message_at", "closed_at")
_TICKET_SELECT = "SELECT " + ", ".join("t." + c for c in _TICKET_COLS) + " FROM support_tickets t"


def _ticket(row) -> dict:
    return dict(zip(_TICKET_COLS, row))


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


def _user_view(t: dict) -> dict:
    """What the account sees of its own ticket — no priority, no internal id."""
    return {k: t[k] for k in ("public_id", "category", "status", "subject", "created_at",
                              "last_message_at", "closed_at")}


def _lock_user_open(conn, user_id: int, open_max: int, exclude_id: int = None) -> None:
    """Row lock on the account (serialises its creates / reopens) → refuse past open_max."""
    conn.run("SELECT id FROM users WHERE id = :u FOR UPDATE", u=user_id)
    n = conn.run("SELECT COUNT(*) FROM support_tickets WHERE user_id = :u AND status <> 'closed' "
                 "AND id <> :x", u=user_id, x=exclude_id or 0)[0][0]
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


def _insert_ticket(conn, user_id, guest_email, category, subject) -> tuple:
    for _ in range(3):   # 36^10 ids — a clash is practically impossible, retried anyway
        rows = conn.run(
            "INSERT INTO support_tickets (public_id, user_id, guest_email, category, subject) "
            "VALUES (:p, :u, :g, :c, :s) ON CONFLICT (public_id) DO NOTHING RETURNING id, public_id",
            p=generate_public_id(PUBLIC_ID_PREFIX), u=user_id, g=guest_email, c=category, s=subject)
        if rows:
            return int(rows[0][0]), rows[0][1]
    raise RuntimeError("support public_id clash")


def _insert_message(conn, ticket_id: int, author_type: str, author_id, body: str) -> None:
    conn.run("INSERT INTO support_messages (ticket_id, author_type, author_id, body) VALUES (:t, :a, :i, :b)",
             t=ticket_id, a=author_type, i=None if author_id is None else str(author_id), b=body)


# ── account ──
def create_user_ticket(user_id: int, category: str, subject: str, body: str, open_max: int) -> dict:
    def fn(conn):
        _lock_user_open(conn, user_id, open_max)
        tid, pid = _insert_ticket(conn, user_id, None, category, subject)
        _insert_message(conn, tid, "user", user_id, body)
        return {"public_id": pid}
    return _tx(fn)


def list_user_tickets(user_id: int, limit: int = USER_LIST_MAX) -> list:
    with db_conn() as conn:
        rows = conn.run(_TICKET_SELECT + " WHERE t.user_id = :u ORDER BY t.last_message_at DESC, t.id DESC LIMIT :l",
                        u=user_id, l=max(1, min(USER_LIST_MAX, int(limit))))
    return [_user_view(_ticket(r)) for r in rows]


def get_user_ticket(public_id: str, user_id: int) -> dict:
    with db_conn() as conn:
        rows = conn.run(_TICKET_SELECT + " WHERE t.public_id = :p AND t.user_id = :u", p=public_id, u=user_id)
        if not rows:
            raise LookupError("ticket")
        t = _ticket(rows[0])
        out = _user_view(t)
        out["messages"] = _messages(conn, t["id"], admin=False)
        out["can_reopen"] = _reopen_allowed(conn, t)
        return out


def _reopen_allowed(conn, t: dict) -> bool:
    if t["status"] != "closed":
        return True
    if t["closed_at"] is None:
        return True
    rows = conn.run("SELECT closed_at > NOW() - :d * INTERVAL '1 day' FROM support_tickets WHERE id = :t",
                    t=t["id"], d=REOPEN_DAYS)
    return bool(rows and rows[0][0])


def _locked_user_ticket(conn, public_id: str, user_id: int) -> dict:
    rows = conn.run(_TICKET_SELECT + " WHERE t.public_id = :p AND t.user_id = :u FOR UPDATE",
                    p=public_id, u=user_id)
    if not rows:
        raise LookupError("ticket")
    return _ticket(rows[0])


def user_reply(public_id: str, user_id: int, body: str, open_max: int) -> dict:
    """Reply → status open. Closed: within REOPEN_DAYS → reopened (open_max applies), else refused."""
    def fn(conn):
        t = _locked_user_ticket(conn, public_id, user_id)
        reopened = t["status"] == "closed"
        if reopened:
            if not _reopen_allowed(conn, t):
                raise SupportError(409, "reopen_expired", "support.error.reopen_expired")
            _lock_user_open(conn, user_id, open_max, exclude_id=t["id"])
        _insert_message(conn, t["id"], "user", user_id, body)
        conn.run("UPDATE support_tickets SET status = 'open', closed_at = NULL, updated_at = NOW(), "
                 "last_message_at = NOW() WHERE id = :t", t=t["id"])
        return {"public_id": public_id, "status": "open", "reopened": reopened}
    return _tx(fn)


def user_close(public_id: str, user_id: int) -> dict:
    def fn(conn):
        t = _locked_user_ticket(conn, public_id, user_id)
        if t["status"] != "closed":
            conn.run("UPDATE support_tickets SET status = 'closed', closed_at = NOW(), updated_at = NOW() "
                     "WHERE id = :t", t=t["id"])
        return {"public_id": public_id, "status": "closed"}
    return _tx(fn)


# ── guest (login problems — category account only) ──
def create_guest_ticket(email: str, subject: str, body: str) -> dict:
    def fn(conn):
        tid, pid = _insert_ticket(conn, None, email, GUEST_CATEGORY, subject)
        _insert_message(conn, tid, "guest", None, body)
        return {"public_id": pid}
    return _tx(fn)


# ── admin (support.manage) ──
_REQUESTER_SQL = ("LEFT JOIN users u ON u.id = t.user_id")
_REQUESTER_COLS = ", u.tw_id, u.full_name, u.email, u.user_type"


def _admin_row(row) -> dict:
    t = _ticket(row[:len(_TICKET_COLS)])
    tw_id, name, email, utype = row[len(_TICKET_COLS):]
    t["requester"] = ({"kind": "user", "tw_id": tw_id, "name": name or "", "email": email or "", "user_type": utype}
                      if t["user_id"] else {"kind": "guest", "email": t["guest_email"] or ""})
    t.pop("id")
    t.pop("user_id")
    return t


def admin_list(status: str = "", category: str = "", priority: str = "", page: int = 1,
               limit: int = 20) -> dict:
    where, params = [], {}
    for col, val, allowed in (("status", status, STATUSES), ("category", category, CATEGORIES),
                              ("priority", priority, PRIORITIES)):
        if val:
            if val not in allowed:
                raise SupportError(422, "invalid_filter", "support.error.invalid_value")
            where.append(f"t.{col} = :{col}")
            params[col] = val
    page = max(1, int(page))
    limit = max(1, min(ADMIN_PAGE_MAX, int(limit)))
    w = (" WHERE " + " AND ".join(where)) if where else ""
    with db_conn() as conn:
        total = int(conn.run("SELECT COUNT(*) FROM support_tickets t" + w, **params)[0][0])
        rows = conn.run(_TICKET_SELECT.replace(" FROM", _REQUESTER_COLS + " FROM", 1) + " " + _REQUESTER_SQL + w
                        + " ORDER BY t.last_message_at DESC, t.id DESC LIMIT :lim OFFSET :off",
                        lim=limit, off=(page - 1) * limit, **params)
    return {"items": [_admin_row(r) for r in rows], "total": total, "page": page, "limit": limit}


def admin_get(public_id: str) -> dict:
    with db_conn() as conn:
        rows = conn.run(_TICKET_SELECT.replace(" FROM", _REQUESTER_COLS + " FROM", 1) + " " + _REQUESTER_SQL
                        + " WHERE t.public_id = :p", p=public_id)
        if not rows:
            raise LookupError("ticket")
        tid = int(rows[0][0])
        out = _admin_row(rows[0])
        out["messages"] = _messages(conn, tid, admin=True)
        return out


def _locked_ticket(conn, public_id: str) -> dict:
    rows = conn.run(_TICKET_SELECT + " WHERE t.public_id = :p FOR UPDATE", p=public_id)
    if not rows:
        raise LookupError("ticket")
    return _ticket(rows[0])


def admin_reply(public_id: str, admin_sub: str, body: str) -> tuple:
    """Admin reply → awaiting_user (a closed ticket too). → (old status, new status)."""
    def fn(conn):
        t = _locked_ticket(conn, public_id)
        _insert_message(conn, t["id"], "admin", admin_sub, body)
        conn.run("UPDATE support_tickets SET status = 'awaiting_user', closed_at = NULL, updated_at = NOW(), "
                 "last_message_at = NOW() WHERE id = :t", t=t["id"])
        return t["status"], "awaiting_user"
    return _tx(fn)


def admin_update(public_id: str, status: str = None, priority: str = None) -> tuple:
    """Status and / or priority. → (old {field: value}, new {field: value}) of the fields sent."""
    if status is None and priority is None:
        raise SupportError(422, "nothing_to_change", "support.error.invalid_value")
    if status is not None and status not in STATUSES:
        raise SupportError(422, "invalid_status", "support.error.invalid_value")
    if priority is not None and priority not in PRIORITIES:
        raise SupportError(422, "invalid_priority", "support.error.invalid_value")

    def fn(conn):
        t = _locked_ticket(conn, public_id)
        old, new = {}, {}
        if status is not None:
            old["status"], new["status"] = t["status"], status
        if priority is not None:
            old["priority"], new["priority"] = t["priority"], priority
        closed_sql = ""
        if status is not None and status != t["status"]:
            closed_sql = ", closed_at = NOW()" if status == "closed" else ", closed_at = NULL"
        conn.run("UPDATE support_tickets SET status = :s, priority = :p, updated_at = NOW()" + closed_sql
                 + " WHERE id = :t", s=new.get("status", t["status"]), p=new.get("priority", t["priority"]), t=t["id"])
        return old, new
    return _tx(fn)
