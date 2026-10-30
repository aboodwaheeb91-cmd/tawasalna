"""admin_staff.py — Admin staff accounts + admin two-step login (task 8.4b · docs/rules/admin-staff.md ·
SYSTEMS_INDEX §25h).

The ONE reader / writer of the admin account tables. server.py (admin_login · check_admin) calls it.
  Tables (migrate_admin_staff — critical startup migration):
    admin_roles           roles the owner defines: name + perms (text[])
    admin_staff           one row per staff member: email (lower) · password_hash · role · allow / deny perms ·
                          status invited | active | suspended · MFA secret (encrypted) · session_version
    admin_owner_mfa       ONE row (id = 1): the owner's MFA secret (encrypted) · enabled_at · last_step ·
                          session_version · reset_on (the ADMIN_MFA_RESET day already applied)
    admin_recovery_codes  subject 'owner' | 'staff:<id>' · SHA-256 of the code · used_at (each code once)
    admin_invites         token hash · staff · kind invite | mfa_reset — table only here, used by 8.4c
  Roles + staff management (task 8.4c-2a1): seed_default_roles (once ever) · list / create / update / delete_role ·
  list_staff · set_access · set_suspended — the owner's writes, each in one transaction (server.py checks
  staff.manage + step-up first and sends the emails after the commit).
  TOTP (RFC 6238, stdlib): SHA-1 · 6 digits · 30 s · ±1 step · a step is accepted once (last_step only grows).
  Secrets at rest: Fernet with a key derived (SHA-256) from ADMIN_MFA_KEY (≥ 32 chars) — missing / short →
  mfa_key_ok() False → the admin login answers 503.
  Effective staff perms = (role perms ∪ allow) − deny, kept to admin_perms.GRANTABLE — read from the DB on
  every admin request (staff_session), never from the token.
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

from auth import db_conn
import admin_perms

TOTP_STEP = 30
TOTP_DIGITS = 6
TOTP_SKEW = 1            # ± steps accepted around now
RECOVERY_COUNT = 10
MFA_KEY_MIN = 32
ISSUER = "Tawasalna"
OWNER = "owner"
STAFF_PREFIX = "staff:"
_RC_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # no 0 / o / 1 / l / i — read back without mistakes
_RC_LEN = 10
_now = time.time   # the TOTP clock (tests move it)

SCHEMA_SQL = (
    """CREATE TABLE IF NOT EXISTS admin_roles (
        id         SERIAL PRIMARY KEY,
        name       TEXT NOT NULL UNIQUE,
        perms      TEXT[] NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS admin_staff (
        id             SERIAL PRIMARY KEY,
        email          TEXT NOT NULL CONSTRAINT admin_staff_email_lower_chk CHECK (email = lower(email)),
        name           TEXT NOT NULL DEFAULT '',
        password_hash  TEXT NULL,
        role_id        INTEGER NULL REFERENCES admin_roles(id) ON DELETE SET NULL,
        allow_perms    TEXT[] NOT NULL DEFAULT '{}',
        deny_perms     TEXT[] NOT NULL DEFAULT '{}',
        status         TEXT NOT NULL DEFAULT 'invited'
                       CONSTRAINT admin_staff_status_chk CHECK (status IN ('invited', 'active', 'suspended')),
        mfa_secret_enc TEXT NULL,
        mfa_enabled_at TIMESTAMPTZ NULL,
        mfa_last_step  BIGINT NULL,
        session_version INTEGER NOT NULL DEFAULT 1,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_login_at  TIMESTAMPTZ NULL
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS admin_staff_email_uq ON admin_staff (lower(email))",
    """CREATE TABLE IF NOT EXISTS admin_owner_mfa (
        id              INTEGER PRIMARY KEY CONSTRAINT admin_owner_mfa_one_row CHECK (id = 1),
        secret_enc      TEXT NULL,
        enabled_at      TIMESTAMPTZ NULL,
        last_step       BIGINT NULL,
        session_version INTEGER NOT NULL DEFAULT 1,
        reset_on        DATE NULL
    )""",
    "INSERT INTO admin_owner_mfa (id) VALUES (1) ON CONFLICT (id) DO NOTHING",
    """CREATE TABLE IF NOT EXISTS admin_recovery_codes (
        id        SERIAL PRIMARY KEY,
        subject   TEXT NOT NULL CONSTRAINT admin_recovery_subject_chk CHECK (subject ~ '^(owner|staff:[0-9]+)$'),
        code_hash TEXT NOT NULL,
        used_at   TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
    "CREATE INDEX IF NOT EXISTS admin_recovery_codes_subject_idx ON admin_recovery_codes (subject)",
    """CREATE TABLE IF NOT EXISTS admin_invites (
        id         SERIAL PRIMARY KEY,
        token_hash TEXT NOT NULL UNIQUE,
        staff_id   INTEGER NOT NULL REFERENCES admin_staff(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL CONSTRAINT admin_invites_kind_chk CHECK (kind IN ('invite', 'mfa_reset')),
        expires_at TIMESTAMPTZ NOT NULL,
        used_at    TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""",
)


def migrate_admin_staff():
    """Idempotent (task 8.4b). Critical: check_admin reads admin_owner_mfa / admin_staff on every admin request."""
    with db_conn() as conn:
        for sql in SCHEMA_SQL:
            conn.run(sql)


# ── TOTP (RFC 6238 over RFC 4226) ──
def totp_code(key: bytes, counter: int, digits: int = TOTP_DIGITS, algo: str = "sha1") -> str:
    mac = hmac.new(key, struct.pack(">Q", int(counter)), algo).digest()
    off = mac[-1] & 0x0F
    n = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(n).zfill(digits)


def _b32(secret: str) -> bytes:
    s = str(secret or "").strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def new_secret() -> str:
    """160-bit random secret, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def is_totp_format(code: str) -> bool:
    return len(code) == TOTP_DIGITS and code.isascii() and code.isdigit()


def match_step(secret: str, code: str, now: float = None):
    """The time step (now ± TOTP_SKEW) whose code equals `code`, or None. Replay is the caller's job (last_step)."""
    code = str(code or "").strip()
    if not is_totp_format(code):
        return None
    try:
        key = _b32(secret)
    except Exception:
        return None
    step = int((_now() if now is None else now) // TOTP_STEP)
    hit = None
    for s in range(step - TOTP_SKEW, step + TOTP_SKEW + 1):
        if hmac.compare_digest(totp_code(key, s), code):
            hit = s
    return hit


def otpauth_uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}", safe="")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER, safe='')}"
            f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_STEP}")


# ── secret encryption (ADMIN_MFA_KEY) ──
def _mfa_key() -> str:
    return os.environ.get("ADMIN_MFA_KEY", "").strip()


def mfa_key_ok() -> bool:
    return len(_mfa_key()) >= MFA_KEY_MIN


def _fernet():
    from cryptography.fernet import Fernet
    if not mfa_key_ok():
        raise RuntimeError("ADMIN_MFA_KEY is not configured")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(_mfa_key().encode("utf-8")).digest()))


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt(token: str):
    """→ the secret, or None (no token · wrong key · tampered)."""
    from cryptography.fernet import InvalidToken
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError):
        return None


