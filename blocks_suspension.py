"""blocks_suspension.py — Account Suspension (admin) + User Blocks (task 5.4 · docs/SYSTEMS_INDEX.md §25f ·
docs/rules/blocks-suspension.md).

Suspension — admin only, reversible, nothing deleted:
  users.suspended_at / suspended_reason / suspended_by  (suspended_reason + suspended_by are admin-only data)
  set_suspension()  → the ONE writer (PUT /admin/user/{id}/suspension). The session check reads the flag through
                      auth.get_session_state → server._jwt_decode: every request of a suspended account = 401
                      (the same path as a deleted account); login refused (401 account_suspended).
  A suspended account's content is hidden from everyone by the queries below (profile, posts, comments, jobs) —
  rows stay in place and come back when the suspension is lifted.

Blocks — a user blocks a user, both directions, no notification:
  blocks (blocker_id, blocked_id, created_at) · PK (blocker_id, blocked_id) · CHECK no self block.
  block() / unblock() / list_blocked() — every read / write is scoped to blocker_id = the JWT user (the app is
  the only DB client; RLS is on and anon / authenticated have no grant — rls_lockdown).
  block() deletes the follow rows of both directions in the same transaction. Job applications are never touched.

The ONE visibility rule — SQL fragments, used by every list / read that shows another account's content:
  visible_sql(col, viewer)  → account `col` is not suspended / deleted AND no block row between it and `viewer`
  active_sql(col)           → account `col` is not suspended / deleted (jobs: a block never hides a job)
  (task 8.5a — a soft-deleted account (account_deletion.py) hides exactly like a suspended one; keep_deleted=True
   only on shared records that stay: conversations + unread count)
  is_hidden(viewer, target) → the same rule as one bool (profile / post / follow / message checks)
A hidden account answers exactly like a missing one (404 «غير موجود») — never a «blocked» message.

Pure SQL builders at import time; DB functions import auth lazily (auth.py imports this module).
"""

# ── Visibility rule ─────────────────────────────────────────────────────────

def active_sql(col: str, keep_deleted: bool = False) -> str:
    """Account `col` is not suspended and not deleted (task 8.5a — a deleted account hides like a suspended one).
    keep_deleted=True — ONLY for records shared with another person that stay after a deletion (conversations ·
    unread count): a deleted account stays listed there (scrubbed to «حساب محذوف» by account_deletion.scrub),
    a suspended one that is not deleted is still hidden."""
    if keep_deleted:
        return (f"NOT EXISTS (SELECT 1 FROM users bs_u WHERE bs_u.id = {col} "
                "AND bs_u.suspended_at IS NOT NULL AND bs_u.deleted_at IS NULL)")
    return (f"NOT EXISTS (SELECT 1 FROM users bs_u WHERE bs_u.id = {col} "
            "AND (bs_u.suspended_at IS NOT NULL OR bs_u.deleted_at IS NOT NULL))")


def visible_sql(col: str, viewer: str = ":bs_viewer", keep_deleted: bool = False) -> str:
    """Account `col` is visible to `viewer` (SQL expression / param; 0 = guest): not suspended / deleted + no block
    either way. keep_deleted — see active_sql (shared records only)."""
    return (active_sql(col, keep_deleted) + " AND NOT EXISTS (SELECT 1 FROM blocks bs_b WHERE "
            f"(bs_b.blocker_id = {viewer} AND bs_b.blocked_id = {col}) OR "
            f"(bs_b.blocker_id = {col} AND bs_b.blocked_id = {viewer}))")


def _viewer(viewer_id) -> int:
    try:
        return int(viewer_id or 0)
    except (TypeError, ValueError):
        return 0


def is_hidden(viewer_id, target_id, conn=None) -> bool:
    """True when target is suspended or a block exists between viewer and target (either direction).
    The viewer never hides from itself."""
    vid, tid = _viewer(viewer_id), int(target_id)
    if vid and vid == tid:
        return False
    if conn is None:
        from auth import db_conn
        with db_conn() as c:
            return is_hidden(vid, tid, c)
    rows = conn.run("SELECT NOT (" + visible_sql(":tid", ":bs_viewer") + ")", tid=tid, bs_viewer=vid)
    return bool(rows and rows[0][0])


def is_suspended(user_id: int, conn=None) -> bool:
    """Suspended OR deleted (task 8.5a) — the account is out: no page, no inbound support mail."""
    if conn is None:
        from auth import db_conn
        with db_conn() as c:
            return is_suspended(user_id, c)
    rows = conn.run("SELECT suspended_at IS NOT NULL OR deleted_at IS NOT NULL FROM users WHERE id = :uid",
                    uid=int(user_id))
    return bool(rows and rows[0][0])


# ── Blocks ──────────────────────────────────────────────────────────────────

class BlockError(Exception):
    """code: not_found (404) · self_block (422)."""
    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code = code
        self.status = status


