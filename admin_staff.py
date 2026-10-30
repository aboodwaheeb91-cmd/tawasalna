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
    """Live state for check_admin — {sv, perms} for an active staff member with MFA bound, else None."""
    with db_conn() as conn:
        rows = conn.run(
            "SELECT s.status, s.session_version, s.mfa_enabled_at, s.allow_perms, s.deny_perms, r.perms "
            "FROM admin_staff s LEFT JOIN admin_roles r ON r.id = s.role_id WHERE s.id = :id", id=int(sid))
    if not rows or rows[0][0] != "active" or rows[0][2] is None:
        return None
    r = rows[0]
    return {"sv": int(r[1]), "perms": effective_perms(r[5], r[3], r[4])}


def staff_mark_login(sid: int) -> None:
    with db_conn() as conn:
        conn.run("UPDATE admin_staff SET last_login_at = NOW() WHERE id = :id", id=int(sid))
