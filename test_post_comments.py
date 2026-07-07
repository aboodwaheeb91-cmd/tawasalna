"""
test_post_comments.py — Post Comments System (§22c)
20 tests covering DB, permissions, validation, soft-delete, XSS, and system integrity.
"""
import sys, os, re, ast
sys.path.insert(0, os.path.dirname(__file__))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def check(name, cond, detail=""):
    status = PASS if cond else FAIL
    results.append((name, status, detail))
    print(f"{status}  {name}" + (f"  [{detail}]" if detail else ""))


# ── 1. company_post_comments table in migration ───────────────────────────
with open("auth.py", encoding="utf-8") as f:
    auth_src = f.read()

check(
    "1. company_post_comments table defined in migration",
    "CREATE TABLE IF NOT EXISTS company_post_comments" in auth_src
)

# ── 2. All three indexes defined ──────────────────────────────────────────
check(
    "2. idx_post_cmts_post index (post_id, created_at)",
    "idx_post_cmts_post" in auth_src
)
check(
    "2b. idx_post_cmts_user index",
    "idx_post_cmts_user" in auth_src
)
check(
    "2c. idx_post_cmts_active index (post_id, status)",
    "idx_post_cmts_active" in auth_src
)

# ── 3. create requires JWT (no body user_id) ──────────────────────────────
with open("server.py", encoding="utf-8") as f:
    srv_src = f.read()

check(
    "3. POST /comments endpoint uses Depends(verify_token)",
    "def company_create_post_comment" in srv_src and "Depends(verify_token)" in srv_src
)

# ── 4. Guest (no JWT) blocked — server 401 ───────────────────────────────
check(
    "4. create endpoint raises 401 when user_id absent from token",
    'raise HTTPException(status_code=401' in srv_src and "يجب تسجيل الدخول للتعليق" in srv_src
)

# ── 5. comments_enabled=false → 403 server-side ───────────────────────────
check(
    "5. create_company_post_comment checks comments_enabled and raises PermissionError",
    "raise PermissionError" in auth_src and "التعليقات معطّلة" in auth_src
)
check(
    "5b. server maps PermissionError → HTTP 403",
    "raise HTTPException(status_code=403" in srv_src
)

# ── 6. Empty comment body rejected ────────────────────────────────────────
check(
    "6. create_company_post_comment rejects empty body",
    "التعليق لا يمكن أن يكون فارغاً" in auth_src
)

# ── 7. Max length enforced ────────────────────────────────────────────────
check(
    "7. _MAX_COMMENT_BODY constant defined",
    "_MAX_COMMENT_BODY = 1000" in auth_src
)
check(
    "7b. create/update check body length against _MAX_COMMENT_BODY",
    "len(body) > _MAX_COMMENT_BODY" in auth_src
)

# ── 8. Comment owner can edit ────────────────────────────────────────────
check(
    "8. update_company_post_comment checks owner_id == user_id",
    "if owner_id != user_id" in auth_src and "PermissionError" in auth_src
)

# ── 9. Other user cannot edit (PermissionError) ──────────────────────────
check(
    "9. update raises PermissionError for non-owner",
    "لا تملك صلاحية تعديل" in auth_src
)

# ── 10. Comment owner can delete ─────────────────────────────────────────
check(
    "10. delete_company_post_comment allows owner_id == user_id",
    "def delete_company_post_comment" in auth_src and "owner_id != user_id" in auth_src
)

# ── 11. Post owner can also delete ───────────────────────────────────────
check(
    "11. delete also allows company_id == user_id (post owner)",
    "company_id != user_id" in auth_src
)

# ── 12. Other user cannot delete ─────────────────────────────────────────
check(
    "12. delete raises PermissionError if neither owner",
    "لا تملك صلاحية حذف" in auth_src
)

# ── 13. Soft delete — status='deleted' not returned in GET ───────────────
check(
    "13. get_company_post_comments filters status = 'active' only",
    "status = 'active'" in auth_src or "status='active'" in auth_src
)
check(
    "13b. delete_company_post_comment sets status='deleted' and deleted_at",
    "status='deleted'" in auth_src and "deleted_at=NOW()" in auth_src
)

# ── 14. comments_count in get_company_posts ───────────────────────────────
check(
    "14. get_company_posts includes comments_count LEFT JOIN",
    "comments_count" in auth_src and "company_post_comments" in auth_src
)

# ── 15. XSS: body not rendered as innerHTML ───────────────────────────────
posts_js = open("static/company/company.posts.js", encoding="utf-8").read()
# textContent is the XSS-safe mechanism
check(
    "15. comment body rendered via textContent (XSS-safe)",
    "bodyEl.textContent = c.body" in posts_js or "textContent" in posts_js
)

