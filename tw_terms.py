"""tw_terms.py — Terms acceptance at registration (task terms · SYSTEMS_INDEX §1d).

One place for:
  * TERMS_VERSION — the version of /terms + /privacy a new account accepts. Change it when the
    text of either page changes; POST /auth/register stores the value current at that moment.
  * migrate_terms_acceptance() — startup migration `terms_acceptance` (server._startup_migrations):
    two nullable columns on users, nothing else. NULL = an account created before this feature
    (no backfill — existing users are not asked to accept again in this task).
  * CONTACT_EMAIL — the contact address on /privacy + /terms (task 7.6). Code only, never a
    tw_strings key: a content.edit admin must not be able to redirect privacy requests.
"""
from auth import db_conn

TERMS_VERSION = "2026-10-23"
CONTACT_EMAIL = "support@tawasolna.com"


def migrate_terms_acceptance():
    """Idempotent: users.terms_accepted_at (when) + users.terms_version (which text)."""
    with db_conn() as conn:
        conn.run("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ")
        conn.run("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_version TEXT")