# ── recovery codes ──
def new_recovery_codes() -> list:
    out = []
    for _ in range(RECOVERY_COUNT):
        raw = "".join(secrets.choice(_RC_ALPHABET) for _ in range(_RC_LEN))
        out.append(raw[:5] + "-" + raw[5:])
    return out


def recovery_hash(code: str) -> str:
    norm = "".join(ch for ch in str(code or "").lower() if ch not in "- ")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _replace_recovery_codes(conn, subject: str) -> list:
    codes = new_recovery_codes()
    conn.run("DELETE FROM admin_recovery_codes WHERE subject = :s", s=subject)
    for c in codes:
        conn.run("INSERT INTO admin_recovery_codes (subject, code_hash) VALUES (:s, :h)", s=subject, h=recovery_hash(c))
    return codes


def owner_new_recovery_codes(sv: int):
    """Task 8.4c-1 — a new set of 10 owner recovery codes (the old ones void) → the codes (shown once), or None
    (owner MFA not bound / session_version changed). The owner row is locked first, so two parallel calls leave
    ONE valid set (the second deletes the first one's codes after it commits)."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run("SELECT 1 FROM admin_owner_mfa WHERE id = 1 AND enabled_at IS NOT NULL "
                            "AND session_version = :sv FOR UPDATE", sv=int(sv))
            codes = _replace_recovery_codes(conn, OWNER) if rows else None
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return codes


def recovery_remaining(subject: str) -> int:
    with db_conn() as conn:
        return int(conn.run("SELECT COUNT(*) FROM admin_recovery_codes WHERE subject = :s AND used_at IS NULL",
                            s=subject)[0][0])


# ── perms ──
def effective_perms(role_perms, allow, deny) -> frozenset:
    """(role ∪ allow) − deny, only names of admin_perms.GRANTABLE (owner-only perms and "*" never survive)."""
    granted = set(role_perms or []) | set(allow or [])
    return frozenset((granted - set(deny or [])) & set(admin_perms.GRANTABLE))


def staff_id(subject: str):
    """'staff:<id>' → int id, else None."""
    if not isinstance(subject, str) or not subject.startswith(STAFF_PREFIX):
        return None
    rest = subject[len(STAFF_PREFIX):]
    return int(rest) if rest.isascii() and rest.isdigit() and len(rest) <= 9 else None


# ── owner ──
def owner_session_version() -> int:
    with db_conn() as conn:
        rows = conn.run("SELECT session_version FROM admin_owner_mfa WHERE id = 1")
    return int(rows[0][0]) if rows else 1


def owner_state() -> dict:
    with db_conn() as conn:
        conn.run("INSERT INTO admin_owner_mfa (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        r = conn.run("SELECT enabled_at, session_version FROM admin_owner_mfa WHERE id = 1")[0]
    return {"enabled": r[0] is not None, "sv": int(r[1])}


def owner_reset(today: str) -> bool:
    """ADMIN_MFA_RESET (docs/rules/admin-staff.md → owner recovery): once per `today` — clears the owner's MFA
    + recovery codes and bumps session_version (every owner session ends). True when it ran now."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            conn.run("INSERT INTO admin_owner_mfa (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
            rows = conn.run(
                "UPDATE admin_owner_mfa SET secret_enc = NULL, enabled_at = NULL, last_step = NULL, "
                "session_version = session_version + 1, reset_on = CAST(:d AS DATE) "
                "WHERE id = 1 AND reset_on IS DISTINCT FROM CAST(:d AS DATE) RETURNING 1", d=today)
            if rows:
                conn.run("DELETE FROM admin_recovery_codes WHERE subject = :s", s=OWNER)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return bool(rows)


def owner_begin_enroll():
    """No MFA bound yet → a fresh pending secret (stored encrypted) → (secret, sv); already bound → None."""
    secret = new_secret()
    with db_conn() as conn:
        rows = conn.run("UPDATE admin_owner_mfa SET secret_enc = :e, last_step = NULL "
                        "WHERE id = 1 AND enabled_at IS NULL RETURNING session_version", e=encrypt(secret))
    return (secret, int(rows[0][0])) if rows else None


def owner_confirm_enroll(code: str, sv: int, now: float = None):
    """The first code from the app binds the pending secret → the 10 recovery codes (shown once), or None."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run("SELECT secret_enc, enabled_at, session_version FROM admin_owner_mfa WHERE id = 1 FOR UPDATE")
            codes = None
            if rows and rows[0][1] is None and int(rows[0][2]) == int(sv) and rows[0][0]:
                step = match_step(decrypt(rows[0][0]) or "", code, now)
                if step is not None:
                    conn.run("UPDATE admin_owner_mfa SET enabled_at = NOW(), last_step = :s WHERE id = 1", s=step)
                    codes = _replace_recovery_codes(conn, OWNER)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return codes


# ── second factor (owner + staff) ──
_FACTOR_SQL = {
    "owner": ("SELECT secret_enc, enabled_at, session_version FROM admin_owner_mfa WHERE id = 1",
              "UPDATE admin_owner_mfa SET last_step = :s WHERE id = 1 AND session_version = :sv "
              "AND enabled_at IS NOT NULL AND (last_step IS NULL OR last_step < :s) RETURNING 1"),
    "staff": ("SELECT mfa_secret_enc, mfa_enabled_at, session_version FROM admin_staff WHERE id = :id AND status = 'active'",
              "UPDATE admin_staff SET mfa_last_step = :s WHERE id = :id AND session_version = :sv AND status = 'active' "
              "AND mfa_enabled_at IS NOT NULL AND (mfa_last_step IS NULL OR mfa_last_step < :s) RETURNING 1"),
}


def verify_second_factor(subject: str, code: str, sv: int, now: float = None):
    """TOTP (each step once) or an unused recovery code (crossed out now) for a subject whose MFA is bound and whose
    session_version is still `sv` → {"method": "totp"} | {"method": "recovery", "remaining": n}; else None."""
    sid = staff_id(subject)
    if subject != OWNER and sid is None:
        return None
    sel, upd = _FACTOR_SQL["owner" if subject == OWNER else "staff"]
    kw = {} if subject == OWNER else {"id": sid}
    code = "".join(str(code or "").split())
    with db_conn() as conn:
        rows = conn.run(sel, **kw)
        if not rows or rows[0][1] is None or int(rows[0][2]) != int(sv):
            return None
        if is_totp_format(code):
            step = match_step(decrypt(rows[0][0]) or "", code, now)
            if step is None or not conn.run(upd, s=step, sv=int(sv), **kw):
                return None
            return {"method": "totp"}
        if not code or len(code) > 32:
            return None
        if not conn.run("UPDATE admin_recovery_codes SET used_at = NOW() WHERE subject = :sub AND code_hash = :h "
                        "AND used_at IS NULL RETURNING id", sub=subject, h=recovery_hash(code)):
            return None
        left = conn.run("SELECT COUNT(*) FROM admin_recovery_codes WHERE subject = :sub AND used_at IS NULL", sub=subject)
    return {"method": "recovery", "remaining": int(left[0][0])}


# ── staff ──
def staff_for_login(email: str):
    """→ {id, password_hash, status, mfa, sv} or None. Email compared lower-case."""
    with db_conn() as conn:
        rows = conn.run("SELECT id, password_hash, status, mfa_enabled_at, session_version FROM admin_staff "
                        "WHERE lower(email) = lower(:e)", e=str(email or "").strip())
    if not rows:
        return None
    r = rows[0]
    return {"id": int(r[0]), "password_hash": r[1], "status": r[2], "mfa": r[3] is not None, "sv": int(r[4])}


def staff_session(sid: int):
    """Live state for check_admin — {sv, perms, name} for an active staff member with MFA bound, else None."""
    with db_conn() as conn:
        rows = conn.run(
            "SELECT s.status, s.session_version, s.mfa_enabled_at, s.allow_perms, s.deny_perms, r.perms, s.name "
            "FROM admin_staff s LEFT JOIN admin_roles r ON r.id = s.role_id WHERE s.id = :id", id=int(sid))
    if not rows or rows[0][0] != "active" or rows[0][2] is None:
        return None
    r = rows[0]
    return {"sv": int(r[1]), "perms": effective_perms(r[5], r[3], r[4]), "name": r[6] or ""}


def staff_mark_login(sid: int) -> None:
    with db_conn() as conn:
        conn.run("UPDATE admin_staff SET last_login_at = NOW() WHERE id = :id", id=int(sid))


# ── roles + staff management (task 8.4c-2a1 · docs/rules/admin-staff.md rule 10) ──
# The owner's writes (staff.manage + step-up — server.py checks, then calls here). Every write runs in ONE
# transaction; rows are locked role first, then staff (update_role · delete_role · set_access) — one order, no
# deadlock. A role cannot be deleted while staff use it (role_in_use): delete_role locks the role FOR UPDATE and
# set_access locks the target role FOR SHARE, so a delete and an assignment at the same moment serialise — the
# delete sees the assignment (409) or the assignment no longer finds the role (422). The FK's SET NULL never fires.
# Perm changes bump session_version only when the effective perms really changed (old tokens re-read the DB anyway).
DEFAULT_ROLES = (
    ("دعم", ("support.manage", "users.view", "message.send")),
    ("توثيق", ("kyc.review", "users.view")),
    ("محتوى", ("content.edit", "jobs.manage")),
    ("بلاغات وإشراف", ("reports.manage", "users.view")),
)
SEED_MARK = "admin_roles_seed_84c2a1"
_SEED_LOCK = 842201          # pg_advisory_xact_lock key — two boots at once seed once
STATUSES = ("invited", "active", "suspended")


class StaffError(ValueError):
    """An owner write refused on purpose → server.py answers api_error(status, code, twT admin.staff.error.<code>)."""
    def __init__(self, status: int, code: str, field: str = None):
        super().__init__(code)
        self.status, self.code, self.field = status, code, field


def seed_default_roles() -> bool:
    """The 4 ready roles — ONCE ever (app_migrations mark, claimed under an advisory lock in the same transaction):
    a role the owner deleted or edited never comes back. A name already taken is left alone. True = seeded now."""
    from auth import _migration_claim_once
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            conn.run("SELECT pg_advisory_xact_lock(:k)", k=_SEED_LOCK)
            first = _migration_claim_once(conn, SEED_MARK)
            if first:
                for name, perms in DEFAULT_ROLES:
                    conn.run("INSERT INTO admin_roles (name, perms) VALUES (:n, :p) ON CONFLICT (name) DO NOTHING",
                             n=name, p=list(perms))
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return first


def clean_perms(value, field: str) -> list:
    """A list of GRANTABLE names (sorted, no duplicates). An OWNER_ONLY perm · "*" · an unknown name · not a
    list of strings → StaffError 422 invalid_perms."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(p, str) for p in value):
        raise StaffError(422, "invalid_perms", field)
    if any(p not in admin_perms.GRANTABLE for p in value):
        raise StaffError(422, "invalid_perms", field)
    return sorted(set(value))


def clean_role_name(value, max_len: int) -> str:
    name = " ".join(value.split()) if isinstance(value, str) else ""
    if not name:
        raise StaffError(422, "invalid_name", "name")
    if len(name) > max_len:
        raise StaffError(422, "name_too_long", "name")
    return name


def _is_unique_violation(e: BaseException) -> bool:
    f = e.args[0] if getattr(e, "args", None) and isinstance(e.args[0], dict) else {}
    return f.get("C") == "23505"


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def list_roles() -> list:
    with db_conn() as conn:
        rows = conn.run("SELECT r.id, r.name, r.perms, COUNT(s.id) FROM admin_roles r "
                        "LEFT JOIN admin_staff s ON s.role_id = r.id GROUP BY r.id ORDER BY r.id")
    return [{"id": int(r[0]), "name": r[1], "perms": sorted(r[2] or []), "staff_count": int(r[3])} for r in rows]


def create_role(name: str, perms: list) -> dict:
    """name / perms already cleaned. Name taken → StaffError 409 name_taken."""
    with db_conn() as conn:
        rows = conn.run("INSERT INTO admin_roles (name, perms) VALUES (:n, :p) ON CONFLICT (name) DO NOTHING "
                        "RETURNING id", n=name, p=list(perms))
    if not rows:
        raise StaffError(409, "name_taken", "name")
    return {"id": int(rows[0][0]), "name": name, "perms": sorted(perms), "staff_count": 0}


def update_role(rid: int, name: str = None, perms: list = None):
    """Rename and / or new perms (cleaned; None = keep). → (role dict, [{"id", "email", "name"}] — the ACTIVE staff
    whose effective perms changed: they get staff_perms_changed after the commit). Every staff member whose
    effective perms changed gets session_version + 1. 404 role_not_found · 409 name_taken."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run("SELECT name, perms FROM admin_roles WHERE id = :id FOR UPDATE", id=int(rid))
            if not rows:
                raise StaffError(404, "role_not_found")
            old_perms = rows[0][1] or []
            new_name = rows[0][0] if name is None else name
            new_perms = list(old_perms) if perms is None else list(perms)
            try:
                conn.run("UPDATE admin_roles SET name = :n, perms = :p WHERE id = :id",
                         n=new_name, p=new_perms, id=int(rid))
            except Exception as e:
                if not _is_unique_violation(e):
                    raise
                raise StaffError(409, "name_taken", "name")
            notify = []
            staff = conn.run("SELECT id, email, name, status, allow_perms, deny_perms FROM admin_staff "
                             "WHERE role_id = :id ORDER BY id FOR UPDATE", id=int(rid))
            for sid, email, sname, status, allow, deny in staff:
                if effective_perms(old_perms, allow, deny) == effective_perms(new_perms, allow, deny):
                    continue
                conn.run("UPDATE admin_staff SET session_version = session_version + 1 WHERE id = :id", id=sid)
                if status == "active":
                    notify.append({"id": int(sid), "email": email, "name": sname or ""})
            count = len(staff)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return {"id": int(rid), "name": new_name, "perms": sorted(new_perms), "staff_count": count}, notify


def delete_role(rid: int) -> None:
    """404 role_not_found · 409 role_in_use while any staff member (any status) has it — move them first."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            if not conn.run("SELECT 1 FROM admin_roles WHERE id = :id FOR UPDATE", id=int(rid)):
                raise StaffError(404, "role_not_found")
            if conn.run("SELECT 1 FROM admin_staff WHERE role_id = :id LIMIT 1", id=int(rid)):
                raise StaffError(409, "role_in_use")
            conn.run("DELETE FROM admin_roles WHERE id = :id", id=int(rid))
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise


_STAFF_SELECT = ("SELECT s.id, s.name, s.email, s.status, s.role_id, r.name, r.perms, s.allow_perms, s.deny_perms, "
                 "s.mfa_enabled_at, s.last_login_at FROM admin_staff s LEFT JOIN admin_roles r ON r.id = s.role_id ")


def _staff_row(r) -> dict:
    """The owner's view of one staff member — never password_hash / mfa_secret_enc / any hash."""
    return {"id": int(r[0]), "name": r[1] or "", "email": r[2], "status": r[3],
            "role": {"id": int(r[4]), "name": r[5]} if r[4] is not None else None,
            "allow": sorted(r[7] or []), "deny": sorted(r[8] or []),
            "effective_perms": sorted(effective_perms(r[6], r[7], r[8])),
            "mfa_bound": r[9] is not None, "last_login_at": _iso(r[10])}


def list_staff() -> list:
    with db_conn() as conn:
        rows = conn.run(_STAFF_SELECT + "ORDER BY s.id")
    return [_staff_row(r) for r in rows]


def _get_staff(conn, sid: int) -> dict:
    rows = conn.run(_STAFF_SELECT + "WHERE s.id = :id", id=int(sid))
    return _staff_row(rows[0])


def set_access(sid: int, role_id, allow: list, deny: list):
    """New role (None = no role) + allow / deny (cleaned). → (staff dict, notify) — notify = True when the
    effective perms changed AND the staff member is active (staff_perms_changed after the commit); a change bumps
    session_version. 404 staff_not_found · 422 invalid_role (no such role — or deleted at the same moment)."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            new_role_perms = []
            if role_id is not None:
                rows = conn.run("SELECT perms FROM admin_roles WHERE id = :id FOR SHARE", id=int(role_id))
                if not rows:
                    raise StaffError(422, "invalid_role", "role_id")
                new_role_perms = rows[0][0] or []
            rows = conn.run("SELECT s.status, r.perms, s.allow_perms, s.deny_perms FROM admin_staff s "
                            "LEFT JOIN admin_roles r ON r.id = s.role_id WHERE s.id = :id FOR UPDATE OF s", id=int(sid))
            if not rows:
                raise StaffError(404, "staff_not_found")
            status, old_role_perms, old_allow, old_deny = rows[0]
            changed = effective_perms(old_role_perms, old_allow, old_deny) != effective_perms(new_role_perms, allow, deny)
            conn.run("UPDATE admin_staff SET role_id = :r, allow_perms = :a, deny_perms = :d, "
                     "session_version = session_version + :b WHERE id = :id",
                     r=None if role_id is None else int(role_id), a=list(allow), d=list(deny),
                     b=1 if changed else 0, id=int(sid))
            out = _get_staff(conn, sid)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return out, bool(changed and status == "active")


def set_suspended(sid: int, suspended: bool):
    """suspend → status suspended · restore (from suspended only, else 409 not_suspended) → active when the password
    and the authenticator are bound, else invited. Both bump session_version (every token dies; restore never
    revives one). → (staff dict, changed) — changed = the status really moved (the email goes after the commit)."""
    with db_conn() as conn:
        conn.run("BEGIN")
        try:
            rows = conn.run("SELECT status, password_hash IS NOT NULL AND mfa_enabled_at IS NOT NULL "
                            "FROM admin_staff WHERE id = :id FOR UPDATE", id=int(sid))
            if not rows:
                raise StaffError(404, "staff_not_found")
            status, ready = rows[0]
            if suspended:
                new = "suspended"
            elif status != "suspended":
                raise StaffError(409, "not_suspended")
            else:
                new = "active" if ready else "invited"
            conn.run("UPDATE admin_staff SET status = :s, session_version = session_version + 1 WHERE id = :id",
                     s=new, id=int(sid))
            out = _get_staff(conn, sid)
            conn.run("COMMIT")
        except Exception:
            conn.run("ROLLBACK")
            raise
    return out, status != new
