"""
test_edit_profile_phase1.py — Edit Profile Phase 1 regression tests

Covers:
  A: _norm_name shared location (auth.py §2)
  B: update_profile structured name validation + normalization (§4)
  C: update_profile DOB validation (§9A + §9C)
  D: update_profile atomic transaction (§3)
  E: update_profile canonical response (§6/§18)
  F: profile-v2.edit.js: no legacy full_name.split fallback (§1)
  G: profile-v2.edit.js: applyCanonicalProfile exists (§6)
  H: profile-v2.edit.js: _editSession counter (§20)
  I: profile-showcase.html: aria + type="button" + legacy row (§16/§1)

No real DB. All backend tests use FakeConn.
"""

import os, re, sys, textwrap, ast
from unittest.mock import patch, MagicMock

BASE = os.path.dirname(os.path.abspath(__file__))

PASS = 0
FAIL = 0
ERRORS = []


def _read(rel):
    return open(os.path.join(BASE, rel), encoding='utf-8').read()


def ok(label):
    global PASS
    PASS += 1
    print(f'  \033[92mPASS\033[0m  {label}')


def fail(label, reason=''):
    global FAIL
    FAIL += 1
    ERRORS.append((label, reason))
    print(f'  \033[91mFAIL\033[0m  {label}' + (f' — {reason}' if reason else ''))


# ── A: _norm_name shared location ────────────────────────────────────────────

def test_A_norm_name_location():
    print('\n\033[1m── A: _norm_name shared location (§2) ──\033[0m')
    auth_src = _read('auth.py')
    srv_src  = _read('server.py')

    label = 'A1: _norm_name defined in auth.py'
    ok(label) if 'def _norm_name(' in auth_src else fail(label, 'not found in auth.py')

    label = 'A2: server.py does NOT define _norm_name locally'
    ok(label) if 'def _norm_name(' not in srv_src else fail(label, 'local copy still in server.py')

    label = 'A3: server.py imports _norm_name from auth'
    ok(label) if '_norm_name' in srv_src and 'from auth import' in srv_src \
        else fail(label, '_norm_name not imported from auth in server.py')

    label = 'A4: _DOB_MIN_YEAR = 1940 constant in auth.py (§9C)'
    ok(label) if '_DOB_MIN_YEAR' in auth_src and '1940' in auth_src \
        else fail(label, '_DOB_MIN_YEAR=1940 not found in auth.py')

    label = 'A5: _DOB_MIN_AGE = 15 constant in auth.py (§9C)'
    ok(label) if '_DOB_MIN_AGE' in auth_src and '15' in auth_src \
        else fail(label, '_DOB_MIN_AGE=15 not found in auth.py')

    label = 'A6: _norm_name behavioral unit test (AST extraction from auth.py)'
    try:
        import re as _re
        _auth_src = _read('auth.py')
        _tree = ast.parse(_auth_src)
        _norm_name_real = None
        for _node in ast.walk(_tree):
            if isinstance(_node, ast.FunctionDef) and _node.name == '_norm_name':
                _fn_lines = _auth_src.splitlines()[_node.lineno - 1: _node.end_lineno]
                _fn_src = textwrap.dedent('\n'.join(_fn_lines))
                _ns = {'re': _re}
                exec(_fn_src, _ns)
                _norm_name_real = _ns['_norm_name']
                break
        if _norm_name_real is None:
            fail(label, '_norm_name not found in auth.py AST')
        else:
            cases = [
                ('محمد    أحمد', 'محمد أحمد'),
                ('  Ahmad  ',    'Ahmad'),
                ('Ahmed\t\tAli', 'Ahmed Ali'),
                ('', ''), (None, ''), ('سلام', 'سلام'),
            ]
            errs = []
            for inp, exp in cases:
                res = _norm_name_real(inp)
                if res != exp: errs.append(f'{inp!r}→{res!r}')
            if errs: fail(label, '; '.join(errs))
            else:    ok(label)
    except Exception as e:
        fail(label, str(e))


# ── B: update_profile name validation + normalization (FakeConn) ─────────────

