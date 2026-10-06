"""
PR-4 — Dead files & routes cleanup.

1. No code (html / js / py / manifest) links to a deleted file or a deleted route.
2. Every retired page URL answers with the single shared legacy redirect page
   (_LEGACY_REDIRECT_HTML → twEntryDestination() → /u/{tw_id} or /login).
3. Deleted endpoints answer 404 / 405.

Run: python test_legacy_routes_cleanup.py   (TestClient, no DB)
"""
import os, re, sys, json

os.environ.setdefault('SUPABASE_DB_URL', 'postgresql://x:x@127.0.0.1:5432/notused')
os.environ.setdefault('JWT_SECRET', 'test-secret')

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

results = []
def check(name, cond, detail=''):
    results.append(bool(cond))
    print(('✅ ' if cond else '❌ ') + name + ('' if cond or not detail else f'  [{detail}]'))

def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()

# ── 1. Deleted files are gone ─────────────────────────────────────────────────
DELETED_FILES = [
    'profile.html', 'home.html', 'company-profile.js', 'static/home-v2.js',
    'profile_showcase.html', 'employees-group.html', 'jobs.html', 'edu.html',
    'company.html', 'static/img/qr-card-template-ar.png', 'auto_sync.py',
    '.replit', 'test.py',
]
for f in DELETED_FILES:
    check(f'1. deleted file absent: {f}', not os.path.exists(f))

# ── 2. No code reference to a deleted file / route ───────────────────────────
CODE_EXT = ('.html', '.js', '.py', '.json', '.mjs')
SKIP_DIRS = {'.git', 'node_modules', 'docs', 'static/vendor', '__pycache__'}
SELF = os.path.basename(__file__)

def code_files():
    for dp, dns, fns in os.walk('.'):
        rel = os.path.relpath(dp, '.')
        dns[:] = [d for d in dns if os.path.normpath(os.path.join(rel, d)) not in SKIP_DIRS]
        for fn in fns:
            # test files may name deleted files in comments / history labels
            if fn.endswith(CODE_EXT) and not fn.startswith('test_') and fn != SELF:
                yield os.path.normpath(os.path.join(rel, fn))

# Names with no surviving route at all — must not appear anywhere in code.
DEAD_REFS = {
    'company-profile.js':      r'(?<![\w/.-])/?company-profile\.js',
    'home-v2.js':              r'home-v2\.js',
    'profile_showcase.html':   r'profile_showcase\.html',
    'employees-group':         r'employees-group',
    'qr-card-template-ar.png': r'qr-card-template-ar\.png',
    'auto_sync.py':            r'auto_sync',
    'test.py':                 r'(?<![\w-])test\.py',
    'POST /feedback':          r'["\']/feedback["\']',
    'GET /jobs/match':         r'/jobs/match',
    'POST /appreciate':        r'/appreciate(?![a-z])',
    'sanitize() alias':        r'\bsanitize\(',
    'company menu → /company': r'["\']/company["\']',
    'edu home → /edu':         r'["\']/edu["\']',
}
# server.py legitimately lists /company and /edu as legacy redirect paths.
ALLOWED = {'company menu → /company': {'server.py'}, 'edu home → /edu': {'server.py'}}
hits = {k: [] for k in DEAD_REFS}
srcs = {p: read(p) for p in code_files()}
for p, src in srcs.items():
    for k, pat in DEAD_REFS.items():
        if p in ALLOWED.get(k, ()):
            continue
        if re.search(pat, src):
            hits[k].append(p)
for k, files in hits.items():
    check(f'2. no code reference: {k}', not files, ', '.join(files))

# Retired page files must never be served again — only redirect URLs remain.
srv = read('server.py')
for f in ('profile.html', 'home.html', 'company.html', 'edu.html', 'jobs.html',
          'employees-group.html', 'profile_showcase.html'):
    check(f'2. server.py never serves {f}', f'read_html("{f}")' not in srv)

man = json.loads(read('manifest.json'))
urls = [s['url'] for s in man.get('shortcuts', [])]
check('2. manifest: no jobs.html shortcut', all('jobs' not in u for u in urls), urls)
check('2. manifest: "ملفي" → /profile', any(s['name'] == 'ملفي' and s['url'] == '/profile'
                                            for s in man['shortcuts']), urls)

tws = read('tw_shared.js')
home_fn = tws[tws.index('function twHomeHref('):tws.index('function twAccountHref(')]
check("2. twHomeHref → '/home' for every logged-in type",
      "return '/home';" in home_fn and "'/company'" not in home_fn and "'/edu'" not in home_fn)
check('2. header menu: "بنك المواهب" uses twTalentBankHref',
      "label: 'بنك المواهب', href: twTalentBankHref" in tws and 'بحث عن موظفين' not in tws)
check('2. twTalentBankHref → /u/{tw_id}?cand=',
      "'/u/' + encodeURIComponent(u.tw_id) + '?cand='" in tws)
check('2. home.nav.js co sidebar → twTalentBankHref (label "بنك المواهب")',
      "label: 'بنك المواهب',  href: twTalentBankHref(user)" in read('static/home/home.nav.js'))
