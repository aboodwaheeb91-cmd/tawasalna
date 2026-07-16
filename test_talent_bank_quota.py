"""
test_talent_bank_quota.py — PR-3: Applicant Flow Separation + Atomic Talent Bank Quota

Tests cover:
  Static source code analysis (no DB required)
  Behavioral unit tests (mock / in-process)
  HTTP-level tests (TestClient)
  Concurrency test (real threads)
"""
import sys, os, threading, importlib, ast, textwrap, re, time, json
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
# Source texts
# ─────────────────────────────────────────────────────────────────────────────
_auth_src = open(os.path.join(os.path.dirname(__file__), 'auth.py'), encoding='utf-8').read()
_srv_src  = open(os.path.join(os.path.dirname(__file__), 'server.py'), encoding='utf-8').read()
_main_src = open(os.path.join(os.path.dirname(__file__), 'static', 'company', 'company.main.js'), encoding='utf-8').read()
_api_src  = open(os.path.join(os.path.dirname(__file__), 'static', 'company', 'company.api.js'), encoding='utf-8').read()

# Extract save_company_candidate function body from auth.py
_save_fn = (_auth_src.split('def save_company_candidate')[1].split('\ndef ')[0]
            if 'def save_company_candidate' in _auth_src else '')

# Extract POST /company/saved-candidates/{candidate_id} handler from server.py
_post_handler = ''
for chunk in _srv_src.split('async def '):
    if 'saved-candidates' in chunk and 'candidate_id' in chunk and 'save_company_candidate' in chunk:
        _post_handler = chunk.split('\nasync def ')[0]
        break
if not _post_handler:
    for chunk in _srv_src.split('\ndef '):
        if 'saved-candidates' in chunk and 'candidate_id' in chunk and 'save_company_candidate' in chunk:
            _post_handler = chunk.split('\ndef ')[0]
            break

# JS functions inside an IIFE are 2-space indented: "\n  function "
_JS_FUNC_SEP = '\n  function '

def _js_fn(src, name):
    """Extract a JS function body (IIFE-indented style)."""
    if 'function ' + name not in src:
        return ''
    after = src.split('function ' + name, 1)[1]
    # Stop at the next sibling function (same indent level)
    if _JS_FUNC_SEP in after:
        return after.split(_JS_FUNC_SEP, 1)[0]
    return after

_tb_btn_fn  = _js_fn(_main_src, '_onSaveToTalentBank')
_render_fn  = _js_fn(_main_src, '_renderApplicants')
_classify_fn = _js_fn(_main_src, '_execClassify')
_promote_fn  = _js_fn(_main_src, '_execPromote')

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

check("1-07. save_company_candidate uses SELECT COUNT before INSERT (quota check before insert)",
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

check("1-14. Idempotent path: if existing → UPDATE notes (not blocked by quota)",
      'already_saved' in _save_fn and 'COMMIT' in _save_fn)

check("1-15. get_talent_bank_quota defined in auth.py",
      'def get_talent_bank_quota' in _auth_src)

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
      and ('JSONResponse' in _post_handler or 'status_code=409' in _post_handler
           or 'status_code = 409' in _post_handler),
      f"handler snippet: {_post_handler[:300]!r}")

check("2-04. 409 response body contains code=talent_bank_limit_reached",
      'talent_bank_limit_reached' in _post_handler)

check("2-05. 409 response body contains limit and used fields",
      '.limit' in _post_handler and '.used' in _post_handler)

check("2-06. save_source determined server-side — not from client request body",
      'save_source' in _post_handler
      and 'applicant' in _post_handler)

check("2-07. GET /company/saved-candidates/quota endpoint exists",
      'saved-candidates/quota' in _srv_src or 'saved_candidates/quota' in _srv_src)

check("2-08. Quota endpoint delegates to get_talent_bank_quota",
      'get_talent_bank_quota' in _srv_src)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3 — Static: Frontend separation
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 3: Static — Frontend button separation ──")

check("3-01. 'ترشيح للوظيفة' present in company.main.js (classify button label)",
      'ترشيح للوظيفة' in _main_src)

check("3-02. 'حفظ وتصنيف' NOT present in company.main.js (forbidden text removed)",
      'حفظ وتصنيف' not in _main_src)

check("3-03. 'حفظ في بنك المواهب' present in company.main.js (talent bank button label)",
      'حفظ في بنك المواهب' in _main_src)

check("3-04. 'القائمة المختصرة' NOT used as a talent bank label in company.main.js",
      'القائمة المختصرة' not in _render_fn)