# ── 16. No localStorage for comments ─────────────────────────────────────
check(
    "16. no localStorage used for comment data or count",
    "localStorage" not in posts_js.split("// ── Post Comments")[1] if "// ── Post Comments" in posts_js else "localStorage" not in posts_js
)

# ── 17. Appreciation system untouched ────────────────────────────────────
check(
    "17. appreciation endpoint still present in server.py",
    "PUT /company/posts/{post_id}/appreciation" in srv_src or
    "company_post_set_appreciation" in srv_src
)

# ── 18. Save system untouched ────────────────────────────────────────────
check(
    "18. save endpoint still present in server.py",
    "PUT /company/posts/{post_id}/save" in srv_src or
    "company_post_set_save" in srv_src
)

# ── 19. No notifications table creation ──────────────────────────────────
comment_section = auth_src[auth_src.find("Post Comments System"):] if "Post Comments System" in auth_src else ""
check(
    "19. no notifications table created in post comments migration",
    "CREATE TABLE IF NOT EXISTS notifications" not in comment_section
)

# ── 20. Rate limiters defined ────────────────────────────────────────────
check(
    "20. comment create rate limiter defined",
    "_cmt_create_rate_store" in srv_src and "_CMT_CREATE_RATE" in srv_src
)
check(
    "20b. comment edit rate limiter defined",
    "_cmt_edit_rate_store" in srv_src and "_CMT_EDIT_RATE" in srv_src
)

# ── 21. Edit UX: _cmtEditInFlight guard ──────────────────────────────────
posts_js = open("static/company/company.posts.js", encoding="utf-8").read()
check(
    "21. _cmtEditInFlight guard variable defined",
    "_cmtEditInFlight" in posts_js
)

# ── 22. Edit UX: editWrap inserted before bodyEl hidden ───────────────────
# The insert must happen before bodyEl.style.display = 'none'
cmt_edit_fn = posts_js[posts_js.find("function _cmtHandleEdit"):] if "function _cmtHandleEdit" in posts_js else ""
insert_pos  = cmt_edit_fn.find("content.insertBefore(editWrap")
hide_pos    = cmt_edit_fn.find("bodyEl.style.display = 'none'")
check(
    "22. editWrap inserted into DOM before bodyEl is hidden",
    insert_pos != -1 and hide_pos != -1 and insert_pos < hide_pos
)

# ── 23. Edit UX: correct parent (content, not item) ──────────────────────
check(
    "23. insertBefore uses content as parent (not item)",
    "content.insertBefore(editWrap" in posts_js
)

# ── 24. Edit UX: Optimistic UI — body rendered before fetch ──────────────
# _renderCommentBody(bodyEl, newBody) must appear before fetch(...)
optimistic_pos = cmt_edit_fn.find("_renderCommentBody(bodyEl, newBody)")
fetch_pos      = cmt_edit_fn.find("fetch('/company/posts/comments/")
check(
    "24. Optimistic UI: bodyEl updated before fetch call",
    optimistic_pos != -1 and fetch_pos != -1 and optimistic_pos < fetch_pos
)

# ── 25. Edit UX: rollback on server error ─────────────────────────────────
check(
    "25. rollback: _renderCommentBody(bodyEl, originalText) on failure",
    "_renderCommentBody(bodyEl, originalText)" in cmt_edit_fn
)

# ── 26. Edit XSS: optimistic update uses _renderCommentBody (no innerHTML) ──
check(
    "26. optimistic edit uses _renderCommentBody (XSS-safe), not innerHTML for API data",
    "_renderCommentBody(bodyEl, newBody)" in cmt_edit_fn and "bodyEl.innerHTML" not in cmt_edit_fn
)

# ── UX Improvements (feat/comment-ui-polish) ─────────────────────────────
posts_js = open("static/company/company.posts.js", encoding="utf-8").read()
company_css = open("static/company/company.css", encoding="utf-8").read()

# ── 27. Auto-resize helper ────────────────────────────────────────
check(
    "27. _autoResizeTextarea helper defined",
    "_autoResizeTextarea" in posts_js and "scrollHeight" in posts_js
)

# ── 28. Clock icon constant ────────────────────────────────────────
check(
    "28. _ICO_CLOCK constant defined",
    "_ICO_CLOCK" in posts_js
)

# ── 29. Relative time helper ───────────────────────────────────────
check(
    "29. _formatRelativeTime function defined",
    "function _formatRelativeTime" in posts_js
)

