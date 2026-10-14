"""test_ds_color_gap_tokens.py — PR 4.11: the profile / company color gaps got DS-COLOR tokens.

For every new token (COLOR-SYSTEM.md CLR-35 → PR 4.11 tokens):
  1. defined in tw_shared.css with its -rgb twin
  2. resolved value (var() chain followed) = the literal the pages used before (zero visual change)
  3. admin-overridable: listed in theme_tokens.KNOWN (= GET /admin/theme/colors tokens) and an
     override renders the base + derived twin in /theme.css

Run: python -m pytest tests/test_ds_color_gap_tokens.py -q
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import theme_tokens as tt  # noqa: E402

CSS = open(os.path.join(ROOT, "tw_shared.css"), encoding="utf-8").read()
DEFS = dict(re.findall(r"(?m)^\s*(--color-[\w-]+)\s*:\s*([^;]+);", CSS))

# token → value the pages hard-coded before PR 4.11
OLD = {
    "--color-skill-level-1": "#9ca3af", "--color-skill-level-2": "#60a5fa",
    "--color-skill-level-3": "#a78bfa", "--color-skill-level-4": "#00c896",
    "--color-skill-level-5": "#fbbf24",
    "--color-status-open-to-work": "#22d3ee",
    "--color-pipeline-contacted": "#38bdf8",
    "--color-pipeline-viewed": "#6366f1",
    "--color-pipeline-viewed-text": "#818cf8",
    "--color-pipeline-viewed-text-light": "#a5b4fc",
    "--color-categorical-orange-light": "#fb923c",
    "--color-brand-accent-strong": "#7c3aed",
    "--color-cover-start": "#0f2027", "--color-cover-mid": "#203a43", "--color-cover-end": "#2c5364",
}


def _resolve(name):
    value = DEFS[name].strip()
    m = re.fullmatch(r"var\((--color-[\w-]+)\)", value)
    return _resolve(m.group(1)) if m else value.lower()


def _rgb(hex_):
    return ",".join(str(int(hex_[i:i + 2], 16)) for i in (1, 3, 5))


def test_tokens_defined_with_old_values():
    for token, old in OLD.items():
        assert token in DEFS and token + "-rgb" in DEFS, token
        assert _resolve(token) == old, (token, _resolve(token), old)
        assert _resolve(token + "-rgb").replace(" ", "") == _rgb(old), token + "-rgb"


def test_tokens_in_admin_color_list():
    for token in OLD:
        assert tt.KNOWN.get(token) is True, token
        css = tt.render_css({token: "#123456"})
        assert f"{token}: #123456;" in css and f"{token}-rgb: 18,52,86;" in css
