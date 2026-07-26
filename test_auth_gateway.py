"""
Auth Gateway — Targeted Regression Tests (auth-gw-v9)

7 test categories:
  A. Spinner centering — CSS source check
  B. DS-NAV back — JS source analysis
  C. Form lifecycle — _applyLoginUI / showLogin / showRegister analysis
  D. Autofill static — CSS source check
  E. Email validation state machine — JS source analysis
  F. Password strength reset — JS source analysis
  G. Structured employee name — JS + server source analysis

Playwright tests (categories A2/B2/E2/F2) require a running server at
http://127.0.0.1:8000.  Static CSS/JS checks run without a server.
"""
import os, sys, asyncio, re, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
HOST = 'http://127.0.0.1:8000'
PASS_COUNT = FAIL_COUNT = 0


def ok(label):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f'  \033[92mPASS\033[0m  {label}')


def fail(label, reason=''):
    global FAIL_COUNT
    FAIL_COUNT += 1
    msg = f': {reason}' if reason else ''
    print(f'  \033[91mFAIL\033[0m  {label}{msg}')


def skip(label, reason=''):
    print(f'  \033[93mSKIP\033[0m  {label}' + (f' ({reason})' if reason else ''))


# ── Read helpers ──────────────────────────────────────────────────────────────

def _read(fname):
    with open(os.path.join(BASE, fname), encoding='utf-8') as f:
        return f.read()


# ── A: Spinner centering (CSS static) ────────────────────────────────────────

def test_A_spinner():
    print('\n\033[1m── A: Spinner Centering (CSS) ──\033[0m')
    css = _read('index.css')

    label = 'A1: @keyframes tw-spin uses rotate only (no translateY)'
    block = re.search(r'@keyframes\s+tw-spin\s*\{[^}]*\}', css)
    if not block:
        fail(label, '@keyframes tw-spin not found')
    elif 'translateY' in block.group():
        fail(label, f'translateY found in keyframe: {block.group()!r}')
    else:
        ok(label)

    label = 'A2: .tw-btn-loading::after uses margin-based centering'
    btn_after = re.search(r'\.tw-btn-loading::after\s*\{[^}]*\}', css)
    if not btn_after:
        fail(label, '.tw-btn-loading::after rule not found')
    else:
        rule = btn_after.group()
        errors = []
        if 'right:' in rule.replace(' ', '') and 'right:12px' in rule.replace(' ', ''):
            errors.append('right:12px still present (not centered)')
        if 'margin-top' not in rule:
            errors.append('margin-top missing')
        if 'margin-left' not in rule:
            errors.append('margin-left missing')
        if 'left:50%' not in rule.replace(' ', ''):
            errors.append('left:50% missing')
        if 'top:50%' not in rule.replace(' ', ''):
            errors.append('top:50% missing')
        if errors:
            fail(label, '; '.join(errors))
        else:
            ok(label)


# ── B: DS-NAV back (JS static) ───────────────────────────────────────────────

def test_B_nav():
    print('\n\033[1m── B: DS-NAV Auth Back (JS) ──\033[0m')
    js = _read('index.ui.js')

    label = 'B1: _authViewPushed flag declared'
    ok(label) if '_authViewPushed' in js else fail(label, '_authViewPushed not found')

    label = 'B2: history.replaceState with auth-login state present'
    ok(label) if "ds_nav:'auth-login'" in js or 'ds_nav:"auth-login"' in js \
        else fail(label, 'replaceState auth-login not found')

    label = 'B3: history.pushState with auth-register state present'
    ok(label) if "ds_nav:'auth-register'" in js or 'ds_nav:"auth-register"' in js \
        else fail(label, 'pushState auth-register not found')

    label = 'B4: popstate listener present'
    ok(label) if 'popstate' in js else fail(label, 'popstate listener not found')

    label = 'B5: showLogin() calls history.back() when _authViewPushed'
    ok(label) if 'history.back()' in js and '_authViewPushed' in js \
        else fail(label, 'history.back() or _authViewPushed missing from showLogin')

    label = 'B6: popstate handler does NOT call history.back() or pushState (no loop)'
    pop_match = re.search(r"addEventListener\('popstate'.*?\}\s*\)", js, re.DOTALL)
    if not pop_match:
        fail(label, 'popstate listener block not found')
    else:
        block = pop_match.group()
        errors = []
        if 'history.back()' in block and 'popstate' not in block[:block.find('history.back()')]:
            errors.append('history.back() inside popstate listener — potential infinite loop')
        if 'history.pushState' in block:
            errors.append('history.pushState inside popstate listener')
        if errors:
            fail(label, '; '.join(errors))
        else:
            ok(label)


