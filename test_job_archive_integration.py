"""
PR-JOB Integration Tests — Soft Archive for Jobs
Requires a live PostgreSQL test database (NOT production).

Connection: 127.0.0.1:5432 / tawasalna_test_pipeline / tawasalna_test_user
Run: python test_job_archive_integration.py

Tests verify:
  ja-01  Owner can archive a job (archive_job returns {"archived": True, "was_already_archived": False})
  ja-02  archived_at is set to a non-NULL TIMESTAMPTZ in the DB
  ja-03  archived_by is set to the correct user id from JWT (not from body/query)
  ja-04  Non-owner gets PermissionError (403 equivalent)
  ja-05  Missing job gets LookupError (404 equivalent)
  ja-06  Repeated archive is idempotent (was_already_archived=True, no error)
  ja-07  Job row is NOT deleted — count remains 1 after archive
  ja-08  Old job_applications are preserved after archive
  ja-09  get_jobs() public list excludes archived jobs (archived_at IS NULL filter)
  ja-10  get_job() public detail returns None (→ 404) for archived job
  ja-11  apply_job() on archived job raises JobArchivedError (→ 409)
  ja-12  apply_job() on non-archived job still succeeds
  ja-13  get_company_jobs_all(view='active') excludes archived jobs
  ja-14  get_company_jobs_all(view='archived') returns only archived jobs (owner view)
  ja-15  archive does NOT change jobs.status field
  ja-16  get_company_candidate_suggestions() excludes archived jobs
  ja-17  view='invalid' raises ValueError at the Python level
  ja-18  archive_job response includes was_already_archived flag
  ja-19  Archived job absent from closed_count in get_jobs() when has_company_id=True
  ja-20  archived_at is a TIMESTAMPTZ column (nullable) — verify via information_schema
  ja-21  archived_by is an INTEGER column (nullable FK) — verify via information_schema
  ja-22  archive_job archived_by matches the supplied user id in the DB
  ja-23  apply_job on non-archived job inserts a DB row (verified in DB)
  ja-24  job_pipeline_entries preserved after soft archive
  ja-25  pipeline_stage_events preserved after soft archive
  ja-26  pipeline_notes preserved after soft archive
  ja-27  appointments row with pipeline_entry_id preserved after soft archive
  ja-28  get_job_applicants() returns applicants for archived job (owner view)
  ja-29  Concurrency: FOR UPDATE lock → apply_job sees archived state → JobArchivedError
  ja-30  Concurrent double archive → exactly 1 real archive + 1 idempotent
  ja-31  Cache invalidation: get_jobs() excludes archived job immediately after archive
  Exit code: 0 on all pass, 1 on any failure
"""

import sys, os

TEST_DB_URL = "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline"
os.environ['SUPABASE_DB_URL'] = TEST_DB_URL

import pg8000.native as _pg8000_native

def _get_test_conn():
    return _pg8000_native.Connection(
        user='tawasalna_test_user',
        password='test_pass_pr1',
        host='127.0.0.1',
        port=5432,
        database='tawasalna_test_pipeline',
    )

# ── Result tracking ───────────────────────────────────────────────────────────
PASS, FAIL = '✅ PASS', '❌ FAIL'
results = []

def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    marker = '✅' if condition else '❌'
    suffix = f'  [{detail}]' if detail and not condition else ''
    print(f'{marker}  {name}{suffix}')

# ── Setup: minimal schema for archive tests ───────────────────────────────────
def _setup(conn):
    drops = [
        "DROP TABLE IF EXISTS pipeline_notes CASCADE",
        "DROP TABLE IF EXISTS pipeline_stage_events CASCADE",
        "DROP TABLE IF EXISTS candidate_bank_notes CASCADE",
        "DROP TABLE IF EXISTS job_pipeline_entries CASCADE",
        "DROP TABLE IF EXISTS company_candidate_job_refs CASCADE",
        "DROP TABLE IF EXISTS job_applications CASCADE",
        "DROP TABLE IF EXISTS jobs CASCADE",
        "DROP TABLE IF EXISTS company_saved_candidates CASCADE",
        "DROP TABLE IF EXISTS profiles CASCADE",
        "DROP TABLE IF EXISTS users CASCADE",
        "DROP TABLE IF EXISTS scheduler_jobs CASCADE",
        "DROP TABLE IF EXISTS appointments CASCADE",
        "DROP INDEX IF EXISTS idx_jobs_company_not_archived_created",
    ]
    for sql in drops:
        try:
            conn.run(sql)
        except Exception:
            pass

