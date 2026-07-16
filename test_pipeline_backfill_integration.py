"""
PR-2: Pipeline Backfill + Dual-write — PostgreSQL Integration Tests.

Runs against LOCAL test PostgreSQL database — NEVER touches production.
DB: tawasalna_test_pipeline @ 127.0.0.1:5432

27+ behavioral test cases covering all 17 correction points.
"""

import os
import sys

TEST_DB_URL = "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline"
os.environ["SUPABASE_DB_URL"] = TEST_DB_URL

sys.path.insert(0, os.path.dirname(__file__))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def check(name, condition, detail=None):
    status = PASS if condition else FAIL
    results.append((name, status, detail or ""))
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"{'✅' if condition else '❌'}  {name}{suffix}")


def fail(name, exc):
    results.append((name, FAIL, str(exc)[:120]))
    print(f"❌  {name}  [EXCEPTION: {exc}]")


from auth import (
    get_conn, release_conn,
    _migrate_pipeline_schema_v1,
    _migrate_partial_unique_application_id,
    _pipeline_upsert_entry,
    _pipeline_update_stage,
    pipeline_backfill_dry_run,
    run_pipeline_backfill,
    hash_password,
    BlockingConflictError,
    promote_application_to_shortlist,
    update_candidate_job_status,
    apply_job,
)