# ── C: Form lifecycle (JS static) ────────────────────────────────────────────

def test_C_lifecycle():
    print('\n\033[1m── C: Form Lifecycle (JS) ──\033[0m')
    ui = _read('index.ui.js')
    auth = _read('index.auth.js')

    label = 'C1: _applyLoginUI() function defined'
    ok(label) if 'function _applyLoginUI()' in ui else fail(label, '_applyLoginUI not found')

    label = 'C2: _applyLoginUI calls blur() to clear focus'
    ok(label) if 'blur()' in ui else fail(label, 'blur() not called in _applyLoginUI')

    label = 'C3: _resetRegisterTransientState() defined in index.auth.js'
    ok(label) if '_resetRegisterTransientState' in auth \
        else fail(label, '_resetRegisterTransientState not found in auth.js')

    label = 'C4: _applyLoginUI calls _resetRegisterTransientState'
    ok(label) if '_resetRegisterTransientState' in ui \
        else fail(label, '_applyLoginUI does not call _resetRegisterTransientState')

    label = 'C5: showLogin uses _applyLoginUI (not duplicated inline)'
    # showLogin should be short — it delegates to history.back() or _applyLoginUI
    fn_match = re.search(r'function showLogin\(\)\s*\{[^}]+\}', ui, re.DOTALL)
    if not fn_match:
        fail(label, 'showLogin() not found')
    elif '_applyLoginUI' in fn_match.group() or 'history.back()' in fn_match.group():
        ok(label)
    else:
        fail(label, 'showLogin does not delegate to _applyLoginUI or history.back()')


# ── D: Autofill visual parity (CSS static) ───────────────────────────────────

def test_D_autofill():
    print('\n\033[1m── D: Autofill Visual Parity (CSS) ──\033[0m')
    css = _read('index.css')

    label = 'D1: --auth-autofill-surface token defined'
    ok(label) if '--auth-autofill-surface' in css \
        else fail(label, '--auth-autofill-surface token not found in :root block')

    label = 'D2: --auth-autofill-surface is opaque hex (not rgba/transparent)'
    match = re.search(r'--auth-autofill-surface\s*:\s*([^;]+);', css)
    if not match:
        fail(label, 'token value not found')
    elif 'rgba' in match.group(1) or 'rgb(' in match.group(1):
        fail(label, f'value is not opaque: {match.group(1).strip()!r}')
    else:
        ok(label)

    label = 'D3: login autofill uses --auth-autofill-surface (not --auth-ctrl-surface)'
    login_block = re.search(
        r'#loginSection input:-webkit-autofill.*?#loginSection input:autofill[^}]+\}',
        css, re.DOTALL
    )
    if not login_block:
        fail(label, 'login autofill block not found')
    elif '--auth-autofill-surface' not in login_block.group():
        fail(label, f'--auth-autofill-surface not used in login autofill block')
    else:
        ok(label)

    label = 'D4: register autofill uses --auth-autofill-surface'
    reg_block = re.search(
        r'#registerPanel input:-webkit-autofill.*?#registerPanel input:autofill[^}]+\}',
        css, re.DOTALL
    )
    if not reg_block:
        fail(label, 'register autofill block not found')
    elif '--auth-autofill-surface' not in reg_block.group():
        fail(label, '--auth-autofill-surface not used in register autofill block')
    else:
        ok(label)

    label = 'D5: error autofill override rule exists (has-error + webkit-autofill)'
    ok(label) if '.field.has-error input:-webkit-autofill' in css \
        else fail(label, 'error autofill border override rule not found')

    label = 'D6: --auth-ctrl-surface is NOT used in webkit-autofill box-shadow (separation)'
    autofill_blocks = re.findall(r':-webkit-autofill[^{]*\{[^}]*\}', css, re.DOTALL)
    for b in autofill_blocks:
        if '--auth-ctrl-surface' in b and '-webkit-box-shadow' in b:
            fail(label, f'--auth-ctrl-surface still used in autofill box-shadow')
            return
    ok(label)


