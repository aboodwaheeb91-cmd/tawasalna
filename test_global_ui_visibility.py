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
_tests_run = 0

def check(name, condition, detail=""):
    global _tests_run
    _tests_run += 1
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
check("A11 — invalidateSession uses explicit key allowlist (_SESSION_KEYS)",
      "_SESSION_KEYS" in auth_sync and "_SESSION_KEYS[i]" in auth_sync)
check("A12 — invalidateSession supports opts.redirect",
      "opts.redirect" in auth_sync)
check("A13 — onSessionChange backward compatible",
      "onSessionChange" in auth_sync)
check("A14 — pageshow force-fires on bfcache restore",
      "e.persisted" in auth_sync)
check("A15 — _expiryTimer cleared in invalidateSession",
      "_expiryTimer" in auth_sync and "clearTimeout(_expiryTimer)" in auth_sync)
check("A16 — missing exp → invalid (typeof check)",
      "typeof claims.exp !== 'number'" in auth_sync)
check("A17 — JWT user_id mismatch → stale",
      "user_id_mismatch" in auth_sync)
check("A18 — tw_user change detection (_prevUserStr fingerprint)",
      "_prevUserStr" in auth_sync)
check("A19 — expiry timer capped at MAX_TIMEOUT_MS (2^31-1)",
      "_MAX_TIMEOUT_MS" in auth_sync and "0x7FFFFFFF" in auth_sync)
check("A20 — session key allowlist defined (tw_jwt, tw_user)",
      "'tw_jwt'" in auth_sync and "'tw_user'" in auth_sync and "_SESSION_KEYS" in auth_sync)
check("A21 — exp <= now catches boundary (not strict <)",
      "claims.exp <= now" in auth_sync)
check("A22 — missing user_id claim → invalid (reason: missing_user_id)",
      "missing_user_id" in auth_sync)
check("A23 — missing user_type claim → invalid (reason: missing_user_type)",
      "missing_user_type" in auth_sync)
check("A24 — tw_user present without JWT → stale (reason: no_jwt_with_user)",
      "no_jwt_with_user" in auth_sync)
check("A25 — non-finite exp → invalid (isFinite check)",
      "isFinite(claims.exp)" in auth_sync)


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
check("B13 — loadGlobalBadges uses TwAuthSync.getSessionSnapshot()",
      "getSessionSnapshot" in shared and "loadGlobalBadges" in shared)
check("B14 — 401 invalidates session but 403 does NOT",
      "r.status === 401" in shared and "r.status === 401 || r.status === 403" not in shared)
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
check("B23 — candidates item in policy with accountTypes",
      "'candidates'" in shared and "accountTypes: ['co']" in shared)
check("B24 — accountTypes filter in _twMenuItemsForSnapshot",
      "item.accountTypes" in shared and "indexOf(utype)" in shared)
check("B25 — badge WS uses generation counter (_gen)",
      "_gen" in shared)
check("B26 — badge WS uses _activeUid for account-switch detection",
      "_activeUid" in shared)
check("B27 — _clearBadges includes data-ah-notif-badge selector",
      "data-ah-notif-badge" in shared)
check("B28 — loadGlobalBadges Authorization header uses userId from snapshot",
      "snap.userId" in shared or "userId" in shared)
check("B29 — twLogout fallback uses key allowlist (not Object.keys loop)",
      "_LOGOUT_KEYS" in shared and
      "Object.keys(localStorage)" not in shared.split("function twLogout")[1].split("function ")[0])
check("B30 — _badgeGeneration counter present (stale-response guard)",
      "_badgeGeneration" in shared)
check("B31 — loadGlobalBadges has no raw localStorage fallback (no tw_user parse inside)",
      # Old fallback parsed tw_user directly inside loadGlobalBadges
      "parse(localStorage.getItem('tw_user')" not in shared.split("function loadGlobalBadges")[1].split("function ")[0]
      and "getTwUser()" not in shared.split("function loadGlobalBadges")[1].split("function ")[0])
check("B32 — 401 on messages endpoint also handled",
      shared.count("r.status === 401") >= 2)
check("B33 — badges cleared at start of loadGlobalBadges (before fetch)",
      'style.display = \'none\'' in shared.split("function loadGlobalBadges")[1].split("fetch(")[0]
      or 'style.display="none"' in shared.split("function loadGlobalBadges")[1].split("fetch(")[0]
      or "el.style.display = 'none'" in shared.split("var gen = ")[0].split("loadGlobalBadges")[-1])
_lgb_body = shared.split("function loadGlobalBadges")[1].split("\n\nfunction ")[0] if "function loadGlobalBadges" in shared else ""
check("B34 — loadGlobalBadges writes to data-ah-notif-badge selector",
      'data-ah-notif-badge' in _lgb_body)
