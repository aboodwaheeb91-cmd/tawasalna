"""changelog_collect.py — changelog.d/ fragments → docs/CHANGELOG.md (PR 3.11 · CLAUDE.md → بروتوكول المهام 13).

Every PR writes its entry in its OWN file, changelog.d/<task>.md (e.g. changelog.d/3.11.md),
never in docs/CHANGELOG.md — two open PRs then never conflict on the changelog.

Fragment format (checked by --check, which run_tests.sh runs on every PR):
  line 1:  ## PR <task> — <title> — YYYY-MM-DD      (<task> = the file name without .md)
  then:    at least one "- " bullet

Run:  python tools/changelog_collect.py --check   validate the fragments (no writes)
      python tools/changelog_collect.py           move every fragment into docs/CHANGELOG.md
                                                  (newest date first, above the previous
                                                  entries) and delete the fragments — run on
                                                  main after merges, as its own commit.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAG_DIR = os.path.join(ROOT, "changelog.d")
CHANGELOG = os.path.join(ROOT, "docs", "CHANGELOG.md")
_HEAD_RE = re.compile(r"^## PR (?P<task>\S+) — .+ — (?P<date>\d{4}-\d{2}-\d{2})\s*$")


def fragments() -> list:
    return sorted(p for p in glob.glob(os.path.join(FRAG_DIR, "*.md"))
                  if os.path.basename(p).lower() != "readme.md")


def check_fragment(path: str) -> list:
    """Problems with one fragment ([] = valid)."""
    name = os.path.basename(path)[:-3]
    lines = open(path, encoding="utf-8").read().strip().split("\n")
    m = _HEAD_RE.match(lines[0]) if lines else None
    errs = []
    if not m:
        errs.append("line 1 must be: ## PR <task> — <title> — YYYY-MM-DD")
    elif m.group("task") != name:
        errs.append(f"task in the heading ({m.group('task')}) ≠ file name ({name})")
    if not any(ln.startswith("- ") for ln in lines[1:]):
        errs.append("needs at least one '- ' bullet")
    return errs


def collect() -> int:
    """Insert every fragment into CHANGELOG.md (newest first) and delete it. Returns the count."""
    frags = fragments()
    if not frags:
        return 0
    entries = []
    for p in frags:
        body = open(p, encoding="utf-8").read().strip()
        entries.append((_HEAD_RE.match(body.split("\n")[0]).group("date"), os.path.basename(p), body))
    entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
    text = open(CHANGELOG, encoding="utf-8").read()
    m = re.search(r"^## (?!فهرس)", text, re.M)          # first entry after the index
    at = m.start() if m else len(text)
    block = "\n\n".join(e[2] for e in entries) + "\n\n"
    with open(CHANGELOG, "w", encoding="utf-8") as f:
        f.write(text[:at] + block + text[at:])
    for p in frags:
        os.remove(p)
    return len(entries)


def main(argv) -> int:
    bad = [(os.path.relpath(p, ROOT), e) for p in fragments() for e in check_fragment(p)]
    for rel, err in bad:
        print(f"✗ {rel}: {err}")
    if "--check" in argv or bad:
        if not bad:
            print(f"✓ {len(fragments())} changelog.d fragment(s) valid")
        return 1 if bad else 0
    n = collect()
    print(f"✓ {n} fragment(s) moved into docs/CHANGELOG.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
