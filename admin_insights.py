"""admin_insights.py — Admin Audit Log + Admin Stats (task 5.3a2 · docs/SYSTEMS_INDEX.md §25b / §25c ·
docs/rules/admin-shell.md).

Audit log (§25b)
  admin_audit_log (created_at, actor, action, target, result, status, ip) — migrate_admin_audit_log()
  is a CRITICAL startup migration. audit_record() is called from ONE place only: the
  admin_audit_middleware in server.py (every admin write under /admin/ + the admin login, success
  and failure). It stores names and ids only — never a body, password, token or message text.
    actor   "owner" today (the admin JWT `sub`) — ready for staff accounts (plan 5.3 roles)
    action  the FastAPI route name (e.g. delete_user, admin_login)
    target  path parameters only ("user_id=5")
    result  ok (< 400) · denied (401 / 403 / 429) · failed (anything else)
  audit_list() = GET /admin/audit (check_admin) — page + action filter.

Stats (§25c) — read-only, check_admin, one SQL query per number:
  stats_summary()     → the dashboard cards (+ change vs the previous period where the data allows)
  stats_timeseries()  → daily counts for one metric of TIMESERIES_METRICS (allowlist — table / column
                        names never come from the request)
  activity()          → latest registrations / jobs / KYC submissions / reports
"""
from auth import db_conn

AUDIT_RESULTS = ("ok", "denied", "failed")
AUDIT_PAGE_MAX = 100
_AUDIT_TEXT_MAX = 120

# metric → (table, timestamp column). The ONLY tables / columns the time series can read.
TIMESERIES_METRICS = {
    "users":        ("users", "created_at"),
    "jobs":         ("jobs", "created_at"),
    "applications": ("job_applications", "applied_at"),
}
TIMESERIES_DAYS_MAX = 90
ACTIVITY_LIMIT = 15


