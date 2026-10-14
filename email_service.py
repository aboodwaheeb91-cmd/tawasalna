"""email_service.py — Unified Email System (task 5.1a · docs/SYSTEMS_INDEX.md §54j · docs/rules/email.md).

send_email(to, template_key, vars) is the ONLY function that sends an email on the site.

  provider   Resend HTTP API (Railway blocks SMTP) — key from the RESEND_API_KEY env var only;
             never logged, never returned. Missing key → {"ok": False, "code": "unavailable"}.
  settings   site_settings[email_settings] (JSON): from_address · from_name · site_url ·
             types {template_key: on/off} — validated by validate_settings(), loaded by server.py
             at startup + on admin save (set_settings), never a DB call per email.
  text       subject / body of every template = Strings System keys (email.<template>.*,
             tw_strings.json + admin override) — server.py hands the merged dict via
             set_strings_provider(). One RTL HTML layout + a plain-text version.
             Every variable is HTML-escaped in the HTML part; CR/LF stripped in the subject.
  colors     read from the DS-COLOR primitives in tw_shared.css (email clients have no CSS vars).

Result (never raises): {"ok": True, "code": "sent", "id": <provider id>} or
{"ok": False, "code": "unavailable" | "disabled" | "invalid" | "failed"}.
Logs carry the template + reason only — never the key, the recipient or the body.
"""
import html
import json
import os
import re
import urllib.error
import urllib.request

RESEND_URL = "https://api.resend.com/emails"
SETTING_KEY = "email_settings"
TIMEOUT_SECONDS = 10

# Template registry: key → variables it takes + its parts (Strings keys email.<key>.<part>).
# "types" = the templates the admin can switch off; admin_test is always on (it IS the check).
TEMPLATES = {
    "password_reset":   {"vars": ("name", "link", "minutes"),
                         "parts": ("subject", "body", "button", "note")},
    "password_changed": {"vars": ("name",), "parts": ("subject", "body", "note")},
    "email_change":     {"vars": ("name", "link", "minutes"),
                         "parts": ("subject", "body", "button", "note")},
    "email_changed":    {"vars": ("name",), "parts": ("subject", "body", "note")},
    "kyc_email_otp":    {"vars": ("name", "code", "minutes"), "parts": ("subject", "body", "note")},
    "admin_test":       {"vars": (), "parts": ("subject", "body")},
}
TYPES = ("password_reset", "password_changed", "email_change", "email_changed", "kyc_email_otp")

DEFAULTS = {
    "from_address": "no-reply@tawasolna.com",
    "from_name": "تواصلنا",
    "site_url": "https://tawasolna.com",
    "types": {k: True for k in TYPES},
}

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
_SITE_URL_RE = re.compile(r"^https://[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*(:\d{1,5})?$")
_NAME_BAD_RE = re.compile(r"[\x00-\x1f\x7f<>\"\\,;:@]")
_VAR_RE = re.compile(r"\{([a-z0-9_]+)\}")
FROM_NAME_MAX = 60

_settings = json.loads(json.dumps(DEFAULTS))
_strings_provider = None


def _default_strings() -> dict:
    import tw_strings
    return tw_strings.merged({})


# ── Configuration ────────────────────────────────────────────────────────────
def _api_key() -> str:
    return (os.environ.get("RESEND_API_KEY") or "").strip()


def status() -> str:
    """'configured' | 'missing' — for /health and the admin page (never the key)."""
    return "configured" if _api_key() else "missing"


def is_configured() -> bool:
    return bool(_api_key())


def valid_address(addr) -> bool:
    return isinstance(addr, str) and len(addr) <= 254 and bool(_EMAIL_RE.match(addr))


def get_settings() -> dict:
    return json.loads(json.dumps(_settings))


def set_settings(clean: dict) -> None:
    global _settings
    _settings = json.loads(json.dumps(clean))


def set_strings_provider(fn) -> None:
    """fn() → the merged {key: text} dict (defaults + admin override)."""
    global _strings_provider
    _strings_provider = fn


def type_enabled(template_key: str) -> bool:
    if template_key not in TYPES:
        return template_key in TEMPLATES
    return bool(_settings.get("types", {}).get(template_key, True))


def can_send(template_key: str) -> bool:
    """Key present + this email type switched on."""
    return is_configured() and type_enabled(template_key)


