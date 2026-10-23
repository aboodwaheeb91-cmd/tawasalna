-- Task 4.1 — Unified Admin Settings (docs/rules/settings.md · SYSTEMS_INDEX §25g)
-- Applied by hand on production (Supabase SQL editor). The same DDL runs idempotently at server
-- start (server.py → _startup_migrations: admin_audit_log + app_settings), so order does not matter.

-- ── 1) READ-ONLY check — run first, changes nothing ──────────────────────────
-- expected before: settings_table = NULL · audit_old_new = 0 · audit_rows = any number
SELECT to_regclass('public.app_settings')                         AS settings_table,
       (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'admin_audit_log'
           AND column_name IN ('old_value', 'new_value'))         AS audit_old_new,
       (SELECT COUNT(*) FROM admin_audit_log)                     AS audit_rows;

-- ── 2) Apply (one transaction) ──────────────────────────────────────────────
BEGIN;

-- changed values only (a value equal to the default is deleted by the server)
CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT
);

-- the existing admin audit log carries the old / new value of a settings change (NULL for other rows)
ALTER TABLE admin_audit_log ADD COLUMN IF NOT EXISTS old_value TEXT;
ALTER TABLE admin_audit_log ADD COLUMN IF NOT EXISTS new_value TEXT;

-- same lockdown as every table (task 5.0f — rls_lockdown): no anon / authenticated access
ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_settings FROM anon, authenticated;

COMMIT;

-- ── 3) Verify ──────────────────────────────────────────────────────────────
-- expected after: settings_table = app_settings · audit_old_new = 2 · rls = true
SELECT to_regclass('public.app_settings') AS settings_table,
       (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'admin_audit_log'
           AND column_name IN ('old_value', 'new_value')) AS audit_old_new,
       (SELECT relrowsecurity FROM pg_class WHERE oid = 'public.app_settings'::regclass) AS rls;
