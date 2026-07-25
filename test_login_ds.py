"""
test_login_ds.py — Login Form DS-INP / DS-VAL / DS-BTN runtime tests
Scenarios A–T (20 total). Requires server at http://127.0.0.1:8000.
Run: python test_login_ds.py

Fetch mock strategy: queue-based mock injected via page.evaluate().
  window.__lrc  = request count
  window.__lmq  = mock queue [{status, body, delay}]
  _q(page, status, body, delay) — enqueue one response
  _cnt(page) — return request count so far
"""
import json, os, sys, time, traceback

BASE     = 'http://127.0.0.1:8000'
CHROMIUM = os.environ.get('PLAYWRIGHT_CHROMIUM_PATH', None)

PASS_STR  = '\033[92mPASS\033[0m'
FAIL_STR  = '\033[91mFAIL\033[0m'
SKIP_STR  = '\033[93mSKIP\033[0m'

results = []

def run(label, fn, page):
    try:
        fn(page)
        print(f'  {PASS_STR}  {label}')
        results.append((label, 'pass', None))
    except Exception as exc:
        tb = traceback.format_exc()
        print(f'  {FAIL_STR}  {label}: {exc}')
        results.append((label, 'fail', str(exc)))

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh(page):
    """Navigate to login and inject queue-based fetch mock + redirect override.

    add_init_script (registered once on the page before any navigation) clears
    localStorage before index.auth.js runs, preventing the on-load IIFE from
    triggering a real redirect when a previous test's success path wrote tw_user.
    We wait for #lEmail (not networkidle — tw_shared.js opens a WebSocket that
    keeps the network busy and causes networkidle to hang).
    """
    page.goto(BASE + '/login')
    page.wait_for_selector('#lEmail', timeout=10000)
    # Override redirect + inject fetch mock AFTER page scripts have run
    # (function declarations in index.auth.js overwrite window.redirect on load;
    # we re-override here so success-path calls hit our stub, not location.href)
    page.evaluate("""() => {
        window.redirect = function(u) { window.__mockRedirectUser = u; };
        window.__lrc = 0;
        window.__lmq = [];
        window.__mockRedirectUser = undefined;
        const _origFetch = window.fetch.bind(window);
        window.fetch = async function(url, opts) {
            if(typeof url === 'string' && url.includes('/auth/login')) {
                window.__lrc++;
                const m = window.__lmq.shift() || {status: 503, body: {}};
                if(m.delay) await new Promise(r => setTimeout(r, m.delay));
                const body = JSON.stringify(m.body || {});
                return {
                    ok: m.status >= 200 && m.status < 300,
                    status: m.status,
                    json: async () => JSON.parse(body),
                    text: async () => body
                };
            }
            return _origFetch.apply(this, arguments);
        };
    }""")

def _q(page, status, body=None, delay=0):
    """Enqueue one mock response."""
    if body is None:
        body = {}
    page.evaluate(f'window.__lmq.push({{status:{status},body:{json.dumps(body)},delay:{delay}}})')

def _cnt(page):
    """Return number of /auth/login requests made so far."""
    return page.evaluate('window.__lrc || 0')

def _fill(page, email='', password=''):
    if email:
        page.fill('#lEmail', email)
    if password:
        page.fill('#lPass', password)

_GOOD_RESP = {
    'user': {'id': 1, 'tw_id': 'U962abc', 'full_name': 'أحمد', 'user_type': 'emp'},
    'token': 'tok_test_valid_string'
}

# ── A: Empty submit — both errors shown, focus on email, 0 requests ───────────
def test_a_empty_submit_both_errors(page):
    _fresh(page)
    page.click('#loginBtn')
    email_err = page.locator('#l-email-error')
    pass_err  = page.locator('#l-pass-error')
    assert email_err.is_visible(), 'email error must be visible'
    assert pass_err.is_visible(),  'pass error must be visible'
    assert 'مطلوب' in (email_err.text_content() or ''), 'email error must say مطلوب'
    assert 'مطلوب' in (pass_err.text_content() or ''),  'pass error must say مطلوب'
    focused = page.evaluate('document.activeElement.id')
    assert focused == 'lEmail', f'focus must be on lEmail, got: {focused}'
    assert _cnt(page) == 0, f'0 requests expected on validation failure, got {_cnt(page)}'

