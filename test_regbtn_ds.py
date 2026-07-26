"""
Register Submit Button — DS-BTN Runtime Tests (A–J, 10 tests)

Tests BTN-02 (outlined), BTN-03 (Primary color), BTN-07 (interaction states),
BTN-08 (user-select), BTN-09 (Action Save lifecycle: guard + loading + aria-busy
+ success-locked + error-restore).
"""
import asyncio, threading, json, os, shutil
from pathlib import Path
from playwright.async_api import async_playwright

HOST = 'http://127.0.0.1:8000'
ROOT = Path('/home/user/tawasalna')

PASS_COUNT = 0
FAIL_COUNT = 0


def _find_chromium():
    p = os.environ.get('PLAYWRIGHT_CHROMIUM_PATH', '')
    if p and os.path.isfile(p):
        return p
    if os.path.isfile('/opt/pw-browsers/chromium'):
        return '/opt/pw-browsers/chromium'
    for name in ('chromium', 'chromium-browser', 'google-chrome'):
        found = shutil.which(name)
        if found:
            return found
    return None

CHROMIUM = _find_chromium()


def ok(label):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f'  \033[92mPASS\033[0m  {label}')


def fail(label, reason=''):
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f': {reason}' if reason else ''
    print(f'  \033[91mFAIL\033[0m  {label}{msg}')


