"""
test_company_save_static.py — static twin of test_company_save.py (PR 6.4).

test_company_save.py drives the real company page in Playwright against a live
server (:8000) + a real company account, so CI cannot run it (it is in the
EXCLUDED list of run_tests.sh). This file checks the same 14 behaviours of the
Confirmed Immediate Update save pattern from the source, so CI still catches a
regression. Run: python tests/test_company_save_static.py
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()

MAIN   = read('static/company/company.main.js')
API    = read('static/company/company.api.js')
RENDER = read('static/company/company.render.js')
OPTS   = read('static/shared/tw-options-data.js')
PAGE   = read('company-profile.html')
SERVER = read('server.py')

def fn_body(src, name):
    """Source of `function name(...) { ... }` up to the next sibling function."""
    m = re.search(r'\n(\s*)function ' + re.escape(name) + r'\s*\([^)]*\)\s*\{', src)
    if not m:
        return ''
    nxt = re.compile(r'\n' + m.group(1) + r'(?:function |// ──)').search(src, m.end())
    return src[m.start():nxt.start() if nxt else len(src)]

PASS = FAIL = 0
def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1; print('  PASS: %s' % name)
    else:
        FAIL += 1; print('  FAIL: %s%s' % (name, (' — ' + detail) if detail else ''))

save  = fn_body(MAIN, 'saveEdit')
local = fn_body(MAIN, '_applyCompanyLocalUpdate')
load  = fn_body(API, 'loadData')
_code = lambda src: re.sub(r'//[^\n]*', '', src)   # comments mention «no renderAll»

print('\n[R] Route — the page opens at /u/{tw_id} (F7), /company-profile?id= is a 302')
check('Smart Router injects _companyProfileIdFromRoute into company-profile.html',
      'window._companyProfileIdFromRoute' in SERVER)
check('loadData reads _companyProfileIdFromRoute first (Smart Router)',
      load.find('_companyProfileIdFromRoute') != -1
      and load.find('_companyProfileIdFromRoute') < load.find("get('id')"))
check('company-profile.html loads the company scripts + tw-options-data.js',
      all(s in PAGE for s in ('company.api.js', 'company.render.js', 'company.main.js',
                              'tw-options-data.js')))

print('\n[T01] Required functions exist')
check('saveEdit defined + exported on window', bool(save) and 'window.saveEdit' in MAIN)
check('_applyCompanyLocalUpdate defined + exported on window',
      bool(local) and 'window._applyCompanyLocalUpdate' in MAIN)

print('\n[T02–T08] Save flow — behaviour checked at runtime (PR 4.3c)')
# The order (3 PUTs one after the other), success → closeEdit + button reset, failure →
# modal stays open + part named + button reset + only confirmed parts applied, and the
# double-submit guard run against the real code in tests/test_company_admin_runtime.js.
check('runtime twin exists and extracts saveEdit', 'co-save-edit' in read('tests/test_company_admin_runtime.js')
      and '@vm-extract-begin: co-save-edit' in MAIN)
check('_applyCompanyLocalUpdate writes full_name + bio and re-renders the profile',
      'p.full_name = profilePayload.full_name' in local and 'p.bio' in local
      and 'renderProfile()' in local)
check('save goes through twApi (API Client Rule), never fetch directly',
      'twApi(' in save and 'fetch(' not in _code(save))
check('success path closes via closeEdit() (overlay + its history entry)', 'closeEdit()' in _code(save))
check('returns early when the save button is already disabled',
      'if (saveBtn && saveBtn.disabled) return;' in save)

print('\n[T09] companyState.profile.full_name updated locally')
check('_applyCompanyLocalUpdate writes into companyState.profile',
      'companyState.profile' in local and 'p.full_name' in local)

print('\n[T10] companyState.branches is an array after save')
check('branchesArr is an array assigned to companyState.branches',
      'var branchesArr = [];' in save and 'companyState.branches = branchesArr' in local)

print('\n[T11] openAllBranchesModal still works after save')
check('openAllBranchesModal exported on window (company.render.js)',
      'window.openAllBranchesModal' in RENDER and bool(fn_body(RENDER, 'openAllBranchesModal')))

print('\n[T12] TW.countryFlagEl available (shared tw-options-data.js)')
check('TW.countryFlagEl defined in tw-options-data.js', 'TW.countryFlagEl = function' in OPTS)

print('\n[T13] No full reload during save')
check('save path never calls renderAll / location.reload',
      'renderAll' not in _code(save) and 'location.reload' not in _code(save)
      and 'renderAll' not in _code(local))

print('\n[T14] loadData({silent:true}) skips renderAll')
check('success path syncs with loadData({ silent: true })',
      'loadData({ silent: true })' in save)
check('loadData calls renderAll only inside `if (!silent)`',
      re.search(r'if \(!silent\) \{[^}]*window\.renderAll\(\)', load) is not None)

print('\n' + '=' * 60)
print('Results: %d passed, %d failed out of %d checks' % (PASS, FAIL, PASS + FAIL))
print('=' * 60)
sys.exit(1 if FAIL else 0)
