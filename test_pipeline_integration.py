"""
PR-1 Integration Tests — Employment Pipeline Schema
Requires a live PostgreSQL test database (NOT production).

Connection: 127.0.0.1:5432 / tawasalna_test_pipeline / tawasalna_test_user
Run: python test_pipeline_integration.py

Tests verify that:
  - Migration runs once (first time)
  - Migration is idempotent (second time, no error)
  - Tables/columns exist in information_schema
  - CHECK constraints accept/reject correct values
  - UNIQUE(company_id, candidate_id, job_id) enforced
  - migration_source_key allows multiple NULLs, rejects duplicate non-NULL
  - CASCADE deletes work (company/candidate deletion removes pipeline entries)
  - RESTRICT on job_id blocks job deletion
  - SET NULL on application_id (application deletion → NULL)
  - SET NULL on appointments.pipeline_entry_id (entry deletion → NULL)
  - application_id: no partial UNIQUE verified via pg_indexes catalog + functional test
    (same non-NULL application_id in two entries with different company/candidate/job triples)
  - save_source CHECK: approved (applicant/suggestion/manual/legacy_unknown/NULL); rejected (profile/application/unknown)
  - jobs.archived_at / archived_by: prerequisites table omits them; migration must add them
  - body CHECK rejects empty/whitespace-only strings in both note tables
  - Exit code: 0 on all pass, 1 on any failure
"""

import sys, os, time

# ── Connection ────────────────────────────────────────────────────────────────
TEST_DB_URL = "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline"
os.environ['SUPABASE_DB_URL'] = TEST_DB_URL

# Patch pg8000 to use the test DB (auth.get_conn reads SUPABASE_DB_URL at call time)
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
    print(f'{marker} {status}  {name}{suffix}')

# ── Setup: tear down + recreate test schema ───────────────────────────────────
def _setup(conn):
    """Drop all test tables so the migration runs fresh."""
    drops = [
        "DROP TABLE IF EXISTS appointments CASCADE",
        "DROP TABLE IF EXISTS pipeline_notes CASCADE",
        "DROP TABLE IF EXISTS pipeline_stage_events CASCADE",
        "DROP TABLE IF EXISTS candidate_bank_notes CASCADE",
        "DROP TABLE IF EXISTS job_pipeline_entries CASCADE",
        "DROP TABLE IF EXISTS job_applications CASCADE",
        "DROP TABLE IF EXISTS jobs CASCADE",
        "DROP TABLE IF EXISTS company_saved_candidates CASCADE",
        "DROP TABLE IF EXISTS users CASCADE",
        "DROP TABLE IF EXISTS scheduler_jobs CASCADE",
        # Remove indexes that migration would create on jobs table
        "DROP INDEX IF EXISTS idx_jobs_company_not_archived_created",
    ]
    for sql in drops:
        try:
            conn.run(sql)
        except Exception:
            pass

def _create_prerequisites(conn):
    """Create minimal prerequisite tables (users, jobs, job_applications, company_saved_candidates, appointments)."""
    conn.run("""
        CREATE TABLE IF NOT EXISTS users (
            id        SERIAL PRIMARY KEY,
            tw_id     TEXT UNIQUE NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'emp'
        )
    """)
    # Deliberately created WITHOUT archived_at / archived_by so the migration
    # can prove it actually adds them via ADD COLUMN IF NOT EXISTS.
    conn.run("""
        CREATE TABLE IF NOT EXISTS jobs (
            id         SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title      TEXT NOT NULL DEFAULT '',
            status     TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS job_applications (
            id         SERIAL PRIMARY KEY,
            job_id     INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status     TEXT NOT NULL DEFAULT 'pending'
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS company_saved_candidates (
            id           BIGSERIAL PRIMARY KEY,
            company_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status       TEXT NOT NULL DEFAULT 'saved',
            CONSTRAINT uq_saved_candidate UNIQUE (company_id, candidate_id)
        )
    """)
    conn.run("""
        CREATE TABLE IF NOT EXISTS appointments (
            id           SERIAL PRIMARY KEY,
            company_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            applicant_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_by   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
        )
    """)

