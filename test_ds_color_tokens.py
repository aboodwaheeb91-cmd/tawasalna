"""DS-COLOR Phase 2 — tokens + admin override + shared-file guard (PR 3.8 · CLR-35 / CLR-36).

  C1  override rejects an unknown token and a non-color value (and CSS injection)
  C2  /theme.css body is empty without an override; a valid override renders :root + -rgb twin
  C3  every Semantic -rgb channel is the twin of a base token (override keeps them in sync)
  C4  the shared files (tw_shared.css · app-header.css · home-v2.css · static/shared/*) have
      no hardcoded color — values live only on --color-* definition lines
  C5  both shell head partials load /theme.css right after tw_shared.css
  R   per-file hardcoded-color report (prints only — never fails)

Run:  python -m pytest test_ds_color_tokens.py -q
"""
import os
import re
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import theme_tokens as tt          # noqa: E402
import ds_color_audit as audit     # noqa: E402


def test_c1_validate_rejects_unknown_token_and_bad_value():
    _clean, errs = tt.validate_overrides({"--color-not-a-token": "#ffffff"})
    assert [e["code"] for e in errs] == ["unknown_token"]
    _clean, errs = tt.validate_overrides({"--color-prim-teal": "#ffffff"})      # primitives are not overridable
    assert [e["code"] for e in errs] == ["unknown_token"]
    for bad in ("red", "#12345", "rgb(300,0,0)", "rgba(0,0,0)", "#fff;}body{display:none",
                "var(--color-brand-primary)", "", 12):
        _clean, errs = tt.validate_overrides({"--color-border-default": bad})
        assert errs and errs[0]["code"] == "invalid_color", bad
    # a token with an -rgb twin takes an opaque hex only
    _clean, errs = tt.validate_overrides({"--color-brand-primary": "rgba(0,0,0,.5)"})
    assert errs and errs[0]["field"] == "--color-brand-primary"
    _clean, errs = tt.validate_overrides(["#fff"])
    assert errs[0]["code"] == "invalid_body"
    clean, errs = tt.validate_overrides({"--color-brand-primary": " #00B386 ",
                                         "--color-border-default": "rgba(255,255,255,.1)"})
    assert not errs and clean == {"--color-brand-primary": "#00b386",
                                  "--color-border-default": "rgba(255,255,255,.1)"}


def test_c2_theme_css_empty_without_override_and_renders_twin():
    assert tt.render_css({}) == ""
    assert tt.render_css(None) == ""
    assert tt.render_css(tt.parse_stored("")) == ""
    css = tt.render_css({"--color-brand-primary": "#0a0", "--color-text-muted": "rgba(255,255,255,.5)"})
    assert css.startswith(":root {") and css.rstrip().endswith("}")
    assert "--color-brand-primary: #0a0;" in css and "--color-brand-primary-rgb: 0,170,0;" in css
    assert "--color-text-muted: rgba(255,255,255,.5);" in css
    # stored junk never reaches the CSS
    assert tt.render_css({"--color-x": "#fff", "--color-ink": "}"}) == ""


def test_c3_rgb_channels_are_twins():
    css = open(os.path.join(_ROOT, "tw_shared.css"), encoding="utf-8").read()
    names = set(re.findall(r"^\s*(--color-[a-z0-9-]+)\s*:", css, re.M))
    orphans = [n for n in names if n.endswith("-rgb") and n[:-4] not in names]
    assert not orphans, orphans
    assert tt.KNOWN["--color-brand-primary"] is True and tt.KNOWN["--color-border-default"] is False


def test_c4_shared_files_have_no_hardcoded_color():
    bad = {}
    for rel in audit.SHARED_FILES:
        lines = audit.literal_lines(os.path.join(_ROOT, rel))
        if lines:
            bad[rel] = lines[:5]
    assert not bad, f"hardcoded color in shared files — use a DS-COLOR token: {bad}"


def test_c5_shell_heads_load_theme_css_after_tw_shared():
    for p in ("shell-head.html", "shell-head.admin.html"):
        html = open(os.path.join(_ROOT, "partials", p), encoding="utf-8").read()
        assert html.count('href="/theme.css"') == 1, p
        assert html.index("tw_shared.css") < html.index('href="/theme.css"'), p


def test_report_hardcoded_colors_per_file():
    rows = audit.report()
    print("\nDS-COLOR hardcoded colors per file (report — pages migrate in Phase 4):")
    for n, rel in rows[:25]:
        print(f"  {n:5d}  {rel}")
    print(f"  {sum(n for n, _ in rows):5d}  TOTAL ({len(rows)} files)")