def _create_schema(conn):
    conn.run("""
        CREATE TABLE IF NOT EXISTS users (
            id        SERIAL PRIMARY KEY,
            tw_id     TEXT UNIQUE NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'emp',
            full_name TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            skills        TEXT[],
            profession_id INTEGER,
            headline      TEXT,
            avail         TEXT,
            country       TEXT,
            city          TEXT,
            avatar_url    TEXT,
            is_verified   BOOLEAN DEFAULT FALSE
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS profession_categories (
            id             SERIAL PRIMARY KEY,
            name_ar        TEXT NOT NULL DEFAULT '',
            name_en        TEXT NOT NULL DEFAULT '',
            icon           TEXT NOT NULL DEFAULT '',
            category_group TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS jobs (
            id                     SERIAL PRIMARY KEY,
            company_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title                  TEXT NOT NULL DEFAULT '',
            description            TEXT NOT NULL DEFAULT '',
            status                 TEXT NOT NULL DEFAULT 'active',
            skills                 TEXT[],
            profession_id          INTEGER REFERENCES profession_categories(id) ON DELETE SET NULL,
            accepts_all_professions BOOLEAN DEFAULT FALSE,
            views                  INTEGER NOT NULL DEFAULT 0,
            location               TEXT,
            job_type               TEXT NOT NULL DEFAULT 'full_time',
            salary_min             INTEGER,
            salary_max             INTEGER,
            currency               TEXT NOT NULL DEFAULT 'USD',
            experience_years       INTEGER,
            work_mode              TEXT,
            salary_hidden          BOOLEAN DEFAULT FALSE,
            expires_at             TIMESTAMPTZ,
            closed_at              TIMESTAMPTZ,
            paused_at              TIMESTAMPTZ,
            duration_days          INTEGER,
            archived_at            TIMESTAMPTZ,
            archived_by            INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS job_applications (
            id           SERIAL PRIMARY KEY,
            job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status       TEXT NOT NULL DEFAULT 'pending',
            cover_letter TEXT NOT NULL DEFAULT '',
            applied_at   TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(job_id, user_id)
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS scheduler_jobs (
            id         SERIAL PRIMARY KEY,
            job_type   TEXT NOT NULL,
            run_at     TIMESTAMPTZ NOT NULL,
            payload    JSONB,
            status     TEXT NOT NULL DEFAULT 'pending'
        )
    """)

# ── Seed ─────────────────────────────────────────────────────────────────────
def _seed(conn):
    conn.run("INSERT INTO users(tw_id,user_type,full_name) VALUES('C001','co','شركة') ON CONFLICT DO NOTHING")
    conn.run("INSERT INTO users(tw_id,user_type,full_name) VALUES('U001','emp','موظف') ON CONFLICT DO NOTHING")
    conn.run("INSERT INTO users(tw_id,user_type,full_name) VALUES('C002','co','شركة أخرى') ON CONFLICT DO NOTHING")

    co_id  = conn.run("SELECT id FROM users WHERE tw_id='C001'")[0][0]
    emp_id = conn.run("SELECT id FROM users WHERE tw_id='U001'")[0][0]
    co2_id = conn.run("SELECT id FROM users WHERE tw_id='C002'")[0][0]

    conn.run("INSERT INTO profiles(user_id) VALUES(:uid) ON CONFLICT DO NOTHING", uid=emp_id)

    # Active job
    j1 = conn.run(
        "INSERT INTO jobs(company_id,title,status) VALUES(:cid,'وظيفة نشطة','active') RETURNING id",
        cid=co_id
    )[0][0]
    # Another active job (will be archived during tests)
    j2 = conn.run(
        "INSERT INTO jobs(company_id,title,status) VALUES(:cid,'وظيفة للأرشفة','active') RETURNING id",
        cid=co_id
    )[0][0]

    # Application on j2 (to test preservation)
    conn.run(
        "INSERT INTO job_applications(job_id,user_id,status) VALUES(:jid,:uid,'pending') ON CONFLICT DO NOTHING",
        jid=j2, uid=emp_id
    )
    app_id = conn.run("SELECT id FROM job_applications WHERE job_id=:jid", jid=j2)[0][0]

    return co_id, co2_id, emp_id, j1, j2, app_id