async def main():
    async with async_playwright() as p:
        launch_kwargs = {'args': ['--no-sandbox']}
        if CHROMIUM:
            launch_kwargs['executable_path'] = CHROMIUM
        browser = await p.chromium.launch(**launch_kwargs)
        ctx     = await browser.new_context()
        page    = await ctx.new_page()

        print('\n\033[1m── Register Submit Button DS-BTN Tests (A–J, 10 tests) ──\033[0m')

        # ── helpers ───────────────────────────────────────────────────────────

        async def open_register():
            await page.goto(f'{HOST}/login')
            await page.wait_for_load_state('networkidle')
            await page.evaluate("showRegister()")
            await page.evaluate("selectType('emp')")
            await page.wait_for_selector('#registerPanel.open', timeout=3000)

        async def fill_valid_form():
            await page.fill('#rName',  'اختبار مستخدم')
            await page.fill('#rEmail', 'test@example.com')
            await page.fill('#rPass',  'password123')
            # ensure emp is selected (default)
            await page.evaluate("window.curType = 'emp'")

        async def get_btn_style(prop):
            return await page.evaluate(
                f"getComputedStyle(document.getElementById('regBtn')).{prop}"
            )

        async def count_register_requests():
            return await page.evaluate("window._testRegReqs || 0")

        async def setup_request_counter():
            await page.evaluate("""
                window._testRegReqs = 0;
                var _orig = window.fetch;
                window.fetch = function(url) {
                    if (typeof url === 'string' && url.includes('/auth/register'))
                        window._testRegReqs++;
                    return _orig.apply(this, arguments);
                };
            """)

        # ── A: BTN-02 — regBtn is outlined (transparent bg, --ac border/color) ──
        label = 'A: BTN-02 outlined — transparent bg, --ac border + color, no gradient'
        try:
            await open_register()
            bg      = await get_btn_style('backgroundImage')
            bg_col  = await get_btn_style('backgroundColor')
            border  = await get_btn_style('borderStyle')
            color   = await get_btn_style('color')
            errors = []
            if 'gradient' in (bg or '').lower():
                errors.append(f'backgroundImage has gradient: {bg[:60]}')
            # transparent = rgba(0,0,0,0) or similar
            if bg_col and 'rgba(0, 0, 0, 0)' not in bg_col and 'transparent' not in bg_col:
                errors.append(f'backgroundColor not transparent: {bg_col}')
            if 'solid' not in (border or ''):
                errors.append(f'border not solid: {border}')
            # color should be greenish (--ac = #00c896 ≈ rgb(0,200,150))
            if color and not ('0, 200' in color or '0,200' in color):
                errors.append(f'color not --ac green: {color}')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── B: BTN-08 — user-select:none ──────────────────────────────────────
        label = 'B: BTN-08 user-select:none on regBtn'
        try:
            await open_register()
            us = await get_btn_style('userSelect')
            if us != 'none':
                fail(label, f'user-select={us}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── C: type="button" + aria-busy="false" defaults ─────────────────────
        label = 'C: type="button" + aria-busy="false" on initial load'
        try:
            await open_register()
            rtype    = await page.evaluate("document.getElementById('regBtn').type")
            aria     = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")
            disabled = await page.evaluate("document.getElementById('regBtn').disabled")
            errors = []
            if rtype != 'button':
                errors.append(f'type={rtype}')
            if aria != 'false':
                errors.append(f'aria-busy={aria}')
            if disabled:
                errors.append('regBtn is disabled on load')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── D: BTN-09 duplicate-submit guard — only 1 request ─────────────────
        label = 'D: BTN-09 duplicate-submit guard — only 1 request on rapid clicks'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            # Route register endpoint to stall so button stays loading
            stall_event = threading.Event()

            async def handle_register(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"email exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_register)

            # First click — enters loading, _rSubmitting = true
            await page.click('#regBtn')
            await page.wait_for_timeout(50)
            # Second invocation — bypasses disabled UI state to test the JS guard
            await page.evaluate("doRegister()")
            await page.wait_for_timeout(100)
            reqs = await count_register_requests()

            # Unblock
            stall_event.set()
            await page.wait_for_timeout(300)
            await page.unroute('**/auth/register')

            if reqs != 1:
                fail(label, f'{reqs} requests fired (expected 1)')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── E: BTN-09 loading state — disabled + aria-busy="true" + spinner ──
        label = 'E: BTN-09 loading — disabled, aria-busy="true", spinner class while in-flight'
        try:
            await open_register()
            await fill_valid_form()

            stall_event = threading.Event()

            async def handle_register_stall(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"email exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_register_stall)

            await page.click('#regBtn')
            await page.wait_for_timeout(80)

            disabled   = await page.evaluate("document.getElementById('regBtn').disabled")
            aria_busy  = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")
            has_spin   = await page.evaluate(
                "document.getElementById('regBtn').classList.contains('tw-btn-loading')"
            )

            stall_event.set()
            await page.wait_for_timeout(300)
            await page.unroute('**/auth/register')

            errors = []
            if not disabled:
                errors.append('regBtn not disabled during loading')
            if aria_busy != 'true':
                errors.append(f'aria-busy during loading: {aria_busy}')
            if not has_spin:
                errors.append('tw-btn-loading class missing during loading')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── F: BTN-09 error restore — button re-enabled, aria-busy="false" ────
        label = 'F: BTN-09 error restore — re-enabled + aria-busy="false" after 4xx/network error'
        try:
            await open_register()
            await fill_valid_form()

            async def handle_409(route):
                await route.fulfill(status=409, body='{"detail":"البريد الإلكتروني مستخدم بالفعل"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_409)
            await page.click('#regBtn')
            await page.wait_for_timeout(600)
            await page.unroute('**/auth/register')

            disabled  = await page.evaluate("document.getElementById('regBtn').disabled")
            aria_busy = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")
            has_spin  = await page.evaluate(
                "document.getElementById('regBtn').classList.contains('tw-btn-loading')"
            )
            errors = []
            if disabled:
                errors.append('regBtn still disabled after error')
            if aria_busy != 'false':
                errors.append(f'aria-busy after error: {aria_busy}')
            if has_spin:
                errors.append('tw-btn-loading still present after error')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── G: BTN-09 success locked — button stays loading until redirect ─────
        label = 'G: BTN-09 success locked — button stays disabled/loading during 700ms gap'
        try:
            await open_register()
            await fill_valid_form()

            fake_user = {'id': 99, 'tw_id': 'U9620test', 'full_name': 'Test',
                         'email': 'test@example.com', 'user_type': 'emp',
                         'country_code': '9620', 'created_at': '2026-01-01T00:00:00'}

            async def handle_success(route):
                await route.fulfill(
                    status=200,
                    body=json.dumps({'user': fake_user, 'token': 'fake.jwt.token'}),
                    headers={'content-type': 'application/json'}
                )

            await page.route('**/auth/register', handle_success)

            await page.evaluate("window._redir_intercepted = false;")
            # Override redirect so we can inspect state in the gap
            await page.evaluate("""
                window._origRedirect = window.redirect;
                window.redirect = function(u) {
                    window._redir_intercepted = true;
                    // do NOT actually navigate
                };
            """)

            await page.click('#regBtn')
            await page.wait_for_timeout(100)  # inside 700ms gap

            disabled  = await page.evaluate("document.getElementById('regBtn').disabled")
            aria_busy = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")
            has_spin  = await page.evaluate(
                "document.getElementById('regBtn').classList.contains('tw-btn-loading')"
            )
            intercepted = await page.evaluate("window._redir_intercepted")

            await page.unroute('**/auth/register')
            # Clear localStorage so the login page auth guard doesn't redirect in subsequent tests
            await page.evaluate("localStorage.removeItem('tw_user'); localStorage.removeItem('tw_jwt');")

            errors = []
            if not intercepted:
                errors.append('redirect was not called (check test setup)')
            if not disabled:
                errors.append('regBtn should remain disabled in success gap')
            if aria_busy != 'true':
                errors.append(f'aria-busy in success gap: {aria_busy}')
            if not has_spin:
                errors.append('tw-btn-loading should remain in success gap')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── H: BTN-09 network abort — button restored ─────────────────────────
        label = 'H: BTN-09 network error — button restored after abort'
        try:
            await open_register()
            await fill_valid_form()

            async def handle_abort(route):
                await route.abort()

            await page.route('**/auth/register', handle_abort)
            await page.click('#regBtn')
            await page.wait_for_timeout(600)
            await page.unroute('**/auth/register')

            disabled  = await page.evaluate("document.getElementById('regBtn').disabled")
            aria_busy = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")
            errors = []
            if disabled:
                errors.append('regBtn still disabled after network abort')
            if aria_busy != 'false':
                errors.append(f'aria-busy after abort: {aria_busy}')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── I: Enter in rPass fires doRegister (same guard applies) ───────────
        label = 'I: Enter in rPass triggers doRegister + guard prevents duplicate'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            stall_event = threading.Event()

            async def handle_stall(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_stall)

            # Enter in rPass
            await page.press('#rPass', 'Enter')
            await page.wait_for_timeout(80)

            # Try Enter again while in-flight
            await page.press('#rPass', 'Enter')
            await page.wait_for_timeout(80)

            reqs = await count_register_requests()
            stall_event.set()
            await page.wait_for_timeout(300)
            await page.unroute('**/auth/register')

            if reqs != 1:
                fail(label, f'{reqs} requests fired (expected 1)')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── J: empty-form submit — 0 requests, button never enters loading ─────
        label = 'J: empty submit — validation blocks — 0 requests, button stays default'
        try:
            await open_register()
            await setup_request_counter()
            await page.click('#regBtn')
            await page.wait_for_timeout(200)
            reqs     = await count_register_requests()
            disabled = await page.evaluate("document.getElementById('regBtn').disabled")
            aria     = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")
            has_spin = await page.evaluate(
                "document.getElementById('regBtn').classList.contains('tw-btn-loading')"
            )
            errors = []
            if reqs != 0:
                errors.append(f'{reqs} requests fired (expected 0)')
            if disabled:
                errors.append('regBtn disabled after failed validation')
            if aria != 'false':
                errors.append(f'aria-busy after failed validation: {aria}')
            if has_spin:
                errors.append('tw-btn-loading class present after failed validation')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        await browser.close()

    print(f'\n\033[1m── {PASS_COUNT} passed, {FAIL_COUNT} failed, 0 skipped ──\033[0m\n')


asyncio.run(main())
