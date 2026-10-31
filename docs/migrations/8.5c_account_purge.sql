-- Task 8.5c — final account purge after account_purge_days (F27) — docs/rules/account-deletion.md · SYSTEMS_INDEX §25i
-- Run by hand on production (Supabase SQL editor) BEFORE the merge. Safe for the code running now: it never reads
-- the new table / column (empty = nothing purged). The startup migration (account_purge.migrate_account_purge,
-- critical) runs the same idempotent statements.
--
-- ── 1) READ-ONLY check — run first, change nothing (one query: the SQL editor shows the last result only) ──
-- expected BEFORE: purged_at = 0 · account_purge = NULL · due_idx = NULL · purged_idx = NULL ·
--                  deleted_older_30d = how many accounts the first daily run will claim
-- SELECT 'purged_at' AS item, COUNT(*)::text AS value FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'purged_at'
-- UNION ALL SELECT 'account_purge', COALESCE(to_regclass('public.account_purge')::text, 'NULL')
-- UNION ALL SELECT 'due_idx', COALESCE(to_regclass('public.idx_account_purge_due')::text, 'NULL')
-- UNION ALL SELECT 'purged_idx', COALESCE(to_regclass('public.idx_users_purged')::text, 'NULL')
-- UNION ALL SELECT 'deleted_total', COUNT(*)::text FROM users WHERE deleted_at IS NOT NULL
-- UNION ALL SELECT 'deleted_older_30d', COUNT(*)::text FROM users
--  WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '30 days';

-- ── 2) The change (one transaction, idempotent) ──
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS purged_at TIMESTAMPTZ;
CREATE TABLE IF NOT EXISTS account_purge (
  user_id BIGINT PRIMARY KEY REFERENCES users(id),
  stage TEXT NOT NULL DEFAULT 'files' CHECK (stage IN ('files', 'db', 'done')),
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_account_purge_due ON account_purge (next_attempt_at) WHERE stage <> 'done';
CREATE INDEX IF NOT EXISTS idx_users_purged ON users(id) WHERE purged_at IS NOT NULL;
ALTER TABLE account_purge ENABLE ROW LEVEL SECURITY;   -- same as rls_lockdown (the app role owns the table)
REVOKE ALL ON account_purge FROM anon, authenticated;
COMMIT;

-- ── 3) After: the check above again → purged_at = 1 · account_purge = account_purge ·
--               due_idx = idx_account_purge_due · purged_idx = idx_users_purged
