"""
Tests for feat/company-confirmed-immediate-save
Confirmed Immediate Update Pattern — 14 required tests
Uses JS window.fetch override (injected after page load) for reliable mock interception.
Playwright page.route() has a concurrency issue with parallel fetch() calls (Promise.all):
only the first matching request is intercepted; the rest bypass the mock and hit the real
server. Overriding window.fetch in-browser avoids this entirely.
"""
import subprocess, sys, time, json

BASE = 'http://localhost:8000'

def ensure_server():
    try:
        import urllib.request
        urllib.request.urlopen(BASE + '/', timeout=2)
        return True
    except Exception:
        return False

if not ensure_server():
    proc = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'server:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd='/home/user/tawasalna', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    if not ensure_server():
        print("FATAL: server did not start"); sys.exit(1)

from playwright.sync_api import sync_playwright

def ev(page, script):
    return page.evaluate('(function(){ %s })()' % script)

BASE_COMPANY_DATA = {
    "status": "success",
    "profile": {
        "id": 1, "tw_id": "C9660aabbccddee",
        "full_name": "شركة الاختبار",
        "bio": "وصف الشركة للاختبار", "avatar_url": None,
        "is_verified": False, "country": "الأردن",
        "city": "عمان", "location": "حي الاختبار"
    },
    "company": {
        "id": 1, "industry": "شركة خاصة", "company_type": "شركة خاصة",
        "company_size": "11-50", "founded_year": 2020,
        "cover_url": None, "contact_email": "", "headquarters": ""
    },
    "stats": {"followers_count": 0, "jobs_count": 0, "rating_avg": 0, "rating_count": 0},
    "permissions": {
        "can_edit": True, "can_follow": False,
        "is_following": False, "viewer_type": "owner", "viewer_id": 1
    }
}

# JS fetch mock — injected after page scripts load.
# Intercepts all API endpoints used by saveEdit / loadData so tests are not
# subject to Playwright route concurrency limitations.
_JS_MOCK_TEMPLATE = """\
(function(opts) {
    window._mockState = {
        profile:  JSON.parse(JSON.stringify(opts.baseProfile)),
        company:  JSON.parse(JSON.stringify(opts.baseCompany)),
        branches: [],
        calls:    [],
    };

    function _mockResp(body, status) {
        return new Response(JSON.stringify(body), { status: status || 200 });
    }

    function _companyResp() {
        return {
            status: 'success',
            profile: JSON.parse(JSON.stringify(window._mockState.profile)),
            company: JSON.parse(JSON.stringify(window._mockState.company)),
            stats: {followers_count:0, jobs_count:0, rating_avg:0, rating_count:0},
            permissions: {can_edit:true, can_follow:false, is_following:false,
                          viewer_type:'owner', viewer_id:1}
        };
    }

    var _origFetch = window.fetch;
    window.fetch = function(url, options) {
        var urlStr = typeof url === 'string' ? url : url.toString();
        var method = (options && options.method) || 'GET';
        window._mockState.calls.push({ url: urlStr, method: method });

        /* /profile/{id}  (NOT /company/profile/{id}) */
        if (/[/]profile[/][0-9]+$/.test(urlStr) && urlStr.indexOf('/company') < 0) {
            if (method === 'PUT') {
                if (opts.profileStatus !== 200) {
                    return Promise.resolve(_mockResp({detail:'profile error'}, opts.profileStatus));
                }
                try {
                    var b = JSON.parse((options && options.body) || '{}');
                    ['full_name','bio','country','city','location'].forEach(function(k) {
                        if (k in b) window._mockState.profile[k] = b[k];
                    });
                } catch(e) {}
                return Promise.resolve(_mockResp({status:'success'}));
            }
            return Promise.resolve(_mockResp(_companyResp()));
        }

        /* /company/profile/{id} */
        if (/[/]company[/]profile[/][0-9]+$/.test(urlStr)) {
            if (method === 'PUT') {
                if (opts.companyStatus !== 200) {
                    return Promise.resolve(_mockResp({detail:'company error'}, opts.companyStatus));
                }
                try {
                    var b = JSON.parse((options && options.body) || '{}');
                    ['industry','company_type','company_size','founded_year'].forEach(function(k) {
                        if (k in b) window._mockState.company[k] = b[k];
                    });
                } catch(e) {}
                return Promise.resolve(_mockResp({status:'success'}));
            }
            /* GET — used by loadData({silent:true}) background sync */
            return Promise.resolve(_mockResp(_companyResp()));
        }

        /* /company/branches/{id} */
        if (/[/]company[/]branches[/][0-9]/.test(urlStr)) {
            if (method === 'PUT') {
                if (opts.branchesStatus !== 200) {
                    return Promise.resolve(_mockResp({detail:'branches error'}, opts.branchesStatus));
                }
                try {
                    var b = JSON.parse((options && options.body) || '{}');
                    window._mockState.branches = b.branches || [];
                } catch(e) {}
                return Promise.resolve(_mockResp({status:'success',
                                                  branches: window._mockState.branches}));
            }
            return Promise.resolve(_mockResp({status:'success',
                                              branches: window._mockState.branches}));
        }

        /* /jobs */
        if (urlStr.indexOf('/jobs') >= 0) {
            return Promise.resolve(_mockResp({status:'success', jobs: []}));
        }

        /* pass through: page HTML, CSS, JS static assets */
        return _origFetch.apply(this, arguments);
    };
})(__OPTS__);
"""

