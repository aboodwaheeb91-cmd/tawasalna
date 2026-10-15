"""test_admin_pages_min.py — PR 4.9: admin pages minimum (admin.html · admin-view.html).

Structure / absence checks (the pages are rebuilt in 5.3):
  A. each page still serves through page_shell.apply_shell (no stray {{v:}})
  B. served page loads tw_shared.js → admin-session.js → tw-overlay.js (DS-OVL) in order
  C. no native confirm / alert / prompt call
  D. no raw fetch( — admin calls go through TwAdminSession.fetch (login via twApi)
  E. local helpers duplicated by tw_shared.js are gone
  F. every twT('admin.…') key used exists in tw_strings.json
  G. every delete / migrate twConfirm is danger:true (admin-view.html — admin.html confirms through
     TwAdminShell.run: behaviour test node tests/test_admin_shell_runtime.js, task 5.3a)
Page JS = inline <script> + the page's own script files (tools/page_audit.page_files).
Run: python tests/test_admin_pages_min.py
"""
import json
import re
import sys

from page_shell import apply_shell
from tools.page_audit import page_files

PAGES = ("admin.html", "admin-view.html")
STRINGS = json.load(open("tw_strings.json", encoding="utf-8"))["ar"]
_fail = 0


def check(name, ok, info=""):
    global _fail
    print(("PASS " if ok else "FAIL ") + name + (("  — " + info) if info and not ok else ""))
    if not ok:
        _fail += 1


def page_js(page, src):
    own = [open(f, encoding="utf-8").read() for f in page_files(page)[1:] if f.endswith(".js")]
    return "\n".join(re.findall(r"<script>(.*?)</script>", src, re.S) + own)


for page in PAGES:
    src = open(page, encoding="utf-8").read()
    js = page_js(page, src)

    served = src
    try:
        served = apply_shell(src, page)
        check(f"A {page} serves", True)
    except ValueError as e:
        check(f"A {page} serves", False, str(e))

    order = [re.search(r'src="/(?:static/)?tw_shared\.js', served), served.find('src="/static/shared/admin-session.js'),
             served.find('src="/static/shared/tw-overlay.js')]
    order = [order[0].start() if order[0] else -1] + order[1:]
    check(f"B {page} script order", -1 not in order and order == sorted(order), str(order))

    native = re.findall(r"(?<![\w.$])(?:window\.)?(confirm|alert|prompt)\s*\(", js)
    check(f"C {page} no native confirm/alert/prompt", not native, str(native))

    raw = re.findall(r"(?<![\w.$])fetch\s*\(", js)
    check(f"D {page} no raw fetch", not raw, f"{len(raw)} call(s)")

    local = re.findall(r"function\s+(showToast|toast|setBtnLoad|twNavigate|initScrollProg)\s*\(", js)
    check(f"E {page} no local shared helpers", not local, str(local))

    keys = re.findall(r"twT\('(admin\.[\w.]+)'", js)
    # 'admin.x.' + value → a dynamic key: at least one key with that prefix must exist
    missing = [k for k in keys if (not any(x.startswith(k) for x in STRINGS) if k.endswith(".") else k not in STRINGS)]
    check(f"F {page} admin.* keys exist", bool(keys) and not missing, str(missing))

    if page == "admin.html":
        continue   # G: confirms run through TwAdminShell.run — node tests/test_admin_shell_runtime.js
    calls = re.findall(r"twConfirm\(\{[^}]*\}\)", js)
    risky = [c for c in calls if re.search(r"admin\.(delete|migrate)", c) and "danger:true" not in c]
    check(f"G {page} delete/migrate confirms are danger", bool(calls) and not risky, str(risky))

print(f"\n{'FAILED' if _fail else 'OK'} ({_fail} failure(s))")
sys.exit(1 if _fail else 0)
