"""account_purge.py — Final account purge after the grace period (task 8.5c · F27 · docs/rules/account-deletion.md ·
docs/SYSTEMS_INDEX.md §25i).

A soft-deleted account (account_deletion.soft_delete — kind 'admin' or 'self') whose deleted_at is older than
tw_settings.limit("account_purge_days") (30) is purged for good by the daily scheduler job `account_purge`:

  queue      account_purge (user_id PK, stage files|db|done, attempts, next_attempt_at, last_error — never a name,
             e-mail, phone or file name). claim() puts a row there under FOR UPDATE on the users row — the same lock
             account_deletion.restore() takes, so a restore and a purge never interleave: once a row exists the
             restore is refused (409 purging / already_purged).
  1. files   every storage object of the account (all upload buckets — referenced paths + every `{uid}_…` object the
             storage lists) → the ONE storage delete (server.storage_delete, registered via set_storage). 404 = gone
             = success. Any failure → attempts + 1, next_attempt_at = NOW() + 2^attempts hours (≤ the cap), the
             database untouched. A later run deletes them again (404 = success) until every one succeeds.
  2. db      ONE transaction (users row FOR UPDATE + still deleted + still older than the period): own data deleted,
             shared records kept with their personal copies emptied, the users row left as a tombstone
             (id · user_type · deleted_at · deleted_kind · purged_at; e-mail = an internal unusable value → the
             address is free again; password = a hash nobody knows; name / tw_id gone) → stage done.
  3. retention  admin audit rows (2 years) · reports (1 year) · appointment_events (1 year) linked to a purged account
             are deleted once older than their period (tw_limits).

The table of what happens to every table: docs/rules/account-deletion.md → «الحذف النهائي».
DB functions import auth lazily (auth.py's scheduler imports this module inside the handler).
"""
import re
import secrets
from datetime import datetime, timedelta, timezone

JOB_TYPE = "account_purge"
RUN_HOUR_UTC = 3                     # the daily job runs at 03:00 UTC (quiet hours)
STAGES = ("files", "db", "done")
# Every upload bucket (server._UPLOAD_KINDS values) — an account's objects are named `{uid}_{kind}_{12 hex}.{ext}`
BUCKETS = ("avatars", "kyc-docs")
_OBJECT_RE = re.compile(r"^(\d+)_[a-z-]+_[0-9a-f]{12}\.(?:jpg|png|webp)$")
_PUBLIC_RE = re.compile(r"/storage/v1/object/public/([a-z0-9-]+)/([^/?#]+)$")
_PRIVATE_RE = re.compile(r"^(kyc-docs)/([^/?#]+)$")
_NEEDLE_MIN = 4                      # an identifier / name shorter than this is never searched for (too common)

_storage = {"delete": None, "list": None}


def set_storage(delete_fn, list_fn) -> None:
    """server.py registers the ONE storage delete + list (same Supabase settings as the uploads)."""
    _storage["delete"], _storage["list"] = delete_fn, list_fn


def _days(name: str) -> int:
    import tw_settings
    return int(tw_settings.limit(name))


# ── Migration (critical — account_deletion.restore reads the queue) ──
# The same statements: docs/migrations/8.5c_account_purge.sql (production, by hand, read-only check first).
APPLY_SQL = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS purged_at TIMESTAMPTZ",
    "CREATE TABLE IF NOT EXISTS account_purge ("
    " user_id BIGINT PRIMARY KEY REFERENCES users(id),"
    " stage TEXT NOT NULL DEFAULT 'files' CHECK (stage IN ('files', 'db', 'done')),"
    " attempts INTEGER NOT NULL DEFAULT 0,"
    " next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
    " last_error TEXT,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
    " updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS idx_account_purge_due ON account_purge (next_attempt_at) WHERE stage <> 'done'",
    "CREATE INDEX IF NOT EXISTS idx_users_purged ON users(id) WHERE purged_at IS NOT NULL",
)


def migrate_account_purge():
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