# ── Seed data helpers ─────────────────────────────────────────────────────────
def _seed(conn):
    """Insert minimal rows: 3 users, 1 job, 1 application."""
    conn.run("INSERT INTO users(tw_id, user_type) VALUES ('C001','co') ON CONFLICT DO NOTHING")
    conn.run("INSERT INTO users(tw_id, user_type) VALUES ('U001','emp') ON CONFLICT DO NOTHING")
    conn.run("INSERT INTO users(tw_id, user_type) VALUES ('U002','emp') ON CONFLICT DO NOTHING")
    rows = conn.run("SELECT id FROM users WHERE tw_id='C001'")
    co_id = rows[0][0]
    rows = conn.run("SELECT id FROM users WHERE tw_id='U001'")
    u1_id = rows[0][0]
    rows = conn.run("SELECT id FROM users WHERE tw_id='U002'")
    u2_id = rows[0][0]
    conn.run(
        "INSERT INTO jobs(company_id, title) VALUES (:cid, 'مهندس برمجيات') RETURNING id",
        cid=co_id
    )
    rows = conn.run("SELECT id FROM jobs WHERE company_id=:cid", cid=co_id)
    j_id = rows[0][0]
    conn.run(
        "INSERT INTO job_applications(job_id, user_id) VALUES (:jid, :uid) RETURNING id",
        jid=j_id, uid=u1_id
    )
    rows = conn.run("SELECT id FROM job_applications WHERE job_id=:jid", jid=j_id)
    app_id = rows[0][0]
    return co_id, u1_id, u2_id, j_id, app_id

# ── Import auth and patch connection ─────────────────────────────────────────
# auth.py uses get_conn() → we patch it to use our test connection directly.
import types as _types
# Stub out anything that might fail on import
if 'server' not in sys.modules:
    import importlib, unittest.mock as _mock
    with _mock.patch.dict(os.environ, {'SUPABASE_DB_URL': TEST_DB_URL}):
        pass  # just ensure env is set

import auth as _auth

print("=" * 60)
print("PR-1 Pipeline Schema — Integration Tests")
print(f"DB: tawasalna_test_pipeline @ 127.0.0.1:5432")
print("=" * 60)

# ── it-01: Migration runs first time ─────────────────────────────────────────
print("\n── Schema Setup ──")
_conn = _get_test_conn()
try:
    _setup(_conn)
    _create_prerequisites(_conn)
finally:
    _conn.close()

# Patch auth to use test connection pool
_test_conns = []

class _TestConnWrapper:
    def __init__(self):
        self._c = _get_test_conn()
    def run(self, sql, **kw):
        return self._c.run(sql, **kw)
    @property
    def columns(self):
        return self._c.columns
    def close(self):
        self._c.close()

_active_conn = None

def _patched_get_conn():
    global _active_conn
    _active_conn = _TestConnWrapper()
    return _active_conn

def _patched_release_conn(c):
    if hasattr(c, 'close'):
        try:
            c.close()
        except Exception:
            pass

_orig_get  = _auth.get_conn
_orig_rel  = _auth.release_conn
_auth.get_conn     = _patched_get_conn
_auth.release_conn = _patched_release_conn

_run1_ok = False
_run1_err = None
try:
    _auth._migrate_pipeline_schema_v1()
    _run1_ok = True
except Exception as _e:
    _run1_err = str(_e)

check("it-01. Migration runs first time without error", _run1_ok, _run1_err)

# ── it-02: Idempotency — run migration a second time ─────────────────────────
_run2_ok = False
_run2_err = None
try:
    _auth._migrate_pipeline_schema_v1()
    _run2_ok = True
except Exception as _e:
    _run2_err = str(_e)

check("it-02. Migration is idempotent (second run, no error)", _run2_ok, _run2_err)

