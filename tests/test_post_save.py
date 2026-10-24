#!/usr/bin/env python3
"""Tests — Post Save System (feat/company-post-save-system)"""
import sys, re

results = []
def ok(n, d):     results.append((n, True,  d, ''));    print(f'✅ Test {n}: {d}')
def fail(n, d, r=''):  results.append((n, False, d, r)); print(f'❌ Test {n}: {d}\n     ↳ {r}')

server  = open('server.py').read()
auth    = open('auth.py').read()
render  = open('static/company/company.render.js').read()
posts   = open('static/company/company.posts.js').read()

# 1. DB migration: company_post_saves table exists
if 'company_post_saves' in auth and 'ON DELETE CASCADE' in auth:
    ok(1, 'auth.py: company_post_saves table in migration ✅')
else:
    fail(1, 'company_post_saves migration', 'غير موجود في auth.py')

# 2. UNIQUE index on (post_id, user_id)
if 'uq_post_save_user' in auth:
    ok(2, 'auth.py: UNIQUE index uq_post_save_user ✅')
else:
    fail(2, 'uq_post_save_user', 'UNIQUE index غير موجود')

# 3. set_company_post_save function — idempotent
if 'def set_company_post_save' in auth and 'ON CONFLICT DO NOTHING' in auth:
    ok(3, 'auth.py: set_company_post_save idempotent ✅')
else:
    fail(3, 'set_company_post_save', 'غير موجود أو ليس idempotent')

# 4. viewer_saved in get_company_posts
if 'viewer_saved' in auth and 'ups.user_id IS NOT NULL' in auth:
    ok(4, 'auth.py: viewer_saved returned from get_company_posts ✅')
else:
    fail(4, 'viewer_saved', 'غير موجود في get_company_posts')

# 5. server.py: set_company_post_save imported
if 'set_company_post_save' in server:
    ok(5, 'server.py: set_company_post_save مستورد ✅')
else:
    fail(5, 'import set_company_post_save', 'غير موجود')

# 6. server.py: PUT /company/posts/{post_id}/save endpoint
if "app.put(\"/company/posts/{post_id}/save\")" in server:
    ok(6, 'server.py: PUT /company/posts/{post_id}/save موجود ✅')
else:
    fail(6, 'PUT /save endpoint', 'غير موجود')

# 7. server.py: SaveStateInput model
if 'class SaveStateInput' in server and 'saved: bool' in server:
    ok(7, 'server.py: SaveStateInput موجود ✅')
else:
    fail(7, 'SaveStateInput', 'غير موجود')

# 8. server.py: rate limiter for save — defined on the shared store (_rate_ok, RATES["post_save"]
#    — task 5.0h-2) and called by the save endpoint (structure, not text)
import ast as _ast, tw_limits as _twl
def _fn_calls(fn_name, callee):
    for node in _ast.walk(_ast.parse(server)):
        if isinstance(node, _ast.FunctionDef) and node.name == fn_name:
            return any(isinstance(c, _ast.Call) and getattr(c.func, 'id', None) == callee for c in _ast.walk(node))
    return False
if _fn_calls('_check_save_rate', '_rate_ok') and 'post_save' in _twl.RATES \
        and _fn_calls('company_post_set_save', '_check_save_rate'):
    ok(8, 'server.py: _check_save_rate موجود ✅')
else:
    fail(8, '_check_save_rate', 'غير موجود')

# 9. server.py: 404 if post not found
if '_check_save_rate' in server:
    save_fn = re.search(r'def company_post_set_save.*?return \{.*?\}', server, re.DOTALL)
    if save_fn and 'get_post_owner' in save_fn.group(0) and '404' in save_fn.group(0):
        ok(9, 'server.py: 404 إذا المنشور غير موجود ✅')
    else:
        fail(9, '404 check', 'غير موجود في company_post_set_save')
else:
    fail(9, '404 check', 'دالة company_post_set_save غير موجودة')

