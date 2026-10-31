"""cert_access.py — Certificate PDFs of courses / education (task 8.7 · docs/rules/certificates.md · SYSTEMS_INDEX §29b).

The ONE source for:
  can_view(viewer_id, owner_id)  who may get a view link of an account's certificate files (server-side, before every
                                 signed link and for every can_view_certificate flag in a profile reply)
  validate_pdf(data_url)         the upload check (magic «%PDF-» · decoded size ≤ cert_max_bytes · no encryption · no
                                 /JavaScript /JS /Launch /EmbeddedFile(s) /OpenAction — also inside Flate streams).
                                 The declared mime / extension decide nothing.
  object_name(uid) / name_of()   the server-made file name {uid}_cert_{12 hex}.pdf in the private bucket cert-docs —
                                 stored as "cert-docs/{name}" in courses.certificate_path / education.certificate_path
  migrate_certificates()         critical startup migration (+ docs/migrations/8.7_certificates.sql for production)

Access table (docs/rules/certificates.md): owner → always · the owner of a job (company) the person applied to:
in review → yes (job closed / expired / hidden by the admin / archived → until the closing time + the period) ·
withdrawn → no · rejected → until the decision time (pipeline_stage_events) + the period · hired → yes · any one
granting application is enough · anyone else → no · deleted / suspended / a block either way → no
(blocks_suspension.visible_sql / active_sql — never a second visibility rule).

Pure SQL builders at import time; DB functions import auth lazily (auth.py is imported by server.py first).
"""
import base64
import binascii
import re
import secrets
import zlib

import blocks_suspension as bs
import tw_settings

BUCKET = "cert-docs"
KINDS = {"course": "courses", "education": "education"}   # URL kind → table (the only two)
_NAME_RE = re.compile(r"^(\d+)_cert_[0-9a-f]{12}\.pdf$")
_DATA_URL_RE = re.compile(r"^data:[^,;]{0,100};base64,")
_FORBIDDEN_NAMES = frozenset({"JavaScript", "JS", "Launch", "EmbeddedFile", "EmbeddedFiles", "OpenAction"})
_PDF_NAME_RE = re.compile(rb"/([^\s/<>\[\]()%{}]+)")
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.S)
_INFLATE_FACTOR = 10           # a stream may inflate to at most cert_max_bytes × this (zip bomb guard → refused)