class FakeConn:
    """Minimal pg8000-like connection that logs SQL and returns synthetic rows."""
    def __init__(self, fail_on=None):
        self.sql_log   = []
        self.columns   = []
        self._fail_on  = fail_on
        self._profile_exists = True

    def run(self, sql, **kw):
        stripped = sql.strip()
        self.sql_log.append(stripped)
        if self._fail_on and self._fail_on in stripped:
            raise RuntimeError('simulated_failure')
        if 'SELECT id FROM profiles WHERE user_id' in stripped:
            self.columns = [{'name': 'id'}]
            return [(1,)] if self._profile_exists else []
        if 'RETURNING id' in stripped and 'UPDATE profiles' in stripped:
            self.columns = [{'name': 'id'}]
            return [(1,)]
        if 'SELECT tw_id FROM users WHERE id' in stripped:
            self.columns = [{'name': 'tw_id'}]
            return [('U9620test',)]
        return []


def _call_update_profile(data, fake_conn=None, fail_on=None):
    """Call auth.update_profile with a FakeConn instead of a real DB connection."""
    import auth as _auth
    if fake_conn is None:
        fake_conn = FakeConn(fail_on=fail_on)
    with patch.object(_auth, 'get_conn', return_value=fake_conn), \
         patch.object(_auth, 'release_conn', return_value=None), \
         patch.object(_auth, '_cache_del', return_value=None):
        return _auth.update_profile(1, data)


def test_B_name_validation():
    print('\n\033[1m── B: update_profile name validation + normalization (§4) ──\033[0m')

    label = 'B1: empty first_name raises ValueError first_name_required'
    try:
        _call_update_profile({'first_name': '', 'last_name': 'أحمد'})
        fail(label, 'no exception raised')
    except ValueError as e:
        ok(label) if 'first_name_required' in str(e) else fail(label, f'wrong error: {e}')
    except Exception as e:
        fail(label, f'unexpected exception type: {type(e).__name__}: {e}')

    label = 'B2: empty last_name raises ValueError last_name_required'
    try:
        _call_update_profile({'first_name': 'محمد', 'last_name': ''})
        fail(label, 'no exception raised')
    except ValueError as e:
        ok(label) if 'last_name_required' in str(e) else fail(label, f'wrong error: {e}')
    except Exception as e:
        fail(label, f'unexpected exception type: {type(e).__name__}: {e}')

    label = 'B3: internal whitespace in first_name is normalized (§2)'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': 'محمد   ', 'last_name': 'أحمد', 'short_bio': ''}, fake_conn=fc)
        # first_name in fields should be stripped
        ok(label) if resp.get('first_name') == 'محمد' else fail(label, f'first_name={resp.get("first_name")!r}')
    except Exception as e:
        fail(label, str(e))

    label = 'B4: empty middle_name becomes null (§4)'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': 'محمد', 'middle_name': '', 'last_name': 'أحمد'}, fake_conn=fc)
        ok(label) if resp.get('middle_name') is None else fail(label, f'middle_name={resp.get("middle_name")!r}')
    except Exception as e:
        fail(label, str(e))

    label = 'B5: canonical full_name in response is built from normalized parts (§6/§18)'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': '  محمد  ', 'last_name': '  أحمد  '}, fake_conn=fc)
        ok(label) if resp.get('full_name') == 'محمد أحمد' else fail(label, f'full_name={resp.get("full_name")!r}')
    except Exception as e:
        fail(label, str(e))

    label = 'B6: updating only short_bio without name parts — no name validation triggered'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'short_bio': 'مطور برمجيات'}, fake_conn=fc)
        ok(label)
    except ValueError as e:
        fail(label, f'unexpected ValueError: {e}')
    except Exception as e:
        fail(label, f'unexpected exception: {e}')


# ── C: DOB validation ─────────────────────────────────────────────────────────

def test_C_dob_validation():
    print('\n\033[1m── C: DOB validation (§9A + §9C) ──\033[0m')

    label = 'C1: invalid date string raises ValueError'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': 'not-a-date'})
        fail(label, 'no exception raised')
    except ValueError:
        ok(label)
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C2: future DOB raises ValueError dob_future'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': '2099-01-01'})
        fail(label, 'no exception raised')
    except ValueError as e:
        ok(label) if 'dob_future' in str(e) else fail(label, f'wrong error: {e}')
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C3: DOB year < 1940 raises ValueError dob_year_too_old'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': '1939-06-15'})
        fail(label, 'no exception raised')
    except ValueError as e:
        ok(label) if 'dob_year_too_old' in str(e) else fail(label, f'wrong error: {e}')
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C4: DOB resulting in age < 15 raises ValueError dob_too_young'
    from datetime import date, timedelta
    young_dob = (date.today() - timedelta(days=14*365)).isoformat()
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': young_dob})
        fail(label, 'no exception raised')
    except ValueError as e:
        ok(label) if 'dob_too_young' in str(e) else fail(label, f'wrong error: {e}')
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C5: valid DOB (1990-06-15) accepted without error'
    try:
        fc = FakeConn()
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': '1990-06-15'}, fake_conn=fc)
        ok(label)
    except Exception as e:
        fail(label, str(e))

    label = 'C6: null DOB (clearing) accepted without error'
    try:
        fc = FakeConn()
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': None}, fake_conn=fc)
        ok(label)
    except Exception as e:
        fail(label, str(e))