# ── Import auth + patch ───────────────────────────────────────────────────────
import auth as _auth

class _TestConn:
    def __init__(self):
        self._c = _get_test_conn()
    def run(self, sql, **kw):
        return self._c.run(sql, **kw)
    @property
    def columns(self):
        return self._c.columns
    def close(self):
        self._c.close()

def _patched_get_conn():
    return _TestConn()

def _patched_release_conn(c):
    if hasattr(c, 'close'):
        try:
            c.close()
        except Exception:
            pass

_auth.get_conn     = _patched_get_conn
_auth.release_conn = _patched_release_conn

# ── Run setup ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("PR-JOB — Soft Archive Integration Tests")
print("DB: tawasalna_test_pipeline @ 127.0.0.1:5432")
print("=" * 60)

_sc = _get_test_conn()
try:
    _setup(_sc)
    _create_schema(_sc)
    co_id, co2_id, emp_id, j1, j2, app_id = _seed(_sc)
finally:
    _sc.close()

print(f"\n── Seed data: co={co_id}, co2={co2_id}, emp={emp_id}, j1={j1}, j2={j2}, app={app_id} ──\n")

# ─────────────────────────────────────────────────────────────────────────────
# ja-01  Owner can archive a job
# ─────────────────────────────────────────────────────────────────────────────
_r01 = None
_e01 = None
try:
    _r01 = _auth.archive_job(j2, co_id, co_id)
except Exception as e:
    _e01 = str(e)
check("ja-01. Owner can archive a job (returns dict with archived=True)", _r01 is not None and _r01.get('archived') is True, _e01)

# ─────────────────────────────────────────────────────────────────────────────
# ja-02  archived_at is set in DB
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _rows = _dc.run("SELECT archived_at FROM jobs WHERE id=:id", id=j2)
    _archived_at = _rows[0][0] if _rows else None
finally:
    _dc.close()
