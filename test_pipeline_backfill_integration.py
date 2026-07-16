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
    _ccjr(conn, bf_co, bf_e3, bf_j2, None)             # NULL → 'new'
    _ccjr(conn, bf_co, bf_e4, bf_j3, "INVALID_X")     # unknown → conflict
    # applications (Pass 2 source)
    bf_app1 = _app(conn, bf_j1, bf_e1, "accepted")   # same triple as e1,j1 → link app_id
    bf_app2 = _app(conn, bf_j2, bf_e3, "viewed")     # same triple as e3,j2 → link app_id
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
    # e1,j1 gets app_id linked; e3,j2 gets app_id linked
    check("11-04. application_links_added >= 2", r.get("application_links_added", 0) >= 2)
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

        check("12-01. Pass-1 entry e1,j1 source='migration'",
              row_e1j1 and row_e1j1[2] == "migration")
        check("12-02. Pass-1 entry e1,j1 stage='shortlisted'",
              row_e1j1 and row_e1j1[1] == "shortlisted")
        check("12-03. Pass-1 entry e2,j1 stage='contacted'",
              row_e2j1 and row_e2j1[1] == "contacted")
        check("12-04. Pass-1 entry e3,j2 stage='new' (NULL status)",
              row_e3j2 and row_e3j2[1] == "new")
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