# ── it-03: Tables exist in information_schema ────────────────────────────────
print("\n── Schema Verification ──")
_vc = _get_test_conn()
try:
    def _table_exists(name):
        rows = _vc.run(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=:n", n=name
        )
        return bool(rows)

    def _col_exists(tbl, col):
        rows = _vc.run(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c",
            t=tbl, c=col
        )
        return bool(rows)

    def _index_exists(name):
        rows = _vc.run(
            "SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n", n=name
        )
        return bool(rows)

    def _constraint_exists(tbl, name):
        rows = _vc.run(
            "SELECT 1 FROM pg_constraint c "
            "JOIN pg_class r ON c.conrelid=r.oid "
            "WHERE r.relname=:t AND c.conname=:n",
            t=tbl, n=name
        )
        return bool(rows)

    check("it-03a. Table job_pipeline_entries exists", _table_exists('job_pipeline_entries'))
    check("it-03b. Table pipeline_stage_events exists", _table_exists('pipeline_stage_events'))
    check("it-03c. Table pipeline_notes exists",        _table_exists('pipeline_notes'))
    check("it-03d. Table candidate_bank_notes exists",  _table_exists('candidate_bank_notes'))

    # Column checks
    check("it-03e. job_pipeline_entries.stage_updated_at exists",
        _col_exists('job_pipeline_entries', 'stage_updated_at'))
    check("it-03f. job_pipeline_entries.job_title_snapshot exists",
        _col_exists('job_pipeline_entries', 'job_title_snapshot'))
    check("it-03g. job_pipeline_entries.archived_at exists",
        _col_exists('job_pipeline_entries', 'archived_at'))
    check("it-03h. pipeline_stage_events.reason exists (not note)",
        _col_exists('pipeline_stage_events', 'reason') and
        not _col_exists('pipeline_stage_events', 'note'))
    check("it-03i. pipeline_notes.created_by exists; no company_id/author_id/deleted_by",
        _col_exists('pipeline_notes', 'created_by') and
        not _col_exists('pipeline_notes', 'company_id') and
        not _col_exists('pipeline_notes', 'author_id') and
        not _col_exists('pipeline_notes', 'deleted_by'))
    check("it-03j. candidate_bank_notes.created_by exists; no author_id/deleted_by",
        _col_exists('candidate_bank_notes', 'created_by') and
        not _col_exists('candidate_bank_notes', 'author_id') and
        not _col_exists('candidate_bank_notes', 'deleted_by'))
    check("it-03k. company_saved_candidates new columns exist",
        _col_exists('company_saved_candidates', 'rating') and
        _col_exists('company_saved_candidates', 'priority') and
        _col_exists('company_saved_candidates', 'tags') and
        _col_exists('company_saved_candidates', 'follow_up_at') and
        _col_exists('company_saved_candidates', 'save_source'))
    check("it-03l. appointments.pipeline_entry_id exists",
        _col_exists('appointments', 'pipeline_entry_id'))

    # Index checks
    check("it-03m. idx_jobs_company_not_archived_created exists (new index name)",
        _index_exists('idx_jobs_company_not_archived_created'))
    check("it-03n. idx_jobs_not_archived does NOT exist (replaced)",
        not _index_exists('idx_jobs_not_archived'))

    # Constraint checks
    check("it-03o. ck_pn_body_nonempty exists on pipeline_notes",
        _constraint_exists('pipeline_notes', 'ck_pn_body_nonempty'))
    check("it-03p. ck_cbn_body_nonempty exists on candidate_bank_notes",
        _constraint_exists('candidate_bank_notes', 'ck_cbn_body_nonempty'))
    # Archive columns: prerequisites table did NOT include them — migration must add them
    check("it-03q. jobs.archived_at added by migration (not in prerequisites)",
        _col_exists('jobs', 'archived_at'))
    check("it-03r. jobs.archived_by added by migration (not in prerequisites)",
        _col_exists('jobs', 'archived_by'))

finally:
    _vc.close()

# ── it-04 / it-05: CHECK constraints — stage and source values ───────────────
print("\n── CHECK Constraints ──")
_cc = _get_test_conn()
try:
    # Insert test user/company/job for FK refs
    _cc.run("INSERT INTO users(tw_id,user_type) VALUES('C_CHK','co') ON CONFLICT DO NOTHING")
    _cc.run("INSERT INTO users(tw_id,user_type) VALUES('U_CHK','emp') ON CONFLICT DO NOTHING")
    _co_chk = _cc.run("SELECT id FROM users WHERE tw_id='C_CHK'")[0][0]
    _u_chk  = _cc.run("SELECT id FROM users WHERE tw_id='U_CHK'")[0][0]
    _cc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'CHK Job') RETURNING id", c=_co_chk)
    _j_chk  = _cc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_chk)[0][0]

    def _try_insert_entry(stage, source):
        try:
            _cc.run(
                "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
                " VALUES(:c,:u,:j,:s,:src)",
                c=_co_chk, u=_u_chk, j=_j_chk, s=stage, src=source
            )
            _cc.run(
                "DELETE FROM job_pipeline_entries WHERE company_id=:c AND candidate_id=:u AND job_id=:j",
                c=_co_chk, u=_u_chk, j=_j_chk
            )
            return True
        except Exception:
            return False

    # Approved stages — all 9 must succeed
    approved_stages = ['new','reviewing','shortlisted','contacted','interview','offer','hired','rejected','withdrawn']
    for _s in approved_stages:
        check(f"it-04a. stage='{_s}' accepted", _try_insert_entry(_s, 'application'))

    # Rejected stage values
    for _bad in ['sourced','screening','assessment','pending','open']:
        check(f"it-04b. stage='{_bad}' rejected", not _try_insert_entry(_bad, 'application'))

    # Approved sources — all 5 must succeed
    approved_sources = ['application','company_add','bank_link','migration','legacy_unknown']
    for _src in approved_sources:
        check(f"it-05a. source='{_src}' accepted", _try_insert_entry('new', _src))

    # Rejected source values
    for _bad_src in ['applicant','suggestion','manual','profile','unknown']:
        check(f"it-05b. source='{_bad_src}' rejected", not _try_insert_entry('new', _bad_src))

