-- Task 7.2a — support system: stage A (expand) — docs/rules/support.md → فترة الانتقال · ARCHITECTURE.md §81
-- Run by hand on production (Supabase SQL editor) BEFORE the merge. Old + new values both allowed; the code
-- after the merge writes the new values only (status 'new' written explicitly — the default stays 'open'
-- until stage B). The startup code never alters these constraints (support.migrate_support = CREATE … IF
-- NOT EXISTS only). rls_lockdown (last startup migration) also covers support_guest_access on every start.
--
-- ── READ-ONLY check — run first, change nothing ─────────────────────────────
-- expected: support_tickets_category_chk + support_tickets_status_chk present (the 7.1 values) ·
--           details / faq_id / legacy_category columns = 0 rows · guest_access = NULL
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conrelid = 'public.support_tickets'::regclass AND conname IN ('support_tickets_category_chk', 'support_tickets_status_chk');
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name = 'support_tickets' AND column_name IN ('details', 'faq_id', 'legacy_category');
-- SELECT to_regclass('public.support_guest_access') AS guest_access;
-- SELECT status, category, COUNT(*) FROM support_tickets GROUP BY 1, 2 ORDER BY 1, 2;

BEGIN;
ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_category_chk;
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_category_chk CHECK (category IN ('account','profile','jobs','technical','complaint','other','verification','education','general'));
ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_status_chk;
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_status_chk CHECK (status IN ('open','awaiting_user','closed','new','in_review','resolved'));
ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_details_chk CHECK (jsonb_typeof(details) = 'object' AND length(details::text) <= 4000);
ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS faq_id TEXT NULL CONSTRAINT support_tickets_faq_chk CHECK (faq_id ~ '^[a-z0-9_]{1,64}$');
ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS legacy_category TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_support_tickets_guest_email ON support_tickets (guest_email) WHERE user_id IS NULL;
CREATE TABLE IF NOT EXISTS support_guest_access (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE CONSTRAINT support_guest_access_hash_chk CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NULL,
  last_used_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_support_guest_access_ticket ON support_guest_access (ticket_id, created_at DESC);
ALTER TABLE support_guest_access ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON support_guest_access FROM anon, authenticated;
REVOKE ALL ON SEQUENCE support_guest_access_id_seq FROM anon, authenticated;
COMMIT;
