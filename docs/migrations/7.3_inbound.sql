-- Task 7.3 — inbound support mail (Resend Receiving) — docs/rules/support.md → البريد الوارد · ARCHITECTURE.md §81
-- Run by hand on production (Supabase SQL editor) BEFORE the merge. Safe for the code running now: it never
-- reads `source`, and the new guest constraint accepts every row the old one accepted (source defaults to 'web').
-- The startup code only creates the two new tables (support.migrate_support = CREATE … IF NOT EXISTS) — it never
-- adds the column or changes a constraint. rls_lockdown (last startup migration) also covers the new tables.
--
-- ── 1) READ-ONLY check — run first, change nothing (one query: the SQL editor shows the last result only) ──
-- expected BEFORE: guest_chk = CHECK (((user_id IS NOT NULL) OR (category = 'account'::text))) ·
--                  source_column = 0 · reply_tokens = NULL · inbound_events = NULL · guest_rows_not_account = 0
-- SELECT 'guest_chk' AS item, pg_get_constraintdef(oid) AS value FROM pg_constraint
--  WHERE conrelid = 'public.support_tickets'::regclass AND conname = 'support_tickets_guest_category_chk'
-- UNION ALL SELECT 'source_column', COUNT(*)::text FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'support_tickets' AND column_name = 'source'
-- UNION ALL SELECT 'reply_tokens', COALESCE(to_regclass('public.support_reply_tokens')::text, 'NULL')
-- UNION ALL SELECT 'inbound_events', COALESCE(to_regclass('public.support_inbound_events')::text, 'NULL')
-- UNION ALL SELECT 'guest_rows_not_account', COUNT(*)::text FROM support_tickets WHERE user_id IS NULL AND category <> 'account';

-- ── 2) The change (one transaction) ──
BEGIN;
ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'web';
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_source_chk CHECK (source IN ('web', 'email'));
ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_guest_category_chk;
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_guest_category_chk
  CHECK (user_id IS NOT NULL OR category = 'account' OR source = 'email');
CREATE TABLE IF NOT EXISTS support_reply_tokens (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE CONSTRAINT support_reply_tokens_hash_chk CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_support_reply_tokens_ticket ON support_reply_tokens (ticket_id, created_at DESC);
CREATE TABLE IF NOT EXISTS support_inbound_events (
  id SERIAL PRIMARY KEY,
  svix_id TEXT NOT NULL UNIQUE,
  email_id TEXT NOT NULL UNIQUE,
  outcome TEXT NOT NULL CONSTRAINT support_inbound_events_outcome_chk CHECK (outcome ~ '^[a-z_]{1,32}$'),
  ticket_id INTEGER NULL REFERENCES support_tickets(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE support_reply_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_inbound_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON support_reply_tokens, support_inbound_events FROM anon, authenticated;
REVOKE ALL ON SEQUENCE support_reply_tokens_id_seq, support_inbound_events_id_seq FROM anon, authenticated;
COMMIT;

-- ── 3) Check AFTER (read-only, one query) ──
-- expected: guest_chk = CHECK (((user_id IS NOT NULL) OR (category = 'account'::text) OR (source = 'email'::text))) ·
--           source_chk present · source_column = 1 · reply_tokens / inbound_events = their names ·
--           source_web = 'N of N' (every existing ticket) · rls_new = 2
-- SELECT 'guest_chk' AS item, pg_get_constraintdef(oid) AS value FROM pg_constraint
--  WHERE conrelid = 'public.support_tickets'::regclass AND conname = 'support_tickets_guest_category_chk'
-- UNION ALL SELECT 'source_chk', pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conrelid = 'public.support_tickets'::regclass AND conname = 'support_tickets_source_chk'
-- UNION ALL SELECT 'source_column', COUNT(*)::text FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'support_tickets' AND column_name = 'source'
-- UNION ALL SELECT 'reply_tokens', COALESCE(to_regclass('public.support_reply_tokens')::text, 'NULL')
-- UNION ALL SELECT 'inbound_events', COALESCE(to_regclass('public.support_inbound_events')::text, 'NULL')
-- UNION ALL SELECT 'source_web', COUNT(*)::text || ' of ' || (SELECT COUNT(*) FROM support_tickets)::text
--  FROM support_tickets WHERE source = 'web'
-- UNION ALL SELECT 'rls_new', COUNT(*)::text FROM pg_class
--  WHERE relname IN ('support_reply_tokens', 'support_inbound_events') AND relrowsecurity;

-- ── 4) Rollback (only if needed — switch types.support_inbound off first). Email tickets would break the old
-- guest constraint: they are moved to 'account' first (their text stays). Run as one transaction. ──
-- BEGIN;
-- UPDATE support_tickets SET legacy_category = COALESCE(legacy_category, category), category = 'account'
--  WHERE user_id IS NULL AND category <> 'account';
-- ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_guest_category_chk;
-- ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_guest_category_chk CHECK (user_id IS NOT NULL OR category = 'account');
-- ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_source_chk;
-- ALTER TABLE support_tickets DROP COLUMN source;
-- DROP TABLE IF EXISTS support_inbound_events;
-- DROP TABLE IF EXISTS support_reply_tokens;
-- COMMIT;
-- Note: rolling back the database also needs the code before this merge (the code after it reads `source`).
