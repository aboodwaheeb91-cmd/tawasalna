"""test_header_nav.py — Unified App Header + Bottom Nav (PR 3.2 · docs/design-system/HEADER-NAV.md).

Static checks:
  A. every converted page mounts the ONE header (placeholder) and keeps no old header code
  B. header order = [back?] home · logo · bell · messages · menu (auth) / login · register (guest)
  C. one logo source (/static/33333.svg via TW_LOGO_SRC)
  D. bottom nav = one registry per account type, no href="#", current tab marked
  E. one badge cap (99+) for bell + messages

Run: python test_header_nav.py
"""
import re
import sys

failures = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  [{detail}]"))
    if not cond:
        failures.append(name)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


TWS = read("tw_shared.js")
CSS = read("static/app-header.css")
HDR = TWS.split("function _twHeaderHtml")[1].split("\nfunction ")[0]

# page → expected data-back (None = no back button)
PAGES = {
    "home-v2.html": None, "notifications.html": None, "messages.html": None,
    "edu-profile.html": None, "appointments.html": None,
    "settings.html": "account", "appointment-room.html": "/appointments", "job-detail.html": "home",
}
WITH_BOTTOM_NAV = {"home-v2.html", "notifications.html", "edu-profile.html", "appointments.html"}
OLD_HEADER = [r'class="sc-header', r'class="nav"', r'class="hdr"', r'class="bnav', r'hw-bnav', r'notif-bnav',
              r'nav-logo', r'(sc|nt|ep|hw|co)MenuBtn', r'initGlobalHeaderMenu\(', r'data-lucide="(home|bell|menu)"',
              r'jdBackBtn', r'goMessenger', r'goBack\(']

print("\nA — converted pages mount the unified header")
for page, back in PAGES.items():
    raw = read(page)
    tag = ('<header data-tw-header data-back="%s"></header>' % back) if back else "<header data-tw-header></header>"
    check(f"A {page}: one header placeholder {tag}", raw.count("data-tw-header") == 1 and tag in raw)
    left = [p for p in OLD_HEADER if re.search(p, raw)]
    check(f"A {page}: no old header code", not left, left)
    check(f"A {page}: no other logo source", "33333.svg" not in raw and "Logo.svg" not in raw)
    check(f"A {page}: loads app-header.css + DS-ICON registry",
          "/static/app-header.css" in raw and "/static/shared/tw-icons.js" in raw)
    has_nav = "<nav data-tw-bottom-nav></nav>" in raw
    check(f"A {page}: bottom nav {'present' if page in WITH_BOTTOM_NAV else 'absent'}",
          has_nav == (page in WITH_BOTTOM_NAV))
check("A home.header.js deleted (header wiring lives in tw_shared.js)",
      "home.header.js" not in read("home-v2.html") and "Home.header" not in read("static/home/home.main.js"))

print("\nB — header order")
pos = [HDR.find(x) for x in ['data-tw-hdr-back', 'data-key="home"', 'class="sc-logo"',
                             'data-key="notifications"', 'data-key="messages"', 'twHdrMenuBtn',
                             'data-tw-session="guest" hidden>تسجيل الدخول', 'href="/login#register"']]
check("B back · home · logo · bell · messages · menu · login · register (DOM = RTL order)",
      all(p > 0 for p in pos) and pos == sorted(pos), pos)
check("B auth items hidden by default (data-tw-session=authenticated) — home, bell, messages, menu",
      HDR.count('data-tw-session="authenticated" hidden') == 4)
check("B guest items: login with ?next= (twLoginHref) + register /login#register",
      "twLoginHref(location.pathname + location.search)" in HDR and HDR.count('data-tw-session="guest" hidden') == 2)
check("B icons from DS-ICON (twIcon) — no inline <svg> / lucide in the header",
      "<svg" not in HDR and "lucide" not in HDR and HDR.count("_twIco(") >= 5)
check("B back uses NAV-05 resolver (no bare history.back())",
      "twNavBack(_twBackFallback(" in TWS and "entryType === 'push'" in TWS)
check("B menu wired by initGlobalHeaderMenu (VM-10)", "initGlobalHeaderMenu('twHdrMenuBtn', 'twHdrMenuDd')" in TWS)

print("\nC — one logo source")
check("C TW_LOGO_SRC = /static/33333.svg", "var TW_LOGO_SRC = '/static/33333.svg';" in TWS)
check("C header uses TW_LOGO_SRC", "TW_LOGO_SRC" in HDR)

print("\nD — bottom nav registry")
REG = TWS.split("var _TW_BOTTOM_NAV = [")[1].split("\n];")[0]
keys = re.findall(r"key: '([a-z]+)'", REG)
check("D keys = home · appointments · messages · notifications · account", keys ==
      ["home", "appointments", "messages", "notifications", "account"], keys)
check("D no '#' href in the registry", "'#'" not in REG and '"#"' not in REG)
check("D account label + icon per type (emp / co / edu)",
      "emp: 'ملفي', co: 'شركتي', edu: 'مؤسستي'" in REG and "twAccountHref(u)" in REG)
check("D resolved href never empty (fallback '/')", "href: href || '/'" in TWS)
check("D current tab = aria-current=page + .is-current", 'is-current" aria-current="page' in TWS)
check("D bottom nav only for authenticated sessions", "nav.hidden = !auth;" in TWS)
check("D mobile only (hidden ≥ 1020px) + body clearance",
      re.search(r"@media \(min-width: 1020px\) \{\s*\.tw-bnav \{ display: none; \}", CSS) is not None
      and "body.tw-has-bnav" in CSS)

print("\nE — one badge cap for bell + messages")
check("E no 9+ cap left", "'9+'" not in TWS and "'9+'" not in read("messages.ws.js"))
check("E messages badge uses twNotifBadgeLabel (loader + WS + messages page)",
      TWS.count("twNotifBadgeLabel(count)") >= 3 and "twNotifBadgeLabel(count)" in read("messages.ws.js"))
check("E header badges carry data-badge notif / msgs", 'data-badge="notif"' in HDR and 'data-badge="msgs"' in HDR)

print(f"\n{'=' * 50}\n{'FAILED: ' + str(len(failures)) if failures else 'All checks passed.'}")
sys.exit(1 if failures else 0)