check("B35 — loadGlobalBadges has userId capture guard (capturedUserId)",
      'capturedUserId' in _lgb_body or '_guardOk' in _lgb_body)
check("B36 — _bindBadgeAuthSync defined in tw_shared.js",
      "_bindBadgeAuthSync" in shared)
check("B37 — _bindBadgeAuthSync is idempotent (_badgeAuthSyncBound guard)",
      "_badgeAuthSyncBound" in shared)
check("B38 — register menu item href is /login#register",
      "'/login#register'" in shared or '"/login#register"' in shared)
check("B39 — _on401 bumps _badgeGeneration (cancel sibling fetch on 401)",
      "_on401" in shared and "_badgeGeneration++" in _lgb_body)
check("B40 — window.load retries _bindBadgeAuthSync",
      # The LAST window.load listener (inside the Badge WS IIFE) must call _bindBadgeAuthSync.
      # Use [-1]: split gives N+1 parts; [-1] is the content AFTER the last occurrence.
      len(shared.split("window.addEventListener('load'")) > 1
      and "_bindBadgeAuthSync" in shared.split("window.addEventListener('load'")[-1])


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
# J — messages.html (VM-10 adoption)
# ═══════════════════════════════════════════════════════
print("\nJ — messages.html")

msg = read("messages.html")
msg_render = read("messages.render.js")

check("J01 — auth-sync.js loaded in messages.html",
      "auth-sync.js" in msg)
check("J02 — auth-sync.js loads before messages.render.js",
      "auth-sync.js" in msg
      and msg.index("auth-sync.js") < msg.index("messages.render.js"))
check("J03 — notifications button has data-tw-session=authenticated",
      'onclick="location.href=\'/notifications\'"' in msg
      and 'data-tw-session="authenticated"' in msg)
check("J04 — profile button has data-tw-session=authenticated",
      'onclick="goMessengerProfile()"' in msg
      and msg.count('data-tw-session="authenticated"') >= 2)
check("J05 — both nav icons start hidden (hidden attribute)",
      msg.count('data-tw-session="authenticated" hidden') >= 2)
check("J06 — initGlobalHeaderMenu wired in messages.render.js",
      "initGlobalHeaderMenu('scMenuBtn'" in msg_render)


# ═══════════════════════════════════════════════════════
# K — home-v2.html (VM-10 adoption)
# ═══════════════════════════════════════════════════════
print("\nK — home-v2.html")

hv2       = read("home-v2.html")
hv2_hdr   = read("static/home/home.header.js")

check("K01 — tw_shared.js loaded in home-v2.html",
      "/tw_shared.js" in hv2)
check("K02 — auth-sync.js loaded in home-v2.html",
      "auth-sync.js" in hv2)
check("K03 — auth-sync.js loads before home.header.js",
      "auth-sync.js" in hv2
      and hv2.index("auth-sync.js") < hv2.index("home.header.js"))
check("K04 — notifications link has data-tw-session=authenticated",
      'href="/notifications"' in hv2
      and 'data-tw-session="authenticated"' in hv2)
check("K05 — messages link has data-tw-session=authenticated",
      'href="/messages"' in hv2
      and hv2.count('data-tw-session="authenticated"') >= 2)
check("K06 — both nav icons start hidden (hidden attribute)",
      hv2.count('data-tw-session="authenticated" hidden') >= 2)
check("K07 — static Settings link removed from dropdown",
      re.search(r'<a[^>]+href=["\']?/settings["\']?[^>]*>.*?الإعدادات', hv2) is None)
check("K08 — static hwLogoutBtn removed from dropdown",
      'id="hwLogoutBtn"' not in hv2)
check("K09 — home.header.js has no startsWith logout violation",
      "startsWith('tw_')" not in hv2_hdr
      and 'startsWith("tw_")' not in hv2_hdr)
check("K10 — home.header.js calls initGlobalHeaderMenu",
      "initGlobalHeaderMenu('hwMenuBtn'" in hv2_hdr)
check("K11 — home.header.js has no local menu toggle",
      "menuDrop.classList.toggle" not in hv2_hdr
      and "classList.toggle('open')" not in hv2_hdr)


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
check("H05 — 401 and 403 are NOT treated identically in badge loader",
      "r.status === 401" in shared and "r.status === 401 || r.status === 403" not in shared)


# ═══════════════════════════════════════════════════════
# I — Repository-wide static guards
# ═══════════════════════════════════════════════════════
print("\nI — Repository-wide static guards")

import glob as _glob

html_files = _glob.glob("*.html") + _glob.glob("**/*.html", recursive=True)
js_files   = _glob.glob("static/**/*.js", recursive=True)

# Allowed files that may still contain the old logout pattern (legacy pages not yet migrated)
_LEGACY_ALLOWED = set()  # all pages with session actions now adopted