def purge_state(user_id: int, conn=None):
    """None (no purge started) | 'purging' (files / db) | 'purged' (done)."""
    if conn is None:
        from auth import db_conn
        with db_conn() as c:
            return purge_state(user_id, c)
    rows = conn.run("SELECT stage FROM account_purge WHERE user_id = :u", u=int(user_id))
    if not rows:
        return None
    return "purged" if rows[0][0] == "done" else "purging"


# ── Daily job ──

def next_run_at(now=None) -> datetime:
    """The next RUN_HOUR_UTC strictly after now (UTC)."""
    now = now or datetime.now(timezone.utc)
    at = now.replace(hour=RUN_HOUR_UTC, minute=0, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def ensure_daily_job(conn=None) -> None:
    """The next day's job exists (scheduler_jobs, dedupe per date — never due at creation). Called by every
    scheduler cycle on the cycle's own connection (no second pool checkout); ON CONFLICT DO NOTHING keeps it one
    row per day."""
    import auth
    at = next_run_at()
    auth.schedule_job(JOB_TYPE, {}, at, f"{JOB_TYPE}:{at.date().isoformat()}", max_attempts=3, conn=conn)


def run_daily() -> dict:
    """The scheduler handler: claim due accounts → files → db → retention. Per-account failures stay in the queue
    (never raised); an unexpected DB failure raises (the scheduler retries the job)."""
    out = {"claimed": claim_due(), "files_failed": 0, "purged": 0, "db_failed": 0}
    for uid in _due_ids():
        r = process_one(uid)
        if r == "files_failed":
            out["files_failed"] += 1
        elif r == "db_failed":
            out["db_failed"] += 1
        elif r == "done":
            out["purged"] += 1
    out["retention"] = retention()
    print(f"[account-purge] claimed={out['claimed']} purged={out['purged']} files_failed={out['files_failed']} "
          f"db_failed={out['db_failed']} retention={out['retention']}")
    return out


def _candidates(conn, days: int, limit: int) -> list:
    return [int(r[0]) for r in conn.run(
        "SELECT u.id FROM users u WHERE u.deleted_at IS NOT NULL AND u.purged_at IS NULL "
        "AND u.deleted_at < NOW() - make_interval(days => :d) "
        "AND NOT EXISTS (SELECT 1 FROM account_purge p WHERE p.user_id = u.id) ORDER BY u.deleted_at LIMIT :n",
        d=days, n=limit)]


def claim_due() -> int:
    """Each candidate in its own short transaction: users row FOR UPDATE (the restore's lock) → still deleted +
    still older than the period → queue row (stage files). → claimed count."""
    from auth import db_conn
    import tw_settings
    days, n = _days("account_purge_days"), int(tw_settings.limit("account_purge_batch"))
    claimed = 0
    with db_conn() as conn:
        for uid in _candidates(conn, days, n):
            conn.run("BEGIN")
            try:
                ok = conn.run("SELECT 1 FROM users WHERE id = :u AND deleted_at IS NOT NULL AND purged_at IS NULL "
                              "AND deleted_at < NOW() - make_interval(days => :d) FOR UPDATE", u=uid, d=days)
                if ok and conn.run("INSERT INTO account_purge (user_id) VALUES (:u) ON CONFLICT DO NOTHING "
                                   "RETURNING 1", u=uid):
                    claimed += 1
                conn.run("COMMIT")
            except Exception:
                conn.run("ROLLBACK")
                raise
    return claimed


def _due_ids() -> list:
    from auth import db_conn
    import tw_settings
    with db_conn() as conn:
        return [int(r[0]) for r in conn.run(
            "SELECT user_id FROM account_purge WHERE stage IN ('files', 'db') AND next_attempt_at <= NOW() "
            "ORDER BY next_attempt_at, user_id LIMIT :n", n=int(tw_settings.limit("account_purge_batch")))]


def _fail(uid: int, error: str) -> None:
    """attempts + 1 · next try after 2^attempts hours (≤ account_purge_retry_max_hours) · last_error = a code /
    count / status only (never a name, an address or a file name)."""
    from auth import db_conn
    import tw_settings
    with db_conn() as conn:
        conn.run("UPDATE account_purge SET attempts = attempts + 1, last_error = :e, updated_at = NOW(), "
                 "next_attempt_at = NOW() + make_interval(hours => LEAST(POWER(2, attempts + 1)::int, :cap)) "
                 "WHERE user_id = :u AND stage <> 'done'",
                 e=error[:200], cap=int(tw_settings.limit("account_purge_retry_max_hours")), u=int(uid))


def process_one(uid: int) -> str:
    """→ 'files_failed' | 'db_failed' | 'done' | 'skipped'."""
    from auth import db_conn
    with db_conn() as conn:
        rows = conn.run("SELECT stage FROM account_purge WHERE user_id = :u", u=int(uid))
    if not rows or rows[0][0] == "done":
        return "skipped"
    if rows[0][0] == "files":
        err = delete_files(uid)
        if err:
            _fail(uid, err)
            return "files_failed"
        with db_conn() as conn:
            conn.run("UPDATE account_purge SET stage = 'db', last_error = NULL, next_attempt_at = NOW(), "
                     "updated_at = NOW() WHERE user_id = :u AND stage = 'files'", u=int(uid))
    try:
        done = purge_db(uid)
    except Exception as e:
        print(f"[account-purge] db stage user={uid} failed: {type(e).__name__}")
        _fail(uid, "db:" + type(e).__name__)
        return "db_failed"
    return "done" if done else "skipped"


# ── 1. files ──

def _object_of(value, uid: int):
    """(bucket, name) of a stored image value that names one of this account's objects, else None."""
    if not isinstance(value, str) or not value:
        return None
    m = _PRIVATE_RE.match(value) or _PUBLIC_RE.search(value.split("?", 1)[0])
    if not m or m.group(1) not in BUCKETS:
        return None
    om = _OBJECT_RE.match(m.group(2))
    if not om or int(om.group(1)) != int(uid):
        return None   # not named for this account (F24) — never someone else's file
    return m.group(1), m.group(2)


def account_files(uid: int, conn) -> set:
    """Objects referenced by the account's own rows (profiles · company_profiles · kyc_submissions)."""
    vals = []
    for sql in ("SELECT avatar_url, cover_url FROM profiles WHERE user_id = :u",
                "SELECT cover_url, NULL FROM company_profiles WHERE user_id = :u",
                "SELECT id_front_url, selfie_url FROM kyc_submissions WHERE user_id = :u"):
        for r in conn.run(sql, u=int(uid)):
            vals.extend(r)
    return {o for o in (_object_of(v, uid) for v in vals) if o}


def delete_files(uid: int):
    """Every object of the account → storage_delete. → None (all gone) | an error code for last_error."""
    from auth import db_conn
    delete, lister = _storage["delete"], _storage["list"]
    if delete is None or lister is None:
        return "storage:not_registered"
    with db_conn() as conn:
        objs = account_files(uid, conn)
    prefix = f"{int(uid)}_"
    for bucket in BUCKETS:
        names = lister(bucket, prefix)
        if names is None:
            return f"storage:list_failed:{bucket}"
        for name in names:
            om = _OBJECT_RE.match(name or "")
            if om and int(om.group(1)) == int(uid):
                objs.add((bucket, name))
    failed, last = 0, None
    for bucket, name in sorted(objs):
        r = delete(bucket, name)
        if not r.get("ok"):
            failed += 1
            last = r.get("status") or r.get("reason")
    if failed:
        return f"storage:{failed}/{len(objs)} failed (last {last})"
    return None


# ── 2. db (one transaction) ──

_OWN_DELETES = (
    # content the person made about themselves / their own account → deleted
    "DELETE FROM company_post_comments WHERE user_id = :u",
    "DELETE FROM company_post_appreciations WHERE user_id = :u",
    "DELETE FROM company_post_saves WHERE user_id = :u",
    "DELETE FROM company_post_views WHERE viewer_user_id = :u",
    "DELETE FROM company_posts WHERE company_id = :u",
    "DELETE FROM profile_follows WHERE follower_id = :u OR followed_id = :u",
    "DELETE FROM profile_interests WHERE actor_user_id = :u OR target_user_id = :u",
    "DELETE FROM profile_views WHERE viewer_user_id = :u OR viewed_user_id = :u",
    "DELETE FROM blocks WHERE blocker_id = :u OR blocked_id = :u",
    "DELETE FROM password_reset_tokens WHERE user_id = :u",
    "DELETE FROM email_notify_prefs WHERE user_id = :u",
    "DELETE FROM email_send_log WHERE user_id = :u",
    "DELETE FROM feed_snapshots WHERE user_id = :u",
    "DELETE FROM profession_suggestions WHERE user_id = :u",
    "DELETE FROM kyc_submissions WHERE user_id = :u",
    "DELETE FROM experience WHERE user_id = :u",
    "DELETE FROM education WHERE user_id = :u",
    "DELETE FROM user_skills WHERE user_id = :u",
    "DELETE FROM user_langs WHERE user_id = :u",
    "DELETE FROM user_links WHERE user_id = :u",
    "DELETE FROM courses WHERE user_id = :u",
    "DELETE FROM company_ratings WHERE rater_id = :u",
    "DELETE FROM company_saved_candidates WHERE company_id = :u",
    "DELETE FROM candidate_bank_notes WHERE company_id = :u",
    "DELETE FROM company_candidate_job_refs WHERE company_id = :u",
    "DELETE FROM pipeline_notes WHERE created_by = :u OR pipeline_entry_id IN "
    "(SELECT id FROM job_pipeline_entries WHERE company_id = :u)",
    "DELETE FROM company_branches WHERE company_id = :u",
    "DELETE FROM company_settings WHERE company_id = :u",
    "DELETE FROM company_profiles WHERE user_id = :u",
    "DELETE FROM profiles WHERE user_id = :u",
)

_SHARED_UPDATES = (
    # shared records stay for the other side («حساب محذوف») — the person's own copies inside them are emptied
    "UPDATE job_applications SET cover_letter = NULL WHERE user_id = :u",
    "UPDATE jobs SET description = NULL WHERE company_id = :u",
    "UPDATE appointments SET representative_name = NULL, notes = NULL, location_text = NULL, online_url = NULL "
    "WHERE company_id = :u OR created_by = :u",
    "UPDATE appointments SET representative_user_id = NULL, representative_name = NULL "
    "WHERE representative_user_id = :u",
    "UPDATE appointment_events SET payload = NULL WHERE actor_id = :u",
    "UPDATE pipeline_stage_events SET reason = NULL WHERE changed_by = :u",
    "UPDATE reports SET reason = NULL, target_url = NULL WHERE reporter_id = :u OR reported_id = :u",
    # admin audit rows about the account keep the internal number only (target user_id=N)
    "UPDATE admin_audit_log SET old_value = NULL, new_value = NULL "
    "WHERE substring(target from '(?:^|,)user_id=(\\d+)(?:,|$)') = :us",
)


def _run(conn, stmt: str, **params):
    """conn.run with only the parameters the statement names."""
    return conn.run(stmt, **{k: v for k, v in params.items() if re.search(r":" + k + r"\b", stmt)})


def _needles(row) -> list:
    """EXACT identifiers searched for in free text left in other rows (e-mail · tw_id · phone · contact e-mail).
    Never the name: a common name («محمد») would hit other people's rows (task 8.5c-2)."""
    tw, _name, email, phone, contact = row
    out = [v.strip() for v in (email, tw, phone, contact) if isinstance(v, str) and v.strip()]
    return [v for v in out if len(v) >= _NEEDLE_MIN]


def _name_needle(row):
    """The full name, replaced by «حساب محذوف» in the notifications of related people only — or None."""
    name = row[1]
    return name.strip() if isinstance(name, str) and len(name.strip()) >= _NEEDLE_MIN else None


# Everyone the account dealt with (task 8.5c-2) — computed BEFORE _OWN_DELETES (it deletes follows / interests /
# views). Only their notifications get the name replaced; nobody else's text is ever touched by name.
_RELATED_SQL = (
    "SELECT receiver_id FROM messages WHERE sender_id = :u "
    "UNION SELECT sender_id FROM messages WHERE receiver_id = :u "
    "UNION SELECT j.company_id FROM job_applications a JOIN jobs j ON j.id = a.job_id WHERE a.user_id = :u "
    "UNION SELECT a.user_id FROM job_applications a JOIN jobs j ON j.id = a.job_id WHERE j.company_id = :u "
    "UNION SELECT unnest(ARRAY[company_id, applicant_id, created_by, representative_user_id]) FROM appointments "
    "WHERE :u IN (company_id, applicant_id, created_by, representative_user_id) "
    "UNION SELECT followed_id FROM profile_follows WHERE follower_id = :u "
    "UNION SELECT follower_id FROM profile_follows WHERE followed_id = :u "
    "UNION SELECT target_user_id FROM profile_interests WHERE actor_user_id = :u "
    "UNION SELECT actor_user_id FROM profile_interests WHERE target_user_id = :u "
    "UNION SELECT viewed_user_id FROM profile_views WHERE viewer_user_id = :u "
    "UNION SELECT viewer_user_id FROM profile_views WHERE viewed_user_id = :u "
    # reactions / comments on the account's posts
    "UNION SELECT x.user_id FROM company_post_appreciations x JOIN company_posts p ON p.id = x.post_id "
    "WHERE p.company_id = :u "
    "UNION SELECT x.user_id FROM company_post_comments x JOIN company_posts p ON p.id = x.post_id "
    "WHERE p.company_id = :u "
    # posts the account reacted to / commented on: the owner + the other commenters
    "UNION SELECT p.company_id FROM company_posts p WHERE p.id IN "
    "(SELECT post_id FROM company_post_appreciations WHERE user_id = :u "
    "UNION SELECT post_id FROM company_post_comments WHERE user_id = :u) "
    "UNION SELECT x.user_id FROM company_post_comments x WHERE x.post_id IN "
    "(SELECT post_id FROM company_post_comments WHERE user_id = :u)"
)


def _related_ids(conn, uid: int) -> list:
    return sorted({int(r[0]) for r in conn.run(_RELATED_SQL, u=int(uid)) if r[0] is not None and int(r[0]) != uid})


def purge_db(uid: int) -> bool:
    """ONE transaction. users row FOR UPDATE + still deleted + still older than the period (else nothing, False).
    → True when the tombstone is written and the queue row is done."""
    from auth import db_conn, hash_password
    uid = int(uid)
    days = _days("account_purge_days")
    dead_hash = hash_password(secrets.token_urlsafe(32))   # bcrypt outside the transaction — nobody knows it
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            row = conn.run(
                "SELECT u.tw_id, u.full_name, u.email, p.phone, cp.contact_email FROM users u "
                "LEFT JOIN profiles p ON p.user_id = u.id LEFT JOIN company_profiles cp ON cp.user_id = u.id "
                "WHERE u.id = :u AND u.deleted_at IS NOT NULL AND u.purged_at IS NULL "
                "AND u.deleted_at < NOW() - make_interval(days => :d) FOR UPDATE OF u", u=uid, d=days)
            stage = conn.run("SELECT stage FROM account_purge WHERE user_id = :u FOR UPDATE", u=uid)
            if not row or not stage or stage[0][0] != "db":
                conn.run("ROLLBACK")
                return False
            tw, email = row[0][0], row[0][2]
            needles, name = _needles(row[0]), _name_needle(row[0])
            related = _related_ids(conn, uid) if name else []   # before _OWN_DELETES (follows / interests / views)
            if tw:
                conn.run("DELETE FROM company_post_comment_mentions WHERE mentioned_tw_id = :t", t=tw)
            # notifications: the account's own + every one it acted in + every one naming an exact identifier
            conn.run("DELETE FROM notifications WHERE user_id = :u OR actor_id = :u OR last_actor_id = :u", u=uid)
            for nd in needles:
                conn.run("DELETE FROM notifications WHERE strpos(COALESCE(title, '') || ' ' || COALESCE(body, ''), "
                         ":n) > 0", n=nd)
            # the name: never deleted by — replaced by «حساب محذوف», in related people's notifications only
            if related:
                import account_deletion as ad
                conn.run("UPDATE notifications SET title = replace(title, :n, :l), body = replace(body, :n, :l) "
                         "WHERE user_id = ANY(CAST(:ids AS BIGINT[])) "
                         "AND (strpos(COALESCE(title, ''), :n) > 0 OR strpos(COALESCE(body, ''), :n) > 0)",
                         n=name, l=ad.deleted_label(), ids=related)
            for stmt in _OWN_DELETES:
                _run(conn, stmt, u=uid, us=str(uid))
            if conn.run("SELECT to_regclass('public.support_tickets') IS NOT NULL")[0][0]:
                conn.run("DELETE FROM support_tickets WHERE user_id = :u OR lower(guest_email) = lower(:e)",
                         u=uid, e=email or "")
                conn.run("DELETE FROM support_guest_otp WHERE lower(email) = lower(:e)", e=email or "")
            for stmt in _SHARED_UPDATES:
                _run(conn, stmt, u=uid, us=str(uid))
            for nd in needles:   # free text anywhere in the audit log with an exact identifier (never the name)
                conn.run("UPDATE admin_audit_log SET old_value = NULL WHERE strpos(lower(old_value), lower(:n)) > 0",
                         n=nd)
                conn.run("UPDATE admin_audit_log SET new_value = NULL WHERE strpos(lower(new_value), lower(:n)) > 0",
                         n=nd)
            conn.run(
                "UPDATE users SET tw_id = NULL, full_name = '', email = :e, password_hash = :h, country_code = NULL, "
                "is_verified = FALSE, kyc_step = 'none', email_verified = FALSE, phone_verified = FALSE, "
                "suspended_at = NULL, suspended_reason = NULL, suspended_by = NULL, deleted_by = NULL, "
                "deleted_reason = NULL, terms_accepted_at = NULL, terms_version = NULL, "
                "session_version = session_version + 1, purged_at = NOW() WHERE id = :u",
                e=f"#purged:{uid}", h=dead_hash, u=uid)
            conn.run("UPDATE account_purge SET stage = 'done', last_error = NULL, updated_at = NOW() "
                     "WHERE user_id = :u", u=uid)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    import auth
    auth._cache_del(f"profile:{uid}")   # a cached copy of the old profile never outlives the purge
    auth._cache_del("jobs:")
    print(f"[account-purge] user={uid} purged")
    return True


# ── 3. retention ──

_PURGED = "(SELECT id FROM users WHERE purged_at IS NOT NULL)"


def retention() -> dict:
    """Rows linked to a purged account, deleted once older than their period (days from tw_limits)."""
    from auth import db_conn
    out = {}
    with db_conn() as conn:
        out["admin_audit_log"] = len(conn.run(
            "DELETE FROM admin_audit_log WHERE created_at < NOW() - make_interval(days => :d) "
            "AND substring(target from '(?:^|,)user_id=(\\d+)(?:,|$)')::bigint IN " + _PURGED + " RETURNING 1",
            d=_days("retention_admin_audit_days")) or [])
        out["reports"] = len(conn.run(
            "DELETE FROM reports WHERE created_at < NOW() - make_interval(days => :d) "
            "AND (reporter_id IN " + _PURGED + " OR reported_id IN " + _PURGED + ") RETURNING 1",
            d=_days("retention_reports_days")) or [])
        out["appointment_events"] = len(conn.run(
            "DELETE FROM appointment_events WHERE created_at < NOW() - make_interval(days => :d) "
            "AND (actor_id IN " + _PURGED + " OR appointment_id IN (SELECT a.id FROM appointments a "
            "WHERE a.company_id IN " + _PURGED + " OR a.applicant_id IN " + _PURGED + ")) RETURNING 1",
            d=_days("retention_appointment_events_days")) or [])
    return out