class EmailSettingsError(ValueError):
    def __init__(self, code: str, message: str, field: str = None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def validate_settings(raw, current: dict = None) -> dict:
    """Admin input (partial) → full clean settings over `current` (default: DEFAULTS).
    Raises EmailSettingsError on the first bad field."""
    if not isinstance(raw, dict):
        raise EmailSettingsError("invalid_body", "صيغة الإعدادات غير صحيحة")
    out = json.loads(json.dumps(current if current is not None else DEFAULTS))
    out.setdefault("types", {})
    for k in raw:
        if k not in DEFAULTS:
            raise EmailSettingsError("unknown_field", "حقل غير معروف", k)
    if "from_address" in raw:
        v = raw["from_address"]
        v = v.strip() if isinstance(v, str) else v
        if not valid_address(v):
            raise EmailSettingsError("invalid_email", "عنوان المرسل غير صحيح", "from_address")
        out["from_address"] = v
    if "from_name" in raw:
        v = raw["from_name"]
        v = v.strip() if isinstance(v, str) else v
        if not isinstance(v, str) or not v or len(v) > FROM_NAME_MAX or _NAME_BAD_RE.search(v):
            raise EmailSettingsError("invalid_name",
                                     f"اسم المرسل مطلوب، حتى {FROM_NAME_MAX} حرف، بدون رموز خاصة", "from_name")
        out["from_name"] = v
    if "site_url" in raw:
        v = raw["site_url"]
        v = v.strip().rstrip("/") if isinstance(v, str) else v
        if not isinstance(v, str) or not _SITE_URL_RE.match(v):
            raise EmailSettingsError("invalid_url", "رابط الموقع لازم يكون https://domain بدون مسار", "site_url")
        out["site_url"] = v
    if "types" in raw:
        t = raw["types"]
        if not isinstance(t, dict):
            raise EmailSettingsError("invalid_value", "صيغة أنواع الإيميل غير صحيحة", "types")
        for k, v in t.items():
            if k not in TYPES:
                raise EmailSettingsError("unknown_type", "نوع إيميل غير معروف", k)
            if not isinstance(v, bool):
                raise EmailSettingsError("invalid_value", "القيمة لازم تكون تشغيل / إيقاف", k)
            out["types"][k] = v
    for k in TYPES:
        out["types"].setdefault(k, True)
    return out


def parse_stored(value: str) -> dict:
    """Stored JSON → clean settings. Unreadable / invalid → defaults (logged, never raised)."""
    if not value:
        return json.loads(json.dumps(DEFAULTS))
    try:
        return validate_settings(json.loads(value))
    except (ValueError, TypeError) as e:
        print(f"[email] stored settings ignored — defaults in use: {getattr(e, 'code', type(e).__name__)}")
        return json.loads(json.dumps(DEFAULTS))


# ── Rendering ────────────────────────────────────────────────────────────────
def _css_color(name: str, fallback: str) -> str:
    """DS-COLOR primitive (hex) from tw_shared.css — the email layout's colors."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tw_shared.css"),
                  encoding="utf-8") as f:
            m = re.search(re.escape(name) + r"\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", f.read())
        return m.group(1) if m else fallback
    except OSError:
        return fallback


_BRAND = _css_color("--color-prim-teal", "#00c896")
_ON_BRAND = _css_color("--color-prim-dark-950", "#070b18")


def _fill(text: str, values: dict, escape) -> str:
    return _VAR_RE.sub(lambda m: escape(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def _no_newlines(s: str) -> str:
    return re.sub(r"[\r\n\x00-\x1f\x7f]+", " ", s).strip()


def render(template_key: str, values: dict) -> dict:
    """→ {"subject", "html", "text"}. values are plain text; escaped here."""
    spec = TEMPLATES[template_key]
    strings = (_strings_provider or _default_strings)()
    vals = {k: str(values.get(k, "") if values.get(k) is not None else "") for k in spec["vars"]}

    def s(key):
        return strings.get(key, "")

    def part(p):
        return s(f"email.{template_key}.{p}") if p in spec["parts"] else ""

    esc = lambda v: html.escape(v, quote=True)   # noqa: E731
    raw = lambda v: v                            # noqa: E731
    name = vals.get("name", "").strip()
    greeting_key = "email.common.greeting" if name else "email.common.greeting_plain"
    link = vals.get("link", "")
    link_ok = link.startswith("https://") and not re.search(r"[\s\"'<>\\]", link)

    subject = _no_newlines(_fill(part("subject"), vals, raw))
    lines_txt = [_fill(s(greeting_key), {"name": name}, raw), "", _fill(part("body"), vals, raw)]
    if link_ok:
        lines_txt += ["", link]
    if part("note"):
        lines_txt += ["", _fill(part("note"), vals, raw)]
    lines_txt += ["", "—", s("email.common.footer")]
    text = "\n".join(lines_txt)

    button = ""
    if link_ok and part("button"):
        href = esc(link)
        button = (
            f'<p style="margin:24px 0;text-align:center;"><a href="{href}" '
            f'style="display:inline-block;background:{_BRAND};color:{_ON_BRAND};text-decoration:none;'
            f'font-weight:700;padding:12px 28px;border-radius:10px;">{esc(part("button"))}</a></p>'
            f'<p style="margin:0 0 8px;font-size:13px;color:#555;">{esc(s("email.common.link_hint"))}</p>'
            f'<p style="margin:0 0 16px;font-size:12px;direction:ltr;text-align:left;word-break:break-all;">'
            f'<a href="{href}" style="color:{_BRAND};">{href}</a></p>'
        )
    note = (f'<p style="margin:16px 0 0;font-size:13px;color:#555;">{_fill(esc(part("note")), vals, esc)}</p>'
            if part("note") else "")
    body_html = (
        '<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'<title>{esc(subject)}</title></head>'
        '<body style="margin:0;padding:0;background:#f4f6f8;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" dir="rtl" '
        'style="max-width:560px;background:#ffffff;border-radius:14px;overflow:hidden;'
        "font-family:Cairo,Tahoma,Arial,sans-serif;text-align:right;color:#1a1f2b;\">"
        f'<tr><td style="background:{_BRAND};color:{_ON_BRAND};padding:18px 24px;font-size:20px;font-weight:800;">'
        f'{esc(_settings.get("from_name") or DEFAULTS["from_name"])}</td></tr>'
        '<tr><td style="padding:24px;font-size:15px;line-height:1.8;">'
        f'<p style="margin:0 0 12px;font-weight:700;">{esc(_fill(s(greeting_key), {"name": name}, raw))}</p>'
        f'<p style="margin:0;">{_fill(esc(part("body")), vals, esc)}</p>'
        f'{button}{note}</td></tr>'
        '<tr><td style="padding:16px 24px;border-top:1px solid #e6e9ee;font-size:12px;color:#777;">'
        f'{esc(s("email.common.footer"))}</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    return {"subject": subject, "html": body_html, "text": text}


# ── Sending ──────────────────────────────────────────────────────────────────
def _post(payload: dict, key: str):
    """One HTTPS POST to Resend. → (status, response dict). Raises on network errors."""
    req = urllib.request.Request(
        RESEND_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 # Resend sits behind Cloudflare, which rejects the default Python-urllib agent.
                 "User-Agent": "tawasolna-email/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            body = r.read() or b"{}"
            return r.status, json.loads(body.decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def send_email(to, template_key: str, vars: dict = None) -> dict:
    """The site's only email sender. Never raises; see module docstring for the result."""
    if template_key not in TEMPLATES:
        print(f"[email] unknown template {template_key!r}")
        return {"ok": False, "code": "invalid"}
    if not valid_address(to):
        print(f"[email] invalid recipient template={template_key}")
        return {"ok": False, "code": "invalid"}
    key = _api_key()
    if not key:
        print(f"[email] not sent template={template_key}: RESEND_API_KEY missing")
        return {"ok": False, "code": "unavailable"}
    if not type_enabled(template_key):
        print(f"[email] not sent template={template_key}: type switched off")
        return {"ok": False, "code": "disabled"}
    try:
        msg = render(template_key, vars or {})
        sender = f'{_settings.get("from_name") or DEFAULTS["from_name"]} ' \
                 f'<{_settings.get("from_address") or DEFAULTS["from_address"]}>'
        code, body = _post({"from": sender, "to": [to], "subject": msg["subject"],
                            "html": msg["html"], "text": msg["text"]}, key)
    except Exception as e:   # network / timeout / bad JSON — type only (no key, no recipient)
        print(f"[email] send failed template={template_key}: {type(e).__name__}")
        return {"ok": False, "code": "failed"}
    if 200 <= code < 300:
        print(f"[email] sent template={template_key} id={str(body.get('id', ''))[:64]}")
        return {"ok": True, "code": "sent", "id": body.get("id")}
    print(f"[email] send failed template={template_key}: http {code}")
    return {"ok": False, "code": "failed"}