# 10 + 11. Save button first render = TwPostCard (task U.2 — behaviour, not source text):
#     viewer_saved → .save-active + data-saved="1" + filled bookmark-check icon; else outline.
import subprocess as _sp, json as _json
_JS = r"""
const vm = require('vm'), fs = require('fs');
const c = { twEscAttr: s => String(s == null ? '' : s), twSafeImageUrl: () => '', twT: k => k,
  twAvatarHtml: () => '', twRelativeTime: () => '', twActionState: () => 'enabled' };
c.twEscHtml = c.twEscAttr; c.window = c; vm.createContext(c);
vm.runInContext(fs.readFileSync('static/shared/tw-icons.js', 'utf8'), c);
vm.runInContext(fs.readFileSync('static/shared/tw-post-card.js', 'utf8'), c);
const r = v => c.TwPostCard.html({ id: 1, body: 'x', viewer_saved: v }, { authorName: 'n' });
const btn = h => h.slice(h.indexOf('pc-btn--save'), h.indexOf('</button>', h.indexOf('pc-btn--save')));
console.log(JSON.stringify({ on: btn(r(true)), off: btn(r(false)),
  checkIco: c.twIcon('bookmark-check', { size: 'sm', filled: true }), plainIco: c.twIcon('bookmark', { size: 'sm' }) }));
"""
try:
    _out = _json.loads(_sp.run(['node', '-e', _JS], capture_output=True, text=True, check=True).stdout)
except Exception as _e:
    _out = {'on': '', 'off': '', 'err': repr(_e)}
if _out.get('checkIco') and _out['checkIco'] in _out['on'] and _out['checkIco'] not in _out['off'] \
        and _out['plainIco'] in _out['off']:
    ok(10, 'TwPostCard: saved → filled bookmark-check icon (DS-ICON) ✅')
else:
    fail(10, 'icoBookmarkCheck', _out.get('err', 'saved icon not rendered'))

if 'save-active' in _out['on'] and 'data-saved="1"' in _out['on'] \
        and 'save-active' not in _out['off'] and 'data-saved="0"' in _out['off']:
    ok(11, 'TwPostCard: save button follows viewer_saved + save-active ✅')
else:
    fail(11, 'viewer_saved in render', _out.get('err', 'state not reflected'))

# 12–18. Save behaviour = TwPostCard.create (task U.2b — moved from company.posts.js;
#     behaviour on the real markup, not source text). The page passes the path (test 13).
_JS2 = r"""
const vm = require('vm'), fs = require('fs');
const { makeDocument } = require('./tests/fixtures/post_card_dom.js');
const out = {};
function boot(signedIn) {
  const doc = makeDocument(), api = [], toast = [], pend = [], ls = { reads: 0 };
  const c = { twEscAttr: s => String(s == null ? '' : s), twSafeImageUrl: () => '', document: doc,
    twT: k => k, twAvatarHtml: () => '', twRelativeTime: () => '', twActionState: () => 'enabled',
    location: { pathname: '/u/C1', search: '', href: '' }, twLoginHref: n => '/login?next=' + n,
    showToast: (m, t) => toast.push(t), twApiMessage: (r, f) => f, setTimeout() {},
    localStorage: { getItem() { ls.reads++; return null; }, setItem() { ls.reads++; } },
    twApi: (p, o) => new Promise(r => { api.push([p, o.method, o.body]); pend.push(r); }) };
  c.twEscHtml = c.twEscAttr; c.window = c; vm.createContext(c);
  vm.runInContext(fs.readFileSync('static/shared/tw-post-card.js', 'utf8'), c);
  const list = doc.createElement('div');
  list.innerHTML = c.TwPostCard.html({ id: 1, body: 'x' }, { authorName: 'n' });
  doc.body.appendChild(list);
  c.TwPostCard.create({ signedIn: () => signedIn, paths: { save: id => '/company/posts/' + id + '/save' } }).bind(list);
  const btn = () => list.querySelector('.pc-btn--save');
  return { api, toast, pend, ls, btn, click: () => doc.click(btn()), login: () => c.location.href };
}
(async () => {
  const t = () => new Promise(r => setImmediate(r));
  const g = boot(false); g.click();
  out.guest = { api: g.api.length, toast: g.toast, login: g.login() };
  const b = boot(true); b.click(); b.click();
  out.queue = { inflight: b.api.length, first: b.api[0], uiOff: b.btn().dataset.saved };
  b.pend.shift()({ ok: true, status: 200, data: { status: 'success', saved: true } }); await t();
  out.stale = { calls: b.api.length, second: b.api[1] && b.api[1][2], uiOff: b.btn().dataset.saved };
  b.pend.shift()({ ok: false, status: 500, data: null }); await t();
  out.rollback = b.btn().dataset.saved;
  out.ls = b.ls.reads;
  console.log(JSON.stringify(out));
})();
"""
try:
    _o = _json.loads(_sp.run(['node', '-e', _JS2], capture_output=True, text=True, check=True).stdout)