# ── B: Before-submit: Required stays passive (no blur Required) ────────────────
def test_b_required_passive_before_submit(page):
    _fresh(page)
    # Type something then clear — no submit yet
    page.fill('#lEmail', 'a')
    page.fill('#lEmail', '')
    page.wait_for_timeout(100)
    err = page.locator('#l-email-error')
    assert not err.is_visible(), 'Required must NOT show before submit when user clears field'

# ── C: Required→Format→Required cycle after submit ────────────────────────────
def test_c_required_format_required_cycle(page):
    _fresh(page)
    # First submit → Required error
    page.click('#loginBtn')
    email_err = page.locator('#l-email-error')
    assert email_err.is_visible(), 'Required must show after submit'
    assert 'مطلوب' in (email_err.text_content() or ''), 'must say مطلوب'
    # Type partial invalid → Format error
    page.fill('#lEmail', 'bad@')
    page.wait_for_timeout(100)
    assert email_err.is_visible(), 'Format error must show on non-empty invalid'
    assert 'صيغة' in (email_err.text_content() or ''), 'must say صيغة'
    # Clear back to empty → Required must return (submit was attempted)
    page.fill('#lEmail', '')
    page.wait_for_timeout(100)
    assert email_err.is_visible(), 'Required must re-show after clearing back to empty post-submit'
    assert 'مطلوب' in (email_err.text_content() or ''), 'must say مطلوب after clearing'

# ── D: Before-submit: blur Format error clears when field goes empty ───────────
def test_d_blur_format_clears_on_empty_before_submit(page):
    _fresh(page)
    # Enter invalid, blur to trigger Format
    page.fill('#lEmail', 'bad@')
    page.locator('#lEmail').blur()
    page.wait_for_timeout(150)
    err = page.locator('#l-email-error')
    assert err.is_visible(), 'Format error must show on blur with invalid email'
    # Now clear — before submit, so Required must NOT appear
    page.fill('#lEmail', '')
    page.wait_for_timeout(100)
    assert not err.is_visible(), 'Format error must clear when field emptied before first submit'

# ── E: Password Required re-shows after submit + clear ────────────────────────
def test_e_pass_required_cycle(page):
    _fresh(page)
    page.click('#loginBtn')
    pass_err = page.locator('#l-pass-error')
    assert pass_err.is_visible(), 'Required must show after submit'
    # Type a character — Required clears
    page.fill('#lPass', 'x')
    page.wait_for_timeout(100)
    assert not pass_err.is_visible(), 'Required must clear when password is non-empty'
    # Clear back — Required must return
    page.fill('#lPass', '')
    page.wait_for_timeout(100)
    assert pass_err.is_visible(), 'Required must re-show when password cleared after submit'
    assert 'مطلوب' in (pass_err.text_content() or ''), 'must say مطلوب'

# ── F: Enter in email field → focuses password, 0 requests ───────────────────
def test_f_enter_email_focuses_password(page):
    _fresh(page)
    page.fill('#lEmail', 'user@example.com')
    page.locator('#lEmail').press('Enter')
    page.wait_for_timeout(100)
    focused = page.evaluate('document.activeElement.id')
    assert focused == 'lPass', f'focus must be on lPass, got: {focused}'
    assert _cnt(page) == 0, f'Enter in email must not fire request, got {_cnt(page)}'

