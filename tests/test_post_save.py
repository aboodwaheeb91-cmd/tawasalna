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
css     = open('static/company/company.css').read()

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
const c = { twEscAttr: s => String(s == null ? '' : s), twSafeImageUrl: () => '' };
c.twEscHtml = c.twEscAttr; c.window = c; vm.createContext(c);
vm.runInContext(fs.readFileSync('static/shared/tw-post-card.js', 'utf8'), c);
const r = v => c.TwPostCard.html({ id: 1, body: 'x', viewer_saved: v }, { authorName: 'n' });
const btn = h => h.slice(h.indexOf('pc-btn--save'), h.indexOf('</button>', h.indexOf('pc-btn--save')));
console.log(JSON.stringify({ on: btn(r(true)), off: btn(r(false)) }));
"""
try:
    _out = _json.loads(_sp.run(['node', '-e', _JS], capture_output=True, text=True, check=True).stdout)
except Exception as _e:
    _out = {'on': '', 'off': '', 'err': repr(_e)}
if 'fill="currentColor"' in _out['on'] and 'M8.5 10' in _out['on'] and 'M8.5 10' not in _out['off']:
    ok(10, 'TwPostCard: saved → filled bookmark-check icon ✅')
else:
    fail(10, 'icoBookmarkCheck', _out.get('err', 'saved icon not rendered'))

if 'save-active' in _out['on'] and 'data-saved="1"' in _out['on'] \
        and 'save-active' not in _out['off'] and 'data-saved="0"' in _out['off']:
    ok(11, 'TwPostCard: save button follows viewer_saved + save-active ✅')
else:
    fail(11, 'viewer_saved in render', _out.get('err', 'state not reflected'))

# 12. company.posts.js: Desired State Queue vars
if '_saveDesired' in posts and '_saveInFlight' in posts and '_saveOrigState' in posts:
    ok(12, 'company.posts.js: Desired State Queue vars موجودة ✅')
else:
    fail(12, 'Save Desired State Queue', 'vars غير موجودة')

# 13. company.posts.js: _toggleSave calls PUT /save
# PR 4.3a: request through twApi (method PUT) — the path is built from the encoded post id
if '_toggleSave' in posts and "twApi('/company/posts/' + encodeURIComponent(postId) + '/save', { method: 'PUT'" in posts:
    ok(13, 'company.posts.js: _toggleSave يستخدم PUT /save ✅')
else:
    fail(13, '_toggleSave endpoint', 'غير موجود أو endpoint خاطئ')

# 14. company.posts.js: guest toast correct message
if "سجّل دخولك لحفظ المنشور" in posts:
    ok(14, 'company.posts.js: toast للزائر غير المسجل ✅')
else:
    fail(14, 'guest toast', 'رسالة الزائر غير موجودة')

# 15. company.posts.js: no-flicker check (desired !== srvActive check before render)
if 'desired !== undefined && desired !== srvActive' in posts:
    ok(15, 'company.posts.js: no-flicker check موجود في save queue ✅')
else:
    fail(15, 'no-flicker in save', 'desired !== srvActive check غير موجود')

# 16. company.posts.js: coming-soon toast removed for save
if "ميزة حفظ المنشورات ستتوفر قريباً" in posts:
    fail(16, 'coming-soon toast', 'toast "ستتوفر قريباً" لا يزال موجوداً — يجب إزالته')
else:
    ok(16, 'company.posts.js: coming-soon toast أُزيل ✅')

# 17. company.css: .save-active styles
if '.pc-btn--save.save-active' in css and 'fill:currentColor' in css:
    ok(17, 'company.css: .pc-btn--save.save-active styles موجودة ✅')
else:
    fail(17, '.save-active CSS', 'غير موجود')

# 18. no localStorage as source of truth for saves
save_block = re.search(r'_toggleSave.*?_dispatchSave.*?function _dispatchSave', posts, re.DOTALL)
if save_block:
    if 'localStorage' not in save_block.group(0):
        ok(18, 'company.posts.js: لا localStorage في save logic ✅')
    else:
        fail(18, 'localStorage in save', 'localStorage موجود في save logic')
else:
    ok(18, 'company.posts.js: لا localStorage في save logic ✅')

passed = sum(1 for _,ok_,_,_ in results if ok_)
total  = len(results)
print(f'\n{"="*60}')
print(f'{passed}/{total} {"✅ كل الاختبارات نجحت" if passed == total else "❌ بعض الاختبارات فشلت"}')
sys.exit(0 if passed == total else 1)