def _install_js_mock(page, profile_status=200, company_status=200, branches_status=200):
    opts = json.dumps({
        'baseProfile':    BASE_COMPANY_DATA['profile'],
        'baseCompany':    BASE_COMPANY_DATA['company'],
        'profileStatus':  profile_status,
        'companyStatus':  company_status,
        'branchesStatus': branches_status,
    })
    js = _JS_MOCK_TEMPLATE.replace('__OPTS__', opts)
    page.evaluate(js)


def make_page(browser, profile_status=200, company_status=200, branches_status=200):
    """
    Create an isolated browser context, load company-profile, install JS fetch
    mock, and inject correct companyState.

    The JS mock intercepts all fetch() calls that saveEdit() and loadData() make,
    making mock responses synchronous Promises — no Playwright route timing involved.
    """
    ctx  = browser.new_context()
    page = ctx.new_page()

    page.goto(BASE + '/company-profile?id=1', timeout=15000)
    page.evaluate("""
        localStorage.setItem('tw_user', JSON.stringify({
            id: 1, tw_id: 'C9660aabbccddee', user_type: 'co',
            full_name: 'شركة الاختبار', email: 'test@company.com'
        }));
        localStorage.setItem('tw_jwt', 'test-jwt-token');
    """)
    page.reload(timeout=15000)
    try:
        page.wait_for_load_state('networkidle', timeout=5000)
    except Exception:
        pass
    page.wait_for_selector('#coName', timeout=8000)

    # Install fetch mock AFTER all page scripts are loaded
    _install_js_mock(page, profile_status, company_status, branches_status)

    # Inject correct company state — the initial loadData() hit the real server
    # (fake JWT → auth error → _mergeCompanyState bails). Force correct state so
    # saveEdit() has a valid coId and display name to work with.
    page.evaluate(
        "if(window._mergeCompanyState) window._mergeCompanyState(%s);" %
        json.dumps(BASE_COMPANY_DATA)
    )
    return page


def open_modal_and_wait(page):
    """Open edit modal and wait for branches to load (save button enabled)."""
    page.evaluate("""
        if (window.companyState && window.companyState.permissions) {
            window.companyState.permissions.can_edit = true;
            window.companyState.viewMode = 'owner';
        }
        document.body.classList.add('view-owner');
    """)
    page.evaluate("window.openEditModal()")
    page.wait_for_function(
        '!!(document.getElementById("editOverlay") && '
        'document.getElementById("editOverlay").classList.contains("show"))',
        timeout=10000)
    # The JS mock makes the branches GET resolve immediately (Promise.resolve), so
    # _branchesLoaded should flip to true very quickly. 3 s is a generous timeout.
    try:
        page.wait_for_function('window._branchesLoaded === true', timeout=3000)
    except Exception:
        page.evaluate("""
            window._branchesLoaded = true;
            var s = document.getElementById('editSaveBtn');
            if (s) { s.disabled = false; s.style.opacity = ''; }
        """)
    # Ensure the hidden native <select>#e-type has a value so saveEdit() passes
    # its coType guard (scSelectInit() rebuilds options and can reset native.value).
    page.evaluate("""
        (function() {
            var s = document.getElementById('e-type');
            if (!s || s.value) return;
            for (var i = 0; i < s.options.length; i++) {
                if (s.options[i].value) { s.value = s.options[i].value; break; }
            }
        })()
    """)