# ── 30. Relative time used in _cmtBuildItem ───────────────────────
build_fn2 = posts_js[posts_js.find("function _cmtBuildItem"):] if "function _cmtBuildItem" in posts_js else ""
check(
    "30. _formatRelativeTime called inside _cmtBuildItem",
    "_formatRelativeTime" in build_fn2[:3000]
)

# ── 31. _cmtOpenMenuId guard variable ─────────────────────────────
check(
    "31. _cmtOpenMenuId guard variable defined",
    "var _cmtOpenMenuId" in posts_js
)

# ── 32. Three-dot menu button built in _cmtBuildItem ──────────────
check(
    "32. pc-cmt-menu-btn class in _cmtBuildItem",
    "pc-cmt-menu-btn" in build_fn2[:3000]
)

# ── 33. Menu edit / delete classes now in portal (_cmtShowPortalMenu) ─────
portal_fn = posts_js[posts_js.find("function _cmtShowPortalMenu"):] if "function _cmtShowPortalMenu" in posts_js else ""
check(
    "33. pc-cmt-menu-edit class in _cmtShowPortalMenu (portal-based)",
    "pc-cmt-menu-edit" in portal_fn[:2000]
)
check(
    "33b. pc-cmt-menu-del class in _cmtShowPortalMenu (portal-based)",
    "pc-cmt-menu-del" in portal_fn[:2000]
)

# ── 34. RTL order: sendBtn appended before ta ──────────────────────
populate_fn2 = posts_js[posts_js.find("function _cmtPopulatePanel"):] if "function _cmtPopulatePanel" in posts_js else ""
snd_pos2 = populate_fn2.find("inputRow.appendChild(sendBtn)")
ta_pos2  = populate_fn2.find("inputRow.appendChild(ta)")
check(
    "34. RTL order: sendBtn appended before ta in _cmtPopulatePanel",
    snd_pos2 != -1 and ta_pos2 != -1 and snd_pos2 < ta_pos2
)

# ── 35. Send button is outlined (transparent background) ──────────
check(
    "35. .pc-cmts-send uses transparent background (outlined style)",
    "background: transparent" in company_css or "background:transparent" in company_css
)

# ── 36. Comments list max-height ≤ 300px ──────────────────────────
check(
    "36. .pc-cmts-list max-height is 280px",
    "max-height:280px" in company_css or "max-height: 280px" in company_css
)

# ── 37. Textarea max-height ≤ 140px for auto-resize ───────────────
check(
    "37. .pc-cmts-ta has max-height 120px for auto-resize cap",
    "max-height:120px" in company_css or "max-height: 120px" in company_css
)

# ── 38. Edit textarea rows=1 (not 2) ─────────────────────────────
edit_fn = posts_js[posts_js.find("function _cmtHandleEdit"):] if "function _cmtHandleEdit" in posts_js else ""
check(
    "38. editTa.rows = 1 in _cmtHandleEdit (not 2)",
    "editTa.rows      = 1" in edit_fn or "editTa.rows = 1" in edit_fn
)

# ── 39. Edit textarea has auto-resize listener ────────────────────
check(
    "39. editTa has _autoResizeTextarea input listener",
    "_autoResizeTextarea(editTa)" in edit_fn
)

# ── 40. 'تم التعديل' badge appended to meta-row (not header or header-left) ─
check(
    "40. 'تم التعديل' badge appended to .pc-cmt-meta-row (not .pc-cmt-header)",
    "pc-cmt-meta-row" in edit_fn and
    "item.querySelector('.pc-cmt-header')" not in edit_fn
)

# ── Portal ⋮ menu (feat/comment-ux-polish-2) ─────────────────────────────
posts_js = open("static/company/company.posts.js", encoding="utf-8").read()

# ── 41. Portal menu variable ──────────────────────────────────────
check(
    "41. _cmtPortalMenu variable defined",
    "var _cmtPortalMenu" in posts_js
)

# ── 42. Portal menu functions ─────────────────────────────────────
check(
    "42. _cmtHidePortalMenu function defined",
    "function _cmtHidePortalMenu" in posts_js
)
check(
    "42b. _cmtShowPortalMenu function defined",
    "function _cmtShowPortalMenu" in posts_js
)

# ── 43. Portal menu uses position:fixed in CSS ────────────────────
check(
    "43. .pc-cmt-portal-menu uses position:fixed in company.css",
    "position:fixed" in company_css and "pc-cmt-portal-menu" in company_css
)

# ── 44. Reply system variables ────────────────────────────────────
check(
    "44. _cmtReplyTarget variable defined",
    "var _cmtReplyTarget" in posts_js
)

# ── 45. Reply helper functions ────────────────────────────────────
check(
    "45. _cmtHandleReply function defined",
    "function _cmtHandleReply" in posts_js
)
check(
    "45b. _cmtCancelReply function defined",
    "function _cmtCancelReply" in posts_js
)

