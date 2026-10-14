"""test_company_colors.py — PR 4.3b: company page colors come from DS-COLOR tokens (CLR-35).

Structure checks on the real files:
  1. company.css defines no custom property that shadows a shared one (--ac / --t2 / --color-* …)
  2. every var(--x) without a fallback in company.css resolves to a definition
     (tw_shared.css / company.css / shared CSS) — nothing points at the deleted page :root
  3. the hard-coded colors left on the page are only the documented no-token set (F30 —
     COLOR-SYSTEM.md CLR-35 → Company page gaps)
  4. dead CSS is gone: .co-hdr, the old avatar classes, local .tw-toast / .tw-skeleton /
     .tw-fab / .tw-empty copies
  5. company logo = rounded square (IMG-03): .co-logo / ring / crop canvas not 50%,
     logo cropper shape 'rect'

Run: python -m pytest tests/test_company_colors.py -q
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from ds_color_audit import LITERAL_RE  # noqa: E402
import page_audit  # noqa: E402

CSS_PATH = os.path.join(ROOT, "static", "company", "company.css")
CSS = open(CSS_PATH, encoding="utf-8").read()

# F30 — colors with no DS-COLOR token (indigo · sky · orange-400 · purple-600 · cover fade ·
# the light-scheme popup). Each one waits for a CLR-26 promotion decision.
F30_RGB = {"99,102,241", "165,180,252", "129,140,248", "56,189,248", "251,146,60",
           "124,58,237", "20,26,36"}
# The light-scheme popup block (@media prefers-color-scheme: light) — no light theme in DS-COLOR yet (CLR-23).
LIGHT_RE = re.compile(r"@media \(prefers-color-scheme: light\) \{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")


def _defs(src):
    return set(re.findall(r"(--[\w-]+)\s*:", src))


def _shared_css():
    paths = [os.path.join(ROOT, "tw_shared.css"), os.path.join(ROOT, "static", "app-header.css")]
    paths += glob.glob(os.path.join(ROOT, "static", "shared", "*.css"))
    return "".join(open(p, encoding="utf-8").read() for p in paths)


def _rule(selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert m, selector + " rule missing"
    return m.group(1)


def _rgb(lit):
    lit = lit.lower()
    if lit.startswith("#"):
        h = lit[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h[:3])
        return "%d,%d,%d" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return ",".join(p.strip() for p in lit[lit.index("(") + 1:].split(",")[:3])


def test_no_shadowed_shared_property():
    shadowed = _defs(CSS) & _defs(_shared_css())
    assert not shadowed, "company.css redefines shared properties: %s" % sorted(shadowed)
    assert not [d for d in _defs(CSS) if d.startswith("--color-")]


def test_every_var_without_fallback_resolves():
    known = _defs(CSS) | _defs(_shared_css())
    bare = set(re.findall(r"var\(\s*(--[\w-]+)\s*\)", CSS))
    assert not bare - known, "undefined: %s" % sorted(bare - known)


def test_only_documented_literals_left():
    files = [os.path.join(ROOT, f) for f in page_audit.page_files("company-profile.html")]
    stray = []
    for path in files:
        src = open(path, encoding="utf-8").read()
        light = {src[:m.start()].count("\n") + 1 + k for m in LIGHT_RE.finditer(src)
                 for k in range(m.group(0).count("\n") + 1)}
        for i, line in enumerate(src.splitlines(), 1):
            if i in light:
                continue
            for m in LITERAL_RE.finditer(line):
                full = m.group(0)
                if not full.startswith("#"):
                    full = line[m.start():line.index(")", m.start()) + 1]
                if _rgb(full) not in F30_RGB:
                    stray.append("%s:%d %s" % (os.path.relpath(path, ROOT), i, full))
    assert not stray, stray


def test_dead_css_removed():
    for sel in (".co-hdr", ".co-app-ava", ".co-fl-ava", ".co-cand-ava", ".co-csc-ava",
                ".tw-toast", ".tw-skeleton", ".tw-fab", ".tw-empty-btn"):
        assert not re.search(r"(?m)^\s*" + re.escape(sel) + r"(?![\w-])", CSS), sel
    assert not re.search(r"(?m)^\s*\.tw-empty(?:-title|-sub)?\s*\{", CSS)


def test_company_logo_is_rounded_square():
    for sel in (".co-logo", ".sc-avatar-wrap::after", "#coLogoCropCanvas"):
        radius = re.search(r"border-radius\s*:\s*([^;]+);", _rule(sel)).group(1).strip()
        assert radius != "50%" and radius.startswith("var(--radius-"), (sel, radius)
    js = open(os.path.join(ROOT, "static", "company", "company.main.js"), encoding="utf-8").read()
    body = re.search(r"function _getLogoCropper\(\)\s*\{(.*?)\n  \}", js, re.S).group(1)
    assert re.search(r"shape:\s*'rect'", body), "logo cropper must be shape 'rect' (IMG-03)"
