"""test_admin_pages_min.py — PR 4.9: admin pages minimum (admin.html · admin-view.html).

Structure / absence checks (the pages are rebuilt in 5.3):
  A. each page still serves through page_shell.apply_shell (no stray {{v:}})
  B. loads tw_shared.js → admin-session.js → tw-overlay.js (DS-OVL) in order
  C. no native confirm / alert / prompt call
  D. no raw fetch( — admin calls go through TwAdminSession.fetch (login via twApi)
  E. local helpers duplicated by tw_shared.js are gone
  F. every twT('admin.…') key used exists in tw_strings.json
  G. every delete / migrate twConfirm is danger:true
Run: python tests/test_admin_pages_min.py
"""
import json
import re
import sys

from page_shell import apply_shell

PAGES = ("admin.html", "admin-view.html")
STRINGS = json.load(open("tw_strings.json", encoding="utf-8"))["ar"]
_fail = 0


def check(name, ok, info=""):
    global _fail
    print(("PASS " if ok else "FAIL ") + name + (("  — " + info) if info and not ok else ""))
    if not ok:
        _fail += 1


def inline_js(src):
    return "\n".join(re.findall(r"<script>(.*?)</script>", src, re.S))


for page in PAGES:
    src = open(page, encoding="utf-8").read()
    js = inline_js(src)

    try:
        apply_shell(src, page)
        check(f"A {page} serves", True)
    except ValueError as e:
        check(f"A {page} serves", False, str(e))

    order = [src.find('src="/tw_shared.js'), src.find('src="/static/shared/admin-session.js'),
             src.find('src="/static/shared/tw-overlay.js')]
    check(f"B {page} script order", -1 not in order and order == sorted(order), str(order))

    native = re.findall(r"(?<![\w.$])(?:window\.)?(confirm|alert|prompt)\s*\(", js)
    check(f"C {page} no native confirm/alert/prompt", not native, str(native))

    raw = re.findall(r"(?<![\w.$])fetch\s*\(", js)
    check(f"D {page} no raw fetch", not raw, f"{len(raw)} call(s)")

    local = re.findall(r"function\s+(showToast|toast|setBtnLoad|twNavigate|initScrollProg)\s*\(", js)
    check(f"E {page} no local shared helpers", not local, str(local))

    keys = re.findall(r"twT\('(admin\.[\w.]+)'", js)
    missing = [k for k in keys if k not in STRINGS]
    check(f"F {page} admin.* keys exist", bool(keys) and not missing, str(missing))

    calls = re.findall(r"twConfirm\(\{[^}]*\}\)", js)
    risky = [c for c in calls if re.search(r"admin\.(delete|migrate)", c) and "danger:true" not in c]
    check(f"G {page} delete/migrate confirms are danger", bool(calls) and not risky, str(risky))

print(f"\n{'FAILED' if _fail else 'OK'} ({_fail} failure(s))")
sys.exit(1 if _fail else 0)