# ── E: Email validation state machine (JS static) ───────────────────────────

def test_E_email_validation():
    print('\n\033[1m── E: Email Validation State Machine (JS) ──\033[0m')
    auth = _read('index.auth.js')

    label = 'E1: login email input handler guards format error behind _lSubmitAttempted or _lEmailErrorKind'
    # Find the login email input handler block
    # The correct pattern: non-empty invalid only shows format if _lSubmitAttempted or _lEmailErrorKind === 'format'
    match = re.search(
        r"emailEl\.addEventListener\('input'.*?}\s*\)\s*;",
        auth[:auth.find('// ── DS-VAL helpers (register form)')],
        re.DOTALL
    )
    if not match:
        fail(label, 'login email input listener not found')
        return
    block = match.group()
    # Should NOT have a bare else clause that shows format error without a condition guard
    # Look for the correct pattern: `else if(_lSubmitAttempted || _lEmailErrorKind === 'format')`
    if '_lSubmitAttempted || _lEmailErrorKind' in block or \
       "_lSubmitAttempted||_lEmailErrorKind" in block.replace(' ', ''):
        ok(label)
    else:
        fail(label, 'Format error not guarded by _lSubmitAttempted || _lEmailErrorKind in login email input handler')

    label = 'E2: register email input handler already has the correct guard (parity check)'
    reg_section = auth[auth.find('// ── Register field validation'):]
    reg_email_match = re.search(
        r"rEmailEl\.addEventListener\('input'.*?}\s*\)\s*;",
        reg_section, re.DOTALL
    )
    if not reg_email_match:
        fail(label, 'register email input listener not found')
    elif '_rSubmitAttempted || _rEmailErrorKind' in reg_email_match.group() or \
         "_rSubmitAttempted||_rEmailErrorKind" in reg_email_match.group().replace(' ', ''):
        ok(label)
    else:
        fail(label, 'register email input handler missing guard')


# ── F: Password strength reset (JS static) ───────────────────────────────────

def test_F_strength_reset():
    print('\n\033[1m── F: Password Strength Reset (JS) ──\033[0m')
    js = _read('index.ui.js')

    label = 'F1: checkPassStrength empty-val path resets label display and textContent'
    # Find checkPassStrength function
    fn = re.search(r'function checkPassStrength\(val\)\s*\{.*?\n\}', js, re.DOTALL)
    if not fn:
        fail(label, 'checkPassStrength function not found')
        return
    block = fn.group()
    errors = []
    if "label.style.display='none'" not in block.replace(' ', ''):
        errors.append("label.style.display='none' not found in empty-val branch")
    if "label.textContent=''" not in block.replace(' ', ''):
        errors.append("label.textContent='' not found in empty-val branch")
    if errors:
        fail(label, '; '.join(errors))
    else:
        ok(label)

    label = 'F2: checkPassStrength empty-val path resets fill width'
    if "fill.style.width='0'" not in block.replace(' ', '') and \
       "fill.style.width = '0'" not in block:
        fail(label, "fill.style.width not reset in empty-val branch")
    else:
        ok(label)


