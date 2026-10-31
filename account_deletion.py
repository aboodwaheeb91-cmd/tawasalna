"""account_deletion.py — Soft account delete + restore (task 8.5a · F27 · docs/rules/account-deletion.md ·
docs/SYSTEMS_INDEX.md §25i).

Nothing is removed: a deleted account keeps its row and every row that points at it (messages, applications,
pipeline, appointments, posts, comments, jobs). Hard delete does not exist on any path (task 8.5c).

  users.deleted_at / deleted_by / deleted_kind ('admin' | 'self') / deleted_reason (admin-only text)
  soft_delete()  → the ONE writer of deleted_* (set) — + session_version + 1 (every token dies) + pending
                   password-reset links deleted, in one statement-level transaction.
  restore()      → the ONE writer of deleted_* (clear) — + session_version + 1 (old tokens stay dead: a new login).
  apply_effects()→ what a deletion does to other people (company: open jobs closed + one in-app notice per
                   affected applicant · any account: upcoming interviews cancelled through auth.cancel_appointment).
                   Run by the call that changed the state only → deleting twice = one notice. Restore never undoes it.

Visibility: blocks_suspension.active_sql / visible_sql hide a deleted account exactly like a suspended one (the ONE
rule). Records shared with another person (conversations · applications · pipeline · appointments) stay and show
the account as «حساب محذوف» — scrub() empties the identity fields in the server reply itself.

DB functions import auth lazily (auth.py imports this module for the label).
"""

KINDS = ("admin", "self")
DELETED_NAME_KEY = "account.deleted"
# Identity fields a reply never carries for a deleted account (name → the label, the rest → None)
PARTY_CLEAR = ("tw_id", "avatar_url", "email", "phone", "headline", "title", "city", "country", "bio")

_strings_provider = None


def set_strings_provider(fn) -> None:
    """server.py passes the Strings System (admin overrides included) — the same pattern as email_service."""
    global _strings_provider
    _strings_provider = fn


def _text(key: str) -> str:
    if _strings_provider is not None:
        try:
            v = (_strings_provider() or {}).get(key)
            if v:
                return v
        except Exception as e:
            print(f"[account-deletion] strings provider failed: {type(e).__name__}")
    import tw_strings
    return tw_strings.merged({}).get(key) or key


def deleted_label() -> str:
    """«حساب محذوف» — twT account.deleted."""
    return _text(DELETED_NAME_KEY)


def deleted_sql(col: str) -> str:
    """Account `col` is soft-deleted (SQL boolean) — read next to a shared record to scrub its identity."""
    return f"EXISTS (SELECT 1 FROM users ad_u WHERE ad_u.id = {col} AND ad_u.deleted_at IS NOT NULL)"


def scrub(d: dict, deleted, name_keys=("full_name",), clear_keys=PARTY_CLEAR, flag: str = "is_deleted") -> dict:
    """In place: a deleted party's name → «حساب محذوف», identity keys → None, d[flag] = True/False."""
    deleted = bool(deleted)
    if deleted:
        label = deleted_label()
        for k in name_keys:
            if k in d:
                d[k] = label
        for k in clear_keys:
            if k in d:
                d[k] = None
    d[flag] = deleted
    return d


class DeletionError(Exception):
    """code: invalid_kind (422)."""
    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code = code
        self.status = status


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _state(row) -> dict:
    """get_session_state shape from (password_changed_at epoch, session_version, suspended, deleted)."""
    return {"changed": int(row[0]) if row[0] is not None else None, "sv": int(row[1] or 0),
            "suspended": bool(row[2]), "deleted": bool(row[3])}


_STATE_COLS = ("EXTRACT(EPOCH FROM password_changed_at), session_version, suspended_at IS NOT NULL, "
               "deleted_at IS NOT NULL")


def soft_delete(user_id: int, by: str, kind: str, reason=None):
    """The ONE writer (set). → None (no such user) |
    {changed, deleted_at, deleted_kind, user_type, state}. changed False = already deleted (nothing written)."""
    if kind not in KINDS:
        raise DeletionError("invalid_kind", 422)
    from auth import db_conn
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run(
                "UPDATE users SET deleted_at = NOW(), deleted_by = :by, deleted_kind = :k, deleted_reason = :r, "
                "session_version = session_version + 1 WHERE id = :uid AND deleted_at IS NULL "
                "RETURNING deleted_at, deleted_kind, user_type, " + _STATE_COLS,
                by=str(by or "-"), k=kind, r=((reason or None) if kind == "admin" else None), uid=int(user_id))
            changed = bool(rows)
            if changed:
                conn.run("DELETE FROM password_reset_tokens WHERE user_id = :uid", uid=int(user_id))
            else:
                rows = conn.run("SELECT deleted_at, deleted_kind, user_type, " + _STATE_COLS +
                                " FROM users WHERE id = :uid", uid=int(user_id))
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    if not rows:
        return None
    r = rows[0]
    return {"changed": changed, "deleted": r[0] is not None, "deleted_at": _iso(r[0]), "deleted_kind": r[1],
            "user_type": r[2], "state": _state(r[3:])}


def restore(user_id: int, by: str, reason: str):
    """The ONE writer (clear). → None (no such user) | {changed, state}. Old tokens stay dead (session_version + 1).
    Jobs stay closed and cancelled interviews stay cancelled. The reason goes to the admin audit log (server)."""
    from auth import db_conn
    with db_conn() as conn:
        rows = conn.run(
            "UPDATE users SET deleted_at = NULL, deleted_by = NULL, deleted_kind = NULL, deleted_reason = NULL, "
            "session_version = session_version + 1 WHERE id = :uid AND deleted_at IS NOT NULL "
            "RETURNING " + _STATE_COLS, uid=int(user_id))
        changed = bool(rows)
        if not changed:
            rows = conn.run("SELECT " + _STATE_COLS + " FROM users WHERE id = :uid", uid=int(user_id))
    if not rows:
        return None
    return {"changed": changed, "state": _state(rows[0])}


