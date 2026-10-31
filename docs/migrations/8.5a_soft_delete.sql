-- Task 8.5a — soft account delete (F27) — docs/rules/account-deletion.md · SYSTEMS_INDEX §25i
-- Run by hand on production (Supabase SQL editor) BEFORE the merge. Safe for the code running now: it never reads
-- the new columns (all NULL = nobody deleted). The startup migration (account_deletion.migrate_account_deletion,
-- critical) runs the same idempotent statements.
--
-- ── 1) READ-ONLY check — run first, change nothing (one query: the SQL editor shows the last result only) ──
-- expected BEFORE: every column count = 0 · kind_chk = NULL · deleted_idx = NULL
-- SELECT 'deleted_at' AS item, COUNT(*)::text AS value FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'deleted_at'
-- UNION ALL SELECT 'deleted_by', COUNT(*)::text FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'deleted_by'
-- UNION ALL SELECT 'deleted_kind', COUNT(*)::text FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'deleted_kind'
-- UNION ALL SELECT 'deleted_reason', COUNT(*)::text FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'deleted_reason'
-- UNION ALL SELECT 'kind_chk', COALESCE((SELECT pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conrelid = 'public.users'::regclass AND conname = 'users_deleted_kind_chk'), 'NULL')
-- UNION ALL SELECT 'deleted_idx', COALESCE(to_regclass('public.idx_users_deleted')::text, 'NULL')
-- UNION ALL SELECT 'users_total', COUNT(*)::text FROM users;

-- ── 2) The change (one transaction, idempotent) ──
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_by TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_kind TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_reason TEXT;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_deleted_kind_chk'
                 AND conrelid = 'public.users'::regclass) THEN
    ALTER TABLE users ADD CONSTRAINT users_deleted_kind_chk
      CHECK (deleted_kind IS NULL OR deleted_kind IN ('admin', 'self'));
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_users_deleted ON users(id) WHERE deleted_at IS NOT NULL;
COMMIT;

-- ── 3) After: the check above again → every column count = 1 · kind_chk = CHECK (...) · deleted_idx = idx_users_deleted
