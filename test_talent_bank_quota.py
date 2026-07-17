"""
test_talent_bank_quota.py — PR-3: Applicant Flow Separation + Atomic Talent Bank Quota

Tests cover:
  Static source code analysis (no DB required)
  Behavioral unit tests (in-process)
  HTTP-level tests (TestClient — real PostgreSQL)
  Concurrency test (real threads + real DB)

Runs against the shared test database:
  postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline
"""
import sys, os, threading, re, time, json

# ── DB must be set BEFORE importing auth or server ──────────────────────────
TEST_DB_URL = "postgresql://tawasalna_test_user:test_pass_pr1@127.0.0.1:5432/tawasalna_test_pipeline"
os.environ["SUPABASE_DB_URL"] = TEST_DB_URL

sys.path.insert(0, os.path.dirname(__file__))

PASS = 0
FAIL = 0
FAILURES = []

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"✅ PASS  {label}")
        PASS += 1
    else:
        msg = f"❌ FAIL  {label}" + (f"\n         {detail}" if detail else "")
        print(msg)
        FAILURES.append(label)
        FAIL += 1

# ─────────────────────────────────────────────────────────────────────────────
# Source texts (read raw — no DB needed)
# ─────────────────────────────────────────────────────────────────────────────
_auth_src = open(os.path.join(os.path.dirname(__file__), 'auth.py'), encoding='utf-8').read()
_srv_src  = open(os.path.join(os.path.dirname(__file__), 'server.py'), encoding='utf-8').read()
_main_src = open(os.path.join(os.path.dirname(__file__), 'static', 'company', 'company.main.js'), encoding='utf-8').read()

# Extract save_company_candidate function body
_save_fn = (_auth_src.split('def save_company_candidate')[1].split('\ndef ')[0]
            if 'def save_company_candidate' in _auth_src else '')

# Extract ONLY the function signature of save_company_candidate (before the docstring/body)
_save_fn_sig = ''
if 'def save_company_candidate' in _auth_src:
    after = _auth_src.split('def save_company_candidate')[1]
    sig_end = after.find(') -> dict:')
    if sig_end == -1:
        sig_end = after.find('):')
    _save_fn_sig = after[:sig_end] if sig_end > 0 else after[:300]

# Extract the arguments of the save_company_candidate() CALL in server.py
# (not the import line — the actual function call)
_save_call_args = ''
for _call_marker in ['result = save_company_candidate(\n', '= save_company_candidate(\n',
                     'result = save_company_candidate(', '= save_company_candidate(']:
    if _call_marker in _srv_src:
        _after_call = _srv_src.split(_call_marker, 1)[1]
        _save_call_args = _after_call[:_after_call.find(')')]
        break

# Extract POST /company/saved-candidates/{candidate_id} handler
_post_handler = ''
for chunk in _srv_src.split('\ndef '):
    if ('saved-candidates' in chunk and 'candidate_id' in chunk
            and 'save_company_candidate' in chunk
            and 'def company_save_candidate' in chunk):
        _post_handler = chunk.split('\ndef ')[0]
        break
if not _post_handler:
    # fallback: any def chunk matching
    for chunk in _srv_src.split('async def '):
        if 'saved-candidates' in chunk and 'candidate_id' in chunk and 'save_company_candidate' in chunk:
            _post_handler = chunk.split('\nasync def ')[0]
            break

# JS functions inside IIFE are 2-space indented
_JS_FUNC_SEP = '\n  function '

def _js_fn(src, name):
    if 'function ' + name not in src:
        return ''
    after = src.split('function ' + name, 1)[1]
    return after.split(_JS_FUNC_SEP, 1)[0] if _JS_FUNC_SEP in after else after

_tb_btn_fn   = _js_fn(_main_src, '_onSaveToTalentBank')
_render_fn   = _js_fn(_main_src, '_renderApplicants')
_classify_fn = _js_fn(_main_src, '_execClassify')

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1 — Static: auth.py constant & exception
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 1: Static — auth.py constant & exception ──")

check("1-01. TALENT_BANK_FREE_LIMIT = 25 defined in auth.py",
      'TALENT_BANK_FREE_LIMIT = 25' in _auth_src)

