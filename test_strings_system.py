"""test_strings_system.py — Strings System + Glossary (PR 3.6 · SYSTEMS_INDEX §59 · docs/GLOSSARY.md).

  A. tw_strings.json loads (ar dictionary, valid keys, glossary keys present)
  B. twT runtime (node, real code from tw_shared.js): text · {vars} · missing key → key + one warning
  C. admin override validation: unknown key / HTML / too long / unknown {var} rejected · empty = default
  D. page delivery: <!--tw:strings--> before tw_shared.js on every page · read_html fills it · admin endpoints
  E. header + bottom nav + header menu + appointments.html carry no fixed Arabic text
  F. glossary report — forbidden words counted across the site (report only, converted places = 0)

Run: python test_strings_system.py
"""
import glob
import json
import os
import re
import subprocess
import sys

import tw_strings

failures = []
AR = re.compile(r"[؀-ۿ]")


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        failures.append(name)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


AR_DICT = tw_strings.DEFAULTS["ar"]
TWS = read("tw_shared.js")

print("\nA — defaults file")
check("A ar dictionary loaded", len(AR_DICT) > 20)
for k in ("account.type.emp", "account.type.co", "account.type.edu", "jobs.post",
          "people.applicants", "people.candidates", "people.talent_bank", "nav.home"):
    check(f"A key {k}", k in AR_DICT)
check("A account type emp = حساب شخصي", AR_DICT["account.type.emp"] == "حساب شخصي")
check("A jobs.post = نشر وظيفة", AR_DICT["jobs.post"] == "نشر وظيفة")

print("\nB — twT runtime (real code)")
src = TWS.split("var _twTWarned = {};")[1].split("window.twT = twT;")[0]
js = ("var warns = []; var console = { warn: function (m) { warns.push(m); } };"
      "var window = { TW_STRINGS: { lang: 'ar', dict: " + json.dumps(
          {"a.b": "مرحبا {name}", "a.c": "نص", "a.d": "{x} و {y}"}, ensure_ascii=False) + " } };"
      "var _twTWarned = {};" + src +
      "var out = { text: twT('a.c'), vars: twT('a.b', { name: 'زعتر' }), keep: twT('a.d', { x: 1 }),"
      " miss1: twT('no.key'), miss2: twT('no.key'), noDict: null };"
      "out.warns = warns.length;"
      "window.TW_STRINGS = undefined; out.noDict = twT('a.c');"
      "process.stdout.write(JSON.stringify(out));")
try:
    r = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30).stdout)
except Exception as e:
    r = {}
    check("B node run", False, e)
check("B text by key", r.get("text") == "نص", r)
check("B {name} replaced", r.get("vars") == "مرحبا زعتر", r)
check("B unknown {y} kept as is", r.get("keep") == "1 و {y}", r)
check("B missing key → the key", r.get("miss1") == "no.key" and r.get("miss2") == "no.key", r)
check("B missing key warns once", r.get("warns") == 1, r)
check("B no dictionary → the key (no throw)", r.get("noDict") == "a.c", r)

print("\nC — admin override validation")


def rejects(raw, code):
    try:
        tw_strings.validate_overrides(raw)
    except tw_strings.StringsError as e:
        return e.code == code
    return False


check("C unknown key rejected", rejects({"nav.nope": "x"}, "unknown_key"))
check("C HTML rejected", rejects({"nav.home": "<b>الرئيسية</b>"}, "html_not_allowed"))
check("C script rejected", rejects({"nav.home": "x<script>"}, "html_not_allowed"))
check("C too long rejected", rejects({"nav.home": "ا" * (tw_strings.MAX_LEN + 1)}, "too_long"))
check("C control char rejected", rejects({"nav.home": "a\u0000b"}, "invalid_value"))
check("C non-text rejected", rejects({"nav.home": 5}, "invalid_value"))
check("C {var} not in default rejected", rejects({"nav.home": "{x}"}, "unknown_placeholder"))
check("C body not a dict rejected", rejects(["x"], "invalid_body"))
ok = tw_strings.validate_overrides({"nav.home": "  البداية ", "page.title": "{page} | تواصلنا", "nav.messages": ""})
check("C valid override kept (trimmed) · default {var} allowed · empty = default",
      ok == {"nav.home": "البداية", "page.title": "{page} | تواصلنا"}, ok)
check("C stored junk dropped, never raised",
      tw_strings.parse_stored('{"nav.home":"<i>","nav.appointments":"مواعيدي"}') == {"nav.appointments": "مواعيدي"}
      and tw_strings.parse_stored("not json") == {})
