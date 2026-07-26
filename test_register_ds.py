"""
Register DS-INP / DS-VAL Runtime Tests
Tests DS-INP anatomy (wrappers, labels, aria, eye toggle) and DS-VAL timing
(Required only after submit, Format on blur, live correction, state machine)
for the three register fields: rName, rEmail, rPass.
"""
import asyncio, os, shutil, sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT    = Path(__file__).resolve().parent
BASE    = 'http://127.0.0.1:8000'
PASS_OK = 0
FAIL_OK = 0


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
    global PASS_OK
    PASS_OK += 1
    print(f'  \033[92mPASS\033[0m  {label}')

def fail(label, reason):
    global FAIL_OK
    FAIL_OK += 1
    print(f'  \033[91mFAIL\033[0m  {label}: {reason}')

async def run():
    async with async_playwright() as pw:
        launch_kwargs = {'args': ['--no-sandbox']}
        if CHROMIUM:
            launch_kwargs['executable_path'] = CHROMIUM
        browser = await pw.chromium.launch(**launch_kwargs)
        ctx  = await browser.new_context(viewport={'width': 390, 'height': 844})
        page = await ctx.new_page()

        # ── helpers ────────────────────────────────────────────────────────────
        async def open_register(t='emp'):
            """Navigate and open register panel for given account type."""
            await page.goto(f'{BASE}/login')
            await page.wait_for_load_state('networkidle')
            await page.evaluate("showRegister()")
            await page.evaluate(f"selectType('{t}')")
            await page.wait_for_selector('#registerPanel.open', timeout=2000)

        async def field_error_text(eid):
            return await page.evaluate(
                f"(function(){{var e=document.getElementById('{eid}');return e?e.textContent.trim():null}})()"
            )

        async def field_error_hidden(eid):
            return await page.evaluate(
                f"(function(){{var e=document.getElementById('{eid}');return e?e.hasAttribute('hidden'):true}})()"
            )

        async def wrapper_has_error(wid):
            return await page.evaluate(
                f"(function(){{var w=document.getElementById('{wid}');return w?w.classList.contains('has-error'):false}})()"
            )

        async def input_aria_invalid(iid):
            return await page.evaluate(
                f"(function(){{var i=document.getElementById('{iid}');return i?i.getAttribute('aria-invalid'):null}})()"
            )

        # ── A: empty submit — all 3 errors, focus rName, 0 requests ──────────
        label = 'A: empty submit — all 3 errors, focus rName, 0 requests'
        try:
            await open_register()
            reqs = []
            page.on('request', lambda r: reqs.append(r) if '/auth/register' in r.url else None)
            await page.evaluate("doRegister()")
            await page.wait_for_timeout(100)
            e_name  = await field_error_hidden('r-name-error')
            e_email = await field_error_hidden('r-email-error')
            e_pass  = await field_error_hidden('r-pass-error')
            focused = await page.evaluate("document.activeElement.id")
            reg_reqs = [r for r in reqs if '/auth/register' in r.url]
            if e_name or e_email or e_pass:
                fail(label, f'errors hidden: name={e_name} email={e_email} pass={e_pass}')
            elif focused != 'rName':
                fail(label, f'focus on {focused}, expected rName')
            elif reg_reqs:
                fail(label, f'{len(reg_reqs)} requests fired')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── B: before submit — Required stays passive (no errors on blur/clear) ──
        label = 'B: before submit — Required stays passive on blur/clear'
        try:
            await open_register()
            # Touch name then clear
            await page.fill('#rName', 'test')
            await page.fill('#rName', '')
            await page.evaluate("document.getElementById('rName').dispatchEvent(new Event('blur'))")
            # Touch email then clear
            await page.fill('#rEmail', 'a@b.com')
            await page.fill('#rEmail', '')
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('blur'))")
            # Touch pass then clear
            await page.fill('#rPass', 'abc')
            await page.fill('#rPass', '')
            await page.evaluate("document.getElementById('rPass').dispatchEvent(new Event('blur'))")
            await page.wait_for_timeout(80)
            e_name  = await field_error_hidden('r-name-error')
            e_email = await field_error_hidden('r-email-error')
            e_pass  = await field_error_hidden('r-pass-error')
            if not e_name or not e_email or not e_pass:
                fail(label, f'unexpected Required errors: name={not e_name} email={not e_email} pass={not e_pass}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── C: Required→clears on type (name field) ───────────────────────────
        label = 'C: Required clears on type after submit (name field)'
        try:
            await open_register()
            await page.evaluate("doRegister()")  # trigger Required on all
            await page.wait_for_timeout(80)
            e_before = await field_error_hidden('r-name-error')
            await page.fill('#rName', 'أ')
            await page.evaluate("document.getElementById('rName').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            e_after = await field_error_hidden('r-name-error')
            if e_before:
                fail(label, 'r-name-error should be visible after empty submit')
            elif not e_after:
                fail(label, 'r-name-error should clear when name is typed')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── D: email blur Format error on non-empty invalid; no error on blur-empty ──
        label = 'D: blur Format clears when field emptied before submit'
        try:
            await open_register()
            # Non-empty invalid → blur → Format error
            await page.fill('#rEmail', 'notanemail')
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('blur'))")
            await page.wait_for_timeout(80)
            e_after_blur = await field_error_hidden('r-email-error')
            # Now clear → should clear the Format error (no Required before submit)
            await page.fill('#rEmail', '')
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            e_after_clear = await field_error_hidden('r-email-error')
            if e_after_blur:
                fail(label, 'blur on invalid non-empty should show Format error')
            elif not e_after_clear:
                fail(label, 'clearing field before submit should hide Format error (no Required)')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── E: email pre-blur timing — no Format on input before blur/submit ────
        label = 'E: email pre-blur timing — no Format on input before blur/submit'
        try:
            await open_register()
            await page.fill('#rEmail', 'bad@')
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            hidden_before   = await field_error_hidden('r-email-error')
            has_err_before  = await wrapper_has_error('wrapper-rEmail')
            aria_inv_before = await input_aria_invalid('rEmail')
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('blur'))")
            await page.wait_for_timeout(80)
            hidden_after_blur   = await field_error_hidden('r-email-error')
            aria_inv_after_blur = await input_aria_invalid('rEmail')
            await page.fill('#rEmail', 'valid@example.com')
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            hidden_after_fix   = await field_error_hidden('r-email-error')
            aria_inv_after_fix = await input_aria_invalid('rEmail')
            errors = []
            if not hidden_before:         errors.append('Format shown during input before blur/submit')
            if has_err_before:            errors.append('has-error before blur/submit')
            if aria_inv_before != 'false':errors.append(f'aria-invalid={aria_inv_before} before blur/submit')
            if hidden_after_blur:         errors.append('Format not shown after blur')
            if aria_inv_after_blur != 'true': errors.append(f'aria-invalid={aria_inv_after_blur} after blur')
            if not hidden_after_fix:      errors.append('Format not cleared after typing valid email')
            if aria_inv_after_fix != 'false': errors.append(f'aria-invalid={aria_inv_after_fix} after fix')
            if errors: fail(label, '; '.join(errors))
            else: ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── F: Required→Format→Required cycle (email, after submit) ──────────
        label = 'F: Required→Format→Required cycle after submit (email)'
        try:
            await open_register()
            await page.evaluate("doRegister()")   # Required on empty email
            await page.wait_for_timeout(80)
            txt_req = await field_error_text('r-email-error')
            await page.fill('#rEmail', 'bad@@')   # non-empty invalid → Format live (after submit)
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            txt_fmt = await field_error_text('r-email-error')
            await page.fill('#rEmail', '')        # clear → Required re-arms (attempted)
            await page.evaluate("document.getElementById('rEmail').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            txt_req2 = await field_error_text('r-email-error')
            if 'مطلوب' not in (txt_req or ''):
                fail(label, f'expected Required, got: {txt_req}')
            elif 'صيغة' not in (txt_fmt or ''):
                fail(label, f'expected Format, got: {txt_fmt}')
            elif 'مطلوب' not in (txt_req2 or ''):
                fail(label, f'expected Required after clear, got: {txt_req2}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── G: password Required re-shows after submit + clear ────────────────
        label = 'G: password Required re-shows after submit + clear'
        try:
            await open_register()
            await page.evaluate("doRegister()")
            await page.wait_for_timeout(80)
            txt1 = await field_error_text('r-pass-error')
            await page.fill('#rPass', 'abc123')
            await page.evaluate("document.getElementById('rPass').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            hidden_after_fill = await field_error_hidden('r-pass-error')
            await page.fill('#rPass', '')
            await page.evaluate("document.getElementById('rPass').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            txt2 = await field_error_text('r-pass-error')
            if 'مطلوب' not in (txt1 or ''):
                fail(label, f'expected Required on empty submit, got: {txt1}')
            elif not hidden_after_fill:
                fail(label, 'error should clear when password >= 6 chars')
            elif 'مطلوب' not in (txt2 or ''):
                fail(label, f'expected Required after clear, got: {txt2}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── H: password short error on submit ─────────────────────────────────
        label = 'H: password short error (< 6 chars) on submit'
        try:
            await open_register()
            await page.fill('#rName', 'أحمد')
            await page.fill('#rEmail', 'a@b.com')
            await page.fill('#rPass', 'abc')     # only 3 chars
            await page.evaluate("doRegister()")
            await page.wait_for_timeout(80)
            txt = await field_error_text('r-pass-error')
            if 'قصيرة' not in (txt or ''):
                fail(label, f'expected short-password error, got: {txt}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── I: short error clears live when >= 6 chars ────────────────────────
        label = 'I: short error clears live when >= 6 chars typed'
        try:
            await open_register()
            await page.fill('#rName', 'أحمد')
            await page.fill('#rEmail', 'a@b.com')
            await page.fill('#rPass', 'abc')
            await page.evaluate("doRegister()")
            await page.wait_for_timeout(80)
            # Now type enough chars
            await page.fill('#rPass', 'abcdef')
            await page.evaluate("document.getElementById('rPass').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            hidden = await field_error_hidden('r-pass-error')
            if not hidden:
                fail(label, 'short error should clear when password reaches 6 chars')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── J: eye toggle — type, icons, aria-pressed, aria-label ─────────────
        label = 'J: eye toggle — type, icons, aria-pressed, aria-label, 0 requests'
        try:
            await open_register()
            reqs = []
            page.on('request', lambda r: reqs.append(r) if '/auth/register' in r.url else None)
            # Initial state
            t0    = await page.evaluate("document.getElementById('rPass').type")
            press0 = await page.evaluate("document.getElementById('rPassEye').getAttribute('aria-pressed')")
            show0  = await page.evaluate("document.getElementById('rEyeShow').hasAttribute('hidden')")
            hide0  = await page.evaluate("document.getElementById('rEyeHide').hasAttribute('hidden')")
            # Click eye
            await page.click('#rPassEye')
            await page.wait_for_timeout(80)
            t1    = await page.evaluate("document.getElementById('rPass').type")
            press1 = await page.evaluate("document.getElementById('rPassEye').getAttribute('aria-pressed')")
            lbl1   = await page.evaluate("document.getElementById('rPassEye').getAttribute('aria-label')")
            show1  = await page.evaluate("document.getElementById('rEyeShow').hasAttribute('hidden')")
            hide1  = await page.evaluate("document.getElementById('rEyeHide').hasAttribute('hidden')")
            # Click again
            await page.click('#rPassEye')
            await page.wait_for_timeout(80)
            t2    = await page.evaluate("document.getElementById('rPass').type")
            press2 = await page.evaluate("document.getElementById('rPassEye').getAttribute('aria-pressed')")
            reg_reqs = [r for r in reqs if '/auth/register' in r.url]
            errors = []
            if t0 != 'password':   errors.append(f'initial type={t0}')
            if press0 != 'false':  errors.append(f'initial aria-pressed={press0}')
            if show0:              errors.append('rEyeShow should be visible initially')
            if not hide0:          errors.append('rEyeHide should be hidden initially')
            if t1 != 'text':       errors.append(f'after toggle type={t1}')
            if press1 != 'true':   errors.append(f'after toggle aria-pressed={press1}')
            if 'إخفاء' not in (lbl1 or ''): errors.append(f'after toggle aria-label={lbl1}')
            if not show1:          errors.append('rEyeShow should be hidden after toggle')
            if hide1:              errors.append('rEyeHide should be visible after toggle')
            if t2 != 'password':   errors.append(f'after second toggle type={t2}')
            if press2 != 'false':  errors.append(f'after second toggle aria-pressed={press2}')
            if reg_reqs:           errors.append(f'{len(reg_reqs)} requests fired')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── K: both loginBtn + regBtn are BTN-02 outlined — no gradient, no scope leak ──
        label = 'K: regBtn gradient — login outlined + register gradient — no scope leak'
        try:
            await open_register()
            login_bg = await page.evaluate(
                "getComputedStyle(document.getElementById('loginBtn')).backgroundImage"
            )
            reg_bg = await page.evaluate(
                "getComputedStyle(document.getElementById('regBtn')).backgroundImage"
            )
            login_border = await page.evaluate(
                "getComputedStyle(document.getElementById('loginBtn')).borderStyle"
            )
            reg_border = await page.evaluate(
                "getComputedStyle(document.getElementById('regBtn')).borderStyle"
            )
            reg_aria_busy = await page.evaluate(
                "document.getElementById('regBtn').getAttribute('aria-busy')"
            )
            reg_type = await page.evaluate(
                "document.getElementById('regBtn').type"
            )
            errors = []
            if 'gradient' in (login_bg or '').lower():
                errors.append('loginBtn should not be gradient (should be outlined)')
            if 'solid' not in (login_border or ''):
                errors.append(f'loginBtn border style: {login_border}')
            if 'gradient' in (reg_bg or '').lower():
                errors.append(f'regBtn should be outlined (BTN-02), got gradient: {(reg_bg or "")[:60]}')
            if 'solid' not in (reg_border or ''):
                errors.append(f'regBtn border style should be solid, got: {reg_border}')
            if reg_aria_busy != 'false':
                errors.append(f'regBtn aria-busy default should be "false", got: {reg_aria_busy}')
            if reg_type != 'button':
                errors.append(f'regBtn type should be "button", got: {reg_type}')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── L: [hidden] scoped to #registerPanel ──────────────────────────────
        label = 'L: [hidden] scoped to #registerPanel, not global'
        try:
            css_text = (ROOT / 'index.css').read_text(encoding='utf-8')
            has_reg_hidden   = '#registerPanel [hidden]' in css_text
            has_login_hidden = '#loginSection [hidden]' in css_text
            # Must NOT have a bare global [hidden] rule that could clobber other pages
            has_bare_hidden  = '\n[hidden]{' in css_text or '\n[hidden] {' in css_text
            if not has_reg_hidden:
                fail(label, '#registerPanel [hidden] rule missing from index.css')
            elif not has_login_hidden:
                fail(label, '#loginSection [hidden] rule missing from index.css')
            elif has_bare_hidden:
                fail(label, 'bare global [hidden] rule present — should be scoped')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── M: autofill CSS scoped to #registerPanel ──────────────────────────
        label = 'M: autofill CSS scoped to #registerPanel, [hidden] scoped'
        try:
            css_text = (ROOT / 'index.css').read_text(encoding='utf-8')
            reg_autofill    = '#registerPanel input:-webkit-autofill' in css_text
            login_autofill  = '#loginSection input:-webkit-autofill'  in css_text
            global_autofill = '\ninput:-webkit-autofill{' in css_text or '\ninput:-webkit-autofill {' in css_text
            if not reg_autofill:
                fail(label, '#registerPanel autofill rule missing')
            elif not login_autofill:
                fail(label, '#loginSection autofill rule missing')
            elif global_autofill:
                fail(label, 'global unscoped autofill rule present')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── N: no JS console errors on load ───────────────────────────────────
        label = 'N: no JS console errors on load'
        try:
            errors_on_load    = []
            pageerrors_on_load = []
            def on_console(msg):
                if msg.type == 'error':
                    errors_on_load.append(msg.text)
            def on_pageerror(err):
                pageerrors_on_load.append(str(err))
            page.on('console', on_console)
            page.on('pageerror', on_pageerror)
            await page.goto(f'{BASE}/login')
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(300)
            page.remove_listener('console', on_console)
            page.remove_listener('pageerror', on_pageerror)
            local_errors = [e for e in errors_on_load
                            if 'unpkg.com' not in e and 'fonts.googleapis' not in e
                            and 'ERR_CONNECTION_RESET' not in e
                            and 'sw.js' not in e]
            all_errors = local_errors + pageerrors_on_load
            if all_errors:
                fail(label, '; '.join(all_errors[:3]))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── O: stale errors cleared on re-submit with valid data (autofill sim) ─
        label = 'O: autofill simulation — stale errors cleared on re-submit'
        try:
            await open_register()
            await page.evaluate("doRegister()")   # trigger all errors
            await page.wait_for_timeout(80)
            # Now set values without input events (autofill simulation)
            await page.evaluate("""
                document.getElementById('rName').value  = 'أحمد محمد';
                document.getElementById('rEmail').value = 'test@example.com';
                document.getElementById('rPass').value  = 'abc123!';
            """)
            # Mock fetch for valid response; stub redirect to avoid navigation
            await page.evaluate("""
                window.__origFetch = window.fetch;
                window.__origRedirect = window.redirect;
                window.redirect = function(){};
                window.fetch = function(url, opts){
                    if(url === '/auth/register'){
                        return Promise.resolve({
                            ok: true, status: 200,
                            json: function(){
                                return Promise.resolve({
                                    user:{id:1,tw_id:'U9620abc',user_type:'emp',full_name:'أحمد محمد',email:'test@example.com'},
                                    token:'tok'
                                });
                            }
                        });
                    }
                    return window.__origFetch(url, opts);
                };
            """)
            await page.evaluate("doRegister()")   # stale errors should be cleared by submit logic
            await page.wait_for_timeout(300)
            e_name  = await field_error_hidden('r-name-error')
            e_email = await field_error_hidden('r-email-error')
            e_pass  = await field_error_hidden('r-pass-error')
            await page.evaluate("""
                window.fetch = window.__origFetch; delete window.__origFetch;
                window.redirect = window.__origRedirect; delete window.__origRedirect;
                localStorage.clear();
            """)
            if not e_name or not e_email or not e_pass:
                fail(label, f'stale errors still visible: name={not e_name} email={not e_email} pass={not e_pass}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── P: strength bar appears on password input ──────────────────────────
        label = 'P: strength bar appears when rPass gets input'
        try:
            await open_register()
            bar_before = await page.evaluate("document.getElementById('passStrengthBar').style.display")
            await page.fill('#rPass', 'abc')
            await page.evaluate("document.getElementById('rPass').dispatchEvent(new Event('input'))")
            await page.wait_for_timeout(80)
            bar_after = await page.evaluate("document.getElementById('passStrengthBar').style.display")
            if bar_after == 'none' or bar_after == '':
                fail(label, f'strength bar not shown after input (display={bar_after})')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── Q: ARIA anatomy on all 3 fields ───────────────────────────────────
        label = 'Q: DS-INP ARIA anatomy — aria-required, aria-invalid, aria-describedby'
        try:
            await open_register()
            checks = [
                ('rName',  'r-name-error',  'wrapper-rName'),
                ('rEmail', 'r-email-error', 'wrapper-rEmail'),
                ('rPass',  'r-pass-error',  'wrapper-rPass'),
            ]
            errors = []
            for (fid, eid, wid) in checks:
                req = await page.evaluate(f"document.getElementById('{fid}').getAttribute('aria-required')")
                inv = await page.evaluate(f"document.getElementById('{fid}').getAttribute('aria-invalid')")
                desc = await page.evaluate(f"document.getElementById('{fid}').getAttribute('aria-describedby')")
                lbl  = await page.evaluate(f"document.querySelector('label[for=\"{fid}\"]')")
                err_role = await page.evaluate(f"document.getElementById('{eid}').getAttribute('role')")
                if req != 'true':    errors.append(f'{fid} aria-required={req}')
                if inv != 'false':   errors.append(f'{fid} aria-invalid={inv}')
                if eid not in (desc or ''): errors.append(f'{fid} aria-describedby={desc}')
                if lbl is None:      errors.append(f'{fid} missing <label for=>')
                if err_role != 'alert': errors.append(f'{eid} role={err_role}')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── R: selectType switches label, placeholder, autocomplete — all 3 types ──
        label = 'R: selectType label/placeholder/autocomplete — emp / co / edu'
        try:
            errors = []
            type_specs = [
                ('emp', 'الاسم الكامل',            'اكتب اسمك...',           'name'),
                ('co',  'اسم الشركة / الجهة',      'اسم شركتك أو مؤسستك...', 'organization'),
                ('edu', 'اسم المؤسسة التعليمية',   'اسم الجامعة أو المركز...','organization'),
            ]
            for (t, exp_label, exp_ph, exp_ac) in type_specs:
                await open_register(t)
                got_label = await page.evaluate("document.getElementById('nameLabel').textContent.trim()")
                got_ph    = await page.evaluate("document.getElementById('rName').placeholder")
                got_ac    = await page.evaluate("document.getElementById('rName').getAttribute('autocomplete')")
                wrap_ok   = await page.evaluate("document.getElementById('wrapper-rName') !== null")
                req_ok    = await page.evaluate("document.getElementById('rName').getAttribute('aria-required')")
                # No new input elements created
                n_inputs  = await page.evaluate(
                    "document.getElementById('registerPanel').querySelectorAll('input').length"
                )
                if got_label != exp_label:
                    errors.append(f'{t}: label="{got_label}" (expected "{exp_label}")')
                if got_ph != exp_ph:
                    errors.append(f'{t}: placeholder="{got_ph}" (expected "{exp_ph}")')
                if got_ac != exp_ac:
                    errors.append(f'{t}: autocomplete="{got_ac}" (expected "{exp_ac}")')
                if not wrap_ok:
                    errors.append(f'{t}: wrapper-rName disappeared')
                if req_ok != 'true':
                    errors.append(f'{t}: aria-required={req_ok}')
                if n_inputs != 3:
                    errors.append(f'{t}: unexpected input count={n_inputs} (expected 3)')
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── S: mobile 375×812 — no overflow, errors not clipped, eye touch target ──
        label = 'S: mobile 375×812 — no horizontal overflow, errors visible, eye ≥44px'
        try:
            mob_ctx  = await browser.new_context(viewport={'width': 375, 'height': 812})
            mob_page = await mob_ctx.new_page()
            await mob_page.goto(f'{BASE}/login')
            await mob_page.wait_for_load_state('networkidle')
            await mob_page.evaluate("showRegister()")
            await mob_page.evaluate("selectType('emp')")
            await mob_page.wait_for_selector('#registerPanel.open', timeout=2000)
            # Submit with all fields empty → all 3 Required errors simultaneously
            await mob_page.evaluate("doRegister()")
            await mob_page.wait_for_timeout(150)

            mob_errors = []

            # No horizontal overflow
            overflow = await mob_page.evaluate(
                "document.body.scrollWidth > document.body.clientWidth"
            )
            if overflow:
                mob_errors.append('horizontal overflow on body')

            # All 3 errors visible (not hidden) — tests simultaneous display
            for eid in ('r-name-error', 'r-email-error', 'r-pass-error'):
                h = await mob_page.evaluate(f"document.getElementById('{eid}').hasAttribute('hidden')")
                if h:
                    mob_errors.append(f'{eid} hidden on mobile')

            # Panel not clipping content — scrollHeight must not exceed clientHeight
            panel_overflow = await mob_page.evaluate("""
                (function(){
                    var p = document.getElementById('registerPanel');
                    if(!p) return null;
                    return {scrollH: p.scrollHeight, clientH: p.clientHeight};
                })()
            """)
            if panel_overflow:
                if panel_overflow['scrollH'] > panel_overflow['clientH'] + 2:
                    mob_errors.append(
                        f'content clipped: scrollHeight={panel_overflow["scrollH"]} > clientHeight={panel_overflow["clientH"]}'
                    )

            # Eye button touch target ≥ 44×44 (min-width/height: 44px in .pass-eye CSS)
            eye_size = await mob_page.evaluate("""
                (function(){
                    var b = document.getElementById('rPassEye');
                    if(!b) return null;
                    var r = b.getBoundingClientRect();
                    return {w: r.width, h: r.height};
                })()
            """)
            if eye_size:
                if eye_size['w'] < 44:
                    mob_errors.append(f'eye button width={eye_size["w"]:.0f}px < 44px')
                if eye_size['h'] < 44:
                    mob_errors.append(f'eye button height={eye_size["h"]:.0f}px < 44px')
            else:
                mob_errors.append('rPassEye not found on mobile')

            # Strength bar visible after password input; re-check panel clipping
            await mob_page.fill('#rPass', 'abc')
            await mob_page.evaluate("document.getElementById('rPass').dispatchEvent(new Event('input'))")
            await mob_page.wait_for_timeout(80)
            bar_display = await mob_page.evaluate(
                "document.getElementById('passStrengthBar').style.display"
            )
            if bar_display == 'none' or bar_display == '':
                mob_errors.append(f'strength bar not visible on mobile (display={bar_display})')

            panel_overflow2 = await mob_page.evaluate("""
                (function(){
                    var p = document.getElementById('registerPanel');
                    if(!p) return null;
                    return {scrollH: p.scrollHeight, clientH: p.clientHeight};
                })()
            """)
            if panel_overflow2 and panel_overflow2['scrollH'] > panel_overflow2['clientH'] + 2:
                mob_errors.append(
                    f'clipped after strength bar: scrollHeight={panel_overflow2["scrollH"]} > clientHeight={panel_overflow2["clientH"]}'
                )

            await mob_ctx.close()

            if mob_errors:
                fail(label, '; '.join(mob_errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        await browser.close()

    print()
    total = PASS_OK + FAIL_OK
    print(f'\033[1m── {PASS_OK} passed, {FAIL_OK} failed, 0 skipped ──\033[0m')
    return FAIL_OK

if __name__ == '__main__':
    print()
    print('\033[1m── Register DS Runtime Tests (A–S, 19 tests) ──\033[0m')
    exit_code = asyncio.run(run())
    sys.exit(exit_code)
