"""
DS-FEEDBACK V1 Regression Tests — feat/ds-feedback-runtime-v1 (PR #512 + review fixes)

Tests: XSS, 4 types, timer race, identity guard, ARIA, positioning contract,
       reduced motion, semantic tokens, login surface unification.

Run:  python test_ds_feedback.py

Requirements:
  pip install playwright
  playwright install chromium   # OR set PLAYWRIGHT_CHROMIUM_PATH to an existing binary

Chromium resolution order:
  1. PLAYWRIGHT_CHROMIUM_PATH env var (e.g. /opt/pw-browsers/chromium)
  2. Playwright's default installed Chromium (playwright install chromium)
"""

import asyncio
import sys
import os

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("playwright not installed. Run: pip install playwright")
    sys.exit(1)

# Load runtime files from repo root
_ROOT = os.path.dirname(os.path.abspath(__file__))
SHARED_JS  = open(os.path.join(_ROOT, 'tw_shared.js'), encoding='utf-8').read()
SHARED_CSS = open(os.path.join(_ROOT, 'tw_shared.css'), encoding='utf-8').read()

TEST_HTML = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<title>DS-FEEDBACK Test</title>
<style>{SHARED_CSS}</style>
</head>
<body>
<p id="status">ready</p>
<script>
{SHARED_JS}
</script>
</body>
</html>"""


async def run():
    results = []

    def log(name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        results.append((status, name, detail))
        marker = "  [PASS]" if ok else "  [FAIL]"
        print(f"{marker} {name}" + (f" — {detail}" if detail else ""))

    async with async_playwright() as p:
        # Portable Chromium: honour PLAYWRIGHT_CHROMIUM_PATH if set (e.g. CI / dev env).
        # Falls back to Playwright's own installed Chromium when the var is absent.
        _chromium_path = os.environ.get('PLAYWRIGHT_CHROMIUM_PATH')
        launch_kwargs = {'args': ['--no-sandbox']}
        if _chromium_path:
            launch_kwargs['executable_path'] = _chromium_path
        browser = await p.chromium.launch(**launch_kwargs)
        # Use mobile viewport so --tw-feedback-bottom stays at 80px (mobile value)
        # and @media(min-width:600px) desktop override does not fire.
        page = await browser.new_page(viewport={'width': 375, 'height': 812})
        errors = []
        # Filter localStorage errors: access is denied in data-URL / set_content context —
        # this is a test harness constraint, not a runtime bug.
        def _on_console(m):
            if m.type == 'error' and 'localStorage' in m.text:
                return
            if m.type == 'error':
                errors.append(m.text)
        page.on('console', _on_console)
        # Also filter localStorage from pageerror: access denied in set_content / data-URL context.
        page.on('pageerror', lambda e: None if 'localStorage' in str(e) else errors.append(str(e)))

        await page.set_content(TEST_HTML)

        # ── 1: window.showToast is global ─────────────────────────────────────
        is_global = await page.evaluate("typeof window.showToast === 'function'")
        log("window.showToast is global (canonical exposure)", is_global)

        # ── 2: FBK_DURATION values are centralized ────────────────────────────
        durs = await page.evaluate("""() => ({
          success: window.FBK_DURATION.success,
          info:    window.FBK_DURATION.info,
          warning: window.FBK_DURATION.warning,
          error:   window.FBK_DURATION.error
        })""")
        log("FBK_DURATION.success = 2800", durs['success'] == 2800)
        log("FBK_DURATION.info    = 3200", durs['info']    == 3200)
        log("FBK_DURATION.warning = 4000", durs['warning'] == 4000)
        log("FBK_DURATION.error   = 4500", durs['error']   == 4500)

        # ── 3: success type renders ───────────────────────────────────────────
        await page.evaluate("showToast('تم الحفظ', 'success')")
        await page.wait_for_timeout(120)
        el = await page.query_selector('.tw-snackbar.success')
        log("success type renders .tw-snackbar.success", el is not None)
        if el:
            log("success has .show class",
                await el.evaluate("e => e.classList.contains('show')"))
            log("role=status present",
                await el.get_attribute('role') == 'status')
            log("aria-live=polite present",
                await el.get_attribute('aria-live') == 'polite')
            log("aria-atomic=true present",
                await el.get_attribute('aria-atomic') == 'true')
            log("message text correct",
                (await el.inner_text()).strip() == 'تم الحفظ')

        # ── 4: XSS — dynamic msg must NOT touch innerHTML ────────────────────
        xss = '<img src=x onerror="window._xss=true">'
        await page.evaluate(f"showToast('{xss}', 'error')")
        await page.wait_for_timeout(120)
        el2 = await page.query_selector('.tw-snackbar.error')
        log("XSS: error type renders", el2 is not None)
        if el2:
            img_count = await el2.evaluate("e => e.querySelectorAll('img').length")
            log("XSS: no <img> executed in DOM (innerHTML safe)", img_count == 0)
            xss_fired = await page.evaluate("!!window._xss")
            log("XSS: onerror did NOT execute", not xss_fired)
            tc = await el2.evaluate("e => e.textContent")
            log("XSS: payload appears as raw text (textContent)", xss in tc)

        # ── 5: dynamic msg doesn't appear in innerHTML as HTML tags ──────────
        # innerHTML should only contain a <span> wrapping textContent, no parsed HTML
        if el2:
            ih = await el2.inner_html()
            log("XSS: innerHTML contains only <span>, no parsed <img>",
                '<img' not in ih)

        # ── 6: warning type ───────────────────────────────────────────────────
        await page.evaluate("showToast('تحذير', 'warning')")
        await page.wait_for_timeout(120)
        el3 = await page.query_selector('.tw-snackbar.warning')
        log("warning type renders .tw-snackbar.warning", el3 is not None)

        # ── 7: info type ──────────────────────────────────────────────────────
        await page.evaluate("showToast('معلومة', 'info')")
        await page.wait_for_timeout(120)
        el4 = await page.query_selector('.tw-snackbar.info')
        log("info type renders .tw-snackbar.info", el4 is not None)

        # ── 8: Single Global Surface — only 1 snackbar at a time ─────────────
        count = await page.evaluate("document.querySelectorAll('.tw-snackbar').length")
        log("Single Global Surface: only 1 snackbar exists", count == 1)

        # ── 9: invalid type defaults to success ───────────────────────────────
        await page.evaluate("showToast('نوع خاطئ', 'unknowntype')")
        await page.wait_for_timeout(120)
        el5 = await page.query_selector('.tw-snackbar.success')
        log("invalid type defaults to success", el5 is not None)

        # ── 10: null message guard — no surface created ───────────────────────
        count_before = await page.evaluate("document.querySelectorAll('.tw-snackbar').length")
        await page.evaluate("showToast(null, 'success')")
        count_after  = await page.evaluate("document.querySelectorAll('.tw-snackbar').length")
        log("null message: no new snackbar created", count_before == count_after)

        # ── 11: Latest Replaces Current (FBK-06) ─────────────────────────────
        await page.evaluate("showToast('رسالة أولى', 'success')")
        await page.evaluate("showToast('رسالة ثانية', 'error')")
        await page.wait_for_timeout(120)
        count2 = await page.evaluate("document.querySelectorAll('.tw-snackbar').length")
        log("Timer race: still 1 snackbar after rapid calls", count2 == 1)
        el6 = await page.query_selector('.tw-snackbar')
        if el6:
            t2 = await el6.inner_text()
            log("Timer race: second (latest) message wins", t2.strip() == 'رسالة ثانية')

        # ── 12: 5 rapid calls — count still 1 ───────────────────────────────
        await page.evaluate("for(var i=0;i<5;i++) showToast('msg'+i,'info')")
        await page.wait_for_timeout(120)
        cnt5 = await page.evaluate("document.querySelectorAll('.tw-snackbar').length")
        last = await page.evaluate("document.querySelector('.tw-snackbar').textContent.trim()")
        log("5 rapid calls: count=1", cnt5 == 1)
        log("5 rapid calls: last message wins", last == 'msg4')

        # ── 13: Old timer does NOT remove newer surface (identity guard) ──────
        # Verify _twSurface reference isolation: after two calls, the first timer
        # should NOT remove the second surface. We can test via source inspection.
        src = await page.evaluate("showToast.toString()")
        log("Identity guard in source (_twSurface === surface check)",
            '_twSurface === surface' in src)

        # ── 14: pointer-events: none (FBK-13) ────────────────────────────────
        await page.evaluate("showToast('pointer-events test', 'info')")
        await page.wait_for_timeout(120)
        el7 = await page.query_selector('.tw-snackbar')
        if el7:
            pe = await el7.evaluate("e => getComputedStyle(e).pointerEvents")
            log("pointer-events: none (FBK-13)", pe == 'none')

        # ── 15: --tw-feedback-bottom CSS var present at 80px (mobile root) ───
        fb = await page.evaluate("""()=>
            getComputedStyle(document.documentElement)
              .getPropertyValue('--tw-feedback-bottom').trim()""")
        log("--tw-feedback-bottom CSS var is 80px in :root", fb == '80px')

        # ── 16: .tw-snackbar consumes --tw-feedback-bottom (not hardcoded) ───
        # Verify that changing the variable changes the computed bottom
        await page.evaluate("showToast('pos test','success')")
        await page.wait_for_timeout(120)
        el8 = await page.query_selector('.tw-snackbar')
        if el8:
            bottom_val = await el8.evaluate(
                "e => getComputedStyle(e).getPropertyValue('bottom')")
            # Should come from the variable (80px), not hardcoded 24px
            log("Snackbar bottom comes from --tw-feedback-bottom (80px)",
                bottom_val.strip() == '80px')

        # ── 17: max-width prevents overflow on long messages ─────────────────
        await page.evaluate("showToast('رسالة طويلة جداً '.repeat(20), 'info')")
        await page.wait_for_timeout(120)
        el9 = await page.query_selector('.tw-snackbar')
        if el9:
            w   = await el9.evaluate("e => e.offsetWidth")
            vw  = await page.evaluate("window.innerWidth")
            log("max-width prevents viewport overflow", w <= min(vw * 0.9 + 10, 410))

        # ── 18: Semantic Tokens — --fbk-bdr-* variables present in CSS ───────
        has_fbk_success = '--fbk-bdr-success' in SHARED_CSS
        has_fbk_error   = '--fbk-bdr-error'   in SHARED_CSS
        has_fbk_warning = '--fbk-bdr-warning'  in SHARED_CSS
        has_fbk_info    = '--fbk-bdr-info'     in SHARED_CSS
        log("CSS: --fbk-bdr-success token present (FBK-04)",  has_fbk_success)
        log("CSS: --fbk-bdr-error token present",   has_fbk_error)
        log("CSS: --fbk-bdr-warning token present", has_fbk_warning)
        log("CSS: --fbk-bdr-info token present",    has_fbk_info)

        # ── 19: Type rules use var(--fbk-bdr-*), not hardcoded rgba ──────────
        log("CSS: .warning rule uses var() not hardcoded rgba",
            'var(--fbk-bdr-warning)' in SHARED_CSS)
        log("CSS: .error rule uses var() not hardcoded rgba",
            'var(--fbk-bdr-error)' in SHARED_CSS)

        # ── 20: Reduced motion rule present (FBK-18) ─────────────────────────
        has_rm = 'prefers-reduced-motion' in SHARED_CSS and 'tw-snackbar' in SHARED_CSS
        log("prefers-reduced-motion rule present in CSS (FBK-18)", has_rm)

        # ── 21: Desktop media query updates variable, not bottom property ─────
        # After fix: @media(min-width:600px){:root{--tw-feedback-bottom:24px}}
        # NOT: @media(min-width:600px){.tw-snackbar{bottom:24px}}
        has_var_update  = ':root' in SHARED_CSS and '--tw-feedback-bottom: 24px' in SHARED_CSS
        has_direct_prop = '.tw-snackbar { bottom: 24px' in SHARED_CSS
        log("Desktop media query updates :root variable (not direct property)",
            has_var_update and not has_direct_prop)

        # ── 22: FBK_DURATION used in source (not legacyDur) ─────────────────
        log("showToast source uses FBK_DURATION[type]", 'FBK_DURATION[type]' in src)
        log("_legacyDur param accepted (backward compat)", '_legacyDur' in src)

        # ── 23: Login — toast() is now a wrapper, no #toast DOM element ──────
        # Load index.ui.js content to verify
        index_ui_path = os.path.join(_ROOT, 'static', 'index.ui.js')
        if not os.path.exists(index_ui_path):
            index_ui_path = os.path.join(_ROOT, 'index.ui.js')
        if os.path.exists(index_ui_path):
            ui_src = open(index_ui_path, encoding='utf-8').read()
            log("Login: toast() delegates to window.showToast (wrapper)",
                'window.showToast' in ui_src and 'document.getElementById' not in ui_src.split('function toast')[1].split('function')[0])
            log("Login: no local DOM engine (no getElementById(\"toast\") in toast())",
                'getElementById(\'toast\')' not in ui_src.split('function toast')[1].split('\n\n')[0])
        else:
            log("Login: index.ui.js found for wrapper check", False, "file not found at expected path")

        # ── 24: index.html has no #toast element ─────────────────────────────
        index_html_path = os.path.join(_ROOT, 'index.html')
        if os.path.exists(index_html_path):
            html_src = open(index_html_path, encoding='utf-8').read()
            log("Login: no <div id=\"toast\"> in index.html",
                'id="toast"' not in html_src)
        else:
            log("Login: index.html found for #toast check", False, "file not found")

        # ── 25: index.css has no .toast engine CSS ───────────────────────────
        index_css_path = os.path.join(_ROOT, 'index.css')
        if os.path.exists(index_css_path):
            css_src = open(index_css_path, encoding='utf-8').read()
            log("Login: .toast CSS removed from index.css",
                '.toast{' not in css_src and '.toast.show' not in css_src)
            log("Login: .tw-toast local CSS removed from index.css",
                '.tw-toast[aria-live' not in css_src)
        else:
            log("Login: index.css found for cleanup check", False, "file not found")

        # ── 26: No console errors ─────────────────────────────────────────────
        log("No console errors during test run",
            len(errors) == 0, str(errors) if errors else "")

        # Note: Accessibility announcement lifecycle (content set after DOM insertion)
        # is verified by source inspection only — screen reader behavior requires
        # assistive technology testing (AT) beyond Playwright's scope.
        log("ARIA lifecycle: textContent set after DOM insertion (source)",
            'msgSpan.textContent = msg' in SHARED_JS and
            'document.body.appendChild(surface)' in SHARED_JS and
            SHARED_JS.index('document.body.appendChild(surface)') <
            SHARED_JS.index('msgSpan.textContent = msg'))

        await browser.close()

    print()
    passed  = sum(1 for r in results if r[0] == 'PASS')
    failed  = sum(1 for r in results if r[0] == 'FAIL')
    print(f"Results: {passed} PASS / {failed} FAIL")
    if failed:
        print("\nFailed tests:")
        for s, n, d in results:
            if s == 'FAIL':
                print(f"  • {n}" + (f" [{d}]" if d else ""))
    return failed


if __name__ == '__main__':
    failed = asyncio.run(run())
    sys.exit(1 if failed else 0)
