-- Task 8.7 — certificate PDFs of courses / education — docs/rules/certificates.md · SYSTEMS_INDEX §29b
-- Run by hand on production (Supabase SQL editor) BEFORE the merge. Safe for the code running now: it never reads
-- the new column or the new bucket. The startup migration (cert_access.migrate_certificates, critical) runs the
-- same idempotent ALTERs; the bucket is created only here (storage schema — not touched by the app).
--
-- ── 1) READ-ONLY check — run first, change nothing (one query: the SQL editor shows the last result only) ──
-- expected BEFORE: courses_path = 0 · education_path = 0 · bucket = NULL
-- SELECT 'courses_path' AS item, COUNT(*)::text AS value FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'courses' AND column_name = 'certificate_path'
-- UNION ALL SELECT 'education_path', COUNT(*)::text FROM information_schema.columns
--  WHERE table_schema = 'public' AND table_name = 'education' AND column_name = 'certificate_path'
-- UNION ALL SELECT 'bucket', COALESCE((SELECT 'public=' || public::text FROM storage.buckets WHERE id = 'cert-docs'), 'NULL')
-- UNION ALL SELECT 'courses_with_legacy_url', COUNT(*)::text FROM courses
--  WHERE certificate_url IS NOT NULL AND certificate_url <> '';

-- ── 2) The change (one transaction, idempotent) ──
BEGIN;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS certificate_path TEXT NULL;
ALTER TABLE education ADD COLUMN IF NOT EXISTS certificate_path TEXT NULL;
-- Private bucket: no public URL; the server signs short links (GET /certificates/{kind}/{id}/view) with the service
-- key. PDF only, 5 MB (= LIMITS["cert_max_bytes"]) — the server checks both first; the bucket is a second wall.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('cert-docs', 'cert-docs', false, 5242880, ARRAY['application/pdf'])
ON CONFLICT (id) DO UPDATE SET public = false, file_size_limit = 5242880, allowed_mime_types = ARRAY['application/pdf'];
COMMIT;
-- No storage.objects policy for anon / authenticated on cert-docs: only the service key (the app server) reads /
-- writes / signs. ❌ never `public = true` · ❌ never a SELECT policy for anon / authenticated on this bucket.

-- ── 3) After: the check above again → courses_path = 1 · education_path = 1 · bucket = public=false