# ── G: Enter in password field fires doLogin() ────────────────────────────────
def test_g_enter_password_fires_login(page):
    _fresh(page)
    _q(page, 401, {'detail': 'wrong'})
    page.fill('#lEmail', 'user@example.com')
    page.fill('#lPass', 'wrongpass')
    page.locator('#lPass').press('Enter')
    page.wait_for_timeout(300)
    assert _cnt(page) == 1, f'Enter in password must fire exactly 1 request, got {_cnt(page)}'

# ── H: Double-click guard — _submitting blocks concurrent doLogin() calls ─────
def test_h_double_submit_guard(page):
    _fresh(page)
    _q(page, 401, {'detail': 'wrong'}, delay=400)
    _fill(page, email='a@b.com', password='pass123')
    page.click('#loginBtn')
    page.wait_for_timeout(30)  # let first handler run synchronously (_submitting=true)
    # Call doLogin() directly (bypasses disabled button, tests JS guard itself)
    page.evaluate('doLogin()')
    page.wait_for_timeout(600)
    assert _cnt(page) == 1, f'double-click guard: expected 1 request, got {_cnt(page)}'

# ── I: In-flight: click + Enter in password both guarded ─────────────────────
def test_i_inflight_enter_also_guarded(page):
    _fresh(page)
    _q(page, 401, {'detail': 'wrong'}, delay=400)
    _fill(page, email='a@b.com', password='pass123')
    page.click('#loginBtn')
    page.locator('#lPass').press('Enter')
    page.wait_for_timeout(600)
    assert _cnt(page) == 1, f'Enter during in-flight must be guarded: expected 1, got {_cnt(page)}'

# ── J: Success gap — button locked, _submitting stays true, no second request ─
def test_j_success_gap_button_locked(page):
    _fresh(page)
    _q(page, 200, _GOOD_RESP, delay=100)
    _fill(page, email='valid@example.com', password='pass123')
    page.click('#loginBtn')
    page.wait_for_timeout(50)  # during the in-flight delay
    btn = page.locator('#loginBtn')
    assert btn.get_attribute('disabled') is not None, 'button must be disabled during in-flight'
    page.wait_for_timeout(200)
    # After success _submitting stays true (redirect pending) — check JS state
    submitting = page.evaluate('typeof _submitting !== "undefined" ? _submitting : null')
    assert submitting is True, f'_submitting must remain true after success, got: {submitting}'
    # Direct doLogin() call must be guarded by _submitting
    page.evaluate('doLogin()')
    page.wait_for_timeout(100)
    assert _cnt(page) == 1, f'after success, lock must hold: expected 1 request, got {_cnt(page)}'

# ── K: 401 → safe banner, not raw data.detail ────────────────────────────────
def test_k_401_shows_safe_banner(page):
    _fresh(page)
    _q(page, 401, {'detail': 'INTERNAL SERVER USER NOT FOUND'})
    _fill(page, email='wrong@example.com', password='wrongpass')
    page.click('#loginBtn')
    page.wait_for_timeout(300)
    banner = page.locator('#l-form-error')
    assert banner.is_visible(), 'auth failure must show form banner'
    txt = page.locator('.l-form-error-text').text_content() or ''
    assert 'INTERNAL' not in txt, f'raw error detail must NOT appear in banner: {txt}'
    assert 'بيانات' in txt, f'expected safe message with بيانات, got: {txt}'

# ── L: 429 → rate-limit message ──────────────────────────────────────────────
def test_l_429_rate_limit_message(page):
    _fresh(page)
    _q(page, 429, {})
    _fill(page, email='a@b.com', password='pass')
    page.click('#loginBtn')
    page.wait_for_timeout(300)
    txt = page.locator('.l-form-error-text').text_content() or ''
    assert 'محاولات' in txt, f'429 must show rate-limit message, got: {txt}'

