"""
test_landing_shell.py — landing.html (/ and /landing.html), Phase C (second converted page)
PAGE-SHELL (F39) · DS-ICON (F37) · DS-SIZE (F36) · DS-COLOR (F35) · Auth Gateway (entry page) · §32 (SW offline)

Static checks on the page as served by read_html (apply_shell), plus sw.js and server.py.
Run: python tests/test_landing_shell.py
"""
import re
import struct
import subprocess
import sys

import page_shell
from page_shell import apply_shell, asset_hash

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


RAW = read("landing.html")
HTML = apply_shell(RAW, "landing.html")          # = read_html("landing.html")
RAW_NC = re.sub(r"/\*[\s\S]*?\*/", "", RAW)    # without CSS / JS block comments
CSS = "\n".join(re.findall(r"<style>([\s\S]*?)</style>", RAW))
JS = RAW[RAW.rindex("<script>"):RAW.rindex("</script>")]
JS_CODE = re.sub(r"^\s*//.*$|/\*[\s\S]*?\*/", "", JS, flags=re.M)
SW = read("sw.js")
SRV = read("server.py")

print("\nA — Page Shell (F39)")
check("A01 raw page: each app marker once",
      RAW.count("<!--tw:shell-head-->") == 1 and RAW.count("<!--tw:shell-scripts-->") == 1)
check("A02 raw page: no shell-owned tags copied by hand",
      not re.search(r'charset|name="viewport"|theme-color|rel="manifest"|apple-touch-icon|rel="icon"'
                    r'|mobile-web-app|fonts\.g|tw_shared|auth-sync', RAW_NC))
check("A03 head marker is the first line after <head>", "<head>\n<!--tw:shell-head-->" in RAW)
check("A04 shared CSS first: tw_shared.css → page <style>",
      HTML.index("tw_shared.css") < HTML.index("<style>\n/* Landing"))
check("A05 tw_shared.js → auth-sync.js → tw-icons.js → page script",
      HTML.index("/static/tw_shared.js?v=") < HTML.index("auth-sync.js?v=")
      < HTML.index("/static/shared/tw-icons.js") < HTML.rindex("<script>"))
srcs = re.findall(r'(?:src|href)="([^"?#]+)', HTML)
dups = sorted({s for s in srcs if srcs.count(s) > 1 and s.endswith((".css", ".js"))})
check("A06 no CSS/JS loaded twice", not dups, dups)
check("A07 charset is the first tag in <head>",
      HTML.index("<head>") < HTML.index('charset="UTF-8"') < HTML.index("<title>"))
check("A08 no legacy root /tw_shared.js on the page (SW allowlist needs /static/)",
      'src="/tw_shared.js' not in HTML)

print("\nB — SEO (page-owned, exactly once when served)")
SEO = ['<title>', 'name="description"', 'property="og:title"', 'property="og:description"',
       'property="og:type"', 'property="og:url"', 'property="og:locale"', 'name="twitter:card"',
       'name="twitter:title"', 'name="twitter:description"', 'name="robots"', 'rel="canonical"']
check("B01 each SEO tag exactly once", all(HTML.count(t) == 1 for t in SEO),
      [t for t in SEO if HTML.count(t) != 1])
partials = "".join(read(f"partials/{p}") for p in ("shell-head.html", "shell-scripts.html"))
check("B02 SEO tags live in the page, not in the shell",
      all(t in RAW and t not in partials for t in SEO))

print("\nC — DS-ICON (F37)")
check("C01 no Lucide / unpkg / CDN script", not re.search(r"lucide|unpkg|cdn\.", HTML, re.I))
check("C02 no inline <svg> / data-lucide in the page HTML", "<svg" not in RAW and "data-lucide" not in RAW)
names = re.findall(r'<i data-tw-icon="([a-z0-9-]+)"(?: data-tw-size="([a-z0-9]+)")?></i>', RAW)
check("C03 static icons = <i data-tw-icon> placeholders", len(names) >= 25 and
      RAW.count("data-tw-icon=") == len(names), len(names))
REG = read("static/shared/tw-icons.js")
reg_names = set(re.findall(r"^\s+'([a-z0-9-]+)': \[[01],", REG, re.M))
check("C04 every icon is a registry meaning name (not an alias / unknown)",
      {n for n, _ in names} <= reg_names, {n for n, _ in names} - reg_names)
check("C05 icon sizes are DS-SIZE icon tokens only",
      {s for _, s in names} <= {"xs", "sm", "md", "lg", "xl", "2xl"}, {s for _, s in names})