except Exception as _e:
    _o = {'err': repr(_e)}

if _o.get('queue', {}).get('inflight') == 1 and _o['queue']['uiOff'] == '0':
    ok(12, 'TwPostCard: Desired State Queue — ضغطتين سريعتين = طلب واحد بالطيران ✅')
else:
    fail(12, 'Save Desired State Queue', _o.get('err', str(_o.get('queue'))))

if _o.get('queue', {}).get('first') == ['/company/posts/1/save', 'PUT', {'saved': True}]:
    ok(13, 'TwPostCard: الحفظ = PUT /save {saved} عبر twApi ✅')
else:
    fail(13, 'save endpoint', _o.get('err', str(_o.get('queue'))))

if _o.get('guest') == {'api': 0, 'toast': [], 'login': '/login?next=/u/C1'}:
    ok(14, 'TwPostCard: الزائر غير المسجل → صفحة الدخول (twLoginHref) بدون طلب ✅')
else:
    fail(14, 'guest login', _o.get('err', str(_o.get('guest'))))

if _o.get('stale') == {'calls': 2, 'second': {'saved': False}, 'uiOff': '0'} and _o.get('rollback') == '1':
    ok(15, 'TwPostCard: no-flicker + طلب الطابور + رجوع عند الفشل ✅')
else:
    fail(15, 'no-flicker in save', _o.get('err', str(_o.get('stale')) + ' / ' + str(_o.get('rollback'))))

# 16. coming-soon toast removed for save (the "removed thing did not come back")
if "ميزة حفظ المنشورات ستتوفر قريباً" in posts or "ميزة حفظ المنشورات ستتوفر قريباً" in open('static/shared/tw-post-card.js').read():
    fail(16, 'coming-soon toast', 'toast "ستتوفر قريباً" لا يزال موجوداً — يجب إزالته')
else:
    ok(16, 'coming-soon toast أُزيل ✅')

# 17. .save-active styles — parsed rule in tw-card.css (task U.2b — moved from company.css)
_card_css = re.sub(r'/\*.*?\*/', '', open('static/shared/tw-card.css').read(), flags=re.S)
_rules = {sel.strip(): body for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', _card_css)}
if 'fill:currentColor' in _rules.get('.pc-btn--save.save-active svg', '').replace(' ', '') \
        and '.pc-btn--save.save-active' in _rules:
    ok(17, 'tw-card.css: .pc-btn--save.save-active styles موجودة ✅')
else:
    fail(17, '.save-active CSS', 'غير موجود')

# 18. no localStorage as source of truth for saves (signed-in save flow never touches it)
if _o.get('ls') == 0:
    ok(18, 'TwPostCard: لا localStorage في save logic ✅')
else:
    fail(18, 'localStorage in save', str(_o.get('ls', _o.get('err'))))

passed = sum(1 for _,ok_,_,_ in results if ok_)
total  = len(results)
print(f'\n{"="*60}')
print(f'{passed}/{total} {"✅ كل الاختبارات نجحت" if passed == total else "❌ بعض الاختبارات فشلت"}')
sys.exit(0 if passed == total else 1)
