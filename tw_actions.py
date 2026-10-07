"""tw_actions.py — Actions Registry (PR 3.7 · docs/design-system/BUTTONS.md BTN-19 · SYSTEMS_INDEX §60).

One definition per UI action (follow, message, schedule, …):
  tw_actions.json        → the registry: labelKey (twT) · icon (DS-ICON) · type · visibleTo ·
                           targets · auth · enabledWhen · confirm (DS-OVL)
  site_settings          → admin override (key `actions_override`, JSON {id: {enabled, visibleTo}})
  page_block(overrides)  → `<script>window.TW_ACTIONS=…</script>`, appended to the Strings block at
                           <!--tw:strings--> (same delivery, same moment: before tw_shared.js), so
                           twAction(id, ctx) in tw_shared.js decides synchronously.

Visibility is UX only (VM-07) — the backend still checks every request.
Pure functions — no DB, no FastAPI (server.py wires the endpoints).
"""
import json
import os
import re

import tw_strings

_ROOT = os.path.dirname(os.path.abspath(__file__))
SETTING_KEY = "actions_override"

# VM-01 modes + VM-02 account types: guest · owner · registered viewer of type emp / co / edu
AUDIENCES = ("guest", "owner", "emp", "co", "edu")
TARGETS = ("emp", "co", "edu")
TYPES = ("primary", "secondary", "danger", "ghost")
CONDITIONS = ("verified",)
OVERRIDE_FIELDS = ("enabled", "visibleTo")

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_ICON_RE = re.compile(r"^\s+'([a-z0-9-]+)': \[[01],", re.M)


def _icon_names() -> set:
    with open(os.path.join(_ROOT, "static", "shared", "tw-icons.js"), encoding="utf-8") as f:
        return set(_ICON_RE.findall(f.read()))


def _subset(v, allowed, empty_ok=False) -> bool:
    return (isinstance(v, list) and (empty_ok or v) and len(set(v)) == len(v)
            and all(isinstance(x, str) and x in allowed for x in v))


def load_registry(path: str = os.path.join(_ROOT, "tw_actions.json")) -> dict:
    """Read + check the registry. Fails loudly (ValueError / OSError) at server start — F9."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    actions = data.get("actions") if isinstance(data, dict) else None
    if not isinstance(actions, dict) or not actions:
        raise ValueError("[actions] tw_actions.json needs an 'actions' object")
    strings, icons = tw_strings.DEFAULTS[tw_strings.DEFAULT_LANG], _icon_names()
    for aid, a in actions.items():
        bad = lambda why: ValueError(f"[actions] {aid}: {why}")
        if not _ID_RE.match(aid) or not isinstance(a, dict):
            raise bad("bad id / entry")
        if a.get("labelKey") not in strings:
            raise bad("labelKey not in tw_strings.json")
        if a.get("icon") not in icons:
            raise bad("icon not in the DS-ICON registry")
        if a.get("type") not in TYPES:
            raise bad(f"type must be one of {TYPES}")
        if not _subset(a.get("visibleTo"), AUDIENCES):
            raise bad(f"visibleTo must be a non-empty subset of {AUDIENCES}")
        if "targets" in a and not _subset(a["targets"], TARGETS):
            raise bad(f"targets must be a subset of {TARGETS}")
        if not isinstance(a.get("auth"), bool):
            raise bad("auth must be true / false")
        if "enabledWhen" in a and not _subset(a["enabledWhen"], CONDITIONS):
            raise bad(f"enabledWhen must be a subset of {CONDITIONS}")
        c = a.get("confirm")
        if c is not None:
            if (not isinstance(c, dict) or not isinstance(c.get("danger"), bool)
                    or any(c.get(k) not in strings for k in ("titleKey", "messageKey", "confirmKey"))):
                raise bad("confirm needs titleKey / messageKey / confirmKey (twT keys) + danger")
        extra = set(a) - {"labelKey", "icon", "type", "visibleTo", "targets", "auth", "enabledWhen", "confirm"}
        if extra:
            raise bad(f"unknown fields {sorted(extra)}")
    return actions


REGISTRY = load_registry()


class ActionsError(ValueError):
    def __init__(self, code: str, message: str, field: str = None):
        super().__init__(message)
        self.code, self.message, self.field = code, message, field


def validate_overrides(raw, registry: dict = None) -> dict:
    """Admin input {id: {enabled?, visibleTo?}} → clean dict (all-or-nothing).
    Raises ActionsError on the first bad entry. An empty entry {} = back to the default."""
    registry = REGISTRY if registry is None else registry
    if not isinstance(raw, dict):
        raise ActionsError("invalid_body", "إعدادات الأزرار لازم تكون كائن JSON (إجراء ← إعداد)", "overrides")
    clean = {}
    for aid, ov in raw.items():
        if not isinstance(aid, str) or aid not in registry:
            raise ActionsError("unknown_action", "إجراء غير معروف", str(aid)[:64])
        if not isinstance(ov, dict):
            raise ActionsError("invalid_value", "إعداد الإجراء لازم يكون كائن", aid)
        extra = [k for k in ov if k not in OVERRIDE_FIELDS]
        if extra:
            raise ActionsError("unknown_field", "حقل غير معروف (المسموح: enabled · visibleTo)", aid)
        out = {}
        if "enabled" in ov:
            if not isinstance(ov["enabled"], bool):
                raise ActionsError("invalid_value", "enabled لازم يكون true / false", aid)
            if ov["enabled"] is False:
                out["enabled"] = False
        if "visibleTo" in ov:
            if not _subset(ov["visibleTo"], AUDIENCES, empty_ok=True):
                raise ActionsError("invalid_value",
                                   "visibleTo لازم يكون من: guest · owner · emp · co · edu", aid)
            if sorted(ov["visibleTo"]) != sorted(registry[aid]["visibleTo"]):
                out["visibleTo"] = list(ov["visibleTo"])
        if out:
            clean[aid] = out
    return clean


def parse_stored(value: str) -> dict:
    """Stored JSON → clean overrides. Bad / stale entries are dropped (logged), never raised."""
    if not value:
        return {}
    try:
        raw = json.loads(value)
    except ValueError:
        print("[actions] stored override is not JSON — ignored")
        return {}
    out = {}
    for k, v in (raw.items() if isinstance(raw, dict) else ()):
        try:
            out.update(validate_overrides({k: v}))
        except ActionsError as e:
            print(f"[actions] stored override {k!r} dropped: {e.code}")
    return out


def merged(overrides: dict, registry: dict = None) -> dict:
    """Registry with the admin overrides applied: enabled:false → "off": true · visibleTo replaced."""
    registry = REGISTRY if registry is None else registry
    out = {}
    for aid, a in registry.items():
        d = dict(a)
        ov = (overrides or {}).get(aid) or {}
        if ov.get("enabled") is False:
            d["off"] = True
        if "visibleTo" in ov:
            d["visibleTo"] = list(ov["visibleTo"])
        out[aid] = d
    return out


def page_block(overrides: dict) -> str:
    """Inline script appended at <!--tw:strings-->. JSON escaped so it can never close the
    script tag (§54) — values are registry data + validated audience names only."""
    payload = json.dumps({"actions": merged(overrides)}, ensure_ascii=False, separators=(",", ":"))
    payload = (payload.replace("<", "\\u003c").replace(">", "\\u003e")
               .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return "<script>window.TW_ACTIONS=" + payload + ";</script>"