finally:
    _cc.close()

# ── it-06: priority CHECK — low/medium/high only ─────────────────────────────
print("\n── priority / rating CHECK ──")
_pc = _get_test_conn()
try:
    _pc.run("INSERT INTO users(tw_id,user_type) VALUES('C_PRI','co') ON CONFLICT DO NOTHING")
    _pc.run("INSERT INTO users(tw_id,user_type) VALUES('U_PRI','emp') ON CONFLICT DO NOTHING")
    _co_pri = _pc.run("SELECT id FROM users WHERE tw_id='C_PRI'")[0][0]
    _u_pri  = _pc.run("SELECT id FROM users WHERE tw_id='U_PRI'")[0][0]
    # Ensure saved row exists for UPDATE test
    _pc.run(
        "INSERT INTO company_saved_candidates(company_id,candidate_id) "
        "VALUES(:c,:u) ON CONFLICT DO NOTHING",
        c=_co_pri, u=_u_pri
    )

    def _try_priority(val):
        try:
            _pc.run(
                "UPDATE company_saved_candidates SET priority=:v "
                "WHERE company_id=:c AND candidate_id=:u",
                v=val, c=_co_pri, u=_u_pri
            )
            _pc.run(
                "UPDATE company_saved_candidates SET priority=NULL "
                "WHERE company_id=:c AND candidate_id=:u",
                c=_co_pri, u=_u_pri
            )
            return True
        except Exception:
            return False

    def _try_rating(val):
        try:
            _pc.run(
                "UPDATE company_saved_candidates SET rating=:v "
                "WHERE company_id=:c AND candidate_id=:u",
                v=val, c=_co_pri, u=_u_pri
            )
            _pc.run(
                "UPDATE company_saved_candidates SET rating=NULL "
                "WHERE company_id=:c AND candidate_id=:u",
                c=_co_pri, u=_u_pri
            )
            return True
        except Exception:
            return False

    check("it-06a. priority='low' accepted",    _try_priority('low'))
    check("it-06b. priority='medium' accepted",  _try_priority('medium'))
    check("it-06c. priority='high' accepted",    _try_priority('high'))
    check("it-06d. priority='normal' rejected",  not _try_priority('normal'))
    check("it-06e. priority='urgent' rejected",  not _try_priority('urgent'))
    check("it-06f. priority=NULL accepted",       _try_priority(None))

    check("it-06g. rating=1 accepted",   _try_rating(1))
    check("it-06h. rating=5 accepted",   _try_rating(5))
    check("it-06i. rating=0 rejected",   not _try_rating(0))
    check("it-06j. rating=6 rejected",   not _try_rating(6))
    check("it-06k. rating=NULL accepted", _try_rating(None))

finally:
    _pc.close()

# ── it-06l–s: save_source CHECK ──────────────────────────────────────────────
print("\n── save_source CHECK ──")
_ssc = _get_test_conn()
try:
    _ssc.run("INSERT INTO users(tw_id,user_type) VALUES('C_SS','co') ON CONFLICT DO NOTHING")
    _ssc.run("INSERT INTO users(tw_id,user_type) VALUES('U_SS','emp') ON CONFLICT DO NOTHING")
    _co_ss = _ssc.run("SELECT id FROM users WHERE tw_id='C_SS'")[0][0]
    _u_ss  = _ssc.run("SELECT id FROM users WHERE tw_id='U_SS'")[0][0]
    _ssc.run(
        "INSERT INTO company_saved_candidates(company_id,candidate_id) "
        "VALUES(:c,:u) ON CONFLICT DO NOTHING",
        c=_co_ss, u=_u_ss
    )

    def _try_save_source(val):
        try:
            _ssc.run(
                "UPDATE company_saved_candidates SET save_source=:v "
                "WHERE company_id=:c AND candidate_id=:u",
                v=val, c=_co_ss, u=_u_ss
            )
            _ssc.run(
                "UPDATE company_saved_candidates SET save_source=NULL "
                "WHERE company_id=:c AND candidate_id=:u",
                c=_co_ss, u=_u_ss
            )
            return True
        except Exception:
            return False

    check("it-06l. save_source='applicant' accepted",      _try_save_source('applicant'))
    check("it-06m. save_source='suggestion' accepted",     _try_save_source('suggestion'))
    check("it-06n. save_source='manual' accepted",         _try_save_source('manual'))
    check("it-06o. save_source='legacy_unknown' accepted", _try_save_source('legacy_unknown'))
    check("it-06p. save_source=NULL accepted",             _try_save_source(None))
    check("it-06q. save_source='profile' rejected",        not _try_save_source('profile'))
    check("it-06r. save_source='application' rejected",    not _try_save_source('application'))
    check("it-06s. save_source='unknown' rejected",        not _try_save_source('unknown'))