# ── Prerequisites ─────────────────────────────────────────────────────────────
PREREQ_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY, tw_id TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL, user_type TEXT NOT NULL DEFAULT 'emp',
    country_code TEXT NOT NULL DEFAULT '9620',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS profiles (
    id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    headline TEXT, bio TEXT, location TEXT, country TEXT, city TEXT, avail TEXT,
    skills TEXT[], avatar_url TEXT, website TEXT, is_verified BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    location TEXT, job_type TEXT, status TEXT NOT NULL DEFAULT 'active',
    salary_min INTEGER, salary_max INTEGER, skills TEXT[],
    closed_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, archived_at TIMESTAMPTZ,
    views INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS job_applications (
    id SERIAL PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', cover_letter TEXT,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(job_id, user_id)
);
CREATE TABLE IF NOT EXISTS company_saved_candidates (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER, saved_by INTEGER, status TEXT NOT NULL DEFAULT 'saved',
    notes TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(company_id, candidate_id)
);
CREATE TABLE IF NOT EXISTS company_candidate_job_refs (
    company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_status TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (company_id, candidate_id, job_id)
);
CREATE TABLE IF NOT EXISTS notifications (
    id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL,
    type_ TEXT NOT NULL DEFAULT 'info', title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '', link TEXT, is_read BOOLEAN NOT NULL DEFAULT FALSE,
    actor_id INTEGER, entity_id INTEGER, entity_type TEXT, event_key TEXT,
    aggregation_key TEXT, aggregation_count INTEGER NOT NULL DEFAULT 1,
    aggregation_kind TEXT, target_type TEXT, target_id INTEGER, action_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id BIGSERIAL PRIMARY KEY, job_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending', dedupe_key TEXT NOT NULL UNIQUE,
    run_at TIMESTAMPTZ NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5, last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS appointments (
    id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
    job_id INTEGER, scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60, status TEXT NOT NULL DEFAULT 'pending',
    notes TEXT, pipeline_entry_id BIGINT, created_by INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS company_posts (
    id BIGSERIAL PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL, comments_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

DROP_SQL = """
DROP TABLE IF EXISTS pipeline_stage_events CASCADE;
DROP TABLE IF EXISTS pipeline_notes CASCADE;
DROP TABLE IF EXISTS job_pipeline_entries CASCADE;
DROP TABLE IF EXISTS candidate_bank_notes CASCADE;
DROP TABLE IF EXISTS company_candidate_job_refs CASCADE;
DROP TABLE IF EXISTS company_saved_candidates CASCADE;
DROP TABLE IF EXISTS job_applications CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS company_posts CASCADE;
DROP TABLE IF EXISTS scheduler_jobs CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS jobs CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;
"""

_uid_seq = [0]


def _uid():
    _uid_seq[0] += 1
    return _uid_seq[0]


def _setup():
    conn = get_conn()
    try:
        conn.run(DROP_SQL)
        conn.run(PREREQ_SQL)
    finally:
        release_conn(conn)
    _migrate_pipeline_schema_v1()


def _user(conn, user_type="emp"):
    n = _uid()
    rows = conn.run(
        "INSERT INTO users (tw_id, full_name, email, password_hash, user_type) "
        "VALUES (:tid, :name, :email, :pw, :ut) RETURNING id",
        tid=f"T{n:06d}", name=f"User{n}", email=f"u{n}@t.com",
        pw=hash_password("test1234"), ut=user_type,
    )
    uid = int(rows[0][0])
    conn.run("INSERT INTO profiles (user_id) VALUES (:uid)", uid=uid)
    return uid


def _job(conn, company_id, title="Job"):
    rows = conn.run(
        "INSERT INTO jobs (company_id, title, description) VALUES (:c, :t, 'd') RETURNING id",
        c=company_id, t=title,
    )
    return int(rows[0][0])


def _app(conn, job_id, user_id, status="pending"):
    rows = conn.run(
        "INSERT INTO job_applications (job_id, user_id, status) VALUES (:j,:u,:s) RETURNING id",
        j=job_id, u=user_id, s=status,
    )
    return int(rows[0][0])


def _ccjr(conn, co, emp, job, status=None):
    conn.run(
        "INSERT INTO company_candidate_job_refs (company_id, candidate_id, job_id, candidate_status) "
        "VALUES (:c,:u,:j,:s)",
        c=co, u=emp, j=job, s=status,
    )


def _entry(conn, co, emp, job):
    rows = conn.run(
        "SELECT id, stage, source, application_id FROM job_pipeline_entries "
        "WHERE company_id=:c AND candidate_id=:u AND job_id=:j",
        c=co, u=emp, j=job,
    )
    return rows[0] if rows else None


def _events(conn, entry_id):
    rows = conn.run(
        "SELECT from_stage, to_stage, reason FROM pipeline_stage_events "
        "WHERE pipeline_entry_id=:e ORDER BY created_at, id",
        e=entry_id,
    )
    return rows or []


def _cnt(conn, tbl):
    return int(conn.run(f"SELECT COUNT(*) FROM {tbl}")[0][0])


# ═══════════════════════════════════════════════════════════════════════════════
# §1  Schema migration
# ═══════════════════════════════════════════════════════════════════════════════
try:
    _setup()
    conn = get_conn()
    try:
        tables = {r[0] for r in conn.run(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )}
        check("1-01. job_pipeline_entries table created", "job_pipeline_entries" in tables)
        check("1-02. pipeline_stage_events table created", "pipeline_stage_events" in tables)
        check("1-03. candidate_bank_notes table created", "candidate_bank_notes" in tables)
        check("1-04. pipeline_notes table created", "pipeline_notes" in tables)
    finally:
        release_conn(conn)
except Exception as e:
    fail("1-01. Schema migration", e)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# §2  _pipeline_upsert_entry: INSERT on first call
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        co1 = _user(conn, "co"); emp1 = _user(conn); job1 = _job(conn, co1)
        eid1 = _pipeline_upsert_entry(conn, company_id=co1, candidate_id=emp1, job_id=job1,
                                       stage="new", source="application")
        row = _entry(conn, co1, emp1, job1)
        check("2-01. Returns int id", eid1 is not None and isinstance(eid1, int))
        check("2-02. Stage='new'", row and row[1] == "new")
        check("2-03. Source='application'", row and row[2] == "application")
        check("2-04. application_id=NULL (not provided)", row and row[3] is None)
        conn.run("COMMIT")
    finally:
        release_conn(conn)
except Exception as e:
    fail("2-01. _pipeline_upsert_entry INSERT", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §3  _pipeline_upsert_entry: idempotent on repeat call (no application_id)
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        eid1a = _pipeline_upsert_entry(conn, company_id=co1, candidate_id=emp1, job_id=job1,
                                        stage="reviewing", source="application")
        eid1b = _pipeline_upsert_entry(conn, company_id=co1, candidate_id=emp1, job_id=job1,
                                        stage="reviewing", source="application")
        check("3-01. Returns same id on repeat (no-op)", eid1a == eid1b == eid1)
        check("3-02. Only one entry exists", _cnt(conn, "job_pipeline_entries") == 1)
        conn.run("COMMIT")
    finally:
        release_conn(conn)
except Exception as e:
    fail("3-01. idempotent upsert", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §4  _pipeline_upsert_entry: links NULL application_id on second call
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        co2 = _user(conn, "co"); emp2 = _user(conn); job2 = _job(conn, co2)
        # Create a real application first
        app2 = _app(conn, job2, emp2, "pending")
        # Backfill entry: no application_id (from ccjr)
        eid2a = _pipeline_upsert_entry(conn, company_id=co2, candidate_id=emp2, job_id=job2,
                                        stage="new", source="migration")
        # Now link the real application_id
        eid2b = _pipeline_upsert_entry(conn, company_id=co2, candidate_id=emp2, job_id=job2,
                                        stage="new", source="application", application_id=app2)
        row = _entry(conn, co2, emp2, job2)
        check("4-01. Returns same entry id when linking", eid2a == eid2b)
        check("4-02. application_id linked to existing entry", row and row[3] == app2)
        conn.run("COMMIT")
    finally:
        release_conn(conn)
except Exception as e:
    fail("4-01. link application_id", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §5  _pipeline_upsert_entry: raises ValueError on application_id mismatch
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        co3 = _user(conn, "co"); emp3 = _user(conn); job3 = _job(conn, co3)
        app3a = _app(conn, job3, emp3, "pending")
        # Insert a second job and get a different app_id
        job3b = _job(conn, co3)
        app3b = _app(conn, job3b, emp3, "pending")
        # Create entry with app3a
        _pipeline_upsert_entry(conn, company_id=co3, candidate_id=emp3, job_id=job3,
                                stage="new", source="application", application_id=app3a)
        # Try to link app3b (different app_id → conflict)
        raised = False
        try:
            _pipeline_upsert_entry(conn, company_id=co3, candidate_id=emp3, job_id=job3,
                                    stage="new", source="application", application_id=app3b)
        except ValueError as ve:
            raised = True
            check("5-01. ValueError raised on app_id mismatch",
                  "conflict" in str(ve).lower() or "application_id" in str(ve).lower())
        check("5-02. ValueError was raised", raised)
        conn.run("ROLLBACK")
    finally:
        release_conn(conn)
except Exception as e:
    fail("5-01. application_id mismatch", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §6  _pipeline_update_stage: returns False when entry doesn't exist
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        co4 = _user(conn, "co"); emp4 = _user(conn); job4 = _job(conn, co4)
        result = _pipeline_update_stage(conn, company_id=co4, candidate_id=emp4, job_id=job4,
                                         new_stage="reviewing")
        check("6-01. Returns False when no entry exists", result is False)
        conn.run("COMMIT")
    finally:
        release_conn(conn)
except Exception as e:
    fail("6-01. update_stage no entry", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §7  _pipeline_update_stage: creates stage event on change
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        eid4 = _pipeline_upsert_entry(conn, company_id=co4, candidate_id=emp4, job_id=job4,
                                       stage="new", source="application")
        evts_before = _cnt(conn, "pipeline_stage_events")
        result = _pipeline_update_stage(conn, company_id=co4, candidate_id=emp4, job_id=job4,
                                         new_stage="reviewing", changed_by=co4)
        check("7-01. Returns True when entry found", result is True)
        check("7-02. Stage event created", _cnt(conn, "pipeline_stage_events") == evts_before + 1)
        evts = _events(conn, eid4)
        check("7-03. Event: from_stage='new', to_stage='reviewing'",
              evts and evts[-1][0] == "new" and evts[-1][1] == "reviewing")
        conn.run("COMMIT")
    finally:
        release_conn(conn)
except Exception as e:
    fail("7-01. stage event created", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §8  _pipeline_update_stage: idempotent (same stage → no new event)
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        evts_before = _cnt(conn, "pipeline_stage_events")
        result = _pipeline_update_stage(conn, company_id=co4, candidate_id=emp4, job_id=job4,
                                         new_stage="reviewing")  # already reviewing
        check("8-01. Returns True (found the row)", result is True)
        check("8-02. No new event for same-stage call",
              _cnt(conn, "pipeline_stage_events") == evts_before)
        conn.run("COMMIT")
    finally:
        release_conn(conn)
except Exception as e:
    fail("8-01. idempotent stage update", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §9  dry_run delegates to pipeline_backfill_dry_run
# ═══════════════════════════════════════════════════════════════════════════════
try:
    dr = run_pipeline_backfill(dry_run=True)
    check("9-01. dry_run=True in result", dr.get("dry_run") is True)
    check("9-02. Has job_applications key", "job_applications" in dr)
    check("9-03. Has company_candidate_job_refs key", "company_candidate_job_refs" in dr)
    check("9-04. Has notes key", "notes" in dr)
    check("9-05. Has conflicts_by_type key", "conflicts_by_type" in dr)
except Exception as e:
    fail("9-01. dry_run delegation", e)

# ═══════════════════════════════════════════════════════════════════════════════
# Fresh state for backfill tests §10-16
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
conn = get_conn()
try:
    bf_co  = _user(conn, "co")
    bf_e1  = _user(conn)
    bf_e2  = _user(conn)
    bf_e3  = _user(conn)
    bf_e4  = _user(conn)
    bf_j1  = _job(conn, bf_co, "Alpha")
    bf_j2  = _job(conn, bf_co, "Beta")
    bf_j3  = _job(conn, bf_co, "Gamma")
    # ccjr (Pass 1 source)
    _ccjr(conn, bf_co, bf_e1, bf_j1, "shortlisted")   # valid
    _ccjr(conn, bf_co, bf_e2, bf_j1, "contacted")     # valid
    _ccjr(conn, bf_co, bf_e3, bf_j2, None)             # NULL → app lookup (app 'viewed' → stage 'reviewing')
    _ccjr(conn, bf_co, bf_e4, bf_j3, "INVALID_X")     # unknown → conflict
    # applications (Pass 2 source)
    bf_app1 = _app(conn, bf_j1, bf_e1, "accepted")   # same triple as e1,j1 → link app_id
    bf_app2 = _app(conn, bf_j2, bf_e3, "viewed")     # same triple as e3,j2 → already linked in Pass-1
    bf_app3 = _app(conn, bf_j3, bf_e1, "pending")    # NEW triple
    # notes (Pass 3 source)
    conn.run(
        "INSERT INTO company_saved_candidates (company_id, candidate_id, notes) "
        "VALUES (:c, :u, 'Great candidate')",
        c=bf_co, u=bf_e1,
    )
    conn.run(
        "INSERT INTO company_saved_candidates (company_id, candidate_id, notes) "
        "VALUES (:c, :u, '') ON CONFLICT DO NOTHING",
        c=bf_co, u=bf_e2,  # empty → not migrated
    )
finally:
    release_conn(conn)

# ═══════════════════════════════════════════════════════════════════════════════
# §10 pipeline_backfill_dry_run: analysis counts
# ═══════════════════════════════════════════════════════════════════════════════
try:
    dr2 = pipeline_backfill_dry_run()
    check("10-01. dry_run=True", dr2.get("dry_run") is True)
    check("10-02. job_applications.total = 3", dr2["job_applications"]["total"] == 3)
    check("10-03. ccjr.total = 4", dr2["company_candidate_job_refs"]["total"] == 4)
    check("10-04. notes.to_migrate = 1", dr2["notes"]["to_migrate"] == 1)
    check("10-05. unknown_ccjr_status detected",
          dr2["conflicts_by_type"].get("unknown_ccjr_status", 0) >= 1)
    check("10-06. blocking_conflicts=False (no app_id mismatch)", dr2.get("blocking_conflicts") is False)
    check("10-07. conflicts_count >= 1", dr2.get("conflicts_count", 0) >= 1)
except Exception as e:
    fail("10-01. dry_run analysis", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §11-14 run_pipeline_backfill execution
# ═══════════════════════════════════════════════════════════════════════════════
try:
    r = run_pipeline_backfill(dry_run=False)
    check("11-01. status='done'", r.get("status") == "done")
    check("11-02. dry_run=False", r.get("dry_run") is False)
    # e1,j1 (ccjr shortlisted) + e2,j1 (ccjr contacted) + e3,j2 (ccjr NULL) + e1,j3 (app only)
    check("11-03. entries_created >= 4", r.get("entries_created", 0) >= 4)
    # e1,j1 gets app_id linked in Pass-2 (NULL ccjr path sets app_id in Pass-1 for e3,j2)
    check("11-04. application_links_added >= 1", r.get("application_links_added", 0) >= 1)
    check("11-05. unknown_statuses list has INVALID_X",
          any(s.get("status") == "INVALID_X" for s in r.get("unknown_statuses", [])))
    check("11-06. conflicts_count >= 1", r.get("conflicts_count", 0) >= 1)

    conn = get_conn()
    try:
        row_e1j1 = _entry(conn, bf_co, bf_e1, bf_j1)
        row_e2j1 = _entry(conn, bf_co, bf_e2, bf_j1)
        row_e3j2 = _entry(conn, bf_co, bf_e3, bf_j2)
        row_e1j3 = _entry(conn, bf_co, bf_e1, bf_j3)
        row_e4j3 = _entry(conn, bf_co, bf_e4, bf_j3)

        # After Pass-2 links app_id to e1,j1, it also updates source='application' (Bnd-2)
        check("12-01. Pass-1 entry e1,j1 source='application' (updated by Pass-2 link)",
              row_e1j1 and row_e1j1[2] == "application")
        check("12-02. Pass-1 entry e1,j1 stage='shortlisted'",
              row_e1j1 and row_e1j1[1] == "shortlisted")
        check("12-03. Pass-1 entry e2,j1 stage='contacted'",
              row_e2j1 and row_e2j1[1] == "contacted")
        # NULL CCJR: app found (bf_app2, viewed→reviewing) → stage='reviewing', source='application' (Bnd-1)
        check("12-04. NULL CCJR entry e3,j2 stage='reviewing' (app was 'viewed')",
              row_e3j2 and row_e3j2[1] == "reviewing")
        check("12-04b. NULL CCJR entry e3,j2 source='application'",
              row_e3j2 and row_e3j2[2] == "application")
        check("12-05. Pass-2 entry e1,j3 source='application' (no ccjr)",
              row_e1j3 and row_e1j3[2] == "application")
        check("12-06. Pass-2 entry e1,j3 stage='new' (pending→new)",
              row_e1j3 and row_e1j3[1] == "new")
        check("12-07. e4,j3 NOT created (INVALID_X status skipped)",
              row_e4j3 is None)

        check("13-01. app_id linked to e1,j1 from Pass-2",
              row_e1j1 and row_e1j1[3] == bf_app1)
        check("13-02. app_id linked to e3,j2 from Pass-2",
              row_e3j2 and row_e3j2[3] == bf_app2)
        check("13-03. e1,j3 has app_id=bf_app3 (fresh insert)",
              row_e1j3 and row_e1j3[3] == bf_app3)

        # §25 initial events
        check("25-01. initial_events_created >= 4", r.get("initial_events_created", 0) >= 4)
        if row_e1j1:
            evts_e1j1 = _events(conn, int(row_e1j1[0]))
            check("25-02. Pass-1 entry has an initial stage event", len(evts_e1j1) >= 1)
            # §26 from_stage=NULL for initial events
            check("26-01. Initial event from_stage=NULL", evts_e1j1[0][0] is None)
            check("26-02. Initial event to_stage='shortlisted'", evts_e1j1[0][1] == "shortlisted")
            check("26-03. Initial event reason='legacy_backfill'",
                  evts_e1j1[0][2] == "legacy_backfill")
    finally:
        release_conn(conn)
except Exception as e:
    fail("11-01. run_pipeline_backfill", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §15 Pass-3: notes → candidate_bank_notes
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        check("15-01. bank_notes_created = 1 (empty notes not migrated)",
              _cnt(conn, "candidate_bank_notes") == 1)
        mrows = conn.run("SELECT migration_source_key, is_migrated FROM candidate_bank_notes")
        check("15-02. migration_source_key set",
              any("legacy:company_saved_candidates:" in (r[0] or "") for r in mrows))
        check("15-03. is_migrated=TRUE", all(r[1] for r in mrows))
        check("15-04. result.bank_notes_created=1", r.get("bank_notes_created") == 1)
    finally:
        release_conn(conn)
except Exception as e:
    fail("15-01. notes migration", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §16 idempotency: 2nd run adds nothing new
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        entries_b = _cnt(conn, "job_pipeline_entries")
        events_b  = _cnt(conn, "pipeline_stage_events")
        notes_b   = _cnt(conn, "candidate_bank_notes")
    finally:
        release_conn(conn)

    r2 = run_pipeline_backfill(dry_run=False)

    conn = get_conn()
    try:
        check("16-01. No new entries on 2nd run",
              _cnt(conn, "job_pipeline_entries") == entries_b)
        check("16-02. No new events on 2nd run",
              _cnt(conn, "pipeline_stage_events") == events_b)
        check("16-03. No new notes on 2nd run",
              _cnt(conn, "candidate_bank_notes") == notes_b)
        check("16-04. entries_created=0 on 2nd run", r2.get("entries_created", 0) == 0)
        check("16-05. bank_notes_created=0 on 2nd run", r2.get("bank_notes_created", 0) == 0)
    finally:
        release_conn(conn)
except Exception as e:
    fail("16-01. idempotency", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §17 ROLLBACK atomicity
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run("BEGIN")
        co_r = _user(conn, "co"); emp_r = _user(conn); job_r = _job(conn, co_r)
        _pipeline_upsert_entry(conn, company_id=co_r, candidate_id=emp_r, job_id=job_r,
                                stage="new", source="application")
        # Count before rollback (inside transaction — visible to this connection)
        in_tx = _cnt(conn, "job_pipeline_entries")
        conn.run("ROLLBACK")
        after = _cnt(conn, "job_pipeline_entries")
        check("17-01. Entry visible inside transaction", in_tx >= 1)
        check("17-02. Entry gone after ROLLBACK (count unchanged)",
              after == entries_b)  # entries_b from §16
    finally:
        release_conn(conn)
except Exception as e:
    fail("17-01. ROLLBACK atomicity", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §18 update_application_status: no auto-save to company_saved_candidates
# §19 pipeline stage updated on status change
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        dw_co  = _user(conn, "co"); dw_emp = _user(conn); dw_job = _job(conn, dw_co)
        dw_app = _app(conn, dw_job, dw_emp, "pending")
    finally:
        release_conn(conn)

    # Create pipeline entry (simulates apply_job)
    conn = get_conn()
    try:
        conn.run("BEGIN")
        _pipeline_upsert_entry(conn, company_id=dw_co, candidate_id=dw_emp, job_id=dw_job,
                                stage="new", source="application", application_id=dw_app,
                                created_by=dw_co, job_title_snapshot="DW Job")
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    from auth import update_application_status
    update_application_status(dw_app, "viewed", actor_id=dw_co)

    conn = get_conn()
    try:
        # No auto-save to company_saved_candidates
        csc = int(conn.run(
            "SELECT COUNT(*) FROM company_saved_candidates WHERE company_id=:c AND candidate_id=:u",
            c=dw_co, u=dw_emp,
        )[0][0])
        check("18-01. No auto-save to company_saved_candidates", csc == 0)

        # Pipeline stage updated to 'reviewing' (viewed → reviewing)
        row = _entry(conn, dw_co, dw_emp, dw_job)
        check("19-01. Stage updated to 'reviewing'", row and row[1] == "reviewing")
        evts = _events(conn, int(row[0])) if row else []
        check("19-02. Stage event created (new → reviewing)",
              any(e[0] == "new" and e[1] == "reviewing" for e in evts))
    finally:
        release_conn(conn)
except Exception as e:
    fail("18-01. no auto-save / stage update", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §20 update_candidate_job_status: passes actor_id to pipeline
# ═══════════════════════════════════════════════════════════════════════════════
try:
    conn = get_conn()
    try:
        conn.run(
            "INSERT INTO company_candidate_job_refs (company_id, candidate_id, job_id, candidate_status) "
            "VALUES (:c, :u, :j, 'saved') ON CONFLICT DO NOTHING",
            c=dw_co, u=dw_emp, j=dw_job,
        )
    finally:
        release_conn(conn)

    from auth import update_candidate_job_status
    ok = update_candidate_job_status(
        company_id=dw_co, candidate_id=dw_emp, job_id=dw_job,
        candidate_status="shortlisted", actor_id=dw_co,
    )
    check("20-01. Returns True", ok is True)

    conn = get_conn()
    try:
        row = _entry(conn, dw_co, dw_emp, dw_job)
        check("20-02. Pipeline stage updated to 'shortlisted'",
              row and row[1] == "shortlisted")
        evts = _events(conn, int(row[0])) if row else []
        check("20-03. Stage event created for shortlisted",
              any(e[1] == "shortlisted" for e in evts))
    finally:
        release_conn(conn)
except Exception as e:
    fail("20-01. actor_id passthrough", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §21 apply_job: pipeline entry created atomically
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        aj_co = _user(conn, "co"); aj_emp = _user(conn); aj_job = _job(conn, aj_co, "AJ Job")
    finally:
        release_conn(conn)

    from auth import apply_job
    res = apply_job(aj_job, aj_emp, "Cover letter")
    check("21-01. apply_job success (not already_applied)", not res.get("already_applied", False))

    conn = get_conn()
    try:
        app_rows = conn.run("SELECT id FROM job_applications WHERE job_id=:j AND user_id=:u",
                            j=aj_job, u=aj_emp)
        app_id = int(app_rows[0][0]) if app_rows else None
        row = _entry(conn, aj_co, aj_emp, aj_job)
        check("21-02. Pipeline entry created", row is not None)
        check("21-03. Stage='new'", row and row[1] == "new")
        check("21-04. Source='application'", row and row[2] == "application")
        check("21-05. application_id matches job_applications.id",
              row and app_id and row[3] == app_id)
    finally:
        release_conn(conn)
except Exception as e:
    fail("21-01. apply_job pipeline", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §22 blocking_conflicts=True on app_id mismatch
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        bc_co = _user(conn, "co"); bc_emp = _user(conn); bc_job = _job(conn, bc_co)
        bc_app = _app(conn, bc_job, bc_emp, "pending")
        # Force a DIFFERENT fake app_id into the pipeline entry — we'll do it via raw SQL
        # (normally impossible via the API — simulates corrupt migration state)
        # We need an existing application with a different id first:
        bc_j2  = _job(conn, bc_co)
        bc_app2 = _app(conn, bc_j2, bc_emp, "pending")  # different application
        # Insert pipeline entry with bc_app2 for the bc_job/bc_emp triple (wrong app_id)
        conn.run("BEGIN")
        conn.run(
            "INSERT INTO job_pipeline_entries "
            "(company_id, candidate_id, job_id, application_id, stage, source) "
            "VALUES (:c, :u, :j, :a, 'new', 'migration')",
            c=bc_co, u=bc_emp, j=bc_job, a=bc_app2,  # bc_app2 != bc_app → mismatch
        )
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    dr3 = pipeline_backfill_dry_run()
    check("22-01. blocking_conflicts=True", dr3.get("blocking_conflicts") is True)
    check("22-02. application_id_mismatch in conflicts_by_type",
          dr3.get("conflicts_by_type", {}).get("application_id_mismatch", 0) >= 1)
except Exception as e:
    fail("22-01. blocking_conflicts", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §24 _migrate_partial_unique_application_id: idempotent
# ═══════════════════════════════════════════════════════════════════════════════
_setup()  # Reset after §22 corrupt state
try:
    _migrate_partial_unique_application_id()
    _migrate_partial_unique_application_id()  # must not raise
    check("24-01. Idempotent (no exception on 2nd call)", True)

    conn = get_conn()
    try:
        idx = conn.run(
            "SELECT indexname FROM pg_indexes WHERE tablename='job_pipeline_entries' "
            "AND indexname='uq_jpe_application_id'"
        )
        check("24-02. Partial UNIQUE index exists", bool(idx))
    finally:
        release_conn(conn)
except Exception as e:
    fail("24-01. idempotent index", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §27 pipeline_stage_events: full chain from_stage set correctly
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        sc_co = _user(conn, "co"); sc_emp = _user(conn); sc_job = _job(conn, sc_co)
        conn.run("BEGIN")
        sc_eid = _pipeline_upsert_entry(conn, company_id=sc_co, candidate_id=sc_emp, job_id=sc_job,
                                         stage="new", source="application")
        _pipeline_update_stage(conn, company_id=sc_co, candidate_id=sc_emp, job_id=sc_job,
                                new_stage="reviewing", changed_by=sc_co)
        _pipeline_update_stage(conn, company_id=sc_co, candidate_id=sc_emp, job_id=sc_job,
                                new_stage="shortlisted", changed_by=sc_co)
        conn.run("COMMIT")
        evts = _events(conn, sc_eid)
        check("27-01. 2 events (new→reviewing, reviewing→shortlisted)", len(evts) == 2)
        check("27-02. First event: new→reviewing",
              evts[0][0] == "new" and evts[0][1] == "reviewing")
        check("27-03. Second event: reviewing→shortlisted",
              evts[1][0] == "reviewing" and evts[1][1] == "shortlisted")
    finally:
        release_conn(conn)
except Exception as e:
    fail("27-01. stage event chain", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §28 null_ccjr_without_application: ccjr NULL with no matching app → conflict
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        na_co  = _user(conn, "co")
        na_emp = _user(conn)
        na_job = _job(conn, na_co)
        _ccjr(conn, na_co, na_emp, na_job, None)  # NULL status, no application exists
    finally:
        release_conn(conn)

    dr28 = pipeline_backfill_dry_run()
    check("28-01. null_ccjr_without_application detected in dry_run",
          dr28["conflicts_by_type"].get("null_ccjr_without_application", 0) >= 1)

    r28 = run_pipeline_backfill(dry_run=False)
    check("28-02. Conflict counted in run result",
          r28["conflicts_by_type"].get("null_ccjr_without_application", 0) >= 1)
    # No pipeline entry created for this triple
    conn = get_conn()
    try:
        row28 = _entry(conn, na_co, na_emp, na_job)
        check("28-03. No pipeline entry created for null_ccjr_without_application",
              row28 is None)
    finally:
        release_conn(conn)
except Exception as e:
    fail("28-01. null_ccjr_without_application", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §29 Comprehensive conflict categories in dry_run
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        cc_co   = _user(conn, "co")
        cc_emp  = _user(conn)
        cc_nomp = _user(conn, "co")   # not an employee
        cc_job  = _job(conn, cc_co)
        # candidate_not_employee: ccjr where candidate is 'co' type
        _ccjr(conn, cc_co, cc_nomp, cc_job, "saved")
        # application with non-employee
        conn.run(
            "INSERT INTO job_applications (job_id, user_id, status) "
            "VALUES (:j, :u, 'pending')",
            j=cc_job, u=cc_nomp,
        )
    finally:
        release_conn(conn)

    dr29 = pipeline_backfill_dry_run()
    check("29-01. candidate_not_employee detected",
          dr29["conflicts_by_type"].get("candidate_not_employee", 0) >= 1)
    check("29-02. conflicts_by_type is a dict", isinstance(dr29["conflicts_by_type"], dict))
    check("29-03. blocking_conflicts is bool", isinstance(dr29["blocking_conflicts"], bool))
except Exception as e:
    fail("29-01. comprehensive conflict categories", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §30 BlockingConflictError: backfill raises with structured report
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        bce_co  = _user(conn, "co")
        bce_emp = _user(conn)
        bce_job = _job(conn, bce_co)
        bce_app = _app(conn, bce_job, bce_emp, "pending")
        # Create a second job to get a different app_id
        bce_j2  = _job(conn, bce_co)
        bce_app2 = _app(conn, bce_j2, bce_emp, "pending")
        # Force pipeline entry with WRONG app_id
        conn.run("BEGIN")
        conn.run(
            "INSERT INTO job_pipeline_entries "
            "(company_id, candidate_id, job_id, application_id, stage, source) "
            "VALUES (:c, :u, :j, :a, 'new', 'migration')",
            c=bce_co, u=bce_emp, j=bce_job, a=bce_app2,
        )
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    raised_bce = None
    try:
        run_pipeline_backfill(dry_run=False)
    except BlockingConflictError as bce:
        raised_bce = bce
    except RuntimeError as rte:
        # run_pipeline_backfill wraps with RuntimeError when not BlockingConflictError
        raised_bce = rte

    check("30-01. BlockingConflictError raised (or RuntimeError wrapping it)",
          raised_bce is not None)
    if isinstance(raised_bce, BlockingConflictError):
        check("30-02. report has error key",
              raised_bce.report.get("error") == "blocking_conflicts")
        check("30-03. conflicts_by_type in report",
              "conflicts_by_type" in raised_bce.report)
    else:
        check("30-02. BlockingConflictError raised directly",
              isinstance(raised_bce, BlockingConflictError))
        check("30-03. skipped (not BlockingConflictError)", False)

    # DB must be clean — backfill must have rolled back
    conn = get_conn()
    try:
        # The bad entry we created should still be there (we didn't clean up)
        # The point is no NEW entry was created
        ent_cnt = _cnt(conn, "job_pipeline_entries")
        check("30-04. No additional entries created on blocking conflict",
              ent_cnt == 1)  # only the bad one we forced
    finally:
        release_conn(conn)
except Exception as e:
    fail("30-01. BlockingConflictError on backfill", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §31 promote_application_to_shortlist: no write to company_saved_candidates
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        ps_co  = _user(conn, "co")
        ps_emp = _user(conn)
        ps_job = _job(conn, ps_co)
        ps_app = _app(conn, ps_job, ps_emp, "pending")
    finally:
        release_conn(conn)

    result31 = promote_application_to_shortlist(ps_app, ps_co)
    check("31-01. promote returns application.status='accepted'",
          result31.get("application", {}).get("status") == "accepted")
    check("31-02. candidate_status='shortlisted' in response",
          result31.get("candidate_status") == "shortlisted")
    check("31-03. general_status is None (no bank row yet)",
          result31.get("general_status") is None)

    conn = get_conn()
    try:
        csc_cnt = int(conn.run(
            "SELECT COUNT(*) FROM company_saved_candidates "
            "WHERE company_id=:c AND candidate_id=:u",
            c=ps_co, u=ps_emp,
        )[0][0])
        check("31-04. company_saved_candidates NOT written by promote (Option B, Bnd-4)",
              csc_cnt == 0)
        # Pipeline entry must exist with stage='shortlisted'
        row31 = _entry(conn, ps_co, ps_emp, ps_job)
        check("31-05. Pipeline entry stage='shortlisted'",
              row31 and row31[1] == "shortlisted")
        # Stage event with reason='application_shortlisted'
        evts31 = _events(conn, int(row31[0])) if row31 else []
        check("31-06. Stage event reason='application_shortlisted'",
              any(e[2] == "application_shortlisted" for e in evts31))
    finally:
        release_conn(conn)
except Exception as e:
    fail("31-01. promote doesn't write bank", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §32 promote_shortlist: general_status read from existing bank row
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        gs_co  = _user(conn, "co")
        gs_emp = _user(conn)
        gs_job = _job(conn, gs_co)
        gs_app = _app(conn, gs_job, gs_emp, "pending")
        # Pre-insert a bank row with status='contacted'
        conn.run(
            "INSERT INTO company_saved_candidates (company_id, candidate_id, status) "
            "VALUES (:c, :u, 'contacted')",
            c=gs_co, u=gs_emp,
        )
    finally:
        release_conn(conn)

    result32 = promote_application_to_shortlist(gs_app, gs_co)
    check("32-01. general_status reads existing bank status",
          result32.get("general_status") == "contacted")
    # Bank row must NOT be modified
    conn = get_conn()
    try:
        bank_row = conn.run(
            "SELECT status FROM company_saved_candidates "
            "WHERE company_id=:c AND candidate_id=:u",
            c=gs_co, u=gs_emp,
        )
        check("32-02. Bank row status unchanged ('contacted')",
              bank_row and bank_row[0][0] == "contacted")
    finally:
        release_conn(conn)
except Exception as e:
    fail("32-01. general_status from bank", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §33 apply_job: created_by=user_id (employee, not company) + initial event
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        aj2_co  = _user(conn, "co")
        aj2_emp = _user(conn)
        aj2_job = _job(conn, aj2_co)
    finally:
        release_conn(conn)

    apply_job(aj2_job, aj2_emp, "test cover")

    conn = get_conn()
    try:
        row33 = _entry(conn, aj2_co, aj2_emp, aj2_job)
        check("33-01. Pipeline entry created by apply_job", row33 is not None)
        if row33:
            # created_by must be the employee (aj2_emp), not the company (aj2_co) (Bnd-6)
            cr_by = conn.run(
                "SELECT created_by FROM job_pipeline_entries WHERE id=:id",
                id=int(row33[0]),
            )
            check("33-02. created_by = employee user_id (not company)",
                  cr_by and int(cr_by[0][0]) == aj2_emp)
            # Initial stage event with reason='application_submitted'
            evts33 = _events(conn, int(row33[0]))
            check("33-03. Initial event created with reason='application_submitted'",
                  any(e[2] == "application_submitted" for e in evts33))
            check("33-04. Initial event from_stage=NULL",
                  any(e[0] is None for e in evts33))
    finally:
        release_conn(conn)
except Exception as e:
    fail("33-01. apply_job created_by + initial event", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §34 event reason: application_status_changed
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        asc_co  = _user(conn, "co")
        asc_emp = _user(conn)
        asc_job = _job(conn, asc_co)
        asc_app = _app(conn, asc_job, asc_emp, "pending")
        conn.run("BEGIN")
        _pipeline_upsert_entry(conn, company_id=asc_co, candidate_id=asc_emp, job_id=asc_job,
                                stage="new", source="application", application_id=asc_app)
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    from auth import update_application_status
    update_application_status(asc_app, "viewed", actor_id=asc_co)

    conn = get_conn()
    try:
        row34 = _entry(conn, asc_co, asc_emp, asc_job)
        evts34 = _events(conn, int(row34[0])) if row34 else []
        check("34-01. event reason='application_status_changed'",
              any(e[2] == "application_status_changed" for e in evts34))
    finally:
        release_conn(conn)
except Exception as e:
    fail("34-01. application_status_changed reason", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §35 event reason: candidate_job_status_changed
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        cjsc_co  = _user(conn, "co")
        cjsc_emp = _user(conn)
        cjsc_job = _job(conn, cjsc_co)
        conn.run(
            "INSERT INTO company_candidate_job_refs (company_id, candidate_id, job_id, candidate_status) "
            "VALUES (:c, :u, :j, 'saved')",
            c=cjsc_co, u=cjsc_emp, j=cjsc_job,
        )
    finally:
        release_conn(conn)

    ok35 = update_candidate_job_status(
        company_id=cjsc_co, candidate_id=cjsc_emp, job_id=cjsc_job,
        candidate_status="shortlisted", actor_id=cjsc_co,
    )
    check("35-01. update_candidate_job_status returns True", ok35 is True)

    conn = get_conn()
    try:
        row35 = _entry(conn, cjsc_co, cjsc_emp, cjsc_job)
        check("35-02. Pipeline entry created by ensure-entry in update_candidate_job_status",
              row35 is not None)
        evts35 = _events(conn, int(row35[0])) if row35 else []
        check("35-03. event reason='candidate_job_status_changed'",
              any(e[2] == "candidate_job_status_changed" for e in evts35))
    finally:
        release_conn(conn)
except Exception as e:
    fail("35-01. candidate_job_status_changed reason + ensure-entry", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §36 update_candidate_job_status: candidate_status=None with no app → ValueError
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        none_co  = _user(conn, "co")
        none_emp = _user(conn)
        none_job = _job(conn, none_co)
        conn.run(
            "INSERT INTO company_candidate_job_refs (company_id, candidate_id, job_id, candidate_status) "
            "VALUES (:c, :u, :j, 'saved')",
            c=none_co, u=none_emp, j=none_job,
        )
    finally:
        release_conn(conn)

    raised36 = False
    try:
        update_candidate_job_status(
            company_id=none_co, candidate_id=none_emp, job_id=none_job,
            candidate_status=None, actor_id=none_co,
        )
    except (ValueError, RuntimeError):
        raised36 = True
    check("36-01. ValueError/RuntimeError raised when None status + no application",
          raised36)
except Exception as e:
    fail("36-01. None status no application", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §37 update_candidate_job_status: candidate_status=None with app → revert pipeline
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        rev_co  = _user(conn, "co")
        rev_emp = _user(conn)
        rev_job = _job(conn, rev_co)
        rev_app = _app(conn, rev_job, rev_emp, "viewed")  # viewed → reviewing
        conn.run(
            "INSERT INTO company_candidate_job_refs (company_id, candidate_id, job_id, candidate_status) "
            "VALUES (:c, :u, :j, 'shortlisted')",
            c=rev_co, u=rev_emp, j=rev_job,
        )
        # Pre-create pipeline at shortlisted
        conn.run("BEGIN")
        _pipeline_upsert_entry(conn, company_id=rev_co, candidate_id=rev_emp, job_id=rev_job,
                                stage="shortlisted", source="application", application_id=rev_app)
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    ok37 = update_candidate_job_status(
        company_id=rev_co, candidate_id=rev_emp, job_id=rev_job,
        candidate_status=None, actor_id=rev_co,
    )
    check("37-01. Returns True when reverting pipeline with None + app", ok37 is True)

    conn = get_conn()
    try:
        row37 = _entry(conn, rev_co, rev_emp, rev_job)
        check("37-02. Pipeline reverted to app-derived stage ('reviewing')",
              row37 and row37[1] == "reviewing")
    finally:
        release_conn(conn)
except Exception as e:
    fail("37-01. None status revert pipeline", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §38 Pass-3 notes: trim + legacy created_at preserved
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        nt_co  = _user(conn, "co")
        nt_emp = _user(conn)
        nt_ts  = "2024-03-15 10:30:00+00"
        conn.run(
            "INSERT INTO company_saved_candidates "
            "(company_id, candidate_id, notes, created_at) "
            "VALUES (:c, :u, '  Great candidate  ', :ts::timestamptz)",
            c=nt_co, u=nt_emp, ts=nt_ts,
        )
    finally:
        release_conn(conn)

    run_pipeline_backfill(dry_run=False)

    conn = get_conn()
    try:
        note_rows = conn.run(
            "SELECT body, created_at, created_by FROM candidate_bank_notes "
            "WHERE company_id=:c AND candidate_id=:u",
            c=nt_co, u=nt_emp,
        )
        check("38-01. Note migrated", bool(note_rows))
        if note_rows:
            check("38-02. Body is trimmed (no leading/trailing spaces)",
                  note_rows[0][0] == "Great candidate")
            check("38-03. created_by=NULL (Bnd-7)",
                  note_rows[0][2] is None)
            # created_at should be close to legacy ts
            ca = str(note_rows[0][1])
            check("38-04. created_at preserved from legacy (contains '2024')",
                  "2024" in ca)
    finally:
        release_conn(conn)
except Exception as e:
    fail("38-01. notes trim + created_at", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §39 Partial UNIQUE index: multiple NULLs allowed
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        mi_co  = _user(conn, "co")
        mi_e1  = _user(conn)
        mi_e2  = _user(conn)
        mi_j1  = _job(conn, mi_co)
        mi_j2  = _job(conn, mi_co)
        conn.run("BEGIN")
        # Two entries without application_id
        _pipeline_upsert_entry(conn, company_id=mi_co, candidate_id=mi_e1, job_id=mi_j1,
                                stage="new", source="migration")
        _pipeline_upsert_entry(conn, company_id=mi_co, candidate_id=mi_e2, job_id=mi_j2,
                                stage="new", source="migration")
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    _migrate_partial_unique_application_id()
    check("39-01. Index created with two NULL application_ids (no unique violation)", True)

    conn = get_conn()
    try:
        idx_rows = conn.run(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename='job_pipeline_entries' AND indexname='uq_jpe_application_id'"
        )
        check("39-02. uq_jpe_application_id index exists", bool(idx_rows))
    finally:
        release_conn(conn)
except Exception as e:
    fail("39-01. multiple NULLs in index", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §40 Partial UNIQUE index: rejects duplicate application_id → BlockingConflictError
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        dup_co  = _user(conn, "co")
        dup_emp = _user(conn)
        dup_j1  = _job(conn, dup_co)
        dup_j2  = _job(conn, dup_co)
        dup_app = _app(conn, dup_j1, dup_emp, "pending")
        conn.run("BEGIN")
        # Insert two entries with the SAME application_id (corrupt state)
        conn.run(
            "INSERT INTO job_pipeline_entries "
            "(company_id, candidate_id, job_id, application_id, stage, source) "
            "VALUES (:c, :u, :j1, :app, 'new', 'application')",
            c=dup_co, u=dup_emp, j1=dup_j1, app=dup_app,
        )
        # Second entry for different job but same app (should never happen in real life)
        conn.run(
            "INSERT INTO job_pipeline_entries "
            "(company_id, candidate_id, job_id, application_id, stage, source) "
            "VALUES (:c, :u, :j2, :app, 'new', 'application')",
            c=dup_co, u=dup_emp, j2=dup_j2, app=dup_app,
        )
        conn.run("COMMIT")
    finally:
        release_conn(conn)

    raised40 = False
    try:
        _migrate_partial_unique_application_id()
    except BlockingConflictError as bce40:
        raised40 = True
        check("40-02. report has duplicate_application_claim",
              bce40.report.get("conflicts_by_type", {}).get("duplicate_application_claim", 0) >= 1)
    except RuntimeError:
        raised40 = True
        check("40-02. RuntimeError raised (index creation rejected duplicate)", True)
    check("40-01. BlockingConflictError/RuntimeError raised on duplicate app_id",
          raised40)
except Exception as e:
    fail("40-01. index rejects duplicate application_id", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §41 source='application' updated when Pass-2 links an entry
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        sl_co  = _user(conn, "co")
        sl_emp = _user(conn)
        sl_job = _job(conn, sl_co)
        sl_app = _app(conn, sl_job, sl_emp, "pending")
        # Pass-1 style: entry with source='migration', no app_id
        conn.run("BEGIN")
        _pipeline_upsert_entry(conn, company_id=sl_co, candidate_id=sl_emp, job_id=sl_job,
                                stage="new", source="migration")
        conn.run("COMMIT")
        # Add ccjr so Pass-1 skips it (entry already exists)
        _ccjr(conn, sl_co, sl_emp, sl_job, "saved")
    finally:
        release_conn(conn)

    run_pipeline_backfill(dry_run=False)

    conn = get_conn()
    try:
        row41 = _entry(conn, sl_co, sl_emp, sl_job)
        check("41-01. application_id linked by Pass-2", row41 and row41[3] == sl_app)
        check("41-02. source updated to 'application' (Bnd-2)",
              row41 and row41[2] == "application")
    finally:
        release_conn(conn)
except Exception as e:
    fail("41-01. source updated to application on link", e)

# ═══════════════════════════════════════════════════════════════════════════════
# §42 stage_source_disagreement detected in dry_run
#     Correct definition: CCJR.candidate_status maps to different stage than
#     JA.status for the same (company, candidate, job) triple.
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn = get_conn()
    try:
        sd_co  = _user(conn, "co")
        sd_emp = _user(conn)
        sd_job = _job(conn, sd_co)
        # JA status 'pending' → maps to 'new'
        sd_app = _app(conn, sd_job, sd_emp, "pending")
        # CCJR candidate_status 'shortlisted' → maps to 'shortlisted' ≠ 'new'
        _ccjr(conn, sd_co, sd_emp, sd_job, "shortlisted")
    finally:
        release_conn(conn)

    dr42 = pipeline_backfill_dry_run()
    check("42-01. stage_source_disagreement detected (CCJR vs JA)",
          dr42["conflicts_by_type"].get("stage_source_disagreement", 0) >= 1)
except Exception as e:
    fail("42-01. stage_source_disagreement", e)


# ═══════════════════════════════════════════════════════════════════════════════
# §43 update_candidate_job_status: CCJR not found → returns False, no pipeline change
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn43 = get_conn()
    try:
        cj43_co  = _user(conn43, "co")
        cj43_emp = _user(conn43)
        cj43_job = _job(conn43, cj43_co)
        # Create a pipeline entry WITHOUT a CCJR row
        conn43.run("BEGIN")
        _pipeline_upsert_entry(conn43, company_id=cj43_co, candidate_id=cj43_emp,
                               job_id=cj43_job, stage="new", source="migration")
        conn43.run("COMMIT")
    finally:
        release_conn(conn43)

    # No CCJR row exists → should return False without touching pipeline
    result43 = update_candidate_job_status(
        company_id=cj43_co, candidate_id=cj43_emp, job_id=cj43_job,
        candidate_status="shortlisted"
    )
    check("43-01. update_candidate_job_status returns False when CCJR not found",
          result43 is False)

    # Pipeline entry stage must not have changed
    conn43b = get_conn()
    try:
        row43 = _entry(conn43b, cj43_co, cj43_emp, cj43_job)
        check("43-02. Pipeline entry stage unchanged when CCJR not found",
              row43 is not None and row43[1] == "new")
    finally:
        release_conn(conn43b)
except Exception as e:
    fail("43-01. CCJR not found returns False", e)


# ═══════════════════════════════════════════════════════════════════════════════
# §44 source normalization: Pass-2 sets source='application' on already-linked entry
#     An entry with matching application_id but source='migration' must be normalized.
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn44 = get_conn()
    try:
        cj44_co  = _user(conn44, "co")
        cj44_emp = _user(conn44)
        cj44_job = _job(conn44, cj44_co)
        cj44_app = _app(conn44, cj44_job, cj44_emp, "pending")
        # Manually create an entry with source='migration' but already linked
        conn44.run("BEGIN")
        conn44.run(
            "INSERT INTO job_pipeline_entries "
            "(company_id, candidate_id, job_id, application_id, stage, source) "
            "VALUES (:c, :u, :j, :a, 'new', 'migration')",
            c=cj44_co, u=cj44_emp, j=cj44_job, a=cj44_app,
        )
        conn44.run("COMMIT")
    finally:
        release_conn(conn44)

    # run_pipeline_backfill in dry_run=False should normalize the source
    run_pipeline_backfill(dry_run=False)

    conn44b = get_conn()
    try:
        row44 = _entry(conn44b, cj44_co, cj44_emp, cj44_job)
        check("44-01. source normalized to 'application' on already-linked entry",
              row44 is not None and row44[2] == "application",
              f"source={row44[2] if row44 else 'no entry'}")
    finally:
        release_conn(conn44b)
except Exception as e:
    fail("44-01. source normalization", e)


# ═══════════════════════════════════════════════════════════════════════════════
# §45 update_application_status: initial_event_reason='application_status_changed'
#     After calling update_application_status, the pipeline stage event's reason
#     must contain 'application_status_changed'.
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    from auth import update_application_status

    conn45 = get_conn()
    try:
        cj45_co  = _user(conn45, "co")
        cj45_emp = _user(conn45)
        cj45_job = _job(conn45, cj45_co)
        cj45_app = _app(conn45, cj45_job, cj45_emp, "pending")
        # Create a saved-candidate record so update_application_status can find it
        conn45.run(
            "INSERT INTO company_saved_candidates "
            "(company_id, candidate_id, job_id, status) "
            "VALUES (:c, :u, :j, 'saved')",
            c=cj45_co, u=cj45_emp, j=cj45_job,
        )
        conn45.run(
            "INSERT INTO company_candidate_job_refs "
            "(company_id, candidate_id, job_id, candidate_status) "
            "VALUES (:c, :u, :j, NULL)",
            c=cj45_co, u=cj45_emp, j=cj45_job,
        )
    finally:
        release_conn(conn45)

    update_application_status(cj45_app, "viewed", actor_id=cj45_co)

    conn45b = get_conn()
    try:
        entry45 = _entry(conn45b, cj45_co, cj45_emp, cj45_job)
        events45 = _events(conn45b, entry45[0]) if entry45 else []
        check("45-01. Pipeline stage event exists after update_application_status",
              len(events45) >= 1)
        reasons45 = [e[2] for e in events45]
        check("45-02. Event reason contains 'application_status_changed'",
              any("application_status_changed" in (r or "") for r in reasons45),
              f"reasons={reasons45}")
    finally:
        release_conn(conn45b)
except Exception as e:
    fail("45-01. initial_event_reason=application_status_changed", e)


# ═══════════════════════════════════════════════════════════════════════════════
# §46 promote_application_to_shortlist: response candidate dict has action='unchanged'
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    conn46 = get_conn()
    try:
        cj46_co  = _user(conn46, "co")
        cj46_emp = _user(conn46)
        cj46_job = _job(conn46, cj46_co)
        cj46_app = _app(conn46, cj46_job, cj46_emp, "pending")
        # Create company_saved_candidates so promote can find the candidate
        conn46.run(
            "INSERT INTO company_saved_candidates "
            "(company_id, candidate_id, job_id, status) "
            "VALUES (:c, :u, :j, 'saved')",
            c=cj46_co, u=cj46_emp, j=cj46_job,
        )
    finally:
        release_conn(conn46)

    resp46 = promote_application_to_shortlist(
        app_id=cj46_app,
        company_id=cj46_co,
    )
    cand46 = resp46.get("candidate", {})
    check("46-01. promote_application_to_shortlist response has 'candidate' dict",
          isinstance(cand46, dict))
    check("46-02. candidate dict has 'action' key",
          "action" in cand46, f"candidate={cand46}")
    check("46-03. candidate['action'] == 'unchanged'",
          cand46.get("action") == "unchanged", f"action={cand46.get('action')}")
except Exception as e:
    fail("46-01. candidate.action='unchanged'", e)


# ═══════════════════════════════════════════════════════════════════════════════
# §47 _migrate_partial_unique_application_id: pg_index + pg_get_expr verification
#     After index creation, UNIQUE property and IS NOT NULL predicate must be confirmed.
# ═══════════════════════════════════════════════════════════════════════════════
_setup()
try:
    _migrate_partial_unique_application_id()

    conn47 = get_conn()
    try:
        idx_rows = conn47.run(
            "SELECT i.indisunique, pg_get_expr(i.indpred, i.indrelid) "
            "FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indrelid "
            "JOIN pg_class ic ON ic.oid = i.indexrelid "
            "WHERE c.relname = 'job_pipeline_entries' "
            "AND ic.relname = 'uq_jpe_application_id'"
        )
        check("47-01. uq_jpe_application_id index exists",
              bool(idx_rows), f"rows={idx_rows}")
        if idx_rows:
            is_unique = bool(idx_rows[0][0])
            predicate = (idx_rows[0][1] or "").lower()
            check("47-02. Index is UNIQUE (indisunique=true)",
                  is_unique, f"indisunique={idx_rows[0][0]}")
            check("47-03. Index predicate contains 'application_id'",
                  "application_id" in predicate, f"predicate={predicate}")
            check("47-04. Index predicate contains 'not null' or 'is not null'",
                  "not null" in predicate or "is not null" in predicate,
                  f"predicate={predicate}")
    finally:
        release_conn(conn47)
except Exception as e:
    fail("47-01. pg_index+pg_get_expr verification", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
passed = sum(1 for _, s, _ in results if s == PASS)
failed = len(results) - passed
print()
print("=" * 60)
print(f"Integration Results: {passed}/{len(results)} passed, {failed} failed")
if failed:
    print("\nFailed:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ❌  {name}" + (f"  [{detail}]" if detail else ""))
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