# ── M: 500 non-JSON body → server error message (not network error) ───────────
def test_m_500_non_json_safe_message(page):
    """Non-JSON 502/500: res.json() throws → data=null → server error branch."""
    _fresh(page)
    # Inject a mock that returns non-parseable body for a 500
    page.evaluate("""() => {
        const _origFetch = window.fetch.bind(window);
        window.fetch = async function(url, opts) {
            if(typeof url === 'string' && url.includes('/auth/login')) {
                window.__lrc = (window.__lrc || 0) + 1;
                return {
                    ok: false,
                    status: 502,
                    json: async () => { throw new SyntaxError('not json'); },
                    text: async () => '<html>Bad Gateway</html>'
                };
            }
            return _origFetch.apply(this, arguments);
        };
    }""")
    _fill(page, email='a@b.com', password='pass')
    page.click('#loginBtn')
    page.wait_for_timeout(300)
    banner = page.locator('#l-form-error')
    assert banner.is_visible(), '500 non-JSON must show error banner'
    txt = page.locator('.l-form-error-text').text_content() or ''
    assert 'تعذّر' in txt or 'خادم' in txt, f'must show server error message, got: {txt}'
    # Button must be restored (not stuck in loading)
    btn = page.locator('#loginBtn')
    assert btn.get_attribute('disabled') is None, 'button must be restored after server error'

# ── N: Network abort → network error message, button restored ─────────────────
def test_n_network_abort_message(page):
    _fresh(page)
    # Mock fetch to throw a network error
    page.evaluate("""() => {
        window.fetch = async function(url, opts) {
            if(typeof url === 'string' && url.includes('/auth/login')) {
                window.__lrc = (window.__lrc || 0) + 1;
                throw new TypeError('Failed to fetch');
            }
        };
    }""")
    _fill(page, email='a@b.com', password='pass')
    page.click('#loginBtn')
    page.wait_for_timeout(300)
    banner = page.locator('#l-form-error')
    assert banner.is_visible(), 'network error must show form banner'
    txt = page.locator('.l-form-error-text').text_content() or ''
    assert 'اتصال' in txt or 'خادم' in txt, f'must show network error message, got: {txt}'
    btn = page.locator('#loginBtn')
    assert btn.get_attribute('disabled') is None, 'button must be restored after network error'

# ── O: Invalid 2xx structure → no redirect, safe error, button restored ───────
def test_o_invalid_2xx_no_redirect(page):
    _fresh(page)
    # 200 but missing required fields
    _q(page, 200, {'user': None, 'token': None})
    _fill(page, email='a@b.com', password='pass123')
    page.click('#loginBtn')
    page.wait_for_timeout(400)
    redirected = page.evaluate('window.__mockRedirectUser')
    assert not redirected, f'invalid 2xx must NOT redirect, got: {redirected}'
    banner = page.locator('#l-form-error')
    assert banner.is_visible(), 'invalid 2xx must show error banner'
    txt = page.locator('.l-form-error-text').text_content() or ''
    assert len(txt) > 0, 'banner must have error text'
    btn = page.locator('#loginBtn')
    assert btn.get_attribute('disabled') is None, 'button must be restored on invalid 2xx'

# ── P: Partial storage failure → rollback both keys, safe error ───────────────
def test_p_storage_failure_rollback(page):
    _fresh(page)
    _q(page, 200, _GOOD_RESP)
    # Override localStorage.setItem to throw on tw_user write
    page.evaluate("""() => {
        const _origSet = localStorage.setItem.bind(localStorage);
        localStorage.setItem = function(k, v) {
            if(k === 'tw_user') throw new DOMException('QuotaExceededError');
            return _origSet(k, v);
        };
    }""")
    _fill(page, email='a@b.com', password='pass123')
    page.click('#loginBtn')
    page.wait_for_timeout(400)
    redirected = page.evaluate('window.__mockRedirectUser')
    assert not redirected, 'storage failure must NOT redirect'
    # tw_user must not be present (rollback)
    tw_user = page.evaluate("localStorage.getItem('tw_user')")
    assert tw_user is None, f'tw_user must be rolled back on storage error, got: {tw_user}'
    tw_jwt  = page.evaluate("localStorage.getItem('tw_jwt')")
    assert tw_jwt  is None, f'tw_jwt must be rolled back on storage error, got: {tw_jwt}'
    banner = page.locator('#l-form-error')
    assert banner.is_visible(), 'storage error must show banner'
    btn = page.locator('#loginBtn')
    assert btn.get_attribute('disabled') is None, 'button must be restored on storage failure'