finally:
    _ssc.close()

# ── it-07: body CHECK — empty/whitespace rejected ────────────────────────────
print("\n── body NOT empty CHECK ──")
_bc = _get_test_conn()
try:
    # Need a pipeline entry for pipeline_notes FK
    _bc.run("INSERT INTO users(tw_id,user_type) VALUES('C_BODY','co') ON CONFLICT DO NOTHING")
    _bc.run("INSERT INTO users(tw_id,user_type) VALUES('U_BODY','emp') ON CONFLICT DO NOTHING")
    _co_b = _bc.run("SELECT id FROM users WHERE tw_id='C_BODY'")[0][0]
    _u_b  = _bc.run("SELECT id FROM users WHERE tw_id='U_BODY'")[0][0]
    _bc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'Body Job') RETURNING id", c=_co_b)
    _j_b = _bc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_b)[0][0]
    _bc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
        " VALUES(:c,:u,:j,'new','application')",
        c=_co_b, u=_u_b, j=_j_b
    )
    _pe_b = _bc.run(
        "SELECT id FROM job_pipeline_entries WHERE company_id=:c AND candidate_id=:u AND job_id=:j",
        c=_co_b, u=_u_b, j=_j_b
    )[0][0]

    def _try_pn(body):
        try:
            _bc.run(
                "INSERT INTO pipeline_notes(pipeline_entry_id, body) VALUES(:pe, :b)",
                pe=_pe_b, b=body
            )
            _bc.run("DELETE FROM pipeline_notes WHERE pipeline_entry_id=:pe", pe=_pe_b)
            return True
        except Exception:
            return False

    def _try_cbn(body):
        try:
            _bc.run(
                "INSERT INTO candidate_bank_notes(company_id,candidate_id,body) VALUES(:c,:u,:b)",
                c=_co_b, u=_u_b, b=body
            )
            _bc.run(
                "DELETE FROM candidate_bank_notes WHERE company_id=:c AND candidate_id=:u",
                c=_co_b, u=_u_b
            )
            return True
        except Exception:
            return False

    check("it-07a. pipeline_notes: non-empty body accepted",       _try_pn('ملاحظة مهمة'))
    check("it-07b. pipeline_notes: empty string '' rejected",       not _try_pn(''))
    check("it-07c. pipeline_notes: spaces-only '   ' rejected",    not _try_pn('   '))
    check("it-07d. candidate_bank_notes: non-empty body accepted",  _try_cbn('ملاحظة عن المرشح'))
    check("it-07e. candidate_bank_notes: empty string '' rejected", not _try_cbn(''))
    check("it-07f. candidate_bank_notes: spaces-only '   ' rejected", not _try_cbn('   '))

finally:
    _bc.close()

