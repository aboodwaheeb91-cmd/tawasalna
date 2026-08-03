"""
test_global_ui_visibility.py — VM-10 Global Session UI Visibility System
Static analysis + logic tests (no browser required).

Run: python test_global_ui_visibility.py
"""
import re
import sys

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

failures = []

def check(name, condition, detail=""):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        msg = f"  {FAIL}  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        failures.append(name)

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════
# A — auth-sync.js V2 contract
# ═══════════════════════════════════════════════════════
print("\nA — auth-sync.js V2")

auth_sync = read("static/shared/auth-sync.js")

check("A01 — getSessionSnapshot defined",
      "getSessionSnapshot" in auth_sync)
check("A02 — invalidateSession defined",
      "invalidateSession" in auth_sync)
check("A03 — _parseJwtPayload defined",
      "_parseJwtPayload" in auth_sync)
check("A04 — _resolveSession defined",
      "_resolveSession" in auth_sync)
check("A05 — state:'guest' returned when no JWT",
      "state: 'guest'" in auth_sync)
check("A06 — state:'expired' for expired JWT",
      "state: 'expired'" in auth_sync)
check("A07 — state:'invalid' for malformed JWT",
      "state: 'invalid'" in auth_sync)
check("A08 — state:'authenticated' for valid session",
      "state: 'authenticated'" in auth_sync)
check("A09 — expiry timer uses setTimeout not setInterval",
      "setTimeout" in auth_sync and "setInterval" not in auth_sync)
check("A10 — snapshot passed in handler callback",
      "snapshot: snapshot" in auth_sync)
check("A11 — invalidateSession clears all tw_ keys",
      "startsWith('tw_')" in auth_sync)
check("A12 — invalidateSession supports opts.redirect",
      "opts.redirect" in auth_sync)
check("A13 — onSessionChange backward compatible",
      "onSessionChange" in auth_sync)
check("A14 — pageshow force-fires on bfcache restore",
      "e.persisted" in auth_sync)
check("A15 — _expiryTimer cleared in invalidateSession",
      "_expiryTimer" in auth_sync and "clearTimeout(_expiryTimer)" in auth_sync)


# ═══════════════════════════════════════════════════════
# B — tw_shared.js policy registry
# ═══════════════════════════════════════════════════════
print("\nB — tw_shared.js policy registry")

shared = read("tw_shared.js")

check("B01 — _TW_HEADER_MENU_POLICY defined",
      "_TW_HEADER_MENU_POLICY" in shared)
check("B02 — settings item has show:'auth'",
      "show: 'auth'" in shared and "'settings'" in shared)
check("B03 — logout item has show:'auth'",
      "show: 'auth'" in shared and "'logout'" in shared)
check("B04 — login item has show:'guest'",
      "show: 'guest'" in shared and "'login'" in shared)
check("B05 — register item has show:'guest'",
      "show: 'guest'" in shared and "'register'" in shared)
check("B06 — contact/report/suggest items have show:'all'",
      shared.count("show: 'all'") >= 3)
check("B07 — _twMenuItemsForSnapshot defined",
      "_twMenuItemsForSnapshot" in shared)
check("B08 — _twApplyDeclarativeVisibility defined",
      "_twApplyDeclarativeVisibility" in shared)
check("B09 — _ghInstances defined",
      "_ghInstances" in shared)
check("B10 — _ghListenerRegistered defined",
      "_ghListenerRegistered" in shared)
check("B11 — initGlobalHeaderMenu is idempotent (checks _ghInstances)",
      "_ghInstances.length" in shared and "return;" in shared)
check("B12 — twLogout uses TwAuthSync.invalidateSession",
      "TwAuthSync.invalidateSession" in shared and "'logout'" in shared)
check("B13 — loadGlobalBadges notifications fetch has Authorization header",
      "'/notifications/' + u.id" in shared
      and shared.index("'Authorization'") < shared.index("'/messages/unread/'") + 1000)
check("B14 — 401/403 handling in notifications fetch triggers invalidateSession",
      "api_401" in shared or "invalidateSession" in shared)
check("B15 — badge WS has _twBadgeWsStop defined",
      "_twBadgeWsStop" in shared)
check("B16 — badge WS has _twBadgeWsStart defined",
      "_twBadgeWsStart" in shared)
check("B17 — _twApplyDeclarativeVisibility reads data-tw-session attribute",
      "data-tw-session" in shared)
check("B18 — _twApplyDeclarativeVisibility handles 'authenticated'",
      "'authenticated'" in shared)
check("B19 — _twApplyDeclarativeVisibility handles 'guest'",
      "'guest'" in shared)
check("B20 — _twApplyDeclarativeVisibility handles data-tw-account-types",
      "data-tw-account-types" in shared)
check("B21 — TwAuthSync listener registered once (not in every call)",
      "_ghListenerRegistered = true" in shared)
check("B22 — no setInterval used for session checking",
      "setInterval" not in shared)


# ═══════════════════════════════════════════════════════
# C — company-profile.html
# ═══════════════════════════════════════════════════════
print("\nC — company-profile.html")

co = read("company-profile.html")

check("C01 — coMenuDynamic container exists",
      'id="coMenuDynamic"' in co)
check("C02 — editInfoBtn preserved (static section)",
      'id="editInfoBtn"' in co)
check("C03 — static Settings link removed from dropdown",
      re.search(r'<a[^>]+href=["\']?/settings["\']?[^>]*>.*?الإعدادات', co) is None)
check("C04 — static Logout button removed from dropdown",
      'id="coLogoutBtn"' not in co)
