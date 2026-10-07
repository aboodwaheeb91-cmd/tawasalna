"""tw_strings.py — Strings System (PR 3.6 · docs/SYSTEMS_INDEX.md §59 · docs/GLOSSARY.md).

One place for every UI text:
  tw_strings.json        → defaults, one dict per language: {"ar": {key: text}, "en": {...} later}
  site_settings          → admin override per language (key `strings_override.<lang>`, JSON {key: text})
  page_block(overrides)  → the inline <script> that read_html() puts at <!--tw:strings--> so
                           twT(key, vars) in tw_shared.js reads window.TW_STRINGS.dict synchronously.

Overrides are validated here only (validate_overrides): known key, text, ≤ MAX_LEN, no HTML
(< or >), no control chars, only the {placeholders} the default text has.
"""
import json
import os
import re

_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LANG = "ar"
MAX_LEN = 300
MARKER = "<!--tw:strings-->"

_KEY_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
_VAR_RE = re.compile(r"\{([a-z0-9_]+)\}")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def setting_key(lang: str = DEFAULT_LANG) -> str:
    return "strings_override." + lang


def load_defaults(path: str = os.path.join(_ROOT, "tw_strings.json")) -> dict:
    """Read + check the defaults file. Fails loudly (ValueError / OSError) — F9."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get(DEFAULT_LANG), dict):
        raise ValueError(f"[strings] tw_strings.json needs a '{DEFAULT_LANG}' dictionary")
    for lang, d in data.items():
        if not isinstance(d, dict):
            raise ValueError(f"[strings] language {lang!r} is not a dictionary")
        for k, v in d.items():
            if not _KEY_RE.match(k) or not isinstance(v, str) or not v or "<" in v or ">" in v:
                raise ValueError(f"[strings] bad entry {lang}.{k}")
    return data


DEFAULTS = load_defaults()


class StringsError(ValueError):
    def __init__(self, code: str, message: str, field: str = None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def validate_overrides(raw, lang: str = DEFAULT_LANG) -> dict:
    """Admin input → clean {key: text}. Empty text = back to default (dropped).
    Raises StringsError on the first bad entry."""
    base = DEFAULTS.get(lang)
    if base is None:
        raise StringsError("unknown_lang", "اللغة غير مدعومة")
    if not isinstance(raw, dict):
        raise StringsError("invalid_body", "صيغة النصوص غير صحيحة")
    clean = {}
    for key, val in raw.items():
        if key not in base:
            raise StringsError("unknown_key", "مفتاح نص غير معروف", key)
        if val is None:
            continue
        if not isinstance(val, str):
            raise StringsError("invalid_value", "النص لازم يكون كتابة", key)
        val = val.strip()
        if not val:
            continue
        if len(val) > MAX_LEN:
            raise StringsError("too_long", f"النص أطول من {MAX_LEN} حرف", key)
        if "<" in val or ">" in val:
            raise StringsError("html_not_allowed", "ممنوع HTML بالنص", key)
        if _CTRL_RE.search(val):
            raise StringsError("invalid_value", "النص فيه رموز غير مسموحة", key)
        if not set(_VAR_RE.findall(val)) <= set(_VAR_RE.findall(base[key])):
            raise StringsError("unknown_placeholder", "النص فيه متغير غير موجود بالنص الأصلي", key)
        clean[key] = val
    return clean


def parse_stored(value: str, lang: str = DEFAULT_LANG) -> dict:
    """Stored JSON → clean overrides. Bad / stale entries are dropped (logged), never raised."""
    if not value:
        return {}
    try:
        raw = json.loads(value)
    except ValueError:
        print("[strings] stored override is not JSON — ignored")
        return {}
    out = {}
    for k, v in (raw.items() if isinstance(raw, dict) else ()):
        try:
            out.update(validate_overrides({k: v}, lang))
        except StringsError as e:
            print(f"[strings] stored override {k!r} dropped: {e.code}")
    return out


def merged(overrides: dict, lang: str = DEFAULT_LANG) -> dict:
    d = dict(DEFAULTS.get(lang) or DEFAULTS[DEFAULT_LANG])
    d.update(overrides or {})
    return d


def page_block(overrides: dict, lang: str = DEFAULT_LANG) -> str:
    """Inline script for <!--tw:strings-->. Text never contains < or > (validated), and
    the JSON is escaped anyway so it can never close the script tag (§54)."""
    payload = json.dumps({"lang": lang, "dict": merged(overrides, lang)}, ensure_ascii=False,
                         separators=(",", ":"))
    payload = (payload.replace("<", "\\u003c").replace(">", "\\u003e")
               .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return "<script>window.TW_STRINGS=" + payload + ";</script>"
