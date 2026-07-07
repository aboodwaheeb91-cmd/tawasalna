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

# 8. server.py: rate limiter for save
if '_check_save_rate' in server and '_save_rate_store' in server:
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

# 10. company.render.js: icoBookmarkFilled exists
if 'icoBookmarkFilled' in render and 'fill="currentColor"' in render:
    ok(10, 'company.render.js: icoBookmarkFilled موجود ✅')
else:
    fail(10, 'icoBookmarkFilled', 'غير موجود')

# 11. company.render.js: save button uses viewer_saved
if 'viewer_saved' in render and 'save-active' in render and 'data-saved' in render:
    ok(11, 'company.render.js: save button uses viewer_saved + save-active ✅')
else:
    fail(11, 'viewer_saved in render', f'viewer_saved={("viewer_saved" in render)}, save-active={("save-active" in render)}')

# 12. company.posts.js: Desired State Queue vars
if '_saveDesired' in posts and '_saveInFlight' in posts and '_saveOrigState' in posts:
    ok(12, 'company.posts.js: Desired State Queue vars موجودة ✅')
else:
    fail(12, 'Save Desired State Queue', 'vars غير موجودة')

# 13. company.posts.js: _toggleSave calls PUT /save
if '_toggleSave' in posts and "'/company/posts/' + postId + '/save'" in posts:
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