old_logout_violators = []
for f in html_files:
    bn = f.split("/")[-1]
    if bn in _LEGACY_ALLOWED:
        continue
    try:
        content = read(f)
    except Exception:
        continue
    if "localStorage.removeItem" in content and "Object.keys(localStorage)" in content:
        old_logout_violators.append(f)

# I01: Pages that explicitly adopted VM-10 (load auth-sync.js) must not also
# have old inline multi-step logout. Legacy pages not yet migrated are excluded.
# Auto-detect VM-10 pages: any HTML page that has a .sc-menu-dropdown element.
_VM10_PAGES = set()
for _f in html_files:
    _bn = _f.split("/")[-1]
    if _bn in _LEGACY_ALLOWED:
        continue
    try:
        _c = read(_f)
        if 'sc-menu-dropdown' in _c:
            _VM10_PAGES.add(_bn)
    except Exception:
        pass

old_logout_violators_vm10 = []
for f in html_files:
    bn = f.split("/")[-1]
    if bn not in _VM10_PAGES:
        continue
    try:
        content = read(f)
    except Exception:
        continue
    if "localStorage.removeItem" in content and "Object.keys(localStorage)" in content:
        old_logout_violators_vm10.append(f)
check("I01 — VM-10 pages have no old inline multi-step logout",
      len(old_logout_violators_vm10) == 0,
      "violators: " + str(old_logout_violators_vm10) if old_logout_violators_vm10 else "")

# I02: auth-sync.js invalidateSession must use _SESSION_KEYS allowlist, not startsWith
# (Check only the VM-10 system files — legacy pages' twLogout fallback is allowed)
check("I02 — auth-sync.js invalidateSession uses _SESSION_KEYS (not startsWith loop)",
      "_SESSION_KEYS[i]" in auth_sync)

# I03: HTML pages that directly call initGlobalHeaderMenu must load auth-sync.js first
pages_with_menu = []
for f in html_files:
    bn = f.split("/")[-1]
    if bn not in _VM10_PAGES:
        continue
    try:
        content = read(f)
    except Exception:
        continue
    if "initGlobalHeaderMenu" in content:
        pages_with_menu.append((f, content))

def _menu_call_pos(content):
    # Match actual call with string argument e.g. initGlobalHeaderMenu('btnId',...)
    # This skips HTML comment mentions like <!-- rendered by initGlobalHeaderMenu() -->
    import re
    m = re.search(r"initGlobalHeaderMenu\s*\(\s*['\"]", content)
    return m.start() if m else -1

# Only check pages that actually have a direct call with arguments
pages_with_direct_call = [(f, c) for f, c in pages_with_menu if _menu_call_pos(c) >= 0]
menu_order_ok = all(
    "auth-sync.js" in content
    and content.index("auth-sync.js") < _menu_call_pos(content)
    for f, content in pages_with_direct_call
)
check("I03 — auth-sync.js loads before direct initGlobalHeaderMenu call on VM-10 pages",
      menu_order_ok)

# I04: All pages that contain .sc-menu-dropdown (auto-detected VM-10 pages) must load auth-sync.js
_sc_dropdown_missing_sync = []
for f in html_files:
    bn = f.split("/")[-1]
    if bn in _LEGACY_ALLOWED:
        continue
    try:
        content = read(f)
    except Exception:
        continue
    if 'sc-menu-dropdown' in content and 'auth-sync.js' not in content:
        _sc_dropdown_missing_sync.append(f)
check("I04 — all pages with .sc-menu-dropdown load auth-sync.js (auto-detected)",
      len(_sc_dropdown_missing_sync) == 0,
      "missing auth-sync.js: " + str(_sc_dropdown_missing_sync) if _sc_dropdown_missing_sync else "")


# ═══════════════════════════════════════════════════════
# M — Repository-wide runtime-code guards
# ═══════════════════════════════════════════════════════
print("\nM — Repository-wide runtime-code guards")

index_auth = read("index.auth.js")
app_header = read("static/app-header.js")

def _code_lines(src):
    """Strip pure comment lines (lines whose first non-space chars are //)."""
    return '\n'.join(
        line for line in src.splitlines()
        if not re.match(r'^\s*//', line)
    )

_index_auth_code = _code_lines(index_auth)
_app_header_code = _code_lines(app_header)

# M01: index.auth.js must not scan localStorage with startsWith('tw_') in actual code
# (comments that warn against this pattern are allowed)
check("M01 — index.auth.js has no startsWith('tw_') in code (not comments)",
      "startsWith('tw_')" not in _index_auth_code
      and 'startsWith("tw_")' not in _index_auth_code)

# M02: app-header.js must not scan localStorage with startsWith('tw_') in actual code
check("M02 — app-header.js has no startsWith('tw_') in code (not comments)",
      "startsWith('tw_')" not in _app_header_code
      and 'startsWith("tw_")' not in _app_header_code)