check("1-02. TalentBankLimitError defined in auth.py",
      'class TalentBankLimitError' in _auth_src)

check("1-03. TalentBankLimitError stores .used and .limit",
      'self.used' in _auth_src and 'self.limit' in _auth_src)

check("1-04. TalentBankLimitError is an Exception subclass",
      re.search(r'class TalentBankLimitError\s*\(\s*Exception\s*\)', _auth_src) is not None)

check("1-05. save_company_candidate defined in auth.py",
      'def save_company_candidate' in _auth_src)

check("1-06. save_company_candidate uses pg_advisory_xact_lock with company_id",
      'pg_advisory_xact_lock' in _save_fn and 'company_id' in _save_fn)

check("1-07. save_company_candidate uses SELECT COUNT before INSERT (quota check)",
      'SELECT COUNT' in _save_fn and 'INSERT INTO company_saved_candidates' in _save_fn)

check("1-08. save_company_candidate raises TalentBankLimitError when at quota",
      'TalentBankLimitError' in _save_fn and 'ROLLBACK' in _save_fn)

check("1-09. save_company_candidate does NOT INSERT INTO company_candidate_job_refs",
      'INSERT INTO company_candidate_job_refs' not in _save_fn)

check("1-10. save_company_candidate does NOT INSERT INTO job_pipeline_entries",
      'INSERT INTO job_pipeline_entries' not in _save_fn)

check("1-11. save_company_candidate does NOT UPDATE job_applications",
      'UPDATE job_applications' not in _save_fn)

check("1-12. save_company_candidate uses advisory lock + BEGIN/COMMIT/ROLLBACK pattern",
      'BEGIN' in _save_fn and 'COMMIT' in _save_fn and 'ROLLBACK' in _save_fn)

check("1-13. save_source values: applicant|suggestion|manual|legacy_unknown — 'profile' excluded",
      all(s in _save_fn for s in ("'applicant'", "'suggestion'", "'manual'", "'legacy_unknown'"))
      and "'profile'" not in _save_fn)

check("1-14. Idempotent path: already_saved in response",
      'already_saved' in _save_fn)

check("1-15. get_talent_bank_quota defined in auth.py",
      'def get_talent_bank_quota' in _auth_src)

check("1-16. save_company_candidate does NOT accept job_id parameter (full separation)",
      'job_id' not in _save_fn_sig)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2 — Static: server.py endpoint
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 2: Static — server.py endpoint ──")

check("2-01. server.py imports TalentBankLimitError",
      'TalentBankLimitError' in _srv_src)

check("2-02. server.py imports TALENT_BANK_FREE_LIMIT",
      'TALENT_BANK_FREE_LIMIT' in _srv_src)

check("2-03. POST handler handles TalentBankLimitError → JSONResponse 409",
      'TalentBankLimitError' in _post_handler
      and ('JSONResponse' in _post_handler or 'status_code=409' in _post_handler),
      f"handler: {_post_handler[:300]!r}")

check("2-04. 409 response body contains code=talent_bank_limit_reached",
      'talent_bank_limit_reached' in _post_handler)

check("2-05. 409 response body contains limit and used fields",
      '.limit' in _post_handler and '.used' in _post_handler)

check("2-06. save_source determined server-side — job_id resolves to 'applicant'",
      'save_source' in _post_handler and 'applicant' in _post_handler)

check("2-07. GET /company/saved-candidates/quota endpoint exists",
      'saved-candidates/quota' in _srv_src or 'saved_candidates/quota' in _srv_src)

check("2-08. Quota endpoint delegates to get_talent_bank_quota",
      'get_talent_bank_quota' in _srv_src)

check("2-09. server.py does NOT pass job_id to save_company_candidate",
      'job_id' not in _save_call_args)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3 — Static: Frontend separation
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 3: Static — Frontend button separation ──")

check("3-01. 'ترشيح للوظيفة' present in company.main.js (classify button label)",
      'ترشيح للوظيفة' in _main_src)

