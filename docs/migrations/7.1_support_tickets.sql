-- Task 7.1 — support tickets (docs/rules/support.md · docs/SYSTEMS_INDEX.md §62 · ARCHITECTURE.md §81)
-- Applied by hand on production (Supabase SQL editor). The same DDL runs idempotently at server start
-- (server.py → _startup_migrations "support_tickets" = support.migrate_support, optional), so running it
-- twice changes nothing. Then rls_lockdown (last startup migration) turns RLS on for the three new tables
-- and keeps anon / authenticated without any grant — section 3 below does the same by hand.

-- ── 1) READ-ONLY checks — run first, change nothing ─────────────────────────
-- expected before: tickets = NULL · messages = NULL · guest_otp = NULL · users_table = users
SELECT to_regclass('public.support_tickets')   AS tickets,
       to_regclass('public.support_messages')  AS messages,
       to_regclass('public.support_guest_otp') AS guest_otp,
       to_regclass('public.users')             AS users_table;
-- expected: 0 rows (no other object already uses these names)
SELECT conname FROM pg_constraint WHERE conname LIKE 'support_%';
SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_support_%';

-- ── 2) Apply (one transaction) ──────────────────────────────────────────────
BEGIN;

CREATE TABLE IF NOT EXISTS support_tickets (
        id              SERIAL PRIMARY KEY,
        public_id       TEXT NOT NULL UNIQUE,
        user_id         INTEGER NULL REFERENCES users(id) ON DELETE CASCADE,
        guest_email     TEXT NULL,
        category        TEXT NOT NULL CONSTRAINT support_tickets_category_chk CHECK (category IN ('account', 'profile', 'jobs', 'technical', 'complaint', 'other')),
        status          TEXT NOT NULL DEFAULT 'open' CONSTRAINT support_tickets_status_chk CHECK (status IN ('open', 'awaiting_user', 'closed')),
        priority        TEXT NOT NULL DEFAULT 'normal' CONSTRAINT support_tickets_priority_chk CHECK (priority IN ('normal', 'high', 'urgent')),
        subject         TEXT NOT NULL CONSTRAINT support_tickets_subject_chk CHECK (length(btrim(subject)) > 0),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        closed_at       TIMESTAMPTZ NULL,
        CONSTRAINT support_tickets_owner_chk CHECK (user_id IS NOT NULL OR guest_email IS NOT NULL),
        CONSTRAINT support_tickets_guest_category_chk CHECK (user_id IS NOT NULL OR category = 'account')
    );

CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets (user_id, last_message_at DESC);

CREATE INDEX IF NOT EXISTS idx_support_tickets_inbox ON support_tickets (status, last_message_at DESC);

CREATE TABLE IF NOT EXISTS support_messages (
        id          SERIAL PRIMARY KEY,
        ticket_id   INTEGER NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
        author_type TEXT NOT NULL CONSTRAINT support_messages_author_chk CHECK (author_type IN ('user', 'guest', 'admin')),
        author_id   TEXT NULL,
        body        TEXT NOT NULL CONSTRAINT support_messages_body_chk CHECK (length(btrim(body)) > 0),
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages (ticket_id, created_at);

CREATE TABLE IF NOT EXISTS support_guest_otp (
        email      TEXT PRIMARY KEY,
        code_hash  TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        attempts   INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

COMMIT;

-- ── 3) Lock down (same as the rls_lockdown startup migration) ───────────────
ALTER TABLE support_tickets   ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_messages  ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_guest_otp ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON support_tickets, support_messages, support_guest_otp FROM anon, authenticated;
REVOKE ALL ON SEQUENCE support_tickets_id_seq, support_messages_id_seq FROM anon, authenticated;

-- ── 4) Verify ──────────────────────────────────────────────────────────────
-- expected after: 3 rows, rls = true for each
SELECT relname, relrowsecurity AS rls FROM pg_class
 WHERE relname IN ('support_tickets', 'support_messages', 'support_guest_otp') ORDER BY relname;
-- expected: 8 CHECK constraints (tickets: category · status · priority · subject · owner · guest_category ·
-- messages: author · body)
SELECT conname FROM pg_constraint WHERE conname LIKE 'support_%' AND contype = 'c' ORDER BY conname;