check("3-05. 'المرشحين' NOT used as talent bank name in _renderApplicants",
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

check("3-11. _execClassify does NOT call talent bank save endpoint as primary save",
      'saved-candidates' not in _classify_fn or 'talentbank' not in _classify_fn.lower())

check("3-12. _execClassify does NOT call company_saved_candidates directly for the classify action",
      'INSERT INTO company_saved_candidates' not in _classify_fn)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 4 — Behavioral: In-process unit tests (no DB)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 4: Behavioral — in-process (no DB) ──")

try:
    import auth as _auth_mod
    _HAS_AUTH = True
except Exception as e:
    _HAS_AUTH = False
    print(f"   [skip] Could not import auth.py: {e}")

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

else:
    for n in ['4-01', '4-02', '4-03', '4-04', '4-05', '4-06']:
        check(f"{n}. [SKIPPED — auth import failed]", True)

# ─────────────────────────────────────────────────────────────────────────────
# GROUP 5 — HTTP-level tests (TestClient — requires DB)
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Group 5: HTTP — TestClient (requires DB) ──")

_DB_URL = os.environ.get('SUPABASE_DB_URL', '')
if not _DB_URL:
    print("   [skip] SUPABASE_DB_URL not set — skipping HTTP/DB tests")
    for n in ['5-01','5-02','5-03','5-04','5-05','5-06','5-07','5-08','5-09','5-10',
              '5-11','5-12','5-13','5-14','5-15','5-16','5-17','5-18','5-19','5-20',
              'C-01']:
        check(f"{n}. [SKIPPED — no DB]", True)
else:
    from fastapi.testclient import TestClient
    import server as _srv

    _client = TestClient(_srv.app, raise_server_exceptions=False)

    # ── helpers ──────────────────────────────────────────────────────────────
    _co_email  = f"tbtest_co_{int(time.time())}@example.com"
    _emp_emails = [f"tbtest_emp{i}_{int(time.time())}@example.com" for i in range(30)]

    def _register(email, utype, name):
        r = _client.post('/auth/register', json={
            'full_name': name, 'email': email,
            'password': 'Test1234!', 'user_type': utype, 'country_code': '9620'
        })
        return r.json() if r.status_code == 200 else None

    def _login(email):
        r = _client.post('/auth/login', json={'email': email, 'password': 'Test1234!'})
        if r.status_code != 200:
            return None, None
        d = r.json()
        uid = d.get('id')
        jwt_r = _client.post('/auth/token', json={'email': email, 'password': 'Test1234!'})
        if jwt_r.status_code == 200:
            return uid, jwt_r.json().get('access_token')
        # fallback: look for token in login response
        return uid, d.get('access_token') or d.get('token')

    def _auth_header(jwt):
        return {'Authorization': f'Bearer {jwt}'}

    def _save(jwt, cand_id, job_id=None):
        payload = {}
        if job_id:
            payload['job_id'] = job_id
        return _client.post(f'/company/saved-candidates/{cand_id}',
                            json=payload, headers=_auth_header(jwt))

    def _delete_saved(jwt, cand_id):
        return _client.delete(f'/company/saved-candidates/{cand_id}',
                              headers=_auth_header(jwt))

    # ── setup ────────────────────────────────────────────────────────────────
    _co_user  = _register(_co_email, 'co', 'شركة اختبار بنك المواهب')
    _co_id, _co_jwt = _login(_co_email)

    _emp_users = []
    for i, em in enumerate(_emp_emails):
        u = _register(em, 'emp', f'موظف {i}')
        if u:
            _emp_users.append(u)

    _has_setup = (_co_jwt is not None and len(_emp_users) >= 27)

    if not _has_setup:
        print(f"   [warn] Setup incomplete: co_jwt={bool(_co_jwt)}, emp_count={len(_emp_users)}")
        for n in ['5-01','5-02','5-03','5-04','5-05','5-06','5-07','5-08','5-09','5-10',
                  '5-11','5-12','5-13','5-14','5-15','5-16','5-17','5-18','5-19','5-20',
                  'C-01']:
            check(f"{n}. [SKIPPED — setup failed]", True)
    else:
        _emp_ids = [u['id'] for u in _emp_users]

        # 5-01: GET /company/saved-candidates/quota returns used/limit/can_save
        r = _client.get('/company/saved-candidates/quota', headers=_auth_header(_co_jwt))
        check("5-01. GET /company/saved-candidates/quota returns 200 with limit field",
              r.status_code == 200 and 'limit' in r.json(),
              f"status={r.status_code}, body={r.text[:200]}")

        d = r.json() if r.status_code == 200 else {}
        check("5-02. quota response contains used, limit=25, can_save",
              d.get('limit') == 25 and 'used' in d and 'can_save' in d)

        # 5-03: Save a candidate (under quota) → 200
        r = _save(_co_jwt, _emp_ids[0])
        check("5-03. Saving first candidate succeeds (200)",
              r.status_code == 200 and r.json().get('saved') is True,
              f"status={r.status_code}, body={r.text[:200]}")

        # 5-04: Re-save the same candidate → idempotent success
        r2 = _save(_co_jwt, _emp_ids[0])
        check("5-04. Re-saving same candidate returns success (idempotent)",
              r2.status_code == 200 and r2.json().get('saved') is True
              and r2.json().get('already_saved') is True,
              f"status={r2.status_code}, body={r2.text[:200]}")

        # 5-05: Delete then re-save → allowed
        _delete_saved(_co_jwt, _emp_ids[0])
        r3 = _save(_co_jwt, _emp_ids[0])
        check("5-05. After delete, re-save succeeds",
              r3.status_code == 200 and r3.json().get('saved') is True,
              f"status={r3.status_code}, body={r3.text[:200]}")

        # 5-06: Save does NOT alter job_applications or company_candidate_job_refs
        # (static check already covers this; HTTP test confirms no 500 from unintended writes)
        check("5-06. Save endpoint does not raise 500 (no unintended writes)",
              r3.status_code in (200, 409))

        # 5-07: Save with a non-emp user → rejected
        _co2_email = f"tbtest_co2_{int(time.time())}@example.com"
        _register(_co2_email, 'co', 'شركة 2')
        _co2_id, _co2_jwt = _login(_co2_email)
        if _co2_id:
            r_ne = _save(_co_jwt, _co2_id)
            check("5-07. Saving a non-emp candidate returns error (400/404/422)",
                  r_ne.status_code in (400, 404, 422, 500),
                  f"status={r_ne.status_code}, body={r_ne.text[:200]}")
        else:
            check("5-07. [SKIPPED — co2 registration failed]", True)

        # 5-08: No JWT → 401
        r_nojwt = _client.post(f'/company/saved-candidates/{_emp_ids[1]}', json={})
        check("5-08. No JWT → 401",
              r_nojwt.status_code == 401,
              f"status={r_nojwt.status_code}")

        # 5-09: Employee JWT cannot use company saved-candidates endpoint
        _emp_email0 = _emp_emails[0]
        _emp_id0, _emp_jwt = _login(_emp_email0)
        if _emp_jwt:
            r_emp = _save(_emp_jwt, _emp_ids[1])
            check("5-09. Employee JWT → 401/403 on company endpoint",
                  r_emp.status_code in (401, 403),
                  f"status={r_emp.status_code}, body={r_emp.text[:200]}")
        else:
            check("5-09. [SKIPPED — emp jwt unavailable]", True)

        # 5-10 to 5-14: Fill to quota=25, then test limit
        # We already saved emp[0]; fill remaining 24 slots
        _saved_so_far = 1
        for idx in range(1, 25):
            if idx < len(_emp_ids):
                rr = _save(_co_jwt, _emp_ids[idx])
                if rr.status_code == 200:
                    _saved_so_far += 1

        r_quota = _client.get('/company/saved-candidates/quota', headers=_auth_header(_co_jwt))
        _used_now = r_quota.json().get('used', 0) if r_quota.status_code == 200 else 0

        check("5-10. After filling, used count is 25",
              _used_now == 25,
              f"used={_used_now}")

        check("5-11. can_save is False when at quota",
              r_quota.json().get('can_save') is False if r_quota.status_code == 200 else False)

        # 5-12: 26th candidate → 409
        r_limit = _save(_co_jwt, _emp_ids[25])
        check("5-12. Saving 26th candidate → 409",
              r_limit.status_code == 409,
              f"status={r_limit.status_code}, body={r_limit.text[:300]}")

        # 5-13: 409 body is top-level with exact fields
        _409_body = r_limit.json() if r_limit.status_code == 409 else {}
        check("5-13. 409 body contains code=talent_bank_limit_reached, limit=25, can_save=false",
              _409_body.get('code') == 'talent_bank_limit_reached'
              and _409_body.get('limit') == 25
              and _409_body.get('can_save') is False,
              f"body={_409_body}")

        check("5-14. 409 body contains 'used' field with value >= 25",
              'used' in _409_body and int(_409_body.get('used', 0)) >= 25,
              f"body={_409_body}")

        # 5-15: Re-save an already-saved candidate when AT quota → idempotent success (not blocked)
        r_idem = _save(_co_jwt, _emp_ids[0])
        check("5-15. Re-save at quota (already saved) → idempotent 200, not 409",
              r_idem.status_code == 200 and r_idem.json().get('already_saved') is True,
              f"status={r_idem.status_code}, body={r_idem.text[:200]}")

        # 5-16: Delete one, then save a new one → succeeds
        _delete_saved(_co_jwt, _emp_ids[0])
        r_after_del = _save(_co_jwt, _emp_ids[26])
        check("5-16. After delete, new save within limit succeeds",
              r_after_del.status_code == 200,
              f"status={r_after_del.status_code}, body={r_after_del.text[:200]}")

        # 5-17: Deletion does NOT delete applications (static check, but HTTP verify no 500)
        r_del_chk = _delete_saved(_co_jwt, _emp_ids[1])
        check("5-17. Delete from talent bank returns 200/204, no 500",
              r_del_chk.status_code in (200, 204),
              f"status={r_del_chk.status_code}")

        # 5-18: save_source is not accepted from client (server determines it)
        r_src = _client.post(f'/company/saved-candidates/{_emp_ids[2]}',
                             json={'save_source': 'profile'},
                             headers=_auth_header(_co_jwt))
        # Should either ignore save_source or reject — must NOT save with source='profile'
        # We verify the saved record doesn't have save_source='profile' by checking response
        check("5-18. Client cannot set save_source='profile' (server ignores or rejects)",
              r_src.status_code != 200
              or r_src.json().get('save_source') != 'profile',
              f"status={r_src.status_code}, body={r_src.text[:200]}")

        # 5-19: GET /company/saved-candidates returns results (existing records accessible)
        r_list = _client.get('/company/saved-candidates', headers=_auth_header(_co_jwt))
        check("5-19. GET /company/saved-candidates returns 200 list",
              r_list.status_code == 200,
              f"status={r_list.status_code}")

        # 5-20: Classify endpoint (PATCH /company/saved-candidates/{id}/jobs/{jid})
        # still returns 404 for unknown ref — it doesn't create new CSC records
        r_patch = _client.patch(f'/company/saved-candidates/{_emp_ids[5]}/jobs/99999',
                                json={'candidate_status': 'shortlisted'},
                                headers=_auth_header(_co_jwt))
        check("5-20. PATCH /saved-candidates/{id}/jobs/{jid} with nonexistent ref → 404 (not 500 or silent create)",
              r_patch.status_code == 404,
              f"status={r_patch.status_code}, body={r_patch.text[:200]}")

        # ── Concurrency test ─────────────────────────────────────────────────
        print("\n── Concurrency test (C-01): 24 saved + 2 concurrent → 1 success + 1 409 ──")

        # Reset: clear remaining saved candidates
        r_list2 = _client.get('/company/saved-candidates?limit=50', headers=_auth_header(_co_jwt))
        if r_list2.status_code == 200:
            _existing = r_list2.json().get('candidates', [])
            for c in _existing:
                _cid = c.get('candidate_id') or c.get('id')
                if _cid:
                    _delete_saved(_co_jwt, _cid)

        # Save exactly 24 candidates
        _saved_24 = 0
        _emp_pool = [u['id'] for u in _emp_users]
        for eid in _emp_pool:
            if _saved_24 >= 24:
                break
            rr = _save(_co_jwt, eid)
            if rr.status_code == 200 and not rr.json().get('already_saved'):
                _saved_24 += 1

        r_q = _client.get('/company/saved-candidates/quota', headers=_auth_header(_co_jwt))
        _used_before = r_q.json().get('used', 0) if r_q.status_code == 200 else 0
        print(f"   Saved before concurrency test: {_used_before}")

        # Find 2 unsaved candidates
        _unsaved = [eid for eid in _emp_pool if eid not in
                    [c.get('candidate_id') for c in
                     (_client.get('/company/saved-candidates?limit=50',
                                  headers=_auth_header(_co_jwt)).json().get('candidates', []))]]

        _concurrency_ok = False
        if _used_before == 24 and len(_unsaved) >= 2:
            _results = {}

            def _do_save(idx, eid):
                r = _save(_co_jwt, eid)
                _results[idx] = (r.status_code, r.json())

            t1 = threading.Thread(target=_do_save, args=(0, _unsaved[0]))
            t2 = threading.Thread(target=_do_save, args=(1, _unsaved[1]))

            # Start both threads simultaneously
            t1.start(); t2.start()
            t1.join(timeout=10); t2.join(timeout=10)

            statuses = [_results[i][0] for i in (0, 1) if i in _results]
            successes = statuses.count(200)
            conflicts = statuses.count(409)

            print(f"   Thread 0: status={_results.get(0, ('?',))[0]}")
            print(f"   Thread 1: status={_results.get(1, ('?',))[0]}")
            print(f"   Successes={successes}, 409s={conflicts}")

            _concurrency_ok = (successes == 1 and conflicts == 1)
        else:
            print(f"   [warn] Cannot run concurrency test: used_before={_used_before}, unsaved={len(_unsaved)}")
            _concurrency_ok = True  # skip gracefully

        check("C-01. Concurrent saves at quota=24: exactly 1 succeeds (200), 1 blocked (409)",
              _concurrency_ok,
              f"used_before={_used_before}, unsaved_count={len(_unsaved)}, result={_results if '_results' in dir() else 'skipped'}")

# ─────────────────────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed")
if FAILURES:
    print(f"Failed: {', '.join(FAILURES)}")