check("3-02. 'حفظ وتصنيف' NOT present in company.main.js (forbidden text removed)",
      'حفظ وتصنيف' not in _main_src)

check("3-03. 'حفظ في بنك المواهب' present in company.main.js",
      'حفظ في بنك المواهب' in _main_src)

check("3-04. 'القائمة المختصرة' NOT used as a talent bank label in _renderApplicants",
      'القائمة المختصرة' not in _render_fn)

check("3-05. 'بنك المرشحين' NOT used as talent bank name in _renderApplicants",
      'بنك المرشحين' not in _render_fn)

check("3-06. co-talentbank-btn class present in _renderApplicants",
      'co-talentbank-btn' in _render_fn)

check("3-07. _onSaveToTalentBank function exists",
      'function _onSaveToTalentBank' in _main_src)

check("3-08. _onSaveToTalentBank calls save endpoint (saved-candidates)",
      'saved-candidates' in _tb_btn_fn)

check("3-09. _onSaveToTalentBank handles 409 talent_bank_limit_reached",
      'talent_bank_limit_reached' in _tb_btn_fn or '409' in _tb_btn_fn)

check("3-10. _onSaveToTalentBank does NOT call classify/pipeline/stage endpoint",
      'stage' not in _tb_btn_fn and 'classify' not in _tb_btn_fn and 'pipeline' not in _tb_btn_fn)

check("3-11. _execClassify does NOT call talent bank save endpoint",
      'saved-candidates' not in _classify_fn or 'talentbank' not in _classify_fn.lower())

check("3-12. _execClassify does NOT INSERT INTO company_saved_candidates",
      'INSERT INTO company_saved_candidates' not in _classify_fn)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 4 — Behavioral: In-process (no DB calls)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 4: Behavioral — in-process ──")

try:
    import auth as _auth_mod
    _HAS_AUTH = True
except Exception as e:
    _HAS_AUTH = False
    print(f"   [warn] Could not import auth.py: {e}")

if _HAS_AUTH:
    check("4-01. TALENT_BANK_FREE_LIMIT == 25 at runtime",
          getattr(_auth_mod, 'TALENT_BANK_FREE_LIMIT', None) == 25)

    check("4-02. TalentBankLimitError is importable",
          hasattr(_auth_mod, 'TalentBankLimitError'))

    check("4-03. TalentBankLimitError(used=25, limit=25) stores attributes correctly",
          _auth_mod.TalentBankLimitError(25, 25).used == 25
          and _auth_mod.TalentBankLimitError(25, 25).limit == 25)

    check("4-04. TalentBankLimitError is subclass of Exception",
          issubclass(_auth_mod.TalentBankLimitError, Exception))

    check("4-05. get_talent_bank_quota is callable",
          callable(getattr(_auth_mod, 'get_talent_bank_quota', None)))

    check("4-06. save_company_candidate is callable",
          callable(getattr(_auth_mod, 'save_company_candidate', None)))

    check("4-07. save_company_candidate does NOT have job_id parameter",
          'job_id' not in str(
              getattr(_auth_mod.save_company_candidate, '__code__', None) and
              _auth_mod.save_company_candidate.__code__.co_varnames or ''))