def migrate_admin_audit_log():
    """Idempotent — admin_audit_log (task 5.3a2). Critical: the admin write path records into it."""
    with db_conn() as conn:
        conn.run("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id         BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                actor      TEXT NOT NULL,
                action     TEXT NOT NULL,
                target     TEXT,
                result     TEXT NOT NULL CHECK (result IN ('ok', 'denied', 'failed')),
                status     INTEGER,
                ip         TEXT
            )""")
        conn.run("CREATE INDEX IF NOT EXISTS admin_audit_log_created_idx ON admin_audit_log (created_at DESC)")
        conn.run("CREATE INDEX IF NOT EXISTS admin_audit_log_action_idx ON admin_audit_log (action, created_at DESC)")


def audit_result(status: int) -> str:
    if status < 400:
        return "ok"
    if status in (401, 403, 429):
        return "denied"
    return "failed"


def _clip(v):
    if v is None:
        return None
    s = "".join(ch for ch in str(v) if ch.isprintable())
    return s[:_AUDIT_TEXT_MAX] or None


def audit_record(actor: str, action: str, target, status: int, ip: str) -> bool:
    """Insert one row. Never raises (the admin request already ran) — a failure is logged."""
    try:
        with db_conn() as conn:
            conn.run(
                "INSERT INTO admin_audit_log (actor, action, target, result, status, ip) "
                "VALUES (:actor, :action, :target, :result, :status, :ip)",
                actor=_clip(actor) or "-", action=_clip(action) or "-", target=_clip(target),
                result=audit_result(int(status)), status=int(status), ip=_clip(ip))
        return True
    except Exception as e:
        print(f"[admin-audit] record failed ({action}): {type(e).__name__}: {e}")
        return False


def audit_list(page: int = 1, limit: int = 20, action: str = "") -> dict:
    page = max(1, int(page))
    limit = max(1, min(AUDIT_PAGE_MAX, int(limit)))
    where, params = "", {}
    if action:
        where, params["action"] = " WHERE action = :action", action
    with db_conn() as conn:
        total = conn.run("SELECT COUNT(*) FROM admin_audit_log" + where, **params)[0][0]
        rows = conn.run(
            "SELECT id, created_at, actor, action, target, result, status, ip FROM admin_audit_log" + where +
            " ORDER BY created_at DESC, id DESC LIMIT :lim OFFSET :off",
            lim=limit, off=(page - 1) * limit, **params)
        actions = [r[0] for r in conn.run("SELECT DISTINCT action FROM admin_audit_log ORDER BY action")]
    cols = ("id", "created_at", "actor", "action", "target", "result", "status", "ip")
    items = []
    for r in rows:
        it = dict(zip(cols, r))
        it["created_at"] = it["created_at"].isoformat() if it["created_at"] else None
        items.append(it)
    return {"items": items, "total": int(total), "page": page, "limit": limit, "actions": actions}


# ── stats ──
def _pct(cur: int, prev: int):
    """Change in percent vs the previous period — None when there is nothing to compare."""
    if not prev:
        return None
    return round((cur - prev) * 100.0 / prev, 1)


def _table_exists(conn, name: str) -> bool:
    return conn.run("SELECT to_regclass(:n) IS NOT NULL", n="public." + name)[0][0]


def stats_summary() -> dict:
    """Dashboard cards. change = new in the last 30 days vs the 30 before (or today vs yesterday);
    None where no timestamp allows it (verified companies · open reports · pending KYC)."""
    out = {}
    with db_conn() as conn:
        def one(sql):
            return int(conn.run(sql)[0][0] or 0)

        def window(table, col, days):
            cur, prev = conn.run(
                f"SELECT COUNT(*) FILTER (WHERE {col} >= CURRENT_DATE - CAST(:d AS INTEGER) + 1), "
                f"COUNT(*) FILTER (WHERE {col} >= CURRENT_DATE - 2 * CAST(:d AS INTEGER) + 1 "
                f"AND {col} < CURRENT_DATE - CAST(:d AS INTEGER) + 1) FROM {table}", d=days)[0]
            return int(cur or 0), int(prev or 0)

        def card(total, cur_prev=None, period=None):
            c = {"value": total, "change": None, "period": None}
            if cur_prev:
                c["change"], c["period"] = _pct(*cur_prev), period
            return c

        out["users"] = card(one("SELECT COUNT(*) FROM users"), window("users", "created_at", 30), "month")
        out["verified_companies"] = card(one(
            "SELECT COUNT(*) FROM users u WHERE u.user_type = 'co' AND (COALESCE(u.is_verified, FALSE) "
            "OR EXISTS (SELECT 1 FROM profiles p WHERE p.user_id = u.id AND p.is_verified))"))
        out["active_jobs"] = card(one("SELECT COUNT(*) FROM jobs WHERE status = 'active'"),
                                  window("jobs", "created_at", 30), "month")
        out["applications"] = card(one("SELECT COUNT(*) FROM job_applications"),
                                   window("job_applications", "applied_at", 30), "month")
        out["open_reports"] = card(one("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
                                   if _table_exists(conn, "reports") else 0)
        out["pending_kyc"] = card(one("SELECT COUNT(*) FROM kyc_submissions WHERE step = 'review'"))
        msgs = window("messages", "created_at", 1)
        out["messages_today"] = card(msgs[0], msgs, "day")
        sent = conn.run(
            "SELECT COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE), "
            "COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - 1 AND created_at < CURRENT_DATE) "
            "FROM email_send_log WHERE status = 'sent'")[0]
        out["emails_today"] = card(int(sent[0] or 0), (int(sent[0] or 0), int(sent[1] or 0)), "day")
    return out


def stats_timeseries(metric: str, days: int) -> dict:
    """Daily counts for the last `days` days (today included). metric MUST be a TIMESERIES_METRICS key."""
    table, col = TIMESERIES_METRICS[metric]   # KeyError = caller skipped the allowlist check
    days = int(days)
    with db_conn() as conn:
        rows = conn.run(
            f"SELECT d::date, COALESCE(c.n, 0) FROM generate_series("
            f"CURRENT_DATE - CAST(:d AS INTEGER) + 1, CURRENT_DATE, INTERVAL '1 day') AS d "
            f"LEFT JOIN (SELECT {col}::date AS day, COUNT(*) AS n FROM {table} "
            f"WHERE {col} >= CURRENT_DATE - CAST(:d AS INTEGER) + 1 GROUP BY 1) c ON c.day = d::date "
            f"ORDER BY 1", d=days)
        total = int(conn.run(f"SELECT COUNT(*) FROM {table}")[0][0] or 0)
    points = [{"date": r[0].isoformat(), "count": int(r[1])} for r in rows]
    return {"metric": metric, "days": days, "points": points,
            "in_range": sum(p["count"] for p in points), "total": total}


def activity(limit: int = ACTIVITY_LIMIT) -> list:
    """Latest events from the existing tables — names / titles only (no emails, no report text)."""
    parts = [
        "(SELECT 'register' AS kind, u.created_at::timestamptz AS at, u.full_name AS title, "
        "u.user_type AS sub, u.id AS ref FROM users u ORDER BY u.created_at DESC NULLS LAST LIMIT :lim)",
        "(SELECT 'job' AS kind, j.created_at::timestamptz, j.title, c.full_name, j.id FROM jobs j "
        "LEFT JOIN users c ON c.id = j.company_id ORDER BY j.created_at DESC NULLS LAST LIMIT :lim)",
        "(SELECT 'kyc' AS kind, k.submitted_at::timestamptz, u.full_name, u.user_type, k.user_id "
        "FROM kyc_submissions k JOIN users u ON u.id = k.user_id WHERE k.step = 'review' "
        "ORDER BY k.submitted_at DESC NULLS LAST LIMIT :lim)",
    ]
    with db_conn() as conn:
        if _table_exists(conn, "reports"):
            parts.append(
                "(SELECT 'report' AS kind, r.created_at::timestamptz, u.full_name, r.report_type, r.id "
                "FROM reports r LEFT JOIN users u ON u.id = r.reported_id "
                "ORDER BY r.created_at DESC NULLS LAST LIMIT :lim)")
        rows = conn.run(" UNION ALL ".join(parts) + " ORDER BY 2 DESC NULLS LAST LIMIT :lim", lim=int(limit))
    return [{"kind": r[0], "at": r[1].isoformat() if r[1] else None, "title": r[2], "sub": r[3], "ref": r[4]}
            for r in rows]