def block(blocker_id: int, blocked_id: int) -> dict:
    """Idempotent. Insert the block + delete follows both directions (one transaction). No notification."""
    a, b = int(blocker_id), int(blocked_id)
    if a == b:
        raise BlockError("self_block", 422)
    from auth import db_conn
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            if not conn.run("SELECT 1 FROM users WHERE id = :b", b=b):
                raise BlockError("not_found", 404)
            conn.run("INSERT INTO blocks (blocker_id, blocked_id) VALUES (:a, :b) "
                     "ON CONFLICT (blocker_id, blocked_id) DO NOTHING", a=a, b=b)
            conn.run("DELETE FROM profile_follows WHERE (follower_id = :a AND followed_id = :b) "
                     "OR (follower_id = :b AND followed_id = :a)", a=a, b=b)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return {"blocked": True}


def unblock(blocker_id: int, blocked_id: int) -> dict:
    """Idempotent — removes only the caller's own row (the other side's block, if any, stays)."""
    from auth import db_conn
    with db_conn() as conn:
        conn.run("DELETE FROM blocks WHERE blocker_id = :a AND blocked_id = :b",
                 a=int(blocker_id), b=int(blocked_id))
    return {"blocked": False}


def list_blocked(blocker_id: int, limit: int, offset: int) -> dict:
    """The caller's own blocks, newest first → {items, total}. Shown in /settings («المحظورون»)."""
    from auth import db_conn
    with db_conn() as conn:
        total = int(conn.run("SELECT COUNT(*) FROM blocks WHERE blocker_id = :a", a=int(blocker_id))[0][0] or 0)
        rows = conn.run(
            "SELECT u.id, u.tw_id, u.full_name, u.user_type, p.avatar_url, b.created_at "
            "FROM blocks b JOIN users u ON u.id = b.blocked_id LEFT JOIN profiles p ON p.user_id = u.id "
            "WHERE b.blocker_id = :a ORDER BY b.created_at DESC, u.id DESC LIMIT :lim OFFSET :off",
            a=int(blocker_id), lim=int(limit), off=int(offset))
    items = [{"id": r[0], "tw_id": r[1], "full_name": r[2] or "", "user_type": r[3], "avatar_url": r[4] or "",
              "blocked_at": r[5].isoformat() if hasattr(r[5], "isoformat") else r[5]} for r in rows]
    return {"items": items, "total": total}


# ── Suspension ──────────────────────────────────────────────────────────────

def set_suspension(user_id: int, suspended: bool, reason, by: str):
    """The ONE writer. → None (no such user) | {suspended, suspended_at, suspended_reason, suspended_by}.
    Re-suspending keeps the first suspended_at (the reason / by are updated)."""
    from auth import db_conn
    with db_conn() as conn:
        if suspended:
            rows = conn.run(
                "UPDATE users SET suspended_at = COALESCE(suspended_at, NOW()), suspended_reason = :r, "
                "suspended_by = :by WHERE id = :uid RETURNING suspended_at, suspended_reason, suspended_by",
                r=(reason or None), by=by, uid=int(user_id))
        else:
            rows = conn.run(
                "UPDATE users SET suspended_at = NULL, suspended_reason = NULL, suspended_by = NULL "
                "WHERE id = :uid RETURNING suspended_at, suspended_reason, suspended_by", uid=int(user_id))
    if not rows:
        return None
    at = rows[0][0]
    return {"suspended": at is not None, "suspended_at": at.isoformat() if hasattr(at, "isoformat") else at,
            "suspended_reason": rows[0][1], "suspended_by": rows[0][2]}


def get_suspension(user_id: int):
    """Admin view of the state → None (no such user) | same dict as set_suspension."""
    from auth import db_conn
    with db_conn() as conn:
        rows = conn.run("SELECT suspended_at, suspended_reason, suspended_by FROM users WHERE id = :uid",
                        uid=int(user_id))
    if not rows:
        return None
    at = rows[0][0]
    return {"suspended": at is not None, "suspended_at": at.isoformat() if hasattr(at, "isoformat") else at,
            "suspended_reason": rows[0][1], "suspended_by": rows[0][2]}


# ── Migration (critical — the session check and every visibility query read these) ──
# The same statements are in the PR as SQL for the Supabase SQL Editor (CHECK_SQL = read-only, APPLY_SQL =
# idempotent). RLS on blocks is enabled here and again by rls_lockdown; no grant to anon / authenticated.

CHECK_SQL = """
SELECT column_name, data_type FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'users'
   AND column_name IN ('suspended_at', 'suspended_reason', 'suspended_by');
SELECT to_regclass('public.blocks') AS blocks_table,
       (SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass('public.blocks')) AS blocks_rls;
"""

APPLY_SQL = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_reason TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_by TEXT",
    "CREATE TABLE IF NOT EXISTS blocks ("
    " blocker_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
    " blocked_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
    " PRIMARY KEY (blocker_id, blocked_id),"
    " CONSTRAINT blocks_no_self CHECK (blocker_id <> blocked_id))",
    "CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON blocks(blocked_id)",
    "ALTER TABLE blocks ENABLE ROW LEVEL SECURITY",
)


def migrate_blocks_suspension():
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