def get_deletion(user_id: int):
    """Admin view → None (no such user) | {deleted, deleted_at, deleted_by, deleted_kind, deleted_reason}."""
    from auth import db_conn
    with db_conn() as conn:
        rows = conn.run("SELECT deleted_at, deleted_by, deleted_kind, deleted_reason FROM users WHERE id = :uid",
                        uid=int(user_id))
    if not rows:
        return None
    at, by, kind, reason = rows[0]
    return {"deleted": at is not None, "deleted_at": _iso(at), "deleted_by": by, "deleted_kind": kind,
            "deleted_reason": reason}


def is_deleted(user_id: int, conn=None) -> bool:
    if conn is None:
        from auth import db_conn
        with db_conn() as c:
            return is_deleted(user_id, c)
    rows = conn.run("SELECT deleted_at IS NOT NULL FROM users WHERE id = :uid", uid=int(user_id))
    return bool(rows and rows[0][0])


# ── Effects on other people (one function — the admin delete now, the user's own delete in 8.5d) ──

def apply_effects(user_id: int) -> dict:
    """While the account is still deleted: company → its open / paused jobs closed (auth.set_job_status — the one
    status change) + ONE in-app notice per applicant still in review (no reason, event_key per deletion) · any
    account → upcoming interviews cancelled through auth.cancel_appointment (the other side gets its notice).
    Nothing is sent to the deleted account itself (create_notification skips a deleted recipient). Each item is
    non-fatal (logged). → counts."""
    import auth
    uid = int(user_id)
    out = {"jobs_closed": 0, "notified": 0, "appointments_cancelled": 0}
    with auth.db_conn() as conn:
        row = conn.run("SELECT user_type, EXTRACT(EPOCH FROM deleted_at)::bigint FROM users "
                       "WHERE id = :uid AND deleted_at IS NOT NULL", uid=uid)
        if not row:
            return out
        utype, episode = row[0][0], int(row[0][1])
        jobs, applicants = [], []
        if utype == "co":
            jobs = [int(r[0]) for r in conn.run(
                "SELECT j.id FROM jobs j WHERE j.company_id = :uid AND j.archived_at IS NULL AND "
                + auth.job_eff_status_sql("j") + " IN ('active', 'paused') ORDER BY j.id", uid=uid)]
            applicants = conn.run(
                "SELECT ja.user_id, ja.status FROM job_applications ja JOIN jobs j ON j.id = ja.job_id "
                "WHERE j.company_id = :uid AND ja.user_id IS NOT NULL", uid=uid)
        appts = [int(r[0]) for r in conn.run(
            "SELECT a.id FROM appointments a JOIN appointment_participants ap "
            "ON ap.appointment_id = a.id AND ap.user_id = :uid "
            "WHERE a.status IN ('draft', 'pending_response', 'confirmed', 'reschedule_requested') "
            "AND (a.scheduled_at IS NULL OR a.scheduled_at > NOW()) ORDER BY a.id", uid=uid)]

    for jid in jobs:
        try:
            auth.set_job_status(jid, None, "closed")
            out["jobs_closed"] += 1
        except (ValueError, LookupError) as e:   # closed meanwhile — nothing to do
            print(f"[account-deletion] close job={jid} skipped: {type(e).__name__}")
        except Exception as e:
            print(f"[account-deletion] close job={jid} failed: {type(e).__name__}: {e}")

    in_review = sorted({int(r[0]) for r in applicants if auth.applicant_visible_status(r[1]) == "in_review"})
    for aid in in_review:
        try:
            if auth.create_notification(
                    user_id=aid, type_="application_closed", title=_text("notif.account_closed.title"),
                    body=_text("notif.account_closed.body"), link="", entity_type="application",
                    event_key=f"account_closed:{uid}:{episode}"):
                out["notified"] += 1
        except Exception as e:
            print(f"[account-deletion] notify user={aid} failed: {type(e).__name__}: {e}")

    for appt_id in appts:
        try:
            auth.cancel_appointment(appt_id, uid)
            out["appointments_cancelled"] += 1
        except (ValueError, PermissionError) as e:   # cancelled / passed meanwhile
            print(f"[account-deletion] cancel appointment={appt_id} skipped: {type(e).__name__}")
        except Exception as e:
            print(f"[account-deletion] cancel appointment={appt_id} failed: {type(e).__name__}: {e}")
    return out


# ── Migration (critical — the session check and every visibility query read these columns) ──
# The same statements: docs/migrations/8.5a_soft_delete.sql (production, by hand, with a read-only check first).

APPLY_SQL = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_by TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_kind TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_reason TEXT",
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_deleted_kind_chk' "
    "AND conrelid = 'public.users'::regclass) THEN ALTER TABLE users ADD CONSTRAINT users_deleted_kind_chk "
    "CHECK (deleted_kind IS NULL OR deleted_kind IN ('admin', 'self')); END IF; END $$",
    "CREATE INDEX IF NOT EXISTS idx_users_deleted ON users(id) WHERE deleted_at IS NOT NULL",
)


def migrate_account_deletion():
    """Idempotent, critical. One transaction."""
    from auth import db_conn
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            for stmt in APPLY_SQL:
                conn.run(stmt)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
