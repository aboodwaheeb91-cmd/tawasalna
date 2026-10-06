"""
test_job_detail_shell.py — job-detail.html, Phase C (first converted page)
PAGE-SHELL (F39) · DS-ICON (F37) · DS-IMAGE (F38) · DS-SIZE (F36) · DS-FEEDBACK (F34) · §54 · VM-10

Static checks on the page as served by read_html (apply_shell), its JS and CSS.
Run: python test_job_detail_shell.py
"""
import re
import sys

from page_shell import apply_shell

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


RAW = read("job-detail.html")
HTML = apply_shell(RAW, "job-detail.html")      # = read_html("job-detail.html")
JS = read("static/job/job-detail.js")
CSS = read("static/job/job-detail.css")
JS_CODE = re.sub(r"^\s*//.*$|/\*[\s\S]*?\*/", "", JS, flags=re.M)

print("\nA — Page Shell (F39)")
check("A01 raw page: each app marker once",
      RAW.count("<!--tw:shell-head-->") == 1 and RAW.count("<!--tw:shell-scripts-->") == 1)
check("A02 raw page: no shell-owned tags copied by hand",
      not re.search(r'charset|name="viewport"|theme-color|rel="manifest"|apple-touch-icon|fonts\.g|tw_shared|auth-sync', RAW))
check("A03 head marker is the first line after <head>", "<head>\n<!--tw:shell-head-->" in RAW)
check("A04 tw_shared.css → app-header.css → job-detail.css",
      HTML.index("tw_shared.css") < HTML.index("app-header.css") < HTML.index("job-detail.css"))
check("A05 tw_shared.js → auth-sync.js → tw-icons.js → job-detail.js",
      HTML.index("/static/tw_shared.js?v=") < HTML.index("auth-sync.js") < HTML.index("tw-icons.js")
      < HTML.index("job-detail.js"))
srcs = re.findall(r'(?:src|href)="([^"?#]+)', HTML)
dups = sorted({s for s in srcs if srcs.count(s) > 1 and s.endswith((".css", ".js"))})
check("A06 no CSS/JS loaded twice", not dups, dups)
check("A07 charset is the first tag in <head>",
      HTML.index("<head>") < HTML.index('charset="UTF-8"') < HTML.index("<title>"))
check("A08 partials load /static/tw_shared.js (SW §32 allowlist)",
      all('src="/static/tw_shared.js?v={{v:tw_shared.js}}"' in read(f"partials/{p}")
          for p in ("shell-scripts.html", "shell-scripts.admin.html")))
srv = read("server.py")
check("A09 legacy /tw_shared.js route still served (old pages)", '@app.get("/tw_shared.js")' in srv)
check("A10 /static/ serves root files (flat fallback → /static/tw_shared.js)",
      "_safe(static_dir, filename) or _safe(base_dir, filename)" in srv)
check("A11 SW caches /static/* (tw_shared.js now inside the allowlist)",
      "path.indexOf('/static/') === 0" in read("sw.js"))

print("\nB — DS-ICON (F37)")
check("B01 no Lucide bundle / CDN", not re.search(r"lucide|unpkg", HTML + JS + CSS, re.I), "lucide/unpkg found")
check("B02 no inline <svg> in the page HTML", "<svg" not in RAW)
check("B03 no _lucideIcon / createIcons", "_lucideIcon" not in JS and "createIcons" not in JS)
check("B04 icons via twIconEl", JS.count("twIconEl(") >= 10, JS.count("twIconEl("))
check("B05 skill icons: TW.getSkillIcon → twIconEl",
      "TW.getSkillIcon(skillName)" in JS and "twIconEl(_skillIconName(s)" in JS)
check("B06 back button = 'prev' (chevron, dir:true)", "_el('jdBackBtn'), 'prev'" in JS)
check("B07 no manual arrow / chevron names",
      not re.search(r"'(arrow|chevron)-(left|right)'", JS_CODE))