# ── it-08: UNIQUE(company_id, candidate_id, job_id) ─────────────────────────
print("\n── UNIQUE / NULL Constraints ──")
_uc = _get_test_conn()
try:
    _uc.run("INSERT INTO users(tw_id,user_type) VALUES('C_UNQ','co') ON CONFLICT DO NOTHING")
    _uc.run("INSERT INTO users(tw_id,user_type) VALUES('U_UNQ','emp') ON CONFLICT DO NOTHING")
    _co_u = _uc.run("SELECT id FROM users WHERE tw_id='C_UNQ'")[0][0]
    _u_u  = _uc.run("SELECT id FROM users WHERE tw_id='U_UNQ'")[0][0]
    _uc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'UNQ Job') RETURNING id", c=_co_u)
    _j_u = _uc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_u)[0][0]

    # First insert succeeds
    _uc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
        " VALUES(:c,:u,:j,'new','application')",
        c=_co_u, u=_u_u, j=_j_u
    )
    # Duplicate must fail
    _dup_ok = False
    try:
        _uc.run(
            "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
            " VALUES(:c,:u,:j,'reviewing','company_add')",
            c=_co_u, u=_u_u, j=_j_u
        )
        _dup_ok = True
    except Exception:
        pass
    check("it-08a. UNIQUE(company,candidate,job) rejects duplicate", not _dup_ok)

    # application_id allows multiple NULLs (no partial unique)
    _uc.run("INSERT INTO users(tw_id,user_type) VALUES('U_UNQ2','emp') ON CONFLICT DO NOTHING")
    _u_u2 = _uc.run("SELECT id FROM users WHERE tw_id='U_UNQ2'")[0][0]
    _null_ok = True
    try:
        _uc.run(
            "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source,application_id)"
            " VALUES(:c,:u2,:j,'new','application',NULL)",
            c=_co_u, u2=_u_u2, j=_j_u
        )
    except Exception as _e:
        _null_ok = False
    check("it-08b. application_id allows multiple NULLs (no partial unique)", _null_ok)

    # Catalog check: verify pg_indexes has no UNIQUE index on application_id alone
    _no_apid_unique_idx = True
    try:
        _apid_idx_rows = _uc.run(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename='job_pipeline_entries' "
            "AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%application_id%'"
        )
        for _row in (_apid_idx_rows or []):
            _idef = _row[0].lower()
            # A partial UNIQUE on application_id alone would NOT contain the three-column triple
            if 'company_id' not in _idef and 'candidate_id' not in _idef and 'job_id' not in _idef:
                _no_apid_unique_idx = False
    except Exception:
        _no_apid_unique_idx = False
    check("it-08b-catalog. No UNIQUE index targeting application_id alone (pg_indexes)", _no_apid_unique_idx)

    # Functional: same non-NULL application_id in two entries with different (company,candidate,job)
    _same_appid_ok = False
    try:
        # Create a real job_application row to use as shared FK reference
        _uc.run(
            "INSERT INTO job_applications(job_id,user_id) VALUES(:j,:u)",
            j=_j_u, u=_u_u
        )
        _app_shared = _uc.run(
            "SELECT id FROM job_applications WHERE job_id=:j AND user_id=:u LIMIT 1",
            j=_j_u, u=_u_u
        )[0][0]
        # Triple A: new company / candidate / job
        _uc.run("INSERT INTO users(tw_id,user_type) VALUES('C_SA','co') ON CONFLICT DO NOTHING")
        _uc.run("INSERT INTO users(tw_id,user_type) VALUES('U_SA','emp') ON CONFLICT DO NOTHING")
        _co_sa = _uc.run("SELECT id FROM users WHERE tw_id='C_SA'")[0][0]
        _u_sa  = _uc.run("SELECT id FROM users WHERE tw_id='U_SA'")[0][0]
        _uc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'SA Job')", c=_co_sa)
        _j_sa  = _uc.run("SELECT id FROM jobs WHERE company_id=:c LIMIT 1", c=_co_sa)[0][0]
        _uc.run(
            "INSERT INTO job_pipeline_entries"
            "(company_id,candidate_id,job_id,stage,source,application_id)"
            " VALUES(:c,:u,:j,'new','application',:a)",
            c=_co_sa, u=_u_sa, j=_j_sa, a=_app_shared
        )
        # Triple B: another new company / candidate / job — same application_id
        _uc.run("INSERT INTO users(tw_id,user_type) VALUES('C_SB','co') ON CONFLICT DO NOTHING")
        _uc.run("INSERT INTO users(tw_id,user_type) VALUES('U_SB','emp') ON CONFLICT DO NOTHING")
        _co_sb = _uc.run("SELECT id FROM users WHERE tw_id='C_SB'")[0][0]
        _u_sb  = _uc.run("SELECT id FROM users WHERE tw_id='U_SB'")[0][0]
        _uc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'SB Job')", c=_co_sb)
        _j_sb  = _uc.run("SELECT id FROM jobs WHERE company_id=:c LIMIT 1", c=_co_sb)[0][0]
        _uc.run(
            "INSERT INTO job_pipeline_entries"
            "(company_id,candidate_id,job_id,stage,source,application_id)"
            " VALUES(:c,:u,:j,'reviewing','application',:a)",
            c=_co_sb, u=_u_sb, j=_j_sb, a=_app_shared
        )
        _same_appid_ok = True
    except Exception:
        pass
    check("it-08b-func. Same application_id in two entries (different triple) is allowed", _same_appid_ok)

    # migration_source_key: multiple NULLs allowed, duplicate non-NULL rejected
    _uc.run(
        "INSERT INTO candidate_bank_notes(company_id,candidate_id,body,migration_source_key)"
        " VALUES(:c,:u,'note1',NULL)",
        c=_co_u, u=_u_u
    )
    _uc.run(
        "INSERT INTO candidate_bank_notes(company_id,candidate_id,body,migration_source_key)"
        " VALUES(:c,:u,'note2',NULL)",
        c=_co_u, u=_u_u
    )
    check("it-08c. migration_source_key: multiple NULLs allowed", True)

    _uc.run(
        "INSERT INTO candidate_bank_notes(company_id,candidate_id,body,migration_source_key)"
        " VALUES(:c,:u,'note3','key_001')",
        c=_co_u, u=_u_u
    )
    _dup_key_ok = False
    try:
        _uc.run(
            "INSERT INTO candidate_bank_notes(company_id,candidate_id,body,migration_source_key)"
            " VALUES(:c,:u,'note4','key_001')",
            c=_co_u, u=_u_u
        )
        _dup_key_ok = True
    except Exception:
        pass
    check("it-08d. migration_source_key: duplicate non-NULL rejected", not _dup_key_ok)