# ── Q: Eye toggle — type, icons, aria-pressed, no request ─────────────────────
def test_q_eye_toggle_full(page):
    _fresh(page)
    btn     = page.locator('#lPassEye')
    passEl  = page.locator('#lPass')
    eyeShow = page.locator('#lEyeShow')
    eyeHide = page.locator('#lEyeHide')
    # Initial state
    assert passEl.get_attribute('type') == 'password', 'initial type must be password'
    assert btn.get_attribute('aria-pressed') == 'false', 'initial aria-pressed must be false'
    assert eyeShow.is_visible(), 'lEyeShow must be visible initially'
    assert not eyeHide.is_visible(), 'lEyeHide must be hidden initially'
    # After one click
    btn.click()
    assert passEl.get_attribute('type') == 'text', 'after click: type must be text'
    assert btn.get_attribute('aria-pressed') == 'true', 'after click: aria-pressed must be true'
    assert not eyeShow.is_visible(), 'lEyeShow must hide after click'
    assert eyeHide.is_visible(), 'lEyeHide must show after click'
    # After second click — back to initial
    btn.click()
    assert passEl.get_attribute('type') == 'password', 'second click: back to password'
    assert btn.get_attribute('aria-pressed') == 'false', 'second click: aria-pressed back to false'
    assert eyeShow.is_visible(), 'lEyeShow must show again'
    assert not eyeHide.is_visible(), 'lEyeHide must hide again'
    assert _cnt(page) == 0, 'eye toggle must not fire any login requests'

# ── R: Login outlined, Register gradient — confirmed by computed style ────────
def test_r_button_styles(page):
    _fresh(page)
    # Login button: #loginSection .cta overrides to background:transparent + green border
    login_bg_img = page.evaluate(
        "getComputedStyle(document.getElementById('loginBtn')).backgroundImage"
    )
    assert login_bg_img == 'none', \
        f'#loginBtn must have no background-image (outlined), got: {login_bg_img}'
    login_border = page.evaluate(
        "getComputedStyle(document.getElementById('loginBtn')).borderColor"
    )
    # var(--ac) = #00c896 = rgb(0,200,150)
    assert '0, 200, 150' in login_border or 'rgb(0, 200, 150)' in login_border, \
        f'#loginBtn must have green (#00c896) outlined border, got: {login_border}'

    # Register button: .cta base = linear-gradient — must NOT be overridden to transparent
    # Show register section first to make #regBtn accessible
    page.evaluate('showRegister()')
    page.wait_for_timeout(50)
    reg_bg_img = page.evaluate(
        "getComputedStyle(document.getElementById('regBtn')).backgroundImage"
    )
    assert 'linear-gradient' in reg_bg_img, \
        f'#regBtn must retain gradient background (Login scope must not leak), got: {reg_bg_img}'
    reg_border_w = page.evaluate(
        "getComputedStyle(document.getElementById('regBtn')).borderWidth"
    )
    assert reg_border_w == '0px', \
        f'#regBtn must have no border (border:none from .cta base), got: {reg_border_w}'