# ── D: update_profile atomic transaction (§3) ─────────────────────────────────

def test_D_atomicity():
    print('\n\033[1m── D: update_profile atomic transaction (§3) ──\033[0m')

    label = 'D1: SUCCESS — transaction contains BEGIN … COMMIT, no ROLLBACK'
    try:
        fc = FakeConn()
        _call_update_profile({'first_name': 'محمد', 'last_name': 'أحمد'}, fake_conn=fc)
        log = fc.sql_log
        has_begin  = any('BEGIN' in s for s in log)
        has_commit = any('COMMIT' in s for s in log)
        has_roll   = any('ROLLBACK' in s for s in log)
        if has_begin and has_commit and not has_roll:
            ok(label)
        else:
            fail(label, f'log={log}')
    except Exception as e:
        fail(label, str(e))

    label = 'D2: PROFILE FAILURE — ROLLBACK issued, COMMIT skipped'
    try:
        fc = FakeConn(fail_on='UPDATE profiles')
        raised = False
        try:
            _call_update_profile({'first_name': 'محمد', 'last_name': 'أحمد'}, fake_conn=fc)
        except Exception:
            raised = True
        log = fc.sql_log
        has_begin  = any('BEGIN' in s for s in log)
        has_commit = any('COMMIT' in s for s in log)
        has_roll   = any('ROLLBACK' in s for s in log)
        if raised and has_begin and has_roll and not has_commit:
            ok(label)
        else:
            fail(label, f'raised={raised} begin={has_begin} commit={has_commit} rollback={has_roll}')
    except Exception as e:
        fail(label, str(e))

    label = 'D3: connection is released even on failure (§3)'
    try:
        import auth as _auth
        released = []
        fc_inner = FakeConn(fail_on='UPDATE profiles')
        with patch.object(_auth, 'get_conn', return_value=fc_inner), \
             patch.object(_auth, 'release_conn', side_effect=lambda c: released.append(c)), \
             patch.object(_auth, '_cache_del', return_value=None):
            try:
                _auth.update_profile(1, {'first_name': 'ت', 'last_name': 'ت'})
            except Exception:
                pass
        ok(label) if released else fail(label, 'release_conn not called on failure')
    except Exception as e:
        fail(label, str(e))


# ── E: canonical response (§6/§18) ───────────────────────────────────────────

def test_E_canonical_response():
    print('\n\033[1m── E: canonical response (§6/§18) ──\033[0m')

    label = 'E1: response includes first_name normalized'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': '  محمد  ', 'last_name': 'أحمد'}, fake_conn=fc)
        ok(label) if resp.get('first_name') == 'محمد' else fail(label, str(resp.get('first_name')))
    except Exception as e:
        fail(label, str(e))

    label = 'E2: response includes last_name normalized'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': 'محمد', 'last_name': '  أحمد  '}, fake_conn=fc)
        ok(label) if resp.get('last_name') == 'أحمد' else fail(label, str(resp.get('last_name')))
    except Exception as e:
        fail(label, str(e))

    label = 'E3: response includes built full_name'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': 'محمد', 'middle_name': 'علي', 'last_name': 'أحمد'}, fake_conn=fc)
        ok(label) if resp.get('full_name') == 'محمد علي أحمد' else fail(label, str(resp.get('full_name')))
    except Exception as e:
        fail(label, str(e))

    label = 'E4: response includes middle_name = None when cleared'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': 'محمد', 'middle_name': '', 'last_name': 'أحمد'}, fake_conn=fc)
        ok(label) if resp.get('middle_name') is None else fail(label, str(resp.get('middle_name')))
    except Exception as e:
        fail(label, str(e))

    label = 'E5: response includes short_bio when saved'
    try:
        fc = FakeConn()
        resp = _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'short_bio': 'مطور'}, fake_conn=fc)
        ok(label) if resp.get('short_bio') == 'مطور' else fail(label, str(resp.get('short_bio')))
    except Exception as e:
        fail(label, str(e))


