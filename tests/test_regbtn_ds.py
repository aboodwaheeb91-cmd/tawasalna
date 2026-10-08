"""
Register Submit Button — DS-BTN Runtime Tests (A–L, 12 tests)

Tests BTN-02 (outlined), BTN-03 (Primary color), BTN-07 (interaction states),
BTN-08 (user-select), BTN-09 (Action Save lifecycle: guard + loading + aria-busy
+ success-locked + error-restore).
"""
import asyncio, sys, threading, json, os, shutil
from pathlib import Path
from playwright.async_api import async_playwright

HOST = 'http://127.0.0.1:8000'

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

        print('\n\033[1m── Register Submit Button DS-BTN Tests (A–L, 12 tests) ──\033[0m')

        # ── helpers ───────────────────────────────────────────────────────────

        async def open_register():
            await page.goto(f'{HOST}/login')
            await page.wait_for_load_state('networkidle')
            await page.evaluate("showRegister()")
            await page.evaluate("selectType('emp')")
            # state='attached': verify selectType() added the open class (DOM check).
            # Visual visibility check is unreliable during the 320ms CSS transition.
            await page.wait_for_selector('#registerPanel.open', timeout=3000, state='attached')

        async def fill_valid_form():
            await page.fill('#rName',  'اختبار مستخدم')
            await page.fill('#rEmail', 'test@example.com')
            await page.fill('#rPass',  'password123')
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

        # ── A: BTN-02 — regBtn is outlined ────────────────────────────────────
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
            if bg_col and 'rgba(0, 0, 0, 0)' not in bg_col and 'transparent' not in bg_col:
                errors.append(f'backgroundColor not transparent: {bg_col}')
            if 'solid' not in (border or ''):
                errors.append(f'border not solid: {border}')
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

        # ── D: duplicate rapid clicks — only 1 request ────────────────────────
        label = 'D: BTN-09 duplicate rapid clicks — only 1 request'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            stall_event = threading.Event()

            async def handle_register_d(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"email exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_register_d)

            await page.click('#regBtn')
            await page.wait_for_timeout(50)
            # Call JS function directly to bypass the disabled UI and test the _rSubmitting guard
            await page.evaluate("doRegister()")
            await page.wait_for_timeout(100)
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

        # ── E: loading state — disabled + aria-busy="true" + spinner ──────────
        label = 'E: BTN-09 loading — disabled, aria-busy="true", spinner class while in-flight'
        try:
            await open_register()
            await fill_valid_form()

            stall_event = threading.Event()

            async def handle_register_e(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"email exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_register_e)

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

        # ── F: error restore — button re-enabled, aria-busy="false" ───────────
        label = 'F: BTN-09 error restore — re-enabled + aria-busy="false" after 4xx error'
        try:
            await open_register()
            await fill_valid_form()

            async def handle_409_f(route):
                await route.fulfill(status=409, body='{"detail":"البريد الإلكتروني مستخدم بالفعل"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_409_f)
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

        # ── G: success locked — button locked on submit, redirect fires exactly once
        label = 'G: BTN-09 success locked — button locked on submit, redirect fires exactly once'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            fake_user = {'id': 99, 'tw_id': 'U9620test', 'full_name': 'Test',
                         'email': 'test@example.com', 'user_type': 'emp',
                         'country_code': '9620', 'created_at': '2026-01-01T00:00:00'}

            async def handle_success_g(route):
                await route.fulfill(
                    status=200,
                    body=json.dumps({'user': fake_user, 'token': 'fake.jwt.token'}),
                    headers={'content-type': 'application/json'}
                )

            await page.route('**/auth/register', handle_success_g)

            # Stub redirect: count calls, do NOT navigate
            await page.evaluate("""
                window._redir_call_count = 0;
                window._origRedirect = window.redirect;
                window.redirect = function(u) {
                    window._redir_call_count++;
                };
            """)

            await page.click('#regBtn')

            # Wait for redirect to fire — event-driven, no fixed sleep.
            # The success-locked pattern sets _success=true then setTimeout(redirect, 700).
            # The button must stay locked from click until redirect fires (finally skips restore).
            await page.wait_for_function("window._redir_call_count >= 1", timeout=3000)

            # After redirect fires: verify success-locked state
            after = await page.evaluate("""({
                disabled: document.getElementById('regBtn').disabled,
                ariaBusy: document.getElementById('regBtn').getAttribute('aria-busy'),
                hasSpin:  document.getElementById('regBtn').classList.contains('tw-btn-loading'),
                redirCount: window._redir_call_count
            })""")
            reqs = await count_register_requests()

            await page.unroute('**/auth/register')
            await page.evaluate("""
                window.redirect = window._origRedirect;
                localStorage.removeItem('tw_user');
                localStorage.removeItem('tw_jwt');
            """)

            errors = []
            # Button must still be locked — if finally ran on success, it would be restored
            if not after['disabled']:
                errors.append('button restored before redirect — finally ran on success path')
            if after['ariaBusy'] != 'true':
                errors.append(f"aria-busy restored before redirect: {after['ariaBusy']}")
            if not after['hasSpin']:
                errors.append('spinner removed before redirect — finally ran on success path')
            if after['redirCount'] != 1:
                errors.append(f"redirect call count: {after['redirCount']} (expected exactly 1)")
            if reqs != 1:
                errors.append(f'{reqs} register requests (expected 1)')

            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── H: network abort — button restored ────────────────────────────────
        label = 'H: BTN-09 network error — button restored after abort'
        try:
            await open_register()
            await fill_valid_form()

            async def handle_abort_h(route):
                await route.abort()

            await page.route('**/auth/register', handle_abort_h)
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

        # ── I: Enter + Enter guard ─────────────────────────────────────────────
        label = 'I: Enter+Enter — first Enter submits, second Enter while in-flight → 1 request'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            stall_event = threading.Event()

            async def handle_stall_i(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_stall_i)

            await page.press('#rPass', 'Enter')
            await page.wait_for_timeout(80)
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

        # ── J: empty submit — validation blocks, 0 requests ───────────────────
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

        # ── K: Click + Enter — distinct from D (click+click) and I (Enter+Enter)
        label = 'K: Click+Enter — click #regBtn then Enter in #rPass while in-flight → 1 request'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            stall_event = threading.Event()

            async def handle_stall_k(route):
                await asyncio.get_event_loop().run_in_executor(None, stall_event.wait)
                await route.fulfill(status=409, body='{"detail":"exists"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_stall_k)

            # Click button (first submit — enters loading)
            await page.click('#regBtn')
            await page.wait_for_timeout(80)
            # While in-flight, press Enter in rPass (tests keydown guard)
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

        # ── L: Failure + Retry — _rSubmitting resets after error ──────────────
        label = 'L: Failure+Retry — 409 restores guard; second attempt fires → 2 total requests'
        try:
            await open_register()
            await fill_valid_form()
            await setup_request_counter()

            # First attempt: 409 error
            async def handle_409_l(route):
                await route.fulfill(status=409, body='{"detail":"البريد الإلكتروني مستخدم بالفعل"}',
                                    headers={'content-type': 'application/json'})

            await page.route('**/auth/register', handle_409_l)
            await page.click('#regBtn')
            await page.wait_for_timeout(500)  # let error restore run
            await page.unroute('**/auth/register')

            disabled_after_err = await page.evaluate("document.getElementById('regBtn').disabled")
            aria_after_err     = await page.evaluate("document.getElementById('regBtn').getAttribute('aria-busy')")

            # Second attempt: success
            fake_user = {'id': 99, 'tw_id': 'U9620test', 'full_name': 'Test',
                         'email': 'test@example.com', 'user_type': 'emp',
                         'country_code': '9620', 'created_at': '2026-01-01T00:00:00'}

            async def handle_success_l(route):
                await route.fulfill(
                    status=200,
                    body=json.dumps({'user': fake_user, 'token': 'fake.jwt.token'}),
                    headers={'content-type': 'application/json'}
                )

            await page.route('**/auth/register', handle_success_l)
            await page.evaluate("""
                window._redir_count_l = 0;
                window._origRedirectL = window.redirect;
                window.redirect = function(u) { window._redir_count_l++; };
            """)

            await page.click('#regBtn')
            # Wait for redirect to fire — event-driven, no fixed sleep
            await page.wait_for_function("window._redir_count_l >= 1", timeout=3000)

            reqs        = await count_register_requests()
            redir_count = await page.evaluate("window._redir_count_l")

            await page.unroute('**/auth/register')
            await page.evaluate("""
                window.redirect = window._origRedirectL;
                localStorage.removeItem('tw_user');
                localStorage.removeItem('tw_jwt');
            """)

            errors = []
            if disabled_after_err:
                errors.append('button still disabled after 409 (guard not reset)')
            if aria_after_err != 'false':
                errors.append(f'aria-busy after error: {aria_after_err}')
            if reqs != 2:
                errors.append(f'{reqs} total requests (expected 2)')
            if redir_count != 1:
                errors.append(f'redirect count: {redir_count} (expected 1 on success)')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        await browser.close()

    print(f'\n\033[1m── {PASS_COUNT} passed, {FAIL_COUNT} failed, 0 skipped ──\033[0m\n')
    return FAIL_COUNT


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