# ── S: Mobile 375px — no overflow, 44px eye touch target, errors visible ──────
def test_s_mobile_375px(page):
    page.set_viewport_size({'width': 375, 'height': 812})
    _fresh(page)
    # No horizontal overflow
    overflow = page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )
    assert not overflow, f'horizontal overflow detected at 375px: scrollWidth > clientWidth'
    # Eye button minimum touch target (44×44)
    btn_box = page.locator('#lPassEye').bounding_box()
    assert btn_box is not None, 'eye button must be visible at 375px'
    assert btn_box['width'] >= 44, f'eye button width must be ≥44px, got {btn_box["width"]}'
    assert btn_box['height'] >= 44, f'eye button height must be ≥44px, got {btn_box["height"]}'
    # Field errors visible after submit
    page.click('#loginBtn')
    assert page.locator('#l-email-error').is_visible(), 'email error must be visible at 375px'
    assert page.locator('#l-pass-error').is_visible(),  'pass error must be visible at 375px'
    # Reset viewport
    page.set_viewport_size({'width': 1280, 'height': 800})

# ── U: Autofill simulation — stale errors cleared inside Submit, no input events ─
def test_u_autofill_clears_stale_errors(page):
    _fresh(page)
    # Step 1: submit empty → both Required errors appear
    page.click('#loginBtn')
    assert page.locator('#l-email-error').is_visible(), 'email error must appear on empty submit'
    assert page.locator('#l-pass-error').is_visible(),  'pass error must appear on empty submit'
    # Step 2: simulate autofill — set values via JS WITHOUT dispatching any input event
    page.evaluate("""() => {
        document.getElementById('lEmail').value = 'valid@example.com';
        document.getElementById('lPass').value = 'password123';
        // Intentionally no dispatchEvent — mimics browser autofill behaviour
    }""")
    # Step 3: queue a 401 (fields are valid so doLogin() proceeds to fetch)
    _q(page, 401, {'detail': 'wrong password'})
    # Step 4: click Login again
    page.click('#loginBtn')
    page.wait_for_timeout(400)
    # Both field errors must be gone (cleared by doLogin() submit-time cleanup)
    assert not page.locator('#l-email-error').is_visible(), \
        'email error must be cleared by submit-time cleanup when field is valid'
    assert not page.locator('#l-pass-error').is_visible(), \
        'pass error must be cleared by submit-time cleanup when field is non-empty'
    # Auth failure banner must show (401 → safe message)
    assert page.locator('#l-form-error').is_visible(), \
        'form error banner must appear on 401'
    assert _cnt(page) == 1, f'must fire exactly 1 login request, got {_cnt(page)}'

# ── V: Autofill CSS selectors scoped to #loginSection (source check) ────────────
def test_v_autofill_selectors_scoped(page):
    with open('/home/user/tawasalna/index.css', 'r', encoding='utf-8') as f:
        css = f.read()
    # Must contain the scoped selector
    assert '#loginSection input:-webkit-autofill' in css, \
        'index.css must contain #loginSection input:-webkit-autofill'
    # Must NOT contain a bare (global) autofill selector
    css_without_scoped = css.replace('#loginSection input:-webkit-autofill', '')
    assert 'input:-webkit-autofill' not in css_without_scoped, \
        'input:-webkit-autofill must appear only under #loginSection scope'
    # [hidden] rule must be scoped to #loginSection, not global
    assert '#loginSection [hidden]' in css, \
        'index.css must contain #loginSection [hidden] (scoped)'
    css_without_scoped_hidden = css.replace('#loginSection [hidden]', '')
    # Bare [hidden] (no #loginSection prefix) must not remain
    import re
    bare_hidden = re.search(r'(?<!\S)\[hidden\]\s*\{', css_without_scoped_hidden)
    assert not bare_hidden, \
        f'[hidden] rule must be scoped to #loginSection, not global; found: {bare_hidden}'