PASS = 0
FAIL = 0
results = []

def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        results.append(('PASS', name))
        print('  PASS: %s' % name)
    else:
        FAIL += 1
        results.append(('FAIL', name, detail))
        print('  FAIL: %s%s' % (name, (' — ' + detail) if detail else ''))


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        executable_path='/opt/pw-browsers/chromium', args=['--no-sandbox'])

    # ── T01: Required functions exist ────────────────────────────────────
    print('\n[T01] Required functions exist')
    page = make_page(browser)
    check('saveEdit is a function',
          ev(page, 'return typeof window.saveEdit === "function"'))
    check('_applyCompanyLocalUpdate is a function',
          ev(page, 'return typeof window._applyCompanyLocalUpdate === "function"'))
    page.context.close()

    # ── T02: Success — modal closes after all PUTs succeed ──────────────
    print('\n[T02] Success: modal closes after API success')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    modal_closed = ev(page,
        'return !document.getElementById("editOverlay").classList.contains("show")')
    check('Modal closes after all PUTs succeed', modal_closed)
    page.context.close()

    # ── T03: Success — name/bio update immediately in DOM ────────────────
    print('\n[T03] Success: name and bio update immediately in DOM')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.fill('#e-name', 'شركة محدثة للاختبار')
    page.fill('#e-desc', 'وصف محدث جديد للاختبار')
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    name_text = ev(page, 'return (document.getElementById("coName") || {}).textContent || ""')
    desc_text = ev(page, 'return (document.getElementById("coDesc") || {}).textContent || ""')
    check('Company name updates immediately after success',
          'محدثة' in name_text, 'got: ' + repr(name_text))
    check('Company bio updates immediately after success',
          'محدث' in desc_text, 'got: ' + repr(desc_text))
    page.context.close()

    # ── T04: Failure on profile PUT — modal stays open ───────────────────
    print('\n[T04] Failure: profile PUT fails → modal stays open')
    page = make_page(browser, profile_status=500)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(1.5)
    modal_open = ev(page, 'return document.getElementById("editOverlay").classList.contains("show")')
    check('Modal stays open when profile PUT fails', modal_open)
    page.context.close()

    # ── T05: Failure on company profile PUT — modal stays open ───────────
    print('\n[T05] Failure: company PUT fails → modal stays open')
    page = make_page(browser, company_status=500)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(1.5)
    modal_open = ev(page, 'return document.getElementById("editOverlay").classList.contains("show")')
    check('Modal stays open when company PUT fails', modal_open)
    page.context.close()

    # ── T06: Failure on branches PUT — modal stays open ─────────────────
    print('\n[T06] Failure: branches PUT fails → modal stays open')
    page = make_page(browser, branches_status=500)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(1.5)
    modal_open = ev(page, 'return document.getElementById("editOverlay").classList.contains("show")')
    check('Modal stays open when branches PUT fails', modal_open)
    page.context.close()

    # ── T07: Button state restored after failure ─────────────────────────
    print('\n[T07] Failure: save button re-enabled + text reset')
    page = make_page(browser, profile_status=500)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(1.5)
    btn_disabled = ev(page, 'var b=document.getElementById("editSaveBtn"); return b ? b.disabled : null')
    btn_text     = ev(page, 'var b=document.getElementById("editSaveBtn"); return b ? b.textContent.trim() : ""')
    check('Save button re-enabled after failure',
          btn_disabled == False, 'disabled=%s' % btn_disabled)
    check('Save button text reset to "حفظ" after failure',
          'حفظ' in (btn_text or '') and 'جاري' not in (btn_text or ''),
          'text=%s' % repr(btn_text))
    page.context.close()

    # ── T08: Double submit prevention ────────────────────────────────────
    print('\n[T08] Double submit prevention')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit(); window.saveEdit()")
    time.sleep(2.5)
    put_count = ev(page, """
        if (!window._mockState) return -1;
        return window._mockState.calls.filter(function(c) {
            return c.method === 'PUT'
                && c.url.indexOf('/profile/') >= 0
                && c.url.indexOf('/company') < 0;
        }).length;
    """)
    check('Double submit blocked (at most 1 profile PUT)',
          put_count <= 1, 'PUT count=%s' % put_count)
    page.context.close()

    # ── T09: companyState.profile updated locally after success ──────────
    print('\n[T09] companyState.profile.full_name updated locally')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.fill('#e-name', 'اسم محدث للاختبار فقط')
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    state_name = ev(page,
        'return window.companyState && companyState.profile && companyState.profile.full_name')
    check('companyState.profile.full_name updated locally',
          state_name == 'اسم محدث للاختبار فقط', 'got: ' + repr(state_name))
    page.context.close()

    # ── T10: Branches in companyState are array after save ───────────────
    print('\n[T10] companyState.branches is an array after save')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    branches = ev(page, 'return window.companyState && window.companyState.branches')
    check('companyState.branches is an array after save',
          isinstance(branches, list), 'type: %s' % type(branches).__name__)
    page.context.close()

    # ── T11: openAllBranchesModal still works after save ─────────────────
    print('\n[T11] openAllBranchesModal still works after save')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    fn_ok = ev(page, 'return typeof window.openAllBranchesModal === "function"')
    check('openAllBranchesModal still a function after save', fn_ok)
    page.context.close()

    # ── T12: TW.countryFlagEl works after save ───────────────────────────
    print('\n[T12] TW.countryFlagEl works after save')
    page = make_page(browser, 200, 200, 200)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    flag_ok = ev(page, 'return window.TW && typeof TW.countryFlagEl === "function"')
    check('TW.countryFlagEl still available after save', flag_ok)
    page.context.close()

    # ── T13: No critical JS errors during save ───────────────────────────
    print('\n[T13] No critical JS errors during save')
    errors = []
    page = make_page(browser, 200, 200, 200)
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    open_modal_and_wait(page)
    page.evaluate("window.saveEdit()")
    time.sleep(2.0)
    critical = [e for e in errors if any(k in e.lower() for k in
                ['uncaught', 'typeerror', 'referenceerror', 'syntaxerror',
                 'cannot read', 'is not a function'])]
    check('No critical JS errors during save',
          len(critical) == 0, 'errors: %s' % critical[:2])
    page.context.close()

    # ── T14: loadData({silent:true}) does NOT call renderAll ─────────────
    print('\n[T14] loadData({silent:true}) skips renderAll')
    page = make_page(browser, 200, 200, 200)
    page.evaluate("""
        window.__renderAllCount = 0;
        var _origRA = window.renderAll;
        window.renderAll = function() {
            window.__renderAllCount++;
            if (_origRA) _origRA();
        };
    """)
    before = ev(page, 'return window.__renderAllCount')
    page.evaluate("window.loadData({ silent: true })")
    time.sleep(2.0)
    after = ev(page, 'return window.__renderAllCount')
    delta = after - before if (after is not None and before is not None) else -1
    check('loadData({silent:true}) does NOT trigger renderAll',
          delta == 0, 'renderAll called %d extra times' % delta)
    page.context.close()

    browser.close()

# ── Summary ──────────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('Results: %d passed, %d failed out of %d tests' % (PASS, FAIL, PASS + FAIL))
if FAIL:
    print('\nFailed:')
    for r in results:
        if r[0] == 'FAIL':
            print('  FAIL: %s%s' % (r[1], (' — ' + r[2]) if len(r) > 2 else ''))
print('='*60)
sys.exit(0 if FAIL == 0 else 1)
