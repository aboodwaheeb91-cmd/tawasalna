"""
DS-INP — Input Value Text Color Stability: targeted regression check (3 assertions).

Verifies that -webkit-text-fill-color is explicitly set in the .field input base
rule so Chromium/WebKit UA cannot override input text color on Focus.

NOT a full test suite.

IMPORTANT: Desktop Playwright does not reproduce Android Chrome UA behavior.
These checks verify the CSS is correctly authored and that computed `color`
does not visibly change on focus in the desktop Chromium context.
Final visual verification requires MANUAL testing on Android Chrome.
"""
import asyncio, sys, os, shutil
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
    global PASS_COUNT, FAIL_COUNT

    print('\n\033[1m── DS-INP Text Color Stability — Regression Check ──\033[0m')

    # ── A + B: Playwright runtime checks ──────────────────────────────────────
    async with async_playwright() as p:
        launch_kwargs = {'args': ['--no-sandbox']}
        if CHROMIUM:
            launch_kwargs['executable_path'] = CHROMIUM
        browser = await p.chromium.launch(**launch_kwargs)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        await page.goto(f'{HOST}/login')
        await page.wait_for_load_state('networkidle')

        # ── A: Login #lEmail — value color stable + placeholder not white ────────
        label = 'A: Login #lEmail — computed color stable in normal and focus'
        try:
            normal_color = await page.evaluate(
                "getComputedStyle(document.getElementById('lEmail')).color"
            )
            await page.click('#lEmail')
            focus_color = await page.evaluate(
                "getComputedStyle(document.getElementById('lEmail')).color"
            )
            await page.evaluate("document.getElementById('lEmail').blur()")

            errors = []
            if not normal_color or 'rgb' not in normal_color:
                errors.append(f'no color value in normal: {normal_color}')
            if normal_color != focus_color:
                errors.append(
                    f'color changed on focus: normal={normal_color}, focus={focus_color}'
                )
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        label = 'A2: Login #lEmail placeholder — webkit-text-fill-color is not #fff (white)'
        try:
            ph_fill = await page.evaluate("""
                (() => {
                    const el = document.getElementById('lEmail');
                    const st = getComputedStyle(el, '::placeholder');
                    return st.getPropertyValue('-webkit-text-fill-color') || st.color;
                })()
            """)
            if ph_fill and ph_fill.strip() in ('rgb(255, 255, 255)', '#fff', '#ffffff', 'white'):
                fail(label, f'placeholder -webkit-text-fill-color is solid white: {ph_fill}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        # ── B: Register #rEmail — value color stable + placeholder not white ──
        label = 'B: Register #rEmail — computed color stable in normal and focus'
        try:
            await page.evaluate("showRegister()")
            await page.evaluate("selectType('emp')")
            await page.wait_for_selector('#registerPanel.open', timeout=3000, state='attached')

            normal_color = await page.evaluate(
                "getComputedStyle(document.getElementById('rEmail')).color"
            )
            await page.click('#rEmail')
            focus_color = await page.evaluate(
                "getComputedStyle(document.getElementById('rEmail')).color"
            )
            await page.evaluate("document.getElementById('rEmail').blur()")

            errors = []
            if not normal_color or 'rgb' not in normal_color:
                errors.append(f'no color value in normal: {normal_color}')
            if normal_color != focus_color:
                errors.append(
                    f'color changed on focus: normal={normal_color}, focus={focus_color}'
                )
            if errors:
                fail(label, '; '.join(errors))
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        label = 'B2: Register #rEmail placeholder — webkit-text-fill-color is not #fff (white)'
        try:
            ph_fill = await page.evaluate("""
                (() => {
                    const el = document.getElementById('rEmail');
                    const st = getComputedStyle(el, '::placeholder');
                    return st.getPropertyValue('-webkit-text-fill-color') || st.color;
                })()
            """)
            if ph_fill and ph_fill.strip() in ('rgb(255, 255, 255)', '#fff', '#ffffff', 'white'):
                fail(label, f'placeholder -webkit-text-fill-color is solid white: {ph_fill}')
            else:
                ok(label)
        except Exception as ex:
            fail(label, str(ex))

        await browser.close()

    # ── C: CSS source check — -webkit-text-fill-color in .field input ─────────
    label = 'C: index.css — -webkit-text-fill-color present in .field input base rule'
    try:
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        field_start = css.find('.field input,')
        if field_start == -1:
            fail(label, '.field input rule not found in index.css')
        else:
            field_end = css.find('}', field_start)
            field_block = css[field_start:field_end]
            if '-webkit-text-fill-color' not in field_block:
                fail(label, '-webkit-text-fill-color missing from .field input block')
            elif 'caret-color' not in field_block:
                fail(label, 'caret-color missing from .field input block')
            else:
                ok(label)
    except Exception as ex:
        fail(label, str(ex))

    # ── D: CSS source check — ::placeholder has -webkit-text-fill-color ────────
    label = 'D: index.css — .field input::placeholder has -webkit-text-fill-color (not solid white)'
    try:
        css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        ph_start = css.find('.field input::placeholder')
        if ph_start == -1:
            fail(label, '.field input::placeholder rule not found in index.css')
        else:
            ph_end = css.find('}', ph_start)
            ph_block = css[ph_start:ph_end]
            if '-webkit-text-fill-color' not in ph_block:
                fail(label, '-webkit-text-fill-color missing from ::placeholder block')
            elif '-webkit-text-fill-color:#fff' in ph_block or '-webkit-text-fill-color: #fff' in ph_block:
                fail(label, '::placeholder -webkit-text-fill-color is solid #fff — regression')
            else:
                ok(label)
    except Exception as ex:
        fail(label, str(ex))

    print(f'\n\033[1m── {PASS_COUNT} passed, {FAIL_COUNT} failed ──\033[0m')
    print('\nNote: Desktop Playwright does not reproduce Android Chrome UA focus behavior.')
    print('      Manual verification on Android Chrome is required after deployment.\n')
    return FAIL_COUNT


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