class CertificateError(Exception):
    """A refused upload — code = the API error code, message = twT key (server maps it to 422 / 413)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ── names ──

def object_name(uid: int) -> str:
    return f"{int(uid)}_cert_{secrets.token_hex(6)}.pdf"


def name_of(path, uid: int):
    """Object name when `path` is exactly cert-docs/{uid}_cert_{12hex}.pdf of this account, else None."""
    if not isinstance(path, str) or not path.startswith(BUCKET + "/"):
        return None
    name = path[len(BUCKET) + 1:]
    m = _NAME_RE.match(name)
    return name if m and int(m.group(1)) == int(uid) else None


# ── upload check ──

def _names(data: bytes) -> set:
    out = set()
    for raw in _PDF_NAME_RE.findall(data):
        # #xx escapes inside a name (/J#61vaScript = /JavaScript)
        try:
            out.add(re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw).decode("latin-1"))
        except Exception:
            continue
    return out


def _inflated_streams(data: bytes, cap: int):
    """Every stream body that inflates as zlib (FlateDecode — object streams hide dictionaries there).
    Total output over `cap` → CertificateError (never unpacked without a bound)."""
    total = 0
    for body in _STREAM_RE.findall(data):
        d = zlib.decompressobj()
        try:
            out = d.decompress(body, cap - total + 1)
        except zlib.error:
            continue          # not Flate (image / other filter) — the raw bytes were scanned already
        total += len(out)
        if total > cap or d.unconsumed_tail:
            raise CertificateError("pdf_unsafe")
        yield out


def validate_pdf(data_url) -> bytes:
    """data URL → the PDF bytes, or CertificateError(code): invalid_file · too_large · not_pdf · pdf_encrypted ·
    pdf_unsafe. Only the bytes decide (the declared type is ignored)."""
    max_bytes = int(tw_settings.limit("cert_max_bytes"))
    if not isinstance(data_url, str) or not data_url:
        raise CertificateError("invalid_file")
    m = _DATA_URL_RE.match(data_url)
    if not m:
        raise CertificateError("invalid_file")
    b64 = data_url[m.end():]
    if len(b64) > (max_bytes * 4) // 3 + 8:            # checked before decoding
        raise CertificateError("too_large")
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        raise CertificateError("invalid_file")
    if len(data) > max_bytes:
        raise CertificateError("too_large")
    if not data.startswith(b"%PDF-"):
        raise CertificateError("not_pdf")
    names = _names(data)
    for inflated in _inflated_streams(data, max_bytes * _INFLATE_FACTOR):
        names |= _names(inflated)
    if "Encrypt" in names:
        raise CertificateError("pdf_encrypted")
    if names & _FORBIDDEN_NAMES:
        raise CertificateError("pdf_unsafe")
    return data


# ── access ──

def _close_time_sql(j: str = "j") -> str:
    """When the job stopped taking the application forward (NULL = still open): closed (closed_at → expires_at →
    created_at, the earliest known — fail closed) · active with expires_at passed · hidden by the admin · archived.
    Paused = frozen, not closed (same as auth._eff_status)."""
    return (f"LEAST(CASE WHEN {j}.status NOT IN ('active', 'paused') "
            f"THEN COALESCE({j}.closed_at, {j}.expires_at, {j}.created_at) END, "
            f"CASE WHEN {j}.status = 'active' AND {j}.expires_at IS NOT NULL AND {j}.expires_at < NOW() "
            f"THEN {j}.expires_at END, {j}.admin_hidden_at, {j}.archived_at)")


def _result_sql(val: str) -> str:
    # the RESULT from any of the three sources (same rule as auth._result_status_on_job)
    return (f"COALESCE(ja.status = '{val}' OR r.candidate_status = '{val}' OR pe.stage = '{val}', FALSE)")


CAN_VIEW_SQL = (
    "SELECT EXISTS (SELECT 1 FROM users o JOIN users v ON v.id = :viewer "
    "WHERE o.id = :owner AND " + bs.active_sql("v.id") + " AND " + bs.visible_sql("o.id", "v.id") + " "
    "AND (o.id = v.id OR EXISTS ("
    "SELECT 1 FROM job_applications ja JOIN jobs j ON j.id = ja.job_id "
    "LEFT JOIN job_pipeline_entries pe ON pe.company_id = j.company_id AND pe.candidate_id = ja.user_id "
    "AND pe.job_id = ja.job_id "
    "LEFT JOIN company_candidate_job_refs r ON r.company_id = j.company_id AND r.candidate_id = ja.user_id "
    "AND r.job_id = ja.job_id "
    "WHERE ja.user_id = o.id AND j.company_id = v.id "
    "AND ja.status IS DISTINCT FROM 'withdrawn' AND pe.stage IS DISTINCT FROM 'withdrawn' "
    "AND (" + _result_sql("hired") + " "
    "OR (NOT " + _result_sql("hired") + " AND " + _result_sql("rejected") + " "
    "AND (SELECT MAX(e.created_at) FROM pipeline_stage_events e WHERE e.pipeline_entry_id = pe.id "
    "AND e.to_stage = 'rejected') + make_interval(days => :days) > NOW()) "
    "OR (NOT " + _result_sql("hired") + " AND NOT " + _result_sql("rejected") + " "
    "AND COALESCE(" + _close_time_sql("j") + " + make_interval(days => :days) > NOW(), TRUE)))"
    ")))"
)


def can_view(viewer_id, owner_id, conn=None) -> bool:
    """True when `viewer_id` may view the certificate files of `owner_id` (the access table above). Guest / bad id
    → False. The ONLY permission check for certificate files — server.py calls it before every signed link."""
    try:
        vid, oid = int(viewer_id or 0), int(owner_id or 0)
    except (TypeError, ValueError):
        return False
    if vid <= 0 or oid <= 0:
        return False
    if conn is None:
        from auth import db_conn
        with db_conn() as c:
            return can_view(vid, oid, c)
    rows = conn.run(CAN_VIEW_SQL, viewer=vid, owner=oid,
                    days=int(tw_settings.limit("cert_access_after_close_days")))
    return bool(rows and rows[0][0])


# ── migration (critical — every profile read selects certificate_path) ──

APPLY_SQL = (
    "ALTER TABLE courses ADD COLUMN IF NOT EXISTS certificate_path TEXT NULL",
    "ALTER TABLE education ADD COLUMN IF NOT EXISTS certificate_path TEXT NULL",
)


def migrate_certificates():
    from auth import db_conn
    with db_conn() as conn:
        for stmt in APPLY_SQL:
            conn.run(stmt)