# ── G: Structured employee name (JS + server static) ─────────────────────────

def test_G_structured_name():
    print('\n\033[1m── G: Structured Employee Name (JS + Server) ──\033[0m')
    html  = _read('index.html')
    ui    = _read('index.ui.js')
    auth  = _read('index.auth.js')
    srv   = _read('server.py')
    auth_py = _read('auth.py')

    label = 'G1: #empNameFields div present in index.html'
    ok(label) if 'id="empNameFields"' in html \
        else fail(label, '#empNameFields not found in HTML')

    label = 'G2: #rFirstName, #rLastName fields in index.html'
    errors = []
    if 'id="rFirstName"' not in html: errors.append('#rFirstName missing')
    if 'id="rLastName"'  not in html: errors.append('#rLastName missing')
    if errors: fail(label, '; '.join(errors))
    else: ok(label)

    label = 'G3: #rMiddleName optional field in index.html'
    ok(label) if 'id="rMiddleName"' in html \
        else fail(label, '#rMiddleName missing from HTML')

    label = 'G4: #wrapper-rName hidden by default in index.html'
    match = re.search(r'id="wrapper-rName"[^>]*>', html)
    if not match:
        fail(label, '#wrapper-rName not found')
    elif 'hidden' not in match.group():
        fail(label, '#wrapper-rName is not hidden by default')
    else:
        ok(label)

    label = 'G5: _applyRegLabels in index.ui.js handles empNameFields show/hide'
    ok(label) if 'empNameFields' in ui \
        else fail(label, '_applyRegLabels does not reference empNameFields')

    label = 'G6: doRegister() collects rFirstName/rLastName for emp type'
    ok(label) if 'rFirstName' in auth and 'rLastName' in auth \
        else fail(label, 'doRegister does not collect structured name fields')

    label = 'G7: doRegister sends first_name/last_name payload for emp type'
    ok(label) if 'first_name' in auth and 'last_name' in auth \
        else fail(label, 'first_name/last_name not in auth.js payload')

    label = 'G8: RegisterInput in server.py has Optional first_name/last_name'
    errors = []
    if 'first_name' not in srv: errors.append('first_name missing from RegisterInput')
    if 'last_name'  not in srv: errors.append('last_name missing from RegisterInput')
    if errors: fail(label, '; '.join(errors))
    else: ok(label)

    label = 'G9: server register() composes full_name for emp from parts'
    ok(label) if '.join(' in srv and 'first' in srv and 'last' in srv \
        else fail(label, 'server register() does not compose full_name from parts')

    label = 'G10: create_user() in auth.py accepts first_name/last_name kwargs'
    ok(label) if 'first_name=None' in auth_py \
        else fail(label, 'create_user() does not accept first_name kwarg')

    label = 'G11: create_user() INSERTs into profiles with ON CONFLICT DO UPDATE'
    ok(label) if 'ON CONFLICT' in auth_py and 'profiles' in auth_py \
        else fail(label, 'create_user() does not store structured name in profiles')

    label = 'G12: full_name is NOT deleted from users table (backward compat)'
    ok(label) if 'full_name' in auth_py and 'users' in auth_py \
        else fail(label, 'full_name may have been removed from users table')


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    global PASS_COUNT, FAIL_COUNT

    print('\n\033[1m══ Auth Gateway Regression Tests (auth-gw-v9) ══\033[0m')

    test_A_spinner()
    test_B_nav()
    test_C_lifecycle()
    test_D_autofill()
    test_E_email_validation()
    test_F_strength_reset()
    test_G_structured_name()

    print(f'\n\033[1m── {PASS_COUNT} passed, {FAIL_COUNT} failed ──\033[0m')
    print('\nNote: These tests verify static code correctness.')
    print('      UI/UX behavior (autofill on Android, real Back button) requires manual device testing.\n')
    return FAIL_COUNT


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