finally:
    _uc.close()

# ── it-09: CASCADE on company/candidate deletion ─────────────────────────────
print("\n── FK Cascade / Restrict Behaviors ──")
_fc = _get_test_conn()
try:
    # Insert fresh company/candidate/job/entry
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('C_CAS','co') ON CONFLICT DO NOTHING")
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('U_CAS','emp') ON CONFLICT DO NOTHING")
    _co_c = _fc.run("SELECT id FROM users WHERE tw_id='C_CAS'")[0][0]
    _u_c  = _fc.run("SELECT id FROM users WHERE tw_id='U_CAS'")[0][0]
    _fc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'CAS Job') RETURNING id", c=_co_c)
    _j_c = _fc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_c)[0][0]
    _fc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
        " VALUES(:c,:u,:j,'new','application')",
        c=_co_c, u=_u_c, j=_j_c
    )
    _pe_c = _fc.run(
        "SELECT id FROM job_pipeline_entries WHERE company_id=:c AND candidate_id=:u",
        c=_co_c, u=_u_c
    )[0][0]

    # Delete candidate → pipeline entry should CASCADE delete
    _fc.run("DELETE FROM users WHERE tw_id='U_CAS'")
    _remaining = _fc.run(
        "SELECT COUNT(*) FROM job_pipeline_entries WHERE id=:pe", pe=_pe_c
    )[0][0]
    check("it-09a. Deleting candidate CASCADEs pipeline entry", _remaining == 0)

    # Reinsert for job RESTRICT test
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('U_RES','emp') ON CONFLICT DO NOTHING")
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('C_RES','co') ON CONFLICT DO NOTHING")
    _co_r = _fc.run("SELECT id FROM users WHERE tw_id='C_RES'")[0][0]
    _u_r  = _fc.run("SELECT id FROM users WHERE tw_id='U_RES'")[0][0]
    _fc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'RES Job') RETURNING id", c=_co_r)
    _j_r = _fc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_r)[0][0]
    _fc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
        " VALUES(:c,:u,:j,'new','company_add')",
        c=_co_r, u=_u_r, j=_j_r
    )
    _restrict_ok = False
    try:
        _fc.run("DELETE FROM jobs WHERE id=:j", j=_j_r)
        _restrict_ok = True  # should NOT reach here
    except Exception:
        pass
    check("it-09b. Deleting job with pipeline entry RESTRICTED (FK RESTRICT)", not _restrict_ok)

    # application_id → SET NULL on application delete
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('C_SN','co') ON CONFLICT DO NOTHING")
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('U_SN','emp') ON CONFLICT DO NOTHING")
    _co_sn = _fc.run("SELECT id FROM users WHERE tw_id='C_SN'")[0][0]
    _u_sn  = _fc.run("SELECT id FROM users WHERE tw_id='U_SN'")[0][0]
    _fc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'SN Job') RETURNING id", c=_co_sn)
    _j_sn = _fc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_sn)[0][0]
    _fc.run(
        "INSERT INTO job_applications(job_id,user_id) VALUES(:j,:u) RETURNING id",
        j=_j_sn, u=_u_sn
    )
    _app_sn = _fc.run(
        "SELECT id FROM job_applications WHERE job_id=:j AND user_id=:u",
        j=_j_sn, u=_u_sn
    )[0][0]
    _fc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source,application_id)"
        " VALUES(:c,:u,:j,'new','application',:a)",
        c=_co_sn, u=_u_sn, j=_j_sn, a=_app_sn
    )
    # Delete the application — FK is SET NULL
    _fc.run("DELETE FROM job_applications WHERE id=:a", a=_app_sn)
    _app_id_after = _fc.run(
        "SELECT application_id FROM job_pipeline_entries "
        "WHERE company_id=:c AND candidate_id=:u AND job_id=:j",
        c=_co_sn, u=_u_sn, j=_j_sn
    )[0][0]
    check("it-09c. Deleting application sets pipeline_entry.application_id = NULL", _app_id_after is None)

    # appointments.pipeline_entry_id → SET NULL on pipeline entry delete
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('C_APT','co') ON CONFLICT DO NOTHING")
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('U_APT','emp') ON CONFLICT DO NOTHING")
    _co_apt = _fc.run("SELECT id FROM users WHERE tw_id='C_APT'")[0][0]
    _u_apt  = _fc.run("SELECT id FROM users WHERE tw_id='U_APT'")[0][0]
    _fc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'APT Job') RETURNING id", c=_co_apt)
    _j_apt = _fc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_apt)[0][0]
    _fc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
        " VALUES(:c,:u,:j,'new','application')",
        c=_co_apt, u=_u_apt, j=_j_apt
    )
    _pe_apt = _fc.run(
        "SELECT id FROM job_pipeline_entries WHERE company_id=:c AND candidate_id=:u",
        c=_co_apt, u=_u_apt
    )[0][0]
    _fc.run(
        "INSERT INTO appointments(company_id,applicant_id,created_by,pipeline_entry_id)"
        " VALUES(:c,:u,:c,:pe)",
        c=_co_apt, u=_u_apt, pe=_pe_apt
    )
    _appt_id = _fc.run(
        "SELECT id FROM appointments WHERE pipeline_entry_id=:pe", pe=_pe_apt
    )[0][0]
    # Delete the pipeline entry — FK is SET NULL
    _fc.run("DELETE FROM job_pipeline_entries WHERE id=:pe", pe=_pe_apt)
    _pe_after = _fc.run(
        "SELECT pipeline_entry_id FROM appointments WHERE id=:a", a=_appt_id
    )[0][0]
    check("it-09d. Deleting pipeline entry sets appointments.pipeline_entry_id = NULL", _pe_after is None)

    # Deleting company CASCADEs pipeline entries
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('C_CDEL','co') ON CONFLICT DO NOTHING")
    _fc.run("INSERT INTO users(tw_id,user_type) VALUES('U_CDEL','emp') ON CONFLICT DO NOTHING")
    _co_cdel = _fc.run("SELECT id FROM users WHERE tw_id='C_CDEL'")[0][0]
    _u_cdel  = _fc.run("SELECT id FROM users WHERE tw_id='U_CDEL'")[0][0]
    _fc.run("INSERT INTO jobs(company_id,title) VALUES(:c,'CDEL Job') RETURNING id", c=_co_cdel)
    _j_cdel = _fc.run("SELECT id FROM jobs WHERE company_id=:c", c=_co_cdel)[0][0]
    _fc.run(
        "INSERT INTO job_pipeline_entries(company_id,candidate_id,job_id,stage,source)"
        " VALUES(:c,:u,:j,'new','bank_link')",
        c=_co_cdel, u=_u_cdel, j=_j_cdel
    )
    _pe_cdel = _fc.run(
        "SELECT id FROM job_pipeline_entries WHERE company_id=:c", c=_co_cdel
    )[0][0]
    # Delete company (cascades jobs → entries)
    _fc.run("DELETE FROM users WHERE tw_id='C_CDEL'")
    _rem = _fc.run("SELECT COUNT(*) FROM job_pipeline_entries WHERE id=:pe", pe=_pe_cdel)[0][0]
    check("it-09e. Deleting company CASCADEs pipeline entries", _rem == 0)

finally:
    _fc.close()

# ── Summary ───────────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, s, _ in results if s == PASS)
total  = len(results)
print("=" * 60)
print(f"Integration Results: {passed}/{total} passed")
if passed == total:
    print("🎉 All integration tests passed!")
else:
    failed = [(n, d) for n, s, d in results if s == FAIL]
    print("Failed:")
    for n, d in failed:
        print(f"  - {n}" + (f": {d}" if d else ""))

# Restore auth connection functions
_auth.get_conn     = _orig_get
_auth.release_conn = _orig_rel

if passed != total:
    sys.exit(1)
