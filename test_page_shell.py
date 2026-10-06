"""
test_page_shell.py — Page Shell (PR-8 / Phase B · docs/design-system/PAGE-SHELL.md)

Run: python test_page_shell.py
"""
import os
import re
import shutil
import sys
import tempfile

import page_shell
from page_shell import apply_shell, build_shell, asset_hash, SHELL_ASSETS

failures = []
_run = 0


def check(name, cond, detail=""):
    global _run
    _run += 1
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f" — {detail}"))
    if not cond:
        failures.append(name)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


PAGE = ("<!DOCTYPE html><html><head>\n<!--tw:shell-head-->\n<title>t</title>\n"
        '<link rel="stylesheet" href="/static/page.css">\n</head><body>\n'
        "<!--tw:shell-scripts-->\n<script src=\"/static/page.js\"></script>\n</body></html>")

print("\nA — marker replacement (app)")
out = apply_shell(PAGE, "t.html")
check("A01 markers removed", "<!--tw:shell-" not in out)
for asset in ("/static/tw_shared.css?v=", "/static/tw_shared.js?v=", "/static/shared/auth-sync.js?v=",
              'rel="manifest"', 'charset="UTF-8"', 'name="viewport"', 'name="theme-color"',
              'rel="icon"', 'href="/apple-touch-icon.png"', "Cairo:wght@400;500;600;700;800;900"):
    check(f"A02 '{asset}' exactly once", out.count(asset) == 1, out.count(asset))
check("A03 shared CSS before page CSS",
      out.index("/static/tw_shared.css") < out.index("/static/page.css"))
check("A04 head block inside <head>", out.index("tw_shared.css") < out.index("</head>"))
check("A05 tw_shared.js → auth-sync.js → page JS",
      out.index("/tw_shared.js") < out.index("auth-sync.js") < out.index("/static/page.js"))
check("A06 no tw-icons.js in shell", "tw-icons" not in out)
check("A07 no unfilled placeholder", "{{" not in out)
check("A08 hash is 10 hex chars",
      re.search(r"tw_shared\.css\?v=[0-9a-f]{10}\"", out) is not None)

print("\nB — page without markers is unchanged")
for name in ("index.html", "messages.html", "admin.html"):
    raw = read(name)
    check(f"B01 {name} byte-identical", apply_shell(raw, name) == raw)

print("\nC — admin variant")
adm = apply_shell(PAGE.replace("shell-head-->", "shell-head:admin-->")
                      .replace("shell-scripts-->", "shell-scripts:admin-->"), "a.html")
check("C01 markers removed", "<!--tw:shell-" not in adm)
check("C02 no auth-sync", "auth-sync" not in adm)
check("C03 no manifest", "manifest" not in adm)
check("C04 SW opt-out meta", '<meta name="tw-sw" content="off">' in adm)
check("C05 tw_shared.js + css once", adm.count("/static/tw_shared.js?v=") == 1 and adm.count("tw_shared.css?v=") == 1)
check("C06 tw_shared.js honours tw-sw=off",
      'meta[name="tw-sw"][content="off"]' in read("tw_shared.js"))

print("\nD — invalid marker use fails loudly")
for label, bad in (("head only", "<head><!--tw:shell-head--></head>"),
                   ("twice", PAGE + "<!--tw:shell-head-->"),
                   ("mixed", PAGE.replace("shell-scripts-->", "shell-scripts:admin-->")),
                   ("unknown", "<!--tw:shell-foo-->"),
                   ("order", "<!--tw:shell-scripts--><!--tw:shell-head-->")):
    try:
        apply_shell(bad, "bad.html")
        check(f"D01 {label} raises", False, "no error")
    except ValueError:
        check(f"D01 {label} raises", True)

print("\nE — content hash changes with the file")
tmp = tempfile.mkdtemp()
try:
    shutil.copytree("partials", os.path.join(tmp, "partials"))
    os.makedirs(os.path.join(tmp, "static", "shared"))
    for rel in SHELL_ASSETS.values():
        shutil.copy(rel, os.path.join(tmp, rel))
    s1 = build_shell(tmp)
    with open(os.path.join(tmp, "tw_shared.css"), "a", encoding="utf-8") as f:
        f.write("\n/* change */\n")
    s2 = build_shell(tmp)
    h1, h2 = s1["<!--tw:shell-head-->"], s2["<!--tw:shell-head-->"]
    check("E01 css hash changed", h1 != h2)
    check("E02 js hashes unchanged", s1["<!--tw:shell-scripts-->"] == s2["<!--tw:shell-scripts-->"])
    check("E03 hash = sha256 prefix of the real file",
          f"tw_shared.css?v={asset_hash('tw_shared.css')}" in page_shell._SHELL["<!--tw:shell-head-->"])
finally:
    shutil.rmtree(tmp)

print("\nF — home-v2.html (pilot page) through the shell")
raw = read("home-v2.html")
hv2 = apply_shell(raw, "home-v2.html")
check("F01 raw page uses app markers", raw.count("<!--tw:shell-head-->") == 1
      and raw.count("<!--tw:shell-scripts-->") == 1)
check("F02 raw page has no shell-owned tags",
      not re.search(r'charset|name="viewport"|fonts\.googleapis|tw_shared|auth-sync', raw))
check("F03 tw_shared.css before app-header.css / home-v2.css",
      hv2.index("tw_shared.css") < hv2.index("app-header.css") < hv2.index("home-v2.css"))
srcs = re.findall(r'(?:src|href)="([^"?#]+)', hv2)
dups = sorted({s for s in srcs if srcs.count(s) > 1 and s.endswith((".css", ".js"))})
check("F04 no CSS/JS loaded twice", not dups, dups)
check("F05 auth-sync.js before home.header.js",
      hv2.index("auth-sync.js") < hv2.index("home.header.js"))
check("F06 charset is the first tag in <head>",
      hv2.index("<head>") < hv2.index('charset="UTF-8"') < hv2.index("<title>"))

print("\nG — server.read_html wiring (static)")
srv = read("server.py")
check("G01 read_html calls apply_shell", "content = apply_shell(content, name)" in srv)
check("G02 partials are not servable (.html not in /static allowlist)",
      "'.html'" not in srv[srv.index("def serve_static"):srv.index("def serve_static") + 600])

print(f"\n{_run - len(failures)}/{_run} passed")
sys.exit(1 if failures else 0)
