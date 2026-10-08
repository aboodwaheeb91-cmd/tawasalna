"""page_audit.py — Phase 4 page checklist counter (PR 3.11 · CLAUDE.md → قائمة الصفحة الموحّدة).

For every page (*.html at the repo root) it counts, in the page itself + the page-specific
scripts / stylesheets it loads (shared files are not counted — tw_shared.*, static/shared/*,
static/vendor/*, static/app-header.css, qrcode.min.js):

  fetch        raw fetch( to the site API (not twApi / TwAdminSession.fetch)
  colors       hard-coded color literals (same rule as scripts/ds_color_audit.py — DS-COLOR)
  ls_session   localStorage get/set/remove of 'tw_user' / 'tw_jwt' (twRequireAuth / TwAuthSync instead)
  dialogs      native alert( / confirm( / prompt( (DS-OVL twAlert / twConfirm instead)
  forsa        the word «فرص» (GLOSSARY: «وظائف»)
  helpers      page-local copies of shared helpers (esc*, sanitize, api, *toast*, getAuthHeaders,
               safe*Url, timeAgo, fmt*/format*Date)
  no_shell     1 = the page has no <!--tw:shell-head marker (DS-SHELL)
  no_header    1 = the page has no data-tw-header (DS-HNAV)

Every number must only go down. tools/page_audit_baseline.json holds the current numbers:
  * a number above its baseline → FAIL (exit 1) — fix the page, never raise the baseline
  * a number below its baseline → OK + "حدّث الـ baseline" — run with --update in the same PR
  * a page missing from the baseline → its baseline is 0 for every metric (new pages start clean)

Run:  python tools/page_audit.py            (table + compare; run_tests.sh runs this)
      python tools/page_audit.py --update   (write the current numbers as the baseline)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from ds_color_audit import count_literals  # noqa: E402 — the one color-literal rule (DS-COLOR)

BASELINE = os.path.join(ROOT, "tools", "page_audit_baseline.json")
METRICS = ("fetch", "colors", "ls_session", "dialogs", "forsa", "helpers", "no_shell", "no_header")

_SHARED = re.compile(r"^(tw_shared\.|static/shared/|static/vendor/|static/app-header\.css$|static/qrcode\.min\.js$|qrcode\.min\.js$|theme\.css$)")
_ASSET_RE = re.compile(r"""<(?:script[^>]*\bsrc|link[^>]*\bhref)\s*=\s*["'](/[^"'?#]+\.(?:js|css))""", re.I)

_FETCH_RE = re.compile(r"(?<![\w$.])fetch\s*\(")
_LS_RE = re.compile(r"""localStorage\s*\.\s*(?:getItem|setItem|removeItem)\s*\(\s*['"]tw_(?:user|jwt)['"]""")
_DIALOG_RE = re.compile(r"(?<![\w$.])(?:window\s*\.\s*)?(?:alert|confirm|prompt)\s*\(")
_FORSA_RE = re.compile("فرص")
_HELPER_NAMES = r"(?:esc\w*|sanitize\w*|api|\w*[Tt]oast\w*|getAuthHeaders|safe\w*Url|timeAgo|fmt\w*|format\w*Date)"
_HELPER_RE = re.compile(r"(?:\bfunction\s+" + _HELPER_NAMES + r"\s*\(|\b(?:var|let|const)\s+" + _HELPER_NAMES
                        + r"\s*=\s*(?:function\b|\([^)]*\)\s*=>|\w+\s*=>))")


def _resolve(url: str):
    """'/static/x.js' → static/x.js if it exists, else x.js (server.py serve_static falls back to the root)."""
    rel = url.lstrip("/")
    if os.path.isfile(os.path.join(ROOT, rel)):
        return rel
    if rel.startswith("static/") and os.path.isfile(os.path.join(ROOT, rel[len("static/"):])):
        return rel[len("static/"):]
    return None


def page_files(page: str) -> list:
    """The page + the page-specific assets it loads (shared files excluded)."""
    html = open(os.path.join(ROOT, page), encoding="utf-8", errors="ignore").read()
    files = [page]
    for url in _ASSET_RE.findall(html):
        rel = _resolve(url)
        if rel and not _SHARED.match(rel) and rel not in files:
            files.append(rel)
    return files


def audit_page(page: str) -> dict:
    html = open(os.path.join(ROOT, page), encoding="utf-8", errors="ignore").read()
    row = dict.fromkeys(METRICS, 0)
    for rel in page_files(page):
        path = os.path.join(ROOT, rel)
        src = open(path, encoding="utf-8", errors="ignore").read()
        row["colors"] += count_literals(path)
        if rel.endswith(".css"):
            continue
        row["fetch"] += len(_FETCH_RE.findall(src))
        row["ls_session"] += len(_LS_RE.findall(src))
        row["dialogs"] += len(_DIALOG_RE.findall(src))
        row["forsa"] += len(_FORSA_RE.findall(src))
        row["helpers"] += len(_HELPER_RE.findall(src))
    row["no_shell"] = 0 if "<!--tw:shell-head" in html else 1
    row["no_header"] = 0 if "data-tw-header" in html else 1
    return row


def pages() -> list:
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*.html")))


def audit() -> dict:
    return {p: audit_page(p) for p in pages()}


def compare(current: dict, baseline: dict):
    """(worse, better) — lists of (page, metric, baseline, now)."""
    worse, better = [], []
    for page, row in current.items():
        base = baseline.get(page, {})
        for m in METRICS:
            b, n = base.get(m, 0), row[m]
            if n > b:
                worse.append((page, m, b, n))
            elif n < b:
                better.append((page, m, b, n))
    return worse, better


def _table(current: dict) -> str:
    w = max(len(p) for p in current)
    out = ["page".ljust(w) + "".join(m.rjust(11) for m in METRICS)]
    for p, row in current.items():
        out.append(p.ljust(w) + "".join(str(row[m]).rjust(11) for m in METRICS))
    out.append("TOTAL".ljust(w) + "".join(str(sum(r[m] for r in current.values())).rjust(11) for m in METRICS))
    return "\n".join(out)


def main(argv) -> int:
    current = audit()
    print(_table(current))
    if "--update" in argv:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        print("\nbaseline written: tools/page_audit_baseline.json")
        return 0
    baseline = json.load(open(BASELINE, encoding="utf-8")) if os.path.isfile(BASELINE) else {}
    worse, better = compare(current, baseline)
    for page, m, b, n in worse:
        print(f"✗ {page}: {m} زاد {b} → {n} — صلّح الصفحة (ممنوع ترفع الـ baseline)")
    if better:
        print("\nنزل (منيح) — حدّث الـ baseline: python tools/page_audit.py --update")
        for page, m, b, n in better:
            print(f"  ↓ {page}: {m} {b} → {n}")
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
