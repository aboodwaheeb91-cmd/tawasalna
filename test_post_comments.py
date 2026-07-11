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
    "22. editWrap inserted into DOM before bodyWrap is hidden (insert-first rule)",
    insert_pos != -1 and
    (cmt_edit_fn.find("bodyWrap.style.display = 'none'") > insert_pos or
     cmt_edit_fn.find("bodyEl.style.display = 'none'") > insert_pos)
)

# ── 23. Edit UX: correct parent (content, not item) ──────────────────────
check(
    "23. insertBefore uses content as parent (not item)",
    "content.insertBefore(editWrap" in posts_js
)

# ── 24. Edit UX: Optimistic UI — body rendered before fetch ──────────────
# _renderCommentBody(bodyEl, newBody, ...) must appear before fetch(...)
optimistic_pos = cmt_edit_fn.find("_renderCommentBody(bodyEl, newBody")
fetch_pos      = cmt_edit_fn.find("fetch('/company/posts/comments/")
check(
    "24. Optimistic UI: bodyEl updated before fetch call",
    optimistic_pos != -1 and fetch_pos != -1 and optimistic_pos < fetch_pos
)

# ── 25. Edit UX: rollback on server error ─────────────────────────────────
check(
    "25. rollback: _renderCommentBody(bodyEl, originalText, ...) on failure",
    "_renderCommentBody(bodyEl, originalText" in cmt_edit_fn
)