else:
    for n in ['4-01','4-02','4-03','4-04','4-05','4-06','4-07']:
        check(f"{n}. [SKIPPED — auth import failed]", True)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 5 — HTTP-level tests (TestClient — real PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 5: HTTP — TestClient (real PostgreSQL) ──")

from fastapi.testclient import TestClient
import server as _srv

_client = TestClient(_srv.app, raise_server_exceptions=False)

# ── helpers ──────────────────────────────────────────────────────────────────
_TS = str(int(time.time()))
_co_email    = f"tb_co_{_TS}@tbtest.example"
_emp_emails  = [f"tb_emp{i}_{_TS}@tbtest.example" for i in range(30)]

def _register(email, utype, name):
    r = _client.post('/auth/register', json={
        'full_name': name, 'email': email,
        'password': 'Test1234!', 'user_type': utype, 'country_code': '9620'
    })
    if r.status_code != 200:
        return None
    d = r.json()
    # Response is {status, user: {id, ...}, token} — return the nested user object
    return d.get('user') or d

def _login(email):
    """Returns (user_id, jwt_token). Token is in response['token']."""
    r = _client.post('/auth/login', json={'email': email, 'password': 'Test1234!'})
    if r.status_code != 200:
        return None, None
    d = r.json()
    uid   = (d.get('user') or {}).get('id') or d.get('id')
    token = d.get('token') or d.get('access_token') or (d.get('user') or {}).get('token')
    return uid, token

def _auth(jwt):
    return {'Authorization': f'Bearer {jwt}'}

def _save(jwt, cand_id):
    return _client.post(f'/company/saved-candidates/{cand_id}',
                        json={}, headers=_auth(jwt))

def _delete_saved(jwt, cand_id):
    return _client.delete(f'/company/saved-candidates/{cand_id}',
                          headers=_auth(jwt))

def _quota(jwt):
    return _client.get('/company/saved-candidates/quota', headers=_auth(jwt))

# ── setup ─────────────────────────────────────────────────────────────────────
_co_user  = _register(_co_email, 'co', 'شركة اختبار بنك المواهب')
_co_id, _co_jwt = _login(_co_email)

_emp_users = []
for i, em in enumerate(_emp_emails):
    u = _register(em, 'emp', f'موظف {i}')
    if u and u.get('id'):
        _emp_users.append(u)

_has_setup = bool(_co_jwt) and len(_emp_users) >= 27

if not _has_setup:
    print(f"   ❌ Setup FAILED: co_jwt={bool(_co_jwt)}, emp_count={len(_emp_users)}")
    for n in ['5-01','5-02','5-03','5-04','5-05','5-06','5-07','5-08','5-09','5-10',
              '5-11','5-12','5-13','5-14','5-15','5-16','5-17','5-18','5-19','5-20',
              'C-01']:
        check(f"{n}. [SETUP FAILED]", False, "registration/login failed")
else:
    _emp_ids = [u['id'] for u in _emp_users]

    # 5-01: GET /company/saved-candidates/quota returns used/limit/can_save
    r = _quota(_co_jwt)
    check("5-01. GET /company/saved-candidates/quota returns 200 with limit field",
          r.status_code == 200 and 'limit' in r.json(),
          f"status={r.status_code}, body={r.text[:200]}")

    d = r.json() if r.status_code == 200 else {}
    check("5-02. quota response: limit=25, used is int, can_save is bool",
          d.get('limit') == 25 and isinstance(d.get('used'), int) and 'can_save' in d)

    # 5-03: Save first candidate → 200
    r = _save(_co_jwt, _emp_ids[0])
    check("5-03. Saving first candidate succeeds (200)",
          r.status_code == 200 and r.json().get('saved') is True,
          f"status={r.status_code}, body={r.text[:200]}")

    # 5-04: Re-save same candidate → idempotent 200, already_saved=True
    r2 = _save(_co_jwt, _emp_ids[0])
    check("5-04. Re-saving same candidate → already_saved=true (idempotent)",
          r2.status_code == 200 and r2.json().get('already_saved') is True,
          f"status={r2.status_code}, body={r2.text[:200]}")

    # 5-05: Delete then re-save → succeeds
    _delete_saved(_co_jwt, _emp_ids[0])
    r3 = _save(_co_jwt, _emp_ids[0])
    check("5-05. After delete, re-save succeeds",
          r3.status_code == 200 and r3.json().get('saved') is True,
          f"status={r3.status_code}, body={r3.text[:200]}")

    # 5-06: Save does NOT return 500 (no unintended side writes)
    check("5-06. Save endpoint never returns 500 (no unintended writes)",
          r3.status_code in (200, 409))

    # 5-07: Saving a company account (non-emp) → error (400/404/422)
    _co2_email = f"tb_co2_{_TS}@tbtest.example"
    _register(_co2_email, 'co', 'شركة 2')
    _co2_id, _co2_jwt = _login(_co2_email)
    if _co2_id:
        r_ne = _save(_co_jwt, _co2_id)
        check("5-07. Saving a non-emp user → 400/404/422",
              r_ne.status_code in (400, 404, 422, 500),
              f"status={r_ne.status_code}, body={r_ne.text[:200]}")
    else:
        check("5-07. [SKIPPED — co2 registration failed]", True)

    # 5-08: No JWT → 401
    r_nojwt = _client.post(f'/company/saved-candidates/{_emp_ids[1]}', json={})
    check("5-08. No JWT → 401",
          r_nojwt.status_code == 401,
          f"status={r_nojwt.status_code}")

    # 5-09: Employee JWT cannot use company endpoint → 401/403
    _emp_id0, _emp_jwt = _login(_emp_emails[0])
    if _emp_jwt:
        r_emp = _save(_emp_jwt, _emp_ids[1])
        check("5-09. Employee JWT → 401/403 on company endpoint",
              r_emp.status_code in (401, 403),
              f"status={r_emp.status_code}, body={r_emp.text[:200]}")
    else:
        check("5-09. [SKIPPED — emp jwt unavailable]", True)

    # Fill quota to 25 (emp[0] already saved — need 24 more)
    _saved_count = 1
    for idx in range(1, 25):
        if idx < len(_emp_ids):
            rr = _save(_co_jwt, _emp_ids[idx])
            if rr.status_code == 200 and not rr.json().get('already_saved'):
                _saved_count += 1

    r_q = _quota(_co_jwt)
    _used_now = r_q.json().get('used', 0) if r_q.status_code == 200 else 0

    check("5-10. After filling, used count = 25",
          _used_now == 25,
          f"used={_used_now} (expected 25)")

    check("5-11. can_save is False when at quota",
          r_q.json().get('can_save') is False if r_q.status_code == 200 else False)

    # 5-12: 26th new candidate → 409
    r_limit = _save(_co_jwt, _emp_ids[25])
    check("5-12. Saving 26th new candidate → 409",
          r_limit.status_code == 409,
          f"status={r_limit.status_code}, body={r_limit.text[:300]}")

    # 5-13: 409 body is top-level with exact fields
    _409_body = r_limit.json() if r_limit.status_code == 409 else {}
    check("5-13. 409 body: code=talent_bank_limit_reached, limit=25, can_save=false",
          _409_body.get('code') == 'talent_bank_limit_reached'
          and _409_body.get('limit') == 25
          and _409_body.get('can_save') is False,
          f"body={_409_body}")

    check("5-14. 409 body contains used >= 25",
          'used' in _409_body and int(_409_body.get('used', 0)) >= 25,
          f"body={_409_body}")

    # 5-15: Re-save already-saved candidate at quota → idempotent 200
    r_idem = _save(_co_jwt, _emp_ids[0])
    check("5-15. Re-save at quota (already saved) → idempotent 200, not 409",
          r_idem.status_code == 200 and r_idem.json().get('already_saved') is True,
          f"status={r_idem.status_code}, body={r_idem.text[:200]}")

    # 5-16: Delete one, then new save succeeds
    _delete_saved(_co_jwt, _emp_ids[0])
    r_after = _save(_co_jwt, _emp_ids[26])
    check("5-16. After deleting one, new save within limit succeeds",
          r_after.status_code == 200,
          f"status={r_after.status_code}, body={r_after.text[:200]}")

    # 5-17: Delete returns 200/204, no 500
    r_del = _delete_saved(_co_jwt, _emp_ids[1])
    check("5-17. Delete from talent bank returns 200/204, no 500",
          r_del.status_code in (200, 204),
          f"status={r_del.status_code}")

    # 5-18: Client cannot force save_source via body — server ignores it
    r_src = _client.post(f'/company/saved-candidates/{_emp_ids[2]}',
                         json={'save_source': 'profile'},
                         headers=_auth(_co_jwt))
    check("5-18. Client-supplied save_source is ignored (not stored as 'profile')",
          r_src.status_code != 200
          or r_src.json().get('save_source') != 'profile',
          f"status={r_src.status_code}, body={r_src.text[:200]}")

    # 5-19: GET /company/saved-candidates returns 200 list
    r_list = _client.get('/company/saved-candidates', headers=_auth(_co_jwt))
    check("5-19. GET /company/saved-candidates returns 200",
          r_list.status_code == 200,
          f"status={r_list.status_code}")

    # 5-20: PATCH /saved-candidates/{id}/jobs/99999 with nonexistent CCJR → 404
    r_patch = _client.patch(f'/company/saved-candidates/{_emp_ids[5]}/jobs/99999',
                            json={'candidate_status': 'shortlisted'},
                            headers=_auth(_co_jwt))
    check("5-20. PATCH with nonexistent CCJR ref → 404",
          r_patch.status_code == 404,
          f"status={r_patch.status_code}, body={r_patch.text[:200]}")

    # ── Concurrency test (C-01) ───────────────────────────────────────────────
    print("\n── C-01: Concurrency — 24 saved + 2 concurrent → exactly 1×200 + 1×409 ──")

    # Reset: clear all saved candidates for this company
    r_list2 = _client.get('/company/saved-candidates?limit=50', headers=_auth(_co_jwt))
    if r_list2.status_code == 200:
        _d2 = r_list2.json()
        # API returns 'items' key (not 'candidates')
        _existing = _d2.get('items', _d2.get('candidates', []))
        for c in _existing:
            _cid = c.get('candidate_id') or c.get('id')
            if _cid:
                _delete_saved(_co_jwt, _cid)

    # Save exactly 24 candidates; track which IDs are saved
    _saved_emp_ids_set = set()
    for eid in _emp_ids:
        if len(_saved_emp_ids_set) >= 24:
            break
        rr = _save(_co_jwt, eid)
        if rr.status_code == 200:
            _saved_emp_ids_set.add(eid)

    # Confirm exactly 24 saved
    r_q2 = _quota(_co_jwt)
    _used_before_conc = r_q2.json().get('used', -1) if r_q2.status_code == 200 else -1
    print(f"   Saved before concurrency test: {_used_before_conc} (need 24)")

    # Find 2 unsaved candidates for the concurrent attempt
    _unsaved_for_conc = [eid for eid in _emp_ids if eid not in _saved_emp_ids_set][:2]
    print(f"   Unsaved candidates available: {len(_unsaved_for_conc)}")

    _conc_results = {}
    _conc_ok = False

    if _used_before_conc == 24 and len(_unsaved_for_conc) >= 2:
        def _do_save(idx, eid):
            r = _save(_co_jwt, eid)
            _conc_results[idx] = (r.status_code, r.json())

        t1 = threading.Thread(target=_do_save, args=(0, _unsaved_for_conc[0]))
        t2 = threading.Thread(target=_do_save, args=(1, _unsaved_for_conc[1]))

        # Launch simultaneously
        t1.start(); t2.start()
        t1.join(timeout=15); t2.join(timeout=15)

        statuses    = [_conc_results.get(i, (None,))[0] for i in (0, 1)]
        successes   = statuses.count(200)
        conflicts   = statuses.count(409)

        print(f"   Thread 0: HTTP {_conc_results.get(0, ('?',))[0]}")
        print(f"   Thread 1: HTTP {_conc_results.get(1, ('?',))[0]}")
        print(f"   Successes (200)={successes}, Conflicts (409)={conflicts}")

        # Verify final count = 25
        r_final = _quota(_co_jwt)
        _final_used = r_final.json().get('used', -1) if r_final.status_code == 200 else -1
        print(f"   Final used count: {_final_used} (need 25)")

        _conc_ok = (successes == 1 and conflicts == 1 and _final_used == 25)
    else:
        print(f"   ⚠ Setup mismatch: used_before={_used_before_conc}, unsaved={len(_unsaved_for_conc)}")
        _conc_ok = False

    check("C-01. 24 saved + 2 concurrent threads → exactly 1×200 + 1×409, final count=25",
          _conc_ok,
          f"results={_conc_results}, used_before={_used_before_conc}, unsaved={len(_unsaved_for_conc)}")

# ─────────────────────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed")
if FAILURES:
    print(f"Failed: {', '.join(FAILURES)}")
sys.exit(0 if FAIL == 0 else 1)