# ── T: No JS syntax/runtime errors on load (network 404s from test server excluded)
def test_t_no_console_errors(page):
    errors = []
    # Infrastructure errors expected when running against the minimal test server:
    # - bg fetch requests from tw_shared.js (notifications, messages, admin/logo)
    # - service-worker / manifest script fetch 404s
    # - WebSocket connect failures
    # These are infrastructure gaps, not JS bugs in the code under test.
    _IGNORE = ['/notifications/', '/messages/', '/admin/logo', '/log/error',
               'net::ERR_', 'Failed to load resource', 'Failed to fetch',
               'bad HTTP response', 'fetching the script',
               'WebSocket', '/ws/', '404', 'manifest']
    def _is_infra(txt):
        return any(s in txt for s in _IGNORE)
    def _capture_err(msg):
        if not _is_infra(msg.text):
            errors.append(msg.text)
    page.on('console', lambda msg: _capture_err(msg) if msg.type == 'error' else None)
    page.on('pageerror', lambda exc: None if _is_infra(str(exc)) else errors.append(str(exc)))
    _fresh(page)
    page.wait_for_timeout(500)
    assert not errors, f'JS errors on load: {errors}'


# ── Runner ────────────────────────────────────────────────────────────────────
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    launch_kwargs = {'args': ['--no-sandbox']}
    if CHROMIUM:
        launch_kwargs['executable_path'] = CHROMIUM
    br  = p.chromium.launch(**launch_kwargs)
    ctx = br.new_context()
    pg  = ctx.new_page()

    # Runs before EVERY navigation's scripts — clears stale localStorage so the
    # on-load IIFE in index.auth.js never finds a cached user from a prior test.
    pg.add_init_script("try { localStorage.clear(); } catch(e) {}")

    print('\n── Login DS Runtime Tests ──')

    run('A: empty submit — both errors, focus email, 0 requests',      test_a_empty_submit_both_errors,     pg)
    run('B: before submit — Required stays passive on clear',           test_b_required_passive_before_submit, pg)
    run('C: Required→Format→Required cycle after submit',               test_c_required_format_required_cycle, pg)
    run('D: blur Format clears when field emptied before submit',       test_d_blur_format_clears_on_empty_before_submit, pg)
    run('E: password Required re-shows after submit + clear',          test_e_pass_required_cycle,          pg)
    run('F: Enter in email focuses password, 0 requests',              test_f_enter_email_focuses_password, pg)
    run('G: Enter in password fires doLogin() → 1 request',            test_g_enter_password_fires_login,   pg)
    run('H: double-click guard — only 1 request',                      test_h_double_submit_guard,          pg)
    run('I: in-flight Enter also guarded — still 1 request',           test_i_inflight_enter_also_guarded,  pg)
    run('J: success gap — button locked, no second request',            test_j_success_gap_button_locked,    pg)
    run('K: 401 → safe banner, not raw data.detail',                   test_k_401_shows_safe_banner,        pg)
    run('L: 429 → rate-limit message',                                 test_l_429_rate_limit_message,       pg)
    run('M: 500 non-JSON → server error message (not network)',        test_m_500_non_json_safe_message,    pg)
    run('N: network abort → network error message, button restored',   test_n_network_abort_message,        pg)
    run('O: invalid 2xx → no redirect, safe error, button restored',   test_o_invalid_2xx_no_redirect,      pg)
    run('P: storage failure → rollback both keys, safe error',         test_p_storage_failure_rollback,     pg)
    run('Q: eye toggle — type, icons, aria-pressed, 0 requests',       test_q_eye_toggle_full,              pg)
    run('R: login outlined + register gradient — no scope leak',       test_r_button_styles,                pg)
    run('S: mobile 375px — no overflow, 44px touch target, errors OK', test_s_mobile_375px,                 pg)
    run('T: no JS console errors on load',                             test_t_no_console_errors,            pg)
    run('U: autofill simulation — stale errors cleared on submit',     test_u_autofill_clears_stale_errors, pg)
    run('V: autofill CSS scoped to #loginSection, [hidden] scoped',    test_v_autofill_selectors_scoped,    pg)

    br.close()

passed  = sum(1 for _, s, _ in results if s == 'pass')
failed  = sum(1 for _, s, _ in results if s == 'fail')
skipped = sum(1 for _, s, _ in results if s == 'skip')
print(f'\n── {passed} passed, {failed} failed, {skipped} skipped ──\n')
if failed:
    sys.exit(1)