check("B08 icon sizes are DS-SIZE token names only",
      set(re.findall(r"size: '([^']+)'", JS_CODE)) | set(re.findall(r", '(xs|sm|md|lg|xl|2xl)'\)", JS_CODE))
      <= {"xs", "sm", "md", "lg", "xl", "2xl"})
EMOJI = re.compile("[←-⇿☀-➿⬀-⯿\U0001F000-\U0001FAFF️]")
check("B09 no emoji / glyph icons in HTML or JS (ICON-11)",
      not EMOJI.search(RAW) and not EMOJI.search(JS_CODE),
      EMOJI.findall(RAW) + EMOJI.findall(JS_CODE))

print("\nC — Session (VM-10 · Auth Gateway)")
check("C01 no direct localStorage in job-detail.js", "localStorage" not in JS)
check("C02 session from TwAuthSync.getSessionSnapshot()", "TwAuthSync.getSessionSnapshot()" in JS)
check("C03 JWT header via getAuthHeaders (tw_shared.js)", "getAuthHeaders(json)" in JS and "_jwt" not in JS)
check("C04 guest actions → /login (apply · save · report)",
      "location.href = '/login'" in JS and JS.count("if (!_authed) { _toLogin(); return; }") >= 3)

print("\nD — DS-IMAGE (F38) · §54")
check("D01 header logo = twAvatarHtml xl eager", "twAvatarHtml(_coEntity, 'xl', { eager: true })" in JS)
check("D02 company card logo = twAvatarHtml lg", "twAvatarHtml(_coEntity, 'lg')" in JS)
check("D03 no hand-built <img> / src assignment",
      "createElement('img')" not in JS and not re.search(r"\.src\s*=", JS_CODE))
check("D04 no local escaping function",
      not re.search(r"function\s+_?(esc|escape|escapeHtml|sanitize)\w*\s*\(|\.replace\(/</g", JS_CODE))
check("D05 no local .jd-logo / .jd-co-av size or shape (DS-IMAGE owns it)",
      not re.search(r"\.jd-(logo|co-av)\s*\{[^}]*(width|height|border-radius)", CSS))

print("\nE — DS-FEEDBACK (F34)")
check("E01 no jd-toast markup / CSS / JS", "jd-toast" not in RAW + CSS + JS and "jdToast" not in RAW + JS)
check("E02 no local showToast", not re.search(r"function\s+showToast", JS))
check("E03 shared showToast used", JS.count("showToast(") >= 5)

print("\nF — DS-SIZE (F36)")
check("F01 no --size-* / --radius-* / --space-* defined in job-detail.css",
      not re.search(r"--(size|radius|space)-[\w-]+\s*:", CSS))
MATCH = {"font-size": r"\.(6|62|58|57|61|59|65|68|66|67|63|64|72|75|7|74|73|71|69|78|76|77|79|82|8|85|84|83|9|88|92|95)rem"
                      r"|1rem|1\.2rem|1\.4rem|1\.6rem|2rem|(10|12|13|14|15|16)px",
         "border-radius": r"(4|6|8|10|12|14|16|20|99|999|50)px|50%",
         "space": r"(2|4|6|8|10|12|14|16|18|20|24|32|40)px"}
left = []
for prop, val in re.findall(r"(?<![\w-])([a-z-]+)\s*:\s*([^;{}]+)", CSS):
    key = "space" if re.match(r"(padding|margin)(-[a-z-]+)?$|(row-|column-)?gap$", prop) else prop
    if key in MATCH and re.search(r"(?<![\w.-])(" + MATCH[key] + r")(?![\w%])", val):
        left.append(f"{prop}: {val.strip()}")
check("F02 no matching / sub-pixel raw value left (SIZE-05)", not left, left)

print(f"\n{_run - len(failures)}/{_run} passed")
sys.exit(1 if failures else 0)
