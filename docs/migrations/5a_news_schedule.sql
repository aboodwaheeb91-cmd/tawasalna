-- Phase 5a — news display window (docs/SYSTEMS_INDEX.md §25h · ARCHITECTURE.md §79)
-- Applied by hand on production (Supabase SQL editor) BEFORE the PR is merged — the new code reads
-- starts_at / ends_at in /home/feed, /admin/news and /news/banner. The same DDL runs idempotently at
-- server start (server.py → _migrate_news_posts), so running it twice changes nothing.

-- ── 1) READ-ONLY check — run first, changes nothing ──────────────────────────
-- expected before: news_table = news_posts · window_cols = 0 · window_chk = 0 · news_rows = any number
SELECT to_regclass('public.news_posts')                                AS news_table,
       (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'news_posts'
           AND column_name IN ('starts_at', 'ends_at'))                AS window_cols,
       (SELECT COUNT(*) FROM pg_constraint
         WHERE conname = 'news_posts_window_chk'
           AND conrelid = 'public.news_posts'::regclass)               AS window_chk,
       (SELECT COUNT(*) FROM news_posts)                               AS news_rows;

-- ── 2) Apply (one transaction) ──────────────────────────────────────────────
BEGIN;

ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ NULL;
ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS ends_at   TIMESTAMPTZ NULL;

-- fixed name; added only when missing (safe to re-run). Existing rows: both NULL → always valid.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'news_posts_window_chk'
                     AND conrelid = 'public.news_posts'::regclass) THEN
        ALTER TABLE news_posts ADD CONSTRAINT news_posts_window_chk
            CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at);
    END IF;
END $$;

COMMIT;

-- ── 3) Verify ──────────────────────────────────────────────────────────────
-- expected after: window_cols = 2 · window_chk = 1
SELECT (SELECT COUNT(*) FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'news_posts'
           AND column_name IN ('starts_at', 'ends_at'))                AS window_cols,
       (SELECT COUNT(*) FROM pg_constraint
         WHERE conname = 'news_posts_window_chk'
           AND conrelid = 'public.news_posts'::regclass)               AS window_chk;