check("C06 hydrated once (twIcon.hydrate) after the entry redirect check",
      JS_CODE.count("twIcon.hydrate(document.body)") == 1
      and JS_CODE.index("twEntryDestination") < JS_CODE.index("twIcon.hydrate"))
check("C07 no stroke / stroke-width in page CSS (currentColor · width 2 — ICON-06/07)",
      not re.search(r"(?<![\w-])stroke(-width)?\s*:", CSS + RAW))
EMOJI = re.compile("[←-⇿✓✔☀-➿⬀-⯿\U0001F000-\U0001FAFF️]")
check("C08 no emoji / glyph icons (ICON-11)", not EMOJI.search(RAW_NC), EMOJI.findall(RAW_NC))

print("\nD — Entry page (Auth Gateway 6 · VM-10 · §54)")
check("D01 no direct localStorage / tw_user", "localStorage" not in RAW_NC and "tw_user" not in RAW_NC)
check("D02 redirect only via twEntryDestination() (TwAuthSync snapshot)",
      "twEntryDestination()" in JS_CODE and JS_CODE.count("location.replace(") == 1
      and "location.replace(_dest)" in JS_CODE and "location.href" not in JS_CODE)
check("D03 no guard on the entry page", 'name="tw-page"' not in RAW)
check("D04 no innerHTML / inline handlers", "innerHTML" not in JS_CODE and not re.search(r"\son[a-z]+=", RAW))

print("\nE — DS-SIZE (F36) · DS-COLOR (F35)")
check("E01 no --size-* / --radius-* / --space-* / --color-* defined in the page",
      not re.search(r"--(size|radius|space|color)-[\w-]+\s*:", CSS))
check("E02 shared legacy aliases not redefined locally (--ac/--ac2/--bg/--t1…--t4)",
      not re.search(r"(?<![\w-])--(ac|ac2|ac3|bg|t|t1|t2|t3|t4|card|border)\s*:", CSS))
check("E03 brand / surface / white hex not hard-coded (DS-COLOR tokens)",
      not re.search(r"#(00c896|2563ff|8b5cf6|070b18|fff|ffffff)\b", CSS + RAW, re.I))
check("E04 brand rgb channels via --color-brand-*-rgb",
      not re.search(r"rgba\(\s*(0,\s*200,\s*150|37,\s*99,\s*255)\s*,", CSS))
MATCH = {"font-size": r"\.(6|62|58|57|61|59|65|68|66|67|63|64|72|75|7|74|73|71|69|78|76|77|79|82|8|85|84|83|9|88|92|95)rem"
                      r"|1rem|1\.2rem|1\.4rem|1\.6rem|2rem|(10|12|13|14|15|16)px",
         "border-radius": r"(4|6|8|10|12|14|16|20|99|999|50)px|50%",
         "space": r"(2|4|6|8|10|12|14|16|18|20|24|32|40)px"}
left = []
for prop, val in re.findall(r"(?<![\w-])([a-z-]+)\s*:\s*([^;{}\"]+)", CSS + "\n" + " ".join(re.findall(r'style="([^"]*)"', RAW))):
    if "clamp(" in val:   # clamp() headings — local T3 (SIZE-09)
        continue
    key = "space" if re.match(r"(padding|margin)(-[a-z-]+)?$|(row-|column-)?gap$", prop) else prop
    if key in MATCH and re.search(r"(?<![\w.-])(" + MATCH[key] + r")(?![\w%])", val):
        left.append(f"{prop}: {val.strip()}")
check("E05 no matching / sub-pixel raw value left (SIZE-05)", not left, left)

print("\nF — Offline fallback (§32 Service Worker)")
assets = re.search(r"const STATIC_ASSETS = \[([\s\S]*?)\];", SW).group(1)
precache = set(re.findall(r"'([^']+)'", assets))
check("F01 landing is the offline fallback and precached",
      "const OFFLINE_FALLBACK = '/landing.html';" in SW and "OFFLINE_FALLBACK," in assets)
shell_assets = set(re.findall(r'(?:src|href)="(/static/[^"?]+)', partials))
check("F02 every shell CSS/JS (partials) is precached", shell_assets and shell_assets <= precache,
      shell_assets - precache)
page_assets = set(re.findall(r'(?:src|href)="(/static/[^"?]+\.(?:css|js))', HTML))
check("F03 every CSS/JS the served page loads is precached", page_assets <= precache, page_assets - precache)
check("F04 offline match ignores the ?v= hash (precache stores bare paths)",
      "caches.match(request, { ignoreSearch: true })" in SW)