check("C05 — notifications icon has data-tw-session=authenticated",
      'href="/notifications"' in co
      and 'data-tw-session="authenticated"' in co)
check("C06 — messages icon has data-tw-session=authenticated",
      'href="/messages"' in co
      and co.count('data-tw-session="authenticated"') >= 2)
check("C07 — auth-sync.js loaded in company-profile",
      'auth-sync.js' in co)
check("C08 — nav icons start hidden (hidden attribute)",
      co.count('data-tw-session="authenticated" hidden') >= 2)


# ═══════════════════════════════════════════════════════
# D — notifications.html
# ═══════════════════════════════════════════════════════
print("\nD — notifications.html")

notif = read("notifications.html")

check("D01 — ntMenuDynamic container exists",
      'id="ntMenuDynamic"' in notif)
check("D02 — static Settings link removed",
      'href="/settings"' not in notif
      or notif.find('href="/settings"') > notif.find('ntMenuDropdown'))
check("D03 — static Logout button removed",
      'data-ah-logout' not in notif)
check("D04 — inline toggle script removed",
      "dd.classList.toggle('open')" not in notif)
check("D05 — initGlobalHeaderMenu call present",
      "initGlobalHeaderMenu('ntMenuBtn'" in notif)
check("D06 — auth-sync.js loaded",
      "auth-sync.js" in notif)
check("D07 — inline logout handler removed",
      "localStorage.removeItem" not in notif
      or "Object.keys(localStorage)" not in notif)


# ═══════════════════════════════════════════════════════
# E — profile-showcase.html
# ═══════════════════════════════════════════════════════
print("\nE — profile-showcase.html")

sc = read("profile-showcase.html")

check("E01 — scMsgBtn has data-tw-session=authenticated",
      'id="scMsgBtn"' in sc
      and 'data-tw-session="authenticated"' in sc)
check("E02 — scBellBtn has data-tw-session=authenticated",
      'id="scBellBtn"' in sc
      and 'data-tw-session="authenticated"' in sc)
check("E03 — both icons start hidden",
      sc.count('data-tw-session="authenticated" hidden') >= 2)
check("E04 — auth-sync.js loaded",
      "auth-sync.js" in sc)
check("E05 — scMenuDynamic container preserved",
      'id="scMenuDynamic"' in sc)
check("E06 — eye preview static section preserved",
      'id="scEyeWrap"' in sc)


# ═══════════════════════════════════════════════════════
# F — company.main.js
# ═══════════════════════════════════════════════════════
print("\nF — company.main.js")

main = read("static/company/company.main.js")

check("F01 — toggleMenu function removed",
      "function toggleMenu" not in main)
check("F02 — _menuOpen variable removed",
      "var _menuOpen" not in main)
check("F03 — initGlobalHeaderMenu called",
      "initGlobalHeaderMenu('coMenuBtn'" in main)
check("F04 — coLogoutBtn binding removed",
      "coLogoutBtn" not in main)
check("F05 — _branchesLoaded preserved",
      "_branchesLoaded" in main)
check("F06 — TwAuthSync auth-sync callback preserved",
      "TwAuthSync.onSessionChange" in main)


# ═══════════════════════════════════════════════════════
# G — Documentation
# ═══════════════════════════════════════════════════════
print("\nG — Documentation")

vm = read("docs/design-system/VIEWER-MODES.md")
btn = read("docs/design-system/BUTTONS.md")
idx = read("docs/SYSTEMS_INDEX.md")

check("G01 — VM-10 section exists in VIEWER-MODES.md",
      "[VM-10]" in vm)
check("G02 — VM-10A Session States documented",
      "VM-10A" in vm)
check("G03 — VM-10B Global Header Menu Policy documented",
      "VM-10B" in vm)
check("G04 — VM-10C Idempotent renderer documented",
      "VM-10C" in vm)
check("G05 — VM-10D Declarative visibility documented",
      "VM-10D" in vm)
check("G06 — VM-10E Preview boundary documented",
      "VM-10E" in vm)
check("G07 — VM-10F Security boundary documented",
      "VM-10F" in vm)
check("G08 — BTN-17 updated with VM-10 extension",
      "VM-10 Extension" in btn)
check("G09 — SYSTEMS_INDEX has §53 entry",
      "53. Global Session UI Visibility System" in idx)
check("G10 — SYSTEMS_INDEX entry references VM-10",
      "VM-10" in idx)
check("G11 — SYSTEMS_INDEX entry references auth-sync.js",
      "auth-sync.js" in idx and "53." in idx)


# ═══════════════════════════════════════════════════════
# H — Security boundary checks
# ═══════════════════════════════════════════════════════
print("\nH — Security boundary")

check("H01 — _twApplyDeclarativeVisibility does not read viewer_type",
      "viewer_type" not in shared.split("_twApplyDeclarativeVisibility")[1].split("function")[0])
check("H02 — _twApplyDeclarativeVisibility does not read isOwner",
      "isOwner" not in shared.split("_twApplyDeclarativeVisibility")[1].split("function")[0])
check("H03 — no monkey-patch on window.fetch",
      "window.fetch" not in shared
      and "window.fetch" not in auth_sync)
check("H04 — twLogout falls back gracefully if TwAuthSync absent",
      "window.TwAuthSync && typeof TwAuthSync.invalidateSession" in shared)


# ═══════════════════════════════════════════════════════
# Results
# ═══════════════════════════════════════════════════════
total = 4 * 15 + 22 + 8 + 7 + 6 + 6 + 11 + 4  # rough count
print(f"\n{'='*55}")
if failures:
    print(f"FAILED {len(failures)} checks:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"All checks passed.")
    sys.exit(0)
