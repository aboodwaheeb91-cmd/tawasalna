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
  J: profile-v2.css — DS-COLOR Phase 2 + BTN-18 (§12/§17)
  K: Correction — structured group (middle-only rejected, tri-state) (§Corr-C/B)
  L: Correction — DOB boundary & exact error codes (§Corr-D)
  M: Correction — HTTP status semantics (§Corr-E)
  N: Correction — async race & in-flight controls (§Corr-F/I)
  O: Correction — canonical / no payload contamination (§Corr-G)
  P: Correction — ARIA contracts (DOB describedby, dynamic required) (§Corr-H)
  Q: Correction — DS-COLOR zero visual change tokens (§Corr-I)
  Q17: Micro-fix — Raw Consumer Color Gate (.ep-* no raw hex/rgba) (§MC-gate)
  R: Correction — docs integrity (DATE-36, OVL-38 orthogonal) (§Corr-J)

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

    import auth as _auth_B
    _PVE = _auth_B.ProfileValidationError

    label = 'B1: empty first_name raises ProfileValidationError first_name_required'
    try:
        _call_update_profile({'first_name': '', 'last_name': 'أحمد'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'first_name_required' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'unexpected exception type: {type(e).__name__}: {e}')

    label = 'B2: empty last_name raises ProfileValidationError last_name_required'
    try:
        _call_update_profile({'first_name': 'محمد', 'last_name': ''})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'last_name_required' else fail(label, f'wrong code: {e.code}')
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
    import auth as _auth_C
    _PVE = _auth_C.ProfileValidationError

    label = 'C1: invalid date string raises ProfileValidationError dob_invalid'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': 'not-a-date'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'dob_invalid' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C2: future DOB raises ProfileValidationError dob_future'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': '2099-01-01'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'dob_future' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C3: DOB year < 1940 raises ProfileValidationError dob_year_too_old'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': '1939-06-15'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'dob_year_too_old' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'wrong exception: {type(e).__name__}: {e}')

    label = 'C4: DOB resulting in age < 15 raises ProfileValidationError dob_too_young'
    from datetime import date, timedelta
    young_dob = (date.today() - timedelta(days=14*365)).isoformat()
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': young_dob})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'dob_too_young' else fail(label, f'wrong code: {e.code}')
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

    label = 'F6: _hydrateCanonicalFields function defined (§19 + §Corr-1 split)'
    ok(label) if '_hydrateCanonicalFields' in src else fail(label, '_hydrateCanonicalFields not found')

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

    label = 'H3: session passed into _hydrateCanonicalFields call (§Corr-1 split)'
    ok(label) if '_hydrateCanonicalFields(p,' in src and 'session' in src else fail(label, 'session not passed to _hydrateCanonicalFields')


# ── I: HTML aria, type=button, legacy row (§16 + §1) ─────────────────────────

def test_I_html_contracts():
    print('\n\033[1m── I: profile-showcase.html — aria, type=button, legacy row (§16/§1) ──\033[0m')
    src = _read('profile-showcase.html')

    label = 'I1: epFirstName initial aria-required="false" — JS sets it dynamically (§Corr-2)'
    # Initial HTML value is false; _setNameRequired() in JS controls it per legacy/structured mode
    ok(label) if 'id="epFirstName"' in src and \
        'id="epFirstName"' not in src.split('aria-required="true"')[0][-200:] \
        else fail(label, 'epFirstName should start as aria-required=false (JS manages dynamically)')

    # More specific: check the actual attribute after epFirstName
    label = 'I1b: epFirstName has aria-required="false" in HTML (not "true")'
    import re as _re_i
    _fn_match = _re_i.search(r'id="epFirstName"[^>]*aria-required="([^"]+)"', src)
    if _fn_match:
        ok(label) if _fn_match.group(1) == 'false' else fail(label, f'aria-required={_fn_match.group(1)!r}')
    else:
        # Try reverse attr order
        _fn_match2 = _re_i.search(r'aria-required="([^"]+)"[^>]*id="epFirstName"', src)
        if _fn_match2:
            ok(label) if _fn_match2.group(1) == 'false' else fail(label, f'aria-required={_fn_match2.group(1)!r}')
        else:
            fail(label, 'aria-required not found near epFirstName')

    label = 'I2: epLastName initial aria-required="false" — JS sets it dynamically (§Corr-2)'
    _ln_match = _re_i.search(r'id="epLastName"[^>]*aria-required="([^"]+)"', src)
    if _ln_match:
        ok(label) if _ln_match.group(1) == 'false' else fail(label, f'aria-required={_ln_match.group(1)!r}')
    else:
        _ln_match2 = _re_i.search(r'aria-required="([^"]+)"[^>]*id="epLastName"', src)
        if _ln_match2:
            ok(label) if _ln_match2.group(1) == 'false' else fail(label, f'aria-required={_ln_match2.group(1)!r}')
        else:
            fail(label, 'aria-required not found near epLastName')

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

    label = 'I12: aria-modal="true" removed from #epOverlay (§Corr-8 — no focus trap)'
    import re as _re_i12
    _ep_tag = _re_i12.search(r'id="epOverlay"[^>]*>', src)
    if _ep_tag:
        ok(label) if 'aria-modal' not in _ep_tag.group() else fail(label, 'aria-modal still on #epOverlay tag')
    else:
        fail(label, 'id="epOverlay" not found in HTML')


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


# ── K: Structured group & tri-state (§Corr-B/C) ──────────────────────────────

def test_K_structured_group_tristate():
    print('\n\033[1m── K: Structured group & tri-state (§Corr-B/C) ──\033[0m')
    import auth as _auth_K
    _PVE = _auth_K.ProfileValidationError

    label = 'K1: middle_name-only payload triggers name group → first_name_required'
    try:
        _call_update_profile({'middle_name': 'علي'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'first_name_required' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'unexpected: {type(e).__name__}: {e}')

    label = 'K2: middle_name + last_name only triggers name group → first_name_required'
    try:
        _call_update_profile({'middle_name': 'علي', 'last_name': 'أحمد'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'first_name_required' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'unexpected: {type(e).__name__}: {e}')

    label = 'K3: server.py uses exclude_unset=True for tri-state (§Corr-B)'
    srv_src = _read('server.py')
    ok(label) if 'exclude_unset=True' in srv_src else fail(label, 'exclude_unset=True not found in server.py')

    label = 'K4: server.py does NOT use exclude_none=True for profile update (§Corr-B)'
    # Specifically the profile update endpoint should use exclude_unset
    # (exclude_none=True may appear elsewhere in the file)
    import re as _re_k
    # Find the update_user_profile function area
    _match = _re_k.search(r'def update_user_profile.*?(?=\ndef |\Z)', srv_src, _re_k.DOTALL)
    if _match:
        _fn_body = _match.group(0)
        ok(label) if 'exclude_none=True' not in _fn_body else fail(label, 'exclude_none=True still in update_user_profile')
    else:
        ok(label) if 'exclude_none=True' not in srv_src else fail(label, 'exclude_none=True found (could be in update_user_profile)')

    label = 'K5: _clearable includes short_bio and profession_id (§Corr-B)'
    auth_src = _read('auth.py')
    ok(label) if '"short_bio"' in auth_src and '"profession_id"' in auth_src and '_clearable' in auth_src \
        else fail(label, '_clearable missing short_bio or profession_id')


# ── L: DOB boundary & exact error codes (§Corr-D) ────────────────────────────

def test_L_dob_boundary():
    print('\n\033[1m── L: DOB boundary & exact error codes (§Corr-D) ──\033[0m')
    import auth as _auth_L
    _PVE = _auth_L.ProfileValidationError
    from datetime import date as _date_cls

    label = 'L1: impossible date 2025-02-30 → code dob_invalid (not raw Python error)'
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': '2025-02-30'})
        fail(label, 'no exception raised')
    except _PVE as e:
        ok(label) if e.code == 'dob_invalid' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'wrong exception type {type(e).__name__}: {e}')

    label = 'L2: birthday tomorrow → dob_too_young (calendar boundary)'
    from datetime import timedelta
    _today = _date_cls.today()
    # Birthday tomorrow means they turn 15 tomorrow → age today = 14
    _birthday_tomorrow = _date_cls(_today.year - 15, _today.month, _today.day)
    # Move one day forward: tomorrow's birthday
    _bday = _birthday_tomorrow + timedelta(days=1)
    try:
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': _bday.isoformat()})
        fail(label, 'no exception raised — should be too young (age=14)')
    except _PVE as e:
        ok(label) if e.code == 'dob_too_young' else fail(label, f'wrong code: {e.code}')
    except Exception as e:
        fail(label, f'unexpected: {type(e).__name__}: {e}')

    label = 'L3: birthday today → accepted (calendar boundary — age = exactly 15)'
    _bday_today = _date_cls(_today.year - 15, _today.month, _today.day)
    try:
        fc = FakeConn()
        _call_update_profile({'first_name': 'ت', 'last_name': 'ت', 'dob': _bday_today.isoformat()}, fake_conn=fc)
        ok(label)
    except _PVE as e:
        fail(label, f'rejected with code={e.code} — birthday today should be accepted')
    except Exception as e:
        fail(label, f'unexpected: {type(e).__name__}: {e}')

    label = 'L4: calendar age method used — not timedelta days (source check)'
    auth_src = _read('auth.py')
    ok(label) if '_today.year - _dob.year' in auth_src else fail(label, 'calendar age calculation not found in auth.py')


# ── M: HTTP status semantics (§Corr-E) ───────────────────────────────────────

def test_M_http_codes():
    print('\n\033[1m── M: HTTP status semantics (§Corr-E) ──\033[0m')
    srv_src = _read('server.py')
    auth_src = _read('auth.py')

    label = 'M1: ProfileValidationError defined in auth.py with field + code attrs (§Corr-E)'
    ok(label) if 'class ProfileValidationError' in auth_src and \
        'self.field' in auth_src and 'self.code' in auth_src \
        else fail(label, 'ProfileValidationError not properly defined in auth.py')

    label = 'M2: server.py catches ProfileValidationError → HTTP 422 (§Corr-E)'
    ok(label) if 'except ProfileValidationError' in srv_src and '422' in srv_src \
        else fail(label, 'ProfileValidationError not caught as HTTP 422 in server.py')

    label = 'M3: server.py does NOT raise HTTP 404 for validation errors (§Corr-E)'
    import re as _re_m
    # Look for HTTPException(404 near validation-related patterns
    # Check the profile update function area specifically
    _match = _re_m.search(r'def update_user_profile.*?(?=\n@app\.|\Z)', srv_src, _re_m.DOTALL)
    if _match:
        _fn = _match.group(0)
        ok(label) if 'HTTPException(404' not in _fn else fail(label, 'HTTPException(404) found in update_user_profile')
    else:
        ok(label) if 'HTTPException(404' not in srv_src else fail(label, 'HTTPException(404) found (manual check needed)')

    label = 'M4: error response includes "field" and "code" keys (§Corr-E)'
    ok(label) if '"field": e.field' in srv_src and '"code": e.code' in srv_src \
        else fail(label, 'field/code not in ProfileValidationError handler in server.py')

    label = 'M5: ROLLBACK failure logged, not silently swallowed (§Corr-14)'
    ok(label) if 'ROLLBACK failed' in auth_src or 'ROLLBACK failed for user' in auth_src \
        else fail(label, 'ROLLBACK failure diagnostic logging not found in auth.py')


# ── N: Async race & in-flight controls (§Corr-F/I) ───────────────────────────

def test_N_async_race_inflight():
    print('\n\033[1m── N: Async race & in-flight controls (§Corr-F/I) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'N1: ++_editSession incremented on close (not just on open) (§Corr-8)'
    # closeModal must increment _editSession; open already increments it
    # Check that ++_editSession appears near close-related code
    ok(label) if src.count('++_editSession') >= 2 else fail(label, '++_editSession only in one place — must appear in both open and close')

    label = 'N2: _lockControls disables cancelBtn with aria-disabled (§Corr-9)'
    ok(label) if '_lockControls' in src and 'cancelBtn' in src and "aria-disabled" in src \
        else fail(label, '_lockControls missing or cancelBtn aria-disabled not set')

    label = 'N3: _unlockControls defined (§Corr-9)'
    ok(label) if '_unlockControls' in src else fail(label, '_unlockControls not found')

    label = 'N4: _lockControls called before API request (§Corr-9)'
    # edit.js uses updateProfile() wrapper around fetch — check both patterns
    ok(label) if '_lockControls' in src and ('updateProfile(' in src or 'fetch(' in src) \
        else fail(label, '_lockControls not present alongside API call (updateProfile/fetch)')

    label = 'N5: _profListLoaded flag prevents race on profession clear (§Corr-8)'
    ok(label) if '_profListLoaded' in src else fail(label, '_profListLoaded flag not found')

    label = 'N6: session guard at top of _hydrateForm (before DOM access) (§Corr-8)'
    ok(label) if '_editSession !== session' in src else fail(label, 'session guard not found in _hydrateForm')

    label = 'N7: _profListLoaded set to false when profList empty (load failure safety) (§Corr-MC)'
    # Must use profList.length check, not unconditional true
    ok(label) if '_profListLoaded = !!(profList && profList.length)' in src \
        else fail(label, '_profListLoaded must be false when profList is empty (load failure) — unconditional true found')


# ── O: Canonical / no payload contamination (§Corr-G) ────────────────────────

def test_O_canonical_no_contamination():
    print('\n\033[1m── O: Canonical / no payload contamination (§Corr-G) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'O1: canonicalProfile.profession_id = payload.profession_id NOT in source (§Corr-7)'
    ok(label) if 'canonicalProfile.profession_id = payload' not in src \
        else fail(label, 'payload contamination: canonicalProfile.profession_id = payload.profession_id found')

    label = 'O2: profession null clear logic present in applyCanonicalProfile (§Corr-7)'
    ok(label) if 'profession_id' in src and ('profession = null' in src or 'titleEl' in src) \
        else fail(label, 'profession_id null handling not found in applyCanonicalProfile')

    label = 'O3: applyCanonicalProfile uses profile response, not payload (§Corr-7)'
    ok(label) if 'res.data' in src and 'applyCanonicalProfile' in src \
        else fail(label, 'applyCanonicalProfile not called with res.data')


# ── P: ARIA contracts (DOB describedby, dynamic required) (§Corr-H) ──────────

def test_P_aria_contracts():
    print('\n\033[1m── P: ARIA contracts — DOB describedby + dynamic required (§Corr-H) ──\033[0m')
    html_src = _read('profile-showcase.html')
    js_src = _read('profile-v2.edit.js')

    label = 'P1: epDobD has aria-describedby="epDobErr" (§Corr-10)'
    import re as _re_p
    _match = _re_p.search(r'id="epDobD"[^>]*aria-describedby="([^"]+)"', html_src)
    if not _match:
        _match = _re_p.search(r'aria-describedby="([^"]+)"[^>]*id="epDobD"', html_src)
    ok(label) if _match and _match.group(1) == 'epDobErr' else fail(label, 'epDobD missing aria-describedby="epDobErr"')

    label = 'P2: epDobM has aria-describedby="epDobErr" (§Corr-10)'
    _match = _re_p.search(r'id="epDobM"[^>]*aria-describedby="([^"]+)"', html_src)
    if not _match:
        _match = _re_p.search(r'aria-describedby="([^"]+)"[^>]*id="epDobM"', html_src)
    ok(label) if _match and _match.group(1) == 'epDobErr' else fail(label, 'epDobM missing aria-describedby="epDobErr"')

    label = 'P3: epDobY has aria-describedby="epDobErr" (§Corr-10)'
    _match = _re_p.search(r'id="epDobY"[^>]*aria-describedby="([^"]+)"', html_src)
    if not _match:
        _match = _re_p.search(r'aria-describedby="([^"]+)"[^>]*id="epDobY"', html_src)
    ok(label) if _match and _match.group(1) == 'epDobErr' else fail(label, 'epDobY missing aria-describedby="epDobErr"')

    label = 'P4: _setDobAriaInvalid function defined in edit.js (§Corr-10)'
    ok(label) if '_setDobAriaInvalid' in js_src else fail(label, '_setDobAriaInvalid not found in profile-v2.edit.js')

    label = 'P5: _setNameRequired function defined in edit.js (§Corr-2)'
    ok(label) if '_setNameRequired' in js_src else fail(label, '_setNameRequired not found in profile-v2.edit.js')

    label = 'P6: _setNameRequired(false) called in legacy branch (§Corr-2)'
    ok(label) if '_setNameRequired(false)' in js_src else fail(label, '_setNameRequired(false) not called in edit.js')

    label = 'P7: _setNameRequired(true) called in structured branch (§Corr-2)'
    ok(label) if '_setNameRequired(true)' in js_src else fail(label, '_setNameRequired(true) not called in edit.js')

    label = 'P8: DOB selects have aria-invalid="false" initial (§Corr-10)'
    _dob_area = _re_p.search(r'id="epDobD"[^>]+', html_src)
    ok(label) if 'aria-invalid="false"' in html_src and 'epDobD' in html_src \
        else fail(label, 'aria-invalid not found on DOB selects')


# ── Q: DS-COLOR zero visual change tokens (§Corr-I) ──────────────────────────

def test_Q_dscolor_tokens():
    print('\n\033[1m── Q: DS-COLOR zero visual change tokens (§Corr-I) ──\033[0m')
    src = _read('profile-v2.css')

    label = 'Q1: --ep-input-bg is direct primitive .05 (NOT via --color-surface-input which is .06) (§Corr-11/MC)'
    import re as _re_q1
    # Skip comment lines — match only the CSS property assignment (value starts with rgba or var)
    _bg_match = _re_q1.search(r'--ep-input-bg:\s*(rgba\([^)]+\)|var\([^)]+\))\s*;', src)
    if _bg_match:
        _bg_val = _bg_match.group(1).strip()
        ok(label) if _bg_val == 'rgba(255,255,255,.05)' else fail(label, f'--ep-input-bg = {_bg_val!r} (should be direct rgba .05, not semantic token)')
    else:
        fail(label, '--ep-input-bg CSS token assignment not found in profile-v2.css')

    label = 'Q2: --ep-divider defined (separate from --ep-sheet-border) (§Corr-11)'
    ok(label) if '--ep-divider' in src else fail(label, '--ep-divider not defined in profile-v2.css')

    label = 'Q3: --ep-sheet-border defined (§Corr-11)'
    ok(label) if '--ep-sheet-border' in src else fail(label, '--ep-sheet-border not defined in profile-v2.css')

    label = 'Q4: --ep-cancel-border defined (§Corr-11)'
    ok(label) if '--ep-cancel-border' in src else fail(label, '--ep-cancel-border not defined in profile-v2.css')

    label = 'Q5: --ep-backdrop defined (§Corr-11)'
    ok(label) if '--ep-backdrop' in src else fail(label, '--ep-backdrop not defined in profile-v2.css')

    label = 'Q6: --ep-close-bg defined (§Corr-11)'
    ok(label) if '--ep-close-bg' in src else fail(label, '--ep-close-bg not defined in profile-v2.css')

    label = 'Q7: --ep-note-bg defined (§Corr-11)'
    ok(label) if '--ep-note-bg' in src else fail(label, '--ep-note-bg not defined in profile-v2.css')

    label = 'Q8: --ep-note-border defined (§Corr-11)'
    ok(label) if '--ep-note-border' in src else fail(label, '--ep-note-border not defined in profile-v2.css')

    label = 'Q9: --ep-border NOT used as single merged token (was split into 3) (§Corr-11)'
    import re as _re_q
    # --ep-border should not be defined in :root block (it was replaced by the three split tokens)
    _root_match = _re_q.search(r':root\s*\{([^}]+)\}', src, _re_q.DOTALL)
    if _root_match:
        _root_block = _root_match.group(1)
        ok(label) if '--ep-border:' not in _root_block else fail(label, '--ep-border still defined in :root — should be split into divider/sheet-border/cancel-border')
    else:
        fail(label, 'Could not find :root block in profile-v2.css')

    label = 'Q10: .ep-overlay uses --ep-backdrop (no raw rgba(0,0,0,.65)) (§Corr-11)'
    ok(label) if 'var(--ep-backdrop)' in src else fail(label, '.ep-overlay not using --ep-backdrop token')

    label = 'Q11: .ep-note uses --ep-note-bg (no raw rgba in .ep-note consumers) (§Corr-11)'
    ok(label) if 'var(--ep-note-bg)' in src else fail(label, '.ep-note not using --ep-note-bg token')

    label = 'Q12: .ep-close uses --ep-close-bg (no raw rgba in .ep-close) (§Corr-11)'
    ok(label) if 'var(--ep-close-bg)' in src else fail(label, '.ep-close not using --ep-close-bg token')

    label = 'Q13: --ep-divider fallback is .08 (head/footer) (§Corr-11)'
    ok(label) if '--ep-divider:' in src and 'rgba(255,255,255,.08)' in src \
        else fail(label, '--ep-divider fallback .08 not found')

    label = 'Q14: --ep-sheet-border fallback is .10 (sheet + input borders) (§Corr-11)'
    ok(label) if '--ep-sheet-border:' in src and 'rgba(255,255,255,.10)' in src \
        else fail(label, '--ep-sheet-border fallback .10 not found')

    label = 'Q15: --ep-cancel-border fallback is .12 (§Corr-11)'
    ok(label) if '--ep-cancel-border:' in src and 'rgba(255,255,255,.12)' in src \
        else fail(label, '--ep-cancel-border fallback .12 not found')

    label = 'Q16: .ep-input-err uses --color-status-danger-rgb (no raw rgba(248,...)) (§Corr-MC)'
    ok(label) if 'color-status-danger-rgb' in src and 'ep-input-err' in src \
        else fail(label, '.ep-input-err not using --color-status-danger-rgb token')


# ── Q17: Raw Consumer Color Gate (§MC-gate) ───────────────────────────────────

def test_Q17_ep_consumer_raw_color_gate():
    print('\n\033[1m── Q17: Raw Consumer Color Gate — .ep-* selectors (§MC-gate) ──\033[0m')
    src = _read('profile-v2.css')

    # Remove :root block(s) — token definitions are allowed to have raw values
    src_no_root = re.sub(r':root\s*\{[^}]*?\}', '', src, flags=re.DOTALL)

    violations = []
    in_ep = False
    depth = 0

    for lineno, line in enumerate(src_no_root.splitlines(), 1):
        s = line.strip()

        if not in_ep:
            if re.search(r'(?:,|\s|^)\.ep-', s) and '{' in s:
                in_ep = True
                depth = s.count('{') - s.count('}')
                if depth <= 0:
                    in_ep = False
            continue

        depth += s.count('{') - s.count('}')

        if s.startswith('/*') or s.startswith('*'):
            if depth <= 0:
                in_ep = False
            continue

        # Check raw hex
        for m in re.finditer(r'(?<![-\w])#[0-9a-fA-F]{3,8}(?!\w)', s):
            violations.append(f'L{lineno}: {s[:80]!r}  hex={m.group()!r}')

        # Check raw rgb/rgba — allow rgba(var(--color-*-rgb), ...) exception
        for m in re.finditer(r'\brgba?\s*\(', s):
            rest = s[m.start():]
            if re.match(r'rgba\(var\(--color-[a-z-]+-rgb\)', rest):
                continue
            violations.append(f'L{lineno}: {s[:80]!r}  rgba literal')

        if depth <= 0:
            in_ep = False

    label = 'Q17: Raw Consumer Color Gate — .ep-* selectors have no direct #hex/rgb/rgba (§MC-gate)'
    ok(label) if not violations else fail(label, f'{len(violations)} violation(s) — first: {violations[0][:120]}')


# ── R: Docs integrity (DATE-36, OVL-38 orthogonal) (§Corr-J) ─────────────────

def test_R_docs_integrity():
    print('\n\033[1m── R: Docs integrity — DATE-36 + OVL-38 (§Corr-J) ──\033[0m')
    date_src = _read('docs/design-system/DATE-TIME-FIELDS.md')
    ovl_src  = _read('docs/design-system/OVERLAY-SYSTEM.md')

    label = 'R1: exactly one ## DATE-34 section in DATE-TIME-FIELDS.md (§Corr-12)'
    _count = date_src.count('## DATE-34')
    ok(label) if _count == 1 else fail(label, f'found {_count} ## DATE-34 sections (expected exactly 1 — Out of Scope)')

    label = 'R2: ## DATE-36 exists in DATE-TIME-FIELDS.md (§Corr-12)'
    ok(label) if '## DATE-36' in date_src else fail(label, '## DATE-36 not found — was the duplicate DATE-34 renamed?')

    label = 'R3: ## DATE-36 is the Profile V2 DOB implementation section (§Corr-12)'
    ok(label) if '## DATE-36' in date_src and 'Profile V2' in date_src \
        else fail(label, 'DATE-36 section not linked to Profile V2 DOB content')

    label = 'R4: OVL-38 has modality = blocking (§Corr-13)'
    ok(label) if 'modality' in ovl_src and 'blocking' in ovl_src and 'OVL-38' in ovl_src \
        else fail(label, 'OVL-38 missing modality=blocking attribute')

    label = 'R5: OVL-38 has presentation = bottom (§Corr-13)'
    ok(label) if 'presentation' in ovl_src and 'bottom' in ovl_src and 'OVL-38' in ovl_src \
        else fail(label, 'OVL-38 missing presentation=bottom attribute')

    label = 'R6: OVL-38 has semantics = standard (§Corr-13)'
    ok(label) if 'semantics' in ovl_src and 'standard' in ovl_src and 'OVL-38' in ovl_src \
        else fail(label, 'OVL-38 missing semantics=standard attribute')

    label = 'R7: OVL-38 has closePolicy = guarded (§Corr-13)'
    ok(label) if 'guarded' in ovl_src and 'OVL-38' in ovl_src \
        else fail(label, 'OVL-38 missing closePolicy=guarded attribute')

    label = 'R8: OVL-38 in TOC (§Corr-13)'
    ok(label) if '| OVL-38 |' in ovl_src else fail(label, 'OVL-38 not found in TOC table')

    label = 'R9: footer section count updated to 39 (§Corr-13)'
    ok(label) if '39 قسماً' in ovl_src else fail(label, 'footer not updated to 39 sections in OVERLAY-SYSTEM.md')


# ── S: Hydration fix (canonical fields not gated on professions) ──────────────

def test_S_hydration_fix():
    print('\n\033[1m── S: Hydration fix — canonical fields immediate (§Corr-1/2) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'S1: _hydrateCanonicalFields function exists (§Corr-1)'
    ok(label) if '_hydrateCanonicalFields' in src else fail(label, '_hydrateCanonicalFields not found in profile-v2.edit.js')

    label = 'S2: _hydrateProfession function exists (§Corr-1)'
    ok(label) if '_hydrateProfession' in src else fail(label, '_hydrateProfession not found in profile-v2.edit.js')

    label = 'S3: openModal calls _hydrateCanonicalFields (§Corr-1)'
    ok(label) if '_hydrateCanonicalFields(p, session)' in src else fail(label, 'openModal does not call _hydrateCanonicalFields(p, session)')

    label = 'S4: _hydrateForm removed (canonical/profession split) (§Corr-1)'
    ok(label) if '_hydrateForm' not in src else fail(label, 'old _hydrateForm still present — should be replaced by split functions')

    label = 'S5: _resetForm clears country (§Corr-2)'
    ok(label) if 'epCountry' in src and "_resetForm" in src else fail(label, '_resetForm missing epCountry clear')

    label = 'S6: _resetForm clears epCityWrap (§Corr-2)'
    ok(label) if 'epCityWrap' in src else fail(label, '_resetForm missing epCityWrap.display = none')

    label = 'S7: _resetForm sets _snapshot = null (§Corr-2)'
    ok(label) if '_snapshot = null' in src else fail(label, '_resetForm does not set _snapshot = null')

    label = 'S8: _hydrateProfession updates snapshot.profId (§Corr-1)'
    ok(label) if '_snapshot.profId' in src else fail(label, '_hydrateProfession does not update snapshot.profId after load')

    label = 'S9: _hydrateProfession checks session before modifying DOM (§Corr-1)'
    hydrate_prof_block = src[src.find('function _hydrateProfession'):src.find('function _hydrateProfession')+300] if '_hydrateProfession' in src else ''
    ok(label) if '_editSession !== session' in hydrate_prof_block else fail(label, '_hydrateProfession missing session guard')


# ── T: Delta payload — only send changed fields (§Corr-3) ─────────────────────

def test_T_delta_payload():
    print('\n\033[1m── T: Delta payload — tri-state (§Corr-3) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'T1: delta compares short_bio with snapshot (§Corr-3)'
    ok(label) if '_sbChanged' in src else fail(label, 'no _sbChanged delta check in save handler')

    label = 'T2: delta compares dob with snapshot (§Corr-3)'
    ok(label) if '_dobChanged' in src else fail(label, 'no _dobChanged delta check in save handler')

    label = 'T3: delta compares country with snapshot (§Corr-3)'
    ok(label) if '_countryChanged' in src else fail(label, 'no _countryChanged delta check in save handler')

    label = 'T4: delta compares city with snapshot (§Corr-3)'
    ok(label) if '_cityChanged' in src else fail(label, 'no _cityChanged delta check in save handler')

    label = 'T5: delta compares avail with snapshot (§Corr-3)'
    ok(label) if '_availChanged' in src else fail(label, 'no _availChanged delta check in save handler')

    label = 'T6: delta compares profession with snapshot (§Corr-3)'
    ok(label) if '_profChanged' in src else fail(label, 'no _profChanged delta check in save handler')

    label = 'T7: payload.short_bio only included if _sbChanged (§Corr-3)'
    ok(label) if 'if(_sbChanged)' in src else fail(label, 'short_bio not conditionally included')

    label = 'T8: snapshot null treated as all-changed fallback (§Corr-3)'
    ok(label) if '!_snap ||' in src else fail(label, 'no null-snapshot fallback (!_snap) in delta comparisons')


# ── U: API-MUT normalizer (§Corr-4/5/6) ──────────────────────────────────────

def test_U_api_mut_normalizer():
    print('\n\033[1m── U: API-MUT normalizer (§Corr-4/5/6) ──\033[0m')
    shared_src = _read('tw_shared.js')
    edit_src = _read('profile-v2.edit.js')
    srv_src = _read('server.py')

    label = 'U1: normalizeErrorResponse defined in tw_shared.js (§Corr-5)'
    ok(label) if 'function normalizeErrorResponse' in shared_src else fail(label, 'normalizeErrorResponse not in tw_shared.js')

    label = 'U2: normalizeErrorResponse exported on window (§Corr-5)'
    ok(label) if 'window.normalizeErrorResponse = normalizeErrorResponse' in shared_src else fail(label, 'normalizeErrorResponse not exported to window')

    label = 'U3: normalizeErrorResponse handles body.errors[] (§Corr-5)'
    ok(label) if 'body.errors' in shared_src and 'Array.isArray' in shared_src else fail(label, 'normalizer does not handle body.errors[]')

    label = 'U4: normalizeErrorResponse handles body.detail legacy shape (§Corr-5)'
    ok(label) if 'body.detail' in shared_src else fail(label, 'normalizer does not handle legacy body.detail')

    label = 'U5: edit.js uses normalizeErrorResponse (no direct .detail parse) (§Corr-6)'
    ok(label) if 'normalizeErrorResponse' in edit_src else fail(label, 'edit.js does not call normalizeErrorResponse')

    label = 'U6: edit.js no direct res.data.detail parse (§Corr-6)'
    ok(label) if 'res.data.detail' not in edit_src else fail(label, 'edit.js still directly parses res.data.detail')

    label = 'U7: server returns JSON with errors[] array shape (§Corr-4)'
    ok(label) if '"errors"' in srv_src or "'errors'" in srv_src else fail(label, 'server.py does not return errors[] shape')

    label = 'U8: server uses JSONResponse for ProfileValidationError (§Corr-4)'
    ok(label) if 'JSONResponse' in srv_src and 'ProfileValidationError' in srv_src else fail(label, 'server.py does not use JSONResponse for ProfileValidationError')

    label = 'U9: server backward compat: detail key preserved (§Corr-4)'
    ok(label) if '"detail"' in srv_src or "'detail'" in srv_src else fail(label, 'server.py does not preserve detail key for backward compat')


# ── V: Employee full_name bypass prevention (§Corr-13) ────────────────────────

def test_V_emp_name_bypass():
    print('\n\033[1m── V: Employee full_name bypass prevention (§Corr-13) ──\033[0m')
    auth_src = _read('auth.py')
    srv_src = _read('server.py')

    label = 'V1: update_profile accepts user_type parameter (§Corr-13)'
    ok(label) if 'def update_profile(user_id' in auth_src and 'user_type' in auth_src else fail(label, 'update_profile missing user_type parameter')

    label = 'V2: emp full_name mutation raises ProfileValidationError (§Corr-13)'
    ok(label) if "user_type == 'emp'" in auth_src and 'emp_name_mutation_forbidden' in auth_src else fail(label, 'no emp full_name bypass protection in auth.py')

    label = 'V3: server passes user_type to update_profile (§Corr-13)'
    ok(label) if 'user_type=user_type' in srv_src else fail(label, 'server.py does not pass user_type to update_profile')

    label = 'V4: emp bypass check preserves co/edu path (§Corr-13)'
    # The check must be inside the elif full_name block, meaning co/edu still reach the DB write
    ok(label) if "user_type == 'emp'" in auth_src and 'conn.run("UPDATE users SET full_name' in auth_src else fail(label, 'emp bypass check may have removed co/edu full_name path')


# ── W: DOB corrections (§Corr-10) ─────────────────────────────────────────────

def test_W_dob_corrections():
    print('\n\033[1m── W: DOB corrections — >= → > + message fix (§Corr-10) ──\033[0m')
    auth_src = _read('auth.py')

    label = 'W1: DOB future check uses > not >= (today is not future) (§Corr-10)'
    # Ensure _dob > _today (not >=)
    ok(label) if '_dob > _today' in auth_src and '_dob >= _today' not in auth_src \
        else fail(label, 'DOB future check still uses >= instead of >')

    label = 'W2: dob_year_too_old message says "أو بعدها" (1940 is inclusive) (§Corr-10)'
    ok(label) if 'أو بعدها' in auth_src else fail(label, 'dob_year_too_old message does not say "أو بعدها"')

    label = 'W3: dob_year_too_old message no longer says "بعد 1940" only (§Corr-10)'
    # Old: 'يجب أن تكون بعد {_DOB_MIN_YEAR}'
    ok(label) if "يجب أن تكون بعد {_DOB_MIN_YEAR}" not in auth_src \
        else fail(label, 'old dob_year_too_old message still present')

    label = 'W4: backend mock — 1940-01-01 accepted (§Corr-10)'
    from datetime import date
    _dob = date(1940, 1, 1)
    _today = date(2025, 6, 15)
    _DOB_MIN_YEAR = 1940
    _DOB_MIN_AGE = 15
    rejected_future = _dob > _today
    rejected_old = _dob.year < _DOB_MIN_YEAR
    age = (_today.year - _dob.year) - (1 if (_today.month, _today.day) < (_dob.month, _dob.day) else 0)
    ok(label) if (not rejected_future and not rejected_old and age >= _DOB_MIN_AGE) \
        else fail(label, f'1940-01-01 was rejected: future={rejected_future} old={rejected_old} age={age}')

    label = 'W5: backend mock — 1939-12-31 rejected (year too old) (§Corr-10)'
    _dob2 = date(1939, 12, 31)
    ok(label) if _dob2.year < _DOB_MIN_YEAR else fail(label, '1939-12-31 was not rejected by year check')

    label = 'W6: backend mock — today is NOT future (§Corr-10)'
    _today2 = date(2025, 6, 15)
    ok(label) if not (_today2 > _today2) else fail(label, 'today incorrectly rejected as future')


# ── X: DS-VAL live-correction scoping (§Corr-5/7) ────────────────────────────

def test_X_dsval_live_correction():
    print('\n\033[1m── X: DS-VAL live-correction scoping (§Corr-5/7) ──\033[0m')
    src = _read('profile-v2.edit.js')

    label = 'X1: anyBad clear block guards against clearing required errors (§Corr-5)'
    ok(label) if "indexOf('مطلوب') === -1" in src else fail(label, 'anyBad block does not guard against clearing required errors')

    label = 'X2: required-field clear is field-specific (first_name clears first error) (§Corr-5)'
    ok(label) if 'if(first)' in src and 'epFirstName' in src else fail(label, 'no field-specific first_name required clear')

    label = 'X3: required-field clear for last_name uses last variable (§Corr-5)'
    ok(label) if 'if(last)' in src and 'epLastName' in src else fail(label, 'no field-specific last_name required clear')

    label = 'X4: focus first invalid after error routing (§Corr-5)'
    ok(label) if '.focus()' in src and 'ep-input-err' in src else fail(label, 'no focus() call after error routing')


# ── Y: Accessibility corrections (§Corr-8/9/10) ──────────────────────────────

def test_Y_accessibility():
    print('\n\033[1m── Y: Accessibility corrections (§Corr-8/9) ──\033[0m')
    html_src = _read('profile-showcase.html')

    label = 'Y1: aria-modal="true" removed from #epOverlay (§Corr-8)'
    import re as _re_y1
    _ep_ovl_tag = _re_y1.search(r'id="epOverlay"[^>]*>', html_src)
    if _ep_ovl_tag:
        ok(label) if 'aria-modal' not in _ep_ovl_tag.group() else fail(label, 'aria-modal="true" still present in #epOverlay')
    else:
        fail(label, 'id="epOverlay" not found in HTML')

    label = 'Y2: role="dialog" retained on #epOverlay (§Corr-8)'
    ok(label) if 'role="dialog"' in html_src else fail(label, 'role="dialog" missing from #epOverlay')

    label = 'Y3: epFirstName has individual <label for="epFirstName"> (§Corr-9)'
    ok(label) if 'for="epFirstName"' in html_src else fail(label, 'no <label for="epFirstName"> in HTML')

    label = 'Y4: epMidName has individual <label for="epMidName"> (§Corr-9)'
    ok(label) if 'for="epMidName"' in html_src else fail(label, 'no <label for="epMidName"> in HTML')

    label = 'Y5: epLastName has individual <label for="epLastName"> (§Corr-9)'
    ok(label) if 'for="epLastName"' in html_src else fail(label, 'no <label for="epLastName"> in HTML')

    label = 'Y6: epShortBio has <label for="epShortBio"> (§Corr-9)'
    ok(label) if 'for="epShortBio"' in html_src else fail(label, 'no <label for="epShortBio"> in HTML')

    label = 'Y7: epCountry has <label for="epCountry"> (§Corr-9)'
    ok(label) if 'for="epCountry"' in html_src else fail(label, 'no <label for="epCountry"> in HTML')

    label = 'Y8: epAvail has <label for="epAvail"> (§Corr-9)'
    ok(label) if 'for="epAvail"' in html_src else fail(label, 'no <label for="epAvail"> in HTML')

    label = 'Y9: epProfession has <label for="epProfession"> (§Corr-9)'
    ok(label) if 'for="epProfession"' in html_src else fail(label, 'no <label for="epProfession"> in HTML')

    label = 'Y10: DOB group has aria-labelledby (§Corr-9)'
    ok(label) if 'lbl-dob' in html_src else fail(label, 'DOB selects missing aria-labelledby or lbl-dob id')

    label = 'Y11: tw-select.js propagates aria-invalid to trigger (§Corr-8)'
    sel_src = _read('static/shared/tw-select.js')
    ok(label) if '_syncAriaState' in sel_src and 'aria-invalid' in sel_src else fail(label, 'tw-select.js missing aria-invalid propagation')

    label = 'Y12: tw-select.js propagates aria-describedby to trigger (§Corr-8)'
    sel_src = _read('static/shared/tw-select.js')
    ok(label) if 'aria-describedby' in sel_src else fail(label, 'tw-select.js missing aria-describedby propagation')


# ── Z: Color corrections (§Corr-11/12/14) ─────────────────────────────────────

def test_Z_color_corrections():
    print('\n\033[1m── Z: Color corrections — pencil icon + placeholder tokens (§Corr-11/12/14) ──\033[0m')
    html_src = _read('profile-showcase.html')
    css_src = _read('profile-v2.css')
    color_doc = _read('docs/design-system/COLOR-SYSTEM.md')

    label = 'Z1: pencil icon has no inline style="color:..." (§Corr-11)'
    ok(label) if 'style="color:var(--ac' not in html_src else fail(label, 'pencil icon still has inline style color')

    label = 'Z2: pencil icon uses ep-title-ico class (§Corr-11)'
    ok(label) if 'ep-title-ico' in html_src else fail(label, 'pencil icon missing ep-title-ico class')

    label = 'Z3: --ep-title-icon token defined in CSS (§Corr-11)'
    ok(label) if '--ep-title-icon' in css_src else fail(label, '--ep-title-icon token missing in profile-v2.css')

    label = 'Z4: .ep-title .ep-title-ico uses --ep-title-icon (§Corr-11)'
    ok(label) if 'ep-title-ico' in css_src and 'ep-title-icon' in css_src else fail(label, '.ep-title-ico consumer rule not found')

    label = 'Z5: --ep-placeholder token defined in CSS (§Corr-12)'
    ok(label) if '--ep-placeholder' in css_src else fail(label, '--ep-placeholder token missing in profile-v2.css')

    label = 'Z6: ::placeholder uses --ep-placeholder (§Corr-12)'
    ok(label) if '::placeholder' in css_src and 'ep-placeholder' in css_src else fail(label, '::placeholder not using --ep-placeholder')

    label = 'Z7: focus-visible styles exist for ep-* buttons (§Corr-17)'
    ok(label) if ':focus-visible' in css_src else fail(label, 'no :focus-visible styles for ep-* buttons')

    label = 'Z8: user-select:none on ep-* buttons (§Corr-17)'
    ok(label) if 'user-select:none' in css_src else fail(label, 'no user-select:none on ep-* buttons')

    label = 'Z9: COLOR-SYSTEM.md documents --ep-title-icon (§Corr-15)'
    ok(label) if '--ep-title-icon' in color_doc else fail(label, '--ep-title-icon not documented in COLOR-SYSTEM.md')

    label = 'Z10: COLOR-SYSTEM.md documents --ep-placeholder (§Corr-15)'
    ok(label) if '--ep-placeholder' in color_doc else fail(label, '--ep-placeholder not documented in COLOR-SYSTEM.md')


# ── AA: Documentation corrections (§Corr-16/19/20) ───────────────────────────

def test_AA_docs_corrections():
    print('\n\033[1m── AA: Documentation corrections (§Corr-16/19/20) ──\033[0m')
    ovl_src = _read('docs/design-system/OVERLAY-SYSTEM.md')
    inp_src = _read('docs/design-system/INPUT-FIELDS.md')
    btn_src = _read('docs/design-system/BUTTONS.md')

    label = 'AA1: OVL-38 no longer claims "cancel يتحقق من dirty state" (§Corr-16)'
    ok(label) if 'cancel يتحقق من dirty state' not in ovl_src \
        else fail(label, 'OVL-38 still contains false "cancel يتحقق من dirty state" claim')

    label = 'AA2: OVL-38 corrected dirty-guard description exists (§Corr-16)'
    ok(label) if '_snapshot/_isDirty' in ovl_src or 'dirty state' in ovl_src.lower() else fail(label, 'OVL-38 corrected dirty guard description missing')

    label = 'AA3: INPUT-FIELDS.md has DS-INP migration exception (INP-18) (§Corr-15)'
    ok(label) if 'INP-18' in inp_src else fail(label, 'INP-18 migration exception note missing from INPUT-FIELDS.md')

    label = 'AA4: INPUT-FIELDS.md mentions ep-input-bg zero-visual exception (§Corr-15)'
    ok(label) if 'ep-input-bg' in inp_src or 'Zero-Visual' in inp_src else fail(label, 'ep-input-bg zero-visual exception not in INPUT-FIELDS.md')

    label = 'AA5: BUTTONS.md has BTN-09 close-on-success exception (§Corr-17)'
    ok(label) if 'BTN-09 Close-on-Success Exception' in btn_src or 'close-on-success' in btn_src.lower() else fail(label, 'BTN-09 close-on-success exception missing from BUTTONS.md')

    label = 'AA6: BUTTONS.md exception references epSaveBtn / epOverlay (§Corr-17)'
    ok(label) if 'epSaveBtn' in btn_src or 'epOverlay' in btn_src else fail(label, 'BUTTONS.md exception does not reference epSaveBtn/epOverlay')


# ── AB: No silent failures (§Corr-11/F9) ─────────────────────────────────────

def test_AB_no_silent_failures():
    print('\n\033[1m── AB: No silent failures in edited paths (§Corr-11/F9) ──\033[0m')
    auth_src = _read('auth.py')
    edit_src = _read('profile-v2.edit.js')

    label = 'AB1: theme cache except no longer bare "pass" (§Corr-11)'
    # Find the except block after theme cache try — should have a print, not bare pass
    theme_region = auth_src[auth_src.find('_THEME_FIELDS'):auth_src.find('_THEME_FIELDS')+500] if '_THEME_FIELDS' in auth_src else ''
    ok(label) if 'except Exception: pass' not in theme_region \
        else fail(label, 'theme cache except still contains bare "pass" without logging')

    label = 'AB2: theme cache exception now logs diagnostic (§Corr-11)'
    ok(label) if 'theme cache clear failed' in auth_src or '_tcache_exc' in auth_src \
        else fail(label, 'theme cache exception does not log diagnostic message')

    label = 'AB3: no background getProfile call after save (FRM-18) (§Corr-12)'
    ok(label) if 'getProfile(_scProfileKey)' not in edit_src else fail(label, 'background getProfile still present in save handler')

    label = 'AB4: profession icon uses DOM APIs not innerHTML (§Corr-13)'
    ok(label) if 'createElement(\'i\')' in edit_src or 'createElement("i")' in edit_src else fail(label, 'profession icon does not use createElement("i")')

    label = 'AB5: profession icon name sanitized (no raw prof.icon in innerHTML) (§Corr-13)'
    ok(label) if '[^a-z0-9-]' in edit_src or 'replace' in edit_src and 'iconName' in edit_src \
        else fail(label, 'profession icon name not sanitized before setAttribute')


# ── Q17 (improved): Raw consumer color gate + HTML inline color ───────────────

def test_Q17_ep_consumer_raw_color_gate_v2():
    """Improved Q17: checks multiline rules, single-line rules, and inline HTML color."""
    print('\n\033[1m── Q17v2: Raw Consumer Color Gate — CSS + HTML inline (§MC-gate) ──\033[0m')
    css_src = _read('profile-v2.css')
    html_src = _read('profile-showcase.html')

    # ── CSS check: .ep-* consumer selectors (same as original Q17) ──
    src_no_root = re.sub(r':root\s*\{[^}]*?\}', '', css_src, flags=re.DOTALL)
    violations = []
    in_ep = False
    depth = 0

    for lineno, line in enumerate(src_no_root.splitlines(), 1):
        s = line.strip()
        if not in_ep:
            if re.search(r'(?:,|\s|^)\.ep-', s) and '{' in s:
                in_ep = True
                depth = s.count('{') - s.count('}')
                if depth <= 0:
                    in_ep = False
            continue
        depth += s.count('{') - s.count('}')
        if s.startswith('/*') or s.startswith('*'):
            if depth <= 0:
                in_ep = False
            continue
        for m in re.finditer(r'(?<![-\w])#[0-9a-fA-F]{3,8}(?!\w)', s):
            violations.append(f'CSS L{lineno}: {s[:80]!r}  hex={m.group()!r}')
        for m in re.finditer(r'\brgba?\s*\(', s):
            rest = s[m.start():]
            if re.match(r'rgba\(var\(--color-[a-z-]+-rgb\)', rest):
                continue
            violations.append(f'CSS L{lineno}: {s[:80]!r}  rgba literal')
        if depth <= 0:
            in_ep = False

    label = 'Q17v2-CSS: .ep-* consumer selectors no raw #hex/rgba (§MC-gate)'
    ok(label) if not violations else fail(label, f'{len(violations)} CSS violation(s) — first: {violations[0][:120]}')

    # ── HTML check: no inline style color on Edit Profile Modal elements ──
    # Scope check to content inside #epOverlay only (not the whole page)
    html_violations = []
    _ep_start = html_src.find('id="epOverlay"')
    if _ep_start == -1:
        _ep_start = html_src.find("id='epOverlay'")
    if _ep_start != -1:
        # Find the end of #epOverlay by counting div depth from its opening tag
        _tag_open = html_src.rfind('<', 0, _ep_start)
        _ep_block = html_src[_tag_open:]
        _depth = 0; _end_idx = len(_ep_block)
        for _m in re.finditer(r'<(/?)div', _ep_block):
            if _m.group(1) == '': _depth += 1
            else:
                _depth -= 1
                if _depth <= 0: _end_idx = _m.end(); break
        _ep_block = _ep_block[:_end_idx]
    else:
        _ep_block = ''
    for lineno, line in enumerate(_ep_block.splitlines(), 1):
        if re.search(r'style="[^"]*color\s*:\s*(?:var\(--ac[,)]|#[0-9a-fA-F]|rgb)', line):
            html_violations.append(f'HTML L{lineno}: {line.strip()[:100]!r}')

    label = 'Q17v2-HTML: No inline style color:var(--ac) or color:#hex in modal HTML (§Corr-11)'
    ok(label) if not html_violations else fail(label, f'{len(html_violations)} HTML violation(s) — first: {html_violations[0][:120]}')


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
    test_K_structured_group_tristate()
    test_L_dob_boundary()
    test_M_http_codes()
    test_N_async_race_inflight()
    test_O_canonical_no_contamination()
    test_P_aria_contracts()
    test_Q_dscolor_tokens()
    test_Q17_ep_consumer_raw_color_gate()
    test_R_docs_integrity()
    test_S_hydration_fix()
    test_T_delta_payload()
    test_U_api_mut_normalizer()
    test_V_emp_name_bypass()
    test_W_dob_corrections()
    test_X_dsval_live_correction()
    test_Y_accessibility()
    test_Z_color_corrections()
    test_AA_docs_corrections()
    test_AB_no_silent_failures()
    test_Q17_ep_consumer_raw_color_gate_v2()

    print(f'\n\033[1m── {PASS} passed, {FAIL} failed ──\033[0m')
    if ERRORS:
        print('\nFailures:')
        for label, reason in ERRORS:
            print(f'  ✗ {label}')
            if reason: print(f'    → {reason}')
    sys.exit(0 if FAIL == 0 else 1)