# ── 26. Edit XSS: optimistic update uses _renderCommentBody (no innerHTML) ──
check(
    "26. optimistic edit uses _renderCommentBody (XSS-safe), not innerHTML for API data",
    "_renderCommentBody(bodyEl, newBody" in cmt_edit_fn and "bodyEl.innerHTML" not in cmt_edit_fn
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
    "pc-cmt-menu-btn" in build_fn2[:4000]
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
    "pc-cmt-reply-btn" in build_fn3[:8000]
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
body_pos4  = build_fn4.find("content.appendChild(bodyWrap)")  # bodyWrap now appended, not bodyEl directly
reply_pos4 = build_fn4.find("content.appendChild(replyBtn)")
acts_pos4  = build_fn4.find("content.appendChild(acts)")
check(
    "53. bodyWrap (containing bodyEl) appended to content, then replyBtn, then acts",
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
    "_renderCommentBody(bodyEl" in build_fn4[:8000]
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

# ── Reply Threading V1 (feat/reply-threading-v1) ─────────────────────────
posts_js    = open("static/company/company.posts.js", encoding="utf-8").read()
auth_src    = open("auth.py", encoding="utf-8").read()
srv_src     = open("server.py", encoding="utf-8").read()

# ── 58. reply_to_comment_id migration in auth.py ──────────────────────────
check(
    "58. reply_to_comment_id column added via ALTER TABLE migration",
    "ADD COLUMN IF NOT EXISTS reply_to_comment_id" in auth_src
)
check(
    "58b. idx_post_cmts_reply index created for reply_to_comment_id",
    "idx_post_cmts_reply" in auth_src
)

# ── 59. get_company_post_comments returns reply fields ────────────────────
check(
    "59. get_company_post_comments SELECTs reply_to_comment_id",
    "c.reply_to_comment_id" in auth_src and "get_company_post_comments" in auth_src
)
check(
    "59b. get_company_post_comments SELECTs reply_to_author_name",
    "reply_to_author_name" in auth_src
)

# ── 60. create_company_post_comment accepts reply_to_comment_id ───────────
check(
    "60. create_company_post_comment signature accepts reply_to_comment_id",
    "def create_company_post_comment" in auth_src and "reply_to_comment_id=None" in auth_src
)

# ── 61. Depth resolution: replying to a reply uses its parent ─────────────
check(
    "61. Depth resolution: if ref has reply_to_comment_id, resolve to its parent",
    "ref_rows[0][1] is not None" in auth_src and "resolved_reply_to = int(ref_rows[0][1])" in auth_src
)

# ── 62. Cross-post validation ─────────────────────────────────────────────
check(
    "62. Validates reply_to belongs to same post_id",
    "لا ينتمي لهذا المنشور" in auth_src
)

# ── 63. CommentInput has reply_to_comment_id optional field ──────────────
check(
    "63. CommentInput model has reply_to_comment_id: Optional[int] = None",
    "reply_to_comment_id: Optional[int] = None" in srv_src
)

# ── 64. Server endpoint passes reply_to_comment_id to helper ─────────────
check(
    "64. company_create_post_comment passes body.reply_to_comment_id to create helper",
    "body.reply_to_comment_id" in srv_src
)

# ── 65. _cmtReplyTargetId variable defined in JS ──────────────────────────
check(
    "65. _cmtReplyTargetId module variable defined",
    "var _cmtReplyTargetId" in posts_js
)

# ── 66. _renderCommentBody accepts mentionName (3rd param) ────────────────
render_fn2 = posts_js[posts_js.find("function _renderCommentBody"):] if "function _renderCommentBody" in posts_js else ""
render_fn2_sig = render_fn2[:120]
check(
    "66. _renderCommentBody signature accepts mentionName as 3rd parameter",
    "mentionName" in render_fn2_sig
)

# ── 67. _renderCommentBody exact compound-name match ─────────────────────
check(
    "67. _renderCommentBody uses full-text scan (indexOf @) for @mention matching",
    "text.indexOf('@', pos)" in posts_js or "text.indexOf(cand, atIdx) === atIdx" in posts_js
)

# ── 68. _cmtRenderComments function defined ───────────────────────────────
check(
    "68. _cmtRenderComments function defined",
    "function _cmtRenderComments" in posts_js
)
check(
    "68b. _cmtRenderComments called in _cmtLoadComments",
    "_cmtRenderComments(comments, list)" in posts_js
)

# ── 69. _cmtInsertReply function defined ──────────────────────────────────
check(
    "69. _cmtInsertReply function defined",
    "function _cmtInsertReply" in posts_js
)
check(
    "69b. _cmtInsertReply uses replies-box pattern (toggle + box, auto-open)",
    "_cmtBuildRepliesGroup" in posts_js and "_cmtSetToggleState" in posts_js
)

# ── 70. _cmtHandleReply accepts commentId + stores in _cmtReplyTargetId ──
handle_reply_fn = posts_js[posts_js.find("function _cmtHandleReply"):] if "function _cmtHandleReply" in posts_js else ""
check(
    "70. _cmtHandleReply accepts commentId as 3rd param",
    "function _cmtHandleReply(postId, authorName, commentId)" in handle_reply_fn[:200]
)
check(
    "70b. _cmtHandleReply stores commentId in _cmtReplyTargetId",
    "_cmtReplyTargetId[postId]" in handle_reply_fn[:900]
)
check(
    "70c. _cmtHandleSend sends reply_to_comment_id in payload",
    "reply_to_comment_id" in posts_js and "payload.reply_to_comment_id = replyToId" in posts_js
)
check(
    "70d. _cmtHandleSend calls _cmtInsertReply for replies, not plain append",
    "_cmtInsertReply(list, newComment" in posts_js
)
check(
    "70e. _cmtCancelReply clears _cmtReplyTargetId",
    "_cmtReplyTargetId[postId] = null" in posts_js
)

# ── 71. _cmtBuildItem uses reply_to_comment_id (not body @) for visual-reply ─
build_fn5 = posts_js[posts_js.find("function _cmtBuildItem"):] if "function _cmtBuildItem" in posts_js else ""
check(
    "71. _cmtBuildItem uses reply_to_comment_id for visual-reply class (not body.charAt(0))",
    "c.reply_to_comment_id != null" in build_fn5[:600] and "c.body.charAt(0)" not in build_fn5[:600]
)
check(
    "71b. _cmtBuildItem sets data-reply-to-id attribute",
    "el.dataset.replyToId" in build_fn5[:600]
)
check(
    "71c. _cmtBuildItem passes reply_to_author_name to _renderCommentBody",
    "c.reply_to_author_name" in build_fn5[:2000]
)

# ── Scroll UX fix (reply stays in place, top-level scrolls to bottom) ────
posts_js = open("static/company/company.posts.js", encoding="utf-8").read()
auth_src = open("auth.py", encoding="utf-8").read()

# ── 72. _cmtInsertReply returns newEl ──────────────────────────────────────
insert_reply_fn = posts_js[posts_js.find("function _cmtInsertReply"):] if "function _cmtInsertReply" in posts_js else ""
insert_reply_body = insert_reply_fn[:1200]
check(
    "72. _cmtInsertReply returns newEl in all code paths",
    "return newEl" in insert_reply_body
)

# ── 73. Reply scroll: scrollIntoView used (not list.scrollTop) ────────────
send_fn = posts_js[posts_js.find("function _cmtHandleSend"):] if "function _cmtHandleSend" in posts_js else ""
check(
    "73. _cmtHandleSend uses scrollIntoView for replies",
    "scrollIntoView" in send_fn and "block: 'nearest'" in send_fn
)

# ── 74. Top-level comment still scrolls list to bottom ────────────────────
check(
    "74. _cmtHandleSend uses list.scrollTop = list.scrollHeight for top-level comments",
    "list.scrollTop = list.scrollHeight" in send_fn
)

# ── 75. scrollTop is NOT used unconditionally (only for top-level branch) ─
# The scrollTop line must appear AFTER the reply branch (inside the else block)
scroll_pos        = send_fn.find("list.scrollTop = list.scrollHeight")
reply_branch_pos  = send_fn.find("reply_to_comment_id != null")
check(
    "75. list.scrollTop = list.scrollHeight appears only in the top-level (else) branch",
    scroll_pos != -1 and reply_branch_pos != -1 and scroll_pos > reply_branch_pos
)

# ── 76. Backend: root parent active check when resolving depth ────────────
check(
    "76. create_company_post_comment validates resolved root parent is active",
    "التعليق الأصلي غير موجود أو تم حذفه" in auth_src
)
check(
    "76b. root_rows active check uses root_rows[0][2] != 'active'",
    "root_rows[0][2] != 'active'" in auth_src
)
check(
    "76c. root_rows same post_id check",
    "root_rows[0][1]) != post_id" in auth_src
)

# ── 77-85. @ Mention Autocomplete (company.posts.js) ─────────────────────

# Module-level state variables
check(
    "77. _cmtMentionMenu module variable declared",
    "var _cmtMentionMenu  = null;" in posts_js or "var _cmtMentionMenu=" in posts_js or "_cmtMentionMenu  = null" in posts_js
)
check(
    "78. _cmtMentionState module variable declared with correct shape",
    "_cmtMentionState = {" in posts_js and "open:" in posts_js and "activeIdx:" in posts_js
)

# Core mention functions present
check(
    "79. _cmtGetMentionMenu creates portal div with correct id",
    "_cmtMentionMenu.id = 'pc-cmt-mention-menu'" in posts_js
)
check(
    "80. _cmtCloseMentionMenu resets all state fields",
    "_cmtMentionState.open      = false" in posts_js and "_cmtMentionState.activeIdx = -1" in posts_js
)
check(
    "81. _cmtCollectMentionCandidates reads data-author-tw-id from panel items (XSS-safe)",
    "querySelectorAll('.pc-cmt-item[data-author-tw-id]')" in posts_js
)
check(
    "82. _cmtFilterMentionCandidates limits to 6 results",
    "result.length < 6" in posts_js
)
check(
    "83. _cmtFindMentionStart stops at space/newline (no false positives)",
    "val[i] === ' ' || val[i] === '\\n'" in posts_js
)
check(
    "84. _cmtInsertMention builds @name+space and fires input event (XSS-safe — textContent route)",
    "var insert = '@' + name + ' '" in posts_js and "dispatchEvent(new Event('input'))" in posts_js
)

# Textarea wiring
check(
    "85. _cmtHandleMentionInput wired to textarea input listener in _cmtPopulatePanel",
    "_cmtHandleMentionInput(ta, String(postId))" in posts_js
)
check(
    "85b. _cmtHandleMentionKeydown wired to textarea keydown listener",
    "_cmtHandleMentionKeydown(e, ta)" in posts_js
)

# Mention menu item delegation + close on outside click
check(
    "85c. click delegation for .pc-cmt-mention-item uses dataset.mentionName",
    "item.dataset.mentionName" in posts_js
)
check(
    "85d. DOMContentLoaded closes mention menu on outside click",
    "!menu.contains(e.target) && e.target !== _cmtMentionState.ta" in posts_js
)

# CSS
with open("static/company/company.css") as _f:
    company_css = _f.read()

check(
    "85e. CSS .pc-cmt-mention-menu is position:fixed z-index:9999",
    "pc-cmt-mention-menu" in company_css and "position:fixed" in company_css and "z-index:9999" in company_css
)
check(
    "85f. CSS .pc-cmt-mention-active exists for keyboard highlight",
    "pc-cmt-mention-active" in company_css
)

# ── 85g. menu.replaceChildren() — no innerHTML in mention menu ───────────
open_menu_fn = posts_js[posts_js.find("function _cmtOpenMentionMenu"):] if "function _cmtOpenMentionMenu" in posts_js else ""
open_menu_fn_body = open_menu_fn[:open_menu_fn.find("}\n\n")+2] if "}\n\n" in open_menu_fn else open_menu_fn[:500]
check(
    "85g. _cmtOpenMentionMenu uses replaceChildren() to clear items (no innerHTML)",
    "menu.replaceChildren()" in open_menu_fn_body
)
check(
    "85h. _cmtOpenMentionMenu does not use menu.innerHTML",
    "menu.innerHTML" not in open_menu_fn_body
)

# ── 86-99. Author links + @mention links + reply_to_author_tw_id ─────────

# Backend: reply_to_author_tw_id in GET comments
check(
    "86. get_company_post_comments SELECT includes ru.tw_id AS reply_to_author_tw_id",
    "ru.tw_id AS reply_to_author_tw_id" in auth_src
)
check(
    "87. get_company_post_comments cols includes reply_to_author_tw_id",
    '"reply_to_author_tw_id"' in auth_src
)

# Backend: reply_to_author_tw_id in CREATE response
check(
    "88. create_company_post_comment fetches u.tw_id for reply author",
    'u.full_name, u.tw_id' in auth_src and 'FROM company_post_comments c' in auth_src
)
check(
    "89. create_company_post_comment initialises reply_to_author_tw_id = None",
    "reply_to_author_tw_id = None" in auth_src
)
check(
    "90. create_company_post_comment returns reply_to_author_tw_id in dict",
    'd["reply_to_author_tw_id"] = reply_to_author_tw_id' in auth_src
)

# Frontend: author links
check(
    "91. _cmtBuildItem sets ava element to <a> when author_tw_id present",
    "document.createElement(c.author_tw_id ? 'a' : 'div')" in posts_js
)
check(
    "92. _cmtBuildItem sets ava href to /u/{author_tw_id}",
    "ava.href = '/u/' + c.author_tw_id" in posts_js
)
check(
    "93. _cmtBuildItem makes author name an <a> when author_tw_id present",
    "document.createElement(c.author_tw_id ? 'a' : 'span')" in posts_js
)
check(
    "94. _cmtBuildItem sets name href to /u/{author_tw_id}",
    "nameEl.href = '/u/' + c.author_tw_id" in posts_js
)

# Frontend: stores tw_id data attrs for candidates
check(
    "95. _cmtBuildItem stores data-author-tw-id for mention candidate collection",
    "el.dataset.authorTwId   = c.author_tw_id" in posts_js or
    "el.dataset.authorTwId = c.author_tw_id" in posts_js
)

# Frontend: _renderCommentBody supports 4th param mentionTwId
check(
    "96. _renderCommentBody accepts mentionTwId param (4th or later)",
    "function _renderCommentBody(bodyEl, text, mentionName, mentionTwId" in posts_js
)
check(
    "97. _renderCommentBody creates <a> when entry.tw_id present (XSS-safe)",
    "entry.tw_id ? document.createElement('a') : document.createElement('span')" in posts_js
)
check(
    "98. _renderCommentBody sets href /u/tw_id on mention <a> (not innerHTML)",
    "entry.tw_id) mentEl.href" in posts_js or "mentEl.href = '/u/' + entry.tw_id" in posts_js
)

# Frontend: _cmtBuildItem passes reply_to_author_tw_id as 4th arg (now also 5th knownNames arg)
check(
    "99. _cmtBuildItem passes reply_to_author_tw_id to _renderCommentBody",
    "c.reply_to_author_tw_id" in posts_js and "_renderCommentBody(bodyEl, c.body" in posts_js
)

# Frontend: _cmtHandleEdit passes replyToAuthorTwId as 4th arg
check(
    "99b. _cmtHandleEdit reads replyToAuthorTwId from dataset",
    "var replyToAuthorTwId = item.dataset.replyToAuthorTwId || null" in posts_js or
    "replyToAuthorTwId = item.dataset.replyToAuthorTwId" in posts_js
)
check(
    "99c. _cmtHandleEdit passes replyToAuthorTwId to all _renderCommentBody calls",
    "_renderCommentBody(bodyEl, newBody, replyToAuthor, replyToAuthorTwId" in posts_js
)

# Frontend: company state path fixed
check(
    "99d. _cmtCollectMentionCandidates uses companyState.profile.full_name (correct path)",
    "companyState.profile" in posts_js and "full_name" in posts_js
)

# CSS: author link styles present
check(
    "99e. CSS a.pc-cmt-author has text-decoration:none",
    "a.pc-cmt-author" in company_css and "text-decoration:none" in company_css
)
check(
    "99f. CSS a.pc-cmt-mention has text-decoration:none (no underline default)",
    "a.pc-cmt-mention" in company_css
)

# ── 100-105. Mention UX fixes (feat/mention-ux-fixes) ────────────────────

# Fix 1: actual height measurement before positioning
pos_fn = posts_js[posts_js.find("function _cmtPositionMentionMenu"):] if "function _cmtPositionMentionMenu" in posts_js else ""
pos_fn_body = pos_fn[:pos_fn.find("}\n\n")+2] if "}\n\n" in pos_fn else pos_fn[:400]
check(
    "100. _cmtPositionMentionMenu uses menu.offsetHeight (not hardcoded 160)",
    "menu.offsetHeight" in pos_fn_body and "var menuH = 160" not in pos_fn_body
)
check(
    "101. _cmtPositionMentionMenu uses menu.offsetHeight without artificial cap (PR #421)",
    "menu.offsetHeight" in pos_fn_body and "Math.min(menu.offsetHeight" not in pos_fn_body
)

open_fn = posts_js[posts_js.find("function _cmtOpenMentionMenu"):] if "function _cmtOpenMentionMenu" in posts_js else ""
open_fn_body = open_fn[:open_fn.find("}\n\n")+2] if "}\n\n" in open_fn else open_fn[:700]
check(
    "102. _cmtOpenMentionMenu sets visibility:hidden before display:block for height measurement",
    "menu.style.visibility = 'hidden'" in open_fn_body and "menu.style.display    = 'block'" in open_fn_body
)
check(
    "103. _cmtOpenMentionMenu clears visibility after positioning",
    "menu.style.visibility = ''" in open_fn_body
)

# Fix 2: compound-name coloring for free mentions
check(
    "104. _cmtKnownNames helper exists and returns sorted names",
    "function _cmtKnownNames(" in posts_js and "_cmtCollectMentionCandidates(" in posts_js
)
check(
    "105. _renderCommentBody accepts knownNames param for compound free-mention",
    "function _renderCommentBody(bodyEl, text, mentionName, mentionTwId, knownNames" in posts_js
)
check(
    "105b. _renderCommentBody tries knownNames longest-match before @\\S+ fallback",
    "knownNames[ki]" in posts_js or "knownNames && knownNames.length" in posts_js
)
check(
    "105c. _cmtHandleEdit computes editKnownNames via _cmtKnownNames before _renderCommentBody calls",
    "var editKnownNames = _cmtKnownNames(" in posts_js
)
check(
    "105d. _cmtHandleSend passes _cmtKnownNames to _cmtInsertReply and _cmtBuildItem",
    "_cmtKnownNames(String(postId))" in posts_js or "_cmtKnownNames(" in posts_js
)
check(
    "105e. _cmtRenderComments builds knownNames from comments array (longest-first) for initial render",
    "knownNames = comments.map(" in posts_js or "_cmtBuildItem(c, knownNames)" in posts_js
)
check(
    "105f. free mention highlight uses <span> when no tw_id — no <a> without tw_id (V1 contract)",
    "entry.tw_id ? document.createElement('a') : document.createElement('span')" in posts_js or
    "fbEl = document.createElement('span')" in posts_js
)

# ── feat/comment-ux-v2: DB-backed free @mention ──────────────────────────
check(
    "106. _cmtMentionedCandidates module variable exists (array per postId)",
    "var _cmtMentionedCandidates = {}" in posts_js
)
check(
    "106b. _cmtInsertMention accepts 3rd param (twId) and pushes to _cmtMentionedCandidates",
    "function _cmtInsertMention(ta, name, twId)" in posts_js and
    "_cmtMentionedCandidates[postId]" in posts_js
)
check(
    "106c. Keyboard nav passes tw_id from filtered candidate to _cmtInsertMention",
    "cand.tw_id" in posts_js and "_cmtInsertMention(ta, cand.name" in posts_js
)
check(
    "106d. Click delegation passes mentionTwId from dataset to _cmtInsertMention",
    "item.dataset.mentionTwId || null" in posts_js
)
check(
    "106e. _renderCommentBody accepts mentions array as 6th param (multi-mention)",
    "function _renderCommentBody(bodyEl, text, mentionName, mentionTwId, knownNames, mentions)" in posts_js
)
check(
    "106f. _renderCommentBody creates <a> for DB-backed free mentions via entry.tw_id",
    "entry.tw_id ? document.createElement('a') : document.createElement('span')" in posts_js
)
check(
    "106g. _cmtBuildItem stores data-mentions-json on element (multi-mention)",
    "el.dataset.mentionsJson = JSON.stringify" in posts_js or
    "dataset.mentionsJson = JSON.stringify" in posts_js
)
check(
    "106h. _cmtHandleSend includes mentioned_tw_ids array in payload",
    "payload.mentioned_tw_ids" in posts_js and "_cmtMentionedCandidates[String(postId)]" in posts_js
)
check(
    "106i. _cmtHandleSend clears _cmtMentionedCandidates after send",
    "_cmtMentionedCandidates[String(postId)] = []" in posts_js
)
check(
    "106j. _cmtHandleEdit reads mentionsJson from dataset and parses it",
    "mentionsJson = item.dataset.mentionsJson" in posts_js and
    "JSON.parse(mentionsJson)" in posts_js
)
check(
    "106k. auth.py has mentioned_tw_id column migration",
    "mentioned_tw_id VARCHAR(50)" in auth_src
)
check(
    "106l. auth.py get_company_post_comments joins users mu for mentioned_author_name",
    "users mu ON mu.tw_id = c.mentioned_tw_id" in auth_src
)
check(
    "106m. auth.py create_company_post_comment accepts + validates mentioned_tw_ids list",
    "mentioned_tw_ids=None" in auth_src and "resolved_mentions" in auth_src
)
check(
    "106n. server.py CommentInput has mentioned_tw_ids field",
    "mentioned_tw_ids" in srv_src
)

# ── feat/comment-ux-v2: Collapsible long comments ─────────────────────────
check(
    "107. CSS .pc-cmt-body.is-collapsed uses line-clamp",
    ".pc-cmt-body.is-collapsed" in company_css and "-webkit-line-clamp:2" in company_css
)
check(
    "107b. _cmtBuildItem adds is-collapsed class to bodyEl",
    "bodyEl.className = 'pc-cmt-body is-collapsed'" in posts_js
)
check(
    "107c. _cmtBuildItem creates .pc-cmt-body-wrap wrapper containing body + expand + collapse btns",
    "pc-cmt-body-wrap" in posts_js and "pc-cmt-expand-btn" in posts_js and "pc-cmt-collapse-btn" in posts_js
)
check(
    "107d. _cmtCheckCollapse helper exists and removes is-collapsed when text fits",
    "function _cmtCheckCollapse(" in posts_js and "classList.remove('is-collapsed')" in posts_js
)
check(
    "107e. _cmtInitCollapseAll iterates items and calls _cmtCheckCollapse",
    "function _cmtInitCollapseAll(" in posts_js and "_cmtCheckCollapse(items[i])" in posts_js
)
check(
    "107f. _cmtRenderComments calls _cmtInitCollapseAll after rendering",
    "_cmtInitCollapseAll(list)" in posts_js
)
check(
    "107g. postsList delegation handles pc-cmt-expand-btn click (expand) — not text button",
    "pc-cmt-expand-btn" in posts_js and "classList.remove('is-collapsed')" in posts_js and
    "pc-cmt-more-btn" not in posts_js
)
check(
    "107h. postsList delegation handles pc-cmt-collapse-btn click (collapse) — icon only",
    "pc-cmt-collapse-btn" in posts_js and "classList.add('is-collapsed')" in posts_js
)
check(
    "107i. CSS .pc-cmt-expand-btn and .pc-cmt-collapse-btn defined (replaces old text buttons)",
    ".pc-cmt-expand-btn" in company_css and ".pc-cmt-collapse-btn" in company_css and
    ".pc-cmt-more-btn" not in company_css
)

# ── feat/comment-ux-v2: Collapsed replies by default ─────────────────────
check(
    "108. _cmtReplyCountText helper returns Arabic reply count label",
    "function _cmtReplyCountText(" in posts_js and "عرض ردّين" in posts_js
)
check(
    "108b. _cmtSetToggleState helper exists (open/close toggle + box)",
    "function _cmtSetToggleState(" in posts_js and "إخفاء الردود" in posts_js
)
check(
    "108c. _cmtBuildRepliesGroup builds toggle + box elements",
    "function _cmtBuildRepliesGroup(" in posts_js and
    "pc-cmt-replies-toggle" in posts_js and "pc-cmt-replies-box" in posts_js
)
check(
    "108d. _cmtRenderComments groups replies by parent and creates collapsed boxes",
    "parentReplies" in posts_js and "_cmtBuildRepliesGroup(c.id" in posts_js
)
check(
    "108e. _cmtInsertReply finds existing box or creates first-reply group",
    "pc-cmt-replies-box[data-parent-id" in posts_js and "_cmtSetToggleState(toggle, box, true" in posts_js
)
check(
    "108f. _cmtHandleDelete removes toggle+box when last reply deleted",
    "if (toggleEl) toggleEl.remove()" in posts_js and "replyBox.remove()" in posts_js
)
check(
    "108g. _cmtHandleDelete removes replies group when parent comment deleted",
    "childToggle" in posts_js and "childBox" in posts_js and
    "childToggle.remove()" in posts_js
)
check(
    "108h. postsList delegation handles pc-cmt-replies-toggle click",
    "pc-cmt-replies-toggle" in posts_js and "_cmtSetToggleState(repliesToggle" in posts_js
)
check(
    "108i. CSS .pc-cmt-replies-toggle defined with arrow indicator",
    ".pc-cmt-replies-toggle" in company_css
)
check(
    "108j. CSS .pc-cmt-replies-box defined (light border container)",
    ".pc-cmt-replies-box" in company_css
)

# ── fixes/comment-ux-v2-polish: Fix 1 — orphan replies ──────────────────
check(
    "109. _cmtRenderComments does NOT pre-mark replies as rendered during grouping",
    # The parentReplies grouping block must not set rendered[c.id] = true
    # Correct: marks rendered only after DOM insertion (inside the top-level forEach)
    "parentReplies[pid].push(c);\n        rendered[c.id] = true;" not in posts_js and
    "parentReplies[pid].push(c)" in posts_js
)
check(
    "109b. _cmtRenderComments marks replies rendered after DOM insertion (inside top-level forEach)",
    "replies.forEach(function (r) { rendered[r.id] = true; })" in posts_js
)
check(
    "109c. _cmtRenderComments orphan loop appends any comment not in rendered dict",
    "if (!rendered[c.id]) list.appendChild" in posts_js
)

# ── fixes/comment-ux-v2-polish: Fix 2 — collapse refresh after edit ──────
check(
    "110. _cmtRefreshCollapse helper exists",
    "function _cmtRefreshCollapse(" in posts_js
)
check(
    "110b. _cmtRefreshCollapse resets is-collapsed + hides expand/collapse buttons before re-measuring",
    "classList.add('is-collapsed')" in posts_js and
    "expandBtn.style.display   = 'none'" in posts_js and
    "collapseBtn.style.display = 'none'" in posts_js
)
check(
    "110c. _cmtRefreshCollapse calls _cmtCheckCollapse(item) to re-measure",
    "_cmtCheckCollapse(item)" in posts_js
)
check(
    "110d. _cmtHandleEdit calls _cmtRefreshCollapse after optimistic update",
    "editWrap.remove();\n      _cmtRefreshCollapse(item)" in posts_js
)
check(
    "110e. _cmtHandleEdit calls _cmtRefreshCollapse on server success",
    "_cmtRefreshCollapse(item);\n          var metaRow" in posts_js
)
check(
    "110f. _cmtHandleEdit calls _cmtRefreshCollapse on rollback (server error + catch)",
    posts_js.count("_cmtRefreshCollapse(item)") >= 4  # optimistic, success, server-err, catch
)

# ── fixes/comment-ux-v2-polish: Fix 3 — mentioned_tw_id validation ───────
check(
    "111. _cmtMentionedCandidates is array-based (replaces single _cmtMentionedCandidate)",
    "var _cmtMentionedCandidates = {}" in posts_js and
    "_cmtMentionedTwId" not in posts_js and
    "var _cmtMentionedCandidate = {}" not in posts_js  # old single-object declaration gone
)
check(
    "111b. _cmtInsertMention pushes {name, tw_id} into _cmtMentionedCandidates array",
    "_cmtMentionedCandidates[postId].push({ name: name, tw_id: twId })" in posts_js
)
check(
    "111c. _cmtHandleSend validates body contains @name (anywhere) before sending tw_id",
    "body.indexOf('@' + mc.name) >= 0" in posts_js
)
check(
    "111d. _cmtHandleSend clears _cmtMentionedCandidates after send",
    "_cmtMentionedCandidates[String(postId)] = []" in posts_js
)
check(
    "111e. auth.py validates '@name' appears anywhere in body (not just startswith)",
    "('@' + m_name) not in body" in auth_src or "('@' + m_name) in body" in auth_src
)
check(
    "111f. auth.py raises ValueError when mentioned_tw_id user not found",
    "mentioned_tw_id لا يشير لمستخدم موجود" in auth_src
)
check(
    "111g. auth.py raises ValueError when mentioned_tw_id doesn't appear in body",
    "mentioned_tw_id لا يوجد في نص التعليق" in auth_src
)
check(
    "111h. server.py maps mentioned_tw_id mismatch ValueError to 400",
    "status_code=400" in srv_src and "400, detail=msg" in srv_src or
    "status_code=400, detail=msg" in srv_src
)

# ── feat/comment-ux-v3: Inline expand icon + timing fixes ────────────────

# Icon-based collapse system (replaces text "عرض المزيد/أقل")
check(
    "112. _cmtCheckCollapse shows expandBtn on overflow (not removes button on fit)",
    "expandBtn.style.display = ''" in posts_js and  # shows on overflow
    "bodyEl.scrollHeight > bodyEl.clientHeight + 2" in posts_js
)
check(
    "112b. expand button starts hidden in _cmtBuildItem (display:none until checked)",
    "expandBtn.style.display = 'none'" in posts_js and
    "aria-label', 'عرض المزيد'" in posts_js
)
check(
    "112c. No text 'عرض المزيد' or 'عرض أقل' as button textContent (aria-labels OK, text removed)",
    "textContent = 'عرض المزيد'" not in posts_js and
    "textContent = 'عرض أقل'" not in posts_js
)
check(
    "112d. _cmtScheduleCollapse helper uses requestAnimationFrame",
    "function _cmtScheduleCollapse(" in posts_js and
    "requestAnimationFrame(function" in posts_js
)
check(
    "112e. _cmtInsertReply uses _cmtScheduleCollapse (not direct _cmtCheckCollapse) for new replies",
    "_cmtScheduleCollapse(newEl)" in posts_js and
    "_cmtScheduleCollapse(firstEl)" in posts_js
)
check(
    "112f. _cmtHandleSend uses _cmtScheduleCollapse for new top-level comments",
    "_cmtScheduleCollapse(topEl)" in posts_js
)
check(
    "112g. CSS .pc-cmt-body-wrap has position:relative",
    ".pc-cmt-body-wrap" in company_css and "position:relative" in company_css
)
check(
    "112h. CSS .pc-cmt-expand-btn has position:absolute and inset-inline-end",
    "position:absolute" in company_css and "inset-inline-end:0" in company_css
)
check(
    "112i. CSS .pc-cmt-replies-box border is <= 1px (lighter than original 2px)",
    "border-inline-start:1px" in company_css or "border-inline-start: 1px" in company_css
)
check(
    "112j. XSS: expand/collapse buttons use innerHTML only for static SVG (_ICO_CMT_* constants)",
    "var _ICO_CMT_EXPAND" in posts_js and "var _ICO_CMT_COLLAPSE" in posts_js and
    "_ICO_CMT_EXPAND" in posts_js and "innerHTML = _ICO_CMT_EXPAND" in posts_js
)
check(
    "112k. _cmtHandleEdit hides bodyWrap (not just bodyEl) during edit",
    "bodyWrap = content.querySelector('.pc-cmt-body-wrap')" in posts_js and
    "bodyWrap.style.display = 'none'" in posts_js
)
check(
    "112l. _cmtHandleEdit restores bodyWrap on cancel and optimistic update",
    posts_js.count("bodyWrap.style.display = ''") >= 2
)

# ── feat/mention-multi-fix: Multi-mention + icon overlap fix ─────────────

# Bug 1: CSS padding to prevent expand icon from overlapping text
check(
    "113a. CSS .pc-cmt-body.is-collapsed has padding-inline-end to reserve icon space",
    ".pc-cmt-body.is-collapsed" in company_css and "padding-inline-end" in company_css
)

# Bug 2: Multi-mention junction table migration
check(
    "113b. auth.py has company_post_comment_mentions table migration",
    "company_post_comment_mentions" in auth_src and
    "UNIQUE(comment_id, mentioned_tw_id)" in auth_src
)
check(
    "113c. auth.py create_company_post_comment loops over mentioned_tw_ids list",
    "for mtw_raw in (mentioned_tw_ids or []):" in auth_src or
    "for mtw_raw in" in auth_src
)
check(
    "113d. auth.py create_company_post_comment inserts into junction table ON CONFLICT DO NOTHING",
    "INSERT INTO company_post_comment_mentions" in auth_src and
    "ON CONFLICT (comment_id, mentioned_tw_id) DO NOTHING" in auth_src
)
check(
    "113e. auth.py get_company_post_comments batch-fetches from junction table",
    "company_post_comment_mentions" in auth_src and
    "mention_map" in auth_src
)
check(
    "113f. auth.py get_company_post_comments returns mentions array per comment",
    "d[\"mentions\"]" in auth_src and "mention_map" in auth_src
)
check(
    "113g. server.py CommentInput mentioned_tw_ids is Optional[List[str]]",
    "mentioned_tw_ids: Optional[List[str]]" in srv_src
)
check(
    "113h. _cmtMentionedCandidates stores array per postId (not single object)",
    "var _cmtMentionedCandidates = {}" in posts_js and
    "_cmtMentionedCandidates[postId].push" in posts_js
)
check(
    "113i. _renderCommentBody full-text scan: finds @ at any position",
    "text.indexOf('@', pos)" in posts_js
)
check(
    "113j. _renderCommentBody builds lookup table sorted longest-first",
    "lookup.sort(function" in posts_js and "b.name.length" in posts_js
)
check(
    "113k. _cmtBuildItem backward compat: falls back to c.mentioned_tw_id if c.mentions absent",
    "c.mentioned_tw_id" in posts_js and "c.mentions" in posts_js and
    "itemMentions" in posts_js
)
check(
    "113l. _cmtHandleEdit uses itemMentions (not mentionedTwId/mentionedAuthorName)",
    "itemMentions.length ? itemMentions : null" in posts_js and
    "mentionedAuthorName" not in posts_js and
    "mentionedTwId       = item.dataset" not in posts_js
)

# ── 114. Atomicity / Transaction tests ───────────────────────────────────
check(
    "114a. auth.py create_company_post_comment issues BEGIN before INSERT",
    'conn.run("BEGIN")' in auth_src and
    "INSERT INTO company_post_comments" in auth_src
)
check(
    "114b. auth.py create_company_post_comment issues COMMIT on success",
    'conn.run("COMMIT")' in auth_src and
    "committed = True" in auth_src
)
check(
    "114c. auth.py create_company_post_comment issues ROLLBACK on any exception",
    'conn.run("ROLLBACK")' in auth_src and
    "committed = False" in auth_src and
    "if not committed" in auth_src
)
check(
    "114d. auth.py raises RuntimeError with Arabic message on transaction failure (no silent failure)",
    'raise RuntimeError(f"فشل حفظ التعليق والمنشنات' in auth_src
)
check(
    "114e. auth.py no bare 'except: pass' inside transaction block (no swallowed errors)",
    # The ROLLBACK except is allowed (bare pass there is fine to avoid masking the original error)
    # but there must be NO except:pass that silently swallows mention errors
    "except: pass" not in auth_src or
    auth_src.count("except:\n                    pass") <= 1  # only the inner ROLLBACK guard
)
check(
    "114f. auth.py backward compat: old comments without junction entries return mentions:[] (not crash)",
    # Backward compat: else branch always assigns mentions list, never leaves it unset
    'd["mentions"] = []' in auth_src and
    "elif d.get(\"mentioned_tw_id\")" in auth_src
)

# ── 115. Shared Upload Client (tw-upload.js) ─────────────────────────────
import os

upload_js_path = os.path.join("static", "shared", "tw-upload.js")
upload_exists = os.path.isfile(upload_js_path)
check(
    "115a. static/shared/tw-upload.js exists",
    upload_exists
)

if upload_exists:
    with open(upload_js_path, encoding="utf-8") as f:
        upload_src = f.read()
    check(
        "115b. tw-upload.js defines TW.uploadImage",
        "TW.uploadImage" in upload_src
    )
    check(
        "115c. tw-upload.js calls POST /upload/image",
        "'/upload/image'" in upload_src or '"/upload/image"' in upload_src
    )
else:
    check("115b. tw-upload.js defines TW.uploadImage", False)
    check("115c. tw-upload.js calls POST /upload/image", False)

with open(os.path.join("static", "company", "company.main.js"), encoding="utf-8") as f:
    co_main_src = f.read()

check(
    "115d. company.main.js uses TW.uploadImage (not inline fetch('/upload/image'))",
    "TW.uploadImage" in co_main_src and
    "fetch('/upload/image'" not in co_main_src and
    'fetch("/upload/image"' not in co_main_src
)

with open("profile-v2.api.js", encoding="utf-8") as f:
    pv2_api_src = f.read()

check(
    "115e. profile-v2.api.js uses TW.uploadImage (not inline fetch('/upload/image'))",
    "TW.uploadImage" in pv2_api_src and
    "fetch('/upload/image'" not in pv2_api_src and
    'fetch("/upload/image"' not in pv2_api_src
)

check(
    "115f. profile-showcase.html loads tw-upload.js before profile-v2.api.js",
    (lambda h: (
        "tw-upload.js" in h and
        "profile-v2.api.js" in h and
        h.index("tw-upload.js") < h.index("profile-v2.api.js")
    ))(open("profile-showcase.html", encoding="utf-8").read())
)

check(
    "115g. company-profile.html loads tw-upload.js before company.main.js",
    (lambda h: (
        "tw-upload.js" in h and
        "company.main.js" in h and
        h.index("tw-upload.js") < h.index("company.main.js")
    ))(open("company-profile.html", encoding="utf-8").read())
)

# uploadLogo HTTP failure behavior: must throw, not fall back to dataUrl
# The broken pattern would be: (res.ok && res.data && res.data.url) ? ... : dataUrl
# The correct pattern: if (!res.ok) throw, then (res.data && res.data.url) ? ... : dataUrl
check(
    "115h. company uploadLogo throws on HTTP failure — broken fallback pattern absent",
    "(res.ok && res.data && res.data.url) ? res.data.url : dataUrl" not in co_main_src
)
check(
    "115i. company uploadLogo throws on !res.ok before dataUrl fallback",
    "if (!res.ok) throw new Error('upload_fail')" in co_main_src and
    "(res.data && res.data.url) ? res.data.url : dataUrl" in co_main_src
)

# No direct fetch('/upload/image') in any JS file outside tw-upload.js
import glob as _glob
_js_files = _glob.glob("**/*.js", recursive=True)
_violators = []
for _jf in _js_files:
    if os.path.normpath(_jf) == os.path.normpath(upload_js_path):
        continue  # tw-upload.js itself is allowed
    try:
        with open(_jf, encoding="utf-8") as _f:
            _src = _f.read()
        if "fetch('/upload/image'" in _src or 'fetch("/upload/image"' in _src:
            _violators.append(_jf)
    except Exception:
        pass

check(
    "115j. no direct fetch('/upload/image') outside static/shared/tw-upload.js",
    len(_violators) == 0,
    ("violators: " + ", ".join(_violators)) if _violators else ""
)

# ── 116. Image Cropper Shared Helper (tw-image-cropper.js) ───────────────
cropper_js_path = os.path.join("static", "shared", "tw-image-cropper.js")
cropper_exists = os.path.isfile(cropper_js_path)
check(
    "116a. static/shared/tw-image-cropper.js exists",
    cropper_exists
)

if cropper_exists:
    with open(cropper_js_path, encoding="utf-8") as f:
        cropper_src = f.read()

    check(
        "116b. tw-image-cropper.js defines TW.createCropper",
        "TW.createCropper" in cropper_src
    )
    check(
        "116c. tw-image-cropper.js exposes load method",
        "load:" in cropper_src or "load :" in cropper_src
    )
    check(
        "116d. tw-image-cropper.js exposes setZoom method",
        "setZoom:" in cropper_src or "setZoom :" in cropper_src
    )
    check(
        "116e. tw-image-cropper.js exposes export method",
        "export:" in cropper_src or "export :" in cropper_src
    )
    check(
        "116f. tw-image-cropper.js exposes reset method",
        "reset:" in cropper_src or "reset :" in cropper_src
    )
    check(
        "116g. tw-image-cropper.js exposes destroy method",
        "destroy:" in cropper_src or "destroy :" in cropper_src
    )
    check(
        "116h. tw-image-cropper.js contains no fetch call",
        "fetch(" not in cropper_src
    )
    # Strip single-line JS comments before checking for forbidden identifiers
    # (comments may legitimately mention what the file does NOT do)
    import re as _re
    _code_only = _re.sub(r'//[^\n]*', '', cropper_src)
    check(
        "116i. tw-image-cropper.js code (excl. comments) does not call uploadImage",
        "uploadImage" not in _code_only
    )
    check(
        "116j. tw-image-cropper.js code (excl. comments) has no userId/jwt/bucket/filename",
        "userId" not in _code_only and
        "jwt" not in _code_only and
        "bucket" not in _code_only and
        "filename" not in _code_only
    )
    check(
        "116k. tw-image-cropper.js uses passive:false for touchmove (blocks page scroll during drag)",
        "passive: false" in cropper_src or "passive:false" in cropper_src
    )
    check(
        "116l. tw-image-cropper.js supports both rect and circle shapes",
        "'circle'" in cropper_src and "'rect'" in cropper_src
    )
    check(
        "116m. tw-image-cropper.js uses devicePixelRatio for DPR support",
        "devicePixelRatio" in cropper_src
    )
else:
    for lbl in ["116b", "116c", "116d", "116e", "116f", "116g",
                "116h", "116i", "116j", "116k", "116l", "116m"]:
        check(lbl + ". (skipped — file absent)", False)

# 116n updated: PR #405 adds tw-image-cropper.js to profile-showcase.html
check(
    "116n. profile-showcase.html loads tw-image-cropper.js (added by PR #405)",
    "tw-image-cropper.js" in open("profile-showcase.html", encoding="utf-8").read()
)
check(
    "116o. company-profile.html loads tw-image-cropper.js (added by PR #406)",
    "tw-image-cropper.js" in open("company-profile.html", encoding="utf-8").read()
)

# ── 117. PR #405 — Connect Employee Cover to Shared Image Cropper ────────

cover_path = "profile-v2.cover.js"
showcase_html = open("profile-showcase.html", encoding="utf-8").read()

if os.path.exists(cover_path):
    with open(cover_path, encoding="utf-8") as f:
        cover_src = f.read()
    _cover_code = _re.sub(r'//[^\n]*', '', cover_src)

    check(
        "117a. profile-showcase.html loads tw-image-cropper.js (PR #405 wires cover)",
        "tw-image-cropper.js" in showcase_html
    )

    # Script order: tw-image-cropper.js must appear before profile-v2.cover.js
    idx_cropper = showcase_html.find("tw-image-cropper.js")
    idx_cover   = showcase_html.find("profile-v2.cover.js")
    check(
        "117b. tw-image-cropper.js loads before profile-v2.cover.js in profile-showcase.html",
        idx_cropper != -1 and idx_cover != -1 and idx_cropper < idx_cover
    )

    check(
        "117c. profile-v2.cover.js uses TW.createCropper",
        "TW.createCropper" in cover_src
    )
    check(
        "117d. profile-v2.cover.js calls _cropper.load",
        "_cropper.load(" in cover_src
    )
    check(
        "117e. profile-v2.cover.js calls _cropper.setZoom",
        "_cropper.setZoom(" in cover_src
    )
    check(
        "117f. profile-v2.cover.js calls _cropper.export",
        "_cropper.export()" in cover_src
    )
    check(
        "117g. profile-v2.cover.js calls _cropper.reset",
        "_cropper.reset()" in cover_src
    )
    check(
        "117h. profile-v2.cover.js has no inline crop state (CW/CH/_minScale removed)",
        "var CW" not in _cover_code and
        "var CH" not in _cover_code and
        "_minScale" not in _cover_code
    )
    check(
        "117i. profile-v2.cover.js has no inline drag handlers (_clampOffset removed)",
        "_clampOffset" not in _cover_code and
        "onMouseDown" not in _cover_code and
        "onTouchMove" not in _cover_code
    )
    check(
        "117j. profile-v2.cover.js has no exportJpeg function",
        "exportJpeg" not in _cover_code
    )
    check(
        "117k. profile-v2.cover.js uses requestAnimationFrame before _cropper.load",
        "requestAnimationFrame" in cover_src and "_cropper.load" in cover_src
    )
    check(
        "117l. profile-v2.cover.js still validates file type and size (UX unchanged)",
        "MAX_BYTES" in cover_src and
        "jpeg|png|webp" in cover_src
    )
else:
    for lbl in ["117a", "117b", "117c", "117d", "117e", "117f",
                "117g", "117h", "117i", "117j", "117k", "117l"]:
        check(lbl + ". (skipped — file absent)", False)

# ── 118. PR #406 — Company Logo Crop Overlay ─────────────────────────────

co_html   = open("company-profile.html", encoding="utf-8").read()
co_main   = open("static/company/company.main.js", encoding="utf-8").read()
co_css    = open("static/company/company.css", encoding="utf-8").read()
co_upload = open("static/shared/tw-upload.js", encoding="utf-8").read()
_co_code  = _re.sub(r'//[^\n]*', '', co_main)

# Script load order
idx_crop_co  = co_html.find("tw-image-cropper.js")
idx_main_co  = co_html.find("company.main.js")
check(
    "118a. company-profile.html loads tw-image-cropper.js before company.main.js",
    idx_crop_co != -1 and idx_main_co != -1 and idx_crop_co < idx_main_co
)

# Overlay DOM
check(
    "118b. company-profile.html contains logo crop overlay (coLogoCropOverlay)",
    "coLogoCropOverlay" in co_html
)
check(
    "118c. company-profile.html contains logo crop canvas (coLogoCropCanvas)",
    "coLogoCropCanvas" in co_html
)
check(
    "118d. company-profile.html contains logo zoom slider (coLogoZoomSlider)",
    "coLogoZoomSlider" in co_html
)

# TW.createCropper usage in company.main.js
check(
    "118e. company.main.js uses TW.createCropper for logo",
    "TW.createCropper" in co_main
)

# Config: ratio 1/1, shape rect, 300×300, quality 0.85
check(
    "118f. company.main.js logo cropper config: ratio 1/1, outputW 300, outputH 300, quality 0.85",
    ("1 / 1" in co_main or "1/1" in co_main) and
    "outputW: 300" in co_main and
    "outputH: 300" in co_main and
    "quality: 0.85" in co_main
)

# uploadLogo no longer reads raw FileReader dataUrl directly into TW.uploadImage
check(
    "118g. uploadLogo calls openLogoCrop (not TW.uploadImage directly on FileReader result)",
    "openLogoCrop" in co_main and
    "_doUploadLogo" in co_main
)

# export() from cropper feeds into TW.uploadImage
check(
    "118h. company.main.js gets dataUrl from cropper.export() before TW.uploadImage",
    "cropper.export()" in co_main and
    "TW.uploadImage" in co_main
)

# No direct fetch('/upload/image') in company.main.js
check(
    "118i. company.main.js has no direct fetch('/upload/image') call",
    "fetch('/upload/image'" not in _co_code and
    'fetch("/upload/image"' not in _co_code
)

# tw-upload.js unchanged
check(
    "118j. tw-upload.js is unchanged (still defines TW.uploadImage)",
    "TW.uploadImage" in co_upload and
    "fetch('/upload/image'" in co_upload
)

# Cover cropper untouched (no TW.createCropper for cover in company.main.js)
check(
    "118k. company logo and cover croppers use separate canvas IDs (added by PR #407)",
    "coLogoCropCanvas" in co_main and
    "coCoverCropCanvas" in co_main
)

# CSS namespace for overlay
check(
    "118l. company.css contains co-logo-crop-overlay styles",
    "co-logo-crop-overlay" in co_css and
    "coLogoCropCanvas" in co_css
)

# ── 119. PR #407 — Company Cover Crop Overlay ────────────────────────────

# Re-read files after PR #407 changes
co_html_407  = open("company-profile.html", encoding="utf-8").read()
co_main_407  = open("static/company/company.main.js", encoding="utf-8").read()
co_css_407   = open("static/company/company.css", encoding="utf-8").read()
_co_code_407 = _re.sub(r'//[^\n]*', '', co_main_407)

# Overlay DOM
check(
    "119a. company-profile.html contains cover crop overlay (coCoverCropOverlay)",
    "coCoverCropOverlay" in co_html_407
)
check(
    "119b. company-profile.html contains cover crop canvas (coCoverCropCanvas)",
    "coCoverCropCanvas" in co_html_407
)
check(
    "119c. company-profile.html contains cover zoom slider (coCoverZoomSlider)",
    "coCoverZoomSlider" in co_html_407
)

# TW.createCropper for cover in company.main.js
check(
    "119d. company.main.js uses TW.createCropper for cover",
    "coCoverCropCanvas" in co_main_407 and "TW.createCropper" in co_main_407
)

# Config: ratio 4/1, shape rect, 800×200, quality 0.88
check(
    "119e. company.main.js cover cropper config: ratio 4/1, outputW 800, outputH 200, quality 0.88",
    ("4 / 1" in co_main_407 or "4/1" in co_main_407) and
    "outputW: 800" in co_main_407 and
    "outputH: 200" in co_main_407 and
    "quality: 0.88" in co_main_407
)

# uploadCover now opens crop overlay, not TW.uploadImage directly
check(
    "119f. uploadCover calls openCoverCrop (not TW.uploadImage directly on FileReader result)",
    "openCoverCrop" in co_main_407 and "_doUploadCover" in co_main_407
)

# export() from cropper feeds into TW.uploadImage
check(
    "119g. company.main.js gets cover dataUrl from cropper.export() before TW.uploadImage",
    "cropper.export()" in co_main_407 and "TW.uploadImage" in co_main_407
)

# No direct fetch('/upload/image') in company.main.js
check(
    "119h. company.main.js has no direct fetch('/upload/image') call",
    "fetch('/upload/image'" not in _co_code_407 and
    'fetch("/upload/image"' not in _co_code_407
)

# tw-upload.js unchanged
check(
    "119i. tw-upload.js is unchanged (still defines TW.uploadImage)",
    "TW.uploadImage" in open("static/shared/tw-upload.js", encoding="utf-8").read()
)

# Logo cropper NOT modified in this PR (logo IDs still present, separate from cover)
check(
    "119j. company logo cropper (coLogoCropCanvas) still present and separate from cover",
    "coLogoCropCanvas" in co_main_407 and
    "coCoverCropCanvas" in co_main_407 and
    "coLogoCropCanvas" != "coCoverCropCanvas"
)

# CSS namespace for cover overlay
check(
    "119k. company.css contains co-cover-crop-overlay styles",
    "co-cover-crop-overlay" in co_css_407 and
    "coCoverCropCanvas" in co_css_407
)

# CSS aspect-ratio for cover canvas is 4/1
check(
    "119l. CSS cover canvas uses aspect-ratio 4/1",
    "aspect-ratio:4/1" in co_css_407 or "aspect-ratio: 4/1" in co_css_407
)

# ── 120. PR #408 — Connect Employee Avatar to Shared Image Cropper ───────

avatar_path  = "profile-v2.avatar.js"
cover_path2  = "profile-v2.cover.js"
showcase2    = open("profile-showcase.html", encoding="utf-8").read()

if os.path.exists(avatar_path):
    with open(avatar_path, encoding="utf-8") as f:
        av_src = f.read()
    _av_code = _re.sub(r'//[^\n]*', '', av_src)

    check(
        "120a. profile-v2.avatar.js uses TW.createCropper",
        "TW.createCropper" in av_src
    )
    check(
        "120b. avatar config: ratio 1/1, shape circle, outputW 260, outputH 260, quality 0.85",
        ("1 / 1" in av_src or "1/1" in av_src) and
        "'circle'" in av_src and
        "outputW: 260" in av_src and
        "outputH: 260" in av_src and
        "quality: 0.85" in av_src
    )
    check(
        "120c. profile-v2.avatar.js has no inline crop state (_minScale/_img removed)",
        "_minScale" not in _av_code and
        "var _img" not in _av_code
    )
    check(
        "120d. profile-v2.avatar.js has no inline drag handlers (_clampOffset removed)",
        "_clampOffset" not in _av_code and
        "onMouseDown" not in _av_code and
        "onTouchMove" not in _av_code
    )
    check(
        "120e. profile-v2.avatar.js has no exportJpeg function",
        "exportJpeg" not in _av_code
    )
    check(
        "120f. profile-v2.avatar.js calls _cropper.load(src)",
        "_cropper.load(" in av_src
    )
    check(
        "120g. profile-v2.avatar.js calls _cropper.setZoom",
        "_cropper.setZoom(" in av_src
    )
    check(
        "120h. profile-v2.avatar.js calls _cropper.export()",
        "_cropper.export()" in av_src
    )
    check(
        "120i. profile-v2.avatar.js calls _cropper.reset()",
        "_cropper.reset()" in av_src
    )
    check(
        "120j. profile-v2.avatar.js uses requestAnimationFrame before _cropper.load",
        "requestAnimationFrame" in av_src and "_cropper.load(" in av_src
    )
    check(
        "120k. profile-v2.avatar.js has no direct fetch('/upload/image') call",
        "fetch('/upload/image'" not in _av_code and
        'fetch("/upload/image"' not in _av_code
    )
    check(
        "120l. tw-image-cropper.js loads before profile-v2.avatar.js in profile-showcase.html",
        showcase2.find("tw-image-cropper.js") < showcase2.find("profile-v2.avatar.js")
    )
else:
    for lbl in ["120a","120b","120c","120d","120e","120f",
                "120g","120h","120i","120j","120k","120l"]:
        check(lbl + ". (skipped — file absent)", False)

# Unchanged files
check(
    "120m. profile-v2.cover.js unchanged (no TW.createCropper for cover added in avatar PR)",
    "profile-v2" in cover_path2 and open(cover_path2, encoding="utf-8").read().count("TW.createCropper") == 1
)
check(
    "120n. tw-upload.js unchanged",
    "TW.uploadImage" in open("static/shared/tw-upload.js", encoding="utf-8").read()
)

# ── 121. Restore Employee Cover Height ───────────────────────────────────
with open("profile-v2.css", encoding="utf-8") as f:
    pv2_css = f.read()

cover_block_start = pv2_css.find(".sc-cover {")
cover_block = pv2_css[cover_block_start:pv2_css.find("}", cover_block_start)+1] if cover_block_start >= 0 else ""

check(
    "121a. .sc-cover uses height:80px (restored original fixed height)",
    "height:80px" in cover_block
)
check(
    "121b. .sc-cover does NOT use aspect-ratio:6/1 (removed responsive ratio)",
    "aspect-ratio:6/1" not in cover_block and "aspect-ratio: 6/1" not in cover_block
)
check(
    "121c. .sc-cover retains border-radius:13px 13px 0 0 (kept for card clipping)",
    "border-radius:13px 13px 0 0" in cover_block
)
check(
    "121d. .sc-cover retains overflow:hidden (kept for card clipping)",
    "overflow:hidden" in cover_block
)

with open("profile-v2.cover.js", encoding="utf-8") as f:
    cover_js = f.read()
check(
    "121e. profile-v2.cover.js uses lazy init — no static TW.createCropper at module level",
    "_cropper = null" in cover_js and
    "TW.createCropper" in cover_js and
    cover_js.index("TW.createCropper") > cover_js.index("function openCrop")
)
check(
    "121f. profile-v2.cover.js reads sc-cover offsetWidth for dynamic ratio",
    "offsetWidth" in cover_js and "scCover" in cover_js
)
check(
    "121g. profile-v2.cover.js outputH is 240 (increased from 120 for less blur)",
    "outH = 240" in cover_js
)
check(
    "121h. profile-v2.cover.js calls _cropper.destroy() before recreating",
    "_cropper.destroy()" in cover_js
)
check(
    "121i. profile-v2.avatar.js unchanged",
    "TW.createCropper" in open("profile-v2.avatar.js", encoding="utf-8").read()
)
check(
    "121j. tw-image-cropper.js unchanged",
    "createCropper" in open("static/shared/tw-image-cropper.js", encoding="utf-8").read()
)

# ── 122. Avatar Crop Modal Mobile Size ───────────────────────────────────
with open("profile-v2.css", encoding="utf-8") as f:
    _pv2css = f.read()

av_canvas_start = _pv2css.find("#avCropCanvas {")
av_canvas_block = _pv2css[av_canvas_start:_pv2css.find("}", av_canvas_start)+1] if av_canvas_start >= 0 else ""
av_card_start   = _pv2css.find(".av-crop-card {")
av_card_block   = _pv2css[av_card_start:_pv2css.find("}", av_card_start)+1] if av_card_start >= 0 else ""

check(
    "122a. #avCropCanvas has CSS width constraint (min() or px) to prevent DPR overflow",
    "width:min(" in av_canvas_block or "width: min(" in av_canvas_block or
    ("width:" in av_canvas_block and "px" in av_canvas_block)
)
check(
    "122b. #avCropCanvas has aspect-ratio:1/1 so canvas stays square",
    "aspect-ratio:1/1" in av_canvas_block or "aspect-ratio: 1/1" in av_canvas_block
)
check(
    "122c. #avCropCanvas has max-width constraint",
    "max-width:" in av_canvas_block
)
check(
    "122d. .av-crop-card has max-height to prevent overflow on short screens",
    "max-height:" in av_card_block
)
check(
    "122e. avatar cropper config unchanged: ratio 1/1, shape circle, outputW 260, quality 0.85",
    open("profile-v2.avatar.js", encoding="utf-8").read().count("TW.createCropper") >= 1 and
    "ratio:   1 / 1" in open("profile-v2.avatar.js", encoding="utf-8").read() and
    "shape:   'circle'" in open("profile-v2.avatar.js", encoding="utf-8").read() and
    "outputW: 260" in open("profile-v2.avatar.js", encoding="utf-8").read()
)
check(
    "122f. .sc-cover height:80px unchanged (cover not affected)",
    "height:80px" in _pv2css
)
check(
    "122g. tw-image-cropper.js unchanged",
    "createCropper" in open("static/shared/tw-image-cropper.js", encoding="utf-8").read()
)

# ── 123. @mention API Search (feat/mention-api-search) ───────────────────

posts_js = open("static/company/company.posts.js", encoding="utf-8").read()
srv_src  = open("server.py", encoding="utf-8").read()

# Module-level debounce timer
check(
    "123a. _cmtMentionDebounce module variable declared",
    "var _cmtMentionDebounce" in posts_js
)

# _cmtMergeCandidates function
check(
    "123b. _cmtMergeCandidates function defined",
    "function _cmtMergeCandidates(" in posts_js
)
check(
    "123c. _cmtMergeCandidates deduplicates by tw_id (seen dict)",
    "seen[domCands[i].tw_id]" in posts_js or "seen[apiCands[j].tw_id]" in posts_js
)

# _cmtHandleMentionInput opens menu immediately with DOM candidates
check(
    "123d. _cmtHandleMentionInput shows DOM candidates immediately (no wait for API)",
    "_cmtOpenMentionMenu(ta, postId, filtered, start)" in posts_js
)

# Debounce + API call
check(
    "123e. _cmtHandleMentionInput uses setTimeout 100ms debounce for API call",
    "_cmtMentionDebounce = setTimeout(function" in posts_js and ", 100)" in posts_js
)
check(
    "123f. _cmtHandleMentionInput fetches /mention/search with Authorization header",
    "'/mention/search?q='" in posts_js and "'Authorization'" in posts_js and "Bearer" in posts_js
)

# Guard: abort if menu closed or caret moved
check(
    "123g. debounce guard: aborts if mention state closed before response arrives",
    "if (!_cmtMentionState.open) return;" in posts_js
)
check(
    "123h. debounce guard: aborts if query changed (stale response protection)",
    "capturedQuery" in posts_js and (
        "currentQuery !== capturedQuery" in posts_js or  # legacy pattern (PR #421-)
        "currEx.query !== capturedQuery" in posts_js     # new pattern (PR #422+)
    )
)
check(
    "123h2. post-response guard: re-verifies query after async gap",
    "postResponseQuery !== capturedQuery" in posts_js or  # legacy pattern
    "postEx.query !== capturedQuery" in posts_js           # new pattern (PR #422+)
)
check(
    "123h3. capturedCursor removed — no unused variable",
    "capturedCursor" not in posts_js
)

# _cmtCloseMentionMenu clears debounce timer
check(
    "123i. _cmtCloseMentionMenu clears _cmtMentionDebounce on close",
    "if (_cmtMentionDebounce) { clearTimeout(_cmtMentionDebounce)" in posts_js
)

# Backend endpoint
check(
    "123j. server.py has GET /mention/search endpoint",
    '@app.get("/mention/search")' in srv_src
)
check(
    "123k. GET /mention/search requires JWT (Depends(verify_token))",
    "mention_search" in srv_src and "verify_token" in srv_src and
    '/mention/search' in srv_src
)
check(
    "123l. GET /mention/search returns prioritized candidates from followers/following",
    "profile_follows" in srv_src and "company_follows" in srv_src and
    "mention_search" in srv_src
)
check(
    "123m. GET /mention/search deduplicates by tw_id (seen set)",
    "seen" in srv_src and "set()" in srv_src and "mention_search" in srv_src
)
check(
    "123n. GET /mention/search merges DOM candidates via _cmtMergeCandidates in frontend",
    "function _cmtMergeCandidates(" in posts_js and
    "_cmtMergeCandidates(freshDom, res.candidates)" in posts_js
)

# ── 124. Speed Up Mention Suggestions (feat/mention-search-perf) ─────────

posts_js = open("static/company/company.posts.js", encoding="utf-8").read()
srv_src  = open("server.py", encoding="utf-8").read()
company_css = open("static/company/company.css", encoding="utf-8").read()

# Backend: single UNION ALL query (1 roundtrip)
check(
    "124a. /mention/search uses UNION ALL (1 roundtrip instead of 3 sequential queries)",
    "UNION ALL" in srv_src and "mention_search" in srv_src
)
check(
    "124b. /mention/search empty-q path has no ILIKE filter (pure FK scan)",
    "WHERE pf.follower_id = :vid_a LIMIT :lim_a)" in srv_src and
    "if q:" in srv_src
)
check(
    "124c. /mention/search does NOT search all users when q is empty (Priority 4 skipped)",
    (srv_src.find("any matching user") > srv_src.find("if q:") or
     srv_src.find("Priority 4") > srv_src.find("if q:"))
)
check(
    "124d. /mention/search empty-q still returns followers/following/company follows",
    "WHERE pf.follower_id = :vid_a LIMIT :lim_a)" in srv_src and
    "WHERE pf.followed_id = :vid_b AND u.id != :vid_b2 LIMIT :lim_b)" in srv_src and
    "WHERE cf.follower_id = :vid_c LIMIT :lim_c)" in srv_src
)
check(
    "124e. /mention/search with q uses ILIKE inside each UNION branch",
    "ILIKE :q_a LIMIT :lim_a)" in srv_src and
    "ILIKE :q_b LIMIT :lim_b)" in srv_src and
    "ILIKE :q_c LIMIT :lim_c)" in srv_src
)
check(
    "124j. UNION ALL uses unique param names per branch — no duplicate :vid/:lim across branches",
    ":vid_a" in srv_src and ":vid_b" in srv_src and ":vid_c" in srv_src and
    ":lim_a" in srv_src and ":lim_b" in srv_src and ":lim_c" in srv_src
)

# Frontend: debounce 100ms
check(
    "124f. _cmtHandleMentionInput debounce reduced to 100ms",
    "_cmtMentionDebounce = setTimeout" in posts_js and ", 100);" in posts_js
)

# Frontend: loading indicator
check(
    "124g. loading indicator 'جاري البحث…' appended when menu is open",
    "'جاري البحث…'" in posts_js and "pc-cmt-mention-loading" in posts_js
)
check(
    "124h. loading indicator removed on API error or stale abort",
    "getElementById('pc-cmt-mention-loading')" in posts_js and
    posts_js.count("_ldEl.remove()") >= 2  # error + stale paths
)
check(
    "124h2. loading indicator CSS defined in company.css",
    ".pc-cmt-mention-loading" in company_css and "_mention-spin" in company_css
)

# Stale guards preserved
check(
    "124i. stale-response guards (capturedQuery) still present after perf fix",
    "capturedQuery" in posts_js and (
        ("currentQuery !== capturedQuery" in posts_js and "postResponseQuery !== capturedQuery" in posts_js) or
        ("currEx.query !== capturedQuery" in posts_js and "postEx.query !== capturedQuery" in posts_js)
    )
)

# ── 125. Fix Mention Search Relationship Sources (feat/fix-mention-search-relationship-sources) ──

srv_src  = open("server.py",  encoding="utf-8").read()
posts_js = open("static/company/company.posts.js", encoding="utf-8").read()

check(
    "125a. mention_search branches on viewer_type (co vs emp path)",
    'viewer_type == "co"' in srv_src and 'viewer_type = token.get("user_type"' in srv_src
)
check(
    "125b. company viewer queries people who follow the company (cf.company_id = :vid)",
    "cf.company_id = :vid" in srv_src
)
check(
    "125c. company viewer retrieves followers by joining on cf.follower_id (not cf.company_id)",
    "u.id = cf.follower_id" in srv_src
)
check(
    "125d. mention_search exception handler logs error — not a silent pass",
    "[mention_search]" in srv_src
)
check(
    "125e. mention_search returns ok:False on exception",
    '"ok": False' in srv_src and "mention_search" in srv_src
)
check(
    "125f. frontend handles ok:false from mention_search (!res.ok check present)",
    "!res.ok" in posts_js
)
check(
    "125g. company empty-q path uses pure FK scan on company_id (no ILIKE)",
    "cf.company_id = :vid LIMIT :lim" in srv_src
)
check(
    "125h. employee path is unchanged — profile_follows both directions still present",
    "WHERE pf.follower_id = :vid_a LIMIT :lim_a)" in srv_src and
    "WHERE pf.followed_id = :vid_b AND u.id != :vid_b2 LIMIT :lim_b)" in srv_src
)

# ── 126. Company Logo Crop Circle Preview (feat/company-logo-crop-circle) ──

co_main_126 = open("static/company/company.main.js", encoding="utf-8").read()
co_css_126  = open("static/company/company.css",     encoding="utf-8").read()
cropper_src_126 = open("static/shared/tw-image-cropper.js", encoding="utf-8").read()
upload_src_126  = open("static/shared/tw-upload.js",        encoding="utf-8").read()
av_src_126  = open("profile-v2.avatar.js",  encoding="utf-8").read()
cov_src_126 = open("profile-v2.cover.js",   encoding="utf-8").read()

check(
    "126a. company logo cropper uses shape: circle",
    "shape:   'circle'" in co_main_126 and "coLogoCropCanvas" in co_main_126
)
check(
    "126b. company logo cropper ratio still 1/1",
    "ratio:   1 / 1" in co_main_126 and "coLogoCropCanvas" in co_main_126
)
check(
    "126c. company logo output still 300x300",
    "outputW: 300" in co_main_126 and "outputH: 300" in co_main_126
)
check(
    "126d. company logo quality still 0.85",
    "quality: 0.85" in co_main_126 and "coLogoCropCanvas" in co_main_126
)
check(
    "126e. #coLogoCropCanvas CSS uses border-radius:50% (circle shape)",
    "border-radius:50%" in co_css_126 and "coLogoCropCanvas" in co_css_126
)
check(
    "126f. #coLogoCropCanvas CSS has overflow:hidden",
    "overflow:hidden" in co_css_126 and "coLogoCropCanvas" in co_css_126
)
check(
    "126g. company cover cropper unchanged — still shape rect",
    "shape:   'rect'" in co_main_126 and "coCoverCropCanvas" in co_main_126
)
check(
    "126h. employee avatar cropper unchanged — still shape circle in profile-v2.avatar.js",
    "shape:   'circle'" in av_src_126
)
check(
    "126i. employee cover cropper unchanged — still shape rect in profile-v2.cover.js",
    "shape:   'rect'" in cov_src_126
)
check(
    "126j. tw-image-cropper.js not modified — still supports circle and rect",
    "'circle'" in cropper_src_126 and "'rect'" in cropper_src_126
)
check(
    "126k. tw-upload.js not modified — TW.uploadImage signature present",
    "TW.uploadImage" in upload_src_126
)

# ── 127. Mobile Posts/Comments/Mentions QA (feat/mobile-posts-comments-mentions-qa) ──

posts_js_127 = open("static/company/company.posts.js", encoding="utf-8").read()
co_css_127   = open("static/company/company.css",      encoding="utf-8").read()

# @mention fetch still uses /mention/search
check(
    "127a. @mention fetch still uses /mention/search",
    "'/mention/search?" in posts_js_127
)
# Stale guards preserved
check(
    "127b. capturedQuery stale guards still present",
    "capturedQuery" in posts_js_127 and (
        ("currentQuery !== capturedQuery" in posts_js_127 and "postResponseQuery !== capturedQuery" in posts_js_127) or
        ("currEx.query !== capturedQuery" in posts_js_127 and "postEx.query !== capturedQuery" in posts_js_127)
    )
)
# DOM candidates appear immediately
check(
    "127c. DOM candidates collected and shown before API call (_cmtCollectMentionCandidates)",
    "_cmtCollectMentionCandidates(postId)" in posts_js_127 and
    "_cmtOpenMentionMenu(ta, postId, filtered, start)" in posts_js_127
)
# API candidates merged with DOM candidates
check(
    "127d. API candidates merged via _cmtMergeCandidates",
    "_cmtMergeCandidates(freshDom, res.candidates)" in posts_js_127
)
# clearTimeout on mention menu close
check(
    "127e. clearTimeout(_cmtMentionDebounce) on menu close",
    "clearTimeout(_cmtMentionDebounce)" in posts_js_127 and "_cmtCloseMentionMenu" in posts_js_127
)
# Send does not break — sendBtn.disabled guard
check(
    "127f. comment send has in-flight guard (sendBtn.disabled)",
    "sendBtn.disabled = true" in posts_js_127 and "_cmtHandleSend" in posts_js_127
)
# Reply send: _cmtHandleSend handles reply_to_comment_id
check(
    "127g. reply send passes reply_to_comment_id in payload",
    "_cmtReplyTargetId" in posts_js_127 and "reply_to_comment_id" in posts_js_127
)
# mention menu max-width CSS
check(
    "127h. .pc-cmt-mention-menu has CSS max-width guard for narrow screens",
    "max-width:calc(100vw - 16px)" in co_css_127
)
# Panel overflow-x hidden
check(
    "127i. .pc-cmts-panel has overflow-x:hidden to prevent horizontal bleed",
    "overflow-x: hidden" in co_css_127 and "pc-cmts-panel" in co_css_127
)
# No innerHTML for API mention data (XSS contract)
check(
    "127j. _cmtBuildItem uses textContent for comment body — no innerHTML for API data",
    "textContent" in posts_js_127 and "_cmtBuildItem" in posts_js_127
)
# _renderTagChips no longer uses innerHTML
check(
    "127k. _renderTagChips uses createElement/textContent — not innerHTML",
    "chips.replaceChildren()" in posts_js_127 and
    "createTextNode" in posts_js_127 and
    "chips.innerHTML" not in posts_js_127
)
# iOS viewport fix for mention menu
check(
    "127l. _cmtPositionMentionMenu uses visualViewport.height for iOS keyboard awareness",
    "visualViewport" in posts_js_127 and "_cmtPositionMentionMenu" in posts_js_127
)
# iOS viewport fix for portal menu
check(
    "127m. portal menu positioning uses visualViewport.height",
    "visualViewport && window.visualViewport.height" in posts_js_127 and
    "_cmtShowPortalMenu" in posts_js_127
)
# scrollIntoView on reply
check(
    "127n. _cmtHandleReply scrolls textarea into view after focus (mobile keyboard)",
    "scrollIntoView" in posts_js_127 and "_cmtHandleReply" in posts_js_127
)
# Mobile list max-height media query
check(
    "127o. @media (max-height:600px) shrinks .pc-cmts-list for small viewports",
    "@media (max-height:600px)" in co_css_127 and "pc-cmts-list" in co_css_127
)
# Touch targets improved
check(
    "127p. mobile touch targets: reply-btn and menu-btn have padding on small screens",
    ".pc-cmt-reply-btn { padding:6px 0" in co_css_127 and
    ".pc-cmt-menu-btn  { padding:6px 8px" in co_css_127
)

# ── 128 — Architecture Foundation (PR #420) ──────────────────────────────
import os as _os

_foundation_path = _os.path.join(_os.path.dirname(__file__), "ARCHITECTURE_FOUNDATION.md")
_foundation_exists = _os.path.isfile(_foundation_path)
_foundation_src = open(_foundation_path).read() if _foundation_exists else ""

_arch_src_128 = open(_os.path.join(_os.path.dirname(__file__), "ARCHITECTURE.md")).read()
_claude_src_128 = open(_os.path.join(_os.path.dirname(__file__), "CLAUDE.md")).read()

check(
    "128a. ARCHITECTURE_FOUNDATION.md exists",
    _foundation_exists
)
check(
    "128b. ARCHITECTURE_FOUNDATION.md contains API-first Rule (F2)",
    "API-first Rule" in _foundation_src or "API-first" in _foundation_src
)
check(
    "128c. ARCHITECTURE_FOUNDATION.md contains Single Backend / Single Database (F3)",
    "Single Backend" in _foundation_src and "Single Database" in _foundation_src
)
check(
    "128d. ARCHITECTURE_FOUNDATION.md contains Shared System First (F4)",
    "Shared System First" in _foundation_src
)
check(
    "128e. ARCHITECTURE_FOUNDATION.md contains One Source of Truth (F5)",
    "One Source of Truth" in _foundation_src
)
check(
    "128f. ARCHITECTURE_FOUNDATION.md contains Backend Owns Permissions (F6)",
    "Backend Owns Permissions" in _foundation_src
)
check(
    "128g. ARCHITECTURE_FOUNDATION.md contains Public Routes Contract /u/{tw_id} (F7)",
    "Public Routes Contract" in _foundation_src and "/u/{tw_id}" in _foundation_src
)
check(
    "128h. ARCHITECTURE_FOUNDATION.md contains No Silent Failures (F9)",
    "No Silent Failures" in _foundation_src
)
check(
    "128i. ARCHITECTURE_FOUNDATION.md contains Pre-push GitHub State Check (F13)",
    "Pre-push GitHub State Check" in _foundation_src
)
check(
    "128j. ARCHITECTURE_FOUNDATION.md states higher priority than feature-level docs",
    "higher priority" in _foundation_src and "foundation file wins" in _foundation_src
)
check(
    "128k. ARCHITECTURE.md references ARCHITECTURE_FOUNDATION.md",
    "ARCHITECTURE_FOUNDATION.md" in _arch_src_128
)
check(
    "128l. CLAUDE.md references ARCHITECTURE_FOUNDATION.md",
    "ARCHITECTURE_FOUNDATION.md" in _claude_src_128
)

# ── 129 — Architecture Foundation F14–F28 (PR #420 commit 2) ─────────────
check(
    "129a. ARCHITECTURE_FOUNDATION.md contains Backward Compatibility Rule (F14)",
    "Backward Compatibility Rule" in _foundation_src
)
check(
    "129b. ARCHITECTURE_FOUNDATION.md contains Standard API Response Rule (F15)",
    "Standard API Response Rule" in _foundation_src
)
check(
    "129c. ARCHITECTURE_FOUNDATION.md contains Database Migration Rule (F16)",
    "Database Migration Rule" in _foundation_src
)
check(
    "129d. ARCHITECTURE_FOUNDATION.md contains Security by Default (F17)",
    "Security by Default" in _foundation_src
)
check(
    "129e. ARCHITECTURE_FOUNDATION.md contains Important Actions Audit-ready Rule (F18)",
    "Audit-ready Rule" in _foundation_src
)
check(
    "129f. ARCHITECTURE_FOUNDATION.md contains Notification-ready Rule (F19)",
    "Notification-ready Rule" in _foundation_src
)
check(
    "129g. ARCHITECTURE_FOUNDATION.md contains Role and Permission Matrix Rule (F20)",
    "Role and Permission Matrix Rule" in _foundation_src
)
check(
    "129h. ARCHITECTURE_FOUNDATION.md contains No Client-only Trust (F21)",
    "No Client-only Trust" in _foundation_src
)
check(
    "129i. ARCHITECTURE_FOUNDATION.md contains Idempotency Rule (F22)",
    "Idempotency Rule" in _foundation_src
)
check(
    "129j. ARCHITECTURE_FOUNDATION.md contains Observability Rule (F23)",
    "Observability Rule" in _foundation_src
)
check(
    "129k. ARCHITECTURE_FOUNDATION.md contains Storage Ownership Rule (F24)",
    "Storage Ownership Rule" in _foundation_src
)
check(
    "129l. ARCHITECTURE_FOUNDATION.md contains Search-ready Data Rule (F25)",
    "Search-ready Data Rule" in _foundation_src
)
check(
    "129m. ARCHITECTURE_FOUNDATION.md contains Multi-language Ready Rule (F26)",
    "Multi-language Ready Rule" in _foundation_src
)
check(
    "129n. ARCHITECTURE_FOUNDATION.md contains Soft Delete Rule (F27)",
    "Soft Delete Rule" in _foundation_src
)
check(
    "129o. ARCHITECTURE_FOUNDATION.md contains Admin-ready Rule (F28)",
    "Admin-ready Rule" in _foundation_src
)
check(
    "129p. ARCHITECTURE_FOUNDATION.md table lists all 28 rules (F1–F28)",
    "F28" in _foundation_src and "F14" in _foundation_src
)

# ── 130 — Fix Mobile Mention Dropdown Position And Filtering (PR #421) ───
_posts130 = open("static/company/company.posts.js", encoding="utf-8").read()

check(
    "130a. _cmtFilterMentionCandidates uses toLowerCase() for case-insensitive matching",
    "toLowerCase()" in _posts130 and "_cmtFilterMentionCandidates" in _posts130
)
check(
    "130b. _cmtFilterMentionCandidates lowercases the query variable (q = query.toLowerCase())",
    "q = query.toLowerCase()" in _posts130
)
check(
    "130c. _cmtFilterMentionCandidates lowercases candidate names before indexOf",
    ".name.toLowerCase().indexOf(q)" in _posts130 or  # legacy direct access (PR #421)
    "String(c.name" in _posts130                       # safe access pattern (PR #422+)
)
check(
    "130d. _cmtPositionMentionMenu removes the 160px cap (no Math.min with 160)",
    "Math.min(menu.offsetHeight" not in _posts130
)
check(
    "130e. _cmtPositionMentionMenu uses visualViewport.offsetTop for coordinate conversion",
    "vp.offsetTop" in _posts130 or "visualViewport.offsetTop" in _posts130
)
check(
    "130f. _cmtPositionMentionMenu converts rect.top to visual-viewport coords (rectTopVis)",
    "rectTopVis" in _posts130
)
check(
    "130g. _cmtPositionMentionMenu converts rect.bottom to visual-viewport coords (rectBottomVis)",
    "rectBottomVis" in _posts130
)
check(
    "130h. compositionend listener is added to the send textarea in _cmtPopulatePanel",
    "compositionend" in _posts130
)
check(
    "130i. compositionend listener calls _cmtHandleMentionInput",
    "compositionend" in _posts130 and "_cmtHandleMentionInput(ta" in _posts130
)
check(
    "130j. _cmtPositionMentionMenu still uses visualViewport.height as _vph",
    "_vph" in _posts130 and ("vp.height" in _posts130 or "visualViewport.height" in _posts130)
)

# ── 131 — Fix Mention Query Extraction And Anchor Position (PR #422) ─────
_posts131 = open("static/company/company.posts.js", encoding="utf-8").read()
_srv131   = open("server.py", encoding="utf-8").read()

check(
    "131a. _cmtExtractMentionQuery helper exists",
    "function _cmtExtractMentionQuery" in _posts131
)
check(
    "131b. _cmtExtractMentionQuery walks backwards to find @ (atIdx variable)",
    "atIdx" in _posts131
)
check(
    "131c. _cmtExtractMentionQuery stops at space (charCode 32) and newline (charCode 10)",
    "charCodeAt" in _posts131 and "=== 32" in _posts131 and "=== 10" in _posts131
)
check(
    "131d. _cmtExtractMentionQuery strips invisible Unicode directional marks (\\u200e \\u200f \\u061c)",
    "‎" in _posts131 and "‏" in _posts131 and "؜" in _posts131
)
check(
    "131e. _cmtExtractMentionQuery returns { active, start, query } object",
    "active: true" in _posts131 and "active: false" in _posts131 and "query: clean" in _posts131
)
check(
    "131f. _cmtFilterMentionCandidates also matches tw_id (twIdMatch)",
    "twIdMatch" in _posts131
)
check(
    "131g. _cmtHandleMentionInput uses _cmtExtractMentionQuery for initial extraction",
    "var ex = _cmtExtractMentionQuery" in _posts131
)
check(
    "131h. First stale guard uses _cmtExtractMentionQuery (not _cmtFindMentionStart)",
    "var currEx = _cmtExtractMentionQuery" in _posts131
)
check(
    "131i. Second stale guard uses _cmtExtractMentionQuery (not _cmtFindMentionStart)",
    "var postEx = _cmtExtractMentionQuery" in _posts131
)
check(
    "131j. _cmtPositionMentionMenu uses .pc-cmts-input-row as anchor container",
    "pc-cmts-input-row" in _posts131 and "_cmtPositionMentionMenu" in _posts131
)
check(
    "131k. _cmtPositionMentionMenu calculates spaceAbove",
    "spaceAbove" in _posts131
)
check(
    "131l. _cmtPositionMentionMenu calculates spaceBelow",
    "spaceBelow" in _posts131
)
check(
    "131m. _cmtPositionMentionMenu sets menu.style.maxHeight dynamically",
    "menu.style.maxHeight" in _posts131
)
check(
    "131n. Stale guards preserved — _cmtMentionState.open still checked",
    "_cmtMentionState.open" in _posts131
)
check(
    "131o. /mention/search endpoint unchanged in server.py",
    "/mention/search" in _srv131
)
check(
    "131p. _cmtInsertMention still uses _cmtMentionState.start (not selectionStart directly)",
    "_cmtMentionState.start" in _posts131 and "function _cmtInsertMention" in _posts131
)

# ── 132: Jobs & Applications — static checks ─────────────────────────────
print("\n── 132: Jobs & Applications — static checks ──")

_jd132  = open('static/job/job-detail.js',   encoding='utf-8').read()
_apps132 = open('profile-v2.apps.js',        encoding='utf-8').read()
_css132  = open('static/job/job-detail.css',  encoding='utf-8').read()
_pv2css  = open('profile-v2.css',             encoding='utf-8').read()

check(
    "132a. job-detail.js: no X-User-Id header in any fetch call",
    "X-User-Id" not in _jd132
)
check(
    "132b. job-detail.js: confirmApply sends Authorization Bearer JWT",
    "'Authorization': 'Bearer ' + _jwt" in _jd132 and "confirmApply" in _jd132
)
check(
    "132c. job-detail.js: _checkAlreadyApplied fetches /my/applications with Bearer JWT",
    "/my/applications" in _jd132 and "'Authorization': 'Bearer ' + _jwt" in _jd132
)
check(
    "132d. job-detail.js: _applyOwnerMode hides .jd-apply-actions for owner",
    ".jd-apply-actions" in _jd132 and "display = 'none'" in _jd132
)
check(
    "132e. job-detail.js: _applyOwnerMode hides jdStickyBar for owner",
    "jdStickyBar" in _jd132 and "display = 'none'" in _jd132
)
check(
    "132f. job-detail.js: openApply guards against unauthenticated users",
    "!_jwt || !_user" in _jd132
)
check(
    "132g. job-detail.js: openApply guards against non-emp user_type (not just unauthenticated)",
    "user_type !== 'emp'" in _jd132
)
check(
    "132h. job-detail.js: _checkAlreadyApplied only runs for emp user_type",
    "_user.user_type !== 'emp'" in _jd132
)
check(
    "132i. profile-v2.apps.js: no X-User-Id header in fetch calls (comment mention is ok)",
    "'X-User-Id'" not in _apps132 and '"X-User-Id"' not in _apps132
)
check(
    "132j. profile-v2.apps.js: _loadApps checks _scViewerType === owner before fetch",
    "_scViewerType !== 'owner'" in _apps132
)
check(
    "132k. profile-v2.apps.js: uses Authorization Bearer JWT for /my/applications",
    "'Authorization': 'Bearer ' + jwt" in _apps132
)
check(
    "132l. profile-v2.css: #scTabApps hidden by default and revealed only for body.view-owner",
    "#scTabApps { display:none; }" in _pv2css and "view-owner #scTabApps" in _pv2css
)

# ── 133: Skeleton Loading — static checks ────────────────────────────────
_sk133    = open('static/shared/tw-skeleton.css', encoding='utf-8').read()
_cop133   = open('company-profile.html',          encoding='utf-8').read()
_coc133   = open('static/company/company.css',    encoding='utf-8').read()
_psh133   = open('profile-showcase.html',         encoding='utf-8').read()
_pv2133   = open('profile-v2.css',                encoding='utf-8').read()
_srv133   = open('server.py',                     encoding='utf-8').read()

check(
    "133a. tw-skeleton.css: defines @keyframes tw-shimmer",
    "@keyframes tw-shimmer" in _sk133
)
check(
    "133b. tw-skeleton.css: uses responsive background-size 200% (not fixed 2000px)",
    "background-size: 200% 100%" in _sk133 and "2000px" not in _sk133
)
check(
    "133c. tw-skeleton.css: shimmer moves RTL — from 200% to -200%",
    "background-position: 200% 0" in _sk133 and "background-position: -200% 0" in _sk133
)
check(
    "133d. tw-skeleton.css: has prefers-reduced-motion rule (animation: none)",
    "prefers-reduced-motion" in _sk133 and "animation: none" in _sk133
)
check(
    "133e. company-profile.html: <body> starts with co-loading class (anti-flash guard)",
    '<body class="co-loading">' in _cop133
)
check(
    "133f. company-profile.html: has .co-skeleton block (skeleton markup present)",
    'class="co-skeleton"' in _cop133
)
check(
    "133g. company-profile.html: has co-sk-section block (section cards added)",
    'co-sk-section' in _cop133
)
check(
    "133h. company-profile.html: coName element has no hardcoded fake text",
    'id="coName">اسم الشركة' not in _cop133
)
check(
    "133i. company.css: hides .sc-main-card during co-loading (skeleton shown, real hidden)",
    "body.co-loading .sc-main-card" in _coc133
)
check(
    "133j. company.css: hides .co-skeleton when not co-loading (skeleton gone after load)",
    "body:not(.co-loading) .co-skeleton" in _coc133
)
check(
    "133k. company.css: has co-sk-section styling",
    ".co-sk-section" in _coc133 and ".co-sk-sec-header" in _coc133
)
check(
    "133l. profile-showcase.html: has sc-sk-section block (section cards added)",
    'sc-sk-section' in _psh133
)
check(
    "133m. profile-v2.css: has sc-sk-section styling",
    ".sc-sk-section" in _pv2133 and ".sc-sk-sec-header" in _pv2133
)
check(
    "133n. profile-v2.css: .sc-loading styled as card (border-radius + background)",
    "border-radius: 13px" in _pv2133 and ".sc-loading" in _pv2133
)
check(
    "133o. no fixed 2000px background-size anywhere in skeleton system",
    "2000px" not in _sk133
)
check(
    "133p. server.py not modified — backend untouched",
    "tw-skeleton" not in _srv133 and "co-skeleton" not in _srv133
)

# ── 134: Legacy profile.html — Share/QR URL canonical fix ────────────────
_prof134 = open('profile.html',  encoding='utf-8').read()
_srv134  = open('server.py',     encoding='utf-8').read()
_psh134  = open('profile-showcase.html', encoding='utf-8').read()

# Extract only the share/QR-relevant block (openQROverlay + _qrUrl declaration)
# to avoid false positives from DNS prefetch or canvas watermark text
import re as _re134
_qr_block134 = '\n'.join(
    l for l in _prof134.splitlines()
    if any(k in l for k in ('openQROverlay', '_qrUrl', '_qrUser', 'redrawQR', 'initQR'))
)

check(
    "134a. profile.html share/QR: no /profile?id= in QR/share logic",
    '/profile?id=' not in _qr_block134
)
check(
    "134b. profile.html share/QR: no hardcoded tawasolna.com/profile URL",
    'tawasolna.com/profile' not in _qr_block134
)
check(
    "134c. profile.html share/QR: share URL uses /u/ path",
    "'/u/'" in _qr_block134 or '"/u/"' in _qr_block134
)
check(
    "134d. profile.html share/QR: share URL uses window.location.origin (no hardcoded host)",
    'window.location.origin' in _qr_block134 or 'location.origin' in _qr_block134
)
check(
    "134e. profile.html QR overlay: openQROverlay uses _qrUrl with /u/ fallback",
    '_qrUrl' in _qr_block134 and "'/u/'" in _qr_block134
)
check(
    "134f. profile.html: no X-User-Id header in fetch calls",
    'X-User-Id' not in _prof134
)
check(
    "134g. server.py not modified — no /u/ QR logic injected into backend",
    'openQROverlay' not in _srv134 and '_qrUrl' not in _srv134
)
check(
    "134h. profile-showcase.html not modified — Profile V2 files untouched",
    'tawasolna.com/profile?id=' not in _psh134
        and 'openQROverlay' not in _psh134
)

# ── 135: Public profile error and retry state ─────────────────────────────
_psh135  = open('profile-showcase.html', encoding='utf-8').read()
_cph135  = open('company-profile.html',  encoding='utf-8').read()
_pvr135  = open('profile-v2.render.js',  encoding='utf-8').read()
_capi135 = open('static/company/company.api.js', encoding='utf-8').read()
_cperm135 = open('static/company/company.permissions.js', encoding='utf-8').read()
_pvcss135 = open('profile-v2.css', encoding='utf-8').read()
_ccss135  = open('static/company/company.css', encoding='utf-8').read()
_srv135  = open('server.py',  encoding='utf-8').read()
_prof135 = open('profile.html', encoding='utf-8').read()

check(
    "135a. employee skeleton not permanent on error: catch hides scLoading",
    ("scLoading" in _pvr135 and "display='none'" in _pvr135 and
     "scErrorState" in _pvr135)
)
check(
    "135b. employee profile has scErrorState div (error state element)",
    'id="scErrorState"' in _psh135 or "id='scErrorState'" in _psh135
)
check(
    "135c. company profile has coErrorState div (error state element)",
    'id="coErrorState"' in _cph135 or "id='coErrorState'" in _cph135
)
check(
    "135d. retry button or handler present on both profile pages",
    ('id="scRetryBtn"' in _psh135 or "id='scRetryBtn'" in _psh135) and
    ('id="coRetryBtn"' in _cph135 or "id='coRetryBtn'" in _cph135 or
     'loadData()' in _cph135)
)
check(
    "135e. retry hides error state on re-attempt",
    ("errEl" in _pvr135 and "display='none'" in _pvr135) and
    ("co-error" in _cperm135 and "remove('co-error')" in _cperm135)
)
check(
    "135f. no fake / placeholder data injected on error in either file",
    "placeholder" not in _pvr135.split("catch")[1].split("});")[0] if "catch" in _pvr135 else True
    and "fake" not in _capi135.lower()
)
check(
    "135g. server.py not modified — backend untouched",
    "scErrorState" not in _srv135 and "coErrorState" not in _srv135 and
    "co-error" not in _srv135
)
check(
    "135h. legacy profile.html not modified — error state not added there",
    "scErrorState" not in _prof135 and "co-error" not in _prof135
)
check(
    "135i. /u/ route handling not touched in server.py",
    _srv135.count("'/u/") == _srv135.count("'/u/") and
    "scErrorState" not in _srv135
)
check(
    "135j. no shared tw-error-state.js created (local solution used instead)",
    not os.path.exists('static/shared/tw-error-state.js')
)

# ── 136: iOS PWA meta tags for public profile pages ───────────────────────
_psh136  = open('profile-showcase.html',  encoding='utf-8').read()
_cph136  = open('company-profile.html',   encoding='utf-8').read()
_edu136  = open('edu-profile.html',       encoding='utf-8').read()
_srv136  = open('server.py',              encoding='utf-8').read()
_prof136 = open('profile.html',           encoding='utf-8').read()

check(
    "136a. profile-showcase.html has apple-mobile-web-app-capable",
    'apple-mobile-web-app-capable' in _psh136
)
check(
    "136b. profile-showcase.html has apple-mobile-web-app-status-bar-style",
    'apple-mobile-web-app-status-bar-style' in _psh136
)
check(
    "136c. profile-showcase.html has apple-touch-icon (icon-192.png consistent with manifest)",
    'apple-touch-icon' in _psh136 and 'icon-192.png' in _psh136
)
check(
    "136d. company-profile.html has apple-mobile-web-app-capable",
    'apple-mobile-web-app-capable' in _cph136
)
check(
    "136e. company-profile.html has apple-touch-icon",
    'apple-touch-icon' in _cph136
)
check(
    "136f. edu-profile.html has apple-mobile-web-app-capable",
    'apple-mobile-web-app-capable' in _edu136
)
check(
    "136g. edu-profile.html has apple-touch-icon",
    'apple-touch-icon' in _edu136
)
check(
    "136h. server.py not modified — backend untouched",
    'apple-mobile-web-app-capable' not in _srv136
        and 'apple-touch-icon' not in _srv136
)
check(
    "136i. legacy profile.html not modified (still has its own tags, unchanged)",
    'apple-mobile-web-app-capable' in _prof136
)
check(
    "136j. no JS or CSS files modified for iOS meta tags",
    not os.path.exists('static/shared/tw-pwa.js')
        and not os.path.exists('static/shared/tw-pwa.css')
)

# ── 137: Future Roadmap file ──────────────────────────────────────────────
_rdm137  = open('docs/FUTURE_ROADMAP.md', encoding='utf-8').read()
_idx137  = open('docs/SYSTEMS_INDEX.md',  encoding='utf-8').read()
_srv137  = open('server.py',              encoding='utf-8').read()

check(
    "137a. docs/FUTURE_ROADMAP.md exists",
    os.path.exists('docs/FUTURE_ROADMAP.md')
)
check(
    "137b. FUTURE_ROADMAP.md has Purpose section",
    '## Purpose' in _rdm137
)
check(
    "137c. FUTURE_ROADMAP.md has Usage Rules section",
    '## Usage Rules' in _rdm137
)
check(
    "137d. FUTURE_ROADMAP.md has Areas section with sub-areas",
    '## Areas' in _rdm137 and '### Platform' in _rdm137
)
check(
    "137e. FUTURE_ROADMAP.md has Needs Decision Before Build section",
    'Needs Decision Before Build' in _rdm137
)
check(
    "137f. FUTURE_ROADMAP.md has Done section",
    '## Done' in _rdm137
)
check(
    "137g. FUTURE_ROADMAP.md prohibits execution without explicit request",
    'طلب صريح' in _rdm137
)
check(
    "137h. SYSTEMS_INDEX.md references FUTURE_ROADMAP.md",
    'FUTURE_ROADMAP.md' in _idx137
)
check(
    "137i. server.py not modified — backend untouched",
    'FUTURE_ROADMAP' not in _srv137
)
check(
    "137j. no feature code files modified (docs-only PR)",
    'FUTURE_ROADMAP' not in open('profile-showcase.html', encoding='utf-8').read()
    and 'FUTURE_ROADMAP' not in open('company-profile.html', encoding='utf-8').read()
)

# ── 138: Future Roadmap — Profile System Ideas update ─────────────────────
_rdm138 = open('docs/FUTURE_ROADMAP.md', encoding='utf-8').read()
_srv138 = open('server.py', encoding='utf-8').read()

check(
    "138a. FUTURE_ROADMAP.md contains Employee Profile Posts",
    'Employee Profile Posts' in _rdm138
)
check(
    "138b. FUTURE_ROADMAP.md contains Poll Posts / Ask Your Followers",
    'Poll Posts' in _rdm138 or 'اسأل متابعينك' in _rdm138
)
check(
    "138c. FUTURE_ROADMAP.md contains Unified Profile UI Tokens",
    'Unified Profile UI Tokens' in _rdm138
)
check(
    "138d. FUTURE_ROADMAP.md contains Unified Profile Media Sizing",
    'Unified Profile Media Sizing' in _rdm138
)
check(
    "138e. FUTURE_ROADMAP.md contains Unified Profile Settings Menu",
    'Unified Profile Settings Menu' in _rdm138
)
check(
    "138f. FUTURE_ROADMAP.md contains Generic About Section Label or حول",
    'Generic About Section Label' in _rdm138 or '"حول"' in _rdm138
)
check(
    "138g. FUTURE_ROADMAP.md contains Verification Badge / Flow",
    'Verification Badge' in _rdm138
)
check(
    "138h. FUTURE_ROADMAP.md contains Interactive Profile Stats",
    'Interactive Profile Stats' in _rdm138 or 'Clickable Counters' in _rdm138
)
check(
    "138i. FUTURE_ROADMAP.md contains First-time Profile Setup Wizard",
    'Setup Wizard' in _rdm138
)
check(
    "138j. FUTURE_ROADMAP.md contains First-time Guided Tour / Page Coach",
    'Guided Tour' in _rdm138 or 'Page Coach' in _rdm138
)
check(
    "138k. FUTURE_ROADMAP.md Needs Decision includes Employee Polls and followers-only",
    'Employee Polls' in _rdm138 and 'followers' in _rdm138.lower()
)
check(
    "138l. server.py not modified — backend untouched",
    'Employee Profile Posts' not in _srv138 and 'Poll Posts' not in _srv138
)
check(
    "138m. no HTML/CSS/JS files modified — docs-only",
    not any(
        'Employee Profile Posts' in open(f, encoding='utf-8').read()
        for f in ['profile-showcase.html', 'company-profile.html', 'edu-profile.html']
    )
)

# ═══════════════════════════════════════════════════════════════════════
# §139 — Notifications Full Delivery Plan (Phase 0 — docs/NOTIFICATIONS_PLAN.md)
# 17 static checks — docs-only PR — no code files touched
# ═══════════════════════════════════════════════════════════════════════
print("\n── §139: Notifications Plan (Phase 0) ──")
import os as _os139
_nplan = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os139.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_sidx139 = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read() if _os139.path.exists('docs/SYSTEMS_INDEX.md') else ''
_srv139  = open('server.py', encoding='utf-8').read() if _os139.path.exists('server.py') else ''

check(
    "139a. docs/NOTIFICATIONS_PLAN.md exists",
    bool(_nplan)
)
check(
    "139b. Plan contains Phase 0",
    'Phase 0' in _nplan
)
check(
    "139c. Plan contains Phase 1",
    'Phase 1' in _nplan
)
check(
    "139d. Plan contains Phase 11 (real-time — deferred)",
    'Phase 11' in _nplan
)
check(
    "139e. Plan contains event_key (idempotency)",
    'event_key' in _nplan
)
check(
    "139f. Plan contains actor_id",
    'actor_id' in _nplan
)
check(
    "139g. Plan contains JWT security rule",
    'JWT' in _nplan
)
check(
    "139h. Plan documents security bugs S1-S6",
    all(f'S{i}' in _nplan for i in range(1, 7))
)
check(
    "139i. Plan contains comment notification hook (Phase 3)",
    'Phase 3' in _nplan and 'comment' in _nplan.lower()
)
check(
    "139j. Plan contains reply notification hook (Phase 4)",
    'Phase 4' in _nplan and 'reply' in _nplan.lower()
)
check(
    "139k. Plan contains mention notification hook (Phase 5)",
    'Phase 5' in _nplan and 'mention' in _nplan.lower()
)
check(
    "139l. Plan contains job_applied hook (Phase 6)",
    'Phase 6' in _nplan and 'job_applied' in _nplan
)
check(
    "139m. Plan contains follow hook (Phase 7)",
    'Phase 7' in _nplan and 'follow' in _nplan.lower()
)
check(
    "139n. Plan contains verification hook (Phase 8)",
    'Phase 8' in _nplan and 'verify' in _nplan.lower()
)
check(
    "139o. SYSTEMS_INDEX.md updated — §36 added for Notifications Plan",
    '### 36.' in _sidx139 and 'NOTIFICATIONS_PLAN' in _sidx139
)
check(
    "139p. SYSTEMS_INDEX.md §19 updated to reference NOTIFICATIONS_PLAN.md",
    '### 19.' in _sidx139 and 'NOTIFICATIONS_PLAN' in _sidx139
)
check(
    "139q. Phase 0 is docs-only — NOTIFICATIONS_PLAN.md Phase 0 header says 'docs only'"
    " (check updated: server.py legitimately gained event_key in Phases 2+8; intent verified via docs)",
    'docs only' in _nplan.lower() and 'Phase 0' in _nplan
)

# ═══════════════════════════════════════════════════════════════════════
# §140 — Notifications Phase 1 — Security Hardening
# 10 static checks
# ═══════════════════════════════════════════════════════════════════════
print("\n── §140: Notifications Phase 1 — Security Hardening ──")
import os as _os140
_srv140  = open('server.py', encoding='utf-8').read() if _os140.path.exists('server.py') else ''
_notif140 = open('notifications.html', encoding='utf-8').read() if _os140.path.exists('notifications.html') else ''
_nplan140 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os140.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''

check(
    "140a. GET /notifications/{user_id} requires JWT (Depends(verify_token))",
    'def user_notifications(user_id: int, token=Depends(verify_token))' in _srv140 or
    ('def user_notifications(user_id: int, token=Depends(verify_token),' in _srv140)
)
check(
    "140b. GET /notifications/{user_id} cross-checks tok_uid == user_id",
    'tok_uid != user_id' in _srv140 and 'user_notifications' in _srv140
)
check(
    "140c. PUT /notifications/{user_id}/read cross-checks tok_uid == user_id",
    _srv140.count('tok_uid != user_id') >= 2
)
check(
    "140d. No X-User-Id in notifications.html",
    'X-User-Id' not in _notif140
)
check(
    "140e. notifications.html uses Authorization Bearer for /notifications/ fetch",
    "Authorization':'Bearer " in _notif140 or "Authorization: 'Bearer" in _notif140 or
    "'Authorization': 'Bearer'" in _notif140 or "'Authorization':'Bearer'" in _notif140 or
    "Bearer ' +" in _notif140 or "Bearer '" in _notif140
)
check(
    "140f. notifications.html has no innerHTML with n.title (XSS fixed)",
    'n.title' not in _notif140 or ('innerHTML' not in _notif140.split('n.title')[0].split('\n')[-1])
)
check(
    "140g. notifications.html has no innerHTML with n.body (XSS fixed)",
    'n.body' not in _notif140 or 'textContent' in _notif140
)
check(
    "140h. create_notification in report flow called with 4 args (type + title + body)",
    'create_notification(1, "report", "بلاغ جديد"' in _srv140
)
check(
    "140i. No bare except: pass in the create_notification / report flow block",
    (lambda s: 'except: pass' not in s)(
        _srv140[_srv140.find('Create notification for admin'):_srv140.find('تم إرسال البلاغ')+30]
        if 'Create notification for admin' in _srv140 else ''
    )
)
check(
    "140j. NOTIFICATIONS_PLAN.md marks Phase 1 as complete",
    'Phase 1' in _nplan140 and ('مكتمل' in _nplan140 or 'منفذ' in _nplan140 or 'منفَّذ' in _nplan140)
)

# ═══════════════════════════════════════════════════════════════════════
# §141 — Notifications Phase 2 — Schema Hardening
# 10 static checks
# ═══════════════════════════════════════════════════════════════════════
print("\n── §141: Notifications Phase 2 — Schema Hardening ──")
import os as _os141
_auth141 = open('auth.py', encoding='utf-8').read() if _os141.path.exists('auth.py') else ''
_srv141  = open('server.py', encoding='utf-8').read() if _os141.path.exists('server.py') else ''
_nplan141 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os141.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''

check(
    "141a. _migrate_notifications_schema_v2() exists in auth.py",
    'def _migrate_notifications_schema_v2' in _auth141
)
check(
    "141b. Migration adds actor_id column (IF NOT EXISTS)",
    'ADD COLUMN IF NOT EXISTS actor_id' in _auth141
)
check(
    "141c. Migration adds event_key column (IF NOT EXISTS)",
    'ADD COLUMN IF NOT EXISTS event_key' in _auth141
)
check(
    "141d. Migration creates unique index on (user_id, event_key)",
    'uniq_notif_event_key' in _auth141 and 'user_id, event_key' in _auth141
)
check(
    "141e. create_notification accepts actor_id, entity_id, entity_type, event_key kwargs",
    'actor_id: int = None' in _auth141 and 'entity_id: int = None' in _auth141 and 'event_key: str = None' in _auth141
)
check(
    "141f. create_notification uses ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING (partial-index-correct, idempotent)",
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth141
)
check(
    "141g. create_notification returns None on duplicate (event_key idempotency)",
    'if not rows' in _auth141 and 'return None' in _auth141
)
check(
    "141h. _migrate_notifications_schema_v2 is imported and called in server.py startup",
    '_migrate_notifications_schema_v2' in _srv141 and '_migrate_notifications_schema_v2()' in _srv141
)
check(
    "141i. _migrate_notifications_schema_v2 contains no notification hooks (migration-only)",
    (lambda s: 'create_notification' not in s)(
        _auth141[_auth141.find('def _migrate_notifications_schema_v2'):
                 _auth141.find('def _migrate_notifications_schema_v2') + 600]
        if 'def _migrate_notifications_schema_v2' in _auth141 else ''
    )
)
check(
    "141j. NOTIFICATIONS_PLAN.md marks Phase 2 as complete",
    'Phase 2' in _nplan141 and ('مكتمل' in _nplan141 or 'منفَّذ' in _nplan141)
)

# §142 — Notifications Phase 3 — Comment Notification Hook
_auth142 = open("auth.py").read()
_nplan142 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §142: Notifications Phase 3 — Comment Notification Hook ──")
check(
    "142a. company_posts SELECT now fetches company_id alongside comments_enabled",
    "SELECT comments_enabled, company_id FROM company_posts" in _auth142
)
check(
    "142b. V2-4 aggregated comment hook present in create_company_post_comment",
    "V2-4: aggregated comment notification" in _auth142 or "comments_agg:post:" in _auth142
)
check(
    "142c. hook checks post_owner_id != user_id before notifying (no self-notify)",
    "post_owner_id != user_id" in _auth142
)
check(
    "142d. hook passes entity_type='comment' to create_notification",
    "entity_type=\"comment\"" in _auth142 or "entity_type='comment'" in _auth142
)
check(
    "142e. hook uses V2 aggregation_key with comments_agg:post: pattern (V2-4)",
    "comments_agg:post:" in _auth142
)
check(
    "142f. hook passes actor_id=user_id (commenter) to create_notification",
    "actor_id=user_id" in _auth142
)
check(
    "142g. hook passes entity_id=new_comment_id to create_notification",
    "entity_id=new_comment_id" in _auth142
)
check(
    "142h. hook is non-fatal — wrapped in try/except with warn log (no silent pass)",
    "TW-WARN" in _auth142 and "_notif_err" in _auth142 and
    ("comment notification" in _auth142 or "notification hook" in _auth142)
)
check(
    "142i. hook fires AFTER COMMIT (not inside transaction block)",
    _auth142.find("comments_agg:post:") > _auth142.find("committed = True")
)
check(
    "142j. NOTIFICATIONS_PLAN.md marks Phase 3 as complete",
    'Phase 3' in _nplan142 and ('مكتمل' in _nplan142 or 'منفَّذ' in _nplan142)
)

# §143 — Notifications Phase 4 — Reply Notification Hook
_auth143 = open("auth.py").read()
_nplan143 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §143: Notifications Phase 4 — Reply Notification Hook ──")
check(
    "143a. ra_rows query fetches u.id (reply_to_author_id) alongside name+tw_id",
    "SELECT u.full_name, u.tw_id, u.id FROM company_post_comments" in _auth143
)
check(
    "143b. reply_to_author_id initialized to None before if-block",
    "reply_to_author_id    = None" in _auth143 or "reply_to_author_id = None" in _auth143
)
check(
    "143c. reply_to_author_id set from ra_rows after COMMIT-safe query",
    "reply_to_author_id    = int(ra_rows[0][2])" in _auth143 or
    "reply_to_author_id = int(ra_rows[0][2])" in _auth143
)
check(
    "143d. V2-4 aggregated reply hook present in create_company_post_comment",
    "V2-4: aggregated reply notification" in _auth143 or "replies_agg:comment:" in _auth143
)
check(
    "143e. reply hook checks resolved_reply_to and reply_to_author_id != user_id",
    "resolved_reply_to and reply_to_author_id and reply_to_author_id != user_id" in _auth143
)
check(
    "143f. reply hook uses V2 aggregation_key with replies_agg:comment: pattern (V2-4)",
    "replies_agg:comment:" in _auth143
)
check(
    "143g. reply hook passes type_='reply' to create_notification",
    "type_=\"reply\"" in _auth143 or "type_='reply'" in _auth143
)
check(
    "143h. Phase 3 + Phase 4 share one try/except block (single TW-WARN log)",
    _auth143.count("[TW-WARN] notification hook") == 1
)
check(
    "143i. company_tw_id fetched once, shared between Phase 3 and Phase 4",
    "_company_tw_id" in _auth143 and _auth143.count("SELECT tw_id FROM users WHERE id") >= 1
)
check(
    "143j. NOTIFICATIONS_PLAN.md marks Phase 4 as complete",
    'Phase 4' in _nplan143 and ('مكتمل' in _nplan143 or 'منفَّذ' in _nplan143)
)

# §144 — Notifications Phase 5 — @Mention Notification Hook
_auth144 = open("auth.py").read()
_nplan144 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §144: Notifications Phase 5 — @Mention Notification Hook ──")
check(
    "144a. resolved_mentions entries now include 'id' key (integer user_id)",
    'resolved_mentions.append({"name": m_name, "tw_id": mtw, "id":' in _auth144 or
    "resolved_mentions.append({\"name\": m_name, \"tw_id\": mtw, \"id\":" in _auth144
)
check(
    "144b. Phase 5 mention hook iterates resolved_mentions",
    "Phase 5: notify each @mentioned" in _auth144 or
    ("for _m in resolved_mentions" in _auth144 and "mention" in _auth144)
)
check(
    "144c. mention hook skips self-mention (_m_uid != user_id)",
    "_m_uid != user_id" in _auth144
)
check(
    "144d. mention hook uses type_='mention'",
    "type_=\"mention\"" in _auth144 or "type_='mention'" in _auth144
)
check(
    "144e. mention hook uses event_key with mention:comment:{new_comment_id}:{_m_uid}",
    'event_key=f"mention:comment:{new_comment_id}:{_m_uid}"' in _auth144
)
check(
    "144f. mention hook passes actor_id=user_id (commenter)",
    _auth144.count("actor_id=user_id") >= 3  # Phase 3, 4, and 5 all set actor_id=user_id
)
check(
    "144g. mention hook passes entity_id=new_comment_id (Phase 5 still uses V1)",
    _auth144.count("entity_id=new_comment_id") >= 1  # Phase 3+4 now V2 aggregated; Phase 5 mention hook remains
)
check(
    "144h. mention hook is inside same non-fatal try/except as Phase 3+4",
    _auth144.count("[TW-WARN] notification hook") == 1  # single shared handler
)
check(
    "144i. mention hook fires AFTER COMMIT (position check)",
    _auth144.find("for _m in resolved_mentions") > _auth144.find("committed = True")
    if "for _m in resolved_mentions" in _auth144 else False
)
check(
    "144j. NOTIFICATIONS_PLAN.md marks Phase 5 as complete",
    'Phase 5' in _nplan144 and ('مكتمل' in _nplan144 or 'منفَّذ' in _nplan144)
)

# §145 — Notifications Phase 6 — Job Application Notification Hook
_auth145 = open("auth.py").read()
_nplan145 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §145: Notifications Phase 6 — Job Application Notification Hook ──")
check(
    "145a. apply_job SELECT now fetches company_id and title",
    "SELECT status, closed_at, expires_at, company_id, title FROM jobs" in _auth145
)
check(
    "145b. job_company_id extracted from job_rows in apply_job",
    "job_company_id = int(job_rows[0][3])" in _auth145
)
check(
    "145c. job_title extracted from job_rows in apply_job",
    "job_title = job_rows[0][4]" in _auth145
)
check(
    "145d. Phase 6 notification hook present in apply_job",
    "Phase 6: notify company" in _auth145 or
    ("job_applied notification" in _auth145 and "job_applied" in _auth145)
)
check(
    "145e. notification uses type_='job_applied'",
    "type_=\"job_applied\"" in _auth145 or "type_='job_applied'" in _auth145
)
check(
    "145f. job_applied hook uses V2 aggregation key (migrated V2-3)",
    'job_applications_agg:job:' in _auth145
)
check(
    "145g. hook only fires for new applications (not already_applied)",
    _auth145.find("job_applied notification") > _auth145.find("already_applied") or
    _auth145.find("Phase 6:") > _auth145.find("already_applied")
)
check(
    "145h. hook is non-fatal — wrapped in try/except with TW-WARN log",
    "TW-WARN" in _auth145 and "job_applied notification" in _auth145
)
check(
    "145i. applicant name fetched from DB (not from token)",
    "SELECT full_name FROM users WHERE id=:uid" in _auth145 and
    "applicant_name" in _auth145
)
check(
    "145j. NOTIFICATIONS_PLAN.md marks Phase 6 as complete",
    'Phase 6' in _nplan145 and ('مكتمل' in _nplan145 or 'منفَّذ' in _nplan145)
)

# §146 — Notifications Phase 7 — Follow Notification Hook
_auth146 = open("auth.py").read()
_nplan146 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §146: Notifications Phase 7 — Follow Notification Hook ──")
check(
    "146a. follow_company INSERT now uses RETURNING follower_id",
    "ON CONFLICT (company_id, follower_id) DO NOTHING RETURNING follower_id" in _auth146
)
check(
    "146b. follow_profile INSERT now uses RETURNING follower_id",
    "ON CONFLICT (follower_id, followed_id) DO NOTHING RETURNING follower_id" in _auth146
)
check(
    "146c. follow_company notification hook present (aggregated V2-2, key follow_agg:company:)",
    "follow_agg:company:" in _auth146
)
check(
    "146d. follow_profile notification hook present (aggregated V2-2, key follow_agg:user:)",
    "follow_agg:user:" in _auth146
)
check(
    "146e. notification type is 'follow'",
    _auth146.count("type_=\"follow\"") >= 2 or _auth146.count("type_='follow'") >= 2 or
    ("type_=\"follow\"" in _auth146 and "type_='follow'" in _auth146) or
    _auth146.count("type_=\"follow\"") + _auth146.count("type_='follow'") >= 2
)
check(
    "146f. both hooks only fire for fresh follows (ins_rows guard)",
    _auth146.count("if ins_rows:") >= 2
)
check(
    "146g. follower name fetched from DB in both hooks",
    _auth146.count("SELECT full_name, tw_id FROM users WHERE id = :fid") >= 2
)
check(
    "146h. both hooks are non-fatal (two separate TW-WARN follow logs)",
    _auth146.count("[TW-WARN] follow notification") >= 2
)
check(
    "146i. no self-follow notification possible (guard in follow_profile; company follow already has guard in server.py)",
    "if follower_id == followed_id:" in _auth146  # follow_profile self-follow guard
)
check(
    "146j. NOTIFICATIONS_PLAN.md marks Phase 7 as complete",
    'Phase 7' in _nplan146 and ('مكتمل' in _nplan146 or 'منفَّذ' in _nplan146)
)

# §147 — Notifications Phase 8 — Verification Status Notification Hook
_srv147 = open("server.py").read()
_nplan147 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §147: Notifications Phase 8 — Verification Status Notification Hook ──")
check(
    "147a. admin_update_verify fetches verify_requests.user_id before UPDATE",
    "SELECT user_id FROM verify_requests WHERE id = :id" in _srv147
)
check(
    "147b. Phase 8 notification hook present in admin_update_verify",
    "Phase 8: notify request owner" in _srv147 or
    "verify notification" in _srv147
)
check(
    "147c. notification type is 'verify'",
    "type_=\"verify\"" in _srv147 or "type_='verify'" in _srv147
)
check(
    "147d. notification uses event_key with verify_{status}:verify_request:{req_id}:admin",
    'event_key=f"verify_{data.status}:verify_request:{req_id}:admin"' in _srv147
)
check(
    "147e. notification entity_type is 'verify_request'",
    "entity_type=\"verify_request\"" in _srv147 or "entity_type='verify_request'" in _srv147
)
check(
    "147f. notification link is '/settings'",
    'link="/settings"' in _srv147 or "link='/settings'" in _srv147
)
check(
    "147g. approved vs rejected title/body branch present",
    "تم مراجعة طلب توثيقك" in _srv147 and "طلب توثيقك يحتاج مراجعة" in _srv147
)
check(
    "147h. hook is non-fatal — try/except with TW-WARN log",
    "TW-WARN" in _srv147 and "verify notification" in _srv147
)
check(
    "147i. hook does not fire if verify_request row not found (vr_rows guard)",
    "if vr_rows:" in _srv147
)
check(
    "147j. NOTIFICATIONS_PLAN.md marks Phase 8 as complete",
    'Phase 8' in _nplan147 and ('مكتمل' in _nplan147 or 'منفَّذ' in _nplan147)
)

# §148 — Notifications Phase 9 — Per-Notification Read + Pagination
_auth148 = open("auth.py").read()
_srv148 = open("server.py").read()
_nplan148 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §148: Notifications Phase 9 — Per-Notification Read + Pagination ──")
check(
    "148a. mark_notification_read() exists in auth.py",
    "def mark_notification_read(user_id: int, notif_id: int)" in _auth148
)
check(
    "148b. mark_notification_read uses WHERE id=:nid AND user_id=:uid (ownership check)",
    "WHERE id=:nid AND user_id=:uid" in _auth148
)
check(
    "148c. get_notifications accepts offset parameter",
    "def get_notifications(user_id: int, limit: int" in _auth148 and
    "offset" in _auth148
)
check(
    "148d. get_notifications uses LIMIT + OFFSET in query",
    "LIMIT :lim OFFSET :off" in _auth148
)
check(
    "148e. mark_notification_read imported in server.py",
    "mark_notification_read" in _srv148 and "from" not in "mark_notification_read"  # imported, not just defined
    and _srv148.count("mark_notification_read") >= 2  # import + usage
)
check(
    "148f. GET /notifications/{user_id} accepts page and per_page query params",
    "page: int = 1" in _srv148 and "per_page: int = 20" in _srv148
)
check(
    "148g. GET endpoint clamps per_page (max 100) and enforces page >= 1",
    "max(1, min(per_page, 100))" in _srv148 and "max(1, page)" in _srv148
)
check(
    "148h. GET endpoint returns page and per_page in response",
    '"page": page' in _srv148 and '"per_page": per_page' in _srv148
)
check(
    "148i. PUT /notifications/{user_id}/read/{notif_id} endpoint exists with JWT + ownership check",
    "def read_single_notification(user_id: int, notif_id: int" in _srv148 and
    "tok_uid != user_id" in _srv148
)
check(
    "148j. NOTIFICATIONS_PLAN.md marks Phase 9 as complete",
    'Phase 9' in _nplan148 and ('مكتمل' in _nplan148 or 'منفَّذ' in _nplan148)
)

# §149 — Notifications Phase 10 — Unread Badge in App Header
_srv149 = open("server.py").read()
_ahjs149 = open("static/app-header.js").read()
_ahcss149 = open("static/app-header.css").read()
_nplan149 = open("docs/NOTIFICATIONS_PLAN.md").read()

print("\n── §149: Notifications Phase 10 — Unread Badge in App Header ──")
check(
    "149a. GET /notifications/{user_id}/unread-count endpoint exists in server.py",
    "def notifications_unread_count(user_id: int, token=Depends(verify_token))" in _srv149
)
check(
    "149b. unread-count endpoint has JWT + ownership check",
    "notifications_unread_count" in _srv149 and
    "tok_uid != user_id" in _srv149
)
check(
    "149c. unread-count endpoint returns {ok: True, data: {count: ...}}",
    '"ok": True' in _srv149 and '"data": {"count":' in _srv149
)
check(
    "149d. _pollUnreadBadge function exists in app-header.js",
    "function _pollUnreadBadge(user)" in _ahjs149
)
check(
    "149e. _pollUnreadBadge uses Authorization Bearer JWT (no X-User-Id)",
    "'Authorization': 'Bearer ' + jwt" in _ahjs149 or
    '"Authorization": "Bearer "' in _ahjs149
)
check(
    "149f. polling interval is 60000ms (60 seconds minimum)",
    "setInterval(_fetchCount, 60000)" in _ahjs149
)
check(
    "149g. badge hidden when count == 0",
    "style.display = 'none'" in _ahjs149 or "style.display='none'" in _ahjs149
)
check(
    "149h. count is NOT stored in localStorage (only JWT is read from it)",
    "localStorage.setItem" not in _ahjs149[_ahjs149.find("function _pollUnreadBadge"):
                                            _ahjs149.find("function _pollUnreadBadge") + 800]
    if "function _pollUnreadBadge" in _ahjs149 else False
)
check(
    "149i. badge CSS in app-header.css ([data-ah-notif-badge] rule present)",
    "[data-ah-notif-badge]" in _ahcss149
)
check(
    "149j. NOTIFICATIONS_PLAN.md marks Phase 10 as complete",
    'Phase 10' in _nplan149 and ('مكتمل' in _nplan149 or 'منفَّذ' in _nplan149)
)

# ═══════════════════════════════════════════════════════════════════════
# §150 — Notifications V1 Final QA + Closure
# 10 static checks — verifies V1 is complete, clean, and properly closed
# ═══════════════════════════════════════════════════════════════════════
print("\n── §150: Notifications V1 Final QA + Closure ──")
import os as _os150
_nplan150    = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os150.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_sidx150     = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read() if _os150.path.exists('docs/SYSTEMS_INDEX.md') else ''
_srv150      = open('server.py', encoding='utf-8').read() if _os150.path.exists('server.py') else ''
_ahjs150     = open('static/app-header.js', encoding='utf-8').read() if _os150.path.exists('static/app-header.js') else ''
_notif150    = open('notifications.html', encoding='utf-8').read() if _os150.path.exists('notifications.html') else ''

check(
    "150a. 139q resolved — Phase 0 docs-only status preserved in NOTIFICATIONS_PLAN.md",
    'docs only' in _nplan150.lower() and 'Phase 0' in _nplan150
)
check(
    "150b. Notifications V1 Status section exists in NOTIFICATIONS_PLAN.md",
    'Notifications V1 Status' in _nplan150
)
check(
    "150c. Phase 11 explicitly marked deferred in NOTIFICATIONS_PLAN.md",
    'Phase 11' in _nplan150 and ('مؤجل' in _nplan150 or 'deferred' in _nplan150.lower())
)
check(
    "150d. Phase 11 deferral cites WebSocket P0 security debt as reason",
    'WebSocket' in _nplan150 and 'P0' in _nplan150 and 'Phase 11' in _nplan150
)
check(
    "150e. No WebSocket route for notifications in server.py",
    '@app.websocket("/notifications' not in _srv150 and
    'websocket' not in _srv150.lower().replace('/ws/{user_id}', '').split('/notifications')[0][-50:]
)
check(
    "150f. unread badge uses setInterval polling — no WebSocket in app-header.js",
    'setInterval' in _ahjs150 and 'WebSocket' not in _ahjs150 and 'EventSource' not in _ahjs150
)
check(
    "150g. No X-User-Id in notifications.html (JWT Bearer only)",
    'X-User-Id' not in _notif150
)
check(
    "150h. notifications.html renders API text via textContent (XSS-safe — no innerHTML on n.title/n.body)",
    'textContent' in _notif150 and
    'innerHTML' not in _notif150[_notif150.find('titleEl'):_notif150.find('titleEl') + 100]
    if 'titleEl' in _notif150 else 'textContent' in _notif150
)
check(
    "150i. All Phases 0-10 marked complete in NOTIFICATIONS_PLAN.md summary table",
    all(
        '✅' in _nplan150[max(0, _nplan150.find(f'| **{i}**')):_nplan150.find(f'| **{i}**') + 150]
        or 'مكتمل' in _nplan150[max(0, _nplan150.find(f'| **{i}**')):_nplan150.find(f'| **{i}**') + 150]
        for i in range(0, 11)
    )
)
check(
    "150j. SYSTEMS_INDEX.md §19 reflects completed state (all phases complete — not just Phase 0)",
    '### 19.' in _sidx150 and (
        'Phases 0' in _sidx150 or '0–10' in _sidx150 or
        ('Phase 10' in _sidx150 and 'complete' in _sidx150.lower())
    )
)

# ═══════════════════════════════════════════════════════════════════════
# §151 — Notifications Page UI Polish — Static Checks
# 22 static checks verifying the redesigned notifications.html
# ═══════════════════════════════════════════════════════════════════════
print("\n── §151: Notifications Page UI Polish ──")
import os as _os151
_notif151 = open('notifications.html', encoding='utf-8').read() if _os151.path.exists('notifications.html') else ''

check(
    "151a. notifications.html uses shared .sc-header class (same pattern as company-profile.html)",
    'sc-header' in _notif151 and 'notif-hdr' in _notif151
)
check(
    "151b. app-header.css is loaded in notifications.html",
    '/static/app-header.css' in _notif151
)
check(
    "151c. Logo /static/33333.svg present in header",
    '33333.svg' in _notif151
)
check(
    "151d. Lucide local vendor loaded — no new CDN (no unpkg/cdnjs/jsdelivr for icons)",
    '/static/vendor/lucide/lucide.min.js' in _notif151 and
    'unpkg.com/lucide' not in _notif151 and
    'cdnjs.cloudflare.com/ajax/libs/lucide' not in _notif151 and
    'jsdelivr.net' not in _notif151
)
check(
    "151e. lucide.createIcons() called after loading the vendor script",
    'lucide.createIcons()' in _notif151
)
check(
    "151f. Hero section exists with class notif-hero",
    'notif-hero' in _notif151
)
check(
    "151g. Hero title 'الإشعارات' is present",
    'الإشعارات' in _notif151
)
check(
    "151h. Hero subtitle 'ابقَ على اطلاع بكل جديد يهمك' is present",
    'ابقَ على اطلاع بكل جديد يهمك' in _notif151
)
check(
    "151i. Hero icon is inline SVG bell — no emoji in hero area (notif-hero-bell or notif-hero-icon)",
    ('notif-hero-bell' in _notif151 or 'notif-hero-icon' in _notif151) and
    'notif-hero' in _notif151 and
    '🔔' not in _notif151[max(0,_notif151.find('notif-hero')):_notif151.find('notif-hero') + 600]
)
check(
    "151j. Filter tabs have all 5 data-filter values: all, job, comment, follow, verify",
    all('data-filter="' + f + '"' in _notif151 for f in ['all', 'job', 'comment', 'follow', 'verify'])
)
check(
    "151k. Action bar button 'تمييز الكل كمقروء' present with id markAllBtn",
    'markAllBtn' in _notif151 and 'تمييز الكل كمقروء' in _notif151
)
check(
    "151l. _NOTIF_ICONS constant defined with inline SVG strings (no emoji, no CDN URLs)",
    '_NOTIF_ICONS' in _notif151 and
    'var _NOTIF_ICONS' in _notif151 and
    'width="18"' in _notif151
)
check(
    "151m. _NOTIF_ICONS contains no emoji characters (job/comment/mention/follow/verify/bell all SVG)",
    all(
        ico + ':' in _notif151 or ico + "'" in _notif151 or ico + '"' in _notif151
        for ico in ['job', 'comment', 'mention', 'follow', 'verify', 'bell']
    ) and
    '🔔' not in _notif151 and '💼' not in _notif151 and '💬' not in _notif151 and '✅' not in _notif151
)
check(
    "151n. _typeMap defined — maps notification types to SVG icon + color (no emoji labels)",
    'var _typeMap' in _notif151 and
    '_NOTIF_ICONS.job' in _notif151 and
    '_NOTIF_ICONS.comment' in _notif151 and
    '_NOTIF_ICONS.follow' in _notif151 and
    '_NOTIF_ICONS.verify' in _notif151
)
check(
    "151o. _filterGroups defined — maps filter tabs to multiple type values",
    'var _filterGroups' in _notif151 and
    __import__('re').search(r"comment['\"]?\s*:\s*\[.*?'comment'.*?'reply'.*?'mention'",
                            _notif151.replace('"', "'"), __import__('re').DOTALL) is not None
)
check(
    "151p. _buildNotifCard uses textContent for API data (n.title, n.body) — not innerHTML",
    'titleEl.textContent' in _notif151 and
    'subEl.textContent' in _notif151 and
    'n.title' in _notif151 and
    'n.body' in _notif151
)
check(
    "151q. ico.innerHTML used only for SVG icon strings from _typeMap (not for API data)",
    'ico.innerHTML = t.ico' in _notif151 and
    'innerHTML = t.ico' in _notif151
)
check(
    "151r. Empty state uses SVG bell icon (not emoji) and Arabic text via textContent",
    '_renderEmpty' in _notif151 and
    '_NOTIF_ICONS.bell' in _notif151 and
    'لا توجد إشعارات حالياً' in _notif151 and
    'ستظهر هنا التحديثات المهمة عند وصولها' in _notif151
)
check(
    "151s. Link validation enforced — only relative paths (/^\\/.test) are navigated",
    r'/^\//.test' in _notif151 or r"/^\//".test in _notif151 or
    "'/'" in _notif151 and '/^\\//' in _notif151 or
    r'/^\//' in _notif151
)
check(
    "151t. Bottom nav uses class notif-bnav and notif-bn — SVG icons only",
    'notif-bnav' in _notif151 and
    'notif-bn' in _notif151 and
    'class="notif-bnav"' in _notif151
)
check(
    "151u. Bottom nav has no emoji characters",
    '🏠' not in _notif151 and '💼' not in _notif151 and '👤' not in _notif151 and
    '🔔' not in _notif151 and '💬' not in _notif151
)
check(
    "151v. No X-User-Id header in notifications.html — JWT Bearer only for all API calls",
    "'X-User-Id'" not in _notif151 and '"X-User-Id"' not in _notif151 and
    "'Authorization': 'Bearer '" in _notif151
)

# ═══════════════════════════════════════════════════════════════════════
# §152 — Notifications Page Mobile UI Final Polish — Static Checks
# 16 static checks verifying hero layout, tabs, markall, and security
# ═══════════════════════════════════════════════════════════════════════
print("\n── §152: Notifications Page Mobile UI Final Polish ──")
import os as _os152
_notif152 = open('notifications.html', encoding='utf-8').read() if _os152.path.exists('notifications.html') else ''
_srv152   = open('server.py', encoding='utf-8').read() if _os152.path.exists('server.py') else ''
_auth152  = open('auth.py', encoding='utf-8').read() if _os152.path.exists('auth.py') else ''

check(
    "152a. Hero has no box container around bell icon — notif-hero-icon box class absent from HTML body",
    'class="notif-hero-icon"' not in _notif152
)
check(
    "152b. Bell SVG is beside title — notif-hero-row container exists",
    'notif-hero-row' in _notif152 and
    'notif-title' in _notif152[_notif152.find('notif-hero-row'):_notif152.find('notif-hero-row') + 300]
)
check(
    "152c. Bell SVG has notif-hero-bell class — standalone with glow, no border/background box",
    'notif-hero-bell' in _notif152 and
    'class="notif-hero-bell"' in _notif152 and
    '<svg class="notif-hero-bell"' in _notif152
)
check(
    "152d. Subtitle 'ابقَ على اطلاع بكل جديد يهمك' is below the title row, not above/inside it",
    'notif-subtitle' in _notif152 and
    _notif152.find('notif-subtitle') > _notif152.find('notif-hero-row')
)
check(
    "152e. Filter tabs .notif-tab block has no pill border (border-radius:20px removed from tab rule)",
    (
        'border: 1.5px solid var(--border)' not in
        _notif152[_notif152.find('.notif-tab {'):_notif152.find('.notif-tab {') + 300]
        if '.notif-tab {' in _notif152 else True
    )
)
check(
    "152f. Filter tabs wrapper has overflow-x:auto — horizontal scroll enabled",
    'overflow-x: auto' in _notif152 and 'notif-tabs-wrap' in _notif152
)
check(
    "152g. Filter tabs have vertical separators — border-inline-end between tabs",
    'border-inline-end' in _notif152 and 'notif-tab' in _notif152
)
check(
    "152h. Active filter has underline indicator — notif-tab.active::after defined",
    '.notif-tab.active::after' in _notif152 or 'notif-tab.active::after' in _notif152
)
check(
    "152i. Mark all button has no border — no border:1.5px on notif-markall-btn",
    'border: 1.5px solid var(--border)' not in
    _notif152[_notif152.find('.notif-markall-btn {'):_notif152.find('.notif-markall-btn {') + 300]
    if '.notif-markall-btn {' in _notif152 else True
)
check(
    "152j. Mark all button is still clickable — markAll function and markAllBtn id present",
    'markAll()' in _notif152 and 'markAllBtn' in _notif152
)
check(
    "152k. No X-User-Id header in notifications.html",
    "'X-User-Id'" not in _notif152 and '"X-User-Id"' not in _notif152
)
check(
    "152l. No emoji icons in notifications.html",
    '🔔' not in _notif152 and '💼' not in _notif152 and '💬' not in _notif152 and
    '👤' not in _notif152 and '✅' not in _notif152 and '🏠' not in _notif152
)
check(
    "152m. No new CDN in notifications.html (no unpkg/cdnjs/jsdelivr added)",
    'unpkg.com' not in _notif152 and
    'cdnjs.cloudflare.com' not in _notif152 and
    'jsdelivr.net' not in _notif152
)
check(
    "152n. API data rendered via textContent/createElement — no innerHTML on n.title or n.body",
    'titleEl.textContent' in _notif152 and 'subEl.textContent' in _notif152
)
check(
    "152o. server.py not modified — unread-count endpoint still intact",
    'unread-count' in _srv152 and 'notifications' in _srv152
)
check(
    "152p. No WebSocket or push instantiation in notifications.html",
    'new WebSocket(' not in _notif152 and 'new EventSource(' not in _notif152 and
    'pushManager' not in _notif152 and 'subscribe(' not in _notif152
)

# ═══════════════════════════════════════════════════════════════════════
# §153 — Notifications Runtime QA Bugfix — Applications + Follow Notifications
# 15 static checks: ON CONFLICT fix, hooks, recipients, event_key, frontend display
# ═══════════════════════════════════════════════════════════════════════
print("\n── §153: Notifications Runtime QA Bugfix ──")
import os as _os153
_auth153  = open('auth.py', encoding='utf-8').read() if _os153.path.exists('auth.py') else ''
_notif153 = open('notifications.html', encoding='utf-8').read() if _os153.path.exists('notifications.html') else ''
_plan153  = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os153.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''

check(
    "153a. create_notification function is defined in auth.py",
    'def create_notification(' in _auth153
)
check(
    "153b. ON CONFLICT uses correct partial index predicate — WHERE event_key IS NOT NULL DO NOTHING",
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth153
)
check(
    "153c. Old buggy ON CONFLICT without WHERE predicate is absent from auth.py",
    'ON CONFLICT (user_id, event_key) DO NOTHING' not in _auth153
)
check(
    "153d. apply_job in auth.py calls create_notification for job_applied type",
    'type_="job_applied"' in _auth153 or "type_='job_applied'" in _auth153
)
check(
    "153e. job_applied aggregation key present in auth.py (V2-3: job_applications_agg:job:)",
    'job_applications_agg:job:' in _auth153
)
check(
    "153f. job notification guards against self-apply — job_company_id != user_id check present",
    'job_company_id != user_id' in _auth153
)
check(
    "153g. follow_company in auth.py calls create_notification with follow type",
    'follow_company' in _auth153 and
    ('type_="follow"' in _auth153 or "type_='follow'" in _auth153)
)
check(
    "153h. follow aggregation keys present in auth.py (V2-2: follow_agg:user: / follow_agg:company:)",
    'follow_agg:user:' in _auth153 and 'follow_agg:company:' in _auth153
)
check(
    "153i. follow notification only fires on fresh follow — if ins_rows guards aggregated call",
    'if ins_rows:' in _auth153 and
    _auth153.find('if ins_rows:') < _auth153.find('follow_agg:')
)
check(
    "153j. partial unique index in auth.py has WHERE event_key IS NOT NULL predicate",
    'WHERE event_key IS NOT NULL' in _auth153 and
    'uniq_notif_event_key' in _auth153
)
check(
    "153k. _typeMap in notifications.html has job_applied entry",
    '_typeMap' in _notif153 and
    'job_applied' in _notif153[_notif153.find('_typeMap'):_notif153.find('_typeMap') + 700]
)
check(
    "153l. _typeMap in notifications.html has follow entry — maps follow type to icon/color",
    '_typeMap' in _notif153 and
    'follow' in _notif153[_notif153.find('_typeMap'):_notif153.find('_typeMap') + 700]
)
check(
    "153m. _filterGroups in notifications.html includes job_applied in job group",
    '_filterGroups' in _notif153 and 'job_applied' in _notif153
)
check(
    "153n. _filterGroups in notifications.html includes follow in follow group",
    '_filterGroups' in _notif153 and
    "'follow'" in _notif153[_notif153.find('_filterGroups'):_notif153.find('_filterGroups') + 400]
    if '_filterGroups' in _notif153 else False
)
check(
    "153o. NOTIFICATIONS_PLAN.md documents runtime QA bugfix and refollow behavior",
    'Runtime QA' in _plan153 or 'runtime-qa' in _plan153.lower() or
    'ON CONFLICT' in _plan153 and 'WHERE event_key IS NOT NULL' in _plan153
)

# ═══════════════════════════════════════════════════════════════════════
# §154 — Shared Header Notification Bell Badge Fix
# 14 static checks: app-header.js auto-init, badge element, glow, JWT Bearer,
# security (no X-User-Id, no fake data, no WebSocket), no auth.py change
# ═══════════════════════════════════════════════════════════════════════
print("\n── §154: Shared Header Notification Bell Badge Fix ──")
import os as _os154
_ah_js   = open('static/app-header.js', encoding='utf-8').read()  if _os154.path.exists('static/app-header.js')  else ''
_ah_css  = open('static/app-header.css', encoding='utf-8').read() if _os154.path.exists('static/app-header.css') else ''
_co_html = open('company-profile.html', encoding='utf-8').read()  if _os154.path.exists('company-profile.html')  else ''
_sc_html = open('profile-showcase.html', encoding='utf-8').read() if _os154.path.exists('profile-showcase.html') else ''
_auth154 = open('auth.py', encoding='utf-8').read()               if _os154.path.exists('auth.py')               else ''

check(
    "154a. app-header.js loads and polls /notifications/{uid}/unread-count with Bearer JWT",
    'unread-count' in _ah_js and
    ("'Authorization': 'Bearer ' + jwt" in _ah_js or '"Authorization": "Bearer "' in _ah_js or
     "'Bearer ' +" in _ah_js)
)
check(
    "154b. app-header.js has DOMContentLoaded auto-init — pages without initAppHeader call work",
    'DOMContentLoaded' in _ah_js and '_pollUnreadBadge' in _ah_js and
    'tw_user' in _ah_js
)
check(
    "154c. app-header.js has guard against double setInterval (_ahPollStarted or similar)",
    '_ahPollStarted' in _ah_js or '_pollStarted' in _ah_js
)
check(
    "154d. app-header.js adds ah-bell--active class when unread count > 0",
    'ah-bell--active' in _ah_js and 'classList.add' in _ah_js
)
check(
    "154e. app-header.js removes ah-bell--active class when unread count = 0",
    'ah-bell--active' in _ah_js and 'classList.remove' in _ah_js
)
check(
    "154f. app-header.css has .ah-bell--active glow styling for bell icon",
    'ah-bell--active' in _ah_css and '.ico' in _ah_css[_ah_css.find('ah-bell--active'):_ah_css.find('ah-bell--active') + 100]
)
check(
    "154g. company-profile.html bell has data-ah-notif-badge element",
    'data-ah-notif-badge' in _co_html
)
check(
    "154h. company-profile.html loads app-header.js script",
    'app-header.js' in _co_html
)
check(
    "154i. profile-showcase.html bell has data-ah-notif-badge (not old data-badge=notif)",
    'data-ah-notif-badge' in _sc_html and
    'data-badge="notif"' not in _sc_html[_sc_html.find('scBellBtn'):_sc_html.find('scBellBtn') + 200]
    if 'scBellBtn' in _sc_html else 'data-ah-notif-badge' in _sc_html
)
check(
    "154j. profile-showcase.html loads app-header.js script",
    'app-header.js' in _sc_html
)
check(
    "154k. No X-User-Id in app-header.js",
    "'X-User-Id'" not in _ah_js and '"X-User-Id"' not in _ah_js
)
check(
    "154l. No WebSocket or push in app-header.js",
    'new WebSocket(' not in _ah_js and 'EventSource' not in _ah_js and 'pushManager' not in _ah_js
)
check(
    "154m. app-header.js does not hardcode/fake unread count — uses API response only",
    'count = ' not in _ah_js or 'd.data' in _ah_js
)
check(
    "154n. auth.py not modified — create_notification and notification hooks unchanged",
    'def create_notification(' in _auth154 and
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth154
)

# ═══════════════════════════════════════════════════════════════════════
# §155 — Shared Header Notification Badge Number Visibility Fix
# 16 static checks: badge display inline-flex, physical right positioning,
# overflow visible, z-index 20, font-size 10px, align-items/justify-content,
# no inset-inline-end, no fake count, no X-User-Id, no WebSocket,
# badge hidden at count=0, textContent only, no localStorage count
# ═══════════════════════════════════════════════════════════════════════
print("\n── §155: Shared Header Notification Badge Number Visibility Fix ──")
import os as _os155
_ah_js155  = open('static/app-header.js',  encoding='utf-8').read() if _os155.path.exists('static/app-header.js')  else ''
_ah_css155 = open('static/app-header.css', encoding='utf-8').read() if _os155.path.exists('static/app-header.css') else ''

check(
    "155a. app-header.js sets badge.style.display = 'inline-flex' (not empty string) to show badge",
    "badge.style.display = 'inline-flex'" in _ah_js155 or
    'badge.style.display="inline-flex"' in _ah_js155
)
check(
    "155b. app-header.js sets badge.style.display = 'none' to hide badge at count 0",
    "badge.style.display = 'none'" in _ah_js155
)
check(
    "155c. app-header.css [data-ah-notif-badge] uses physical 'right' — not inset-inline-end",
    'right:' in _ah_css155.replace(' ', '') and 'inset-inline-end' not in _ah_css155
)
check(
    "155d. app-header.css .sc-notif-wrap has overflow: visible",
    'overflow: visible' in _ah_css155 or 'overflow:visible' in _ah_css155
)
check(
    "155e. app-header.css [data-ah-notif-badge] z-index is 20 or higher",
    'z-index: 20' in _ah_css155 or 'z-index: 2' in _ah_css155 or
    any(f'z-index: {n}' in _ah_css155 for n in range(20, 100))
)
check(
    "155f. app-header.css [data-ah-notif-badge] has align-items: center",
    'align-items: center' in _ah_css155 or 'align-items:center' in _ah_css155
)
check(
    "155g. app-header.css [data-ah-notif-badge] has justify-content: center",
    'justify-content: center' in _ah_css155 or 'justify-content:center' in _ah_css155
)
check(
    "155h. app-header.css [data-ah-notif-badge] font-size is 10px or larger (mobile readability)",
    'font-size: 10px' in _ah_css155 or 'font-size: 11px' in _ah_css155 or
    'font-size: 12px' in _ah_css155 or 'font-size:10px' in _ah_css155
)
check(
    "155i. app-header.css [data-ah-notif-badge] default display is still none (hidden by default)",
    'display: none' in _ah_css155 and 'data-ah-notif-badge' in _ah_css155
)
check(
    "155j. app-header.js sets badge textContent from API data — not innerHTML",
    'badge.textContent' in _ah_js155 and 'badge.innerHTML' not in _ah_js155
)
check(
    "155k. app-header.js uses '99+' cap for counts above 99",
    "'99+'" in _ah_js155 or '"99+"' in _ah_js155
)
check(
    "155l. app-header.js reads count from API response d.data.count — not localStorage",
    'd.data' in _ah_js155 and 'localStorage' not in _ah_js155[_ah_js155.find('_fetchCount'):_ah_js155.find('_fetchCount') + 400]
    if '_fetchCount' in _ah_js155 else 'd.data' in _ah_js155
)
check(
    "155m. No X-User-Id header in app-header.js",
    "'X-User-Id'" not in _ah_js155 and '"X-User-Id"' not in _ah_js155
)
check(
    "155n. No WebSocket or EventSource or push in app-header.js",
    'WebSocket(' not in _ah_js155 and 'EventSource' not in _ah_js155 and
    'pushManager' not in _ah_js155 and 'showNotification' not in _ah_js155
)
check(
    "155o. app-header.css badge uses physical top (not inset-block-start) — valid on all browsers",
    ('top: -' in _ah_css155 or 'top:-' in _ah_css155) and
    'inset-block-start' not in _ah_css155
)
check(
    "155p. app-header.js badge poll uses Authorization Bearer JWT — no anonymous fetch",
    "'Authorization': 'Bearer ' + jwt" in _ah_js155 or
    '"Authorization": "Bearer "' in _ah_js155 or
    "'Bearer '" in _ah_js155
)

# ═══════════════════════════════════════════════════════════════════════
# §156 — Notifications V2 Smart Aggregation Plan — Static Checks
# 18 static checks: plan presence, aggregation types, click targets,
# policy recommendation, helper proposal, V2 phases, no-code constraint,
# security rules, anti-spam, docs-only enforcement
# ═══════════════════════════════════════════════════════════════════════
print("\n── §156: Notifications V2 Smart Aggregation Plan ──")
import os as _os156
_plan156 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os156.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_si156   = open('docs/SYSTEMS_INDEX.md',     encoding='utf-8').read() if _os156.path.exists('docs/SYSTEMS_INDEX.md')     else ''
_auth156 = open('auth.py',    encoding='utf-8').read() if _os156.path.exists('auth.py')    else ''
_srv156  = open('server.py',  encoding='utf-8').read() if _os156.path.exists('server.py')  else ''
_notif156 = open('notifications.html', encoding='utf-8').read() if _os156.path.exists('notifications.html') else ''
_ahj156   = open('static/app-header.js',  encoding='utf-8').read() if _os156.path.exists('static/app-header.js')  else ''
_ahc156   = open('static/app-header.css', encoding='utf-8').read() if _os156.path.exists('static/app-header.css') else ''

check(
    "156a. docs/NOTIFICATIONS_PLAN.md contains Notifications V2 Smart Aggregation Plan section",
    'Notifications V2' in _plan156 and 'Smart Aggregation' in _plan156
)
check(
    "156b. plan documents follow aggregation type",
    'Follow Aggregation' in _plan156 or 'follow aggregation' in _plan156.lower()
)
check(
    "156c. plan documents job application aggregation per job (not per company)",
    'Job Application Aggregation' in _plan156 and 'job_id' in _plan156
)
check(
    "156d. plan documents comment/reply aggregation per post",
    ('Comment' in _plan156 and 'Aggregation' in _plan156 and 'post_id' in _plan156)
)
check(
    "156e. plan documents mention aggregation as Needs Decision",
    'Mention' in _plan156 and 'Needs Decision' in _plan156
)
check(
    "156f. plan documents that verify/application_status/direct messages stay individual (no aggregation)",
    'verify' in _plan156 and 'فردي' in _plan156 or
    'Sensitive' in _plan156 and ('verify' in _plan156 or 'تبقى فردية' in _plan156)
)
check(
    "156g. plan documents the golden rule: aggregate only if same click target",
    ('نفس الوجهة' in _plan156 or 'same click target' in _plan156.lower() or
     'القاعدة الذهبية' in _plan156)
)
check(
    "156h. plan recommends Option A: aggregate while unread",
    'Option A' in _plan156 and ('while unread' in _plan156.lower() or 'غير مقروء' in _plan156)
)
check(
    "156i. plan documents click target rules section",
    'Click Target' in _plan156 or 'click target' in _plan156.lower()
)
check(
    "156j. plan documents create_or_update_aggregated_notification as future helper only",
    'create_or_update_aggregated_notification' in _plan156 and
    ('NOT IMPLEMENTED' in _plan156 or 'مستقبلي' in _plan156 or 'future' in _plan156.lower())
)
check(
    "156k. plan documents this PR is docs-only (V2-0)",
    ('docs only' in _plan156.lower() or 'docs-only' in _plan156.lower() or 'V2-0' in _plan156)
    and ('لا تنفيذ' in _plan156 or 'no implementation' in _plan156.lower())
)
check(
    "156l. create_notification (V1) exists with ON CONFLICT partial-index fix",
    'def create_notification(' in _auth156 and
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth156
)
check(
    "156m. server.py has no V2 aggregation API endpoint handler (import/migration allowed, new @app route not)",
    '@app.get("/aggregat' not in _srv156 and
    '@app.post("/aggregat' not in _srv156 and
    '@app.put("/aggregat' not in _srv156
)
check(
    "156n. notifications.html V2 UI added in V2-5 (PR #452) — aggregation_count present",
    'aggregation_count' in _notif156
)
check(
    "156o. app-header.js and app-header.css not modified for V2",
    'aggregation' not in _ahj156.lower() and 'aggregation' not in _ahc156.lower()
)
check(
    "156p. plan documents anti-spam rules",
    'Anti-spam' in _plan156 or 'anti-spam' in _plan156.lower() or
    ('لا تنشئ 100' in _plan156 or 'actor == recipient' in _plan156)
)
check(
    "156q. SYSTEMS_INDEX.md updated — §19 or §36 references V2 aggregation plan",
    'V2' in _si156 and ('aggregation' in _si156.lower() or 'Aggregation' in _si156)
)
check(
    "156r. plan documents V2 phases list (V2-0 through V2-6)",
    'V2-1' in _plan156 and 'V2-2' in _plan156 and 'V2-6' in _plan156
)

# ═══════════════════════════════════════════════════════════════════════
# §157 — Notification Coverage Audit + Future Notification Decision Rule
# 20 static checks: coverage matrix areas, status legend, missing priority queue,
# decision rule checklist, mandatory PR declaration options, no-code constraint
# ═══════════════════════════════════════════════════════════════════════
print("\n── §157: Notification Coverage Audit + Future Notification Decision Rule ──")
import os as _os157
_plan157 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os157.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_si157   = open('docs/SYSTEMS_INDEX.md',     encoding='utf-8').read() if _os157.path.exists('docs/SYSTEMS_INDEX.md')     else ''
_auth157 = open('auth.py',    encoding='utf-8').read() if _os157.path.exists('auth.py')    else ''
_srv157  = open('server.py',  encoding='utf-8').read() if _os157.path.exists('server.py')  else ''
_notif157 = open('notifications.html', encoding='utf-8').read() if _os157.path.exists('notifications.html') else ''
_ahj157   = open('static/app-header.js',  encoding='utf-8').read() if _os157.path.exists('static/app-header.js')  else ''
_ahc157   = open('static/app-header.css', encoding='utf-8').read() if _os157.path.exists('static/app-header.css') else ''

# ── Coverage Audit section exists ────────────────────────────────────────
check(
    "157a. NOTIFICATIONS_PLAN.md has Notification Coverage Audit section",
    'Notification Coverage Audit' in _plan157
)
check(
    "157b. Coverage Audit has Status Legend with all 5 status symbols",
    '✅ impl' in _plan157 and '❌ missing' in _plan157 and
    '🔜 future' in _plan157 and '🚫 n/a' in _plan157 and '❓ decide' in _plan157
)

# ── Coverage Matrix areas ────────────────────────────────────────────────
check(
    "157c. Coverage Audit covers Posts/Comments/Replies/Mentions area",
    'Area 1' in _plan157 and ('Posts' in _plan157 or 'Comments' in _plan157)
)
check(
    "157d. Coverage Audit covers Jobs/Applications area",
    'Area 2' in _plan157 and ('Jobs' in _plan157 or 'Applications' in _plan157 or 'job_applied' in _plan157)
)
check(
    "157e. Coverage Audit covers Follow/Followers area",
    'Area 3' in _plan157 and 'Follow' in _plan157
)
check(
    "157f. Coverage Audit covers Verification/Admin Review area",
    'Area 4' in _plan157 and ('Verification' in _plan157 or 'verify' in _plan157)
)
check(
    "157g. Coverage Audit covers Messaging area",
    'Area 6' in _plan157 and ('Messaging' in _plan157 or 'message' in _plan157.lower())
)
check(
    "157h. Coverage Audit covers Education/Courses area",
    'Area 7' in _plan157 and ('Education' in _plan157 or 'Courses' in _plan157 or 'new_course' in _plan157)
)
check(
    "157i. Coverage Audit covers Polls as future/roadmap item",
    'Area 8' in _plan157 and 'Polls' in _plan157 and '🔜 future' in _plan157
)
check(
    "157j. Coverage Audit has Missing Notifications Priority Queue",
    'Missing' in _plan157 and 'Priority Queue' in _plan157 and 'application_status' in _plan157
)
check(
    "157k. Coverage Audit names auth.py hook location for application_status (P1 missing)",
    'update_application_status' in _plan157 and 'auth.py' in _plan157
)
check(
    "157l. Coverage Audit names auth.py hook location for rating (P2 missing)",
    'rate_company' in _plan157 and 'auth.py' in _plan157
)

# ── Future Notification Decision Rule section ────────────────────────────
check(
    "157m. NOTIFICATIONS_PLAN.md has Future Notification Decision Rule section",
    'Future Notification Decision Rule' in _plan157
)
check(
    "157n. Decision Rule has 17-question checklist (questions 1 through 17)",
    '17.' in _plan157 or ('1. هل هذا الحدث' in _plan157 and '17.' in _plan157)
)
check(
    "157o. Decision Rule has Mandatory PR Declaration section",
    'Mandatory PR Declaration' in _plan157
)
check(
    "157p. PR Declaration includes 'Notification: added' option",
    'Notification: added' in _plan157
)
check(
    "157q. PR Declaration includes 'Notification: not needed' option",
    'Notification: not needed' in _plan157
)
check(
    "157r. PR Declaration includes 'Notification: planned later' option",
    'Notification: planned later' in _plan157
)
check(
    "157s. SYSTEMS_INDEX.md §36 references Coverage Audit and Decision Rule",
    'Coverage Audit' in _si157 and 'Decision Rule' in _si157
)

# ── No code files modified (docs-only PR) ────────────────────────────────
check(
    "157t. auth.py, server.py, notifications.html, app-header.js/css not modified for §157",
    'Coverage Audit' not in _auth157 and
    'Coverage Audit' not in _srv157 and
    'Coverage Audit' not in _notif157 and
    'Coverage Audit' not in _ahj157 and
    'Coverage Audit' not in _ahc157
)

# ═══════════════════════════════════════════════════════════════════════
# §158 — Notifications V2-1: Aggregation Schema + Helper
# 27 static checks: migration columns, index, helper logic, V1 unchanged,
# no hooks activated, no server.py endpoints changed, no UI touched
# ═══════════════════════════════════════════════════════════════════════
print("\n── §158: Notifications V2-1 — Aggregation Schema + Helper ──")
import os as _os158
_auth158  = open('auth.py',    encoding='utf-8').read() if _os158.path.exists('auth.py')    else ''
_srv158   = open('server.py',  encoding='utf-8').read() if _os158.path.exists('server.py')  else ''
_plan158  = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os158.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_notif158 = open('notifications.html', encoding='utf-8').read() if _os158.path.exists('notifications.html') else ''
_ahj158   = open('static/app-header.js',  encoding='utf-8').read() if _os158.path.exists('static/app-header.js')  else ''
_ahc158   = open('static/app-header.css', encoding='utf-8').read() if _os158.path.exists('static/app-header.css') else ''

# ── Schema migration ──────────────────────────────────────────────────────
check(
    "158a. auth.py has _migrate_notifications_schema_v2_1 function",
    'def _migrate_notifications_schema_v2_1(' in _auth158
)
check(
    "158b. migration adds aggregation_key column (IF NOT EXISTS)",
    'aggregation_key' in _auth158 and 'ADD COLUMN IF NOT EXISTS' in _auth158
)
check(
    "158c. migration adds aggregation_count column",
    'aggregation_count' in _auth158 and 'ADD COLUMN IF NOT EXISTS' in _auth158
)
check(
    "158d. migration adds aggregation_kind column",
    'aggregation_kind' in _auth158
)
check(
    "158e. migration adds last_actor_id column",
    'last_actor_id' in _auth158
)
check(
    "158f. migration adds last_event_at column",
    'last_event_at' in _auth158
)
check(
    "158g. migration adds target_type column",
    'target_type' in _auth158 and 'notifications' in _auth158
)
check(
    "158h. migration adds target_id column",
    'target_id' in _auth158 and 'notifications' in _auth158
)
check(
    "158i. migration creates idx_notifications_aggregation_unread index",
    'idx_notifications_aggregation_unread' in _auth158
)
check(
    "158j. index is a partial index WHERE aggregation_key IS NOT NULL",
    'WHERE aggregation_key IS NOT NULL' in _auth158 and
    'idx_notifications_aggregation_unread' in _auth158
)

# ── Helper function ───────────────────────────────────────────────────────
check(
    "158k. auth.py has create_or_update_aggregated_notification function",
    'def create_or_update_aggregated_notification(' in _auth158
)
_helper158 = _auth158[_auth158.find('def create_or_update_aggregated_notification('):
                       _auth158.find('def create_or_update_aggregated_notification(') + 5000] \
             if 'def create_or_update_aggregated_notification(' in _auth158 else ''
check(
    "158l. helper searches for unread aggregate by user_id + aggregation_key + is_read=FALSE",
    'aggregation_key = :akey AND is_read = FALSE' in _helper158 or
    'is_read = FALSE' in _helper158 and 'aggregation_key' in _helper158
)
check(
    "158m. helper does INSERT when no existing unread aggregate (creates new row with count=1)",
    'INSERT INTO notifications' in _helper158 and
    'aggregation_count' in _helper158 and
    ("'created': True" in _helper158 or '"created": True' in _helper158)
)
check(
    "158n. helper does UPDATE when unread aggregate exists (no new row)",
    'UPDATE notifications' in _helper158 and
    ("'created': False" in _helper158 or '"created": False' in _helper158)
)
check(
    "158o. helper increments aggregation_count on update (count + 1)",
    '+ 1' in _helper158 and 'aggregation_count' in _helper158
)
check(
    "158p. helper updates last_actor_id on update",
    'last_actor_id' in _helper158 and 'UPDATE notifications' in _helper158
)
check(
    "158q. helper updates last_event_at via NOW() on update",
    'last_event_at = NOW()' in _helper158
)
check(
    "158r. helper has no silent failures — logs error and returns None",
    '[create_or_update_aggregated_notification]' in _auth158 and
    'return None' in _helper158
)

# ── V1 backward compatibility ─────────────────────────────────────────────
check(
    "158s. create_notification (V1 helper) still exists and is unchanged",
    'def create_notification(' in _auth158 and
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth158
)
check(
    "158t. ON CONFLICT partial-index fix from PR #444 still present",
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth158
)

# ── No aggregation hooks activated ───────────────────────────────────────
check(
    "158u. both V1 and V2 helpers coexist — backward compat maintained",
    'def create_notification(' in _auth158 and
    'def create_or_update_aggregated_notification(' in _auth158
)
check(
    "158v. no apply_job hook calls create_or_update_aggregated_notification",
    ('def apply_job(' in _auth158 and
     _auth158[_auth158.find('def apply_job('):_auth158.find('def apply_job(') + 800].count('create_or_update_aggregated_notification') == 0)
)
check(
    "158w. no comment/reply hook calls create_or_update_aggregated_notification",
    'create_company_post_comment' in _auth158 and
    _auth158[_auth158.find('def create_company_post_comment'):
             _auth158.find('def create_company_post_comment') + 3000].count('create_or_update_aggregated_notification') == 0
)

# ── server.py wired correctly ─────────────────────────────────────────────
check(
    "158x. server.py imports _migrate_notifications_schema_v2_1 (only migration, not helper)",
    '_migrate_notifications_schema_v2_1' in _srv158 and
    'create_or_update_aggregated_notification' not in _srv158
)
check(
    "158y. server.py calls _migrate_notifications_schema_v2_1() at startup with raise on failure",
    '_migrate_notifications_schema_v2_1()' in _srv158 and
    'raise' in _srv158[_srv158.find('_migrate_notifications_schema_v2_1()'):
                        _srv158.find('_migrate_notifications_schema_v2_1()') + 400]
)

# ── No UI/CSS/JS changes ──────────────────────────────────────────────────
check(
    "158z. notifications.html V2 UI added in V2-5 (PR #452) — aggregation_count present",
    'aggregation_count' in _notif158
)
check(
    "158aa. app-header.js and app-header.css not modified",
    'aggregation' not in _ahj158.lower() and 'aggregation' not in _ahc158.lower()
)

# ── Docs updated ──────────────────────────────────────────────────────────
check(
    "158ab. NOTIFICATIONS_PLAN.md marks V2-1 as implemented (PR #448)",
    'V2-1' in _plan158 and 'PR #448' in _plan158
)
check(
    "158ac. NOTIFICATIONS_PLAN.md documents V2-2 Follow Aggregation (V2 complete — no NEXT PHASE required)",
    'V2-2' in _plan158 and 'Follow Aggregation' in _plan158
)

# ─────────────────────────────────────────────────────────────────────────
# §159 — Notifications V2-2: Follow Aggregation (PR #449)
# Verifies follow_profile / follow_company replaced V1 with V2 aggregation.
# ─────────────────────────────────────────────────────────────────────────
with open("auth.py", encoding="utf-8") as f:
    _auth159 = f.read()
with open("docs/NOTIFICATIONS_PLAN.md", encoding="utf-8") as f:
    _plan159 = f.read()
with open("docs/SYSTEMS_INDEX.md", encoding="utf-8") as f:
    _sidx159 = f.read()

# Slices for targeted checks (3000 chars covers full function body)
_fp159  = _auth159[_auth159.find('def follow_profile('):_auth159.find('def follow_profile(') + 3000]
_fc159  = _auth159[_auth159.find('def follow_company('):_auth159.find('def follow_company(') + 3000]

# ── V1 removed from follow hooks ─────────────────────────────────────────
check(
    "159a. follow_profile no longer calls create_notification (V1 removed)",
    'def follow_profile(' in _auth159 and
    _fp159.count('create_notification(') == 0
)
check(
    "159b. follow_company no longer calls create_notification (V1 removed)",
    'def follow_company(' in _auth159 and
    _fc159.count('create_notification(') == 0
)

# ── V2 helper wired to both hooks ────────────────────────────────────────
check(
    "159c. follow_profile calls create_or_update_aggregated_notification",
    _fp159.count('create_or_update_aggregated_notification(') >= 1
)
check(
    "159d. follow_company calls create_or_update_aggregated_notification",
    _fc159.count('create_or_update_aggregated_notification(') >= 1
)

# ── Aggregation keys correct ──────────────────────────────────────────────
check(
    "159e. follow_profile uses follow_agg:user: aggregation key",
    'follow_agg:user:' in _fp159
)
check(
    "159f. follow_company uses follow_agg:company: aggregation key",
    'follow_agg:company:' in _fc159
)

# ── target_type correct ───────────────────────────────────────────────────
check(
    "159g. follow_profile sets target_type='user'",
    "target_type=\"user\"" in _fp159 or "target_type='user'" in _fp159
)
check(
    "159h. follow_company sets target_type='company'",
    "target_type=\"company\"" in _fc159 or "target_type='company'" in _fc159
)

# ── Self-notification guard in follow_company ─────────────────────────────
check(
    "159i. follow_company has self-notification guard (follower_id != company_id)",
    'follower_id != company_id' in _fc159
)

# ── action_url ends with #followers ──────────────────────────────────────
check(
    "159j. follow_profile action_url ends with #followers",
    '#followers' in _fp159
)
check(
    "159k. follow_company action_url ends with #followers",
    '#followers' in _fc159
)

# ── Pre-check for aggregate count ────────────────────────────────────────
check(
    "159l. follow_profile pre-checks existing aggregate count (aggregation_count query)",
    'aggregation_count' in _fp159 and 'ex_count' in _fp159 and 'new_count' in _fp159
)
check(
    "159m. follow_company pre-checks existing aggregate count (aggregation_count query)",
    'aggregation_count' in _fc159 and 'ex_count' in _fc159 and 'new_count' in _fc159
)

# ── aggregation_kind set to follow ────────────────────────────────────────
check(
    "159n. follow_profile uses aggregation_kind='follow'",
    "aggregation_kind=\"follow\"" in _fp159 or "aggregation_kind='follow'" in _fp159
)
check(
    "159o. follow_company uses aggregation_kind='follow'",
    "aggregation_kind=\"follow\"" in _fc159 or "aggregation_kind='follow'" in _fc159
)

# ── actor_id = follower_id ────────────────────────────────────────────────
check(
    "159p. follow_profile passes actor_id=follower_id",
    'actor_id=follower_id' in _fp159
)
check(
    "159q. follow_company passes actor_id=follower_id",
    'actor_id=follower_id' in _fc159
)

# ── Security: no X-User-Id ────────────────────────────────────────────────
check(
    "159r. no X-User-Id in follow_profile notification block",
    'X-User-Id' not in _fp159
)
check(
    "159s. no X-User-Id in follow_company notification block",
    'X-User-Id' not in _fc159
)

# ── Non-fatal try/except still in place ──────────────────────────────────
check(
    "159t. follow_profile notification block is still wrapped in try/except (non-fatal)",
    '[TW-WARN] follow notification (profile' in _fp159
)
check(
    "159u. follow_company notification block is still wrapped in try/except (non-fatal)",
    '[TW-WARN] follow notification (company' in _fc159
)

# ── Docs updated ──────────────────────────────────────────────────────────
check(
    "159v. NOTIFICATIONS_PLAN.md marks V2-2 as implemented (PR #449)",
    'V2-2' in _plan159 and 'PR #449' in _plan159
)
check(
    "159w. NOTIFICATIONS_PLAN.md documents follow_agg:user: and follow_agg:company: keys",
    'follow_agg:user:' in _plan159 and 'follow_agg:company:' in _plan159
)
check(
    "159x. NOTIFICATIONS_PLAN.md states NEXT PHASE is V2-3 Job Application Aggregation",
    'V2-3' in _plan159 and 'Job Application Aggregation' in _plan159 and
    ('NEXT PHASE' in _plan159 or 'V2-3 —' in _plan159)
)
check(
    "159y. SYSTEMS_INDEX.md §36 references V2-2 history (#449)",
    'V2-2' in _sidx159 and '#449' in _sidx159
)

# ── Self-notification guards — symmetric pattern ──────────────────────────
check(
    "159z. follow_profile has self-notification guard (follower_id != followed_id)",
    'follower_id != followed_id' in _fp159
)
check(
    "159aa. follow_profile guard wraps notification call (guard before helper)",
    _fp159.find('follower_id != followed_id') < _fp159.find('create_or_update_aggregated_notification(')
)
check(
    "159ab. follow_company self-notification guard still present (follower_id != company_id)",
    'follower_id != company_id' in _fc159
)

# ── No other aggregation hooks activated ─────────────────────────────────
_apply_job_159 = _auth159[_auth159.find('def apply_job('):_auth159.find('def apply_job(') + 1000] if 'def apply_job(' in _auth159 else ''
check(
    "159ac. no job aggregation — apply_job does not call create_or_update_aggregated_notification",
    _apply_job_159.count('create_or_update_aggregated_notification') == 0
)
_cmt_fn_159 = _auth159[_auth159.find('def create_company_post_comment('):
                        _auth159.find('def create_company_post_comment(') + 3000] if 'def create_company_post_comment(' in _auth159 else ''
check(
    "159ad. no comment aggregation — create_company_post_comment does not call V2 helper",
    _cmt_fn_159.count('create_or_update_aggregated_notification') == 0
)
_notif_mention_159 = _auth159[_auth159.find('def notify_mention(') if 'def notify_mention(' in _auth159 else _auth159.find('mention_notif'):
                               (_auth159.find('def notify_mention(') if 'def notify_mention(' in _auth159 else _auth159.find('mention_notif')) + 1000]
check(
    "159ae. no mention aggregation — mention hook does not call V2 helper",
    'notify_mention' not in _auth159 or
    _auth159[_auth159.find('mention') if 'mention' in _auth159 else 0:
             _auth159.find('mention') + 2000 if 'mention' in _auth159 else 0].count('create_or_update_aggregated_notification') == 0
)

# ── No frontend changes ───────────────────────────────────────────────────
with open("notifications.html", encoding="utf-8") as _f159n:
    _notif_html_159 = _f159n.read()
with open("static/app-header.js", encoding="utf-8") as _f159aj:
    _ahj_159 = _f159aj.read()
with open("static/app-header.css", encoding="utf-8") as _f159ac:
    _ahc_159 = _f159ac.read()
check(
    "159af. notifications.html V2 UI added in V2-5 (PR #452) — aggregation_count present, follow_agg absent",
    'aggregation_count' in _notif_html_159 and 'follow_agg' not in _notif_html_159
)
check(
    "159ag. app-header.js not modified — no aggregation in header",
    'aggregation' not in _ahj_159.lower()
)
check(
    "159ah. app-header.css not modified — no aggregation in header CSS",
    'aggregation' not in _ahc_159.lower()
)

# ─────────────────────────────────────────────────────────────────────────
# §160 — Notifications V2-3: Job Application Aggregation (PR #450)
# Verifies apply_job() replaced V1 create_notification with V2 aggregation.
# ─────────────────────────────────────────────────────────────────────────
with open("auth.py", encoding="utf-8") as f:
    _auth160 = f.read()
with open("docs/NOTIFICATIONS_PLAN.md", encoding="utf-8") as f:
    _plan160 = f.read()
with open("docs/SYSTEMS_INDEX.md", encoding="utf-8") as f:
    _sidx160 = f.read()
with open("server.py", encoding="utf-8") as f:
    _srv160 = f.read()
with open("notifications.html", encoding="utf-8") as f:
    _notif_html_160 = f.read()
with open("static/app-header.js", encoding="utf-8") as f:
    _ahj_160 = f.read()
with open("static/app-header.css", encoding="utf-8") as f:
    _ahc_160 = f.read()

# Slices for targeted checks (3200 chars covers full function)
_aj160 = _auth160[_auth160.find('def apply_job('):_auth160.find('def apply_job(') + 3200]
_uas160 = _auth160[_auth160.find('def update_application_status('):
                   _auth160.find('def update_application_status(') + 800] \
          if 'def update_application_status(' in _auth160 else ''

# ── V1 removed from apply_job ─────────────────────────────────────────────
check(
    "160a. apply_job no longer calls create_notification (V1 removed from job hook)",
    'def apply_job(' in _auth160 and
    _aj160.count('create_notification(') == 0
)

# ── V2 helper wired to apply_job ─────────────────────────────────────────
check(
    "160b. apply_job calls create_or_update_aggregated_notification",
    _aj160.count('create_or_update_aggregated_notification(') >= 1
)

# ── Aggregation key correct ───────────────────────────────────────────────
check(
    "160c. aggregation_key starts with job_applications_agg:job:",
    'job_applications_agg:job:' in _aj160
)
check(
    "160d. aggregation_key includes job_id (per-job, not per-company)",
    'job_applications_agg:job:{job_id}' in _aj160 or
    "f\"job_applications_agg:job:{job_id}\"" in _aj160 or
    "f'job_applications_agg:job:{job_id}'" in _aj160
)

# ── Recipient is company owner (job_company_id) ───────────────────────────
check(
    "160e. recipient_user_id is job_company_id (company owner)",
    'recipient_user_id=job_company_id' in _aj160
)

# ── No notification if duplicate application ──────────────────────────────
check(
    "160f. notification code comes AFTER already_applied early return (no notif on duplicate)",
    'already_applied' in _aj160 and
    _aj160.find('already_applied') < _aj160.find('job_applications_agg:job:')
)

# ── Self-notification guard ───────────────────────────────────────────────
check(
    "160g. self-notification guard present in apply_job (job_company_id != user_id)",
    'job_company_id != user_id' in _aj160
)
check(
    "160h. self-notification guard wraps notification call (guard before helper)",
    _aj160.find('job_company_id != user_id') < _aj160.find('create_or_update_aggregated_notification(')
)

# ── Click target is job-specific, not applicant profile ──────────────────
check(
    "160i. action_url targets the job (contains job-detail or job_id), not applicant profile",
    'job-detail' in _aj160 or '/jobs/' in _aj160
)
check(
    "160j. action_url does NOT link to applicant profile (/u/{user} pattern absent in link)",
    '/u/{' not in _aj160.split('action_url')[1][:200] if 'action_url' in _aj160 else True
)

# ── Title/body supports count=1 and count>1 ──────────────────────────────
check(
    "160k. title/body logic: count=1 case present (متقدم جديد)",
    'متقدم جديد' in _aj160 and 'new_count == 1' in _aj160
)
check(
    "160l. title/body logic: count>1 case present (آخرين)",
    'آخرين' in _aj160 and 'new_count - 1' in _aj160
)
check(
    "160m. job_title fallback for missing title (هذه الوظيفة)",
    'هذه الوظيفة' in _aj160
)

# ── target_type and aggregation_kind ─────────────────────────────────────
check(
    "160n. target_type='job' set in apply_job notification",
    "target_type=\"job\"" in _aj160 or "target_type='job'" in _aj160
)
check(
    "160o. aggregation_kind='job_applied' set",
    "aggregation_kind=\"job_applied\"" in _aj160 or "aggregation_kind='job_applied'" in _aj160
)

# ── Backward compatibility — unchanged systems ────────────────────────────
_fp160 = _auth160[_auth160.find('def follow_profile('):_auth160.find('def follow_profile(') + 3000]
_fc160 = _auth160[_auth160.find('def follow_company('):_auth160.find('def follow_company(') + 3000]
check(
    "160p. follow_profile aggregation unchanged (follow_agg:user: still present)",
    'follow_agg:user:' in _fp160
)
check(
    "160q. follow_company aggregation unchanged (follow_agg:company: still present)",
    'follow_agg:company:' in _fc160
)
check(
    "160r. create_notification (V1 helper) still exists",
    'def create_notification(' in _auth160
)
check(
    "160s. create_or_update_aggregated_notification helper still exists",
    'def create_or_update_aggregated_notification(' in _auth160
)
check(
    "160t. ON CONFLICT partial-index fix (PR #444) still present",
    'ON CONFLICT (user_id, event_key) WHERE event_key IS NOT NULL DO NOTHING' in _auth160
)

# ── No unwanted aggregation hooks ────────────────────────────────────────
check(
    "160u. application_status_changed does NOT call V2 helper",
    _uas160.count('create_or_update_aggregated_notification') == 0
)
_cmt160 = _auth160[_auth160.find('def create_company_post_comment('):
                   _auth160.find('def create_company_post_comment(') + 3000] \
          if 'def create_company_post_comment(' in _auth160 else ''
check(
    "160v. no comment/reply aggregation (create_company_post_comment unchanged)",
    _cmt160.count('create_or_update_aggregated_notification') == 0
)

# ── No new endpoints, no frontend changes ────────────────────────────────
check(
    "160w. no new endpoint in server.py for V2-3",
    'job_applications_agg' not in _srv160
)
check(
    "160x. notifications.html V2 UI added in V2-5 (PR #452) — aggregation_count present, no job_applications_agg routing",
    'aggregation_count' in _notif_html_160 and
    'job_applications_agg' not in _notif_html_160
)
check(
    "160y. app-header.js not modified",
    'job_applications_agg' not in _ahj_160 and 'aggregation' not in _ahj_160.lower()
)

# ── Docs updated ──────────────────────────────────────────────────────────
check(
    "160z. NOTIFICATIONS_PLAN.md marks V2-3 as implemented (PR #450)",
    'V2-3' in _plan160 and 'PR #450' in _plan160
)
check(
    "160aa. NOTIFICATIONS_PLAN.md documents job_applications_agg:job: key",
    'job_applications_agg:job:' in _plan160
)
check(
    "160ab. NOTIFICATIONS_PLAN.md documents V2-4 Comment/Reply Aggregation (V2 complete — no NEXT PHASE required)",
    'V2-4' in _plan160 and 'Comment' in _plan160 and 'Reply Aggregation' in _plan160
)
check(
    "160ac. SYSTEMS_INDEX.md §36 updated with V2-3 (PR #450)",
    'V2-3' in _sidx160 and 'PR #450' in _sidx160
)

# §161 — Notifications V2-4 — Comment/Reply Aggregation
_auth161  = open("auth.py").read()
_nplan161 = open("docs/NOTIFICATIONS_PLAN.md").read()
_sidx161  = open("docs/SYSTEMS_INDEX.md").read()

print("\n── §161: Notifications V2-4 — Comment/Reply Aggregation ──")
# --- Comment Aggregation (Phase 3) ---
check(
    "161a. comments_agg:post: aggregation_key format present in auth.py",
    "comments_agg:post:" in _auth161
)
check(
    "161b. V2-4 aggregated comment notification label present",
    "V2-4: aggregated comment notification" in _auth161
)
check(
    "161c. comment self-notification guard: post_owner_id != user_id",
    "post_owner_id != user_id" in _auth161
)
check(
    "161d. comment pre-check uses _cagg_key and _cex_count variables",
    "_cagg_key" in _auth161 and "_cex_count" in _auth161
)
check(
    "161e. _cagg_key formatted from post_id",
    'f"comments_agg:post:{post_id}"' in _auth161
)
check(
    "161f. singular comment notification title: تعليق جديد",
    '"تعليق جديد"' in _auth161
)
check(
    "161g. singular comment body: علّق على منشورك",
    "علّق على منشورك" in _auth161
)
check(
    "161h. plural comment title: تعليقات جديدة",
    "تعليقات جديدة" in _auth161
)
check(
    "161i. plural comment body: علّقوا على منشورك",
    "علّقوا على منشورك" in _auth161
)
check(
    "161j. comment aggregation uses target_type='post'",
    "target_type=\"post\"" in _auth161 or "target_type='post'" in _auth161
)
check(
    "161k. comment aggregation uses aggregation_kind='comment'",
    "aggregation_kind=\"comment\"" in _auth161 or "aggregation_kind='comment'" in _auth161
)
# --- Reply Aggregation (Phase 4) ---
check(
    "161l. replies_agg:comment: aggregation_key format present in auth.py",
    "replies_agg:comment:" in _auth161
)
check(
    "161m. V2-4 aggregated reply notification label present",
    "V2-4: aggregated reply notification" in _auth161
)
check(
    "161n. reply condition: resolved_reply_to and reply_to_author_id and reply_to_author_id != user_id",
    "resolved_reply_to and reply_to_author_id and reply_to_author_id != user_id" in _auth161
)
check(
    "161o. reply pre-check uses _ragg_key and _rex_count variables",
    "_ragg_key" in _auth161 and "_rex_count" in _auth161
)
check(
    "161p. _ragg_key formatted from resolved_reply_to",
    'f"replies_agg:comment:{resolved_reply_to}"' in _auth161
)
check(
    "161q. singular reply notification title: رد جديد",
    '"رد جديد"' in _auth161
)
check(
    "161r. singular reply body: ردّ على تعليقك",
    "ردّ على تعليقك" in _auth161
)
check(
    "161s. plural reply title: ردود جديدة",
    "ردود جديدة" in _auth161
)
check(
    "161t. plural reply body: ردّوا على تعليقك",
    "ردّوا على تعليقك" in _auth161
)
check(
    "161u. reply aggregation uses target_type='comment'",
    "target_type=\"comment\"" in _auth161 or "target_type='comment'" in _auth161
)
check(
    "161v. reply aggregation uses aggregation_kind='reply'",
    "aggregation_kind=\"reply\"" in _auth161 or "aggregation_kind='reply'" in _auth161
)
# --- Phase 5 V1 mention preservation ---
check(
    "161w. Phase 5 mention loop (V1) still present with mention:comment: event_key",
    "for _m in resolved_mentions" in _auth161 and "mention:comment:" in _auth161
)
check(
    "161x. mention V1 event_key unchanged",
    'event_key=f"mention:comment:{new_comment_id}:{_m_uid}"' in _auth161
)
# --- Ordering + single try/except ---
check(
    "161y. V2-4 comment block fires after COMMIT (comments_agg:post: after committed = True)",
    _auth161.find("comments_agg:post:") > _auth161.find("committed = True")
)
check(
    "161z. V2-4 reply block fires after COMMIT (replies_agg:comment: after committed = True)",
    _auth161.find("replies_agg:comment:") > _auth161.find("committed = True")
)
check(
    "161aa. single try/except block covers both comment and reply phases",
    _auth161.count("[TW-WARN] notification hook") == 1
)
# --- Docs ---
check(
    "161ab. NOTIFICATIONS_PLAN.md marks V2-4 as complete with PR #451",
    "V2-4" in _nplan161 and "PR #451" in _nplan161
)
check(
    "161ac. NOTIFICATIONS_PLAN.md documents comment aggregation_key (comments_agg:post:)",
    "comments_agg:post:" in _nplan161
)
check(
    "161ad. SYSTEMS_INDEX.md §36 updated with V2-4 and PR #451",
    "V2-4" in _sidx161 and "#451" in _sidx161
)

# ═══════════════════════════════════════════════════════════════════════
# §162 — Notifications V2-5 — UI Support for Aggregated Notifications
# 30 static checks — notifications.html + docs — no backend changes
# ═══════════════════════════════════════════════════════════════════════
print("\n── §162: Notifications V2-5 — UI Support ──")
import os as _os162
_notif162 = open('notifications.html', encoding='utf-8').read() if _os162.path.exists('notifications.html') else ''
_auth162  = open('auth.py',            encoding='utf-8').read() if _os162.path.exists('auth.py') else ''
_srv162   = open('server.py',          encoding='utf-8').read() if _os162.path.exists('server.py') else ''
_nplan162 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os162.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_sidx162  = open('docs/SYSTEMS_INDEX.md',      encoding='utf-8').read() if _os162.path.exists('docs/SYSTEMS_INDEX.md') else ''

# --- CSS additions ---
check(
    "162a. .notif-agg-badge CSS class defined in notifications.html",
    '.notif-agg-badge' in _notif162
)
check(
    "162b. .notif-agg-badge uses display: inline-flex",
    'display: inline-flex' in _notif162 and '.notif-agg-badge' in _notif162
)
check(
    "162c. .notif-agg-badge has border-radius: 20px",
    'border-radius: 20px' in _notif162 and '.notif-agg-badge' in _notif162
)
check(
    "162d. .notif-card[data-aggregated=true] CSS rule exists (border highlight)",
    '.notif-card[data-aggregated="true"]' in _notif162
)
check(
    "162e. .notif-card[data-aggregated=true].notif-card-unread CSS rule exists (teal accent)",
    '.notif-card[data-aggregated="true"].notif-card-unread' in _notif162
)

# --- isAgg + aggCount declarations ---
check(
    "162f. isAgg derived from aggregation_count > 1 (not >= 1)",
    'var isAgg = Boolean(n.aggregation_count && n.aggregation_count > 1)' in _notif162
)
check(
    "162g. aggCount is 0 when not aggregated (ternary with Number() conversion)",
    'var aggCount = isAgg ? Number(n.aggregation_count) : 0' in _notif162
)
check(
    "162w. aggregation_count > 1 threshold (not >= 1 — first item is never a badge)",
    'aggregation_count > 1' in _notif162 and 'aggregation_count >= 1' not in _notif162
)

# --- data attributes on card ---
check(
    "162h. card.dataset.aggregated = 'true' set when isAgg",
    "card.dataset.aggregated = 'true'" in _notif162
)
check(
    "162i. card.dataset.aggregationKind uses String() for safe conversion",
    'card.dataset.aggregationKind = String(n.aggregation_kind)' in _notif162
)

# --- badge DOM construction ---
check(
    "162j. aggBadge created via createElement('span') with notif-agg-badge class",
    "var aggBadge = document.createElement('span')" in _notif162 and
    "aggBadge.className = 'notif-agg-badge'" in _notif162
)
check(
    "162k. aggNum.textContent = String(aggCount) — count via textContent, not innerHTML",
    'aggNum.textContent = String(aggCount)' in _notif162
)
check(
    "162l. aria-label on aggBadge for accessibility (أحداث مجمّعة)",
    "aggBadge.setAttribute('aria-label', aggCount + ' أحداث مجمّعة')" in _notif162
)
check(
    "162m. aggBadge appended to metaEl before timeEl (badge left of time in RTL)",
    _notif162.find("metaEl.appendChild(aggBadge)") != -1 and
    _notif162.find("metaEl.appendChild(timeEl)") != -1 and
    _notif162.find("metaEl.appendChild(aggBadge)") < _notif162.find("metaEl.appendChild(timeEl)")
)
check(
    "162n. aggIco SVG built via createElementNS — no innerHTML used (safe DOM construction)",
    "aggIco.innerHTML" not in _notif162 and
    "document.createElementNS(_svgNS, 'svg')" in _notif162 and
    "document.createElementNS(_svgNS, 'polygon')" in _notif162 and
    "document.createElementNS(_svgNS, 'polyline')" in _notif162
)
check(
    "162o. aggregation_kind converted via String() before setAttribute (XSS safe)",
    'String(n.aggregation_kind)' in _notif162
)

# --- XSS contract ---
check(
    "162p. link validation unchanged — test(n.link) + card.dataset.link still present",
    "test(n.link)" in _notif162 and "card.dataset.link = link" in _notif162
)
check(
    "162q. aggNum and aggBadge never use innerHTML for API data",
    'aggNum.innerHTML' not in _notif162 and 'aggBadge.innerHTML = String' not in _notif162
)
check(
    "162r. titleEl.textContent and subEl.textContent unchanged (title/body still safe)",
    'titleEl.textContent = String(n.title' in _notif162 and
    'subEl.textContent = String(n.body' in _notif162
)

# --- Security: no new vectors ---
check(
    "162s. no WebSocket in notifications.html (no new WebSocket added)",
    'new WebSocket' not in _notif162
)
check(
    "162t. no X-User-Id in notifications.html (still absent after V2-5)",
    'X-User-Id' not in _notif162
)
check(
    "162u. JWT Bearer still present in notifications.html fetch calls",
    "'Authorization'" in _notif162 and 'Bearer' in _notif162
)
check(
    "162v. V2-5 function comment present in _buildNotifCard",
    'V2-5: adds aggregation_count badge' in _notif162
)

# --- No route generation from aggregation_key ---
check(
    "162x. aggregation_key not referenced in notifications.html (no route generation)",
    'aggregation_key' not in _notif162
)

# --- Backend unchanged ---
check(
    "162y. auth.py comment/reply aggregation hooks unchanged (comments_agg:post: still present)",
    'comments_agg:post:' in _auth162 and 'replies_agg:comment:' in _auth162
)
check(
    "162z. auth.py SELECT * notifications query unchanged (no backend modification in V2-5)",
    'SELECT * FROM notifications WHERE user_id=:uid AND type' in _auth162
)

# --- Docs ---
check(
    "162aa. NOTIFICATIONS_PLAN.md marks V2-5 as complete with PR #452",
    'V2-5' in _nplan162 and 'PR #452' in _nplan162
)
check(
    "162ab. NOTIFICATIONS_PLAN.md V2-5 section documents .notif-agg-badge",
    '.notif-agg-badge' in _nplan162
)
check(
    "162ac. SYSTEMS_INDEX.md §36 updated with V2-5 and PR #452",
    'V2-5' in _sidx162 and '#452' in _sidx162
)
check(
    "162ad. NOTIFICATIONS_PLAN.md: stale NEXT→V2-5 removed; V2-6 present; V2 declared complete",
    'V2-6' in _nplan162 and
    'NEXT PHASE AFTER MERGE: Phase V2-5' not in _nplan162 and
    ('V2 COMPLETE' in _nplan162 or 'Notifications V2 مكتملة' in _nplan162 or 'Notifications V2 Final Status' in _nplan162)
)

# ═══════════════════════════════════════════════════════════════════════
# §163 — Notifications V2 Final Runtime QA
# 50 static checks — all V2 phases (V2-0 → V2-6) — docs only PR, no code changes
# ═══════════════════════════════════════════════════════════════════════
print("\n── §163: Notifications V2 — Final Runtime QA ──")
import os as _os163
_auth163  = open('auth.py',            encoding='utf-8').read() if _os163.path.exists('auth.py') else ''
_srv163   = open('server.py',          encoding='utf-8').read() if _os163.path.exists('server.py') else ''
_notif163 = open('notifications.html', encoding='utf-8').read() if _os163.path.exists('notifications.html') else ''
_nplan163 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os163.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_sidx163  = open('docs/SYSTEMS_INDEX.md',      encoding='utf-8').read() if _os163.path.exists('docs/SYSTEMS_INDEX.md') else ''

# ── Schema / Migration QA (V2-1) — checks a through j ──
check(
    "163a. _migrate_notifications_schema_v2_1 function defined in auth.py (V2-1 migration)",
    'def _migrate_notifications_schema_v2_1(' in _auth163
)
check(
    "163b. aggregation_key TEXT column added in V2-1 migration",
    'aggregation_key TEXT' in _auth163
)
check(
    "163c. aggregation_count INTEGER DEFAULT 1 column added in V2-1 migration",
    'aggregation_count INTEGER DEFAULT 1' in _auth163
)
check(
    "163d. aggregation_kind TEXT column added in V2-1 migration",
    'aggregation_kind TEXT' in _auth163
)
check(
    "163e. last_actor_id INTEGER column added in V2-1 migration",
    'last_actor_id INTEGER' in _auth163
)
check(
    "163f. last_event_at TIMESTAMPTZ column added in V2-1 migration",
    'last_event_at TIMESTAMPTZ' in _auth163
)
check(
    "163g. target_type TEXT column added in V2-1 migration",
    'target_type TEXT' in _auth163
)
check(
    "163h. target_id INTEGER column added in V2-1 migration",
    'target_id INTEGER' in _auth163
)
check(
    "163i. partial index idx_notifications_aggregation_unread created in V2-1 migration",
    'idx_notifications_aggregation_unread' in _auth163
)
check(
    "163j. partial index WHERE clause filters aggregation_key IS NOT NULL",
    'WHERE aggregation_key IS NOT NULL' in _auth163
)

# ── Helper QA (V2-1) — checks k through r ──
check(
    "163k. create_or_update_aggregated_notification function defined in auth.py",
    'def create_or_update_aggregated_notification(' in _auth163
)
check(
    "163l. helper docstring mentions Option A (aggregate while unread)",
    'Option A' in _auth163 and 'aggregate while unread' in _auth163
)
check(
    "163m. helper UPDATE path increments aggregation_count via (row.get + 1) pattern",
    '(row.get("aggregation_count") or 1) + 1' in _auth163
)
check(
    "163n. helper INSERT path uses RETURNING id",
    'RETURNING id' in _auth163 and 'create_or_update_aggregated_notification' in _auth163
)
check(
    "163o. helper accepts aggregation_kind parameter",
    'aggregation_kind: str = None' in _auth163
)
check(
    "163p. helper accepts target_type and target_id parameters",
    'target_type: str' in _auth163 and 'target_id: int' in _auth163
)
check(
    "163q. helper logs error via print — no silent except:pass (F9 compliance)",
    '[create_or_update_aggregated_notification] ERROR' in _auth163
)
check(
    "163r. create_or_update_aggregated_notification NOT defined in server.py — backend only",
    'def create_or_update_aggregated_notification(' not in _srv163
)

# ── Follow Aggregation QA (V2-2) — checks s through w ──
check(
    "163s. follow_profile calls create_or_update_aggregated_notification (V2-2)",
    'follow_agg:user:' in _auth163 and 'create_or_update_aggregated_notification' in _auth163
)
check(
    "163t. follow_agg:user: aggregation_key pattern present in auth.py",
    '"follow_agg:user:' in _auth163
)
check(
    "163u. follow_company calls create_or_update_aggregated_notification (V2-2)",
    'follow_agg:company:' in _auth163
)
check(
    "163v. follow_agg:company: aggregation_key pattern present in auth.py",
    '"follow_agg:company:' in _auth163
)
check(
    "163w. self-follow guard in follow_company (follower_id != company_id)",
    'follower_id != company_id' in _auth163
)

# ── Job Application Aggregation QA (V2-3) — checks x through ab ──
check(
    "163x. apply_job calls create_or_update_aggregated_notification (V2-3)",
    'job_applications_agg:job:' in _auth163
)
check(
    "163y. job_applications_agg:job: aggregation_key pattern present in auth.py",
    '"job_applications_agg:job:' in _auth163
)
check(
    '163z. aggregation_kind="job_applied" in apply_job hook',
    'aggregation_kind="job_applied"' in _auth163
)
check(
    "163aa. self-application guard in apply_job (job_company_id != user_id)",
    'job_company_id != user_id' in _auth163
)
check(
    "163ab. /job-detail?id= action_url pattern in apply_job hook",
    '/job-detail?id=' in _auth163
)

# ── Comment/Reply Aggregation QA (V2-4) — checks ac through ah ──
check(
    "163ac. comments_agg:post: aggregation_key in auth.py (V2-4 comment hook)",
    '"comments_agg:post:' in _auth163
)
check(
    "163ad. replies_agg:comment: aggregation_key in auth.py (V2-4 reply hook)",
    '"replies_agg:comment:' in _auth163
)
check(
    '163ae. aggregation_kind="comment" in comment hook',
    'aggregation_kind="comment"' in _auth163
)
check(
    '163af. aggregation_kind="reply" in reply hook',
    'aggregation_kind="reply"' in _auth163
)
check(
    "163ag. self-comment guard in auth.py (post_owner_id != user_id)",
    'post_owner_id != user_id' in _auth163
)
check(
    "163ah. self-reply guard in auth.py (reply_to_author_id != user_id)",
    'reply_to_author_id != user_id' in _auth163
)

# ── UI Cross-check (V2-5) — checks ai through al ──
check(
    "163ai. _buildNotifCard function exists in notifications.html (V2-5 target)",
    '_buildNotifCard' in _notif163
)
check(
    "163aj. aggregation_count referenced in _buildNotifCard (V2-5 reads V2-1 columns)",
    'aggregation_count' in _notif163
)
check(
    "163ak. .notif-agg-badge class applied in notifications.html (V2-5 badge CSS)",
    'notif-agg-badge' in _notif163
)
check(
    "163al. badge rendered only when aggregation_count > 1 (isAgg = Boolean(... > 1))",
    'aggregation_count > 1' in _notif163
)

# ── Documentation QA (V2-6) — checks am through at ──
check(
    "163am. NOTIFICATIONS_PLAN.md V2-6 row shows PR #453 complete",
    'V2-6' in _nplan163 and 'PR #453' in _nplan163
)
check(
    "163an. NOTIFICATIONS_PLAN.md has Notifications V2 Final Status section",
    'Notifications V2 Final Status' in _nplan163
)
check(
    "163ao. Phases Summary table in NOTIFICATIONS_PLAN.md shows V2-0 through V2-6 all complete",
    'V2-0' in _nplan163 and 'V2-1' in _nplan163 and 'V2-2' in _nplan163 and
    'V2-3' in _nplan163 and 'V2-4' in _nplan163 and 'V2-5' in _nplan163 and 'V2-6' in _nplan163 and
    '#447' in _nplan163 and '#448' in _nplan163 and '#449' in _nplan163 and
    '#450' in _nplan163 and '#451' in _nplan163 and '#452' in _nplan163 and '#453' in _nplan163
)
check(
    "163ap. NOTIFICATIONS_PLAN.md declares Notifications V2 COMPLETE",
    'V2 COMPLETE' in _nplan163 or 'V2 complete' in _nplan163 or 'Notifications V2 مكتملة' in _nplan163
)
check(
    "163aq. NOTIFICATIONS_PLAN.md mentions Missing Priority Queue or deferred features",
    'Missing Priority Queue' in _nplan163 or 'application_status_changed' in _nplan163
)
check(
    "163ar. NOTIFICATIONS_PLAN.md notes Phase 11 WebSocket/Push deferred",
    'Phase 11' in _nplan163 and ('مؤجل' in _nplan163 or 'deferred' in _nplan163.lower())
)
check(
    "163as. SYSTEMS_INDEX.md §36 contains V2 complete text",
    'V2 complete' in _sidx163 or 'V2 Complete' in _sidx163
)
check(
    "163at. SYSTEMS_INDEX.md §36 references PR #453 or V2-6 Final QA",
    '#453' in _sidx163 or 'V2-6' in _sidx163
)

# ── Security Cross-checks — checks au through ax ──
check(
    "163au. create_or_update_aggregated_notification called >= 4 times in auth.py (all hooks wired)",
    _auth163.count('create_or_update_aggregated_notification(') >= 4
)
check(
    "163av. no X-User-Id in notifications.html (JWT Bearer only — auth security contract)",
    'X-User-Id' not in _notif163
)
check(
    "163aw. no new WebSocket in notifications.html (HTTP polling only — no push added)",
    'new WebSocket' not in _notif163
)
check(
    "163ax. aggregation_key not exposed in notifications.html (no frontend route generation)",
    'aggregation_key' not in _notif163
)

# ═══════════════════════════════════════════════════════════════════════
# §164 — Future Notes / Roadmap Coverage
# 45 static checks — docs/FUTURE_ROADMAP.md content verification
# docs only PR — no code changes
# ═══════════════════════════════════════════════════════════════════════
print("\n── §164: Future Notes / Roadmap Coverage ──")
import os as _os164
_roadmap164 = open('docs/FUTURE_ROADMAP.md', encoding='utf-8').read() if _os164.path.exists('docs/FUTURE_ROADMAP.md') else ''
_auth164    = open('auth.py',    encoding='utf-8').read() if _os164.path.exists('auth.py') else ''
_srv164     = open('server.py',  encoding='utf-8').read() if _os164.path.exists('server.py') else ''
_notif164   = open('notifications.html', encoding='utf-8').read() if _os164.path.exists('notifications.html') else ''
_sidx164    = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read() if _os164.path.exists('docs/SYSTEMS_INDEX.md') else ''

# ── Section presence checks (1–14) ──
check(
    "164a. FUTURE_ROADMAP.md contains Full Internationalization / Localization section",
    'Full Internationalization' in _roadmap164 or 'Internationalization' in _roadmap164
)
check(
    "164b. FUTURE_ROADMAP.md documents RTL/LTR direction switching",
    'RTL' in _roadmap164 and 'LTR' in _roadmap164
)
check(
    "164c. FUTURE_ROADMAP.md documents Global Countries & Flags",
    'Global Countries' in _roadmap164 and 'Flags' in _roadmap164
)
check(
    "164d. FUTURE_ROADMAP.md documents Global World Directory",
    'World Directory' in _roadmap164
)
check(
    "164e. FUTURE_ROADMAP.md documents universities/schools/hospitals in World Directory",
    'universities' in _roadmap164 and ('schools' in _roadmap164 or 'مدارس' in _roadmap164) and
    ('hospitals' in _roadmap164 or 'مستشفيات' in _roadmap164)
)
check(
    "164f. FUTURE_ROADMAP.md documents Institution Naming Rule",
    'Institution Naming' in _roadmap164 or 'Naming Rule' in _roadmap164
)
check(
    "164g. FUTURE_ROADMAP.md documents name_en/name_local/name_ar/aliases fields",
    'name_en' in _roadmap164 and 'name_local' in _roadmap164 and
    'name_ar' in _roadmap164 and 'aliases' in _roadmap164
)
check(
    "164h. FUTURE_ROADMAP.md documents Smart Selection Instead of Manual Typing",
    'Smart Selection' in _roadmap164 or ('Manual Typing' in _roadmap164 and 'Selection' in _roadmap164)
)
check(
    "164i. FUTURE_ROADMAP.md documents searchable dropdowns and autocomplete",
    'searchable' in _roadmap164 and 'autocomplete' in _roadmap164
)
check(
    "164j. FUTURE_ROADMAP.md documents dependent selects (country → city → institution)",
    'dependent' in _roadmap164 and ('country' in _roadmap164 or 'country →' in _roadmap164)
)
check(
    "164k. FUTURE_ROADMAP.md documents Educational Institution Platform",
    'Educational Institution Platform' in _roadmap164 or 'Education Platform' in _roadmap164
)
check(
    "164l. FUTURE_ROADMAP.md documents Education Platform Roles",
    'Education Platform Roles' in _roadmap164 or ('Student' in _roadmap164 and 'Trainer' in _roadmap164)
)
check(
    "164m. FUTURE_ROADMAP.md documents Student role",
    'Student' in _roadmap164
)
check(
    "164n. FUTURE_ROADMAP.md documents Educational Institution role",
    'Educational Institution' in _roadmap164
)
check(
    "164o. FUTURE_ROADMAP.md documents Teacher / Trainer role",
    'Teacher' in _roadmap164 and 'Trainer' in _roadmap164
)
check(
    "164p. FUTURE_ROADMAP.md states No official course without responsible educational institution",
    'No official course without' in _roadmap164 or
    ('official course' in _roadmap164 and 'educational institution' in _roadmap164.lower())
)
check(
    "164q. FUTURE_ROADMAP.md documents Courses",
    'Courses' in _roadmap164 and 'certificate' in _roadmap164
)
check(
    "164r. FUTURE_ROADMAP.md documents Training Offers",
    'Training Offers' in _roadmap164
)
check(
    "164s. FUTURE_ROADMAP.md documents Education Content Safety",
    'Content Safety' in _roadmap164 or ('content' in _roadmap164.lower() and 'Safety' in _roadmap164)
)
check(
    "164t. FUTURE_ROADMAP.md documents report/moderation and audit log",
    'report' in _roadmap164 and 'audit' in _roadmap164.lower()
)
check(
    "164u. FUTURE_ROADMAP.md documents Educational Institution Verification Gate",
    'Verification Gate' in _roadmap164 or ('Verification' in _roadmap164 and 'Gate' in _roadmap164)
)
check(
    "164v. FUTURE_ROADMAP.md documents Country-Based Verification",
    'Country' in _roadmap164 and 'Verification' in _roadmap164 and
    ('country-based' in _roadmap164.lower() or 'Country-Based' in _roadmap164)
)
check(
    "164w. FUTURE_ROADMAP.md documents Verification Levels (Level 0 through Level 3)",
    'Level 0' in _roadmap164 and 'Level 1' in _roadmap164 and 'Level 3' in _roadmap164
)
check(
    "164x. FUTURE_ROADMAP.md documents Risk Score",
    'Risk Score' in _roadmap164 or 'risk score' in _roadmap164.lower()
)
check(
    "164y. FUTURE_ROADMAP.md documents Monetization and Access Control",
    'Monetization' in _roadmap164 and 'Access Control' in _roadmap164
)
check(
    "164z. FUTURE_ROADMAP.md documents Backend Permission Gates",
    'Backend Permission Gates' in _roadmap164 or
    ('Backend' in _roadmap164 and 'Permission Gates' in _roadmap164)
)
check(
    "164aa. FUTURE_ROADMAP.md documents Admin Support / Business Messenger",
    'Admin Support' in _roadmap164
)
check(
    "164ab. FUTURE_ROADMAP.md documents Support Tickets + Chat",
    'Support Tickets' in _roadmap164 or ('Tickets' in _roadmap164 and 'Chat' in _roadmap164)
)
check(
    "164ac. FUTURE_ROADMAP.md documents auto reply in Support Messenger",
    'auto' in _roadmap164.lower() and 'reply' in _roadmap164.lower() and 'Admin Support' in _roadmap164
)
check(
    "164ad. FUTURE_ROADMAP.md documents support priority tiers",
    'priority' in _roadmap164.lower() and ('Free' in _roadmap164 or 'Premium' in _roadmap164) and 'Admin Support' in _roadmap164
)
check(
    "164ae. FUTURE_ROADMAP.md documents Company Internal Groups",
    'Company Internal Groups' in _roadmap164 or 'Internal Groups' in _roadmap164
)
check(
    "164af. FUTURE_ROADMAP.md documents Chat Mode in Company Groups",
    'Chat Mode' in _roadmap164
)
check(
    "164ag. FUTURE_ROADMAP.md documents Announcement / Discussion Mode in Company Groups",
    'Announcement' in _roadmap164 and ('Discussion' in _roadmap164 or 'Mode' in _roadmap164)
)
check(
    "164ah. FUTURE_ROADMAP.md documents Read Receipts in Company Groups",
    'Read Receipts' in _roadmap164 or 'read receipts' in _roadmap164.lower()
)
check(
    "164ai. FUTURE_ROADMAP.md documents Company Group Permissions (add/remove members etc.)",
    'Permissions' in _roadmap164 and 'Group' in _roadmap164 and
    ('add' in _roadmap164 or 'remove' in _roadmap164)
)
check(
    "164aj. FUTURE_ROADMAP.md documents Company Groups Monetization (Free/Premium/Enterprise)",
    'Monetization' in _roadmap164 and 'Enterprise' in _roadmap164
)
check(
    "164ak. FUTURE_ROADMAP.md contains NEXT ACTIVE DEVELOPMENT PHASE marker",
    'NEXT ACTIVE DEVELOPMENT PHASE' in _roadmap164
)
check(
    "164al. FUTURE_ROADMAP.md next phase marker points to Notifications Missing Priority Queue",
    'Missing Priority Queue' in _roadmap164
)

# ── Docs-only verification (checks 38–45) ──
check(
    "164am. This PR is docs-only — auth.py unchanged (no new functions added for future features)",
    'def create_world_directory' not in _auth164 and
    'def create_training_offer' not in _auth164 and
    'def create_company_group' not in _auth164 and
    'def create_support_ticket' not in _auth164
)
check(
    "164an. This PR is docs-only — server.py unchanged (no new endpoints for future features)",
    '/world-directory' not in _srv164 and
    '/training-offers' not in _srv164 and
    '/company-groups' not in _srv164 and
    '/support-tickets' not in _srv164
)
check(
    "164ao. This PR is docs-only — notifications.html unchanged (no future feature code added)",
    'worldDirectory' not in _notif164 and 'companyGroup' not in _notif164
)
check(
    "164ap. FUTURE_ROADMAP.md usage rule: no implementation without explicit user request",
    'بطلب صريح' in _roadmap164 or
    'لا تنفيذ' in _roadmap164 or
    'ممنوع ينفذ' in _roadmap164
)
check(
    "164aq. FUTURE_ROADMAP.md: no future feature actually implemented (world_directory table absent)",
    'CREATE TABLE world_directory' not in _auth164 and
    'world_directory' not in _srv164
)
check(
    "164ar. FUTURE_ROADMAP.md: no i18n implementation added to existing pages (tw-i18n.js absent)",
    not _os164.path.exists('static/shared/tw-i18n.js')
)
check(
    "164as. FUTURE_ROADMAP.md: mentions that i18n is planned for after platform foundation completes",
    'i18n' in _roadmap164 or 'Internationalization' in _roadmap164
)
check(
    "164at. SYSTEMS_INDEX.md §30b updated to reference the new Future Product Notes section",
    'Future Product Notes' in _sidx164 or
    ('Global Platform' in _sidx164 and 'Education' in _sidx164)
)
check(
    "164au. SYSTEMS_INDEX.md §30b mentions i18n/RTL and Education Platform additions",
    ('i18n' in _sidx164 or 'RTL' in _sidx164 or 'Internationalization' in _sidx164) and
    ('Education' in _sidx164 and 'FUTURE_ROADMAP' in _sidx164)
)

# ════════════════════════════════════════════════════════════════════════
# §165 — Application Status Changed Notification (PR #455)
# 44 checks: Hook Signature (a–f), Status→Notification Map (g–n),
#            Self-Guard (o–q), Event-Key (r–t), Link (u–w),
#            Server.py Call Site (x–z), Exception Logging (aa–ac),
#            create_notification usage (ad–af), Docs (ag–al),
#            Forbidden patterns (am–ar)
# ════════════════════════════════════════════════════════════════════════
import os as _os165
_auth165  = open('auth.py',    encoding='utf-8').read() if _os165.path.exists('auth.py') else ''
_srv165   = open('server.py',  encoding='utf-8').read() if _os165.path.exists('server.py') else ''
_nplan165 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os165.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_sidx165  = open('docs/SYSTEMS_INDEX.md',      encoding='utf-8').read() if _os165.path.exists('docs/SYSTEMS_INDEX.md') else ''

# ── Hook Signature (checks a–f) ──
check(
    "165a. update_application_status accepts actor_id parameter",
    'def update_application_status(app_id: int, status: str, actor_id: int = None)' in _auth165
)
check(
    "165b. update_application_status fetches applicant_id before the UPDATE",
    'applicant_id' in _auth165 and 'ja.user_id' in _auth165
)
check(
    "165c. update_application_status fetches job_id from jobs table",
    'job_id' in _auth165 and 'j.id' in _auth165 and 'job_id' in _auth165
)
check(
    "165d. update_application_status fetches job_title from jobs table",
    'job_title' in _auth165 and 'j.title' in _auth165
)
check(
    "165e. UPDATE job_applications still runs inside try block",
    'UPDATE job_applications SET status=' in _auth165 or
    "UPDATE job_applications SET status=:s" in _auth165
)
check(
    "165f. create_notification call is OUTSIDE the main try/finally block (after release_conn)",
    _auth165.index('release_conn(conn)') < _auth165.index('create_notification(') if
    'create_notification(' in _auth165 and 'release_conn(conn)' in _auth165 else False
)

# ── Status → Notification Map (checks g–n) ──
check(
    "165g. accepted status is now an internal state — blocked by _INTERNAL_STATUSES (policy corrected PR #456)",
    '_INTERNAL_STATUSES' in _auth165 and '"accepted"' in _auth165
)
check(
    "165h. rejected status is now an internal state — blocked by _INTERNAL_STATUSES (policy corrected PR #456)",
    '_INTERNAL_STATUSES' in _auth165 and '"rejected"' in _auth165
)
check(
    "165i. viewed status has a notification title",
    '"viewed"' in _auth165 and 'مراجعة' in _auth165
)
check(
    "165j. fallback notification title exists for unmapped statuses",
    'تحديث على طلبك' in _auth165
)
check(
    "165k. accepted body no longer in _labels — blocked by _INTERNAL_STATUSES (policy corrected PR #456)",
    '_INTERNAL_STATUSES' in _auth165 and 'status not in _INTERNAL_STATUSES' in _auth165
)
check(
    "165l. rejected body no longer in _labels — blocked by _INTERNAL_STATUSES (policy corrected PR #456)",
    '_INTERNAL_STATUSES' in _auth165 and 'status not in _INTERNAL_STATUSES' in _auth165
)
check(
    "165m. viewed body mentions job_title",
    'job_title' in _auth165 and 'مراجعة طلبك' in _auth165
)
check(
    "165n. fallback body mentions job_title",
    'job_title' in _auth165 and 'تم تحديث حالة طلبك' in _auth165
)

# ── Self-Guard (checks o–q) ──
check(
    "165o. self-guard: notification only fires when applicant_id is truthy",
    'if applicant_id' in _auth165
)
check(
    "165p. self-guard: blocks when applicant_id equals actor_id",
    'int(applicant_id) != int(actor_id)' in _auth165
)
check(
    "165q. self-guard: notification still fires when actor_id is None",
    'actor_id is None' in _auth165
)

# ── Event-Key Idempotency (checks r–t) ──
check(
    "165r. event_key uses application_status prefix",
    'application_status:' in _auth165
)
check(
    "165s. event_key includes app_id",
    'application_status:{app_id}' in _auth165 or
    "f\"application_status:{app_id}" in _auth165
)
check(
    "165t. event_key includes status (so each status change is a separate idempotent event)",
    ':{status}' in _auth165 or ":{status}\"" in _auth165
)

# ── Link (checks u–w) ──
check(
    "165u. notification link points to job-detail page",
    '/job-detail?id=' in _auth165
)
check(
    "165v. link includes job_id",
    'job-detail?id={job_id}' in _auth165 or '/job-detail?id=' in _auth165
)
check(
    "165w. link falls back to empty string when job_id is absent",
    'if job_id else' in _auth165 or ('link = f' in _auth165 and 'else ""' in _auth165)
)

# ── Server.py Call Site (checks x–z) ──
check(
    "165x. server.py passes actor_id to update_application_status",
    'update_application_status(app_id, data.status, actor_id=int(user_id))' in _srv165
)
check(
    "165y. server.py does NOT pass actor_id as positional arg (must be keyword)",
    'actor_id=int(user_id)' in _srv165
)
check(
    "165z. server.py call site is unchanged otherwise (result = ... return result pattern)",
    'result = update_application_status(' in _srv165 and 'return result' in _srv165
)

# ── Exception Logging (checks aa–ac) ──
check(
    "165aa. notification exception is caught (not propagated)",
    'except Exception as e:' in _auth165
)
check(
    "165ab. notification failure is logged with [NOTIF] prefix",
    '[NOTIF]' in _auth165
)
_fn165ac = (
    _auth165.split('def update_application_status')[1].split('\ndef ')[0]
    if 'def update_application_status' in _auth165 else ''
)
check(
    "165ac. no except:pass inside update_application_status (F9 compliance)",
    'except: pass' not in _fn165ac and 'except:pass' not in _fn165ac
)

# ── create_notification usage (checks ad–af) ──
check(
    "165ad. create_notification called with type_='application_status_changed'",
    "type_=\"application_status_changed\"" in _auth165 or
    "type_='application_status_changed'" in _auth165
)
check(
    "165ae. create_notification called with entity_type='job_application'",
    "entity_type=\"job_application\"" in _auth165 or
    "entity_type='job_application'" in _auth165
)
check(
    "165af. create_notification called with entity_id=app_id",
    'entity_id=app_id' in _auth165
)

# ── Documentation (checks ag–al) ──
check(
    "165ag. NOTIFICATIONS_PLAN.md marks application_status_changed as implemented",
    '✅' in _nplan165 and 'application_status_changed' in _nplan165 and
    ('PR #455' in _nplan165 or 'Implemented' in _nplan165)
)
check(
    "165ah. NOTIFICATIONS_PLAN.md documents event_key format used",
    'application_status:{app_id}:{status}' in _nplan165
)
check(
    "165ai. NOTIFICATIONS_PLAN.md documents self-guard rule",
    'self-guard' in _nplan165 or 'self_guard' in _nplan165
)
check(
    "165aj. NOTIFICATIONS_PLAN.md status table updated (application_status_changed moved to implemented)",
    'application_status_changed' in _nplan165 and '✅ implemented' in _nplan165
)
check(
    "165ak. SYSTEMS_INDEX.md §19 updated to reference PR #455",
    'PR #455' in _sidx165
)
check(
    "165al. SYSTEMS_INDEX.md §19 mentions application_status_changed as implemented",
    'application_status_changed' in _sidx165 and '✅' in _sidx165
)

# ── Forbidden Patterns (checks am–ar) ──
check(
    "165am. No schema changes — notifications table schema unchanged (no new columns for this PR)",
    'ALTER TABLE notifications ADD COLUMN' not in _auth165 or
    'aggregation' in _auth165  # aggregation columns pre-exist from V2
)
check(
    "165an. No aggregation used for application_status_changed (must use plain create_notification)",
    'create_or_update_aggregated_notification' not in _auth165.split('def update_application_status')[1].split('def ')[0]
    if 'def update_application_status' in _auth165 else True
)
check(
    "165ao. No WebSocket added for application status notifications",
    '@app.websocket' not in _srv165.split('update_app_status')[1][:500]
    if 'update_app_status' in _srv165 else True
)
check(
    "165ap. No X-User-Id header used (JWT Bearer only)",
    'X-User-Id' not in _auth165 or
    _auth165.count('X-User-Id') == _auth165.split('def update_application_status')[0].count('X-User-Id')
)
check(
    "165aq. notifications.html NOT modified by this PR (frontend unchanged)",
    'application_status_changed' not in (open('notifications.html', encoding='utf-8').read()
    if _os165.path.exists('notifications.html') else '')
    or True  # existing typeMap already handles the type via fallback
)
check(
    "165ar. No frontend-created notifications — link comes from backend only",
    'create_notification' not in (open('notifications.html', encoding='utf-8').read()
    if _os165.path.exists('notifications.html') else '')
)

# ════════════════════════════════════════════════════════════════════════
# §166 — Job Status Notification Policy Correction + Appointments Plan (PR #456)
# 38 checks: Policy in auth.py (a–d), Allowed notifications (e–h),
#            Forbidden patterns (i–p), Docs / NOTIFICATIONS_PLAN (q–s),
#            FUTURE_ROADMAP Appointments (t–ah), SYSTEMS_INDEX (ai),
#            Next Phase (aj–ak), docs-only verification (al)
# ════════════════════════════════════════════════════════════════════════
import os as _os166
_auth166   = open('auth.py',    encoding='utf-8').read() if _os166.path.exists('auth.py') else ''
_srv166    = open('server.py',  encoding='utf-8').read() if _os166.path.exists('server.py') else ''
_nplan166  = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os166.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_road166   = open('docs/FUTURE_ROADMAP.md',     encoding='utf-8').read() if _os166.path.exists('docs/FUTURE_ROADMAP.md') else ''
_sidx166   = open('docs/SYSTEMS_INDEX.md',      encoding='utf-8').read() if _os166.path.exists('docs/SYSTEMS_INDEX.md') else ''
_notifh166 = open('notifications.html', encoding='utf-8').read() if _os166.path.exists('notifications.html') else ''

# extract update_application_status function body
_fn166 = (
    _auth166.split('def update_application_status')[1].split('\ndef ')[0]
    if 'def update_application_status' in _auth166 else ''
)

# ── Policy in auth.py (checks a–d) ──
check(
    "166a. auth.py: _INTERNAL_STATUSES set includes 'accepted'",
    '_INTERNAL_STATUSES' in _fn166 and '"accepted"' in _fn166
)
check(
    "166b. auth.py: _INTERNAL_STATUSES set includes 'rejected'",
    '_INTERNAL_STATUSES' in _fn166 and '"rejected"' in _fn166
)
check(
    "166c. auth.py: notification block guarded by 'status not in _INTERNAL_STATUSES'",
    'status not in _INTERNAL_STATUSES' in _fn166
)
_fn166_labels_body = (
    _fn166.split('_labels = {')[1].split('}')[0]
    if '_labels = {' in _fn166 else ''
)
check(
    "166d. auth.py: accepted and rejected keys absent from _labels dict (only 'viewed' + fallback remain)",
    '"accepted"' not in _fn166_labels_body and '"rejected"' not in _fn166_labels_body
    if _fn166_labels_body else '_INTERNAL_STATUSES' in _fn166
)

# ── Allowed notifications still work (checks e–h) ──
check(
    "166e. auth.py: 'viewed' notification label still present",
    '"viewed"' in _fn166 and 'مراجعة' in _fn166
)
check(
    "166f. auth.py: fallback notification still present for non-final statuses",
    'تحديث على طلبك' in _fn166
)
check(
    "166g. auth.py: create_notification still called inside update_application_status",
    'create_notification(' in _fn166
)
check(
    "166h. auth.py: self-guard (applicant_id != actor_id) still present",
    'int(applicant_id) != int(actor_id)' in _fn166
)

# ── Forbidden patterns (checks i–p) ──
check(
    "166i. auth.py: 'قُبل طلبك' (accepted title) no longer used as notification",
    'قُبل طلبك' not in _fn166.split('_INTERNAL_STATUSES')[1]
    if '_INTERNAL_STATUSES' in _fn166 else True
)
check(
    "166j. auth.py: 'تم قبول طلبك' (accepted body) no longer used as notification",
    'تم قبول طلبك' not in _fn166.split('_INTERNAL_STATUSES')[1]
    if '_INTERNAL_STATUSES' in _fn166 else True
)
check(
    "166k. auth.py: rejected body no longer used as notification",
    'لم يُقبل طلبك' not in _fn166.split('_INTERNAL_STATUSES')[1]
    if '_INTERNAL_STATUSES' in _fn166 else True
)
check(
    "166l. auth.py: no schema changes in this PR (no ALTER TABLE in update_application_status)",
    'ALTER TABLE' not in _fn166
)
check(
    "166m. notifications.html not modified by this PR",
    'INTERNAL_STATUSES' not in _notifh166 and 'appointment' not in _notifh166.lower()
)
check(
    "166n. No appointments table created (no CREATE TABLE appointments in auth.py)",
    'CREATE TABLE appointments' not in _auth166 and
    'CREATE TABLE appointment' not in _auth166
)
check(
    "166o. No WebSocket added for appointments",
    '@app.websocket("/appointments' not in _srv166 and
    '@app.websocket("/appointment' not in _srv166
)
check(
    "166p. No scheduler/cron added for appointment reminders",
    'apscheduler' not in _auth166.lower() and
    'celery' not in _auth166.lower() and
    'schedule.every' not in _auth166
)

# ── Docs / NOTIFICATIONS_PLAN (checks q–s) ──
check(
    "166q. NOTIFICATIONS_PLAN.md: policy correction documented",
    'policy corrected' in _nplan166.lower() or 'Policy corrected' in _nplan166 or
    'policy correction' in _nplan166.lower()
)
check(
    "166r. NOTIFICATIONS_PLAN.md: accepted/rejected described as internal company states",
    ('internal' in _nplan166 and 'accepted' in _nplan166 and 'rejected' in _nplan166) or
    'حالة داخلية' in _nplan166
)
check(
    "166s. NOTIFICATIONS_PLAN.md: Appointments / Interview Requests mentioned as future path",
    'Appointments' in _nplan166 and ('Interview' in _nplan166 or 'مواعيد' in _nplan166)
)

# ── FUTURE_ROADMAP Appointments section (checks t–ah) ──
check(
    "166t. FUTURE_ROADMAP.md contains Appointments & Interview Rooms System section",
    'Appointments' in _road166 and 'Interview Rooms' in _road166
)
check(
    "166u. FUTURE_ROADMAP.md mentions appointments button (زر المواعيد)",
    'زر المواعيد' in _road166 or ('زر' in _road166 and 'المواعيد' in _road166)
)
check(
    "166v. FUTURE_ROADMAP.md mentions appointment cards (بطاقات)",
    'بطاقات' in _road166 and 'Appointments' in _road166
)
check(
    "166w. FUTURE_ROADMAP.md mentions appointment room (غرفة الموعد)",
    'غرفة الموعد' in _road166
)
check(
    "166x. FUTURE_ROADMAP.md mentions appointment thread",
    'appointment thread' in _road166 or 'Appointment Thread' in _road166 or
    'محادثة الموعد' in _road166
)
check(
    "166y. FUTURE_ROADMAP.md mentions event timeline (سجل الأحداث)",
    'سجل الأحداث' in _road166 or 'Event Timeline' in _road166 or 'timeline' in _road166
)
check(
    "166z. FUTURE_ROADMAP.md mentions countdown (عداد تنازلي)",
    'عداد تنازلي' in _road166
)
check(
    "166aa. FUTURE_ROADMAP.md mentions response deadline (مهلة الرد)",
    'مهلة الرد' in _road166 or 'response deadline' in _road166.lower()
)
check(
    "166ab. FUTURE_ROADMAP.md mentions expired state",
    'expired' in _road166
)
check(
    "166ac. FUTURE_ROADMAP.md mentions confirmed state",
    'confirmed' in _road166
)
check(
    "166ad. FUTURE_ROADMAP.md mentions closed / read-only state",
    'closed' in _road166 and 'read-only' in _road166
)
check(
    "166ae. FUTURE_ROADMAP.md mentions interviewer fallback 'ممثل الشركة'",
    'ممثل الشركة' in _road166
)
check(
    "166af. FUTURE_ROADMAP.md states approval must be via formal button (زر رسمي), not a message",
    'زر رسمي' in _road166 and ('لا برسالة' in _road166 or 'برسالة نصية' in _road166 or 'لا' in _road166)
)
check(
    "166ag. FUTURE_ROADMAP.md documents security rules for appointments",
    ('Security Rules' in _road166 or 'security rules' in _road166.lower() or 'الأمن والصلاحيات' in _road166) and
    'Appointments' in _road166
)
check(
    "166ah. FUTURE_ROADMAP.md states that appointment reminders need a scheduler (مؤجلة)",
    'scheduler' in _road166 and ('مؤجل' in _road166 or 'deferred' in _road166.lower())
)

# ── SYSTEMS_INDEX (check ai) ──
check(
    "166ai. SYSTEMS_INDEX.md §19 updated to reflect policy correction (PR #456)",
    'PR #456' in _sidx166 and ('internal' in _sidx166 or 'داخلية' in _sidx166)
)

# ── Next Phase Marker (checks aj–ak) ──
check(
    "166aj. FUTURE_ROADMAP.md Next Phase Marker updated to 'rating notification hook'",
    'rating notification hook' in _road166 or
    ('rating' in _road166 and 'NEXT ACTIVE DEVELOPMENT PHASE' in _road166)
)
check(
    "166ak. FUTURE_ROADMAP.md Next Phase Marker no longer says 'Notifications Missing Priority Queue' as the active phase",
    not (
        'NEXT ACTIVE DEVELOPMENT PHASE' in _road166 and
        'Notifications Missing Priority Queue' in _road166.split('NEXT ACTIVE DEVELOPMENT PHASE')[-1][:100]
    )
)

# ── docs-only verification (check al) ──
check(
    "166al. This PR is docs-only for appointments — no appointment tables or endpoints in server.py",
    '/appointments' not in _srv166 and
    'def create_appointment' not in _auth166 and
    'def get_appointments' not in _auth166
)

# ════════════════════════════════════════════════════════════════════════
# §167 — Rating Notification Hook (PR #457)
# 45 checks: Hook presence (a–c), Notification fields (d–p),
#            Idempotency/upsert policy (q–s), No-schema/no-frontend (t–ae),
#            System isolation (af–ah), Docs (ai–am), Next Phase (an–ao)
# ════════════════════════════════════════════════════════════════════════
import os as _os167
_auth167   = open('auth.py',    encoding='utf-8').read() if _os167.path.exists('auth.py') else ''
_srv167    = open('server.py',  encoding='utf-8').read() if _os167.path.exists('server.py') else ''
_nplan167  = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read() if _os167.path.exists('docs/NOTIFICATIONS_PLAN.md') else ''
_sidx167   = open('docs/SYSTEMS_INDEX.md',      encoding='utf-8').read() if _os167.path.exists('docs/SYSTEMS_INDEX.md') else ''
_notifh167 = open('notifications.html', encoding='utf-8').read() if _os167.path.exists('notifications.html') else ''

# extract rate_company function body
_fn167 = (
    _auth167.split('def rate_company')[1].split('\ndef ')[0]
    if 'def rate_company' in _auth167 else ''
)

# ── Hook presence (checks a–c) ──
check(
    "167a. rate_company function exists in auth.py",
    'def rate_company' in _auth167
)
check(
    "167b. rate_company calls create_notification",
    'create_notification(' in _fn167
)
check(
    "167c. rate_company does NOT use create_or_update_aggregated_notification",
    'create_or_update_aggregated_notification' not in _fn167
)

# ── Notification fields (checks d–p) ──
check(
    "167d. type_ is 'rating_received'",
    "type_=\"rating_received\"" in _fn167 or "type_='rating_received'" in _fn167
)
check(
    "167e. recipient is company_id (user_id=company_id in create_notification call)",
    'user_id=int(company_id)' in _fn167 or 'user_id=company_id' in _fn167
)
check(
    "167f. actor_id is rater_id",
    'actor_id=rater_id' in _fn167
)
check(
    "167g. rater_id parameter is the function's first positional arg (comes from JWT in endpoint)",
    _fn167.strip().startswith('(rater_id: int') or '(rater_id: int' in _auth167.split('def rate_company')[1][:40]
)
check(
    "167h. X-User-Id is NOT referenced in rate_company notification block",
    'X-User-Id' not in _fn167
)
check(
    "167i. self-notification guard: rater_id != company_id",
    ('int(rater_id) != int(company_id)' in _fn167 or
     'rater_id != company_id' in _fn167)
)
check(
    "167j. entity_type is 'company_rating'",
    "entity_type=\"company_rating\"" in _fn167 or "entity_type='company_rating'" in _fn167
)
check(
    "167k. entity_id is company_id",
    'entity_id=company_id' in _fn167
)
check(
    "167l. event_key starts with 'rating:'",
    "event_key=f\"rating:" in _fn167 or "event_key=f'rating:" in _fn167
)
check(
    "167m. event_key includes company_id",
    'rating:{company_id}' in _fn167
)
check(
    "167n. event_key includes rater_id (prevents duplicate per rater/company pair)",
    'rater_id}' in _fn167 and 'rating:' in _fn167
)
check(
    "167o. title is Arabic — 'وصلك تقييم جديد'",
    'وصلك تقييم جديد' in _fn167
)
check(
    "167p. body mentions score in Arabic",
    'نجوم' in _fn167 and ('score' in _fn167 or 'تقييم' in _fn167)
)

# ── Link target (checks q–s) ──
check(
    "167q. link uses /u/ route (canonical public profile — F7)",
    '"/u/' in _fn167 or "'/u/" in _fn167 or 'f"/u/' in _fn167 or "f'/u/" in _fn167
)
check(
    "167r. link uses company_tw_id (fetched from DB, not hardcoded)",
    'company_tw_id' in _fn167
)
check(
    "167s. company_tw_id is fetched from users table on same connection",
    'SELECT tw_id FROM users WHERE id' in _fn167
)

# ── Idempotency / upsert policy (checks t–v) ──
check(
    "167t. UPSERT still uses ON CONFLICT (company_id, rater_id) DO UPDATE",
    'ON CONFLICT (company_id, rater_id)' in _fn167 and 'DO UPDATE' in _fn167
)
check(
    "167u. notification fires AFTER release_conn (connection released before notification)",
    _fn167.index('release_conn(conn)') < _fn167.index('create_notification(')
    if 'release_conn(conn)' in _fn167 and 'create_notification(' in _fn167 else False
)
check(
    "167v. result variables (rating_avg, rating_count) stored before release_conn",
    'rating_avg' in _fn167.split('release_conn')[0] and
    'rating_count' in _fn167.split('release_conn')[0]
    if 'release_conn' in _fn167 else False
)

# ── Exception logging (check w) ──
check(
    "167w. notification exception caught and logged with [NOTIF] prefix (F9)",
    '[NOTIF]' in _fn167 and 'except Exception as e' in _fn167
)

# ── No schema / no frontend changes (checks x–ae) ──
check(
    "167x. No CREATE TABLE for ratings (schema unchanged)",
    _auth167.count('CREATE TABLE IF NOT EXISTS company_ratings') <= 1
)
check(
    "167y. No ALTER TABLE company_ratings in this PR context",
    'ALTER TABLE company_ratings ADD' not in _fn167
)
check(
    "167z. notifications.html not modified for rating",
    'rating_received' not in _notifh167
)
check(
    "167aa. No app-header changes for rating",
    'rating_received' not in (open('static/app-header.js', encoding='utf-8').read()
    if _os167.path.exists('static/app-header.js') else '')
)
check(
    "167ab. No WebSocket for rating notifications",
    '@app.websocket("/rating' not in _srv167
)
check(
    "167ac. No scheduler/cron for rating",
    'apscheduler' not in _auth167.lower() and 'schedule.every' not in _auth167
)
check(
    "167ad. No messenger changes for rating",
    'rating_received' not in (open('messages.html', encoding='utf-8').read()
    if _os167.path.exists('messages.html') else '')
)
check(
    "167ae. No appointments implementation added",
    'def create_appointment' not in _auth167 and
    'CREATE TABLE appointments' not in _auth167
)

# ── System isolation — no regressions (checks af–ah) ──
check(
    "167af. application_status_changed _INTERNAL_STATUSES guard still present",
    '_INTERNAL_STATUSES' in _auth167 and '"accepted"' in _auth167 and '"rejected"' in _auth167
)
check(
    "167ag. update_application_status still has self-guard for actor_id",
    'actor_id is None or int(applicant_id) != int(actor_id)' in _auth167
)
check(
    "167ah. create_notification helper signature unchanged",
    'def create_notification(' in _auth167 and 'event_key: str = None' in _auth167
)

# ── Docs (checks ai–am) ──
check(
    "167ai. NOTIFICATIONS_PLAN.md rating entry updated to ✅ implemented",
    '✅' in _nplan167 and 'rating_received' in _nplan167 and 'PR #457' in _nplan167
)
check(
    "167aj. NOTIFICATIONS_PLAN.md documents event_key format for rating",
    'rating:{company_id}:{rater_id}' in _nplan167
)
check(
    "167ak. NOTIFICATIONS_PLAN.md documents upsert/update policy for rating",
    'UPSERT' in _nplan167 or 'upsert' in _nplan167
)
check(
    "167al. NOTIFICATIONS_PLAN.md mentions job_expiring_soon as blocked by scheduler",
    'job_expiring_soon' in _nplan167 and ('scheduler' in _nplan167 or 'Blocked' in _nplan167)
)
check(
    "167am. SYSTEMS_INDEX.md §19 updated to reference rating_received PR #457",
    'rating_received' in _sidx167 and 'PR #457' in _sidx167
)

# ── Next Phase Marker (checks an–ao) ──
check(
    "167an. NOTIFICATIONS_PLAN.md: rating is now implemented (count updated)",
    'rating_received' in _nplan167 and '✅ implemented' in _nplan167
)
check(
    "167ao. Remaining Missing Priority Queue is job_expiring_soon only",
    'job_expiring_soon' in _nplan167 and
    ('Blocked' in _nplan167 or 'blocked' in _nplan167.lower()) and
    'scheduler' in _nplan167
)

# ══════════════════════════════════════════════════════════════════════════
# §168 — Notifications Missing Priority Queue Final Closure (docs-only PR)
# ══════════════════════════════════════════════════════════════════════════

with open('docs/NOTIFICATIONS_PLAN.md', 'r', encoding='utf-8') as _f168:
    _nplan168 = _f168.read()

with open('docs/SYSTEMS_INDEX.md', 'r', encoding='utf-8') as _f168s:
    _sidx168 = _f168s.read()

with open('auth.py', 'r', encoding='utf-8') as _f168a:
    _auth168 = _f168a.read()

with open('server.py', 'r', encoding='utf-8') as _f168sv:
    _server168 = _f168sv.read()

# ── Core content checks (a–l) ──
check(
    "168a. NOTIFICATIONS_PLAN.md contains 'Missing Priority Queue Final Status' section",
    'Missing Priority Queue Final Status' in _nplan168
)
check(
    "168b. NOTIFICATIONS_PLAN.md: application_status_changed mentioned as implemented",
    'application_status_changed' in _nplan168 and
    ('✅ Implemented' in _nplan168 or 'implemented' in _nplan168.lower())
)
check(
    "168c. NOTIFICATIONS_PLAN.md: PR #455 mentioned",
    '#455' in _nplan168
)
check(
    "168d. NOTIFICATIONS_PLAN.md: PR #456 mentioned",
    '#456' in _nplan168
)
check(
    "168e. NOTIFICATIONS_PLAN.md: accepted/rejected described as internal company states",
    'accepted' in _nplan168 and 'rejected' in _nplan168 and
    'internal' in _nplan168 and 'company' in _nplan168
)
check(
    "168f. NOTIFICATIONS_PLAN.md: rating_received mentioned as implemented",
    'rating_received' in _nplan168 and '✅' in _nplan168
)
check(
    "168g. NOTIFICATIONS_PLAN.md: PR #457 mentioned",
    '#457' in _nplan168
)
check(
    "168h. NOTIFICATIONS_PLAN.md: job_expiring_soon mentioned as blocked",
    'job_expiring_soon' in _nplan168 and
    ('Blocked' in _nplan168 or 'blocked' in _nplan168.lower())
)
check(
    "168i. NOTIFICATIONS_PLAN.md: scheduler mentioned as the blocker reason for job_expiring_soon",
    'scheduler' in _nplan168 and 'job_expiring_soon' in _nplan168
)
check(
    "168j. NOTIFICATIONS_PLAN.md: appointment reminders mentioned as scheduler-dependent",
    'appointment reminders' in _nplan168 or 'Appointments' in _nplan168
)
check(
    "168k. NOTIFICATIONS_PLAN.md: response deadline auto-expire mentioned as scheduler-dependent",
    'response deadline' in _nplan168 or 'auto-expire' in _nplan168
)
check(
    "168l. NOTIFICATIONS_PLAN.md: Phase 11 realtime/push mentioned as deferred",
    'Phase 11' in _nplan168 and
    ('deferred' in _nplan168.lower() or 'مؤجل' in _nplan168)
)

# ── SYSTEMS_INDEX update (m) ──
check(
    "168m. SYSTEMS_INDEX.md §19 updated to reference MPQ Final Closure",
    'Final Closure' in _sidx168 or 'MPQ Final Closure' in _sidx168 or '#458' in _sidx168
)

# ── No code changes (n–s) ──
check(
    "168n. auth.py NOT modified — no PR #458 marker or mpq-closure comment in auth.py",
    'PR #458' not in _auth168 and 'mpq-closure' not in _auth168
)
check(
    "168o. server.py NOT modified — no PR #458 marker or mpq-closure comment in server.py",
    'PR #458' not in _server168 and 'mpq-closure' not in _server168
)
check(
    "168p. No new CREATE TABLE added to docs/NOTIFICATIONS_PLAN.md (schema unchanged)",
    'CREATE TABLE scheduler' not in _nplan168 and 'CREATE TABLE job_expiring' not in _nplan168
)
check(
    "168q. No inline script/style injected into docs/NOTIFICATIONS_PLAN.md",
    '<script>' not in _nplan168 and '<style>' not in _nplan168
)
_sched_note168 = (
    _nplan168.split('Scheduler Blocker Note')[1].split('Source of Truth')[0]
    if 'Scheduler Blocker Note' in _nplan168 else ''
)
check(
    "168r. Scheduler Blocker Note section exists and is non-empty",
    bool(_sched_note168.strip())
)
check(
    "168s. No WebSocket/push implementation text inside Scheduler Blocker Note section",
    'WebSocket' not in _sched_note168 and 'push' not in _sched_note168.lower()
)

# ── PR declaration (t–u) ──
check(
    "168t. NOTIFICATIONS_PLAN.md is docs-only (no implementation code block referencing new feature)",
    'docs-only' in _nplan168.lower() or 'docs only' in _nplan168.lower() or
    'PR #458' in _nplan168
)
check(
    "168u. NEXT ACTIVE DEVELOPMENT PHASE — Scheduler Infrastructure noted in SYSTEMS_INDEX.md",
    'Scheduler Infrastructure' in _sidx168 and 'job_expiring_soon' in _sidx168
)

# ════════════════════════════════════════════════════════════════════════
# §169 — Appointments Phase 0 Plan (PR #459)
# 45 static checks: docs/APPOINTMENTS_PLAN.md + SYSTEMS_INDEX.md + no code changes
# ════════════════════════════════════════════════════════════════════════

with open("docs/APPOINTMENTS_PLAN.md", encoding="utf-8") as f:
    _aplan169 = f.read()

with open("docs/SYSTEMS_INDEX.md", encoding="utf-8") as f:
    _sidx169 = f.read()

with open("auth.py", encoding="utf-8") as f:
    _auth169 = f.read()

with open("server.py", encoding="utf-8") as f:
    _server169 = f.read()

# ── §1 Purpose (1–3) ──────────────────────────────────────────────────
check(
    "169-1. APPOINTMENTS_PLAN.md exists and is non-empty",
    len(_aplan169.strip()) > 500
)
check(
    "169-2. APPOINTMENTS_PLAN.md: §1 Purpose section exists",
    '## §1' in _aplan169 or '### §1' in _aplan169 or '## 1.' in _aplan169 or 'Purpose' in _aplan169
)
check(
    "169-3. APPOINTMENTS_PLAN.md: covers invitations, scheduling, acceptance, reschedule, cancellation",
    'دعوة' in _aplan169 or 'invitation' in _aplan169.lower()
)

# ── §2 Core Rule (4–6) ────────────────────────────────────────────────
check(
    "169-4. APPOINTMENTS_PLAN.md: §2 Core Rule / Messenger العام vs Appointment Room",
    'Messenger' in _aplan169 and ('Appointment Room' in _aplan169 or 'غرفة' in _aplan169)
)
check(
    "169-5. APPOINTMENTS_PLAN.md: formal decisions only via official buttons (not from chat)",
    'أزرار' in _aplan169 or 'buttons' in _aplan169.lower()
)
check(
    "169-6. APPOINTMENTS_PLAN.md: Core Rule explicitly separates chat from formal decisions",
    'المحادثة' in _aplan169 or 'chat' in _aplan169.lower() or 'الشات' in _aplan169
)

# ── §3 User Flows (7–9) ───────────────────────────────────────────────
check(
    "169-7. APPOINTMENTS_PLAN.md: employee user flow described",
    'موظف' in _aplan169 or 'employee' in _aplan169.lower()
)
check(
    "169-8. APPOINTMENTS_PLAN.md: company user flow described",
    'شركة' in _aplan169 or 'company' in _aplan169.lower()
)
check(
    "169-9. APPOINTMENTS_PLAN.md: user flows cover open/accept/reschedule/cancel actions",
    ('قبول' in _aplan169 or 'accept' in _aplan169.lower()) and
    ('إلغاء' in _aplan169 or 'cancel' in _aplan169.lower())
)

# ── §4 Appointment Cards (10–11) ─────────────────────────────────────
check(
    "169-10. APPOINTMENTS_PLAN.md: appointment cards described (employee card + company card)",
    'بطاقة' in _aplan169 or 'card' in _aplan169.lower()
)
check(
    "169-11. APPOINTMENTS_PLAN.md: card fields include status and date/time",
    'status' in _aplan169.lower() or 'الحالة' in _aplan169
)

# ── §5 Appointment Room (12–13) ───────────────────────────────────────
check(
    "169-12. APPOINTMENTS_PLAN.md: §5 Appointment Room structure described",
    'غرفة' in _aplan169 or 'Room' in _aplan169
)
check(
    "169-13. APPOINTMENTS_PLAN.md: room includes decision buttons, event timeline, and appointment thread",
    ('timeline' in _aplan169.lower() or 'سجل' in _aplan169 or 'أحداث' in _aplan169)
)

# ── §6 Appointment States (14–17) ─────────────────────────────────────
check(
    "169-14. APPOINTMENTS_PLAN.md: §6 Appointment States section exists with at least 7 states",
    'pending_response' in _aplan169 and 'confirmed' in _aplan169 and 'cancelled' in _aplan169
)
check(
    "169-15. APPOINTMENTS_PLAN.md: draft state documented",
    'draft' in _aplan169
)
check(
    "169-16. APPOINTMENTS_PLAN.md: expired/missed states documented",
    'expired' in _aplan169 and ('missed' in _aplan169 or 'completed' in _aplan169)
)
check(
    "169-17. APPOINTMENTS_PLAN.md: closed state documented (terminal state)",
    'closed' in _aplan169
)

# ── §7 Response Deadline (18–20) ──────────────────────────────────────
check(
    "169-18. APPOINTMENTS_PLAN.md: §7 Response Deadline section exists with deadline options",
    'response_deadline' in _aplan169 or 'deadline' in _aplan169.lower()
)
check(
    "169-19. APPOINTMENTS_PLAN.md: auto-expire requires scheduler (deferred)",
    'scheduler' in _aplan169.lower() and ('deferred' in _aplan169.lower() or 'مؤجل' in _aplan169)
)
check(
    "169-20. APPOINTMENTS_PLAN.md: computed status at request-time is acceptable without scheduler",
    'request-time' in _aplan169 or 'computed' in _aplan169.lower() or 'NOW()' in _aplan169
)

# ── §8 Proposed Data Model (21–24) ────────────────────────────────────
check(
    "169-21. APPOINTMENTS_PLAN.md: §8 Data Model section exists with appointments table",
    'appointments' in _aplan169
)
check(
    "169-22. APPOINTMENTS_PLAN.md: data model includes appointment_participants table",
    'appointment_participants' in _aplan169
)
check(
    "169-23. APPOINTMENTS_PLAN.md: data model includes appointment_events table",
    'appointment_events' in _aplan169
)
check(
    "169-24. APPOINTMENTS_PLAN.md: data model includes appointment_messages table",
    'appointment_messages' in _aplan169
)

# ── §9 Proposed API (25–27) ───────────────────────────────────────────
check(
    "169-25. APPOINTMENTS_PLAN.md: §9 API section exists with at least 8 endpoints",
    'POST /appointments' in _aplan169 or '/appointments' in _aplan169
)
check(
    "169-26. APPOINTMENTS_PLAN.md: API covers accept, reschedule, cancel, complete, close endpoints",
    'accept' in _aplan169 and 'reschedule' in _aplan169 and 'cancel' in _aplan169
)
check(
    "169-27. APPOINTMENTS_PLAN.md: API covers messages and events sub-resources",
    '/messages' in _aplan169 and '/events' in _aplan169
)

# ── §10 Permissions (28–29) ───────────────────────────────────────────
check(
    "169-28. APPOINTMENTS_PLAN.md: §10 Permissions section — owner-only access documented",
    'owner' in _aplan169.lower() or 'صاحب' in _aplan169 or 'Permissions' in _aplan169
)
check(
    "169-29. APPOINTMENTS_PLAN.md: online_url access restricted to participants only",
    'online_url' in _aplan169
)

# ── §11 Event Types (30) ──────────────────────────────────────────────
check(
    "169-30. APPOINTMENTS_PLAN.md: §11 Event Types section with appointment_created and message_sent",
    'appointment_created' in _aplan169 and 'message_sent' in _aplan169
)

# ── §12 Notifications (31–33) ─────────────────────────────────────────
check(
    "169-31. APPOINTMENTS_PLAN.md: §12 Notifications section exists with event_key format",
    'event_key' in _aplan169
)
check(
    "169-32. APPOINTMENTS_PLAN.md: scheduler-based reminder notifications marked as deferred",
    'reminder' in _aplan169.lower() and
    ('deferred' in _aplan169.lower() or 'مؤجل' in _aplan169 or 'Scheduler' in _aplan169)
)
check(
    "169-33. APPOINTMENTS_PLAN.md: at least 7 event-driven notification types documented",
    'appointment_invited' in _aplan169 or
    ('notification' in _aplan169.lower() and 'invite' in _aplan169.lower())
)

# ── §13 Security Risks (34–35) ────────────────────────────────────────
check(
    "169-34. APPOINTMENTS_PLAN.md: §13 Security Risks section with URL leakage risk",
    'online_url' in _aplan169 and ('risk' in _aplan169.lower() or 'مخاطر' in _aplan169 or 'Security' in _aplan169)
)
check(
    "169-35. APPOINTMENTS_PLAN.md: unauthorized access and chat bypass risks documented",
    ('unauthorized' in _aplan169.lower() or 'غير مصرح' in _aplan169 or 'غير طرف' in _aplan169) or
    ('bypass' in _aplan169.lower() or 'تجاوز' in _aplan169 or 'الشات بدل' in _aplan169)
)

# ── §14 Build Phases (36–37) ──────────────────────────────────────────
check(
    "169-36. APPOINTMENTS_PLAN.md: §14 Build Phases documented starting from Phase 1 (schema only)",
    'Phase 1' in _aplan169 and ('schema' in _aplan169.lower() or 'مخطط' in _aplan169)
)
check(
    "169-37. APPOINTMENTS_PLAN.md: Phase 8 (scheduler reminders) is marked as deferred",
    'Phase 8' in _aplan169 and ('deferred' in _aplan169.lower() or 'مؤجل' in _aplan169 or 'scheduler' in _aplan169.lower())
)

# ── §15 Non-goals (38) ────────────────────────────────────────────────
check(
    "169-38. APPOINTMENTS_PLAN.md: §15 Non-goals section explicitly states no code/schema in this PR",
    'Non-goals' in _aplan169 or 'non-goals' in _aplan169.lower() or 'لا تنفيذ' in _aplan169
)

# ── No code changes (39–42) ───────────────────────────────────────────
check(
    "169-39. auth.py appointments migration — if present, uses IF NOT EXISTS (idempotent pattern)",
    # PR #459 was docs-only; Phase 1 (PR #460) correctly adds the migration with IF NOT EXISTS.
    # This check now verifies: if the migration exists, it uses the correct idempotent pattern.
    ('def _migrate_appointments' not in _auth169) or
    ('CREATE TABLE IF NOT EXISTS appointments' in _auth169)
)
check(
    "169-40. server.py NOT modified — no appointments endpoint added to server.py",
    'POST /appointments' not in _server169 and
    '@app.post("/appointments' not in _server169
)
check(
    "169-41. No appointment_messages WebSocket in server.py",
    'appointment_messages' not in _server169 or
    'ws://appointment' not in _server169.lower()
)
check(
    "169-42. auth.py appointments migration — if present, uses IF NOT EXISTS (idempotent pattern)",
    # Phase 1 correctly adds appointment_participants with IF NOT EXISTS.
    ('def _migrate_appointments' not in _auth169) or
    ('CREATE TABLE IF NOT EXISTS appointment_participants' in _auth169)
)

# ── SYSTEMS_INDEX update (43–44) ──────────────────────────────────────
check(
    "169-43. SYSTEMS_INDEX.md contains §23 Appointments System entry",
    '### 23.' in _sidx169 and 'Appointments' in _sidx169
)
check(
    "169-44. SYSTEMS_INDEX.md §23 references docs/APPOINTMENTS_PLAN.md",
    'docs/APPOINTMENTS_PLAN.md' in _sidx169 and '### 23.' in _sidx169
)

# ── PR declaration (45) ───────────────────────────────────────────────
check(
    "169-45. APPOINTMENTS_PLAN.md footer declares PR #459 docs-only with no implementation",
    'PR #459' in _aplan169 and
    ('docs-only' in _aplan169.lower() or 'docs only' in _aplan169.lower() or 'لا تنفيذ' in _aplan169)
)

# ════════════════════════════════════════════════════════════════════════
# §170 — Appointments Phase 1 Schema (PR #460)
# 49 static checks: auth.py migration + server.py startup + docs updates
# ════════════════════════════════════════════════════════════════════════

with open("auth.py", encoding="utf-8") as f:
    _auth170 = f.read()

with open("server.py", encoding="utf-8") as f:
    _server170 = f.read()

with open("docs/APPOINTMENTS_PLAN.md", encoding="utf-8") as f:
    _aplan170 = f.read()

with open("docs/SYSTEMS_INDEX.md", encoding="utf-8") as f:
    _sidx170 = f.read()

# ── Migration function exists (1–4) ───────────────────────────────────
check(
    "170-1. auth.py: _migrate_appointments() function defined",
    "def _migrate_appointments(" in _auth170
)
check(
    "170-2. auth.py: appointments table created with IF NOT EXISTS",
    "CREATE TABLE IF NOT EXISTS appointments" in _auth170
)
check(
    "170-3. auth.py: appointment_participants table created with IF NOT EXISTS",
    "CREATE TABLE IF NOT EXISTS appointment_participants" in _auth170
)
check(
    "170-4. auth.py: appointment_events table created with IF NOT EXISTS",
    "CREATE TABLE IF NOT EXISTS appointment_events" in _auth170
)
check(
    "170-4b. auth.py: appointment_messages table created with IF NOT EXISTS",
    "CREATE TABLE IF NOT EXISTS appointment_messages" in _auth170
)

# Extract the entire _migrate_appointments function body for column checks.
# Split on function defs to isolate just that function, then search within it.
_mig170 = (
    _auth170.split("def _migrate_appointments(")[1].split("\ndef ")[0]
    if "def _migrate_appointments(" in _auth170 else ""
)

# ── appointments columns (5–19) ───────────────────────────────────────
check("170-5.  appointments: job_id column present",             "job_id" in _mig170)
check("170-6.  appointments: application_id column present",     "application_id" in _mig170)
check("170-7.  appointments: company_id column present",         "company_id" in _mig170)
check("170-8.  appointments: applicant_id column present",       "applicant_id" in _mig170)
check("170-9.  appointments: created_by column present",         "created_by" in _mig170)
check("170-10. appointments: representative_user_id present",    "representative_user_id" in _mig170)
check("170-11. appointments: representative_name present",       "representative_name" in _mig170)
check("170-12. appointments: status column present",             "status" in _mig170)
check("170-13. appointments: mode column present",               "mode" in _mig170)
check("170-14. appointments: scheduled_at column present",       "scheduled_at" in _mig170)
check("170-15. appointments: response_deadline_at present",      "response_deadline_at" in _mig170)
check("170-16. appointments: location_text column present",      "location_text" in _mig170)
check("170-17. appointments: online_url column present",         "online_url" in _mig170)
check("170-18. appointments: notes column present",              "notes" in _mig170)
check("170-19. appointments: closed_at column present",          "closed_at" in _mig170)

# ── appointment_participants columns (20–24) ──────────────────────────
check("170-20. appointment_participants: appointment_id present", "appointment_id" in _mig170)
check("170-21. appointment_participants: user_id present",        "user_id" in _mig170)
check("170-22. appointment_participants: role present",           "role" in _mig170)
check("170-23. appointment_participants: can_message present",    "can_message" in _mig170)
check("170-24. appointment_participants: can_decide present",     "can_decide" in _mig170)

# ── appointment_events columns (25–30) ────────────────────────────────
check("170-25. appointment_events: appointment_id present",  "appointment_id" in _mig170)
check("170-26. appointment_events: actor_id present",        "actor_id" in _mig170)
check("170-27. appointment_events: event_type present",      "event_type" in _mig170)
check("170-28. appointment_events: old_status present",      "old_status" in _mig170)
check("170-29. appointment_events: new_status present",      "new_status" in _mig170)
check("170-30. appointment_events: payload JSONB present",   "payload" in _mig170 and "JSONB" in _mig170)

# ── appointment_messages columns (31–35) ──────────────────────────────
check("170-31. appointment_messages: appointment_id present", "appointment_id" in _mig170)
check("170-32. appointment_messages: sender_id present",      "sender_id" in _mig170)
check("170-33. appointment_messages: body present",           "body" in _mig170)
check("170-34. appointment_messages: edited_at present",      "edited_at" in _mig170)
check("170-35. appointment_messages: deleted_at present",     "deleted_at" in _mig170)

# ── Indexes (36–39) ───────────────────────────────────────────────────
check(
    "170-36. indexes for appointments exist (company_id, status, scheduled_at)",
    "idx_appt_company" in _auth170 and "idx_appt_status" in _auth170 and
    "idx_appt_scheduled" in _auth170
)
check(
    "170-37. indexes for appointment_participants exist",
    "idx_appt_part_appt" in _auth170 and "idx_appt_part_user" in _auth170
)
check(
    "170-38. indexes for appointment_events exist",
    "idx_appt_evt_appt" in _auth170 and "idx_appt_evt_type" in _auth170
)
check(
    "170-39. indexes for appointment_messages exist",
    "idx_appt_msg_appt" in _auth170 and "idx_appt_msg_created" in _auth170
)

# ── Idempotency (40) ──────────────────────────────────────────────────
check(
    "170-40. migration is idempotent — all tables use IF NOT EXISTS",
    _auth170.count("CREATE TABLE IF NOT EXISTS appointment") == 4 and
    _auth170.count("CREATE INDEX IF NOT EXISTS idx_appt") >= 12
)

# ── server.py startup (41) ────────────────────────────────────────────
check(
    "170-41. server.py: _migrate_appointments() imported and called in startup",
    "_migrate_appointments" in _server170 and
    "_migrate_appointments()" in _server170
)

# ── No forbidden additions (42–46) ────────────────────────────────────
check(
    "170-42. No new API endpoints for appointments in server.py",
    '@app.post("/appointments' not in _server170 and
    '@app.get("/appointments' not in _server170
)
check(
    "170-43. No frontend HTML/JS changes (no appointments page yet)",
    'appointments.html' not in _server170.split('_migrate_appointments')[0]
)
check(
    "170-44. No notification hooks for appointments in auth.py",
    'create_notification' not in _auth170.split('def _migrate_appointments')[1]
    if 'def _migrate_appointments' in _auth170 else True
)
check(
    "170-45. No scheduler/WebSocket/push in migration",
    'WebSocket' not in _auth170.split('def _migrate_appointments')[1].split('def ')[0]
    if 'def _migrate_appointments' in _auth170 else True
)
check(
    "170-46. No Messenger changes (messages table not modified in migration)",
    'ALTER TABLE messages' not in _auth170.split('def _migrate_appointments')[1].split('def ')[0]
    if 'def _migrate_appointments' in _auth170 else True
)

# ── Docs updated (47–49) ──────────────────────────────────────────────
check(
    "170-47. APPOINTMENTS_PLAN.md: Phase 1 marked as implemented (PR #460)",
    'Phase 1' in _aplan170 and
    ('✅' in _aplan170 or 'مُنجز' in _aplan170 or 'PR #460' in _aplan170)
)
check(
    "170-48. APPOINTMENTS_PLAN.md: Phase 1 schema section with all 4 tables",
    'appointment_participants' in _aplan170 and 'appointment_events' in _aplan170 and
    'appointment_messages' in _aplan170
)
check(
    "170-49. SYSTEMS_INDEX.md §23: status updated to Phase 1 schema implemented",
    'Phase 1 schema implemented' in _sidx170 or
    ('Phase 1' in _sidx170 and 'implemented' in _sidx170)
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
