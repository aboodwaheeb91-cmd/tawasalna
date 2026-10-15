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
  activity()          → latest registrations / jobs / KYC submissions / reports (paged — task 5.3a3)

Users table (§25d — task 5.3a3) — read-only, check_admin:
  users_list()  = GET /admin/users         (search · type · verification · sort · page / limit ≤ USERS_PAGE_MAX)
  users_csv()   = GET /admin/users/export  (same filters, same columns minus the image — the export is
                  recorded in the audit log by the middleware: AUDIT_READ_ROUTES in server.py)
  One SQL builder (_users_where) for both. Fields: id · tw_id · full_name · avatar_url (profiles, else the
  company logo in company_profiles — the existing image source) · user_type · email · verification
  (verified | pending | unverified) · created_at. Nothing else (no password hash, phone, tokens …).

Jobs table (§25e — task 5.3j) — read-only, check_admin:
  jobs_list()   = GET /admin/jobs  (every state: active · paused · closed · expired · hidden · archived — state from
                  auth.job_eff_status_sql, the SQL twin of _eff_status · search title / company · status ·
                  page / limit ≤ JOBS_PAGE_MAX · counts per state · applicant_count per job)
"""
import csv
import io

from auth import db_conn, job_active_sql, job_eff_status_sql, _ALLOWED_DURATIONS

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
ACTIVITY_LIMIT = 8          # dashboard card (task 5.3a3 — «عرض الكل» opens the paged list)
ACTIVITY_PAGE_MAX = 50

USER_TYPES = ("emp", "co", "edu")
USER_VERIFICATION = ("verified", "pending", "unverified")
USER_SORTS = ("newest", "oldest")
USERS_PAGE_MAX = 100
USERS_EXPORT_MAX = 50000
USERS_Q_MAX = 100


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
            "SELECT COUNT(*) FROM users u WHERE u.user_type = 'co' "
            "AND EXISTS (SELECT 1 FROM profiles p WHERE p.user_id = u.id AND p.is_verified)"))
        out["active_jobs"] = card(one("SELECT COUNT(*) FROM jobs j WHERE " + job_active_sql("j")),
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


def activity(page: int = 1, limit: int = ACTIVITY_LIMIT) -> dict:
    """Latest events from the existing tables, newest first, paged (task 5.3a3) — names / titles only
    (no emails, no report text). Each source is cut at page * limit rows before the merge."""
    page = max(1, int(page))
    limit = max(1, min(ACTIVITY_PAGE_MAX, int(limit)))
    upto = page * limit
    parts = [
        "(SELECT 'register' AS kind, u.created_at::timestamptz AS at, u.full_name AS title, "
        "u.user_type AS sub, u.id AS ref FROM users u ORDER BY u.created_at DESC NULLS LAST LIMIT :upto)",
        "(SELECT 'job' AS kind, j.created_at::timestamptz, j.title, c.full_name, j.id FROM jobs j "
        "LEFT JOIN users c ON c.id = j.company_id ORDER BY j.created_at DESC NULLS LAST LIMIT :upto)",
        "(SELECT 'kyc' AS kind, k.submitted_at::timestamptz, u.full_name, u.user_type, k.user_id "
        "FROM kyc_submissions k JOIN users u ON u.id = k.user_id WHERE k.step = 'review' "
        "ORDER BY k.submitted_at DESC NULLS LAST LIMIT :upto)",
    ]
    counts = ["(SELECT COUNT(*) FROM users)", "(SELECT COUNT(*) FROM jobs)",
              "(SELECT COUNT(*) FROM kyc_submissions k JOIN users u ON u.id = k.user_id WHERE k.step = 'review')"]
    with db_conn() as conn:
        if _table_exists(conn, "reports"):
            parts.append(
                "(SELECT 'report' AS kind, r.created_at::timestamptz, u.full_name, r.report_type, r.id "
                "FROM reports r LEFT JOIN users u ON u.id = r.reported_id "
                "ORDER BY r.created_at DESC NULLS LAST LIMIT :upto)")
            counts.append("(SELECT COUNT(*) FROM reports)")
        rows = conn.run(" UNION ALL ".join(parts) + " ORDER BY 2 DESC NULLS LAST LIMIT :lim OFFSET :off",
                        upto=upto, lim=limit, off=(page - 1) * limit)
        total = int(conn.run("SELECT " + " + ".join(counts))[0][0] or 0)
    items = [{"kind": r[0], "at": r[1].isoformat() if r[1] else None, "title": r[2], "sub": r[3], "ref": r[4]}
             for r in rows]
    return {"items": items, "total": total, "page": page, "limit": limit}


# ── users table (§25d — task 5.3a3) ──
# verification of one account — profiles.is_verified, the one badge source (task 5.0c —
# auth.set_user_verified); "pending" = not verified + a KYC submission in review.
_VERIFIED_SQL = "COALESCE(p.is_verified, FALSE)"
_PENDING_SQL = "EXISTS (SELECT 1 FROM kyc_submissions k WHERE k.user_id = u.id AND k.step = 'review')"
_USERS_FROM = (" FROM users u LEFT JOIN profiles p ON p.user_id = u.id"
               " LEFT JOIN company_profiles cp ON cp.user_id = u.id")
USERS_COLUMNS = ("id", "tw_id", "full_name", "avatar_url", "user_type", "email", "verification", "created_at")


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _users_where(q: str = "", user_type: str = "", verification: str = ""):
    """→ (where SQL, params). Values are validated by the caller (server.py) — only allowlisted
    type / verification reach here; q is always a bound parameter."""
    conds, params = [], {}
    q = (q or "").strip()
    if q:
        conds.append("(u.full_name ILIKE :q OR u.email ILIKE :q OR u.tw_id ILIKE :q)")
        params["q"] = _like(q)
    if user_type:
        conds.append("u.user_type = :t")
        params["t"] = user_type
    if verification == "verified":
        conds.append(_VERIFIED_SQL)
    elif verification == "pending":
        conds.append("NOT " + _VERIFIED_SQL + " AND " + _PENDING_SQL)
    elif verification == "unverified":
        conds.append("NOT " + _VERIFIED_SQL + " AND NOT " + _PENDING_SQL)
    return (" WHERE " + " AND ".join(conds)) if conds else "", params


def _users_rows(conn, where, params, sort, limit, offset):
    order = "ASC" if sort == "oldest" else "DESC"
    return conn.run(
        "SELECT u.id, u.tw_id, u.full_name, COALESCE(NULLIF(p.avatar_url, ''), cp.avatar_url), u.user_type, u.email, "
        "CASE WHEN " + _VERIFIED_SQL + " THEN 'verified' WHEN " + _PENDING_SQL + " THEN 'pending' ELSE 'unverified' END, "
        "u.created_at" + _USERS_FROM + where +
        f" ORDER BY u.created_at {order} NULLS LAST, u.id {order} LIMIT :lim OFFSET :off",
        lim=int(limit), off=int(offset), **params)


def _user_item(r) -> dict:
    it = dict(zip(USERS_COLUMNS, r))
    it["created_at"] = it["created_at"].isoformat() if it["created_at"] else None
    return it


def users_list(q: str = "", user_type: str = "", verification: str = "", sort: str = "newest",
               page: int = 1, limit: int = 20) -> dict:
    page = max(1, int(page))
    limit = max(1, min(USERS_PAGE_MAX, int(limit)))
    where, params = _users_where(q, user_type, verification)
    with db_conn() as conn:
        total = int(conn.run("SELECT COUNT(*)" + _USERS_FROM + where, **params)[0][0] or 0)
        rows = _users_rows(conn, where, params, sort, limit, (page - 1) * limit)
    return {"items": [_user_item(r) for r in rows], "total": total, "page": page, "limit": limit}


# CSV columns = the table columns without the image (header names are data, not UI text)
_CSV_FIELDS = ("id", "tw_id", "full_name", "user_type", "email", "verification", "created_at")


def _csv_cell(v) -> str:
    s = "" if v is None else str(v)
    # spreadsheet formula injection: a cell that starts with = + - @ (or tab / CR) is read as text
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def users_csv(q: str = "", user_type: str = "", verification: str = "", sort: str = "newest") -> str:
    where, params = _users_where(q, user_type, verification)
    with db_conn() as conn:
        rows = _users_rows(conn, where, params, sort, USERS_EXPORT_MAX, 0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_CSV_FIELDS)
    for r in rows:
        it = _user_item(r)
        w.writerow([_csv_cell(it[f]) for f in _CSV_FIELDS])
    return "\ufeff" + buf.getvalue()   # BOM → Arabic names open correctly in Excel


# ── jobs table (§25e — task 5.3j) ──
# Every job in every state. The state is ONE value per row: 'archived' when archived_at is set, else 'hidden'
# when the admin hid it (5.3j phase 2), else the effective status from auth.job_eff_status_sql (the SQL twin
# of _eff_status — never computed in the page). effective_status is returned too (for archived / hidden rows
# it tells which actions fit: reactivate = closed / expired · extend = active / paused).
JOB_ADMIN_STATUSES = ("active", "paused", "closed", "expired", "hidden", "archived")
JOBS_PAGE_MAX = 100
_JOB_STATE_SQL = ("(CASE WHEN j.archived_at IS NOT NULL THEN 'archived' WHEN j.admin_hidden_at IS NOT NULL "
                  "THEN 'hidden' ELSE " + job_eff_status_sql("j") + " END)")
_JOBS_FROM = " FROM jobs j LEFT JOIN users u ON u.id = j.company_id"
JOBS_COLUMNS = ("id", "title", "company_id", "company_name", "company_tw_id", "company_type", "status",
                "created_at", "expires_at", "closed_at", "paused_at", "archived_at", "duration_days", "views",
                "applicant_count", "effective_status", "admin_hidden_at", "admin_hidden_reason")


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def jobs_list(q: str = "", status: str = "", page: int = 1, limit: int = 20) -> dict:
    """GET /admin/jobs. status MUST be '' or a JOB_ADMIN_STATUSES value (checked by server.py); q is a bound
    parameter (title or company name). counts = jobs per state for the same search (the status tabs)."""
    page = max(1, int(page))
    limit = max(1, min(JOBS_PAGE_MAX, int(limit)))
    conds, params = [], {}
    q = (q or "").strip()
    if q:
        conds.append("(j.title ILIKE :q OR u.full_name ILIKE :q)")
        params["q"] = _like(q)
    search = (" WHERE " + " AND ".join(conds)) if conds else ""
    where = search
    if status:
        where = (search + " AND " if search else " WHERE ") + _JOB_STATE_SQL + " = :st"
        params_page = dict(params, st=status)
    else:
        params_page = params
    with db_conn() as conn:
        counts = {s: 0 for s in JOB_ADMIN_STATUSES}
        counts["all"] = 0
        for st, n in conn.run("SELECT " + _JOB_STATE_SQL + ", COUNT(*)" + _JOBS_FROM + search + " GROUP BY 1",
                              **params):
            counts["all"] += int(n)
            if st in JOB_ADMIN_STATUSES:
                counts[st] = int(n)
        total = int(conn.run("SELECT COUNT(*)" + _JOBS_FROM + where, **params_page)[0][0] or 0)
        rows = conn.run(
            "SELECT j.id, j.title, j.company_id, u.full_name, u.tw_id, u.user_type, " + _JOB_STATE_SQL + ", "
            "j.created_at, j.expires_at, j.closed_at, j.paused_at, j.archived_at, j.duration_days, "
            "COALESCE(j.views, 0), (SELECT COUNT(*) FROM job_applications a WHERE a.job_id = j.id), "
            + job_eff_status_sql("j") + ", j.admin_hidden_at, j.admin_hidden_reason"
            + _JOBS_FROM + where +
            " ORDER BY j.created_at DESC NULLS LAST, j.id DESC LIMIT :lim OFFSET :off",
            lim=limit, off=(page - 1) * limit, **params_page)
    items = []
    for r in rows:
        it = dict(zip(JOBS_COLUMNS, r))
        for k in ("created_at", "expires_at", "closed_at", "paused_at", "archived_at", "admin_hidden_at"):
            it[k] = _iso(it[k])
        it["applicant_count"] = int(it["applicant_count"] or 0)
        items.append(it)
    # durations = the only allowed listing durations (auth._ALLOWED_DURATIONS) — the page's reactivate / extend choices
    return {"items": items, "total": total, "page": page, "limit": limit, "counts": counts,
            "durations": sorted(_ALLOWED_DURATIONS)}
