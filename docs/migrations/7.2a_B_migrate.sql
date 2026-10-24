-- Task 7.2a — support system: stage B (migrate + contract) — docs/rules/support.md → فترة الانتقال
-- Run by hand AFTER the latest Railway deploy is Active on the merge commit, with ONE replica (no old code
-- still writing 'open' / 'closed' / 'other'). closed_at is not changed. The backup table is dropped by hand
-- after a week (DROP TABLE support_tickets_bak_72;).
--
-- READ-ONLY check after: SELECT status, category, COUNT(*) FROM support_tickets GROUP BY 1, 2 ORDER BY 1, 2;
--   expected: only new / in_review / awaiting_user / resolved · no 'other'.

CREATE TABLE support_tickets_bak_72 AS SELECT * FROM support_tickets;
ALTER TABLE support_tickets_bak_72 ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON support_tickets_bak_72 FROM anon, authenticated;
BEGIN;
UPDATE support_tickets SET legacy_category = category WHERE legacy_category IS NULL AND (category = 'other' OR status IN ('open','closed'));
UPDATE support_tickets SET category = 'general' WHERE category = 'other';
UPDATE support_tickets t SET status = CASE WHEN EXISTS (SELECT 1 FROM support_messages m WHERE m.ticket_id = t.id AND m.author_type = 'admin') THEN 'in_review' ELSE 'new' END WHERE status = 'open';
UPDATE support_tickets SET status = 'resolved' WHERE status = 'closed';
ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_category_chk;
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_category_chk CHECK (category IN ('account','verification','profile','jobs','education','technical','complaint','general'));
ALTER TABLE support_tickets DROP CONSTRAINT support_tickets_status_chk;
ALTER TABLE support_tickets ADD CONSTRAINT support_tickets_status_chk CHECK (status IN ('new','in_review','awaiting_user','resolved'));
ALTER TABLE support_tickets ALTER COLUMN status SET DEFAULT 'new';
COMMIT;
