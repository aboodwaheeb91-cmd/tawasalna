"""test_company_colors.py — PR 4.3b: company page colors come from DS-COLOR tokens (CLR-35).

Structure checks on the real files:
  1. company.css defines no custom property that shadows a shared one (--ac / --t2 / --color-* …)
  2. every var(--x) without a fallback in company.css resolves to a definition
     (tw_shared.css / company.css / shared CSS) — nothing points at the deleted page :root
  3. zero hard-coded colors on the page (PR 4.11 gave the last gaps a token — CLR-35 →
     PR 4.11 tokens) and no prefers-color-scheme: light block (no light theme — CLR-23)
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


def test_no_shadowed_shared_property():
    shadowed = _defs(CSS) & _defs(_shared_css())
    assert not shadowed, "company.css redefines shared properties: %s" % sorted(shadowed)
    assert not [d for d in _defs(CSS) if d.startswith("--color-")]


def test_every_var_without_fallback_resolves():
    known = _defs(CSS) | _defs(_shared_css())
    bare = set(re.findall(r"var\(\s*(--[\w-]+)\s*\)", CSS))
    assert not bare - known, "undefined: %s" % sorted(bare - known)


def test_no_literal_colors_left():
    stray = []
    for rel in page_audit.page_files("company-profile.html"):
        for i, line in enumerate(open(os.path.join(ROOT, rel), encoding="utf-8").read().splitlines(), 1):
            stray += ["%s:%d %s" % (rel, i, m.group(0)) for m in LITERAL_RE.finditer(line)]
    assert not stray, stray
    assert "prefers-color-scheme" not in CSS


def test_dead_css_removed():
    for sel in (".co-hdr", ".co-app-ava", ".co-fl-ava", ".co-cand-ava", ".co-csc-ava",
                ".tw-toast", ".tw-skeleton", ".tw-fab", ".tw-empty-btn"):
        assert not re.search(r"(?m)^\s*" + re.escape(sel) + r"(?![\w-])", CSS), sel
    assert not re.search(r"(?m)^\s*\.tw-empty(?:-title|-sub)?\s*\{", CSS)


def test_company_logo_is_rounded_square():
    for sel in (".co-logo", ".sc-avatar-wrap::after", "#coLogoCropCanvas"):
        radius = re.search(r"border-radius\s*:\s*([^;]+);", _rule(sel)).group(1).strip()
        assert radius != "50%" and re.fullmatch(r"\d+px", radius), (sel, radius)
    js = open(os.path.join(ROOT, "static", "company", "company.main.js"), encoding="utf-8").read()
    body = re.search(r"function _getLogoCropper\(\)\s*\{(.*?)\n  \}", js, re.S).group(1)
    assert re.search(r"shape:\s*'rect'", body), "logo cropper must be shape 'rect' (IMG-03)"
