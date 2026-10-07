"""ds_color_audit.py — DS-COLOR hardcoded-color audit (PR 3.8 · COLOR-SYSTEM.md CLR-35).

Counts color literals (hex · rgb()/rgba() · hsl()/hsla() with numbers) per file.
A color built from a token — rgba(var(--color-…-rgb), a) — is not a literal.

Not counted:
  * tw_shared.css lines that DEFINE a --color-* token (the one place values live)
  * a line carrying `tw-color-literal: <reason>` (documented exception — e.g. the
    cropper's JPEG export matte); the reason is mandatory

SHARED_FILES must stay at zero (test_ds_color_tokens.py fails otherwise).
Everything else is a report only — pages migrate with their page (Phase 4).

Run:  python scripts/ds_color_audit.py        (prints the per-file report)
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHARED_FILES = ["tw_shared.css", "static/app-header.css", "static/home-v2.css"] + sorted(
    os.path.relpath(p, ROOT).replace(os.sep, "/")
    for p in glob.glob(os.path.join(ROOT, "static", "shared", "*.*")))

_SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", "docs", "tests", "flags", "icons", "img"}
_SKIP_FILES = {"qrcode.min.js"}

LITERAL_RE = re.compile(
    r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b"
    r"|\b(?:rgba?|hsla?)\(\s*[\d.]")
_TOKEN_DEF_RE = re.compile(r"^\s*--color-[\w-]+\s*:")
_EXCEPTION_RE = re.compile(r"tw-color-literal:\s*\S")


def literal_lines(path: str) -> list:
    """[(line_no, line)] with at least one uncounted-exempt color literal."""
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    out = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            if not LITERAL_RE.search(line) or _EXCEPTION_RE.search(line):
                continue
            if rel == "tw_shared.css" and _TOKEN_DEF_RE.match(line):
                continue
            out.append((i, line.rstrip("\n")))
    return out


def count_literals(path: str) -> int:
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    n = 0
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if _EXCEPTION_RE.search(line) or (rel == "tw_shared.css" and _TOKEN_DEF_RE.match(line)):
                continue
            n += len(LITERAL_RE.findall(line))
    return n


def site_files() -> list:
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn in _SKIP_FILES or fn.startswith("test_") or not fn.endswith((".css", ".html", ".js")):
                continue
            files.append(os.path.join(dirpath, fn))
    return sorted(files)


def report() -> list:
    """[(count, relpath)] for every site file with literals, most first."""
    rows = [(count_literals(p), os.path.relpath(p, ROOT).replace(os.sep, "/")) for p in site_files()]
    return sorted((r for r in rows if r[0]), key=lambda r: (-r[0], r[1]))


if __name__ == "__main__":
    rows = report()
    for n, rel in rows:
        print(f"{n:6d}  {rel}")
    print(f"{sum(n for n, _ in rows):6d}  TOTAL ({len(rows)} files)")
    sys.exit(0)