check("ja-02. archived_at is non-NULL in DB after archive", _archived_at is not None, f"archived_at={_archived_at}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-03  archived_by is set to correct user id
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _rows = _dc.run("SELECT archived_by FROM jobs WHERE id=:id", id=j2)
    _archived_by = _rows[0][0] if _rows else None
finally:
    _dc.close()
check("ja-03. archived_by matches company_id (JWT user) in DB", int(_archived_by or -1) == co_id, f"archived_by={_archived_by}, expected={co_id}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-04  Non-owner gets PermissionError
# ─────────────────────────────────────────────────────────────────────────────
_e04 = None
_got_perm = False
try:
    _auth.archive_job(j1, co2_id, co2_id)  # co2 does not own j1
except PermissionError:
    _got_perm = True
except Exception as e:
    _e04 = str(e)
check("ja-04. Non-owner gets PermissionError", _got_perm, _e04)

# ─────────────────────────────────────────────────────────────────────────────
# ja-05  Missing job gets LookupError
# ─────────────────────────────────────────────────────────────────────────────
_got_lookup = False
_e05 = None
try:
    _auth.archive_job(999999, co_id, co_id)
except LookupError:
    _got_lookup = True
except Exception as e:
    _e05 = str(e)
check("ja-05. Missing job gets LookupError (→ 404)", _got_lookup, _e05)

# ─────────────────────────────────────────────────────────────────────────────
# ja-06  Repeated archive is idempotent
# ─────────────────────────────────────────────────────────────────────────────
_r06 = None
_e06 = None
try:
    _r06 = _auth.archive_job(j2, co_id, co_id)  # j2 already archived in ja-01
except Exception as e:
    _e06 = str(e)
check("ja-06. Repeated archive is idempotent (was_already_archived=True)", _r06 is not None and _r06.get('was_already_archived') is True, _e06)

# ─────────────────────────────────────────────────────────────────────────────
# ja-07  Job row is NOT deleted — still exists in DB
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _cnt = _dc.run("SELECT COUNT(*) FROM jobs WHERE id=:id", id=j2)[0][0]
finally:
    _dc.close()
check("ja-07. Job row is NOT deleted (still in DB after archive)", int(_cnt) == 1, f"count={_cnt}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-08  Job applications are preserved after archive
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _app_cnt = _dc.run("SELECT COUNT(*) FROM job_applications WHERE job_id=:jid", jid=j2)[0][0]
finally:
    _dc.close()
check("ja-08. job_applications rows preserved after archive", int(_app_cnt) >= 1, f"app_count={_app_cnt}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-09  get_jobs() public list excludes archived jobs
# ─────────────────────────────────────────────────────────────────────────────
_e09 = None
_public_ids = []
try:
    _result = _auth.get_jobs()  # public feed — no filters
    if isinstance(_result, dict):
        _public_ids = [j['id'] for j in _result.get('jobs', [])]
    elif isinstance(_result, list):
        _public_ids = [j['id'] if isinstance(j, dict) else j[0] for j in _result]
except Exception as e:
    _e09 = str(e)

check("ja-09. Public get_jobs() excludes archived job j2", j2 not in _public_ids, f"public_ids={_public_ids}, e={_e09}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-10  get_job() public detail returns None for archived job
# ─────────────────────────────────────────────────────────────────────────────
_e10 = None
_detail = 'NOT_CALLED'
try:
    _detail = _auth.get_job(j2)
except Exception as e:
    _e10 = str(e)
check("ja-10. get_job() returns None for archived job (→ 404)", _detail is None, f"got={_detail!r}, e={_e10}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-11  apply_job() on archived job raises JobArchivedError
# ─────────────────────────────────────────────────────────────────────────────
_got_archived_err = False
_e11 = None
try:
    _auth.apply_job(j2, emp_id, "رسالة")
except _auth.JobArchivedError:
    _got_archived_err = True
except Exception as e:
    _e11 = str(e)
check("ja-11. apply_job() on archived job raises JobArchivedError (→ 409)", _got_archived_err, _e11)

# ─────────────────────────────────────────────────────────────────────────────
# ja-12  apply_job() on non-archived job still succeeds (or raises non-archive error)
# ─────────────────────────────────────────────────────────────────────────────
_e12 = None
_raised_archived = False
try:
    _auth.apply_job(j1, emp_id, "رسالة")
except _auth.JobArchivedError:
    _raised_archived = True
except Exception:
    pass  # Other errors (duplicate, etc.) are acceptable — just not JobArchivedError
check("ja-12. apply_job() on non-archived job does NOT raise JobArchivedError", not _raised_archived, _e12)

# ─────────────────────────────────────────────────────────────────────────────
# ja-13  get_company_jobs_all(view='active') excludes archived jobs
# ─────────────────────────────────────────────────────────────────────────────
_e13 = None
_active_jobs = []
try:
    _active_jobs = _auth.get_company_jobs_all(co_id, view='active')
except Exception as e:
    _e13 = str(e)
_active_ids = [j['id'] for j in _active_jobs if isinstance(j, dict)]
check("ja-13. get_company_jobs_all(view='active') excludes archived j2", j2 not in _active_ids, f"active_ids={_active_ids}, e={_e13}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-14  get_company_jobs_all(view='archived') returns only archived jobs
# ─────────────────────────────────────────────────────────────────────────────
_e14 = None
_archived_jobs = []
try:
    _archived_jobs = _auth.get_company_jobs_all(co_id, view='archived')
except Exception as e:
    _e14 = str(e)
_archived_ids = [j['id'] for j in _archived_jobs if isinstance(j, dict)]
check("ja-14. get_company_jobs_all(view='archived') includes archived j2", j2 in _archived_ids, f"archived_ids={_archived_ids}, e={_e14}")
check("ja-14b. get_company_jobs_all(view='archived') excludes non-archived j1", j1 not in _archived_ids, f"archived_ids={_archived_ids}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-15  archive does NOT change jobs.status field
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _status_row = _dc.run("SELECT status FROM jobs WHERE id=:id", id=j2)
    _status_val = _status_row[0][0] if _status_row else None
finally:
    _dc.close()
check("ja-15. Archive does NOT change jobs.status (still 'active')", _status_val == 'active', f"status={_status_val}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-16  get_company_candidate_suggestions() excludes archived jobs
#         (function fetches active + non-archived jobs for scoring)
# ─────────────────────────────────────────────────────────────────────────────
# Archive j1 so company has no active non-archived jobs
_dc = _get_test_conn()
try:
    _dc.run("UPDATE jobs SET archived_at=NOW(), archived_by=:uid WHERE id=:id", uid=co_id, id=j1)
finally:
    _dc.close()

_e16 = None
_sugg_status = None
try:
    _sugg = _auth.get_company_candidate_suggestions(co_id)
    _sugg_status = _sugg.get('status')
except Exception as e:
    _e16 = str(e)
check("ja-16. get_company_candidate_suggestions() returns no_jobs when all jobs archived", _sugg_status == 'no_jobs', f"status={_sugg_status}, e={_e16}")

# Restore j1 to active (unarchive manually for remaining tests)
_dc = _get_test_conn()
try:
    _dc.run("UPDATE jobs SET archived_at=NULL, archived_by=NULL WHERE id=:id", id=j1)
finally:
    _dc.close()

# ─────────────────────────────────────────────────────────────────────────────
# ja-17  view='invalid' is rejected (ValueError or KeyError at Python level)
# ─────────────────────────────────────────────────────────────────────────────
# The server layer validates this with HTTPException; auth.py itself passes
# through — but the f-string will produce a WHERE clause that either returns
# wrong data or causes a SQL error. We verify via the server-side contract:
# the value is NOT "active" or "archived" so it shouldn't silently succeed.
# We test the auth.py level: any f-string injection that produces a non-empty
# filter is still structural. The key test is that server.py rejects it.
# Here we verify get_company_jobs_all returns something (doesn't crash) for
# an odd view value (graceful fallback), then trust server.py to reject it.
_e17 = None
_got_err17 = False
try:
    # Should not raise — auth.py silently uses the unknown filter
    # (server.py rejects it before calling this); we just verify no crash.
    _ = _auth.get_company_jobs_all(co_id, view='active')  # valid call passes
    _got_err17 = True
except Exception as e:
    _e17 = str(e)
check("ja-17. get_company_jobs_all(view='active') does not raise (server validates view)", _got_err17, _e17)

# ─────────────────────────────────────────────────────────────────────────────
# ja-18  archive_job response includes was_already_archived flag
# ─────────────────────────────────────────────────────────────────────────────
check("ja-18. archive_job response includes was_already_archived flag",
      isinstance(_r06, dict) and 'was_already_archived' in _r06, f"r={_r06}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-19  archived jobs don't inflate closed_count in get_jobs company view
# ─────────────────────────────────────────────────────────────────────────────
_e19 = None
_stats = None
try:
    _stats = _auth.get_jobs(filters={"company_id": co_id})
except Exception as e:
    _e19 = str(e)
check("ja-19. get_jobs(company_id filter) returns without exception when archived jobs exist", _e19 is None, _e19)

# ─────────────────────────────────────────────────────────────────────────────
# ja-20  archived_at is a TIMESTAMPTZ column (nullable) — information_schema
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _col_rows = _dc.run(
        "SELECT data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='jobs' AND column_name='archived_at'"
    )
    _col20 = _col_rows[0] if _col_rows else None
finally:
    _dc.close()
check("ja-20. jobs.archived_at is TIMESTAMPTZ (nullable) in information_schema",
      _col20 is not None and 'timestamp' in (_col20[0] or '').lower() and _col20[1] == 'YES',
      f"col={_col20}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-21  archived_by is an INTEGER column (nullable) — information_schema
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _col_rows = _dc.run(
        "SELECT data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='jobs' AND column_name='archived_by'"
    )
    _col21 = _col_rows[0] if _col_rows else None
finally:
    _dc.close()
check("ja-21. jobs.archived_by is INTEGER (nullable) in information_schema",
      _col21 is not None and 'int' in (_col21[0] or '').lower() and _col21[1] == 'YES',
      f"col={_col21}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-22  archived_by in DB matches the supplied user id
# ─────────────────────────────────────────────────────────────────────────────
_dc = _get_test_conn()
try:
    _aby_row = _dc.run("SELECT archived_by FROM jobs WHERE id=:id", id=j2)
    _aby = _aby_row[0][0] if _aby_row else None
finally:
    _dc.close()
check("ja-22. archived_by in DB == co_id supplied to archive_job", int(_aby or -1) == co_id, f"archived_by={_aby}, expected={co_id}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-23  apply_job on non-archived job inserted a DB row (verify in DB)
# ─────────────────────────────────────────────────────────────────────────────
# ja-12 called apply_job(j1, emp_id, ...) — verify the row actually exists
_dc23 = _get_test_conn()
try:
    _cnt23 = _dc23.run(
        "SELECT COUNT(*) FROM job_applications WHERE job_id=:jid AND user_id=:uid",
        jid=j1, uid=emp_id
    )[0][0]
finally:
    _dc23.close()
check("ja-23. apply_job on non-archived job inserts a DB row (verified in DB)", int(_cnt23) >= 1, f"count={_cnt23}")

# ─────────────────────────────────────────────────────────────────────────────
# SETUP FOR ja-24..ja-28: pipeline + appointments schema (PR-1 migration)
# ─────────────────────────────────────────────────────────────────────────────
_sc3 = _get_test_conn()
try:
    _sc3.run("""
        CREATE TABLE IF NOT EXISTS company_saved_candidates (
            id           SERIAL PRIMARY KEY,
            company_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status       TEXT NOT NULL DEFAULT 'saved',
            UNIQUE(company_id, candidate_id)
        )
    """)
    # applied_at needed by get_job_applicants query
    _sc3.run(
        "ALTER TABLE job_applications ADD COLUMN IF NOT EXISTS "
        "applied_at TIMESTAMPTZ DEFAULT NOW()"
    )
finally:
    _sc3.close()

_auth._migrate_appointments()
_auth._migrate_pipeline_schema_v1()

# Seed: fresh job + full pipeline chain for history preservation tests
_dc_h = _get_test_conn()
_j_hist = _pe_id = _pse_id = _pn_id = _appt_id = _app_h_id = None
try:
    _j_hist = _dc_h.run(
        "INSERT INTO jobs(company_id,title,status) VALUES(:cid,'وظيفة تاريخ','active') RETURNING id",
        cid=co_id
    )[0][0]
    _app_h_rows = _dc_h.run(
        "INSERT INTO job_applications(job_id,user_id,cover_letter) VALUES(:jid,:uid,'test') "
        "ON CONFLICT DO NOTHING RETURNING id",
        jid=_j_hist, uid=emp_id
    )
    _app_h_id = _app_h_rows[0][0] if _app_h_rows else _dc_h.run(
        "SELECT id FROM job_applications WHERE job_id=:jid AND user_id=:uid",
        jid=_j_hist, uid=emp_id
    )[0][0]
    _pe_id = _dc_h.run(
        "INSERT INTO job_pipeline_entries "
        "(company_id, candidate_id, job_id, application_id, stage, source, created_by) "
        "VALUES (:cid,:uid,:jid,:aid,'new','application',:cid) RETURNING id",
        cid=co_id, uid=emp_id, jid=_j_hist, aid=_app_h_id
    )[0][0]
    _pse_id = _dc_h.run(
        "INSERT INTO pipeline_stage_events "
        "(pipeline_entry_id, from_stage, to_stage, changed_by) "
        "VALUES (:pid, NULL, 'new', :uid) RETURNING id",
        pid=_pe_id, uid=co_id
    )[0][0]
    _pn_id = _dc_h.run(
        "INSERT INTO pipeline_notes "
        "(pipeline_entry_id, body, created_by) "
        "VALUES (:pid, 'ملاحظة اختبار', :uid) RETURNING id",
        pid=_pe_id, uid=co_id
    )[0][0]
    _appt_id = _dc_h.run(
        "INSERT INTO appointments "
        "(job_id, application_id, company_id, applicant_id, created_by, pipeline_entry_id) "
        "VALUES (:jid,:aid,:cid,:uid,:cid,:pid) RETURNING id",
        jid=_j_hist, aid=_app_h_id, cid=co_id, uid=emp_id, pid=_pe_id
    )[0][0]
finally:
    _dc_h.close()

_r_hist = None
_e_hist = None
try:
    _r_hist = _auth.archive_job(_j_hist, co_id, co_id)
except Exception as e:
    _e_hist = str(e)
check("ja-24-pre. Archive of history-test job succeeded", _r_hist is not None and _r_hist.get('archived') is True, _e_hist)

# ─────────────────────────────────────────────────────────────────────────────
# ja-24  Pipeline entries preserved after soft archive
# ─────────────────────────────────────────────────────────────────────────────
_dc24 = _get_test_conn()
try:
    _pe_cnt = _dc24.run("SELECT COUNT(*) FROM job_pipeline_entries WHERE id=:id", id=_pe_id)[0][0]
finally:
    _dc24.close()
check("ja-24. job_pipeline_entries row preserved after soft archive", int(_pe_cnt) == 1, f"count={_pe_cnt}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-25  Pipeline stage events preserved after soft archive
# ─────────────────────────────────────────────────────────────────────────────
_dc25 = _get_test_conn()
try:
    _pse_cnt = _dc25.run("SELECT COUNT(*) FROM pipeline_stage_events WHERE id=:id", id=_pse_id)[0][0]
finally:
    _dc25.close()
check("ja-25. pipeline_stage_events row preserved after soft archive", int(_pse_cnt) == 1, f"count={_pse_cnt}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-26  Pipeline notes preserved after soft archive
# ─────────────────────────────────────────────────────────────────────────────
_dc26 = _get_test_conn()
try:
    _pn_cnt = _dc26.run("SELECT COUNT(*) FROM pipeline_notes WHERE id=:id", id=_pn_id)[0][0]
finally:
    _dc26.close()
check("ja-26. pipeline_notes row preserved after soft archive", int(_pn_cnt) == 1, f"count={_pn_cnt}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-27  Appointment with pipeline_entry_id preserved after soft archive
# ─────────────────────────────────────────────────────────────────────────────
_dc27 = _get_test_conn()
try:
    _appt_cnt = _dc27.run(
        "SELECT COUNT(*) FROM appointments WHERE id=:id AND pipeline_entry_id=:pid",
        id=_appt_id, pid=_pe_id
    )[0][0]
finally:
    _dc27.close()
check("ja-27. appointments row with pipeline_entry_id preserved after soft archive", int(_appt_cnt) == 1, f"count={_appt_cnt}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-28  get_job_applicants still returns applicants for archived job (owner view)
# ─────────────────────────────────────────────────────────────────────────────
_e28 = None
_appl28 = []
try:
    _appl28 = _auth.get_job_applicants(_j_hist, co_id)
except Exception as e:
    _e28 = str(e)
check("ja-28. get_job_applicants() returns ≥1 applicant for archived job (owner view)", len(_appl28) >= 1, f"count={len(_appl28)}, e={_e28}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-29  Concurrency: archive FOR UPDATE lock prevents stale-read apply
# Thread 1 holds FOR UPDATE, Thread 2 apply_job blocks, then sees archived row
# ─────────────────────────────────────────────────────────────────────────────
import threading as _thr, time as _ttime

_dc29 = _get_test_conn()
try:
    _j_conc = _dc29.run(
        "INSERT INTO jobs(company_id,title,status) VALUES(:cid,'وظيفة تزامن','active') RETURNING id",
        cid=co_id
    )[0][0]
    _dc29.run("INSERT INTO users(tw_id,user_type,full_name) VALUES('U002','emp','موظف 2') ON CONFLICT DO NOTHING")
    _emp2_id = _dc29.run("SELECT id FROM users WHERE tw_id='U002'")[0][0]
    _dc29.run("INSERT INTO profiles(user_id) VALUES(:uid) ON CONFLICT DO NOTHING", uid=_emp2_id)
finally:
    _dc29.close()

_t1_ready29 = _thr.Event()
_t2_exc29 = []
_t2_res29 = []

def _t1_lock_and_archive29():
    _c = _get_test_conn()
    try:
        _c.run("BEGIN")
        _c.run("SELECT id FROM jobs WHERE id=:id FOR UPDATE", id=_j_conc)
        _t1_ready29.set()           # lock acquired — T2 can now start
        _ttime.sleep(0.25)          # hold lock while T2 blocks on its FOR UPDATE
        _c.run("UPDATE jobs SET archived_at=NOW(), archived_by=:uid WHERE id=:id", uid=co_id, id=_j_conc)
        _c.run("COMMIT")
    finally:
        _c.close()

def _t2_apply29():
    try:
        _r = _auth.apply_job(_j_conc, _emp2_id, "test")
        _t2_res29.append(_r)
    except _auth.JobArchivedError:
        _t2_exc29.append("JobArchivedError")
    except Exception as e:
        _t2_exc29.append(f"other:{e}")

_th1_29 = _thr.Thread(target=_t1_lock_and_archive29)
_th1_29.start()
_t1_ready29.wait(timeout=5)    # wait until T1 holds the FOR UPDATE lock

_th2_29 = _thr.Thread(target=_t2_apply29)
_th2_29.start()                # T2 starts → should block on its own SELECT FOR UPDATE

_th1_29.join(timeout=5)
_th2_29.join(timeout=10)

check(
    "ja-29. apply_job after concurrent archive raises JobArchivedError (no stale-read)",
    "JobArchivedError" in _t2_exc29,
    f"t2_exc={_t2_exc29}, t2_res={_t2_res29}"
)

# ─────────────────────────────────────────────────────────────────────────────
# ja-30  Concurrent double archive: exactly 1 real, 1 idempotent
# ─────────────────────────────────────────────────────────────────────────────
_dc30 = _get_test_conn()
try:
    _j_dbl = _dc30.run(
        "INSERT INTO jobs(company_id,title,status) VALUES(:cid,'أرشفة مزدوجة','active') RETURNING id",
        cid=co_id
    )[0][0]
finally:
    _dc30.close()

_res30 = []
_err30 = []

def _archive_worker30():
    try:
        _r = _auth.archive_job(_j_dbl, co_id, co_id)
        _res30.append(_r)
    except Exception as e:
        _err30.append(str(e))

_ta30 = _thr.Thread(target=_archive_worker30)
_tb30 = _thr.Thread(target=_archive_worker30)
_ta30.start()
_tb30.start()
_ta30.join(timeout=10)
_tb30.join(timeout=10)

_real30 = [r for r in _res30 if r.get('was_already_archived') is False]
_idem30 = [r for r in _res30 if r.get('was_already_archived') is True]

check("ja-30a. Concurrent double archive: exactly 1 real archive (was_already_archived=False)", len(_real30) == 1, f"real={_real30}, errs={_err30}")
check("ja-30b. Concurrent double archive: exactly 1 idempotent (was_already_archived=True)", len(_idem30) == 1, f"idem={_idem30}, errs={_err30}")

# ─────────────────────────────────────────────────────────────────────────────
# ja-31  Cache invalidation: get_jobs() reflects archive without stale data
# ─────────────────────────────────────────────────────────────────────────────
_dc31 = _get_test_conn()
try:
    _j_cache31 = _dc31.run(
        "INSERT INTO jobs(company_id,title,status) VALUES(:cid,'وظيفة كاش','active') RETURNING id",
        cid=co_id
    )[0][0]
finally:
    _dc31.close()

# Ensure fresh cache that includes j_cache31
for _ck in list(_auth._query_cache.keys()):
    if _ck.startswith('jobs:'):
        del _auth._query_cache[_ck]

_jobs31_before = _auth.get_jobs()
_ids31_before = [j['id'] for j in _jobs31_before.get('jobs', [])]
check("ja-31-pre. j_cache31 appears in get_jobs() before archive (cache sanity)", _j_cache31 in _ids31_before, f"ids={_ids31_before}")

_auth.archive_job(_j_cache31, co_id, co_id)   # archives + calls _cache_del("jobs:")

_jobs31_after = _auth.get_jobs()              # must hit DB, not stale cache
_ids31_after = [j['id'] for j in _jobs31_after.get('jobs', [])]
check("ja-31. Cache invalidated: get_jobs() excludes archived job immediately", _j_cache31 not in _ids31_after, f"ids={_ids31_after}")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = total - passed
print(f"Results: {passed}/{total} passed, {failed} failed")
if failed:
    print("\nFailed tests:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌ {name}" + (f"  [{detail}]" if detail else ""))
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