# M03: company.main.js no dangling window.toggleMenu export (uses main read in F section)
check("M03 — company.main.js no dangling window.toggleMenu export",
      "window.toggleMenu = toggleMenu" not in main)

# M04: app-header.js fail-closed removes session keys before redirect
check("M04 — app-header.js fail-closed removes tw_jwt before redirect",
      "removeItem('tw_jwt')" in app_header or 'removeItem("tw_jwt")' in app_header)

# M04b: redirect is ordered AFTER the key removals
_ah_fallback   = app_header.split("Last-resort fallback")[1] if "Last-resort fallback" in app_header else app_header
_ah_remove_idx  = _ah_fallback.find("removeItem('tw_jwt')")
_ah_redirect_idx = _ah_fallback.find("location.replace('/login')")
check("M04b — app-header.js redirect follows key removal (code order)",
      _ah_remove_idx != -1 and _ah_redirect_idx != -1 and _ah_remove_idx < _ah_redirect_idx)

# M05: loadGlobalBadges writes to data-ah-notif-badge in the notif UPDATE path
# (B34 checks presence in the body; M05 checks it's specifically in the write path after fetch)
_lgb_after_notif_fetch = ""
if "function loadGlobalBadges" in shared:
    _lgb_full = shared.split("function loadGlobalBadges")[1].split("\n\nfunction ")[0]
    # The write path is after the first fetch call
    _lgb_after_notif_fetch = _lgb_full.split(".then(function(d)")[1] if ".then(function(d)" in _lgb_full else ""
check("M05 — loadGlobalBadges writes data-ah-notif-badge in notif update path (not just clear)",
      'data-ah-notif-badge' in _lgb_after_notif_fetch)

# M06: No setInterval badge/unread polling in any root or key shared JS files
_badge_poll_files = [
    "tw_shared.js", "index.auth.js", "index.ui.js",
    "static/app-header.js", "static/home/home.header.js",
]
_setinterval_badge_violators = []
for _bpf in _badge_poll_files:
    try:
        _bpf_content = read(_bpf)
        if re.search(r"setInterval\s*\([^)]*(?:badge|unread|notif|msgs)", _bpf_content, re.IGNORECASE):
            _setinterval_badge_violators.append(_bpf)
    except Exception:
        pass
check("M06 — no setInterval badge/unread polling in root or shared JS files",
      len(_setinterval_badge_violators) == 0,
      "violators: " + str(_setinterval_badge_violators) if _setinterval_badge_violators else "")


# ═══════════════════════════════════════════════════════
# L — edu-profile.html (VM-10 adoption)
# ═══════════════════════════════════════════════════════
print("\nL — edu-profile.html")

ep = read("edu-profile.html")

check("L01 — tw_shared.js loaded in edu-profile.html",
      "/tw_shared.js" in ep)
check("L02 — auth-sync.js loaded in edu-profile.html",
      "auth-sync.js" in ep)
check("L03 — auth-sync.js loads before initGlobalHeaderMenu call",
      "auth-sync.js" in ep
      and ep.index("auth-sync.js") < ep.index("initGlobalHeaderMenu"))
check("L04 — app-header.css loaded",
      "app-header.css" in ep)
check("L05 — sc-menu-dropdown element present",
      'sc-menu-dropdown' in ep)
check("L06 — initGlobalHeaderMenu wired to epMenuBtn",
      "initGlobalHeaderMenu('epMenuBtn'" in ep)
check("L07 — static doLogout() function removed",
      "function doLogout" not in ep)
check("L08 — static toggleMenu() function removed",
      "function toggleMenu" not in ep)
check("L09 — _menuOpen variable removed",
      "_menuOpen" not in ep)
check("L10 — static #dropMenu div removed",
      'id="dropMenu"' not in ep)
check("L11 — static logout button removed from nav",
      'onclick="doLogout()"' not in ep)
check("L12 — notifications link has data-tw-session=authenticated",
      'href="/notifications"' in ep
      and 'data-tw-session="authenticated"' in ep)
check("L13 — messages link has data-tw-session=authenticated",
      'href="/messages"' in ep
      and ep.count('data-tw-session="authenticated"') >= 1)
check("L14 — both session nav icons start hidden",
      ep.count('data-tw-session="authenticated" hidden') >= 2)
check("L15 — owner actions still present (VM-01 separation)",
      'id="ownerActions"' in ep
      and 'onclick="openEditModal()"' in ep)


# ═══════════════════════════════════════════════════════
# Results
# ═══════════════════════════════════════════════════════
print(f"\n{'='*55}")
print(f"Checks run: {_tests_run}  |  Passed: {_tests_run - len(failures)}  |  Failed: {len(failures)}")
if failures:
    print(f"\nFAILED {len(failures)} checks:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"All checks passed.")
    sys.exit(0)