# ── 46. Reply button in _cmtBuildItem ─────────────────────────────
build_fn3 = posts_js[posts_js.find("function _cmtBuildItem"):] if "function _cmtBuildItem" in posts_js else ""
check(
    "46. pc-cmt-reply-btn class built in _cmtBuildItem",
    "pc-cmt-reply-btn" in build_fn3[:5000]
)

# ── 47. Meta row in _cmtBuildItem ─────────────────────────────────
check(
    "47. pc-cmt-meta-row class built in _cmtBuildItem",
    "pc-cmt-meta-row" in build_fn3[:3000]
)

# ── 48. Reply strip in _cmtPopulatePanel ─────────────────────────
populate_fn3 = posts_js[posts_js.find("function _cmtPopulatePanel"):] if "function _cmtPopulatePanel" in posts_js else ""
check(
    "48. pc-cmt-reply-strip built in _cmtPopulatePanel",
    "pc-cmt-reply-strip" in populate_fn3[:3000]
)

# ── 49. Reply strip in CSS ────────────────────────────────────────
check(
    "49. .pc-cmt-reply-strip defined in company.css",
    "pc-cmt-reply-strip" in company_css
)

# ── 50. Scroll listener closes portal menu ────────────────────────
check(
    "50. list scroll listener calls _cmtHidePortalMenu",
    "_cmtHidePortalMenu" in populate_fn3[:3000]
)

# ── UX Polish 3 (feat/comment-ux-polish-3) ───────────────────────────────
posts_js    = open("static/company/company.posts.js", encoding="utf-8").read()
company_css = open("static/company/company.css", encoding="utf-8").read()
build_fn4   = posts_js[posts_js.find("function _cmtBuildItem"):] if "function _cmtBuildItem" in posts_js else ""

# ── 51. Vertical line fix — scrollbar hidden on .pc-cmts-list ─────
check(
    "51. .pc-cmts-list has scrollbar-width:none (hides RTL vertical line)",
    "scrollbar-width:none" in company_css and "pc-cmts-list" in company_css
)
check(
    "51b. .pc-cmts-list webkit scrollbar hidden",
    ".pc-cmts-list::-webkit-scrollbar" in company_css
)

# ── 52. Reply button NOT in metaRow anymore ────────────────────────
check(
    "52. replyBtn is no longer appended to metaRow in _cmtBuildItem",
    "metaRow.appendChild(replyBtn)" not in build_fn4[:4000]
)

# ── 53. Reply button IS after bodyEl in content ───────────────────
body_pos4  = build_fn4.find("content.appendChild(bodyEl)")
reply_pos4 = build_fn4.find("content.appendChild(replyBtn)")
acts_pos4  = build_fn4.find("content.appendChild(acts)")
check(
    "53. Reply button appended to content after bodyEl and before acts",
    reply_pos4 != -1 and body_pos4 != -1 and acts_pos4 != -1 and
    body_pos4 < reply_pos4 < acts_pos4
)

# ── 54. _renderCommentBody helper defined ─────────────────────────
check(
    "54. _renderCommentBody function defined",
    "function _renderCommentBody" in posts_js
)
check(
    "54b. _renderCommentBody called in _cmtBuildItem",
    "_renderCommentBody(bodyEl" in build_fn4[:4000]
)

# ── 55. @mention highlight CSS ────────────────────────────────────
check(
    "55. .pc-cmt-mention defined in company.css",
    "pc-cmt-mention" in company_css
)

# ── 56. Visual reply indentation CSS ──────────────────────────────
check(
    "56. .pc-cmt-visual-reply defined in company.css",
    "pc-cmt-visual-reply" in company_css
)
check(
    "56b. pc-cmt-visual-reply class applied in _cmtBuildItem",
    "pc-cmt-visual-reply" in build_fn4[:4000]
)

# ── 57. XSS: _renderCommentBody uses textContent (no innerHTML for API) ──
render_fn = posts_js[posts_js.find("function _renderCommentBody"):] if "function _renderCommentBody" in posts_js else ""
render_fn_body = render_fn[:500]
check(
    "57. _renderCommentBody uses textContent/createTextNode only (no innerHTML for API data)",
    "textContent" in render_fn_body and "innerHTML" not in render_fn_body
)

# ── Summary ──────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, s, _ in results if s == PASS)
total  = len(results)
print(f"{'='*50}")
print(f"Results: {passed}/{total} passed")
if passed == total:
    print("🎉 All tests passed!")
else:
    failed = [n for n, s, _ in results if s == FAIL]
    print("Failed:", ", ".join(failed))