try:
    base = subprocess.run(["git", "merge-base", "origin/main", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "-U0", base, "--", "sw.js"], capture_output=True,
                          text=True, check=True).stdout
    check("F05 sw.js changed → BUILD_TIME bumped (activate drops old caches)",
          not diff or re.search(r"^\+const BUILD_TIME = ", diff, re.M))
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    check("F05 git diff vs origin/main available", False, str(e))

print("\nG — Routes & caching")
check("G01 / and /landing.html serve read_html('landing.html') (shell applied)",
      SRV.count('read_html("landing.html")') == 2)
check("G02 / keeps Cache-Control max-age=300", 'headers={"Cache-Control": "public, max-age=300"}' in SRV)
check("G03 shared assets carry the content hash ?v= (busts the 1-day /static cache)",
      all(re.search(re.escape(a) + r"\?v=[0-9a-f]{10}\"", HTML)
          for a in ("/static/tw_shared.css", "/static/tw_shared.js", "/static/shared/auth-sync.js")))

print("\nH — F30 close-out of PR #560 (signup links · offline logo · page ?v= · share image)")
UI = read("index.ui.js")
hrefs = re.findall(r'<a href="(/login[^"]*)"', RAW)
check("H01 signup links open the register form (one link per role hash + general register)",
      all(h in hrefs for h in ("/login#register", "/login#register-emp", "/login#register-co",
                               "/login#register-edu", "/login")), hrefs)
check("H01b guest header = unified app header (twMountAppChrome — HEADER-NAV.md), no page nav",
      RAW.count("<header data-tw-header></header>") == 1 and "<nav" not in RAW
      and "/static/app-header.css" in RAW)
check("H02 index.ui.js hash router maps each hash to the right form",
      "hash === '#register-emp')      { showRegister(); selectType('emp'); }" in UI
      and "hash === '#register-co')  { showRegister(); selectType('co');  }" in UI
      and "hash === '#register-edu') { showRegister(); selectType('edu'); }" in UI
      and "hash === '#register')     { showRegister(); }" in UI)
page_imgs = set(re.findall(r'<img src="(/static/[^"?]+)"', RAW))
check("H03 every page <img> (logo) is precached for offline", page_imgs and page_imgs <= precache,
      page_imgs - precache)
th = asset_hash("static/shared/tw-icons.js")
check("H04 tw-icons.js carries its content hash (landing + job-detail, {{v:}} in the page)",
      f'/static/shared/tw-icons.js?v={th}"' in HTML and "{{" not in HTML
      and f'tw-icons.js?v={th}"' in apply_shell(read("job-detail.html"), "job-detail.html"))
check("H05 tw-icons.js is a page asset, never a shell asset (F37)",
      "tw-icons.js" in page_shell.PAGE_ASSETS and "tw-icons.js" not in page_shell.SHELL_ASSETS)
_pg = "<head>\n<!--tw:shell-head-->\n{}\n<!--tw:shell-scripts-->\n</html>"
for case, bad in (("unknown asset", _pg.format('<script src="/x.js?v={{v:x.js}}">')),
                  ("shell asset via page", _pg.format('<link href="/a?v={{v:tw_shared.css}}">')),
                  ("path-like name", _pg.format("{{v:../server.py}}")),
                  ("no markers", '<script src="/x.js?v={{v:tw-icons.js}}">')):
    try:
        apply_shell(bad, "bad.html")
        check(f"H06 {case} placeholder raises ValueError", False, "no error")
    except ValueError:
        check(f"H06 {case} placeholder raises ValueError", True)
check("H07 page placeholders resolve before the partials go in (partials never re-scanned)",
      apply_shell(_pg.format("ok"), "t.html", page_hashes={}).count("{{") == 0)
OG = "https://tawasolna.com/static/og-image.png"
SHARE = {'property="og:site_name" content="تواصلنا"', f'property="og:image" content="{OG}"',
         'property="og:image:width" content="1200"', 'property="og:image:height" content="630"',
         'property="og:image:type" content="image/png"', 'name="twitter:card" content="summary_large_image"',
         f'name="twitter:image" content="{OG}"'}
check("H08 share tags present exactly once", all(HTML.count(t) == 1 for t in SHARE),
      [t for t in SHARE if HTML.count(t) != 1])
with open("static/og-image.png", "rb") as f:
    head = f.read(24)
check("H09 static/og-image.png is a 1200×630 PNG",
      head[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", head[16:24]) == (1200, 630))

print(f"\n{_run - len(failures)}/{_run} passed")
sys.exit(1 if failures else 0)