blk = tw_strings.page_block({"nav.home": "البداية"})
check("C page block = merged dict, script-safe",
      blk.startswith("<script>window.TW_STRINGS=") and '"nav.home":"البداية"' in blk
      and blk.count("<") == 2 and " " not in blk)

print("\nD — page delivery + admin endpoints")
SRV = read("server.py")
check("D read_html fills the marker from the cached override block",
      "_read_html_cached(name).replace(tw_strings.MARKER, _STRINGS_BLOCK, 1)" in SRV)
check("D overrides loaded at startup (no DB call while serving a page)",
      "await asyncio.to_thread(_strings_load_overrides)" in SRV)
get_ = SRV.split('@app.get("/admin/strings")')[1].split("\n@app.")[0]
put_ = SRV.split('@app.put("/admin/strings")')[1].split("\n@app.")[0]
check("D GET /admin/strings admin-only", "check_admin(request)" in get_)
check("D PUT /admin/strings admin-only + validated + saved + live",
      "check_admin(request)" in put_ and "tw_strings.validate_overrides(" in put_
      and "set_site_setting(tw_strings.setting_key()" in put_ and "_strings_set_overrides(clean)" in put_)
shell = read("partials/shell-scripts.html")
check("D shell: marker right before tw_shared.js",
      "<!--tw:strings-->\n<script src=\"/static/tw_shared.js" in shell)
for page in sorted(glob.glob("*.html")):
    raw = read(page)
    m = re.search(r'<script src="/tw_shared\.js', raw)
    if m:
        check(f"D {page}: marker before tw_shared.js", 0 <= raw.rfind("<!--tw:strings-->", 0, m.start()))

print("\nE — no fixed text in the converted places")
HDR = TWS.split("function _twHeaderHtml")[1].split("\nfunction ")[0]
NAV = TWS.split("var _TW_BOTTOM_NAV = [")[1].split("\n];")[0]
MENU = TWS.split("var _TW_HEADER_MENU_POLICY = [")[1].split("\n];")[0]
ITEM = TWS.split("function _twHeaderMenuItemHtml")[1].split("\nfunction ")[0]
MOUNT = TWS.split("function twMountAppChrome")[1].split("\nwindow.twMountAppChrome")[0]
for name, part in (("header", HDR), ("bottom nav", NAV), ("header menu", MENU),
                   ("menu item", ITEM), ("mount", MOUNT)):
    check(f"E {name}: no Arabic text", not AR.search(part), AR.findall(part)[:5])
APPT = read("appointments.html")
code = re.sub(r"<!--.*?-->|//[^\n]*|/\*.*?\*/", "", APPT.split("<body>")[1], flags=re.S)
check("E appointments.html body: no Arabic text", not AR.search(code), AR.findall(code)[:5])
check("E appointments.html <title> set by twT", "<title></title>" in APPT and "document.title = twT(" in APPT)
used = set(re.findall(r"""(?:twT\(|_twLbl\(|labelKey: |data-tw-t(?:-label)?=)['"]([a-z0-9_.]+)['"]""", TWS + APPT))
used |= set(re.findall(r"'(nav\.account\.[a-z]+)'", NAV))
missing = sorted(k for k in used if k not in AR_DICT and not k.endswith(".") and k != "key")
check("E every literal key used exists in tw_strings.json", not missing, missing)

print("\nF — glossary report (forbidden words)")
rows = [r for r in read("docs/GLOSSARY.md").splitlines() if r.startswith("| ") and "`" in r.split("|")[-2]]
terms = []
for r in rows:
    for m in re.finditer(r"`([^`]+)`( \(مراجعة\))?", r.split("|")[-2]):
        terms.append((m.group(1), bool(m.group(2))))
check("F glossary parsed", len(terms) >= 8, terms)
files = [f for f in glob.glob("*.html") + glob.glob("*.js") + glob.glob("static/**/*.js", recursive=True)
         if not os.path.basename(f).startswith("test_") and "/vendor/" not in f]
for term, review in terms:
    hits = {f: len(re.findall(term, read(f))) for f in files}
    hits = {f: n for f, n in hits.items() if n}
    tag = "مراجعة" if review else "مخالفة"
    print(f"  REPORT  {term} ({tag}): {sum(hits.values())} في {len(hits)} ملف"
          + ("" if not hits else " — " + ", ".join(f"{f}:{n}" for f, n in sorted(hits.items())[:6])))
    for name, part in (("header/nav/menu", HDR + NAV + MENU + ITEM), ("appointments.html", APPT),
                       ("tw_strings.json", json.dumps(AR_DICT, ensure_ascii=False))):
        if not review:
            check(f"F {name}: no «{term}»", not re.search(term, part))

print(f"\n{'=' * 50}\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