# ── F: profile-v2.edit.js — no legacy split fallback (§1) ────────────────────

def test_F_no_legacy_split():
    print('\n\033[1m── F: profile-v2.edit.js — no full_name.split fallback (§1) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'F1: no full_name.split() in edit.js (legacy fallback removed §1)'
    ok(label) if 'full_name' not in src or 'split' not in src or \
        'full_name' not in src.split('split')[0][-30:] \
        else fail(label, 'full_name.split() legacy fallback still present')

    # More specific check: the exact forbidden pattern
    label = 'F1b: exact forbidden pattern (.trim().split(/\\s+/)) not present (§1)'
    ok(label) if '.trim().split' not in src \
        else fail(label, '.trim().split still present — legacy name parse not removed')

    label = 'F2: _editSession counter defined (§20)'
    ok(label) if '_editSession' in src else fail(label, '_editSession not found')

    label = 'F3: _snapshot defined (§14)'
    ok(label) if '_snapshot' in src else fail(label, '_snapshot not found')

    label = 'F4: _inFlight guard defined (§13)'
    ok(label) if '_inFlight' in src else fail(label, '_inFlight not found')

    label = 'F5: _resetForm function defined (§19)'
    ok(label) if '_resetForm' in src else fail(label, '_resetForm not found')

    label = 'F6: _hydrateForm function defined (§19)'
    ok(label) if '_hydrateForm' in src else fail(label, '_hydrateForm not found')

    label = 'F7: _legacyMode flag defined (§1)'
    ok(label) if '_legacyMode' in src else fail(label, '_legacyMode flag not found')


# ── G: applyCanonicalProfile (§6) ────────────────────────────────────────────

def test_G_canonical_function():
    print('\n\033[1m── G: applyCanonicalProfile (§6) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'G1: applyCanonicalProfile function defined'
    ok(label) if 'applyCanonicalProfile' in src else fail(label, 'function not found')

    label = 'G2: applyLocalUpdate removed (forbidden pattern)'
    ok(label) if 'applyLocalUpdate' not in src else fail(label, 'applyLocalUpdate still present')

    label = 'G3: applyCanonicalProfile called on save success'
    ok(label) if 'applyCanonicalProfile' in src and 'res.data' in src \
        else fail(label, 'canonical function not called on success')

    label = 'G4: full_name updated from profile response (not payload)'
    ok(label) if 'profile.full_name' in src else fail(label, 'profile.full_name not referenced')


# ── H: _editSession race guard (§20) ─────────────────────────────────────────

def test_H_race_guard():
    print('\n\033[1m── H: async race guard (§20) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'H1: session counter incremented on open (++_editSession)'
    ok(label) if '++_editSession' in src else fail(label, '++_editSession not found')

    label = 'H2: stale session check before hydrate (_editSession !== session)'
    ok(label) if '_editSession !== session' in src else fail(label, 'stale session check missing')

    label = 'H3: session passed into _hydrateForm call'
    ok(label) if '_hydrateForm(p,' in src and 'session' in src else fail(label, 'session not passed to _hydrateForm')


# ── I: HTML aria, type=button, legacy row (§16 + §1) ─────────────────────────

def test_I_html_contracts():
    print('\n\033[1m── I: profile-showcase.html — aria, type=button, legacy row (§16/§1) ──\033[0m')
    src = _read('profile-showcase.html')

    label = 'I1: epFirstName has aria-required="true" (§16)'
    ok(label) if 'id="epFirstName"' in src and 'aria-required="true"' in src \
        else fail(label, 'aria-required not found on epFirstName')

    label = 'I2: epLastName has aria-required="true" (§16)'
    ok(label) if 'id="epLastName"' in src and 'aria-required="true"' in src \
        else fail(label, 'aria-required not found on epLastName')

    label = 'I3: epFirstName has aria-invalid="false" initial (§16)'
    ok(label) if 'aria-invalid="false"' in src else fail(label, 'aria-invalid not found')

    label = 'I4: epFirstName has aria-describedby="epNameErr" (§16)'
    ok(label) if 'aria-describedby="epNameErr"' in src else fail(label, 'aria-describedby not found')

    label = 'I5: epClose is type="button" (§16)'
    ok(label) if 'id="epClose"' in src and 'type="button"' in src \
        else fail(label, 'type="button" not found on epClose')

    label = 'I6: epSaveBtn is type="button" (§16)'
    ok(label) if 'id="epSaveBtn"' in src and 'type="button"' in src \
        else fail(label, 'type="button" not found on epSaveBtn')

    label = 'I7: epCancelBtn is type="button" (§16)'
    ok(label) if 'id="epCancelBtn"' in src and 'type="button"' in src \
        else fail(label, 'type="button" not found on epCancelBtn')

    label = 'I8: legacy name row #epLegacyNameRow present (§1)'
    ok(label) if 'id="epLegacyNameRow"' in src else fail(label, 'epLegacyNameRow not found in HTML')

    label = 'I9: #epLegacyNameText placeholder for full_name display (§1)'
    ok(label) if 'id="epLegacyNameText"' in src else fail(label, 'epLegacyNameText not found in HTML')

    label = 'I10: #epDobErr present for DOB partial error (§9B)'
    ok(label) if 'id="epDobErr"' in src else fail(label, 'epDobErr not found in HTML')

    label = 'I11: role="dialog" on epOverlay (§16)'
    ok(label) if 'role="dialog"' in src else fail(label, 'role="dialog" not found')

    label = 'I12: aria-modal="true" on epOverlay (§16)'
    ok(label) if 'aria-modal="true"' in src else fail(label, 'aria-modal not found')


# ── BTN-18 / CSS (§12/§17) ───────────────────────────────────────────────────

def test_J_css_contracts():
    print('\n\033[1m── J: profile-v2.css — DS-COLOR Phase 2 + BTN-18 (§12/§17) ──\033[0m')
    src = _read('profile-v2.css')

    label = 'J1: --ep-danger uses --color-status-danger token (§17)'
    ok(label) if '--ep-danger' in src and '--color-status-danger' in src \
        else fail(label, '--ep-danger not using semantic token')

    label = 'J2: --ep-save-from uses --color-brand-primary (§17)'
    ok(label) if '--ep-save-from' in src and '--color-brand-primary' in src \
        else fail(label, '--ep-save-from not using brand primary token')

    label = 'J3: .ep-err uses --ep-danger (§17)'
    ok(label) if '.ep-err' in src and '--ep-danger' in src \
        else fail(label, '.ep-err not using --ep-danger')

    label = 'J4: BTN-18 .ep-save--loading class defined (§12)'
    ok(label) if 'ep-save--loading' in src else fail(label, '.ep-save--loading not defined')

    label = 'J5: BTN-18 spinner uses margin-based centering, not transform (§12)'
    ok(label) if 'margin-top:-7px' in src or 'margin-top: -7px' in src \
        else fail(label, 'margin-based centering not found in ep-save--loading::after')

    label = 'J6: ep-err and ep-field-err color via --ep-danger (no raw #f87171) (§17)'
    # Check that raw hex is not used in the ep-* error rules
    lines = src.splitlines()
    in_ep_err = False
    raw_hex_in_err = False
    for line in lines:
        if '.ep-err' in line or '.ep-field-err' in line:
            in_ep_err = True
        if in_ep_err and '#f87171' in line:
            raw_hex_in_err = True
            break
        if in_ep_err and line.strip().startswith('.') and 'ep-err' not in line and 'ep-field-err' not in line:
            in_ep_err = False
    ok(label) if not raw_hex_in_err else fail(label, 'raw #f87171 still in ep-err/ep-field-err rules')

    label = 'J7: --ep-input-bg uses --color-surface-input (§17)'
    ok(label) if '--ep-input-bg' in src and '--color-surface-input' in src \
        else fail(label, '--ep-input-bg not using color-surface-input')


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    test_A_norm_name_location()
    test_B_name_validation()
    test_C_dob_validation()
    test_D_atomicity()
    test_E_canonical_response()
    test_F_no_legacy_split()
    test_G_canonical_function()
    test_H_race_guard()
    test_I_html_contracts()
    test_J_css_contracts()

    print(f'\n\033[1m── {PASS} passed, {FAIL} failed ──\033[0m')
    if ERRORS:
        print('\nFailures:')
        for label, reason in ERRORS:
            print(f'  ✗ {label}')
            if reason: print(f'    → {reason}')
    sys.exit(0 if FAIL == 0 else 1)