msg_js = read('messages.render.js')
check('2. messages.render.js home → twHomeHref(_user) for every type (no Talent Bank exception)',
      'window.location.href = twHomeHref(_user);' in msg_js and 'twTalentBankHref' not in msg_js)
check('2. edu-profile.html goHome → twHomeHref()',
      "window.location.href=twHomeHref();" in read('edu-profile.html'))
st_html = read('settings.html')
check('2. settings.html goBack → twAccountHref(_user), no hardcoded profile paths',
      'window.location.href = twAccountHref(_user);' in st_html
      and "?id=' + _pid" not in st_html)
check('2. job-detail.js "أكمل مهاراتك الآن" → twAccountHref',
      'twAccountHref(_user)' in read('static/job/job-detail.js'))
main_js = read('static/company/company.main.js')
check('2. company.main.js: empty ?cand= opens Talent Bank (cand !== null)',
      'if (cand !== null)' in main_js and '_pendingManageOpen      = cand || null;' in main_js)
home_main = read('static/home/home.main.js')
check('2. home.main.js guard decides from TwAuthSync.getSessionSnapshot()',
      'TwAuthSync.getSessionSnapshot()' in home_main
      and "localStorage.getItem('tw_user')" not in home_main)
check('2. server.py: Heroku comment fixed → Railway', 'Heroku' not in srv)

# ── 3. Legacy URLs → shared redirect page; deleted endpoints → 404/405 ───────
import server
from fastapi.testclient import TestClient
client = TestClient(server.app)

LEGACY = ['/profile', '/profile.html', '/company', '/company.html', '/edu',
          '/edu.html', '/home.html', '/jobs.html', '/company-profile', '/company-profile.html']
page = server._LEGACY_REDIRECT_HTML
check('3. redirect page loads tw_shared.js then auth-sync.js',
      0 < page.index('/tw_shared.js') < page.index('/static/shared/auth-sync.js'))
check('3. redirect page decides via twEntryDestination() with /login fallback',
      'twEntryDestination()' in page and 'location.replace(d||"/login")' in page
      and 'tw_user' not in page)
check('3. old _COMPANY_PROFILE_REDIRECT_HTML removed (one source)',
      not hasattr(server, '_COMPANY_PROFILE_REDIRECT_HTML'))
for u in LEGACY:
    r = client.get(u, follow_redirects=False)
    check(f'3. GET {u} → 200 shared redirect page', r.status_code == 200 and r.text == page,
          r.status_code)

# ?id= on every legacy URL → 302 /u/{tw_id} (any account type) via the single lookup
from unittest.mock import patch
check('3. single id → tw_id lookup (_get_co_tw_id merged)',
      hasattr(server, '_tw_id_for_user_id') and not hasattr(server, '_get_co_tw_id'))
_TW = {7: 'U00000007aa', 8: 'C00000008bb', 9: 'T00000009cc'}   # emp / co / edu
_calls = []
def _fake_lookup(uid):
    _calls.append(uid)
    return _TW.get(uid)
with patch.object(server, '_tw_id_for_user_id', side_effect=_fake_lookup):
    for u in LEGACY:
        for uid, tw in _TW.items():
            r = client.get(f'{u}?id={uid}', follow_redirects=False)
            check(f'3. GET {u}?id={uid} → 302 /u/{tw}',
                  r.status_code == 302 and r.headers.get('location') == f'/u/{tw}',
                  (r.status_code, r.headers.get('location')))
        r = client.get(f'{u}?id=999999', follow_redirects=False)
        check(f'3. GET {u}?id=<unknown> → redirect page, no 302',
              r.status_code == 200 and r.text == page, r.status_code)
    n_before = len(_calls)
    for bad in ('abc', 'U00000007aa', '-5', '1.5', '', '²', '١٢', '1' * 20, '9' * 19):
        r = client.get('/profile', params={'id': bad}, follow_redirects=False)
        check(f'3. GET /profile?id={bad!r} (not numeric) → redirect page, no 302',
              r.status_code == 200 and r.text == page, r.status_code)
    check('3. non-numeric / unicode-digit / over-long id never hits the DB lookup',
          len(_calls) == n_before)
    r = client.get('/profile', params={'id': '9' * 18}, follow_redirects=False)
    check('3. 18-digit id still reaches the lookup (unknown → redirect page)',
          r.status_code == 200 and r.text == page and _calls[-1] == int('9' * 18))
    n_before = len(_calls)
    r = client.get('/profile.html', follow_redirects=False)
    check('3. GET /profile.html without id → redirect page, no lookup',
          r.status_code == 200 and r.text == page and len(_calls) == n_before)

r = client.get('/home', follow_redirects=False)
check('3. GET /home still serves Home V2', r.status_code == 200 and 'home.main.js' in r.text)

for method, u in [('post', '/feedback'), ('get', '/jobs/match/1'),
                  ('post', '/company/posts/1/appreciate'), ('get', '/company-profile.js'),
                  ('get', '/employees-group'), ('get', '/employees-group.html')]:
    r = getattr(client, method)(u, follow_redirects=False)
    check(f'3. {method.upper()} {u} → gone (404/405)', r.status_code in (404, 405), r.status_code)

passed = sum(results)
print(f'\n{passed}/{len(results)} passed')
sys.exit(0 if passed == len(results) else 1)
