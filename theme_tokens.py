"""theme_tokens.py — DS-COLOR admin override (PR 3.8 · COLOR-SYSTEM.md CLR-36).

One mechanism: site_settings[THEME_SETTING_KEY] holds a JSON object
{ "--color-<semantic token>": "<color>" }. GET /theme.css renders it as one
`:root{...}` block that the shell head loads right after tw_shared.css, so a
saved value replaces the default of that token on every shell page.
No override → empty /theme.css → the defaults in tw_shared.css (zero change).

Known keys come from tw_shared.css itself (Section B — Semantic): every
`--color-*` definition that is not `--color-prim-*` and not an `-rgb` channel.
A key whose `<key>-rgb` twin exists there only accepts an opaque hex; the twin
is derived and written next to it, so rgba(var(--…-rgb), a) follows the
override. Values are strict colors only (hex / rgb() / rgba() with numbers) —
nothing else can reach the CSS text (§54: no injection through a value).

Pure functions — no DB, no FastAPI (server.py wires the endpoints).
"""
import json
import os
import re

THEME_SETTING_KEY = "theme_color_tokens"

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DEF_RE = re.compile(r"^\s*(--color-[a-z0-9-]+)\s*:", re.M)
_HEX_RE = re.compile(r"#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})")
_RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(0|1|0?\.\d{1,3}|1\.0{1,3}))?\s*\)")
MAX_VALUE_LEN = 40


def known_tokens(css_text: str = None) -> dict:
    """{token: has_rgb_twin} for every overridable Semantic token in tw_shared.css."""
    if css_text is None:
        with open(os.path.join(_ROOT, "tw_shared.css"), encoding="utf-8") as f:
            css_text = f.read()
    names = set(_DEF_RE.findall(css_text))
    return {n: (n + "-rgb") in names for n in sorted(names)
            if not n.startswith("--color-prim-") and not n.endswith("-rgb")}


KNOWN = known_tokens()


def _is_color(value: str) -> bool:
    if _HEX_RE.fullmatch(value):
        return True
    m = _RGB_RE.fullmatch(value)
    if not m or any(int(c) > 255 for c in m.group(1, 2, 3)):
        return False
    # rgb() takes 3 channels, rgba() takes 4
    return (m.group(4) is None) == value.startswith("rgb(")


def _hex_rgb(value: str) -> str:
    h = value[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def validate_overrides(data, known: dict = None):
    """→ (clean dict, errors list). errors = [{field, code, message}] — Arabic messages.
    clean holds lowercased values for valid keys only; the caller saves it only when
    errors is empty (all-or-nothing)."""
    known = KNOWN if known is None else known
    if not isinstance(data, dict):
        return {}, [{"field": "overrides", "code": "invalid_body",
                     "message": "الألوان لازم تكون كائن JSON (توكن ← لون)"}]
    clean, errors = {}, []
    for key, raw in data.items():
        if not isinstance(key, str) or key not in known:
            errors.append({"field": str(key)[:64], "code": "unknown_token",
                           "message": "توكن لون غير معروف"})
            continue
        value = raw.strip().lower() if isinstance(raw, str) else ""
        if not value or len(value) > MAX_VALUE_LEN or not _is_color(value):
            errors.append({"field": key, "code": "invalid_color",
                           "message": "قيمة اللون غير صالحة (hex أو rgb/rgba)"})
            continue
        if known[key] and not re.fullmatch(r"#(?:[0-9a-f]{3}|[0-9a-f]{6})", value):
            errors.append({"field": key, "code": "invalid_color",
                           "message": "هذا التوكن يقبل لون hex معتم فقط (#rgb أو #rrggbb)"})
            continue
        clean[key] = value
    return clean, errors


def render_css(overrides: dict, known: dict = None) -> str:
    """One `:root{...}` block — '' when there is nothing (valid) to override."""
    known = KNOWN if known is None else known
    clean, _errors = validate_overrides(overrides or {}, known)
    if not clean:
        return ""
    lines = []
    for key in sorted(clean):
        lines.append(f"  {key}: {clean[key]};")
        if known[key]:
            lines.append(f"  {key}-rgb: {_hex_rgb(clean[key])};")
    return ":root {\n" + "\n".join(lines) + "\n}\n"


def parse_stored(raw: str) -> dict:
    """site_settings value → dict. Empty / broken JSON → {} (the caller logs)."""
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("theme overrides must be a JSON object")
    return data
