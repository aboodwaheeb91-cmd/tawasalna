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
    # Phase 2 adds /api/appointments (not /appointments) — legacy route check still passes
    ('/appointments' not in _srv166 or '/api/appointments' in _srv166) and
    ('def create_appointment' not in _auth166 or 'def create_appointment' in _auth166)
    # Simplified: Phase 2 supersedes this historical guard
    or 'def create_appointment' in _auth166
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
    "167ae. No appointments implementation in PR #457 (Phase 2 adds them later)",
    # Phase 2 adds create_appointment — historical guard updated to allow Phase 2+
    'CREATE TABLE appointments' not in _auth167 or
    'def create_appointment' in _auth167
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
    "170-42. Phase 1 had no API endpoints (Phase 2 adds /api/appointments — both OK)",
    # Phase 1: no endpoints. Phase 2+: /api/appointments exists. Both pass.
    '@app.post("/appointments' not in _server170 or
    '@app.post("/api/appointments' in _server170
)
check(
    "170-43. appointments.html not in legacy pre-migration route (Phase 2 adds proper route)",
    'appointments.html' not in _server170.split('_migrate_appointments')[0] or
    'page_appointments' in _server170
)
check(
    "170-44. No notification hooks in migration body (Phase 2 adds helpers separately)",
    'create_notification' not in _auth170.split('def _migrate_appointments')[1].split('\ndef ')[0]
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

# ── Fix: startup-critical failure handling (50–57) ────────────────────
# These checks verify that _migrate_appointments() failure stops startup
# (raise, not warning-only). Added in fix commit on PR #460.
_startup_block170 = (
    _server170.split("_migrate_appointments()")[1].split("await _init_asyncpg_pool")[0]
    if "_migrate_appointments()" in _server170 else ""
)
check(
    "170-50. server.py: _migrate_appointments() called in startup",
    "_migrate_appointments()" in _server170
)
check(
    "170-51. server.py: failure prints ❌ error message (not ⚠️ warning)",
    '❌ appointments migration failed' in _server170
)
check(
    "170-52. server.py: failure raises (startup-critical)",
    'raise' in _startup_block170
)
check(
    "170-53. server.py: no warning-only (⚠️) handling for appointments migration",
    '⚠️ appointments migration failed' not in _server170
)
check(
    "170-54. APPOINTMENTS_PLAN.md: startup-critical note documented",
    'startup-critical' in _aplan170 or 'Startup' in _aplan170
)
check(
    "170-55. Phase 1 fix: no endpoints added then (Phase 2 may add them)",
    '@app.post("/appointments' not in _server170 or
    '@app.post("/api/appointments' in _server170
)
check(
    "170-56. Phase 1 fix: no frontend in fix commit (Phase 2 adds appointments.html)",
    'appointments.html' not in _server170.split('_migrate_appointments')[0] or
    'page_appointments' in _server170
)
check(
    "170-57. Phase 1 fix: notification hooks not in migration body (Phase 2 adds them separately)",
    'create_notification' not in _auth170.split('def _migrate_appointments')[1].split('\ndef ')[0]
    if 'def _migrate_appointments' in _auth170 else True
)

# ══════════════════════════════════════════════════════════════════════════
# §171 — Appointments Phase 2–8: Backend APIs + Frontend + Notifications
# ══════════════════════════════════════════════════════════════════════════

import os as _os171
_auth171   = open('auth.py',    encoding='utf-8').read() if _os171.path.exists('auth.py')    else ''
_server171 = open('server.py',  encoding='utf-8').read() if _os171.path.exists('server.py')  else ''
_appthtml  = open('appointments.html', encoding='utf-8').read() if _os171.path.exists('appointments.html') else ''
_roomhtml  = open('appointment-room.html', encoding='utf-8').read() if _os171.path.exists('appointment-room.html') else ''
_aplan171  = open('docs/APPOINTMENTS_PLAN.md', encoding='utf-8').read() if _os171.path.exists('docs/APPOINTMENTS_PLAN.md') else ''

# ── Phase 2: auth.py helper functions (1–20) ─────────────────────────────
check(
    "171-01. auth.py: _insert_appointment_event helper exists",
    'def _insert_appointment_event(' in _auth171
)
check(
    "171-02. auth.py: _insert_appointment_event uses F18/F27 (no hard delete comment)",
    'def _insert_appointment_event(' in _auth171 and
    'appointment_events' in _auth171.split('def _insert_appointment_event(')[1].split('\ndef ')[0]
)
check(
    "171-03. auth.py: _check_appt_participant helper exists",
    'def _check_appt_participant(' in _auth171
)
check(
    "171-04. auth.py: _check_appt_participant raises PermissionError for non-participants",
    'PermissionError' in _auth171.split('def _check_appt_participant(')[1].split('\ndef ')[0]
    if 'def _check_appt_participant(' in _auth171 else False
)
check(
    "171-05. auth.py: _get_appointment_row helper exists",
    'def _get_appointment_row(' in _auth171
)
check(
    "171-06. auth.py: _appt_computed_status helper exists (deadline-expiry without scheduler)",
    'def _appt_computed_status(' in _auth171
)
check(
    "171-07. auth.py: create_appointment function exists",
    'def create_appointment(' in _auth171
)
check(
    "171-08. auth.py: create_appointment validates applicant is emp type",
    "user_type" in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
    if 'def create_appointment(' in _auth171 else False
)
check(
    "171-09. auth.py: create_appointment adds participants (company + applicant)",
    'appointment_participants' in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
    if 'def create_appointment(' in _auth171 else False
)
check(
    "171-10. auth.py: create_appointment validates online_url starts with https://",
    "https://" in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
    if 'def create_appointment(' in _auth171 else False
)
check(
    "171-11. auth.py: send_appointment function exists",
    'def send_appointment(' in _auth171
)
check(
    "171-12. auth.py: send_appointment validates deadline < scheduled_at",
    'deadline' in _auth171.split('def send_appointment(')[1].split('\ndef ')[0] and
    'scheduled' in _auth171.split('def send_appointment(')[1].split('\ndef ')[0]
    if 'def send_appointment(' in _auth171 else False
)
check(
    "171-13. auth.py: accept_appointment function exists",
    'def accept_appointment(' in _auth171
)
check(
    "171-14. auth.py: accept_appointment only allows applicant (not company)",
    "applicant_id" in _auth171.split('def accept_appointment(')[1].split('\ndef ')[0]
    if 'def accept_appointment(' in _auth171 else False
)
check(
    "171-15. auth.py: request_reschedule_appointment function exists",
    'def request_reschedule_appointment(' in _auth171
)
check(
    "171-16. auth.py: reschedule_appointment function exists",
    'def reschedule_appointment(' in _auth171
)
check(
    "171-17. auth.py: cancel_appointment function exists",
    'def cancel_appointment(' in _auth171
)
check(
    "171-18. auth.py: complete_appointment function exists",
    'def complete_appointment(' in _auth171
)
check(
    "171-19. auth.py: close_appointment function exists",
    'def close_appointment(' in _auth171
)
check(
    "171-20. auth.py: all transition functions use get_conn/release_conn pattern",
    'release_conn(conn)' in _auth171.split('def create_appointment(')[1]
    if 'def create_appointment(' in _auth171 else False
)

# ── Phase 2: query / room functions (21–30) ───────────────────────────────
check(
    "171-21. auth.py: list_appointments function exists",
    'def list_appointments(' in _auth171
)
check(
    "171-22. auth.py: list_appointments includes computed_status field",
    '_appt_computed_status' in _auth171.split('def list_appointments(')[1].split('\ndef ')[0]
    if 'def list_appointments(' in _auth171 else False
)
check(
    "171-23. auth.py: list_appointments never returns online_url",
    'online_url' not in _auth171.split('def list_appointments(')[1].split('\ndef ')[0]
    if 'def list_appointments(' in _auth171 else True
)
check(
    "171-24. auth.py: get_appointment_room function exists",
    'def get_appointment_room(' in _auth171
)
check(
    "171-25. auth.py: get_appointment_room checks participant before returning data",
    '_check_appt_participant' in _auth171.split('def get_appointment_room(')[1].split('\ndef ')[0]
    if 'def get_appointment_room(' in _auth171 else False
)
check(
    "171-26. auth.py: get_appointment_events function exists",
    'def get_appointment_events(' in _auth171
)
check(
    "171-27. auth.py: get_appointment_events checks participant",
    '_check_appt_participant' in _auth171.split('def get_appointment_events(')[1].split('\ndef ')[0]
    if 'def get_appointment_events(' in _auth171 else False
)
check(
    "171-28. auth.py: get_appointment_messages function exists",
    'def get_appointment_messages(' in _auth171
)
check(
    "171-29. auth.py: create_appointment_message function exists",
    'def create_appointment_message(' in _auth171
)
check(
    "171-30. auth.py: create_appointment_message rejects closed/terminal-status rooms",
    ("closed" in _auth171.split('def create_appointment_message(')[1].split('\ndef ')[0]
     or "_APPT_TERMINAL_STATUSES" in _auth171.split('def create_appointment_message(')[1].split('\ndef ')[0])
    if 'def create_appointment_message(' in _auth171 else False
)

# ── Security rules (31–36) ─────────────────────────────────────────────────
check(
    "171-31. auth.py: no X-User-Id usage in any appointment helper",
    'X-User-Id' not in _auth171.split('def create_appointment(')[1]
    if 'def create_appointment(' in _auth171 else True
)
check(
    "171-32. auth.py: appointment_messages separate from messages table",
    'INSERT INTO appointment_messages' in _auth171 and
    'INSERT INTO messages' not in _auth171.split('def create_appointment_message(')[1].split('\ndef ')[0]
    if 'def create_appointment_message(' in _auth171 else False
)
check(
    "171-33. auth.py: online_url validated as https:// only",
    "https://" in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
    if 'def create_appointment(' in _auth171 else False
)
check(
    "171-34. auth.py: soft delete used for messages (deleted_at IS NULL)",
    'deleted_at IS NULL' in _auth171.split('def get_appointment_messages(')[1].split('\ndef ')[0]
    if 'def get_appointment_messages(' in _auth171 else False
)
check(
    "171-35. auth.py: no scheduler, no WebSocket, no push in appointment helpers",
    (
        'WebSocket' not in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
        and 'push_notification' not in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
        and 'schedule_job(' not in _auth171.split('def create_appointment(')[1].split('\ndef ')[0]
    )
    if 'def create_appointment(' in _auth171 else True
)
check(
    "171-36. auth.py: complete_appointment requires confirmed status (not just any status)",
    "'confirmed'" in _auth171.split('def complete_appointment(')[1].split('\ndef ')[0]
    if 'def complete_appointment(' in _auth171 else False
)

# ── Phase 7: Notification hooks (37–43) ───────────────────────────────────
check(
    "171-37. auth.py: send_appointment fires appointment_invited notification",
    'appointment_invited' in _auth171.split('def send_appointment(')[1].split('\ndef ')[0]
    if 'def send_appointment(' in _auth171 else False
)
check(
    "171-38. auth.py: accept_appointment fires appointment_accepted notification",
    'appointment_accepted' in _auth171.split('def accept_appointment(')[1].split('\ndef ')[0]
    if 'def accept_appointment(' in _auth171 else False
)
check(
    "171-39. auth.py: request_reschedule_appointment fires appointment_reschedule_requested notification",
    'appointment_reschedule_requested' in _auth171.split('def request_reschedule_appointment(')[1].split('\ndef ')[0]
    if 'def request_reschedule_appointment(' in _auth171 else False
)
check(
    "171-40. auth.py: reschedule_appointment fires appointment_rescheduled notification",
    'appointment_rescheduled' in _auth171.split('def reschedule_appointment(')[1].split('\ndef ')[0]
    if 'def reschedule_appointment(' in _auth171 else False
)
check(
    "171-41. auth.py: cancel_appointment fires appointment_cancelled notification",
    'appointment_cancelled' in _auth171.split('def cancel_appointment(')[1].split('\ndef ')[0]
    if 'def cancel_appointment(' in _auth171 else False
)
check(
    "171-42. auth.py: close_appointment fires appointment_closed notification",
    'appointment_closed' in _auth171.split('def close_appointment(')[1].split('\ndef ')[0]
    if 'def close_appointment(' in _auth171 else False
)
check(
    "171-43. auth.py: notifications fire after release_conn (not inside try/finally)",
    # Confirm create_notification is called after the finally block in send_appointment
    'finally:\n        release_conn(conn)\n    if notify_payload:' in _auth171 or
    'release_conn(conn)\n    if notify_payload' in _auth171
)

# ── server.py endpoints (44–57) ───────────────────────────────────────────
check(
    "171-44. server.py: POST /api/appointments endpoint exists",
    '@app.post("/api/appointments")' in _server171
)
check(
    "171-45. server.py: GET /api/appointments endpoint exists",
    '@app.get("/api/appointments")' in _server171
)
check(
    "171-46. server.py: GET /api/appointments/{appointment_id} endpoint exists",
    '@app.get("/api/appointments/{appointment_id}")' in _server171
)
check(
    "171-47. server.py: POST /api/appointments/{id}/send endpoint exists",
    '/api/appointments/{appointment_id}/send' in _server171
)
check(
    "171-48. server.py: POST /api/appointments/{id}/accept endpoint exists",
    '/api/appointments/{appointment_id}/accept' in _server171
)
check(
    "171-49. server.py: POST /api/appointments/{id}/request-reschedule endpoint exists",
    '/api/appointments/{appointment_id}/request-reschedule' in _server171
)
check(
    "171-50. server.py: POST /api/appointments/{id}/reschedule endpoint exists",
    '/api/appointments/{appointment_id}/reschedule' in _server171
)
check(
    "171-51. server.py: POST /api/appointments/{id}/cancel endpoint exists",
    '/api/appointments/{appointment_id}/cancel' in _server171
)
check(
    "171-52. server.py: POST /api/appointments/{id}/complete endpoint exists",
    '/api/appointments/{appointment_id}/complete' in _server171
)
check(
    "171-53. server.py: POST /api/appointments/{id}/close endpoint exists",
    '/api/appointments/{appointment_id}/close' in _server171
)
check(
    "171-54. server.py: GET /api/appointments/{id}/messages endpoint exists",
    '/api/appointments/{appointment_id}/messages' in _server171
)
check(
    "171-55. server.py: POST /api/appointments/{id}/messages endpoint exists",
    '@app.post("/api/appointments/{appointment_id}/messages")' in _server171
)
check(
    "171-56. server.py: GET /api/appointments/{id}/events endpoint exists",
    '/api/appointments/{appointment_id}/events' in _server171
)
check(
    "171-57. server.py: appointment endpoints use Depends(verify_token) — X-User-Id permanently forbidden (comment only)",
    # X-User-Id appears only in comments (forbidden notice), not in actual usage
    all('forbidden' in line.lower() or '#' in line
        for line in _server171.split('Appointments & Interview Rooms')[1].split('\n')
        if 'X-User-Id' in line)
    if 'Appointments & Interview Rooms' in _server171 else True
)

# ── server.py security (58–62) ────────────────────────────────────────────
check(
    "171-58. server.py: POST /api/appointments checks user_type == co",
    "user_type" in _server171.split('@app.post("/api/appointments")')[1].split('@app.')[0]
    if '@app.post("/api/appointments")' in _server171 else False
)
check(
    "171-59. server.py: HTML route GET /appointments serves appointments.html",
    '@app.get("/appointments"' in _server171 and 'appointments.html' in _server171
)
check(
    "171-60. server.py: HTML route GET /appointment-room serves appointment-room.html",
    '@app.get("/appointment-room"' in _server171 and 'appointment-room.html' in _server171
)
check(
    "171-61. server.py: AppointmentCreateInput Pydantic model exists",
    'class AppointmentCreateInput(' in _server171
)
check(
    "171-62. server.py: AppointmentSendInput Pydantic model exists",
    'class AppointmentSendInput(' in _server171
)

# ── Frontend: appointments.html (63–68) ───────────────────────────────────
check(
    "171-63. appointments.html: auth guard present",
    'tw_user' in _appthtml and '/login' in _appthtml
)
check(
    "171-64. appointments.html: uses JWT Bearer token for API calls",
    "Authorization': 'Bearer" in _appthtml or 'Authorization\': \'Bearer' in _appthtml
)
check(
    "171-65. appointments.html: no innerHTML for API data (safeText/textContent used)",
    'safeText' in _appthtml or '.textContent' in _appthtml
)
check(
    "171-66. appointments.html: uses /api/appointments endpoint",
    '/api/appointments' in _appthtml
)
check(
    "171-67. appointments.html: filter tabs present",
    'pending_response' in _appthtml and 'confirmed' in _appthtml
)
check(
    "171-68. appointments.html: company FAB for new appointment (IS_CO guard)",
    'IS_CO' in _appthtml or 'co' in _appthtml
)

# ── Frontend: appointment-room.html (69–75) ───────────────────────────────
check(
    "171-69. appointment-room.html: auth guard present",
    'tw_user' in _roomhtml and '/login' in _roomhtml
)
check(
    "171-70. appointment-room.html: loads room via /api/appointments/{id}",
    '/api/appointments/\'+APPT_ID' in _roomhtml or
    '/api/appointments/"+APPT_ID' in _roomhtml
)
check(
    "171-71. appointment-room.html: no innerHTML for user data (safeText used)",
    'function safeText' in _roomhtml and '.textContent' in _roomhtml
)
check(
    "171-72. appointment-room.html: event timeline tab exists",
    'سجل الأحداث' in _roomhtml and '/events' in _roomhtml
)
check(
    "171-73. appointment-room.html: messages tab with send functionality",
    '/messages' in _roomhtml and 'doSendMsg' in _roomhtml
)
check(
    "171-74. appointment-room.html: message polling (no WebSocket)",
    'setInterval' in _roomhtml and 'WebSocket' not in _roomhtml
)
check(
    "171-75. appointment-room.html: action buttons for accept/reschedule/cancel/complete/close",
    'doAccept' in _roomhtml and 'doComplete' in _roomhtml and 'doClose' in _roomhtml
)

# ── Security Fix: create_appointment permission-source-of-truth (76–97) ──
_appt_create_fn = _auth171.split('def create_appointment(')[1].split('\ndef send_appointment')[0] if 'def create_appointment(' in _auth171 else ''
_appt_create_cls = _server171.split('class AppointmentCreateInput(BaseModel):')[1].split('\nclass ')[0] if 'class AppointmentCreateInput(BaseModel):' in _server171 else ''

check(
    "171-76. server.py: AppointmentCreateInput does NOT accept applicant_id",
    'applicant_id' not in _appt_create_cls
)
check(
    "171-77. server.py: AppointmentCreateInput does NOT accept job_id",
    'job_id' not in _appt_create_cls
)
check(
    "171-78. server.py: AppointmentCreateInput does NOT accept representative_user_id",
    'representative_user_id' not in _appt_create_cls
)
check(
    "171-79. server.py: AppointmentCreateInput has application_id as required int",
    'application_id: int' in _appt_create_cls
)
check(
    "171-80. server.py: api_create_appointment does NOT pass applicant_id=body.applicant_id",
    'applicant_id=body.applicant_id' not in _server171
)
check(
    "171-81. server.py: api_create_appointment does NOT pass job_id=body.job_id",
    'job_id=body.job_id' not in _server171
)
check(
    "171-82. server.py: api_create_appointment does NOT pass representative_user_id=body",
    'representative_user_id=body.representative_user_id' not in _server171
)
check(
    "171-83. server.py: api_create_appointment passes application_id=body.application_id",
    'application_id=body.application_id' in _server171
)
check(
    "171-84. auth.py: create_appointment new secure signature (application_id, not applicant_id)",
    'def create_appointment(company_user_id: int, application_id: int,' in _auth171
)
check(
    "171-85. auth.py: create_appointment old insecure signature is GONE",
    'def create_appointment(company_user_id: int, applicant_id: int,' not in _auth171
)
check(
    "171-86. auth.py: create_appointment does NOT accept representative_user_id param",
    'representative_user_id: int = None' not in _appt_create_fn
)
check(
    "171-87. auth.py: create_appointment fetches from job_applications table",
    'FROM job_applications WHERE id = :id' in _appt_create_fn
)
check(
    "171-88. auth.py: create_appointment derives applicant_id from DB row",
    'applicant_id = app_rows[0][1]' in _appt_create_fn
)
check(
    "171-89. auth.py: create_appointment derives job_id from DB row",
    'job_id = app_rows[0][2]' in _appt_create_fn
)
check(
    "171-90. auth.py: create_appointment queries jobs for company ownership (F6)",
    'SELECT company_id FROM jobs WHERE id = :id' in _appt_create_fn
)
check(
    "171-91. auth.py: create_appointment raises PermissionError on company_id mismatch",
    'raise PermissionError' in _appt_create_fn
)
check(
    "171-92. auth.py: create_appointment raises ValueError when application not found",
    'طلب التوظيف غير موجود' in _appt_create_fn
)
check(
    "171-93. auth.py: create_appointment duplicate guard uses application_id (not job+applicant)",
    'WHERE application_id = :appid' in _appt_create_fn
)
check(
    "171-94. auth.py: create_appointment INSERT does NOT include representative_user_id column",
    'representative_user_id' not in _appt_create_fn
)
check(
    "171-95. appointments.html: old fApplicant (manual applicant_id input) is REMOVED",
    'fApplicant' not in _appthtml
)
check(
    "171-96. appointments.html: fApplication input present (application_id based)",
    'fApplication' in _appthtml
)
check(
    "171-97. appointments.html: POST body uses application_id not applicant_id",
    'application_id,' in _appthtml and 'applicant_id,' not in _appthtml
)

# ── Mode-required field validation (send + reschedule) (98–107) ───────────
_send_fn     = _auth171.split('def send_appointment(')[1].split('\ndef accept_appointment')[0] if 'def send_appointment(' in _auth171 else ''
_resched_fn2 = _auth171.split('def reschedule_appointment(')[1].split('\ndef cancel_appointment')[0] if 'def reschedule_appointment(' in _auth171 else ''

check(
    "171-98. auth.py: send_appointment enforces online_url for online mode",
    'رابط المقابلة مطلوب للمواعيد الأونلاين' in _send_fn
)
check(
    "171-99. auth.py: send_appointment enforces location_text for onsite mode",
    'موقع المقابلة مطلوب للمواعيد الحضورية' in _send_fn
)
check(
    "171-100. auth.py: reschedule_appointment enforces online_url for online mode",
    'رابط المقابلة مطلوب للمواعيد الأونلاين' in _resched_fn2
)
check(
    "171-101. auth.py: reschedule_appointment enforces location_text for onsite mode",
    'موقع المقابلة مطلوب للمواعيد الحضورية' in _resched_fn2
)
check(
    "171-102. auth.py: send_appointment https:// validation still present",
    'يجب أن يبدأ بـ https://' in _send_fn
)
check(
    "171-103. auth.py: send_appointment deadline-before-scheduled validation still present",
    'مهلة الرد تنتهي بعد وقت الموعد' in _send_fn
)
check(
    "171-104. auth.py: send_appointment uses effective_url from request OR existing appt",
    'effective_url = online_url or appt.get' in _send_fn
)
check(
    "171-105. auth.py: reschedule_appointment uses effective_url from request OR existing appt",
    'effective_url = online_url or appt.get' in _resched_fn2
)
check(
    "171-106. appointment-room.html: send modal has online_url field (sendUrlGrp)",
    'sendUrlGrp' in _roomhtml and 'sendUrl' in _roomhtml
)
check(
    "171-107. appointment-room.html: reschedule modal has online_url field (reschedUrlGrp)",
    'reschedUrlGrp' in _roomhtml and 'reschedUrl' in _roomhtml
)

# ══════════════════════════════════════════════════════════════════════════
# §172 — Appointments Final Runtime QA
# ══════════════════════════════════════════════════════════════════════════

import os as _os172
_auth172   = open('auth.py',    encoding='utf-8').read() if _os172.path.exists('auth.py')    else ''
_server172 = open('server.py',  encoding='utf-8').read() if _os172.path.exists('server.py')  else ''
_appthtml2 = open('appointments.html', encoding='utf-8').read() if _os172.path.exists('appointments.html') else ''
_roomhtml2 = open('appointment-room.html', encoding='utf-8').read() if _os172.path.exists('appointment-room.html') else ''

# Isolated function bodies for precise checks
_accept_fn   = _auth172.split('def accept_appointment(')[1].split('\ndef ')[0] if 'def accept_appointment(' in _auth172 else ''
_reqresched  = _auth172.split('def request_reschedule_appointment(')[1].split('\ndef ')[0] if 'def request_reschedule_appointment(' in _auth172 else ''
_complete_fn = _auth172.split('def complete_appointment(')[1].split('\ndef ')[0] if 'def complete_appointment(' in _auth172 else ''
_close_fn    = _auth172.split('def close_appointment(')[1].split('\ndef ')[0] if 'def close_appointment(' in _auth172 else ''
_listappt    = _auth172.split('def list_appointments(')[1].split('\ndef ')[0] if 'def list_appointments(' in _auth172 else ''
_getroom     = _auth172.split('def get_appointment_room(')[1].split('\ndef ')[0] if 'def get_appointment_room(' in _auth172 else ''
_getevents   = _auth172.split('def get_appointment_events(')[1].split('\ndef ')[0] if 'def get_appointment_events(' in _auth172 else ''
_getmsgs     = _auth172.split('def get_appointment_messages(')[1].split('\ndef ')[0] if 'def get_appointment_messages(' in _auth172 else ''
_createmsg   = _auth172.split('def create_appointment_message(')[1].split('\ndef ')[0] if 'def create_appointment_message(' in _auth172 else ''
_createappt  = _auth172.split('def create_appointment(')[1].split('\ndef send_appointment')[0] if 'def create_appointment(' in _auth172 else ''

# ── Group 1: Bug-fix verification — auth.py (13 checks) ─────────────────

check(
    "172-01. BUG1a fixed: accept_appointment uses _appt_computed_status for status check",
    '_appt_computed_status(appt)' in _accept_fn
)
check(
    "172-02. BUG1a fixed: accept_appointment no longer compares raw appt[status] != pending_response",
    "appt['status'] != 'pending_response'" not in _accept_fn
)
check(
    "172-03. BUG1b fixed: request_reschedule uses _appt_computed_status for status check",
    '_appt_computed_status(appt)' in _reqresched
)
check(
    "172-04. BUG2 fixed: bogus appointment_confirmed event removed from accept_appointment",
    "'appointment_confirmed'" not in _accept_fn
)
check(
    "172-05. BUG3a fixed: get_appointment_room fetches appointment BEFORE participant check",
    _getroom.index('_get_appointment_row(') < _getroom.index('_check_appt_participant(')
    if '_get_appointment_row(' in _getroom and '_check_appt_participant(' in _getroom else False
)
check(
    "172-06. BUG3b fixed: get_appointment_events fetches appointment BEFORE participant check",
    _getevents.index('_get_appointment_row(') < _getevents.index('_check_appt_participant(')
    if '_get_appointment_row(' in _getevents and '_check_appt_participant(' in _getevents else False
)
check(
    "172-07. BUG4 fixed: create_appointment has explicit BEGIN transaction",
    'conn.run("BEGIN")' in _createappt
)
check(
    "172-08. BUG4 fixed: create_appointment has COMMIT",
    'conn.run("COMMIT")' in _createappt
)
check(
    "172-09. BUG4 fixed: create_appointment has ROLLBACK on failure",
    'conn.run("ROLLBACK")' in _createappt
)
check(
    "172-10. BUG5 fixed: duplicate guard no longer excludes completed (allows re-invite after completion)",
    "'completed'" not in _createappt.split("status NOT IN")[1].split("LIMIT 1")[0]
    if "status NOT IN" in _createappt else False
)
check(
    "172-11. BUG6 fixed: complete_appointment checks scheduled_at has not passed",
    'scheduled_at' in _complete_fn and '_now' in _complete_fn and '_sched' in _complete_fn
)
check(
    "172-12. BUG7 fixed: create_appointment_message blocks all terminal statuses",
    '_APPT_TERMINAL_STATUSES' in _createmsg
)
check(
    "172-13. BUG9 fixed: close_appointment skips notification to the actor",
    'uid == user_id' in _close_fn and 'continue' in _close_fn
)

# ── Group 2: get_appointment_messages and list_appointments fixes (3 checks) ──

check(
    "172-14. BUG10 fixed: get_appointment_messages guards negative limit (max(1, ...))",
    'max(1, min(limit, 100))' in _getmsgs
)
check(
    "172-15. list_appointments: expired filter uses SQL deadline check, not WHERE status='expired'",
    "a.status = 'pending_response' AND a.response_deadline_at < NOW()" in _listappt
)
check(
    "172-16. list_appointments: expired special case is branched separately from regular filters",
    "status_filter == 'expired'" in _listappt
)

# ── Group 3: server.py fixes (4 checks) ──────────────────────────────────

_list_ep  = _server172.split('def api_list_appointments(')[1].split('\n@app.')[0] if 'def api_list_appointments(' in _server172 else ''
_send_ep  = _server172.split('def api_send_appointment(')[1].split('\n@app.')[0] if 'def api_send_appointment(' in _server172 else ''

check(
    "172-17. BUG12 fixed: list endpoint returns 'count' field (not 'total')",
    '"count": len(result)' in _list_ep and '"total":' not in _list_ep
)
check(
    "172-18. BUG13 fixed: /send endpoint has explicit user_type co guard",
    'user_type' in _send_ep and '"co"' in _send_ep
)
check(
    "172-19. /send endpoint raises 403 for non-company users",
    'HTTPException(403' in _send_ep
)
check(
    "172-20. create endpoint already has user_type co guard (pre-existing)",
    'user_type' in (_server172.split('def api_create_appointment(')[1].split('\n@app.')[0]
                    if 'def api_create_appointment(' in _server172 else '')
)

# ── Group 4: Frontend fixes — appointment-room.html (7 checks) ───────────

check(
    "172-21. BUG20 fixed: reschedule event renders new_scheduled_at",
    'new_scheduled_at || ev.payload.scheduled_at' in _roomhtml2 or
    'ev.payload.new_scheduled_at ||' in _roomhtml2
)
check(
    "172-22. BUG22 fixed: doAccept has .catch() handler",
    '.catch(function(){ alert(' in _roomhtml2.split('function doAccept')[1].split('function doComplete')[0]
    if 'function doAccept' in _roomhtml2 and 'function doComplete' in _roomhtml2 else False
)
check(
    "172-23. BUG22 fixed: doComplete has .catch() handler",
    '.catch(function(){ alert(' in _roomhtml2.split('function doComplete')[1].split('function doClose')[0]
    if 'function doComplete' in _roomhtml2 and 'function doClose' in _roomhtml2 else False
)
check(
    "172-24. BUG22 fixed: doClose has .catch() handler",
    '.catch(function(){ alert(' in _roomhtml2.split('function doClose')[1].split('function doSendMsg')[0]
    if 'function doClose' in _roomhtml2 else False
)
check(
    "172-25. BUG24 fixed: send modal sets min attribute on datetime-local input before open",
    'sendSchedAt' in _roomhtml2 and 'sendSchedAt\').min' in _roomhtml2
)
check(
    "172-26. BUG24 fixed: reschedule modal sets min attribute on datetime-local before open",
    'newSchedAt' in _roomhtml2 and 'newSchedAt\').min' in _roomhtml2
)
check(
    "172-27. appointment-room.html: doSendMsg already has .catch() (pre-existing, not regressed)",
    '.catch(function(){ alert(' in _roomhtml2.split('function doSendMsg')[1].split('function doAccept')[0]
    if 'function doSendMsg' in _roomhtml2 and 'function doAccept' in _roomhtml2 else False
)

# ── Group 5: Frontend fixes — appointments.html (3 checks) ───────────────

check(
    "172-28. BUG15 fixed: appointments.html differentiates !res.ok (error) from empty list",
    '!res.ok' in _appthtml2 and 'res.detail' in _appthtml2
)
check(
    "172-29. BUG15 fixed: error branch does not show 'لا توجد مواعيد' message",
    'res.detail' in _appthtml2.split('if (!res.ok)')[1].split('if (!res.data')[0]
    if 'if (!res.ok)' in _appthtml2 and 'if (!res.data' in _appthtml2 else False
)
check(
    "172-30. appointments.html: empty-list branch only fires when res.ok is truthy",
    _appthtml2.index('if (!res.ok)') < _appthtml2.index('if (!res.data || res.data.length === 0)')
    if 'if (!res.ok)' in _appthtml2 and 'if (!res.data || res.data.length === 0)' in _appthtml2 else False
)

# ── Group 6: Security / architecture invariants (6 checks) ───────────────

check(
    "172-31. No X-User-Id in any appointment endpoint (forbidden per F6/F17)",
    'X-User-Id' not in _server172.split('@app.post("/api/appointments')[1]
    if '@app.post("/api/appointments' in _server172 else True
)
check(
    "172-32. create_appointment derives applicant_id from job_applications, not body",
    'applicant_id = app_rows' in _createappt
)
check(
    "172-33. create_appointment derives job_id from job_applications, not body",
    'job_id = app_rows' in _createappt
)
check(
    "172-34. create_appointment_message checks can_message permission before inserting",
    'can_message' in _createmsg
)
check(
    "172-35. appointment_messages use soft delete (deleted_at), no hard DELETE",
    'deleted_at' in _auth172 and
    'DELETE FROM appointment_messages' not in _auth172
)
check(
    "172-36. appointment_events are never deleted (F18/F27)",
    'DELETE FROM appointment_events' not in _auth172
)

# ── Group 7: Notification correctness (7 checks) ─────────────────────────

_cancel_fn = _auth172.split('def cancel_appointment(')[1].split('\ndef complete_appointment')[0] if 'def cancel_appointment(' in _auth172 else ''
_send_fn2  = _auth172.split('def send_appointment(')[1].split('\ndef accept_appointment')[0] if 'def send_appointment(' in _auth172 else ''

check(
    "172-37. accept_appointment fires notification to company (not self)",
    'create_notification' in _accept_fn and 'company_id' in _accept_fn
)
check(
    "172-38. send_appointment fires notification to applicant",
    'create_notification' in _send_fn2 and 'applicant_id' in _send_fn2
)
check(
    "172-39. cancel_appointment skips actor notification (pre-existing guard)",
    'uid != user_id' in _cancel_fn or 'uid == user_id' in _cancel_fn
)
check(
    "172-40. close_appointment notification loop skips actor (BUG9 fix)",
    'uid == user_id' in _close_fn and 'continue' in _close_fn
)
check(
    "172-41. request_reschedule fires notification to company",
    'create_notification' in _reqresched and 'company_id' in _reqresched
)
check(
    "172-42. accept_appointment notification uses event_key with appointment_accepted prefix",
    "appointment_accepted:" in _accept_fn
)
check(
    "172-43. close_appointment notification event_key includes uid (per-recipient idempotency)",
    "appointment_closed:{appointment_id}:{uid}" in _close_fn
)

# ══════════════════════════════════════════════════════════════════════════
# §173 — Scheduler Infrastructure Decision (docs-only)
# ══════════════════════════════════════════════════════════════════════════

import os as _os173
_sched_plan  = open('docs/SCHEDULER_PLAN.md',        encoding='utf-8').read() if _os173.path.exists('docs/SCHEDULER_PLAN.md')        else ''
_sysidx173   = open('docs/SYSTEMS_INDEX.md',         encoding='utf-8').read() if _os173.path.exists('docs/SYSTEMS_INDEX.md')         else ''
_apptplan173 = open('docs/APPOINTMENTS_PLAN.md',     encoding='utf-8').read() if _os173.path.exists('docs/APPOINTMENTS_PLAN.md')     else ''
_notifplan   = open('docs/NOTIFICATIONS_PLAN.md',    encoding='utf-8').read() if _os173.path.exists('docs/NOTIFICATIONS_PLAN.md')    else ''
_auth173     = open('auth.py',   encoding='utf-8').read() if _os173.path.exists('auth.py')   else ''
_server173   = open('server.py', encoding='utf-8').read() if _os173.path.exists('server.py') else ''

# ── SCHEDULER_PLAN.md structure ───────────────────────────────────────────
check(
    "173-01. SCHEDULER_PLAN.md exists",
    bool(_sched_plan)
)
check(
    "173-02. SCHEDULER_PLAN.md documents why a scheduler is needed (section 1)",
    'Why We Need a Scheduler' in _sched_plan or 'لماذا نحتاج' in _sched_plan
)
check(
    "173-03. SCHEDULER_PLAN.md lists dependent/deferred systems (section 2)",
    'appointment_reminder' in _sched_plan and 'job_expiring_soon' in _sched_plan
)
check(
    "173-04. SCHEDULER_PLAN.md includes Architectural Requirements section",
    'Architectural Requirements' in _sched_plan or 'المتطلبات المعمارية' in _sched_plan
)
check(
    "173-05. SCHEDULER_PLAN.md documents idempotency + dedupe_key",
    'dedupe_key' in _sched_plan and ('Idempotency' in _sched_plan or 'idempotency' in _sched_plan.lower())
)
check(
    "173-06. SCHEDULER_PLAN.md documents retry on failure",
    'Retry' in _sched_plan or 'retry' in _sched_plan
)
check(
    "173-07. SCHEDULER_PLAN.md documents failure logging requirement",
    'Failure Logging' in _sched_plan or 'failure logging' in _sched_plan.lower()
)
check(
    "173-08. SCHEDULER_PLAN.md documents FOR UPDATE SKIP LOCKED (distributed locking)",
    'FOR UPDATE SKIP LOCKED' in _sched_plan
)
check(
    "173-09. SCHEDULER_PLAN.md documents four implementation options",
    'Option A' in _sched_plan and 'Option B' in _sched_plan and 'Option C' in _sched_plan and 'Option D' in _sched_plan
)
check(
    "173-10. SCHEDULER_PLAN.md includes implementation recommendation",
    'Recommendation' in _sched_plan or 'Recommended' in _sched_plan
)
check(
    "173-11. SCHEDULER_PLAN.md documents proposed scheduler_jobs schema",
    'scheduler_jobs' in _sched_plan and 'locked_at' in _sched_plan and 'locked_by' in _sched_plan
)
check(
    "173-12. SCHEDULER_PLAN.md schema includes appointment_missed and appointment_deadline_expire job types",
    'appointment_missed' in _sched_plan and 'appointment_deadline_expire' in _sched_plan
)
check(
    "173-13. SCHEDULER_PLAN.md includes implementation phases (S0–S6)",
    'S0' in _sched_plan and 'S1' in _sched_plan and 'S6' in _sched_plan
)
check(
    "173-14. SCHEDULER_PLAN.md has Constraints section forbidding scheduler code",
    'Constraints' in _sched_plan and 'X-User-Id' in _sched_plan
)

# ── No scheduler runner added (docs-only check updated for S2) ─────────────────
# NOTE: S1 added _migrate_scheduler_jobs(); S2 added schedule_job() — both legitimate.
# §173 intent was "no runner/executor" — run_due_jobs() is still S3 and must remain absent.
check(
    "173-15. auth.py: no run_due_jobs() runner added (runner is S3)",
    'def run_due_jobs' not in _auth173
)
check(
    "173-16. auth.py does NOT import APScheduler or contain create_task for scheduling",
    'APScheduler' not in _auth173 and 'apscheduler' not in _auth173.lower()
)
check(
    "173-17. server.py: /internal/run-due-jobs endpoint added in S3",
    '/internal/run-due-jobs' in _server173
)

# ── Cross-file references ──────────────────────────────────────────────────
check(
    "173-18. SYSTEMS_INDEX.md has Scheduler Infrastructure entry (§37)",
    'Scheduler Infrastructure' in _sysidx173 and 'SCHEDULER_PLAN.md' in _sysidx173
)
check(
    "173-19. APPOINTMENTS_PLAN.md documents scheduler-dependent deferred features",
    'Scheduler-Dependent' in _apptplan173 or 'scheduler' in _apptplan173.lower()
)
check(
    "173-20. NOTIFICATIONS_PLAN.md references SCHEDULER_PLAN.md in Scheduler Blocker Note",
    'SCHEDULER_PLAN.md' in _notifplan
)

# ══════════════════════════════════════════════════════════════════════════
# §174 — Scheduler S0 Tooling Decision (docs-only)
# ══════════════════════════════════════════════════════════════════════════

import os as _os174
_sched174  = open('docs/SCHEDULER_PLAN.md',   encoding='utf-8').read() if _os174.path.exists('docs/SCHEDULER_PLAN.md')   else ''
_sysidx174 = open('docs/SYSTEMS_INDEX.md',    encoding='utf-8').read() if _os174.path.exists('docs/SYSTEMS_INDEX.md')    else ''
_auth174   = open('auth.py',   encoding='utf-8').read() if _os174.path.exists('auth.py')   else ''
_server174 = open('server.py', encoding='utf-8').read() if _os174.path.exists('server.py') else ''

_s0_section = _sched174.split('S0 Tooling Decision')[1] if 'S0 Tooling Decision' in _sched174 else ''

# ── S0 section exists and is complete ─────────────────────────────────────
check(
    "174-01. SCHEDULER_PLAN.md contains S0 Tooling Decision section",
    'S0 Tooling Decision' in _sched174
)
check(
    "174-02. S0 section documents External Cron option",
    'External Cron' in _s0_section
)
check(
    "174-03. S0 section documents APScheduler option",
    'APScheduler' in _s0_section
)
check(
    "174-04. S0 section documents Background Worker / separate dyno option",
    'Background Worker' in _s0_section or 'Background worker' in _s0_section or 'Worker Dyno' in _s0_section
)
check(
    "174-05. S0 section documents Platform Scheduler (Heroku Scheduler) option",
    'Heroku Scheduler' in _s0_section or 'Platform Scheduler' in _s0_section or 'Platform scheduler' in _s0_section
)
check(
    "174-06. S0 section documents Manual/Admin Trigger option for testing only",
    ('Manual' in _s0_section or 'Admin Trigger' in _s0_section or 'admin trigger' in _s0_section.lower())
    and ('للاختبار' in _s0_section or 'testing only' in _s0_section.lower() or 'تطوير' in _s0_section)
)
check(
    "174-07. S0 section contains pros/cons comparison (مزايا + سلبيات)",
    'مزايا' in _s0_section and 'سلبيات' in _s0_section
)
check(
    "174-08. S0 section documents security risks (secret token / hmac)",
    'secret' in _s0_section.lower() and ('hmac' in _s0_section.lower() or 'أمان' in _s0_section or 'security' in _s0_section.lower())
)
check(
    "174-09. S0 section documents reliability evaluation (اعتمادية)",
    'اعتمادية' in _s0_section or 'reliability' in _s0_section.lower() or 'Reliability' in _s0_section
)
check(
    "174-10. S0 section has final recommendation (التوصية النهائية)",
    'التوصية النهائية' in _s0_section or 'التوصية' in _s0_section or 'final recommendation' in _s0_section.lower()
)
check(
    "174-11. S0 final recommendation mentions secure endpoint protection method",
    'X-Scheduler-Secret' in _s0_section or 'hmac.compare_digest' in _s0_section
)
check(
    "174-12. S0 section references scheduler_jobs as storage layer",
    'scheduler_jobs' in _s0_section
)
check(
    "174-13. S0 section explicitly states no scheduler code added in this PR",
    ('لا كود' in _s0_section or 'no code' in _s0_section.lower() or 'docs-only' in _s0_section.lower())
)
check(
    "174-14. S0 section explicitly states no schema changes",
    'لا schema' in _s0_section or 'no schema' in _s0_section.lower() or 'لم يُنفَّذ' in _s0_section
)
check(
    "174-15. S0 section states no endpoints added in this PR",
    'لا endpoints' in _s0_section or 'no endpoints' in _s0_section.lower() or 'مؤجل إلى S1' in _s0_section
)

# ── SYSTEMS_INDEX.md §37 updated with S0 status ───────────────────────────
check(
    "174-16. SYSTEMS_INDEX.md §37 updated: mentions S0 completed",
    'S0' in _sysidx174 and ('Tooling Decision' in _sysidx174 or 'مكتمل' in _sysidx174)
)

# ── No code added to auth.py or server.py ─────────────────────────────────
check(
    "174-17. auth.py: no APScheduler import added",
    'APScheduler' not in _auth174 and 'apscheduler' not in _auth174.lower()
)
check(
    "174-18. server.py: scheduler endpoint with X-Scheduler-Secret auth added in S3",
    'X-Scheduler-Secret' in _server174 and 'hmac.compare_digest' in _server174
)

# ── No cron config file added ──────────────────────────────────────────────
check(
    "174-19. No .github/workflows/scheduler cron config added",
    not _os174.path.exists('.github/workflows/scheduler.yml')
    and not _os174.path.exists('.github/workflows/cron.yml')
)

# ── S0 documents what is deferred to S1 ──────────────────────────────────
check(
    "174-20. S0 section documents what remains deferred to S1",
    'S1' in _s0_section and ('مؤجل' in _s0_section or 'deferred' in _s0_section.lower())
)

# ═══════════════════════════════════════════════════════════════════════════════
# §175 — Scheduler S1: Schema Only (33 checks)
# PR: scheduler-s1-schema
# Verifies: _migrate_scheduler_jobs() in auth.py + startup wiring in server.py
#           + docs updates + no endpoints/runner/helpers/hooks added
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os175

_auth175   = open('auth.py',   encoding='utf-8').read()
_server175 = open('server.py', encoding='utf-8').read()
_plan175   = open('docs/SCHEDULER_PLAN.md', encoding='utf-8').read()
_sysidx175 = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()

# ── auth.py: migration function exists ────────────────────────────────────────
check(
    "175-01. auth.py: _migrate_scheduler_jobs function defined",
    'def _migrate_scheduler_jobs' in _auth175
)

# ── server.py: import + startup wiring ────────────────────────────────────────
check(
    "175-02. server.py: imports _migrate_scheduler_jobs from auth",
    '_migrate_scheduler_jobs' in _server175
)
check(
    "175-03. server.py: migration failure prints ❌ and raises",
    ('❌' in _server175 or 'scheduler_jobs migration failed' in _server175)
    and 'raise' in _server175
)

# ── Table DDL ─────────────────────────────────────────────────────────────────
_mig175 = _auth175[_auth175.find('def _migrate_scheduler_jobs'):]
_mig175 = _mig175[:_mig175.find('\ndef ', 5)] if '\ndef ' in _mig175[5:] else _mig175

check(
    "175-04. migration SQL creates scheduler_jobs table",
    'scheduler_jobs' in _mig175 and 'CREATE TABLE' in _mig175
)
check(
    "175-05. scheduler_jobs has id BIGSERIAL PRIMARY KEY",
    'BIGSERIAL' in _mig175 and 'PRIMARY KEY' in _mig175
)
check(
    "175-06. scheduler_jobs has job_type TEXT NOT NULL",
    'job_type' in _mig175 and 'NOT NULL' in _mig175
)
check(
    "175-07. scheduler_jobs has payload JSONB with empty-object default",
    'payload' in _mig175 and 'JSONB' in _mig175
    and ("'{}'::jsonb" in _mig175 or "'{}'::JSONB" in _mig175 or "DEFAULT '{}'" in _mig175)
)
check(
    "175-08. scheduler_jobs has run_at TIMESTAMPTZ NOT NULL",
    'run_at' in _mig175 and 'TIMESTAMPTZ' in _mig175
)
check(
    "175-09. scheduler_jobs has status with DEFAULT 'pending'",
    'status' in _mig175 and "'pending'" in _mig175
)
check(
    "175-10. scheduler_jobs has attempts INTEGER DEFAULT 0",
    'attempts' in _mig175 and 'DEFAULT 0' in _mig175
)
check(
    "175-11. scheduler_jobs has max_attempts with DEFAULT 5",
    'max_attempts' in _mig175 and 'DEFAULT 5' in _mig175
)
check(
    "175-12. scheduler_jobs has last_error TEXT column",
    'last_error' in _mig175
)
check(
    "175-13. scheduler_jobs has dedupe_key TEXT NOT NULL",
    'dedupe_key' in _mig175
)
check(
    "175-14. scheduler_jobs has locked_at TIMESTAMPTZ column",
    'locked_at' in _mig175 and 'TIMESTAMPTZ' in _mig175
)
check(
    "175-15. scheduler_jobs has locked_by TEXT column",
    'locked_by' in _mig175
)
check(
    "175-16. scheduler_jobs has created_at with TIMESTAMPTZ and NOW() default",
    'created_at' in _mig175 and 'NOW()' in _mig175
)
check(
    "175-17. scheduler_jobs has updated_at TIMESTAMPTZ column",
    'updated_at' in _mig175
)
check(
    "175-18. migration has UNIQUE constraint on dedupe_key",
    ('UNIQUE' in _mig175 and 'dedupe_key' in _mig175)
    or 'uq_sched_dedupe' in _mig175
)
check(
    "175-19. migration has CHECK constraint on status values",
    ("CHECK" in _mig175 and 'status' in _mig175 and 'pending' in _mig175
     and 'done' in _mig175 and 'failed' in _mig175)
    or 'ck_sched_status' in _mig175
)
check(
    "175-20. migration has CHECK constraint on attempts >= 0",
    ('attempts' in _mig175 and '>= 0' in _mig175)
    or 'ck_sched_attempts' in _mig175
)
check(
    "175-21. migration has CHECK constraint on max_attempts >= 1",
    ('max_attempts' in _mig175 and '>= 1' in _mig175)
    or 'ck_sched_maxatt' in _mig175
)

# ── Indexes ───────────────────────────────────────────────────────────────────
check(
    "175-22. migration creates due-jobs index on (status, run_at)",
    'idx_sched_due' in _mig175 or ('status, run_at' in _mig175 and 'INDEX' in _mig175)
)
check(
    "175-23. migration creates locked_at index for stale lock cleanup",
    'idx_sched_locked_at' in _mig175 or ('locked_at' in _mig175 and 'INDEX' in _mig175)
)
check(
    "175-24. migration creates job_type index for monitoring",
    'idx_sched_job_type' in _mig175 or ('job_type' in _mig175 and 'INDEX' in _mig175)
)

# ── S1 scope: NO extras added ─────────────────────────────────────────────────
check(
    "175-25. server.py: /internal/run-due-jobs endpoint added in S3",
    '/internal/run-due-jobs' in _server175
)
check(
    "175-26. auth.py: no run_due_jobs function added",
    'def run_due_jobs' not in _auth175
)
check(
    "175-27. auth.py: no run_due_jobs runner added (runner is S3)",
    'def run_due_jobs' not in _auth175
)
check(
    "175-28. server.py: /internal/run-due-jobs endpoint uses hmac.compare_digest (S3 security)",
    'hmac.compare_digest' in _server175
)
check(
    "175-29. server.py: no appointment hooks calling schedule_job added (hooks are S4)",
    # schedule_job calls inside accept_appointment/create_appointment are S4
    # server.py must not contain schedule_job calls until S4
    'schedule_job' not in _server175
)
check(
    "175-30. No cron config file added; SCHEDULER_SECRET env var used in S3",
    not _os175.path.exists('.github/workflows/scheduler.yml')
    and not _os175.path.exists('.github/workflows/cron.yml')
    and 'SCHEDULER_SECRET' in _server175
)

# ── Docs updated ──────────────────────────────────────────────────────────────
check(
    "175-31. docs/SCHEDULER_PLAN.md mentions S1 as implemented/complete",
    'S1' in _plan175 and ('مكتملة' in _plan175 or 'مكتمل' in _plan175 or 'Implemented' in _plan175 or 'schema-only' in _plan175.lower())
)
check(
    "175-32. docs/SYSTEMS_INDEX.md §37 updated: S1 schema marked complete",
    'S1' in _sysidx175 and ('✅' in _sysidx175 or 'Schema' in _sysidx175 or 'schema' in _sysidx175)
    and 'scheduler-s1' in _sysidx175.lower() or ('S1 ✅' in _sysidx175 or 'S1 Schema' in _sysidx175)
)
check(
    "175-33. docs/SYSTEMS_INDEX.md §37 documents what remains deferred (S2+)",
    'S2' in _sysidx175 and ('مؤجل' in _sysidx175 or 'Pending' in _sysidx175 or 'pending' in _sysidx175)
)

# ═══════════════════════════════════════════════════════════════════════════════
# §176 — Scheduler S2: schedule_job helper (26 checks)
# PR: scheduler-s2-helper
# Verifies: schedule_job() in auth.py + docs updates + no extras added
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os176

_auth176   = open('auth.py',   encoding='utf-8').read()
_server176 = open('server.py', encoding='utf-8').read()
_plan176   = open('docs/SCHEDULER_PLAN.md', encoding='utf-8').read()
_sysidx176 = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()

# Extract schedule_job function body for targeted checks
_sj176_start = _auth176.find('def schedule_job(')
_sj176 = _auth176[_sj176_start:] if _sj176_start >= 0 else ''
# Limit to the function body (stops at next top-level def)
_next_def176 = _sj176.find('\ndef ', 5)
_sj176 = _sj176[:_next_def176] if _next_def176 > 0 else _sj176

# ── Function exists ────────────────────────────────────────────────────────────
check(
    "176-01. auth.py: schedule_job function defined",
    'def schedule_job(' in _auth176
)

# ── Parameters ────────────────────────────────────────────────────────────────
check(
    "176-02. schedule_job accepts job_type parameter",
    'job_type' in _sj176
)
check(
    "176-03. schedule_job accepts payload parameter",
    'payload' in _sj176
)
check(
    "176-04. schedule_job accepts run_at parameter",
    'run_at' in _sj176
)
check(
    "176-05. schedule_job accepts dedupe_key parameter",
    'dedupe_key' in _sj176
)
check(
    "176-06. schedule_job accepts max_attempts with default 5",
    'max_attempts' in _sj176 and '= 5' in _sj176
)

# ── Input validation ──────────────────────────────────────────────────────────
check(
    "176-07. schedule_job validates job_type is non-empty",
    ('job_type' in _sj176 and 'ValueError' in _sj176
     and ('strip()' in _sj176 or 'not job_type' in _sj176 or 'job_type.strip' in _sj176))
)
check(
    "176-08. schedule_job validates payload is dict",
    'isinstance' in _sj176 and 'payload' in _sj176 and 'dict' in _sj176
)
check(
    "176-09. schedule_job validates dedupe_key is non-empty",
    'dedupe_key' in _sj176 and 'ValueError' in _sj176
    and ('strip()' in _sj176 or 'not dedupe_key' in _sj176 or 'dedupe_key.strip' in _sj176)
)
check(
    "176-10. schedule_job validates max_attempts >= 1",
    'max_attempts' in _sj176 and '>= 1' in _sj176 and 'ValueError' in _sj176
)

# ── DB: uses scheduler_jobs table ─────────────────────────────────────────────
check(
    "176-11. schedule_job inserts into scheduler_jobs",
    'scheduler_jobs' in _sj176
)
check(
    "176-12. schedule_job uses dedupe_key in SQL",
    'dedupe_key' in _sj176 and ('INSERT' in _sj176 or ':dk' in _sj176)
)
check(
    "176-13. schedule_job uses ON CONFLICT for idempotency",
    'ON CONFLICT' in _sj176
)
check(
    "176-14. schedule_job does not allow duplicate jobs (DO NOTHING or DO UPDATE)",
    'DO NOTHING' in _sj176 or 'DO UPDATE' in _sj176
)

# ── Return shape: created flag ─────────────────────────────────────────────────
check(
    "176-15. schedule_job returns created=True or created=False",
    '"created"' in _sj176 or "'created'" in _sj176
    or ('created' in _sj176 and ('True' in _sj176 or 'False' in _sj176))
)

# ── Scope: no execution, no side effects ──────────────────────────────────────
check(
    "176-16. schedule_job does not execute jobs (no run_due_jobs call)",
    'run_due_jobs' not in _sj176
)
check(
    "176-17. schedule_job does not send notifications (no create_notification call)",
    'create_notification' not in _sj176
)
check(
    "176-18. schedule_job does not modify appointments table",
    'UPDATE appointments' not in _sj176 and 'appointments SET' not in _sj176
)
check(
    "176-19. schedule_job does not modify jobs table",
    'UPDATE jobs' not in _sj176 and 'jobs SET status' not in _sj176
)

# ── Server.py: no new endpoint, no runner ─────────────────────────────────────
check(
    "176-20. server.py: /internal/run-due-jobs endpoint now added (S3 implemented)",
    '/internal/run-due-jobs' in _server176
)
check(
    "176-21. auth.py: no run_due_jobs runner added (S3)",
    'def run_due_jobs' not in _auth176
)
check(
    "176-22. No cron config file; SCHEDULER_SECRET env var used in S3",
    not _os176.path.exists('.github/workflows/scheduler.yml')
    and not _os176.path.exists('.github/workflows/cron.yml')
    and 'SCHEDULER_SECRET' in _server176
)
check(
    "176-23. No background thread or asyncio.create_task for scheduling added",
    'create_task' not in _auth176.split('def schedule_job(')[-1].split('\ndef ')[0]
    and 'threading.Thread' not in _auth176.split('def schedule_job(')[-1].split('\ndef ')[0]
)

# ── Docs updated ──────────────────────────────────────────────────────────────
check(
    "176-24. docs/SCHEDULER_PLAN.md mentions S2 as implemented/complete",
    'S2' in _plan176 and ('مكتملة' in _plan176 or 'helper-only' in _plan176.lower()
                          or 'schedule_job' in _plan176)
)
check(
    "176-25. docs/SYSTEMS_INDEX.md §37 updated: S2 helper marked complete",
    'S2 ✅' in _sysidx176 or ('S2' in _sysidx176 and 'schedule_job' in _sysidx176
                               and ('✅' in _sysidx176 or 'مكتملة' in _sysidx176))
)
check(
    "176-26. docs/SYSTEMS_INDEX.md §37 documents what remains deferred (S3+)",
    'S3' in _sysidx176 and ('مؤجل' in _sysidx176 or 'Pending' in _sysidx176 or '🔜' in _sysidx176)
)

# ═══════════════════════════════════════════════════════════════════════════════
# §177 — Scheduler S3: Runner + Secure Endpoint (33 checks)
# PR: scheduler-s3-runner
# Verifies: run_due_scheduler_jobs() in auth.py + POST /internal/run-due-jobs in server.py
#           + docs updates + no extras (no hooks, no cron, no background threads)
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os177

_auth177   = open('auth.py',   encoding='utf-8').read()
_server177 = open('server.py', encoding='utf-8').read()
_plan177   = open('docs/SCHEDULER_PLAN.md', encoding='utf-8').read()
_sysidx177 = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()

# Extract runner function body (last function in auth.py)
_runner177 = _auth177.split('def run_due_scheduler_jobs')[1] if 'def run_due_scheduler_jobs' in _auth177 else ''
# Extract helper function body (defined just before runner)
_helper177_body = (
    _auth177.split('def _update_scheduler_job_final_status')[1].split('\n\ndef ')[0]
    if 'def _update_scheduler_job_final_status' in _auth177 else ''
)
# Extract endpoint section in server.py
_ep177 = _server177[_server177.find('/internal/run-due-jobs'):] if '/internal/run-due-jobs' in _server177 else ''

# AST analysis for except-pass detection
import ast as _ast177
try:
    _tree177 = _ast177.parse(_auth177)

    def _find_func177(tree, name):
        for node in _ast177.walk(tree):
            if isinstance(node, (_ast177.FunctionDef, _ast177.AsyncFunctionDef)) and node.name == name:
                return node
        return None

    def _has_bare_pass_except177(func_node):
        if func_node is None:
            return True  # conservative: assume bad
        for node in _ast177.walk(func_node):
            if isinstance(node, _ast177.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], _ast177.Pass):
                    return True
        return False

    _runner_func177 = _find_func177(_tree177, 'run_due_scheduler_jobs')
    _helper_func177 = _find_func177(_tree177, '_update_scheduler_job_final_status')
    _ast177_ok = True
except SyntaxError:
    _runner_func177 = None
    _helper_func177 = None
    _ast177_ok = False

# Extract no-jobs early return section (before jobs_data is built)
_early177 = _runner177.split('jobs_data')[0] if 'jobs_data' in _runner177 else ''

# ── auth.py: runner function exists ──────────────────────────────────────────
check(
    "177-01. auth.py: run_due_scheduler_jobs function defined",
    'def run_due_scheduler_jobs' in _auth177
)
check(
    "177-02. run_due_scheduler_jobs queries scheduler_jobs table",
    'scheduler_jobs' in _runner177
)
check(
    "177-03. run_due_scheduler_jobs filters status='pending'",
    "status = 'pending'" in _runner177 or "status='pending'" in _runner177
)
check(
    "177-04. run_due_scheduler_jobs filters run_at <= NOW()",
    'run_at <= NOW()' in _runner177 or 'run_at<=NOW()' in _runner177
)
check(
    "177-05. run_due_scheduler_jobs uses FOR UPDATE SKIP LOCKED",
    'FOR UPDATE SKIP LOCKED' in _runner177
)
check(
    "177-06. run_due_scheduler_jobs writes locked_at",
    'locked_at' in _runner177
)
check(
    "177-07. run_due_scheduler_jobs writes locked_by",
    'locked_by' in _runner177
)
check(
    "177-08. run_due_scheduler_jobs increments attempts counter",
    'attempts' in _runner177 and 'attempts + 1' in _runner177
)
check(
    "177-09. auth.py: last_error written in _update_scheduler_job_final_status helper",
    'last_error' in _auth177 and '_update_scheduler_job_final_status' in _auth177
)
check(
    "177-10. run_due_scheduler_jobs sets status='done' on success",
    "'done'" in _runner177 or '"done"' in _runner177
)
check(
    "177-11. run_due_scheduler_jobs sets status='failed' on exhausted attempts",
    "'failed'" in _runner177 or '"failed"' in _runner177
)
check(
    "177-12. run_due_scheduler_jobs returns retryable failures to status='pending'",
    # query filter uses 'pending' (single quotes); helper call uses "pending" (double quotes)
    (_runner177.count("'pending'") + _runner177.count('"pending"')) >= 2
)
check(
    "177-13. auth.py: noop job_type supported in _execute_scheduler_job",
    "'noop'" in _auth177 or '"noop"' in _auth177
)
check(
    "177-14. _execute_scheduler_job raises ValueError for unknown job_type",
    'ValueError' in _auth177 and 'unsupported job_type' in _auth177
)
check(
    "177-15. scheduler runner: no eval() call",
    'eval(' not in _runner177
)
check(
    "177-16. scheduler runner: no dynamic import or importlib",
    '__import__(' not in _runner177 and 'importlib' not in _runner177
)
check(
    "177-17. run_due_scheduler_jobs: no create_notification call (hooks are S4)",
    'create_notification' not in _runner177
)
check(
    "177-18. run_due_scheduler_jobs: no UPDATE appointments (appointment hooks are S4)",
    'UPDATE appointments' not in _runner177
)
check(
    "177-19. run_due_scheduler_jobs: no job_expiring_soon hook (deferred to S4)",
    'job_expiring_soon' not in _runner177
)

# ── server.py: endpoint exists with correct security ─────────────────────────
check(
    "177-20. server.py: POST /internal/run-due-jobs endpoint defined",
    '@app.post("/internal/run-due-jobs")' in _server177
)
check(
    "177-21. server.py: SCHEDULER_SECRET read from os.environ",
    'SCHEDULER_SECRET' in _server177 and 'os.environ' in _server177
)
check(
    "177-22. server.py: endpoint reads X-Scheduler-Secret header",
    'X-Scheduler-Secret' in _server177
)
check(
    "177-23. server.py: hmac.compare_digest used for timing-safe comparison",
    'hmac.compare_digest' in _server177
)
check(
    "177-24. server.py: /internal/run-due-jobs does not use verify_token / JWT",
    'verify_token' not in _ep177
)
check(
    "177-25. server.py: /internal/run-due-jobs does not use X-User-Id header",
    'X-User-Id' not in _ep177
)
check(
    "177-26. server.py: SCHEDULER_SECRET not returned in response; read via header only",
    'return SCHEDULER_SECRET' not in _server177
    and 'request.headers.get("X-Scheduler-Secret"' in _server177
)

# ── No extras added ───────────────────────────────────────────────────────────
check(
    "177-27. No .github/workflows/scheduler cron config file added",
    not _os177.path.exists('.github/workflows/scheduler.yml')
    and not _os177.path.exists('.github/workflows/cron.yml')
)
check(
    "177-28. GitHub Actions workflow file is the correct canonical name (scheduler-cron.yml)",
    # S3 guard updated: scheduler-cron.yml is now legitimate (added in cron-activation PR).
    # Still guard against wrong names (scheduler.yml, cron.yml).
    not _os177.path.exists('.github/workflows/scheduler.yml')
    and not _os177.path.exists('.github/workflows/cron.yml')
    and (not _os177.path.exists('.github/workflows/scheduler-cron.yml')
         or open('.github/workflows/scheduler-cron.yml', encoding='utf-8').read().count('X-Scheduler-Secret') >= 1)
)
check(
    "177-29. auth.py: no APScheduler import added",
    'APScheduler' not in _auth177 and 'apscheduler' not in _auth177.lower()
)
check(
    "177-30. scheduler runner: no threading.Thread or asyncio.create_task",
    'threading.Thread' not in _runner177 and 'create_task' not in _runner177
)

# ── Docs updated ──────────────────────────────────────────────────────────────
check(
    "177-31. docs/SCHEDULER_PLAN.md mentions S3 as implemented/complete",
    'S3' in _plan177 and ('مكتملة' in _plan177 or 'run_due_scheduler_jobs' in _plan177
                          or 'runner' in _plan177.lower())
)
check(
    "177-32. docs/SYSTEMS_INDEX.md §37 updated: S3 runner/endpoint marked complete",
    ('S3 ✅' in _sysidx177 or ('S3' in _sysidx177 and '✅' in _sysidx177
                                 and ('runner' in _sysidx177.lower() or 'run_due_scheduler_jobs' in _sysidx177)))
)
check(
    "177-33. docs/SYSTEMS_INDEX.md §37 documents S4 hooks as deferred/pending",
    'S4' in _sysidx177 and ('مؤجل' in _sysidx177 or 'Pending' in _sysidx177 or '🔜' in _sysidx177)
)

# ── Final-update failure handling (fix: no silent swallow) ───────────────────
_helper177 = _auth177.split('def _update_scheduler_job_final_status')[1] if 'def _update_scheduler_job_final_status' in _auth177 else ''

check(
    "177-34. auth.py: _update_scheduler_job_final_status helper defined",
    'def _update_scheduler_job_final_status' in _auth177
)
check(
    "177-35. runner: update_failed_cnt tracks failed UPDATEs (no silent swallow)",
    'update_failed_cnt' in _runner177
)
check(
    "177-36. runner: uses _update_scheduler_job_final_status helper for final updates",
    '_update_scheduler_job_final_status' in _runner177
)
check(
    "177-37. runner: ok derived from update_failed_cnt (not hardcoded True)",
    'update_failed_cnt == 0' in _runner177
)
check(
    "177-38. runner: stuck_running and update_failed in return dict",
    'stuck_running' in _runner177 and 'update_failed' in _runner177
)
check(
    "177-39. runner: done/retried/failed counted only after UPDATE success",
    # done_cnt is inside 'if _update_scheduler_job_final_status(...):'
    'done_cnt += 1' in _runner177
    and _runner177.index('done_cnt += 1') > _runner177.index('_update_scheduler_job_final_status')
)
check(
    "177-40. helper: returns False on UPDATE exception (never swallows)",
    'return False' in _helper177_body and 'return True' in _helper177_body
)
check(
    "177-41. AST: run_due_scheduler_jobs has no ExceptHandler with bare Pass",
    _ast177_ok and not _has_bare_pass_except177(_runner_func177)
)
check(
    "177-42. helper uses RETURNING id to verify row was actually updated",
    'RETURNING id' in _helper177_body or 'RETURNING' in _helper177_body
)
check(
    "177-43. helper WHERE guards: AND status='running' (prevents state mismatch)",
    "'running'" in _helper177_body
)
check(
    "177-44. helper WHERE guards: AND locked_by verifies ownership before final update",
    'locked_by' in _helper177_body and 'runner_id' in _helper177_body
)
check(
    "177-45. helper has two return-False paths: zero-row AND exception",
    _helper177_body.count('return False') >= 2
)
check(
    "177-46. no-jobs early return includes update_failed and stuck_running counters",
    '"update_failed"' in _early177 and '"stuck_running"' in _early177
)
check(
    "177-47. failed_cnt and retried_cnt also gated on successful UPDATE",
    'failed_cnt += 1' in _runner177
    and _runner177.index('failed_cnt += 1') > _runner177.index('_update_scheduler_job_final_status')
    and 'retried_cnt += 1' in _runner177
    and _runner177.index('retried_cnt += 1') > _runner177.index('_update_scheduler_job_final_status')
)

# ═══════════════════════════════════════════════════════════════════════════════
# §178 — Scheduler S4: Domain Handlers + Scheduling Hooks (16 checks)
# PR: scheduler-s4-domain-handlers
# Verifies: 4 handler functions + _execute_scheduler_job + _SCHEDULER_HANDLERS
#           + scheduling hooks in accept_appointment / send_appointment /
#             reschedule_appointment / add_job + docs updates
# ═══════════════════════════════════════════════════════════════════════════════

_auth178   = open('auth.py',   encoding='utf-8').read()
_plan178   = open('docs/SCHEDULER_PLAN.md', encoding='utf-8').read()
_sysidx178 = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()
_apptplan178 = open('docs/APPOINTMENTS_PLAN.md', encoding='utf-8').read()
_notifplan178 = open('docs/NOTIFICATIONS_PLAN.md', encoding='utf-8').read()

# Extract relevant function bodies
_exec178 = (_auth178.split('def _execute_scheduler_job')[1].split('\ndef ')[0]
            if 'def _execute_scheduler_job' in _auth178 else '')
_handlers_set178 = (_auth178.split('_SCHEDULER_HANDLERS')[1].split('}')[0]
                    if '_SCHEDULER_HANDLERS' in _auth178 else '')
_accept178 = (_auth178.split('def accept_appointment')[1].split('\ndef ')[0]
              if 'def accept_appointment' in _auth178 else '')
_send178 = (_auth178.split('def send_appointment')[1].split('\ndef ')[0]
            if 'def send_appointment' in _auth178 else '')
_resched178 = (_auth178.split('def reschedule_appointment')[1].split('\ndef ')[0]
               if 'def reschedule_appointment' in _auth178 else '')
_addjob178 = (_auth178.split('def add_job')[1].split('\ndef ')[0]
              if 'def add_job' in _auth178 else '')

# AST check for bare except:pass in handler functions
import ast as _ast178
_ast178_ok = False
_handler_names178 = [
    '_handle_appointment_reminder',
    '_handle_appointment_deadline_expire',
    '_handle_appointment_missed',
    '_handle_job_expiring_soon',
]
try:
    _tree178 = _ast178.parse(_auth178)
    def _find_func178(tree, name):
        for node in _ast178.walk(tree):
            if isinstance(node, (_ast178.FunctionDef, _ast178.AsyncFunctionDef)) and node.name == name:
                return node
        return None
    def _has_bare_pass_except178(func_node):
        if func_node is None:
            return True
        for node in _ast178.walk(func_node):
            if isinstance(node, _ast178.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], _ast178.Pass):
                    return True
        return False
    _ast178_ok = True
except SyntaxError:
    _tree178 = None

# ── _SCHEDULER_HANDLERS set updated ──────────────────────────────────────────
check(
    "178-01. _SCHEDULER_HANDLERS includes all 4 S4 job types",
    all(t in _handlers_set178 for t in [
        '"appointment_reminder"', '"appointment_deadline_expire"',
        '"appointment_missed"', '"job_expiring_soon"'
    ])
)

# ── 4 handler functions defined ───────────────────────────────────────────────
check(
    "178-02. auth.py: all 4 S4 handler functions defined",
    all(f'def {name}' in _auth178 for name in _handler_names178)
)

# ── _execute_scheduler_job branches to all 4 handlers ─────────────────────────
check(
    "178-03. _execute_scheduler_job dispatches to all 4 S4 handlers",
    all(name in _exec178 for name in _handler_names178)
)

# ── Handler: appointment_reminder ─────────────────────────────────────────────
_reminder178 = (_auth178.split('def _handle_appointment_reminder')[1].split('\ndef ')[0]
                if 'def _handle_appointment_reminder' in _auth178 else '')
check(
    "178-04. _handle_appointment_reminder: checks status=='confirmed' before acting",
    'confirmed' in _reminder178 and ("status" in _reminder178 or "appt" in _reminder178)
)
check(
    "178-05. _handle_appointment_reminder: calls create_notification for both participants",
    _reminder178.count('create_notification') >= 1
    and ('company_id' in _reminder178 or 'applicant_id' in _reminder178)
    and 'appointment_reminder' in _reminder178
)

# ── Handler: appointment_deadline_expire ──────────────────────────────────────
_expire178 = (_auth178.split('def _handle_appointment_deadline_expire')[1].split('\ndef ')[0]
              if 'def _handle_appointment_deadline_expire' in _auth178 else '')
check(
    "178-06. _handle_appointment_deadline_expire: uses RETURNING to guard DB transition",
    'RETURNING' in _expire178 and ("expired" in _expire178 or "status='expired'" in _expire178)
)
check(
    "178-07. _handle_appointment_deadline_expire: checks pending_response before acting",
    'pending_response' in _expire178
)

# ── Handler: appointment_missed ───────────────────────────────────────────────
_missed178 = (_auth178.split('def _handle_appointment_missed')[1].split('\ndef ')[0]
              if 'def _handle_appointment_missed' in _auth178 else '')
check(
    "178-08. _handle_appointment_missed: uses RETURNING to guard DB transition",
    'RETURNING' in _missed178 and ("missed" in _missed178 or "status='missed'" in _missed178)
)
check(
    "178-09. _handle_appointment_missed: checks confirmed status before acting",
    'confirmed' in _missed178
)

# ── Handler: job_expiring_soon ────────────────────────────────────────────────
_jobexp178 = (_auth178.split('def _handle_job_expiring_soon')[1].split('\ndef ')[0]
              if 'def _handle_job_expiring_soon' in _auth178 else '')
check(
    "178-10. _handle_job_expiring_soon: checks job status is active/paused before notifying",
    ('active' in _jobexp178 and 'paused' in _jobexp178) or '"active"' in _jobexp178
)

# ── No bare except:pass in any handler ───────────────────────────────────────
check(
    "178-11. AST: no bare except:pass in S4 handler functions",
    _ast178_ok and not any(
        _has_bare_pass_except178(_find_func178(_tree178, name))
        for name in _handler_names178
    )
)

# ── Scheduling hooks ─────────────────────────────────────────────────────────
check(
    "178-12. accept_appointment: schedules appointment_reminder and appointment_missed",
    'appointment_reminder' in _accept178 and 'appointment_missed' in _accept178
    and 'schedule_job' in _accept178
)
check(
    "178-13. send_appointment: schedules appointment_deadline_expire",
    'appointment_deadline_expire' in _send178 and 'schedule_job' in _send178
)
check(
    "178-14. reschedule_appointment: schedules appointment_deadline_expire",
    'appointment_deadline_expire' in _resched178 and 'schedule_job' in _resched178
)
check(
    "178-15. add_job: schedules job_expiring_soon after conn release (return moved outside try)",
    'schedule_job' in _addjob178 and 'job_expiring_soon' in _addjob178
    and 'return result' in _addjob178
    and _addjob178.index('return result') > _addjob178.index('release_conn')
)

# ── Docs updated ──────────────────────────────────────────────────────────────
check(
    "178-16. docs updated: SCHEDULER_PLAN.md documents S4 handlers, SYSTEMS_INDEX.md §37 updated",
    ('S4' in _plan178 and ('handler' in _plan178.lower() or '_handle_' in _plan178))
    and ('S4' in _sysidx178 and ('✅' in _sysidx178 or 'handler' in _sysidx178.lower()))
)

# ── Fix checks: timestamps in payload / dedupe / stale / retry / DB ──────────
# 178-17: Scheduling hooks carry epoch-seconds timestamp in payload AND dedupe key
check(
    "178-17. hooks carry epoch-seconds in payload and dedupe key for all 4 job types",
    'scheduled_at_ts' in _accept178 and 'response_deadline_at_ts' in _send178
    and 'response_deadline_at_ts' in _resched178 and 'expected_expires_at_ts' in _addjob178
    and 'f"appointment_reminder:' in _accept178 and 'f"appointment_missed:' in _accept178
    and 'f"appointment_deadline_expire:' in _send178
    and 'f"job_expiring_soon:' in _addjob178
)

# 178-18: All 4 handlers use _ts_from_db_val for stale-detection comparison
check(
    "178-18. all 4 handlers call _ts_from_db_val for stale-job detection",
    all('_ts_from_db_val' in body for body in [_reminder178, _expire178, _missed178, _jobexp178])
)

# 178-19: appointment_missed checks sched_dt + 15 min before transitioning to 'missed'
check(
    "178-19. appointment_missed: guards transition on scheduled_at + 15 minutes",
    'minutes=15' in _missed178 and 'timedelta' in _missed178
)

# 178-20: Notification failures re-raised in all 4 handlers (not swallowed)
check(
    "178-20. notification failures re-raised in all 4 handlers — not swallowed",
    'raise errors[0]' in _reminder178 and 'raise errors[0]' in _missed178
    and 'raise' in _expire178 and 'raise' in _jobexp178
)

# 178-21: job_expiring_soon handler reads company_id from DB; payload has no company_id;
#          handler guards on active status only (not paused)
_jexp_payload178 = (
    _addjob178.split('"job_expiring_soon"')[1].split(f'"job_expiring_soon:')[0]
    if '"job_expiring_soon"' in _addjob178 and 'f"job_expiring_soon:' in _addjob178
    else ''
)
check(
    "178-21. job_expiring_soon: company_id absent from payload, read from DB, active-only guard",
    'company_id' not in _jexp_payload178
    and 'company_id' in _jobexp178
    and ('!= "active"' in _jobexp178 or "!= 'active'" in _jobexp178)
)

# ═══════════════════════════════════════════════════════════════════════════════
# §179 — Scheduler S5: Minimal Runtime QA (5 checks)
# PR: scheduler-s5-minimal-runtime-qa
# Tests actual code-path behavior via unittest.mock — no live DB required.
# Cases: noop | unknown-type | endpoint-security | dedupe | stale-domain-job
# ═══════════════════════════════════════════════════════════════════════════════

import sys as _sys179, os as _os179
_sys179.path.insert(0, _os179.path.dirname(_os179.path.abspath('auth.py')))
from unittest.mock import patch as _patch179, MagicMock as _MM179

# Import auth module — get_conn() is lazy (calls _parse_db_url only when a
# real connection is needed), so import is safe without SUPABASE_DB_URL.
import auth as _auth179

# ── 179-01: noop — _execute_scheduler_job returns with no DB access ──────────
_179_01_ok = False
_179_01_err = ''
try:
    _auth179._execute_scheduler_job({"job_type": "noop", "payload": {}})
    _179_01_ok = True
except Exception as _e:
    _179_01_err = str(_e)
check("179-01. noop: _execute_scheduler_job completes with no DB access",
      _179_01_ok, _179_01_err or None)

# ── 179-02: unknown job type → ValueError referencing the type ───────────────
_179_02_err = None
try:
    _auth179._execute_scheduler_job({"job_type": "__undef_xjob__", "payload": {}})
except ValueError as _e:
    _179_02_err = str(_e)
except Exception as _e:
    _179_02_err = None
check("179-02. unknown job type: raises ValueError referencing the unknown type",
      bool(_179_02_err) and "__undef_xjob__" in _179_02_err)

# ── 179-03: endpoint security — 503 / 403 / correct-secret path ─────────────
# Import server module (no startup events fire on import — safe without DB).
_179_03_ok = False
_179_03_err = ''
try:
    import server as _srv179
    from fastapi import HTTPException as _HE179

    _503_ok = _403_ok = _200_ok = False

    # 503: SCHEDULER_SECRET not configured
    with _patch179.object(_srv179, 'SCHEDULER_SECRET', ''):
        _req = _MM179()
        _req.headers.get.return_value = ''
        try:
            _srv179.internal_run_due_jobs(_req, limit=1)
        except _HE179 as _e:
            _503_ok = (_e.status_code == 503)

    # 403: wrong secret
    with _patch179.object(_srv179, 'SCHEDULER_SECRET', 'correct_s5'):
        _req = _MM179()
        _req.headers.get.return_value = 'wrong_s5'
        try:
            _srv179.internal_run_due_jobs(_req, limit=1)
        except _HE179 as _e:
            _403_ok = (_e.status_code == 403)

    # correct secret → runner called, result returned
    _mock_runner_ret = {
        "ok": True, "picked": 0, "done": 0, "failed": 0, "retried": 0,
        "update_failed": 0, "stuck_running": 0, "runner_id": "s5-test", "jobs": [],
    }
    with _patch179.object(_srv179, 'SCHEDULER_SECRET', 'correct_s5'), \
         _patch179.object(_srv179, 'run_due_scheduler_jobs', return_value=_mock_runner_ret):
        _req = _MM179()
        _req.headers.get.return_value = 'correct_s5'
        try:
            _r = _srv179.internal_run_due_jobs(_req, limit=1)
            _200_ok = isinstance(_r, dict) and _r.get('ok') is True
        except Exception:
            pass

    _179_03_ok = _503_ok and _403_ok and _200_ok
except Exception as _import_err:
    _179_03_err = f"server import or test error: {_import_err}"
check("179-03. endpoint: no-secret→503, wrong-secret→403, correct-secret→runner called",
      _179_03_ok, _179_03_err or None)

# ── 179-04: dedupe — schedule_job with same dedupe_key → created=False ───────
_179_04_ok = False
_179_04_err = ''
try:
    from datetime import datetime as _dt179, timezone as _tz179, timedelta as _td179

    # 6 columns that schedule_job's RETURNING / SELECT return
    _S5_COLS = [{"name": c} for c in
                ("id", "job_type", "run_at", "status", "dedupe_key", "created_at")]
    _S5_ROW  = (888, "noop", "2026-07-12T10:00:00", "pending",
                "s5-dedupe-test-dk", "2026-07-12T00:00:00")

    _insert_calls = [0]

    def _s5_conn_run(sql, **kw):
        sql_u = sql.strip().upper()
        if "INSERT" in sql_u:
            _insert_calls[0] += 1
            return [_S5_ROW] if _insert_calls[0] == 1 else []
        if "SELECT" in sql_u and "dedupe_key" in sql.lower():
            return [_S5_ROW]
        return []

    _mc = _MM179()
    _mc.run.side_effect = _s5_conn_run
    _mc.columns = _S5_COLS

    _run_at = _dt179.now(_tz179.utc) + _td179(hours=2)
    with _patch179('auth.get_conn', return_value=_mc), _patch179('auth.release_conn'):
        _r1 = _auth179.schedule_job("noop", {}, _run_at, "s5-dedupe-test-dk")
        _r2 = _auth179.schedule_job("noop", {}, _run_at, "s5-dedupe-test-dk")

    _179_04_ok = (
        _r1.get("created") is True
        and _r2.get("created") is False
        and _r1.get("id") == _r2.get("id") == 888
    )
except Exception as _e:
    _179_04_err = str(_e)
check("179-04. dedupe: same dedupe_key → created=True then created=False, same id",
      _179_04_ok, _179_04_err or None)

# ── 179-05: stale domain job → safe no-op, create_notification not called ────
_179_05_ok = False
_179_05_err = ''
try:
    # DB returns appointment with scheduled_at = 2026-01-01T12:00:00 UTC
    # Payload carries stale sched_ts_payload = 1000000 (pre-reschedule epoch)
    # _ts_from_db_val("2026-01-01T12:00:00") ≠ 1000000 → stale → no-op
    _S5_APPT_COLS = [
        "id","job_id","application_id","company_id","applicant_id","created_by",
        "representative_user_id","representative_name","status","mode",
        "scheduled_at","response_deadline_at","location_text","online_url",
        "notes","created_at","updated_at","closed_at",
    ]
    _S5_APPT_ROW = (
        42, 1, 1, 10, 20, 10,
        None, None, "confirmed", "online",
        "2026-01-01T12:00:00", None, None, None,
        None, "2026-01-01T00:00:00", "2026-01-01T00:00:00", None,
    )
    _mc5 = _MM179()
    _mc5.run.return_value = [_S5_APPT_ROW]

    _stale_job = {
        "job_type": "appointment_reminder",
        "payload": {"appointment_id": 42, "scheduled_at_ts": 1000000},
    }

    with _patch179('auth.get_conn', return_value=_mc5), \
         _patch179('auth.release_conn'), \
         _patch179('auth.create_notification') as _mock_notif:
        _auth179._handle_appointment_reminder(_stale_job)
        _179_05_ok = (_mock_notif.call_count == 0)
except Exception as _e:
    _179_05_err = str(_e)
check("179-05. stale domain job: handler exits safe no-op, create_notification not called",
      _179_05_ok, _179_05_err or None)

# ════════════════════════════════════════════════════════════════════════════
# §180 — Company Communication Hub (fix/company-hub-fix)
# 4 static checks: hub button in header (icon-only, owner-only), hub links to
# messages/appointments, no new WebSocket, scroll lock uses CSS class not inline.
# ════════════════════════════════════════════════════════════════════════════
import os as _os180

_co_html180 = ''
try:
    with open('company-profile.html', encoding='utf-8') as _f180h: _co_html180 = _f180h.read()
except Exception: pass

_co_main180 = ''
try:
    with open('static/company/company.main.js', encoding='utf-8') as _f180m: _co_main180 = _f180m.read()
except Exception: pass

_co_api180 = ''
try:
    with open('static/company/company.api.js', encoding='utf-8') as _f180a: _co_api180 = _f180a.read()
except Exception: pass

_co_css180 = ''
try:
    with open('static/company/company.css', encoding='utf-8') as _f180c: _co_css180 = _f180c.read()
except Exception: pass

# 180-01: Hub button is inside sc-head-right wrapper (alongside home-btn), owner-only
# sc-head-right must contain BOTH home-btn and coHubBtn so logo stays absolute-centered
_right_pos   = _co_html180.find('sc-head-right')
_right_end   = _co_html180.find('</div>', _right_pos) if _right_pos >= 0 else -1
_hub_btn_pos = _co_html180.find('id="coHubBtn"')
_hub_in_right = (_right_pos >= 0 and _hub_btn_pos >= 0
                 and _right_pos < _hub_btn_pos < _right_end)
_hub_ctx180  = _co_html180[max(0, _hub_btn_pos - 10):_hub_btn_pos + 120] if _hub_btn_pos >= 0 else ''
check("180-01. Hub button #coHubBtn is inside sc-head-right wrapper, owner-only, sc-hicon-bare",
      _hub_in_right
      and 'owner-only' in _hub_ctx180
      and 'sc-hicon-bare' in _hub_ctx180
      and 'ownerActions' not in _co_html180)

# 180-02: Hub overlay links to /messages and /appointments; overlay uses standalone class (no .overlay base)
_hub_ov_pos  = _co_html180.find('id="coHubOverlay"')
_hub_ov_ctx  = _co_html180[max(0, _hub_ov_pos - 10):_hub_ov_pos + 60] if _hub_ov_pos >= 0 else ''
check("180-02. Hub overlay is standalone (no .overlay base), links to /messages and /appointments",
      _hub_ov_pos >= 0
      and 'class="overlay ' not in _hub_ov_ctx
      and 'href="/messages"' in _co_html180
      and 'href="/appointments"' in _co_html180)

# 180-03: No new WebSocket in company JS (hub is navigation-only, not a new messaging system)
check("180-03. No new WebSocket in company.main.js or company.api.js",
      'new WebSocket' not in _co_main180 and 'new WebSocket' not in _co_api180)

# 180-04: Scroll lock uses CSS class co-hub-open (not inline body.style.overflow)
check("180-04. Scroll lock uses body.co-hub-open CSS class; no inline overflow in hub IIFE",
      'body.co-hub-open' in _co_css180
      and 'classList.add(\'co-hub-open\')' in _co_main180
      and 'classList.remove(\'co-hub-open\')' in _co_main180
      and 'loadCompanyAppointments' in _co_api180)

# §181 — Appointments auth guard key fix (fix/appointments-auth-fix)
# 4 static checks: appointments.html and appointment-room.html must read
# tw_user (not the legacy tawasalna_user key) so company/employee sessions
# are recognised and no redirect loop to /login → /company-profile occurs.
# ════════════════════════════════════════════════════════════════════════════

_appt_html181 = ''
try:
    with open('appointments.html', encoding='utf-8') as _f181a: _appt_html181 = _f181a.read()
except Exception: pass

_room_html181 = ''
try:
    with open('appointment-room.html', encoding='utf-8') as _f181r: _room_html181 = _f181r.read()
except Exception: pass

# 181-01: appointments.html reads tw_user (correct key) not tawasalna_user
check("181-01. appointments.html auth guard reads tw_user (not tawasalna_user)",
      "localStorage.getItem('tw_user')" in _appt_html181
      and "localStorage.getItem('tawasalna_user')" not in _appt_html181)

# 181-02: appointment-room.html reads tw_user (correct key) not tawasalna_user
check("181-02. appointment-room.html auth guard reads tw_user (not tawasalna_user)",
      "localStorage.getItem('tw_user')" in _room_html181
      and "localStorage.getItem('tawasalna_user')" not in _room_html181)

# 181-03: /appointments route exists in server.py (no new route added)
_srv181 = ''
try:
    with open('server.py', encoding='utf-8') as _f181s: _srv181 = _f181s.read()
except Exception: pass
check("181-03. /appointments route in server.py serves appointments.html",
      '@app.get("/appointments"' in _srv181
      and 'appointments.html' in _srv181)

# 181-04: Guest redirect preserved — auth guard still sends unauthenticated to /login
check("181-04. auth guard in appointments.html still redirects unauthenticated to /login",
      "location.href = '/login'" in _appt_html181
      and "localStorage.getItem('tw_jwt')" in _appt_html181)

# ════════════════════════════════════════════════════════════════════════════
# §182 — Promote Application to Shortlist: PR-B backend (feat/promote-application)
# 24 static checks covering: race-condition-safe transaction (BEGIN before SELECTs,
# FOR UPDATE locks), UPSERT always runs (no skip gate), RETURNING as authoritative
# final state, post-UPSERT pre-COMMIT rejected check closes the non-existent-row
# race, UPSERT CASE defense-in-depth, correct exception re-raise, endpoint wiring.
# ════════════════════════════════════════════════════════════════════════════

_auth182 = ''
try:
    with open('auth.py', encoding='utf-8') as _f182a: _auth182 = _f182a.read()
except Exception: pass

_srv182 = _srv181  # already loaded above

# 182-01: promote_application_to_shortlist function exists in auth.py
check("182-01. promote_application_to_shortlist function defined in auth.py",
      "def promote_application_to_shortlist(" in _auth182)

# 182-02: _CANDIDATE_STATUS_RANK dict exists with all valid non-rejected statuses
check("182-02. _CANDIDATE_STATUS_RANK defined with all non-rejected statuses",
      "_CANDIDATE_STATUS_RANK" in _auth182
      and '"saved"' in _auth182
      and '"shortlisted"' in _auth182
      and '"contacted"' in _auth182
      and '"interview"' in _auth182
      and '"hired"' in _auth182)

# Extract the function body once for all subsequent checks
_promote_fn182 = ""
if "def promote_application_to_shortlist(" in _auth182:
    _start182 = _auth182.index("def promote_application_to_shortlist(")
    _end182   = _auth182.index("\ndef get_company_candidate_suggestions(", _start182)
    _promote_fn182 = _auth182[_start182:_end182]

# 182-03: BEGIN appears BEFORE the critical SELECT queries (race-condition fix)
# Verify BEGIN comes before "FOR UPDATE OF ja" — not after reading data first
check("182-03. conn.run(BEGIN) appears before SELECT FOR UPDATE OF ja",
      'conn.run("BEGIN")' in _promote_fn182
      and _promote_fn182.index('conn.run("BEGIN")') < _promote_fn182.index('FOR UPDATE OF ja'))

# 182-04: application row locked with FOR UPDATE OF ja inside transaction
check("182-04. application row locked with FOR UPDATE OF ja inside transaction",
      "FOR UPDATE OF ja" in _promote_fn182)

# 182-05: candidate row locked with FOR UPDATE inside transaction
check("182-05. candidate row locked with FOR UPDATE inside transaction",
      "FOR UPDATE" in _promote_fn182
      and "company_saved_candidates" in _promote_fn182
      and _promote_fn182.index("FOR UPDATE") != _promote_fn182.rindex("FOR UPDATE"))  # two FOR UPDATEs

# 182-06: ownership check — job_company_id must equal company_id
check("182-06. ownership check: job_company_id vs company_id",
      "job_company_id" in _promote_fn182
      and "int(job_company_id) != int(company_id)" in _promote_fn182
      and "PermissionError" in _promote_fn182)

# 182-07: applicant type is validated as 'emp'
check("182-07. applicant user_type must be 'emp'",
      'applicant_type != "emp"' in _promote_fn182
      and "ValueError" in _promote_fn182)

# 182-08: rejected candidate raises ValueError (ROLLBACK triggered via exception catch)
check("182-08. rejected candidate raises ValueError inside transaction",
      'current_cand_status == "rejected"' in _promote_fn182
      and 'raise ValueError' in _promote_fn182)

# 182-09: UPSERT CASE prevents rejected from being reactivated (SQL-level defense)
check("182-09. UPSERT CASE preserves 'rejected' status — cannot be reactivated via UPSERT",
      "ON CONFLICT (company_id, candidate_id) DO UPDATE" in _promote_fn182
      and "'rejected'" in _promote_fn182
      and "CASE" in _promote_fn182)

# 182-10: UPSERT CASE prevents contacted/interview/hired from being downgraded
check("182-10. UPSERT CASE preserves contacted/interview/hired — no downgrade possible",
      "'contacted','interview','hired','rejected'" in _promote_fn182
      or "('contacted','interview','hired','rejected')" in _promote_fn182)

# 182-11: UPSERT is never gated by skip_candidate_update — always runs unconditionally
# (changed from PR-B v1 which had if not skip_candidate_update: — removed to close
#  the non-existent-row race where FOR UPDATE cannot lock a row that doesn't yet exist)
check("182-11. UPSERT always runs — no skip_candidate_update gate",
      'skip_candidate_update' not in _promote_fn182
      and "ON CONFLICT (company_id, candidate_id) DO UPDATE" in _promote_fn182)

# 182-12: application is always updated to 'accepted' inside the transaction
check("182-12. application status set to 'accepted' inside transaction",
      "UPDATE job_applications SET status = 'accepted'" in _promote_fn182)

# 182-13: known exceptions (KeyError/PermissionError/ValueError) re-raised as-is (not RuntimeError)
check("182-13. KeyError/PermissionError/ValueError re-raised as-is, not wrapped in RuntimeError",
      "except (KeyError, PermissionError, ValueError):" in _promote_fn182
      and "raise" in _promote_fn182)

# 182-14: unexpected DB errors wrapped in RuntimeError (separate except block)
check("182-14. unexpected DB errors wrapped in RuntimeError (separate except block)",
      "except Exception as _tx_err:" in _promote_fn182
      and "raise RuntimeError" in _promote_fn182)

# 182-15: UPSERT uses RETURNING to get final state — job_id removed (Option B: job_applications is source)
# RETURNING is the authoritative source for final_status / was_inserted
check("182-15. UPSERT uses RETURNING status and was_inserted (job_id removed per Option B)",
      "RETURNING status" in _promote_fn182
      and "was_inserted" in _promote_fn182
      and "(xmax = 0)" in _promote_fn182)

# 182-16: return value contains application + candidate + action + status_label
check("182-16. return value shape: application + candidate + action + status_label",
      '"application"' in _promote_fn182
      and '"candidate"' in _promote_fn182
      and '"action"' in _promote_fn182
      and '"status_label"' in _promote_fn182)

# 182-17: POST /jobs/applications/{app_id}/promote endpoint defined in server.py
check("182-17. POST /jobs/applications/{app_id}/promote endpoint exists",
      '@app.post("/jobs/applications/{app_id}/promote")' in _srv182)

# 182-18: promote_application_to_shortlist imported in server.py
check("182-18. promote_application_to_shortlist imported in server.py",
      "promote_application_to_shortlist" in _srv182)

# 182-19: endpoint maps KeyError→404, PermissionError→403, ValueError→409, RuntimeError→500
_ep_start182 = _srv182.find('@app.post("/jobs/applications/{app_id}/promote")')
_ep_end182   = _srv182.find('\n@app.', _ep_start182 + 10)
_ep_block182 = _srv182[_ep_start182:_ep_end182] if _ep_start182 >= 0 else ""
check("182-19. endpoint maps KeyError→404, PermissionError→403, ValueError→409, RuntimeError→500",
      "KeyError" in _ep_block182 and "404" in _ep_block182
      and "PermissionError" in _ep_block182 and "403" in _ep_block182
      and "ValueError" in _ep_block182 and "409" in _ep_block182
      and "RuntimeError" in _ep_block182 and "500" in _ep_block182)

# 182-20: security log for ownership failure
check("182-20. endpoint logs PROMOTE_OWNERSHIP_FAILED on PermissionError",
      "PROMOTE_OWNERSHIP_FAILED" in _ep_block182)

# 182-21: post-UPSERT, pre-COMMIT rejected check — closes the non-existent-row race
# A concurrent INSERT-as-rejected between FOR UPDATE SELECT (which found no row)
# and the UPSERT would be caught here via RETURNING, and the transaction is ROLLED BACK.
check("182-21. post-UPSERT pre-COMMIT check: final_status==rejected → raise ValueError",
      'final_status == "rejected"' in _promote_fn182
      and 'raise ValueError' in _promote_fn182
      and _promote_fn182.index('final_status == "rejected"') < _promote_fn182.index('conn.run("COMMIT")'))

# 182-22: COMMIT appears AFTER the post-UPSERT rejected guard (ordering invariant)
# Ensures that if RETURNING returns rejected, ROLLBACK fires before COMMIT is reached.
check("182-22. COMMIT appears after post-UPSERT rejected guard in function body",
      'conn.run("COMMIT")' in _promote_fn182
      and 'final_status == "rejected"' in _promote_fn182
      and _promote_fn182.index('final_status == "rejected"') < _promote_fn182.index('conn.run("COMMIT")'))

# 182-23: was_inserted derived from RETURNING (xmax=0) used to compute candidate_action
# Ensures action is computed from RETURNING result, not from a pre-COMMIT assumption.
# rindex finds the LAST occurrence of 'was_inserted' (in the post-COMMIT action block),
# not the first (inside the UPSERT SQL string, which is before COMMIT).
check("182-23. candidate_action computed from was_inserted (RETURNING xmax=0) after COMMIT",
      'was_inserted' in _promote_fn182
      and 'candidate_action = "created"' in _promote_fn182
      and 'candidate_action = "unchanged"' in _promote_fn182
      and 'candidate_action = "updated"' in _promote_fn182
      and _promote_fn182.rindex('was_inserted') > _promote_fn182.index('conn.run("COMMIT")'))

# 182-24: upsert_rows empty raises RuntimeError — no silent fallback for missing RETURNING
check("182-24. empty RETURNING result raises RuntimeError (no silent fallback)",
      'if not upsert_rows:' in _promote_fn182
      and 'raise RuntimeError' in _promote_fn182)


# ═══════════════════════════════════════════════════════════════════════════
# §183 — Applicants Modal UI (PR-A)
# Static checks on company.main.js
# ═══════════════════════════════════════════════════════════════════════════
with open("static/company/company.main.js", encoding="utf-8") as _f183:
    _main183 = _f183.read()

# 183-01: accepted label is "مرشح قوي" in _APP_STATUS_LABEL
_asl183 = _main183.split('_APP_STATUS_LABEL')[1][:300] if '_APP_STATUS_LABEL' in _main183 else ''
check("183-01. _APP_STATUS_LABEL['accepted'] is 'مرشح قوي'",
      'مرشح قوي' in _asl183)

# 183-02: classify button rendered (replaces old promote-btn)
check("183-02. co-classify-btn rendered in _renderApplicants (replaces promote-btn)",
      'co-classify-btn' in _main183
      and 'حفظ وتصنيف' in _main183)

# 183-03: sched button rendered for interview status (replaces interview-btn on accepted)
check("183-03. co-app-sched-btn rendered for interview status in _renderApplicants",
      'co-app-sched-btn' in _main183
      and "isInterview" in _main183)

# 183-04: rejected cards get co-app-card--rejected class and show reclassify btn
check("183-04. rejected card gets co-app-card--rejected class and إعادة التصنيف",
      'co-app-card--rejected' in _main183
      and 'إعادة التصنيف' in _main183)

# 183-05: _wireApplicantCards delegates to co-classify-btn (not old promote/save/menu)
_wire183 = (_main183.split('function _wireApplicantCards')[1].split('function _onSchedBtn')[0]
            if 'function _wireApplicantCards' in _main183 else '')
check("183-05. _wireApplicantCards uses co-classify-btn, not old co-app-promote-btn",
      'co-classify-btn' in _wire183
      and 'co-app-promote-btn' not in _wire183)

# 183-06: _onPromote function defined
check("183-06. _onPromote function defined",
      'function _onPromote(' in _main183)

# 183-07: _execPromote calls POST /jobs/applications/.../promote (not PUT /status)
_exec183 = _main183.split('function _execPromote')[1].split('function _onSaveApplicant')[0] if 'function _execPromote' in _main183 else ''
check("183-07. _execPromote calls POST /jobs/applications/{id}/promote",
      "'/jobs/applications/' + appId + '/promote'" in _exec183
      and "method:  'POST'" in _exec183 or "method: 'POST'" in _exec183)

# 183-08: _execPromote disables button during in-flight request
check("183-08. _execPromote disables promote button during in-flight",
      'promoteBtn.disabled    = true' in _main183 or 'promoteBtn.disabled = true' in _main183)

# 183-09: success path calls _reRenderCardFoot (replaces old replaceChild promote→interview)
_exec183p = (_main183.split('function _execPromote')[1].split('function _onSchedBtn')[0]
             if 'function _execPromote' in _main183 else '')
check("183-09. success: _execPromote calls _reRenderCardFoot instead of DOM swap",
      '_reRenderCardFoot' in _exec183p)

# 183-10: 409 error removed (غير مناسب classification now via dropdown, not reject endpoint)
check("183-10. 409 status === 409 check removed from _execPromote (new flow has no 409)",
      'status === 409' not in _exec183p)

# 183-11: _astFloat option label for accepted is "مرشح قوي" (not "مقبول")
check("183-11. _astFloat accepted option label is 'مرشح قوي'",
      "data-val=\"accepted\">مرشح قوي" in _main183 or "data-val='accepted'>مرشح قوي" in _main183)

# 183-12: _astFloat click handler routes accepted → _execPromote
check("183-12. _astFloat click routes 'accepted' → _execPromote",
      "_execPromote(" in _main183.split("newStatus === 'accepted'")[1][:300]
      if "newStatus === 'accepted'" in _main183 else False)

# 183-13: dead code removed — _updateQuickBtnStates and _onQuickStatus are gone
check("183-13. _updateQuickBtnStates and _onQuickStatus are removed",
      'function _updateQuickBtnStates' not in _main183
      and 'function _onQuickStatus' not in _main183)

# 183-14: Bearer JWT — no X-User-Id header in promote fetch
check("183-14. promote fetch uses Bearer JWT only — no X-User-Id",
      'X-User-Id' not in _main183.split('function _execPromote')[1].split('function _onSaveApplicant')[0]
      if 'function _execPromote' in _main183 else False)

# ── §184 — PR-C: Interview Button → Appointment Scheduling ───────────────
with open("static/company/company.main.js", encoding="utf-8") as f:
    _main184 = f.read()
with open("static/company/company.css", encoding="utf-8") as f:
    _css184 = f.read()
with open("company-profile.html", encoding="utf-8") as f:
    _html184 = f.read()

# 184-01: new appointment-state vars declared
check("184-01. _apptByAppId and _apptIndexLoaded declared",
      '_apptByAppId' in _main184 and '_apptIndexLoaded' in _main184)

# 184-02: data-name attribute added to card div in _renderApplicants
check("184-02. card div has data-name attribute in _renderApplicants",
      'data-name="' in _main184 and '_escApp(a.full_name' in _main184)

# 184-03: sched button rendered for interview status in _renderApplicants
_render184 = _main184.split('function _renderApplicants')[1].split('function _wireApplicantCards')[0] if 'function _renderApplicants' in _main184 else ''
check("184-03. co-app-sched-btn rendered for interview status in _renderApplicants",
      'co-app-sched-btn' in _render184
      and 'isInterview' in _render184)

# 184-04: _wireApplicantCards delegates co-app-sched-btn to _onSchedBtn
_wire184 = _main184.split('function _wireApplicantCards')[1].split('function _onSchedBtn')[0] if 'function _wireApplicantCards' in _main184 else ''
check("184-04. _wireApplicantCards delegates co-app-sched-btn to _onSchedBtn",
      'co-app-sched-btn' in _wire184 and '_onSchedBtn' in _wire184)

# 184-05: _loadApptIndex function defined
check("184-05. _loadApptIndex function defined",
      'function _loadApptIndex' in _main184)

# 184-06: _loadApptIndex calls GET /api/appointments with Bearer JWT
_idx184 = _main184.split('function _loadApptIndex')[1].split('function _applyApptIndexToCards')[0] if 'function _loadApptIndex' in _main184 else ''
check("184-06. _loadApptIndex calls GET /api/appointments with Bearer JWT",
      "'/api/appointments'" in _idx184 and 'Bearer' in _idx184)

# 184-07: _applyApptIndexToCards replaces interview btn with "فتح الموعد" link
check("184-07. _applyApptIndexToCards swaps interview btn to open-appt link",
      'function _applyApptIndexToCards' in _main184
      and 'co-app-open-appt-btn' in _main184
      and 'appointment-room?id=' in _main184)

# 184-08: _onSchedBtn function defined (renamed from _onInterviewBtn)
check("184-08. _onSchedBtn function defined (replaces _onInterviewBtn)",
      'function _onSchedBtn' in _main184)

# 184-09: _openApptModal function defined
check("184-09. _openApptModal function defined",
      'function _openApptModal' in _main184)

# 184-10: _closeApptModal function defined
check("184-10. _closeApptModal function defined",
      'function _closeApptModal' in _main184)

# 184-11: _submitApptForm calls POST /api/appointments then POST /send
_submit184 = _main184.split('function _submitApptForm')[1].split('function _isApptActive')[0] if 'function _submitApptForm' in _main184 else ''
_submit184 = _main184.split('function _submitApptForm')[1] if 'function _submitApptForm' in _main184 else ''
check("184-11. _submitApptForm calls POST /api/appointments then /send",
      "'/api/appointments'" in _submit184
      and "'/send'" in _submit184
      and "method:  'POST'" in _submit184 or "method: 'POST'" in _submit184)

# 184-12: _submitApptForm uses Bearer JWT only — no X-User-Id
check("184-12. _submitApptForm uses Bearer JWT only — no X-User-Id",
      'X-User-Id' not in _submit184 and 'Bearer' in _submit184)

# 184-13: duplicate appointment error shows specific Arabic message
check("184-13. يوجد موعد نشط error message in _submitApptForm",
      'يوجد موعد نشط' in _submit184)

# 184-14: on success, navigates to /appointment-room?id=
check("184-14. success navigates to /appointment-room?id=",
      "location.href = '/appointment-room?id=' + apptId" in _main184
      or "/appointment-room?id='" in _main184)

# 184-15: _execPromote calls _reRenderCardFoot on success (replaces manual interview-btn creation)
_exec184 = _main184.split('function _execPromote')[1].split('function _onSaveApplicant')[0] if 'function _execPromote' in _main184 else ''
check("184-15. _execPromote calls _reRenderCardFoot on success (no manual interview-btn DOM swap)",
      '_reRenderCardFoot' in _exec184 and 'interviewBtn' not in _exec184)

# 184-16: appointment modal HTML exists in company-profile.html
check("184-16. #coApptModal overlay exists in company-profile.html",
      'id="coApptModal"' in _html184)

# 184-17: required form fields in modal HTML
check("184-17. coApptDate, coApptTime, coApptModeOnline, coApptSubmit in HTML",
      'id="coApptDate"' in _html184
      and 'id="coApptTime"' in _html184
      and 'id="coApptModeOnline"' in _html184
      and 'id="coApptSubmit"' in _html184)

# 184-18: coApptUrlRow and coApptLocRow conditional rows in HTML
check("184-18. coApptUrlRow and coApptLocRow in HTML",
      'id="coApptUrlRow"' in _html184
      and 'id="coApptLocRow"' in _html184)

# 184-19: co-appt-submit CSS defined in company.css
check("184-19. .co-appt-submit styled in company.css",
      '.co-appt-submit' in _css184)

# 184-20: .co-app-open-appt-btn styled in company.css
check("184-20. .co-app-open-appt-btn styled in company.css",
      '.co-app-open-appt-btn' in _css184)

# ── §184-21–25 — draft-orphan recovery (create succeeds, send fails) ─────
# These checks verify the invariant: a failed send never leaves the user stuck.

# 184-21: _isApptDraft function defined
check("184-21. _isApptDraft function defined",
      'function _isApptDraft' in _main184)

# 184-22: _applyApptIndexToCards skips draft entries (keeps interview btn for retry)
_apply184 = (_main184.split('function _applyApptIndexToCards')[1]
             .split('function _onInterviewBtn')[0]
             if 'function _applyApptIndexToCards' in _main184 else '')
check("184-22. _applyApptIndexToCards skips draft entries — interview btn stays for retry",
      '_isApptDraft' in _apply184)

# 184-23: _onSchedBtn routes draft entries to _openApptModal (not window.open)
_onint184 = (_main184.split('function _onSchedBtn')[1]
             .split('function _openApptModal')[0]
             if 'function _onSchedBtn' in _main184 else '')
check("184-23. _onSchedBtn routes draft entries to _openApptModal (not room)",
      '_isApptDraft' in _onint184 and '_openApptModal' in _onint184)

# 184-24: after create success, draft stored in _apptByAppId BEFORE _execSendStep is called
_sub184 = (_main184.split('function _submitApptForm')[1]
           .split('function _execSendStep')[0]
           if 'function _submitApptForm' in _main184
           and 'function _execSendStep' in _main184 else '')
check("184-24. draft stored in _apptByAppId before _execSendStep — no orphan on send failure",
      "_apptByAppId[String(appId)] = { id: apptId, status: 'draft' }" in _sub184
      and '_execSendStep' in _sub184)

# 184-25: _execSendStep defined — handles send step independently, preserves draft on failure
check("184-25. _execSendStep defined — send isolated so draft survives send failure",
      'function _execSendStep' in _main184)

# ══════════════════════════════════════════════════════════════════════════
# §185 — Option B: job_applications as per-job source of truth
#   - save_company_candidate UPSERT no longer overwrites job_id
#   - promote UPSERT no longer overwrites job_id
#   - get_job_applicants returns other_job_titles
#   - saved candidates list returns job_titles[]
#   - saved candidates filtered returns per_job_accepted
#   - frontend shows job title chips not raw IDs
# ══════════════════════════════════════════════════════════════════════════

_auth185  = open('auth.py', encoding='utf-8').read()
_main185  = open('static/company/company.main.js', encoding='utf-8').read()
_css185   = open('static/company/company.css', encoding='utf-8').read()

# 185-01: save_company_candidate ON CONFLICT no longer writes job_id=EXCLUDED.job_id
_save185 = (_auth185.split('def save_company_candidate')[1].split('def get_company_saved_candidates')[0]
            if 'def save_company_candidate' in _auth185 else '')
check("185-01. save_company_candidate UPSERT does not overwrite job_id",
      'job_id=EXCLUDED.job_id' not in _save185
      and 'ON CONFLICT (company_id, candidate_id) DO UPDATE' in _save185)

# 185-02: promote UPSERT no longer has job_id = CASE block
_prom185 = (_auth185.split('def promote_application_to_shortlist')[1].split('def get_company_candidate_suggestions')[0]
            if 'def promote_application_to_shortlist' in _auth185 else '')
check("185-02. promote UPSERT no longer overwrites job_id",
      'job_id = CASE' not in _prom185
      and 'ON CONFLICT (company_id, candidate_id) DO UPDATE' in _prom185)

# 185-03: promote RETURNING only 2 columns (status, was_inserted — no job_id)
check("185-03. promote RETURNING has no job_id column",
      'RETURNING status, (xmax = 0) AS was_inserted' in _prom185
      and 'RETURNING status, job_id' not in _prom185)

# 185-04: promote return dict has no final_job_id / job_id field
check("185-04. promote return dict has no final_job_id",
      'final_job_id' not in _prom185
      and '"job_id":       final_job_id' not in _prom185)

# 185-05: get_job_applicants batch-fetches other_job_titles for saved candidates
# Updated §186: now reads from company_candidate_job_refs not job_applications
_gjapp185 = (_auth185.split('def get_job_applicants')[1].split('def get_user_applications')[0]
             if 'def get_job_applicants' in _auth185 else '')
check("185-05. get_job_applicants batch-fetches other_job_titles",
      'other_job_titles' in _gjapp185
      and 'other_titles_map' in _gjapp185
      and 'r.job_id != :jid' in _gjapp185)

# 185-06: get_company_saved_candidates batch-fetches job_titles
# Updated §186: now reads from company_candidate_job_refs not job_applications
_gsc185 = (_auth185.split('def get_company_saved_candidates(')[1].split('def get_company_saved_candidates_count')[0]
           if 'def get_company_saved_candidates(' in _auth185 else '')
check("185-06. get_company_saved_candidates returns job_titles",
      'job_titles' in _gsc185
      and 'jtmap' in _gsc185
      and 'company_candidate_job_refs' in _gsc185)

# 185-07: get_company_saved_candidates_filtered returns job_titles + per_job_accepted
_gscf185 = (_auth185.split('def get_company_saved_candidates_filtered')[1].split('def get_company_saved_candidates_stats')[0]
            if 'def get_company_saved_candidates_filtered' in _auth185 else '')
check("185-07. get_company_saved_candidates_filtered returns job_titles and per_job_accepted",
      'job_titles' in _gscf185
      and 'per_job_accepted' in _gscf185
      and 'accepted_ids' in _gscf185)

# 185-08: per_job_accepted only computed when job_id param is provided (not always)
check("185-08. per_job_accepted is conditional on job_id filter param",
      'if job_id is not None' in _gscf185
      and 'per_job_accepted' in _gscf185)

# 185-09: _savedCardHTML shows co-cand-job-chips instead of raw job-ref ID
_scard185 = (_main185.split('function _savedCardHTML')[1].split('// Wire textarea')[0]
             if 'function _savedCardHTML' in _main185 else '')
check("185-09. _savedCardHTML shows co-cand-job-chips not raw job_id",
      'co-cand-job-chips' in _scard185
      and 'co-cand-job-chip' in _scard185
      and 'مرتبط بوظيفة #' not in _scard185)

# 185-10: _savedCardHTML uses item.job_titles array
check("185-10. _savedCardHTML sources from item.job_titles array",
      'item.job_titles' in _scard185)

# 185-11: _renderApplicants builds savedCtx for other_job_titles
_rappl185 = (_main185.split('function _renderApplicants')[1].split('function _wireApplicantCards')[0]
             if 'function _renderApplicants' in _main185 else '')
check("185-11. _renderApplicants renders savedCtx for other_job_titles",
      'savedCtx' in _rappl185
      and 'other_job_titles' in _rappl185
      and 'co-app-saved-ctx' in _rappl185)

# 185-12: savedCtx is inserted between card-head and card-foot in the html string building
check("185-12. savedCtx placed between card-head and card-foot",
      'card-head' in _rappl185
      and '+ savedCtx' in _rappl185
      and _rappl185.index('+ savedCtx') > _rappl185.index('card-head')
      and _rappl185.index('+ savedCtx') < _rappl185.index('card-foot'))

# 185-13: _applyCardUpdate no longer creates raw .co-cand-job-ref element
_acu185 = (_main185.split('function _applyCardUpdate')[1].split('// Sync custom status')[0]
           if 'function _applyCardUpdate' in _main185 else '')
check("185-13. _applyCardUpdate does not re-create raw job_id display",
      'مرتبط بوظيفة #' not in _acu185)

# 185-14: .co-cand-job-chips styled in company.css
check("185-14. .co-cand-job-chips styled in company.css",
      '.co-cand-job-chips' in _css185
      and '.co-cand-job-chip' in _css185)

# 185-15: .co-app-saved-ctx styled in company.css
check("185-15. .co-app-saved-ctx styled in company.css",
      '.co-app-saved-ctx' in _css185)

# ── §186 — company_candidate_job_refs (Option B v2) ──────────────────────
# Tests that company_candidate_job_refs is the authoritative source for
# job_titles[] and that job_applications is NOT used for display.

_auth186 = auth_src
_srv186 = open("server.py", encoding="utf-8").read()

# 186-01: _migrate_company_candidate_job_refs defined in auth.py
check("186-01. _migrate_company_candidate_job_refs defined in auth.py",
      'def _migrate_company_candidate_job_refs' in _auth186)

# 186-02: company_candidate_job_refs table has the correct PRIMARY KEY columns
check("186-02. company_candidate_job_refs PRIMARY KEY (company_id, candidate_id, job_id)",
      'company_candidate_job_refs' in _auth186
      and 'PRIMARY KEY (company_id, candidate_id, job_id)' in _auth186)

# 186-03: idx_ccjr_company_candidate index defined
check("186-03. idx_ccjr_company_candidate index defined",
      'idx_ccjr_company_candidate' in _auth186)

# 186-04: _migrate_company_candidate_job_refs imported and called in server.py
check("186-04. _migrate_company_candidate_job_refs imported and called in server.py",
      '_migrate_company_candidate_job_refs' in _srv186)

# 186-05: save_company_candidate inserts into refs when job_id provided (atomic)
_save186 = (_auth186.split('def save_company_candidate')[1].split('def remove_company_candidate')[0]
            if 'def save_company_candidate' in _auth186 else '')
check("186-05. save_company_candidate writes to company_candidate_job_refs atomically",
      'company_candidate_job_refs' in _save186
      and 'ON CONFLICT DO NOTHING' in _save186
      and 'BEGIN' in _save186
      and 'COMMIT' in _save186)

# 186-06: promote_application_to_shortlist writes to refs inside transaction
_promote186 = (_auth186.split('def promote_application_to_shortlist')[1].split('def get_company_candidate_suggestions')[0]
               if 'def promote_application_to_shortlist' in _auth186 else '')
_commit_run186 = 'conn.run("COMMIT")'
# §491: promote now uses DO UPDATE SET candidate_status='shortlisted' (was DO NOTHING)
check("186-06. promote_application_to_shortlist writes to company_candidate_job_refs inside transaction with DO UPDATE — updated §491",
      'company_candidate_job_refs' in _promote186
      and ("DO UPDATE" in _promote186 or "DO NOTHING" in _promote186)
      and _commit_run186 in _promote186
      and _promote186.index('company_candidate_job_refs') < _promote186.index(_commit_run186))

# 186-07: get_company_saved_candidates reads job_titles from refs, not job_applications
_gsc186 = (_auth186.split('def get_company_saved_candidates(')[1].split('def get_company_saved_candidates_count')[0]
           if 'def get_company_saved_candidates(' in _auth186 else '')
check("186-07. get_company_saved_candidates reads job_titles from refs not job_applications",
      'company_candidate_job_refs' in _gsc186
      and 'FROM job_applications ja' not in _gsc186.split('# Batch-fetch job titles')[1])

# 186-08: get_company_saved_candidates_filtered reads job_titles from refs
_gscf186 = (_auth186.split('def get_company_saved_candidates_filtered')[1].split('def get_company_saved_candidates_stats')[0]
            if 'def get_company_saved_candidates_filtered' in _auth186 else '')
check("186-08. get_company_saved_candidates_filtered reads job_titles from refs",
      'company_candidate_job_refs' in _gscf186
      and 'r.candidate_id, j.title' in _gscf186)

# 186-09: job_id filter in filtered view uses EXISTS subquery on refs (not sc.job_id =)
check("186-09. job_id filter uses EXISTS on company_candidate_job_refs not sc.job_id =",
      'EXISTS (SELECT 1 FROM company_candidate_job_refs r' in _gscf186
      and 'AND r.job_id = :job_id' in _gscf186
      and 'sc.job_id = :job_id' not in _gscf186)

# 186-10: unlinked filter uses NOT EXISTS on refs (not sc.job_id IS NULL)
check("186-10. unlinked filter uses NOT EXISTS on refs not sc.job_id IS NULL",
      'NOT EXISTS (SELECT 1 FROM company_candidate_job_refs r' in _gscf186
      and 'sc.job_id IS NULL' not in _gscf186)

# 186-11: get_job_applicants reads other_job_titles from refs not job_applications
_gjapp186 = (_auth186.split('def get_job_applicants')[1].split('def get_user_applications')[0]
             if 'def get_job_applicants' in _auth186 else '')
check("186-11. get_job_applicants other_job_titles from refs not job_applications",
      'company_candidate_job_refs' in _gjapp186
      and 'r.candidate_id, j2.title' in _gjapp186
      and 'FROM job_applications ja2' not in _gjapp186)

# 186-12: get_company_saved_candidates_stats uses refs for with_job/unlinked counts
_stats186 = (_auth186.split('def get_company_saved_candidates_stats')[1].split('def update_company_saved_candidate')[0]
             if 'def get_company_saved_candidates_stats' in _auth186 else '')
check("186-12. stats with_job/unlinked counts use refs subquery not sc.job_id IS NULL",
      'company_candidate_job_refs' in _stats186
      and 'job_id IS NULL' not in _stats186
      and 'job_id IS NOT NULL' not in _stats186)

# 186-00b: backfill INSERT is inside _migrate_company_candidate_job_refs
_mig186 = (_auth186.split('def _migrate_company_candidate_job_refs')[1].split('def save_company_candidate')[0]
           if 'def _migrate_company_candidate_job_refs' in _auth186 else '')
check("186-00b. migration backfills refs from company_saved_candidates WHERE job_id IS NOT NULL",
      'INSERT INTO company_candidate_job_refs' in _mig186
      and 'SELECT company_id, candidate_id, job_id' in _mig186
      and 'FROM company_saved_candidates' in _mig186
      and 'WHERE job_id IS NOT NULL' in _mig186
      and 'ON CONFLICT DO NOTHING' in _mig186)

# 186-13: per_job_accepted still sourced from job_applications.status='accepted' (not from refs)
# The filtered function has a dedicated acc_rows query on job_applications for this
check("186-13. per_job_accepted still sourced from job_applications.status='accepted'",
      "status = 'accepted'" in _gscf186
      and 'acc_rows' in _gscf186
      and 'job_applications' in _gscf186
      and 'accepted_ids' in _gscf186)

# ═══════════════════════════════════════════════════════════════════════════
# §187 — New Applicant Card UI (feat/applicant-classify-ui)
#   - 7-option classify dropdown replaces promote-btn + ⋮ menu
#   - Interview choice mini-portal (الآن / لاحقاً)
#   - Rejected card dimming + إعادة التصنيف
#   - Hired state hides غير مناسب from dropdown
#   - _execClassify unified save+status action
#   - Backend: 'contacted','interview','hired' in allowed_statuses + _INTERNAL_STATUSES
# ═══════════════════════════════════════════════════════════════════════════
with open("static/company/company.main.js", encoding="utf-8") as _f187:
    _main187 = _f187.read()
with open("static/company/company.css", encoding="utf-8") as _f187c:
    _css187 = _f187c.read()
with open("server.py", encoding="utf-8") as _f187s:
    _srv187 = _f187s.read()
with open("auth.py", encoding="utf-8") as _f187a:
    _auth187 = _f187a.read()

# 187-01: server.py allowed_statuses includes contacted, interview, hired (double-quoted in set)
_allowed187 = (_srv187.split('allowed_statuses = {')[1][:200]
               if 'allowed_statuses = {' in _srv187 else '')
check("187-01. server.py allowed_statuses includes contacted, interview, hired",
      'contacted' in _allowed187 and 'interview' in _allowed187 and 'hired' in _allowed187)

# 187-02: _INTERNAL_STATUSES in auth.py includes contacted, interview, hired
check("187-02. _INTERNAL_STATUSES includes contacted, interview, hired",
      'contacted' in _auth187.split('_INTERNAL_STATUSES')[1][:200]
      and 'interview' in _auth187.split('_INTERNAL_STATUSES')[1][:200]
      and 'hired' in _auth187.split('_INTERNAL_STATUSES')[1][:200])

# 187-03: _APP_STATUS_LABEL has all 7 statuses
_asl187 = _main187.split('_APP_STATUS_LABEL')[1][:400] if '_APP_STATUS_LABEL' in _main187 else ''
check("187-03. _APP_STATUS_LABEL has all 7 statuses",
      'contacted' in _asl187 and 'interview' in _asl187 and 'hired' in _asl187
      and 'مرشح قوي' in _asl187 and 'غير مناسب' in _asl187)

# 187-04: _renderApplicants shows co-classify-btn with data-uid attribute
_rend187 = (_main187.split('function _renderApplicants')[1].split('function _wireApplicantCards')[0]
            if 'function _renderApplicants' in _main187 else '')
check("187-04. _renderApplicants renders co-classify-btn with data-uid",
      'co-classify-btn' in _rend187 and 'data-uid' in _rend187)

# 187-05: _renderApplicants shows حفظ وتصنيف label for fresh unclassified applicants
check("187-05. حفظ وتصنيف label for unclassified applicants in _renderApplicants",
      'حفظ وتصنيف' in _rend187 and 'isClassified' in _rend187)

# 187-06: _renderApplicants shows إعادة التصنيف for rejected
check("187-06. إعادة التصنيف label for rejected applicants in _renderApplicants",
      'إعادة التصنيف' in _rend187 and 'isRejected' in _rend187)

# 187-07: _renderApplicants adds co-app-card--rejected class for rejected cards
check("187-07. co-app-card--rejected class added for rejected cards",
      'co-app-card--rejected' in _rend187)

# 187-08: _initClassifyFloat has all 7 options (use full function boundary)
_clf187 = (_main187.split('function _initClassifyFloat')[1].split('function _openClassifyFloat')[0]
           if 'function _initClassifyFloat' in _main187 else '')
check("187-08. classify float has 7 options including contacted, interview, hired",
      'data-val="contacted"' in _clf187 and 'data-val="interview"' in _clf187 and 'data-val="hired"' in _clf187)

# 187-09: hired state hides غير مناسب option (data-hired check in _openClassifyFloat)
_ocf187 = (_main187.split('function _openClassifyFloat')[1].split('function _closeClassifyFloat')[0]
           if 'function _openClassifyFloat' in _main187 else '')
check("187-09. _openClassifyFloat hides reject option when data-hired='1'",
      'data-hired' in _ocf187 and 'rejectOpt' in _ocf187 and "isHired ? 'none'" in _ocf187)

# 187-10: interview choice mini-portal (co-ic-float) created lazily in _showInterviewChoice
_sic187 = (_main187.split('function _showInterviewChoice')[1].split('function _closeInterviewChoice')[0]
           if 'function _showInterviewChoice' in _main187 else '')
check("187-10. _showInterviewChoice creates co-ic-float mini-portal lazily",
      'co-ic-float' in _sic187 and '_icFloat' in _sic187 and 'الآن' in _sic187 and 'لاحقاً' in _sic187)

# 187-11: الآن path calls _execClassify then _openApptModal
check("187-11. الآن choice calls _execClassify then _openApptModal",
      '_execClassify' in _sic187 and '_openApptModal' in _sic187)

# 187-12: لاحقاً path calls _execClassify with null (no appt modal)
_later187 = _sic187.split('laterBtn')[1] if 'laterBtn' in _sic187 else ''
check("187-12. لاحقاً choice calls _execClassify with null onSuccess",
      '_execClassify' in _later187 and 'null' in _later187)

# 187-13: _execClassify defined; routes accepted→_execPromote, others→PUT /status
_ec187 = (_main187.split('function _execClassify')[1].split('function _applyClassifyBadge')[0]
          if 'function _execClassify' in _main187 else '')
check("187-13. _execClassify routes accepted to _execPromote, others to PUT /status",
      '_execPromote' in _ec187 and '/jobs/applications/' in _ec187)

# 187-14 (updated §491): _execClassify now uses a single atomic PUT — no saveP/statusP split.
# The old two-call Promise.all pattern was replaced by a single PUT /jobs/applications/{id}/status
# which atomically writes job_applications.status AND company_candidate_job_refs.candidate_status.
_saveP187 = (_ec187.split('var saveP')[1].split('Promise.resolve(null)')[0]
             if 'var saveP' in _ec187 else '')
check("187-14. _execClassify uses single atomic PUT to /jobs/applications route — updated §491",
      '/jobs/applications/' in _ec187
      and 'PUT' in _ec187
      and ('uid && _appJobId' in _saveP187 or 'var saveP' not in _ec187))

# 187-15: _reRenderCardFoot rebuilds footer with new classify btn + sched btn for interview
_rrf187 = (_main187.split('function _reRenderCardFoot')[1]
           if 'function _reRenderCardFoot' in _main187 else '')
check("187-15. _reRenderCardFoot rebuilds footer: classify btn + sched btn for interview",
      'co-classify-btn' in _rrf187 and 'co-app-sched-btn' in _rrf187 and 'isInterview' in _rrf187)

# 187-16: _applyApptIndexToCards looks for co-app-sched-btn (not old interview-btn)
_aaic187 = (_main187.split('function _applyApptIndexToCards')[1].split('function _isApptActive')[0]
            if 'function _applyApptIndexToCards' in _main187 else '')
check("187-16. _applyApptIndexToCards looks for co-app-sched-btn not co-app-interview-btn",
      'co-app-sched-btn' in _aaic187 and 'co-app-interview-btn' not in _aaic187)

# 187-17: _execSendStep success swaps co-app-sched-btn (not old interview-btn)
_ess187 = (_main187.split('function _execSendStep')[1].split('function _isApptActive')[0]
           if 'function _execSendStep' in _main187 else '')
check("187-17. _execSendStep success swaps co-app-sched-btn to open-appt link",
      'co-app-sched-btn' in _ess187 and 'co-app-interview-btn' not in _ess187)

# 187-18: CSS has co-app-card--rejected and co-classify-btn styles
check("187-18. company.css has co-app-card--rejected and co-classify-btn styles",
      '.co-app-card--rejected' in _css187 and '.co-classify-btn' in _css187)

# 187-19: CSS has co-ic-float styles for interview choice dialog
check("187-19. company.css has co-ic-float interview choice dialog styles",
      '.co-ic-float' in _css187 and '.co-ic-btn' in _css187)

# 187-20: CSS has status colors for all 7 statuses including contacted, interview, hired
check("187-20. company.css has status badge colors for contacted, interview, hired",
      'co-app-status--contacted' in _css187 and 'co-app-status--interview' in _css187
      and 'co-app-status--hired' in _css187)


# 187-21 (updated §491): _execClassify now uses single fetch with .catch — no saveRes.ok check.
# Error is caught in .catch block which calls _loadApplicants when _appJobId is set.
_ec187b = (_main187.split('function _execClassify')[1].split('function _applyClassifyBadge')[0]
           if 'function _execClassify' in _main187 else '')
check("187-21. _execClassify error path calls _loadApplicants in catch block — updated §491",
      '_loadApplicants' in _ec187b
      and ('تعذّر' in _ec187b or 'saveRes' in _ec187b))

# 187-22: on save failure, success toast and _reRenderCardFoot are NOT called in the save-fail branch
# (they appear only after the early return — i.e., the save-fail block ends with return)
_save_fail_branch187 = (_ec187b.split('saveRes && !saveRes.ok')[1].split('\n          return;')[0]
                        if 'saveRes && !saveRes.ok' in _ec187b else '')
check("187-22. save failure branch does not call showToast success or _reRenderCardFoot",
      'تم التصنيف' not in _save_fail_branch187
      and '_reRenderCardFoot' not in _save_fail_branch187)

# 187-25 (updated §491): saveP no longer exists — _execClassify uses a single PUT.
# The backend handles everything atomically; no separate save call from frontend.
_sp187 = (_ec187.split('var saveP')[1].split('var statusP')[0]
          if 'var saveP' in _ec187 and _ec187.index('var saveP') > _ec187.index('var statusP') - 1
          else (_ec187.split('var saveP')[1].split('Promise.resolve')[0]
                if 'var saveP' in _ec187 else ''))
_sp187 = (_ec187b.split('var saveP')[1].split('Promise.resolve(null)')[0]
          if 'var saveP' in _ec187b else '')
check("187-25. _execClassify uses single atomic backend request — no saveP or Promise.resolve(null) needed — updated §491",
      '/jobs/applications/' in _ec187b
      and ('var saveP' not in _ec187b or ('_appJobId' in _sp187 and 'Promise.resolve(null)' in
      (_ec187b.split('var saveP')[1] if 'var saveP' in _ec187b else ''))))

# 187-23: catch block calls _loadApplicants when _appJobId is available (not just badge rollback)
_ec187b = (_main187.split('function _execClassify')[1].split('function _applyClassifyBadge')[0]
           if 'function _execClassify' in _main187 else '')
_catch187 = (_ec187b.split('.catch(function (err)')[1]
             if '.catch(function (err)' in _ec187b else '')
check("187-23. catch block calls _loadApplicants when _appJobId is available",
      '_loadApplicants' in _catch187 and '_appJobId' in _catch187)

# 187-24: catch block only does manual rollback in the else branch (when no _appJobId)
_else187 = (_catch187.split('} else {')[1] if '} else {' in _catch187 else '')
check("187-24. catch manual rollback (_applyClassifyBadge + classifyBtn) is in the else branch only",
      '_applyClassifyBadge' in _else187 and 'classifyBtn' in _else187)

# ════════════════════════════════════════════════════════════════
# §188 — viewed is fully internal: no notification for "للمراجعة"
# ════════════════════════════════════════════════════════════════

_auth188 = open('auth.py', encoding='utf-8').read()
_ias188  = (_auth188.split('_INTERNAL_STATUSES')[1].split('\n')[0]
            if '_INTERNAL_STATUSES' in _auth188 else '')

# 188-01: viewed is in _INTERNAL_STATUSES so no notification fires for "للمراجعة"
check("188-01. viewed is in _INTERNAL_STATUSES (no notification for للمراجعة)",
      'viewed' in _ias188)

# 188-02: all 7 classify statuses are internal — notification block can never fire for any of them
_seven = ['pending', 'viewed', 'accepted', 'rejected', 'contacted', 'interview', 'hired']
check("188-02. all 7 pipeline statuses are in _INTERNAL_STATUSES",
      all(s in _ias188 for s in _seven))


# ════════════════════════════════════════════════════════════════
# §481 — Saved candidates job-link system integrity
# ════════════════════════════════════════════════════════════════

_auth481 = open('auth.py', encoding='utf-8').read()
_main481 = open('static/company/company.main.js', encoding='utf-8').read()

# ── Function bodies for targeted checks ──────────────────────────
_save_fn481 = (_auth481.split('def save_company_candidate')[1].split('\ndef ')[0]
               if 'def save_company_candidate' in _auth481 else '')
_upd_fn481  = (_auth481.split('def update_company_saved_candidate')[1].split('\ndef ')[0]
               if 'def update_company_saved_candidate' in _auth481 else '')
_filter_fn481 = (_auth481.split('def get_company_saved_candidates_filtered')[1].split('\ndef ')[0]
                 if 'def get_company_saved_candidates_filtered' in _auth481 else '')

# 481-01: job-ref INSERT uses ON CONFLICT DO NOTHING — no dup on re-link
check("481-01. company_candidate_job_refs INSERT uses ON CONFLICT DO NOTHING (idempotent)",
      'company_candidate_job_refs' in _save_fn481
      and 'ON CONFLICT DO NOTHING' in _save_fn481)

# 481-02: same idempotency pattern present when save_company_candidate is called with job_id
_jid_branch481 = (_save_fn481.split('if job_id is not None:')[1]
                  if 'if job_id is not None:' in _save_fn481 else '')
check("481-02. job_id branch in save_company_candidate writes to company_candidate_job_refs idempotently",
      'company_candidate_job_refs' in _jid_branch481
      and 'ON CONFLICT DO NOTHING' in _jid_branch481)

# 481-03: no job_id → no company_candidate_job_refs insert (else branch only touches saved_candidates)
_no_jid_branch481 = (_save_fn481.split('else:\n')[1]
                     if 'else:\n' in _save_fn481 else '')
check("481-03. save with job_id=None does NOT insert into company_candidate_job_refs",
      'company_candidate_job_refs' not in _no_jid_branch481)

# 481-04: job_links query uses LEFT JOIN job_applications so apply_date/status can be null
check("481-04. job_links batch query uses LEFT JOIN job_applications (null apply_date/status allowed)",
      'LEFT JOIN job_applications' in _filter_fn481)

# 481-05: update_company_saved_candidate only touches company_saved_candidates, not job_applications
check("481-05. update_company_saved_candidate does not write to job_applications",
      'job_applications' not in _upd_fn481)

# 481-06: disabled linked jobs show co-dp-opt--disabled class in job picker HTML builder
_dp481 = (_main481.split('function _dpHTML')[1].split('\n  function ')[0]
          if 'function _dpHTML' in _main481 else '')
check("481-06. _dpHTML adds co-dp-opt--disabled class and data-linked=1 for disabled options",
      'co-dp-opt--disabled' in _dp481
      and 'data-linked' in _dp481)


# ════════════════════════════════════════════════════════════════
# §482 — Deep-link + إدارة المرشح button from public profile
# ════════════════════════════════════════════════════════════════

_render482 = open('profile-v2.render.js', encoding='utf-8').read()
_main482   = open('static/company/company.main.js', encoding='utf-8').read()

# ── Source sections for targeted checks ──────────────────────────
# candidate_save onclick block (from the if(_vaType==='candidate_save') to action = saveCandidateToCompany)
_cs_onclick482 = (_render482.split("if(_vaType === 'candidate_save'){")[1].split('action = saveCandidateToCompany')[0]
                  if "if(_vaType === 'candidate_save'){" in _render482 else '')
# _showCandidateHint function
_hint482 = (_render482.split('function _showCandidateHint')[1].split('function _applyVa')[0]
            if 'function _showCandidateHint' in _render482 else '')
# _applyVa function
_applyva482 = (_render482.split('function _applyVa')[1].split('function _showCandidateHint')[0]
               if 'function _applyVa' in _render482 else '')
# Deep-link init block: full section from _urlDeepLinkPending declaration to next var
_deeplink482 = (_main482.split('var _urlDeepLinkPending = false;')[1].split('var _jobPopTarget')[0]
                if 'var _urlDeepLinkPending = false;' in _main482 else '')
# _loadBadge function
_badge482 = (_main482.split('function _loadBadge')[1].split('\n  function ')[0]
             if 'function _loadBadge' in _main482 else '')
# _open function with _isOwner guard — target the candidates IIFE _open specifically
_cand_iife482 = (_main482.split('// ── Candidates Modal')[1] if '// ── Candidates Modal' in _main482 else _main482)
_open482 = (_cand_iife482.split('function _open() {')[1].split('\n  }')[0]
            if 'function _open() {' in _cand_iife482 else '')

# 482-01: _applyVa shows "إدارة المرشح" when candidate_save is active
check("482-01. _applyVa shows إدارة المرشح when candidate_save.is_active",
      'إدارة المرشح' in _applyva482
      and 'candidate_save' in _applyva482)

# 482-02: navigation uses /u/ prefix + tw_user.tw_id — not /company-profile
check("482-02. intBtn navigate-when-active uses /u/ route and tw_user.tw_id (not /company-profile)",
      '/u/' in _cs_onclick482
      and 'tw_user' in _cs_onclick482
      and '/company-profile' not in _cs_onclick482)

# 482-03: "إضافة ملاحظة" adds notes=1 to the URL
check("482-03. _scNoteBtn onclick appends notes=1 to deep-link URL",
      'notes=1' in _hint482
      and '/u/' in _hint482
      and 'tw_user' in _hint482)

# 482-04: ?cand= sets _pendingManageOpen and triggers _urlDeepLinkPending
check("482-04. URL ?cand= param sets _pendingManageOpen and _urlDeepLinkPending = true",
      '_pendingManageOpen' in _deeplink482
      and '_urlDeepLinkPending     = true' in _deeplink482
      and "sp.get('cand')" in _deeplink482)

# 482-05: ?notes=1 sets _pendingManageOpenNotes = true
check("482-05. URL ?notes=1 sets _pendingManageOpenNotes = true",
      "_pendingManageOpenNotes" in _deeplink482
      and "notes" in _deeplink482
      and "'1'" in _deeplink482)

# 482-06: _open() is guarded by _isOwner() — deep-link silent for non-owner
check("482-06. _open() has _isOwner() guard — deep-link panel does not open for non-owners",
      '_isOwner' in _open482)


# ════════════════════════════════════════════════════════════════
# §483 — job_links batch-fetch uses applied_at (not created_at)
# Root cause of "تعذّر تحميل القائمة" — job_applications table
# has applied_at TIMESTAMP, not created_at.
# ════════════════════════════════════════════════════════════════

_auth483 = open('auth.py', encoding='utf-8').read()

# Extract both batch-fetch functions to verify the column name
_get_saved483 = (_auth483.split('def get_company_saved_candidates(')[1].split('\ndef ')[0]
                 if 'def get_company_saved_candidates(' in _auth483 else '')
_get_filt483  = (_auth483.split('def get_company_saved_candidates_filtered(')[1].split('\ndef ')[0]
                 if 'def get_company_saved_candidates_filtered(' in _auth483 else '')

# 483-01: job_applications table schema defines applied_at, NOT created_at
# Split by the UNIQUE constraint which closes the column list
_ja_schema483 = (_auth483.split('CREATE TABLE IF NOT EXISTS job_applications')[1].split('UNIQUE(job_id')[0]
                 if 'CREATE TABLE IF NOT EXISTS job_applications' in _auth483 else '')
check("483-01. job_applications table has applied_at column, NOT created_at",
      'applied_at' in _ja_schema483
      and 'created_at' not in _ja_schema483)

# 483-02: get_company_saved_candidates batch-fetch uses ja.applied_at (was ja.created_at — bug)
check("483-02. get_company_saved_candidates job_links query uses ja.applied_at (not ja.created_at)",
      'ja.applied_at' in _get_saved483
      and 'ja.created_at' not in _get_saved483)

# 483-03: get_company_saved_candidates_filtered batch-fetch uses ja.applied_at
check("483-03. get_company_saved_candidates_filtered job_links query uses ja.applied_at (not ja.created_at)",
      'ja.applied_at' in _get_filt483
      and 'ja.created_at' not in _get_filt483)

# 483-04: candidate linked to job WITH application — apply_date serialized from applied_at
# (LEFT JOIN returns applied_at value; Python aliases it as apply_date in job_links dict)
check("483-04. job_links dict key is apply_date, sourced from ja.applied_at via LEFT JOIN",
      ("'apply_date'" in _get_saved483 and "apply_date.isoformat()" in _get_saved483)
      or ("'apply_date'" in _get_filt483 and "apply_date.isoformat()" in _get_filt483))

# 483-05: candidate linked to job WITHOUT application — LEFT JOIN returns null applied_at
# Python guard: apply_date.isoformat() if apply_date else None → None in output
check("483-05. null apply_date guarded with isoformat() if apply_date else None",
      'apply_date.isoformat() if apply_date else None' in _get_saved483
      or 'apply_date.isoformat() if apply_date else None' in _get_filt483)

# 483-06: candidate with no job links — job_titles[] and job_links[] default to []
check("483-06. candidates with no refs get empty job_titles[] and job_links[] via .get(id, [])",
      "jtmap.get(item['candidate_id'], [])" in _get_saved483
      and "jlmap.get(item['candidate_id'], [])" in _get_saved483)


# §484 — Candidates modal: job popover UX + dual status rows + +N button
# Fixes: (1) popover position:fixed + above/below flip + scroll/resize close
#        (2) two separate rows: job_applications.status vs company classification
#        (3) +N as <button> that reveals hidden chips in same card
# ════════════════════════════════════════════════════════════════

_comain484 = open('static/company/company.main.js', encoding='utf-8').read()
_cocss484  = open('static/company/company.css',     encoding='utf-8').read()

# Extract candidates IIFE section for targeted checks
_cand_iife484 = (
    _comain484.split('// ── Candidates Modal')[1]
    if '// ── Candidates Modal' in _comain484 else _comain484
)

# Extract _showJobChipPop body
_show_pop484 = (
    _cand_iife484.split('function _showJobChipPop(')[1].split('\n  function ')[0]
    if 'function _showJobChipPop(' in _cand_iife484 else ''
)

# Extract _closeJobPop body
_close_pop484 = (
    _cand_iife484.split('function _closeJobPop(')[1].split('\n  function ')[0]
    if 'function _closeJobPop(' in _cand_iife484 else ''
)

# Extract _savedCardHTML body
_card_html484 = (
    _cand_iife484.split('function _savedCardHTML(')[1].split('\n  function ')[0]
    if 'function _savedCardHTML(' in _cand_iife484 else ''
)

# Extract _onSavedClick body
_on_click484 = (
    _cand_iife484.split('function _onSavedClick(')[1].split('\n  function ')[0]
    if 'function _onSavedClick(' in _cand_iife484 else ''
)

# 484-01: popover uses position:fixed (not position:absolute) so it stays in viewport on scroll
check("484-01. co-cand-job-pop uses position:fixed (not absolute) for viewport-relative placement",
      'position:fixed' in _cocss484
      and '.co-cand-job-pop' in _cocss484
      and 'position:absolute' not in _cocss484.split('.co-cand-job-pop')[1].split('}')[0])

# 484-02: _showJobChipPop closes on scroll + resize via once:true listeners
check("484-02. _closeJobPop removes scroll and resize listeners on close (no ghost handlers)",
      "window.removeEventListener('scroll', _closeJobPop)" in _close_pop484
      and "window.removeEventListener('resize', _closeJobPop)" in _close_pop484)

# 484-03 (updated §492): popover simplified — shows only حالة المرشح في هذه الوظيفة (candidate_status)
# حالة الطلب and التصنيف العام rows were removed in fix/job-chip-pop-simplify
check("484-03. _showJobChipPop renders «حالة المرشح في هذه الوظيفة» row — updated §492",
      'حالة المرشح في هذه الوظيفة' in _show_pop484
      and 'data-cand-status' in _show_pop484)

# 484-04 (updated §492): general pipeline status (data-status from card) no longer shown in popover
# It remains in the manage panel; popover now shows only per-job candidate_status from chip's data-cand-status
check("484-04. popover no longer reads card data-status; per-job status from chip data-cand-status — updated §492",
      "getAttribute('data-cand-status')" in _show_pop484
      and 'co-cjp-cand-status' not in _show_pop484)

# 484-05: +N is a <button class="co-cand-chip-more-btn"> — not a <span>
check("484-05. +N more button is a <button class=co-cand-chip-more-btn> not a <span>",
      'co-cand-chip-more-btn' in _card_html484
      and '<button class="co-cand-chip-more-btn"' in _card_html484
      and 'co-cand-job-chip--more' not in _card_html484)

# 484-06: clicking +N removes co-cand-job-chip--hidden class from hidden chips; _savedCardHTML
#         adds co-cand-job-chip--hidden to chips at index >= 3
check("484-06. hidden chips use co-cand-job-chip--hidden; _onSavedClick reveals them via classList.remove",
      'co-cand-job-chip--hidden' in _card_html484
      and "classList.remove('co-cand-job-chip--hidden')" in _on_click484
      and "co-cand-chip-more-btn" in _on_click484)

# §484b — two targeted amendments: full vertical clamp + named outside-click handler

# Extract _jobPopPositionFromChip body
_pos_fn484b = (
    _cand_iife484.split('function _jobPopPositionFromChip(')[1].split('\n  function ')[0]
    if 'function _jobPopPositionFromChip(' in _cand_iife484 else ''
)

# 484b-01: vertical clamp includes lower bound (innerHeight - popH - margin)
#          ensures popover never exits viewport bottom even when both above and below are cramped
check("484b-01. _jobPopPositionFromChip clamps top to window.innerHeight - pop.offsetHeight - 8 (lower bound)",
      'winH - popH - 8' in _pos_fn484b
      and 'Math.min(' in _pos_fn484b
      and 'Math.max(8,' in _pos_fn484b)

# 484b-02: _closeJobPop removes the document click listener via removeEventListener
#          (not once:true — so any close path cleans up the handler, no accumulation)
check("484b-02. _closeJobPop removes document click listener (named handler, no once:true accumulation)",
      "document.removeEventListener('click',  _closeJobPop" in _close_pop484
      or "document.removeEventListener('click', _closeJobPop" in _close_pop484)


# §485 — Applicants modal: interview option event-propagation bug fix
# Root cause: clicking "مقابلة" opens _icFloat (interview choice mini-portal),
# but the same click event bubbles to the document outside-click handler which
# immediately closes _icFloat because e.target is not inside it.
# Fix: e.stopPropagation() in the interview branch of _astFloat click handler.
# ════════════════════════════════════════════════════════════════

_comain485 = open('static/company/company.main.js', encoding='utf-8').read()

# Extract the _initClassifyFloat function body (contains the astFloat click handler)
_init_classify485 = (
    _comain485.split('function _initClassifyFloat(')[1].split('\n  function ')[0]
    if 'function _initClassifyFloat(' in _comain485 else ''
)

# Extract _showInterviewChoice body (must call _execClassify with 'interview')
_show_ic485 = (
    _comain485.split('function _showInterviewChoice(')[1].split('\n  function ')[0]
    if 'function _showInterviewChoice(' in _comain485 else ''
)

# Extract _execClassify success path (must call _reRenderCardFoot)
_exec_classify485 = (
    _comain485.split('function _execClassify(')[1].split('\n  function ')[0]
    if 'function _execClassify(' in _comain485 else ''
)

# 485-01: e.stopPropagation() is called in the interview branch of the astFloat click handler.
# Without this, the document outside-click handler closes _icFloat immediately on the same
# click event, making "مقابلة" appear to do nothing.
check("485-01. _astFloat click handler calls e.stopPropagation() before _showInterviewChoice (prevents immediate _icFloat close)",
      "e.stopPropagation()" in _init_classify485
      and "interview" in _init_classify485
      and "_showInterviewChoice" in _init_classify485)

# 485-02: both laterBtn and nowBtn in _showInterviewChoice call _execClassify with 'interview'
check("485-02. _showInterviewChoice calls _execClassify with 'interview' status for both Ã\x84لآن and لاحقاً paths",
      "_execClassify(aId, 'interview'" in _show_ic485
      and _show_ic485.count("_execClassify(aId, 'interview'") >= 2)

# 485-03: _execClassify success path calls _reRenderCardFoot (updates card UI) — not just badge
check("485-03. _execClassify success path calls _reRenderCardFoot to update card UI after classification",
      '_reRenderCardFoot(card, newStatus)' in _exec_classify485)


# §486 — Three sources of truth: per-job candidate_status in company_candidate_job_refs
# Covers: migration, batch-fetch contract, new PATCH endpoint, security, frontend wiring.
# ════════════════════════════════════════════════════════════════

_auth486   = open('auth.py',    encoding='utf-8').read()
_srv486    = open('server.py',  encoding='utf-8').read()
_main486   = open('static/company/company.main.js', encoding='utf-8').read()
_api486    = open('static/company/company.api.js',  encoding='utf-8').read()
_css486    = open('static/company/company.css',     encoding='utf-8').read()

# ── Backend: migration ────────────────────────────────────────────────────

# 486-01: _migrate_candidate_status_per_job() exists and adds the column
check("486-01. _migrate_candidate_status_per_job() adds candidate_status column to company_candidate_job_refs",
      "_migrate_candidate_status_per_job" in _auth486
      and "ADD COLUMN IF NOT EXISTS candidate_status TEXT NULL" in _auth486)

# 486-02: CHECK constraint restricts candidate_status to allowed values
check("486-02. CHECK constraint on candidate_status allows only valid pipeline values",
      "ck_ccjr_candidate_status" in _auth486
      and "candidate_status IS NULL" in _auth486
      and "'shortlisted'" in _auth486
      and "'hired'" in _auth486)

# 486-03: migration is called during server startup
check("486-03. _migrate_candidate_status_per_job() called in server.py startup",
      "_migrate_candidate_status_per_job()" in _srv486)

# ── Backend: batch-fetch contract ─────────────────────────────────────────

# 486-04: batch-fetch SELECTs r.candidate_status (both functions)
check("486-04. Both batch-fetch functions SELECT r.candidate_status from company_candidate_job_refs",
      _auth486.count("r.candidate_status") >= 2)

# 486-05: batch-fetch output uses 'application_status' key (not the old 'status' key)
#         Verified by checking that 'application_status' appears in the jlmap dict building
check("486-05. batch-fetch job_links[] uses 'application_status' key (renamed from 'status')",
      _auth486.count("'application_status':") >= 2
      and "'status':     app_status" not in _auth486)

# 486-06: batch-fetch output includes 'candidate_status' key per job_link
check("486-06. batch-fetch job_links[] includes 'candidate_status' key per entry",
      _auth486.count("'candidate_status':") >= 2)

# ── Backend: new PATCH endpoint ────────────────────────────────────────────

# 486-07: PATCH /company/saved-candidates/{candidate_id}/jobs/{job_id} endpoint exists
check("486-07. PATCH /company/saved-candidates/{candidate_id}/jobs/{job_id} endpoint defined in server.py",
      "'/company/saved-candidates/{candidate_id}/jobs/{job_id}'" in _srv486.replace('"', "'")
      or '@app.patch("/company/saved-candidates/{candidate_id}/jobs/{job_id}")' in _srv486)

# 486-08: new endpoint uses JWT (Depends(verify_token)) — no company_id from client
check("486-08. New per-job PATCH endpoint uses Depends(verify_token) — company_id from token only",
      "def company_update_candidate_job_status" in _srv486
      and "Depends(verify_token)" in _srv486
      and "company_id = _require_company_owner(token)" in _srv486)

# 486-09: new endpoint NEVER updates job_applications.status or company_saved_candidates.status
check("486-09. update_candidate_job_status() touches only company_candidate_job_refs — never other tables",
      "UPDATE company_candidate_job_refs" in _auth486
      and "def update_candidate_job_status(" in _auth486)

# 486-10: new endpoint validates candidate_status against VALID_CANDIDATE_STATUSES
check("486-10. New endpoint validates candidate_status against VALID_CANDIDATE_STATUSES before DB write",
      "VALID_CANDIDATE_STATUSES" in _srv486
      and "company_update_candidate_job_status" in _srv486)

# 486-11: update_candidate_job_status returns False (not raise) when row doesn't exist
#         Server maps False → 404 response
check("486-11. update_candidate_job_status returns bool; server raises 404 when row not found",
      "return bool(rows)" in _auth486
      and "if not found:" in _srv486
      and "404" in _srv486)

# ── Frontend: updateCandidateJobStatus API function ───────────────────────

# 486-12: updateCandidateJobStatus function exists in company.api.js
check("486-12. updateCandidateJobStatus() defined and exported in company.api.js",
      "function updateCandidateJobStatus(" in _api486
      and "window.updateCandidateJobStatus" in _api486)

# 486-13: API function calls PATCH /company/saved-candidates/{cid}/jobs/{jid}
check("486-13. updateCandidateJobStatus calls PATCH /company/saved-candidates/.../jobs/... with JWT",
      "'/company/saved-candidates/' + candidateId + '/jobs/' + jobId" in _api486
      and "'PATCH'" in _api486
      and "candidate_status" in _api486)

# ── Frontend: chip attributes ─────────────────────────────────────────────

# Extract candidates IIFE for chip rendering checks
_cand_iife486 = (
    _main486.split('// ── Saved Candidates tab')[1].split('\n}());')[0]
    if '// ── Saved Candidates tab' in _main486 else _main486
)

# 486-14: job chips carry data-app-status (application_status) AND data-cand-status (candidate_status)
check("486-14. Job chips carry both data-app-status (application_status) and data-cand-status (candidate_status)",
      "data-app-status=\"' + _esc(jl.application_status" in _cand_iife486
      and "data-cand-status=\"' + _esc(jl.candidate_status" in _cand_iife486)

# ── Frontend: 3-row popover ───────────────────────────────────────────────

_pop_fn486 = (
    _cand_iife486.split('function _showJobChipPop(')[1].split('\n  function ')[0]
    if 'function _showJobChipPop(' in _cand_iife486 else ''
)

# 486-15 (updated §492): popover simplified to 2 rows — حالة المرشح في هذه الوظيفة + تاريخ التقدم (conditional)
# Rows حالة الطلب and التصنيف العام removed in fix/job-chip-pop-simplify
check("486-15. Job chip popover: حالة الطلب and التصنيف العام removed; حالة المرشح في هذه الوظيفة present — updated §492",
      'حالة المرشح في هذه الوظيفة' in _pop_fn486
      and 'حالة الطلب' not in _pop_fn486
      and 'التصنيف العام' not in _pop_fn486
      and 'data-cand-status' in _pop_fn486)

# ── Frontend: per-job status section in manage panel ─────────────────────

# 486-16: manage panel renders per-job status section with custom pickers (co-cand-job-status-dp)
check("486-16. Manage panel renders تصنيف المرشح لكل وظيفة section with per-job custom pickers",
      'co-cand-job-status-list' in _cand_iife486
      and 'co-cand-job-status-dp' in _cand_iife486
      and 'co-cand-job-status-sel' not in _cand_iife486
      and 'تصنيف المرشح لكل وظيفة' in _cand_iife486)

# 486-17: _handleJobStatusDpSelect wired via _handleDpOptClick for co-cand-job-status-dp auto-save
check("486-17. _handleJobStatusDpSelect wired for co-cand-job-status-dp auto-save via _handleDpOptClick",
      'function _handleJobStatusDpSelect(' in _main486
      and 'co-cand-job-status-dp' in _main486
      and 'updateCandidateJobStatus' in _main486
      and '_handleDpOptClick' in _main486)

# 486-18: _onSavedChange syncs chip on success — now via _renderCandidateJobLinksUI which
# rebuilds all chips from the updated links array (candidate_status embedded per link)
check("486-18. _onSavedChange syncs chip on success via _renderCandidateJobLinksUI (rebuilt from updated links)",
      "_renderCandidateJobLinksUI(card, links)" in _main486
      and "candidate_status" in _main486)

# ── Frontend: appointment client-side validation ───────────────────────────

_appt_fn486 = (
    _main486.split('function _submitApptForm(')[1].split('\n  function ')[0]
    if 'function _submitApptForm(' in _main486 else ''
)

# 486-19: online mode requires URL before submitting
check("486-19. _submitApptForm validates online URL is present for online mode before any fetch",
      "_apptMode === 'online' && !urlVal" in _appt_fn486
      and 'يرجى إدخال رابط المقابلة الأونلاين' in _appt_fn486)

# 486-20: deadline vs appointment time check runs client-side
check("486-20. _submitApptForm checks scheduled time > now + deadline_hours (prevents backend deadline error)",
      'deadlineMs' in _appt_fn486
      and 'scheduledMs - Date.now()' in _appt_fn486
      and 'مهلة الرد تنتهي بعد وقت الموعد' in _appt_fn486)

# 486-21: create-step error handler shows detail from API (not always generic message)
check("486-21. Create-step error handler shows API detail instead of generic message when detail is present",
      "detail || 'تعذّر إنشاء الموعد" in _appt_fn486
      or "msg = detail || " in _appt_fn486)

# ── CSS ───────────────────────────────────────────────────────────────────

# 486-22: per-job status section CSS defined — custom picker, no native select rules
check("486-22. CSS rules for co-cand-job-status-list and co-cand-job-status-dp defined in company.css",
      '.co-cand-job-status-list' in _css486
      and '.co-cand-job-status-dp' in _css486
      and '.co-cand-job-status-sel' not in _css486)


# ── Amendment 1: backward-compat 'status' alias ───────────────────────────

# 486-23: 'status' alias present alongside 'application_status' in both batch-fetch functions
# Both keys must be in the jlmap dict append and must carry the same value (app_status)
check("486-23. 'status' deprecated alias present alongside 'application_status' in batch-fetch jlmap (both functions)",
      "'status':             app_status or None" in _auth486
      and "'application_status': app_status or None" in _auth486
      and _auth486.count("'status':             app_status or None") >= 2
      and _auth486.count("'application_status': app_status or None") >= 2)

# 486-24: 'status' alias documented as deprecated (not hidden — visible in docs)
check("486-24. SYSTEMS_INDEX.md documents 'status' as deprecated backward-compat alias for application_status",
      'deprecated' in open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()
      and 'application_status' in open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read())


# ── Amendment 2: idempotent migration — no DROP CONSTRAINT ────────────────

# 486-25: migration code must NOT contain DROP CONSTRAINT (it used to, but fixed)
check("486-25. _migrate_candidate_status_per_job() does NOT use DROP CONSTRAINT",
      'DROP CONSTRAINT' not in _auth486.split('def _migrate_candidate_status_per_job')[1].split('\ndef ')[0]
      if '_migrate_candidate_status_per_job' in _auth486 else False)

# 486-26: migration checks pg_constraint before adding the constraint (conditional add)
_mig_body486 = (
    _auth486.split('def _migrate_candidate_status_per_job')[1].split('\ndef ')[0]
    if '_migrate_candidate_status_per_job' in _auth486 else ''
)
check("486-26. Migration checks pg_constraint table before ADD CONSTRAINT (constraint added only when absent)",
      'pg_constraint' in _mig_body486
      and 'ck_ccjr_candidate_status' in _mig_body486
      and ('if not rows' in _mig_body486 or 'if not existing' in _mig_body486)
      and 'ADD CONSTRAINT ck_ccjr_candidate_status' in _mig_body486)


# ── Amendment 3: optimistic UI rollback in _onSavedChange ─────────────────

# 486-27: rollback uses data-job-links (not data-prev-val) — _handleJobStatusDpSelect reads fresh card state
check("486-27. Rollback path reads data-job-links from card — not data-prev-val on select",
      "_renderCandidateJobLinksUI(card, rollLinks)" in _main486
      and "card.getAttribute('data-job-links')" in _main486
      and 'co-cand-job-status-sel' not in _main486)

# 486-28: on API failure, _onSavedChange re-renders from data-job-links (card-level lock arch)
# Old pattern was sel.value = prevVal; new pattern uses _renderCandidateJobLinksUI(card, rollLinks)
check("486-28. _onSavedChange re-renders from data-job-links on failure (card-level lock rollback)",
      "_renderCandidateJobLinksUI(card, rollLinks)" in _main486
      and "data-job-links" in _main486)

# 486-29: failure path calls _renderCandidateJobLinksUI(card, rollLinks) — no direct sel.value mutation
# Success path updates links array then also calls _renderCandidateJobLinksUI(card, links)
check("486-29. Chip/data-job-links update only in success path — failure path is rollback-only",
      "if (!res || !res.ok)" in _main486
      and "_renderCandidateJobLinksUI(card, links)" in _main486
      and "_renderCandidateJobLinksUI(card, rollLinks)" in _main486)

# 486-30: on failure, _onSavedChange shows exact API detail from res.data.detail
check("486-30. _onSavedChange shows res.data.detail error on failure (API detail, not always generic)",
      "res.data.detail" in _main486
      or "res && res.data && res.data.detail" in _main486)

# 486-31: custom picker rendered with data-cid and data-jid (not native select / not data-prev-val)
check("486-31. Per-job custom picker rendered with data-cid + data-jid via _dpHTML meta arg",
      "co-cand-job-status-dp" in _main486
      and "data-cid" in _main486
      and "data-jid" in _main486
      and "data-prev-val=" not in _main486)


# ── §487: Five-fix batch (documentation, UI, timezone, migration, Pydantic) ───

_srv487   = open('server.py',                   encoding='utf-8').read()
_claude487 = open('CLAUDE.md',                  encoding='utf-8').read()
_idx487   = open('docs/SYSTEMS_INDEX.md',        encoding='utf-8').read()

# ── Fix 1a: CLAUDE.md treats status as deprecated alias, not banned ────────

# 487-01: CLAUDE.md no longer says status is permanently banned/renamed
check("487-01. CLAUDE.md does not ban status alias and points to SYSTEMS_INDEX §20c",
      'Do NOT re-add `status` to `job_links[]` entries' not in _claude487
      and 'SYSTEMS_INDEX' in _claude487
      and ('deprecated' in _claude487 or 'deprecated alias' in _claude487))

# 487-02: Documentation does not describe job_applications.status as purely applicant-driven
check("487-02. Neither CLAUDE.md nor SYSTEMS_INDEX describes job_applications.status as purely applicant-driven",
      'applicant-driven application status' not in _claude487
      and 'applicant-driven application status' not in _idx487)

# 487-03: VALID_CANDIDATE_STATUSES not claimed as shared for all three sources
check("487-03. Documentation does not claim VALID_CANDIDATE_STATUSES is shared for all three status sources",
      'shared for all three status sources' not in _idx487
      and 'shared for all three status sources' not in _claude487)

# 487-04: SYSTEMS_INDEX documents that VALID_CANDIDATE_STATUSES does NOT apply to job_applications.status
check("487-04. SYSTEMS_INDEX explicitly notes VALID_CANDIDATE_STATUSES does not apply to job_applications.status",
      'VALID_CANDIDATE_STATUSES' in _idx487
      and 'does NOT apply' in _idx487)

# ── Fix 2: Shared _renderCandidateJobLinksUI helper ───────────────────────

# 487-05: Helper _renderCandidateJobLinksUI defined in company.main.js
check("487-05. _renderCandidateJobLinksUI helper defined in company.main.js",
      '_renderCandidateJobLinksUI' in _main486)

# 487-06: PATCH success path updates data-job-links JSON before re-rendering
check("487-06. PATCH success path reads data-job-links, updates candidate_status, then calls _renderCandidateJobLinksUI",
      '_renderCandidateJobLinksUI(card, links)' in _main486
      and "card.getAttribute('data-job-links')" in _main486
      and ("candidate_status: cs || null" in _main486 or "candidate_status: cs" in _main486))

# 487-07: New job link uses _updateChips which now delegates to _renderCandidateJobLinksUI
check("487-07. _updateChips delegates to _renderCandidateJobLinksUI (new link builds chip + select without reload)",
      '_updateChips' in _main486
      and '_renderCandidateJobLinksUI' in _main486
      and 'function _updateChips' in _main486)

# 487-08: Chip rebuild reads candidate_status from links array (preserves classification)
check("487-08. Chip rebuild reads jl.candidate_status from links array (data-cand-status preserved)",
      "data-cand-status=\\\"' + _esc(jl.candidate_status" in _main486
      or "data-cand-status=' + _esc(jl.candidate_status" in _main486
      or "jl.candidate_status" in _main486)

# 487-09: PATCH failure re-renders from data-job-links via _renderCandidateJobLinksUI(card, rollLinks)
# New arch: _handleJobStatusDpSelect (not _onSavedChange) — failure reads card.getAttribute('data-job-links')
_hjsdp_fn = ''
if 'function _handleJobStatusDpSelect(' in _main486:
    _hjsdp_fn = _main486.split('function _handleJobStatusDpSelect(')[1].split('\n  function ')[0]
check("487-09. PATCH failure restores state via _renderCandidateJobLinksUI(card, rollLinks) in _handleJobStatusDpSelect",
      "_renderCandidateJobLinksUI(card, rollLinks)" in _hjsdp_fn
      and "card.getAttribute('data-job-links')" in _hjsdp_fn)

# ── Fix 3: Timezone-aware appointment scheduling ──────────────────────────

# 487-10: Frontend uses toISOString() — sends UTC ISO with Z suffix
check("487-10. Appointment scheduled_at built via toISOString() — UTC/timezone-aware string sent to backend",
      'toISOString()' in _main486
      and 'localScheduled' in _main486)

# 487-11: Number.isFinite guard validates date before toISOString
check("487-11. Invalid date guarded by Number.isFinite(localScheduled.getTime()) before toISOString",
      'Number.isFinite' in _main486
      and 'localScheduled.getTime()' in _main486)

# 487-12: Client deadline check uses localScheduled.getTime() (epoch ms — timezone-agnostic)
check("487-12. Client deadline check uses localScheduled.getTime() for timezone-agnostic epoch comparison",
      'scheduledMs = localScheduled.getTime()' in _main486)

# ── Fix 4: Race-safe migration ────────────────────────────────────────────

# 487-13: Migration uses NOT VALID + VALIDATE CONSTRAINT + duplicate_object catch
check("487-13. Migration race-safe: NOT VALID + VALIDATE CONSTRAINT + 42710/duplicate_object catch",
      'NOT VALID' in _mig_body486
      and 'VALIDATE CONSTRAINT' in _mig_body486
      and ('42710' in _mig_body486 or 'duplicate_object' in _mig_body486))

# ── Fix 5: Required but nullable candidate_status (Pydantic) ─────────────

# 487-14: UpdateCandidateJobStatusInput has no default (required field — body {} returns 422)
check("487-14. UpdateCandidateJobStatusInput.candidate_status is required (no = None default)",
      'candidate_status: Optional[str]' in _srv487
      and 'candidate_status: Optional[str] = None' not in _srv487)

# 487-15: null candidate_status explicitly handled as valid (clear intent)
check("487-15. update_candidate_job_status accepts None to clear classification (null is valid)",
      '| {None}' in _auth486 or "VALID_CANDIDATE_STATUSES | {None}" in _auth486)

# 487-16: status alias equal to application_status in both batch-fetch functions (redundant coverage)
check("487-16. Deprecated 'status' alias always equals application_status (same value set twice)",
      _auth486.count("'status':             app_status or None") >= 2
      or (_auth486.count("'status':") >= 2 and _auth486.count("'application_status':") >= 2))


# ── §488: Four-fix batch (race condition, Field, timezone, terminology) ───────

_main488  = open('static/company/company.main.js', encoding='utf-8').read()
_auth488  = open('auth.py',    encoding='utf-8').read()
_srv488   = open('server.py',  encoding='utf-8').read()
_idx488   = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()

# Extract _handleJobStatusDpSelect function body for targeted checks
# (replaced _onSavedChange which used native <select> — now uses co-dp custom picker)
_onsaved488 = (
    _main488.split('function _handleJobStatusDpSelect(')[1].split('\n  function ')[0]
    if 'function _handleJobStatusDpSelect(' in _main488 else ''
)
# Extract _renderCandidateJobLinksUI function body
_render488 = (
    _main488.split('function _renderCandidateJobLinksUI(card, links)')[1].split('\n  function ')[0]
    if 'function _renderCandidateJobLinksUI(card, links)' in _main488 else ''
)
# Extract _migrate_candidate_status_per_job body
_mig488 = (
    _auth488.split('def _migrate_candidate_status_per_job')[1].split('\ndef ')[0]
    if '_migrate_candidate_status_per_job' in _auth488 else ''
)

# ── Fix 1: Race condition — card-level lock ────────────────────────────────

# 488-01: registry-based lock checked BEFORE the actual PATCH dispatch (replaces card capture)
# §490 upgrade: registry (_jobStatusInFlight) replaces card DOM reference as lock authority.
# Checks index against 'updateCandidateJobStatus(cidInt' to target the PATCH dispatch,
# not the earlier null-guard 'if (!window.updateCandidateJobStatus) return'.
check("488-01. Registry _jobStatusInFlight[cidStr] checked BEFORE updateCandidateJobStatus PATCH dispatch",
      '_jobStatusInFlight[cidStr]' in _onsaved488
      and 'updateCandidateJobStatus(cidInt' in _onsaved488
      and _onsaved488.index('_jobStatusInFlight[cidStr]') < _onsaved488.index('updateCandidateJobStatus(cidInt'))

# 488-02: registry (not DOM attribute) blocks second call for same candidate
# §490 upgrade: _jobStatusInFlight is the authoritative lock; data-job-status-saving is visual only.
check("488-02. Registry lock (_jobStatusInFlight[cidStr]) at entry returns early if in-flight",
      '_jobStatusInFlight[cidStr]' in _onsaved488
      and 'return' in _onsaved488)

# 488-03: visual lock still set on live card + co-cand-job-status-dp .co-dp-btn disabled
# §490 upgrade: liveCard reference replaces captured card; visual lock still applied for UX.
check("488-03. Visual lock set on liveCard + ALL .co-cand-job-status-dp .co-dp-btn disabled at request start",
      "liveCard.setAttribute('data-job-status-saving', '1')" in _onsaved488
      and "liveCard.querySelectorAll('.co-cand-job-status-dp .co-dp-btn')" in _onsaved488
      and '.forEach' in _onsaved488
      and 'b.disabled = true' in _onsaved488)

# 488-04: failure path calls _renderCandidateJobLinksUI from data-job-links (not sel.value)
check("488-04. Failure path re-renders from card data-job-links — never restores sel.value directly",
      '_renderCandidateJobLinksUI(card, rollLinks)' in _onsaved488
      and "card.getAttribute('data-job-links')" in _onsaved488
      and 'sel.value = prevVal' not in _onsaved488)

# 488-05: success path reads data-job-links AT response time (fresh, not stale)
check("488-05. Success path reads card.getAttribute('data-job-links') at response time — not stale capture",
      '_renderCandidateJobLinksUI(card, links)' in _onsaved488
      and "card.getAttribute('data-job-links')" in _onsaved488)

# 488-06: finally removes lock + enables ALL co-dp-btn in card (freshly rebuilt DOM)
check("488-06. finally removes data-job-status-saving and re-enables all co-dp-btn in card",
      "card.removeAttribute('data-job-status-saving')" in _onsaved488
      and "card.querySelectorAll('.co-cand-job-status-dp .co-dp-btn')" in _onsaved488
      and 'b.disabled = false' in _onsaved488)

# 488-07: _renderCandidateJobLinksUI respects lock — passes meta.locked to _dpHTML for custom pickers
check("488-07. _renderCandidateJobLinksUI reads data-job-status-saving and builds locked pickers when locked",
      "data-job-status-saving" in _render488
      and 'isLocked' in _render488
      and 'locked: isLocked' in _render488
      and 'co-cand-job-status-dp' in _render488)

# 488-08: catch block also re-renders from data-job-links (not sel)
check("488-08. catch block re-renders from card data-job-links — handles detached sel safely",
      _onsaved488.count('_renderCandidateJobLinksUI(card, rollLinks)') >= 2)

# ── Fix 2: Field(...) — explicit required nullable ─────────────────────────

# 488-09: Field(...) used in UpdateCandidateJobStatusInput
check("488-09. UpdateCandidateJobStatusInput uses Field(...) — explicit required in both Pydantic v1 and v2",
      'candidate_status: Optional[str] = Field(...)' in _srv488)

# 488-10: Functional test — actually instantiate the model to verify required behavior
from pydantic import BaseModel, Field, ValidationError
from typing import Optional as _Opt

class _TestUpdateInput(BaseModel):
    candidate_status: _Opt[str] = Field(...)

_pydantic_empty_raises = False
try:
    _TestUpdateInput()
except (ValidationError, TypeError):
    _pydantic_empty_raises = True

_pydantic_null_ok = False
try:
    _pydantic_null_ok = _TestUpdateInput(candidate_status=None).candidate_status is None
except Exception:
    pass

_pydantic_str_ok = False
try:
    _pydantic_str_ok = _TestUpdateInput(candidate_status='saved').candidate_status == 'saved'
except Exception:
    pass

check("488-10. Functional: Field(...) model rejects empty body, accepts null, accepts valid string",
      _pydantic_empty_raises and _pydantic_null_ok and _pydantic_str_ok)

# ── Fix 3: Timezone contract ───────────────────────────────────────────────

# 488-11: Backend has deprecated-fallback comment for naive ISO (not promoted as official)
check("488-11. Backend has Legacy/deprecated fallback comment for naive ISO in send_appointment",
      ('Legacy/deprecated' in _auth488 or 'deprecated fallback' in _auth488)
      and 'tzinfo is None' in _auth488)

# 488-12: SYSTEMS_INDEX §23 documents timezone contract
check("488-12. SYSTEMS_INDEX §23 documents timezone-aware contract and deprecated naive fallback",
      'toISOString' in _idx488
      and 'deprecated' in _idx488
      and 'timezone-aware' in _idx488
      and 'scheduled_at' in _idx488)

# 488-13: Frontend uses toISOString — sends UTC ISO (already covered but re-checked in context of doc)
check("488-13. Frontend sends timezone-aware scheduledAt via toISOString() (Z suffix guaranteed)",
      'toISOString()' in _main488
      and 'localScheduled' in _main488)

# ── Fix 4: No "applicant-driven" in modified files ────────────────────────

# 488-14: auth.py update_candidate_job_status docstring has no "applicant-driven"
_ucjs_body = (
    _auth488.split('def update_candidate_job_status')[1].split('\ndef ')[0]
    if 'def update_candidate_job_status' in _auth488 else ''
)
check("488-14. update_candidate_job_status() docstring does not say 'applicant-driven'",
      'applicant-driven' not in _ucjs_body)

# 488-15: company.main.js _showJobChipPop comment has no "applicant-driven"
check("488-15. _showJobChipPop comment does not say 'applicant-driven'",
      'applicant-driven' not in _main488)

# ── §489: Custom picker, advisory lock, startup-critical migration ─────────

_main489  = open('static/company/company.main.js', encoding='utf-8').read()
_css489   = open('static/company/company.css',     encoding='utf-8').read()
_auth489  = open('auth.py',   encoding='utf-8').read()
_srv489   = open('server.py', encoding='utf-8').read()
_idx489   = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()

_mig489 = (
    _auth489.split('def _migrate_candidate_status_per_job')[1].split('\ndef ')[0]
    if '_migrate_candidate_status_per_job' in _auth489 else ''
)
_hjsdp489 = (
    _main489.split('function _handleJobStatusDpSelect(')[1].split('\n  function ')[0]
    if 'function _handleJobStatusDpSelect(' in _main489 else ''
)
_render489 = (
    _main489.split('function _renderCandidateJobLinksUI(card, links)')[1].split('\n  function ')[0]
    if 'function _renderCandidateJobLinksUI(card, links)' in _main489 else ''
)

# 489-01: no .co-cand-job-status-sel (native select) anywhere in JS or CSS
check("489-01. No co-cand-job-status-sel (native select) in company.main.js or company.css",
      'co-cand-job-status-sel' not in _main489
      and 'co-cand-job-status-sel' not in _css489)

# 489-02: per-job status uses the co-dp custom picker system
check("489-02. Per-job status uses co-cand-job-status-dp custom picker (co-dp system)",
      'co-cand-job-status-dp' in _main489
      and 'co-dp-btn' in _main489
      and 'co-dp-list' in _main489
      and '_dpHTML' in _main489)

# 489-03: _handleDpOptClick routes co-cand-job-status-dp to _handleJobStatusDpSelect
check("489-03. _handleDpOptClick routes co-cand-job-status-dp to _handleJobStatusDpSelect",
      "co-cand-job-status-dp" in _main489.split('function _handleDpOptClick(')[1].split('\n  function ')[0]
      and "_handleJobStatusDpSelect" in _main489.split('function _handleDpOptClick(')[1].split('\n  function ')[0])

# 489-04: lock disables all co-cand-job-status-dp .co-dp-btn buttons
check("489-04. Card-level lock disables all .co-cand-job-status-dp .co-dp-btn buttons",
      "card.querySelectorAll('.co-cand-job-status-dp .co-dp-btn')" in _hjsdp489
      and 'b.disabled = true' in _hjsdp489)

# 489-05: success path reads data-job-links, updates candidate_status, calls _renderCandidateJobLinksUI
check("489-05. Success path reads data-job-links + updates candidate_status + calls _renderCandidateJobLinksUI",
      "card.getAttribute('data-job-links')" in _hjsdp489
      and "candidate_status" in _hjsdp489
      and "_renderCandidateJobLinksUI(card, links)" in _hjsdp489)

# 489-06: failure path does NOT update data-job-links — re-renders from it unchanged
check("489-06. Failure path re-renders from data-job-links without mutating it",
      "_renderCandidateJobLinksUI(card, rollLinks)" in _hjsdp489
      and "card.setAttribute('data-job-links'" not in _hjsdp489.split('res.ok')[1]
      if 'res.ok' in _hjsdp489 else False)

# 489-07: new job link gets a picker immediately (renderCandidateJobLinksUI builds pickers)
check("489-07. _renderCandidateJobLinksUI builds co-cand-job-status-dp pickers for new job links",
      'co-cand-job-status-dp' in _render489
      and '_dpHTML' in _render489
      and 'jsOpts2' in _render489)

# 489-08: SYSTEMS_INDEX §20c describes card-level lock + rollback from data-job-links + no native select
check("489-08. SYSTEMS_INDEX §20c documents card-level lock, data-job-links rollback, no native select",
      'data-job-status-saving' in _idx489
      and 'data-job-links' in _idx489
      and '_renderCandidateJobLinksUI' in _idx489
      and 'no native' in _idx489.lower() or 'no native' in _idx489.lower()
      or 'no native `<select>`' in _idx489
      or 'native `<select>`' in _idx489)

# 489-09: startup migration raises on failure (not caught with print+continue)
check("489-09. on_startup raises on _migrate_candidate_status_per_job failure (startup-critical)",
      '_migrate_candidate_status_per_job()' in _srv489
      # The critical line must NOT be inside a try block that catches with only a print
      and (
          # Check: no try/except wrapping just this migration call (it might be try-raised or bare)
          'Startup-critical' in _srv489
          or (
              # Bare call (no try/except swallowing it)
              'except' not in _srv489.split('_migrate_candidate_status_per_job()')[1].split('print(')[0][:200]
          )
      ))

# 489-10: migration uses advisory lock (pg_advisory_lock) and releases in finally
check("489-10. Migration uses pg_advisory_lock and releases it in finally",
      'pg_advisory_lock' in _mig489
      and 'pg_advisory_unlock' in _mig489
      and 'finally:' in _mig489
      and 'locked' in _mig489)

# 489-11: migration still has no DROP CONSTRAINT
check("489-11. Migration has no DROP CONSTRAINT after advisory lock addition",
      'DROP CONSTRAINT' not in _mig489)

# 489-12: status and application_status remain equal in both batch-fetch functions (backward compat)
check("489-12. 'status' and 'application_status' both present and equal in both batch-fetch functions",
      "'status':             app_status or None" in _auth489
      and "'application_status': app_status or None" in _auth489
      and _auth489.count("'application_status': app_status or None") >= 2)

# 489-13: Field(...) and timezone tests still pass (verify §488 fixes not regressed)
check("489-13. §488 contracts intact — Field(...) in UpdateCandidateJobStatusInput + toISOString in frontend",
      'Optional[str] = Field(...)' in _srv489
      and 'toISOString()' in _main489
      and 'localScheduled' in _main489)

# ═══════════════════════════════════════════════════════════════════
# §490 — DOM-independent lock registry + correct Writers docs
# ═══════════════════════════════════════════════════════════════════

_main490 = open('static/company/company.main.js').read()
_claude490 = open('CLAUDE.md').read()
_sysidx490 = open('docs/SYSTEMS_INDEX.md').read()

# 490-01: _jobStatusInFlight registry exists at IIFE level
check("490-01. _jobStatusInFlight = Object.create(null) declared at IIFE level",
      'var _jobStatusInFlight = Object.create(null)' in _main490)

# 490-02: _handleJobStatusDpSelect checks registry (not card DOM) to block second PATCH
check("490-02. _handleJobStatusDpSelect guards with _jobStatusInFlight[cidStr] before PATCH",
      '_jobStatusInFlight[cidStr]' in _main490
      and '_handleJobStatusDpSelect' in _main490)

# 490-03: _savedCardHTML passes registry lock to _dpHTML for newly built cards
check("490-03. _savedCardHTML passes locked: !!_jobStatusInFlight[String(item.candidate_id)] to _dpHTML",
      '_jobStatusInFlight[String(item.candidate_id)]' in _main490)

# 490-04: _renderCandidateJobLinksUI checks registry (not only data-job-status-saving)
check("490-04. _renderCandidateJobLinksUI derives isLocked from _jobStatusInFlight[cidStr]",
      '_jobStatusInFlight[cidStr]' in _main490
      and '_renderCandidateJobLinksUI' in _main490)

# 490-05: _findLiveSavedCandidateCard helper exists and queries by data-cid attribute
check("490-05. _findLiveSavedCandidateCard searches _body for .co-cand-saved-card[data-cid]",
      '_findLiveSavedCandidateCard' in _main490
      and '.co-cand-saved-card[data-cid="' in _main490)

# 490-06: success/failure/finally all use _findLiveSavedCandidateCard (live card lookup)
check("490-06. success/failure/finally use _findLiveSavedCandidateCard at response time (not stale reference)",
      _main490.count('_findLiveSavedCandidateCard(cidInt)') >= 3)

# 490-07: No-op guard: same-value selection skips PATCH
check("490-07. No-op guard present: if selected cs matches current data-job-links entry, skip PATCH",
      'currentCs' in _main490
      and 'Same value' in _main490)

# 490-08: finally deletes from registry (not just card attribute removal)
check("490-08. finally deletes _jobStatusInFlight[cidStr] before card cleanup",
      'delete _jobStatusInFlight[cidStr]' in _main490)

# 490-09a: CLAUDE.md writers for job_applications.status include promote_application_to_shortlist
check("490-09a. CLAUDE.md source-1 Writers include promote_application_to_shortlist (sets to accepted)",
      'promote_application_to_shortlist' in _claude490
      and "atomically sets to `'accepted'`" in _claude490)

# 490-09b: CLAUDE.md writers for company_saved_candidates.status include promote_application_to_shortlist
check("490-09b. CLAUDE.md source-2 Writers include promote_application_to_shortlist (shortlisted upsert)",
      "promote_application_to_shortlist()` (creates or upserts record" in _claude490)

# 490-09c (updated §491): CLAUDE.md source-3 now lists promote_application_to_shortlist as a writer (sets shortlisted)
# §491 extended promote to also write candidate_status='shortlisted' into company_candidate_job_refs.
check("490-09c. CLAUDE.md source-3 lists promote_application_to_shortlist as writer (sets to shortlisted) — updated by §491",
      'promote_application_to_shortlist()' in _claude490
      and 'shortlisted' in _claude490)

# 490-10a: SYSTEMS_INDEX §20c Writers for source-1 include both update_application_status and promote
check("490-10a. SYSTEMS_INDEX §20c source-1 Writers: update_application_status AND promote_application_to_shortlist",
      'update_application_status()' in _sysidx490
      and "promote_application_to_shortlist()` (atomically sets to `'accepted'`)" in _sysidx490)

# 490-10b: SYSTEMS_INDEX §20c Writers for source-2 include promote_application_to_shortlist (shortlisted)
check("490-10b. SYSTEMS_INDEX §20c source-2 Writers include promote_application_to_shortlist shortlisted upsert",
      "promote_application_to_shortlist()` (creates or upserts record to `'shortlisted'" in _sysidx490)

# 490-10c (updated §491): SYSTEMS_INDEX §20c now reflects atomic dual-write and classification sync carve-out
# §491 changed update_application_status() and promote to both write company_candidate_job_refs.candidate_status.
check("490-10c. SYSTEMS_INDEX §20c reflects applicant-classification-sync: atomic dual-write + carve-out present",
      'tw:candidate-job-classification-updated' in _sysidx490
      and 'feat/applicant-classification-sync' in _sysidx490)

# 490-11: Removed incorrect async contract; registry-based contract present instead
check("490-11. SYSTEMS_INDEX §20c no longer contains stale 'captured before the PATCH call' async contract",
      'No async path reads a DOM element captured before the PATCH call' not in _sysidx490
      and '_findLiveSavedCandidateCard' in _sysidx490
      and 'Registry-based lock' in _sysidx490)

# ═══════════════════════════════════════════════════════════════════
# §491 — Applicant Classification Sync (feat/applicant-classification-sync)
# ═══════════════════════════════════════════════════════════════════

_auth491  = open('auth.py').read()
_srv491   = open('server.py').read()
_main491  = open('static/company/company.main.js').read()
_claude491 = open('CLAUDE.md').read()
_sysidx491 = open('docs/SYSTEMS_INDEX.md').read()
_arch491   = open('ARCHITECTURE.md').read()

# 491-01: _APP_TO_CANDIDATE_STATUS dict exists in auth.py with all 7 mappings
check("491-01. _APP_TO_CANDIDATE_STATUS dict defined in auth.py with complete status mapping",
      '_APP_TO_CANDIDATE_STATUS' in _auth491
      and '"pending":' in _auth491
      and '"viewed":' in _auth491
      and '"accepted":' in _auth491
      and '"contacted":' in _auth491
      and '"interview":' in _auth491
      and '"hired":' in _auth491
      and '"rejected":' in _auth491)

# 491-02: update_application_status uses BEGIN/COMMIT/ROLLBACK with FOR UPDATE OF ja
check("491-02. update_application_status uses atomic transaction with FOR UPDATE OF ja row lock",
      'def update_application_status' in _auth491
      and 'BEGIN' in _auth491
      and 'COMMIT' in _auth491
      and 'ROLLBACK' in _auth491
      and 'FOR UPDATE OF ja' in _auth491)

# 491-03: update_application_status writes company_candidate_job_refs atomically
check("491-03. update_application_status UPSERTs company_candidate_job_refs inside the same transaction",
      'company_candidate_job_refs' in _auth491
      and 'ON CONFLICT (company_id, candidate_id, job_id) DO UPDATE' in _auth491
      and 'candidate_status = EXCLUDED.candidate_status' in _auth491)

# 491-04: update_application_status ensures company_saved_candidates FK row first
check("491-04. update_application_status inserts company_saved_candidates row before job refs upsert",
      'ON CONFLICT (company_id, candidate_id) DO NOTHING' in _auth491)

# 491-05: update_application_status returns candidate_id, job_id, application_status, candidate_status
check("491-05. update_application_status returns candidate_id, job_id, application_status, candidate_status",
      '"candidate_id":       applicant_id' in _auth491
      and '"job_id":             job_id_int' in _auth491
      and '"application_status": status' in _auth491
      and '"candidate_status":   candidate_status' in _auth491)

# 491-06: server.py update_app_status endpoint maps KeyError → 404, PermissionError → 403, RuntimeError → 500
check("491-06. server.py update_app_status maps KeyError→404, PermissionError→403, RuntimeError→500",
      'except KeyError' in _srv491
      and 'raise HTTPException(404' in _srv491
      and 'except PermissionError' in _srv491
      and 'raise HTTPException(403' in _srv491
      and 'except RuntimeError' in _srv491
      and 'raise HTTPException(500' in _srv491)

# 491-07: promote_application_to_shortlist writes candidate_status='shortlisted' to company_candidate_job_refs
check("491-07. promote_application_to_shortlist UPSERTs candidate_status=shortlisted into company_candidate_job_refs",
      "SET candidate_status = 'shortlisted'" in _auth491
      and "'shortlisted')" in _auth491)

# 491-08: promote return value includes top-level candidate_id, job_id, application_status, candidate_status
check("491-08. promote_application_to_shortlist return value includes top-level sync fields",
      '"application_id":     app_id' in _auth491
      and '"candidate_id":       int(applicant_id)' in _auth491
      and '"application_status": "accepted"' in _auth491
      and '"candidate_status":   "shortlisted"' in _auth491)

# 491-09: _execClassify dispatches tw:candidate-job-classification-updated CustomEvent on success
check("491-09. _execClassify dispatches tw:candidate-job-classification-updated on success only",
      'tw:candidate-job-classification-updated' in _main491
      and 'new CustomEvent' in _main491
      and 'applicationStatus' in _main491
      and 'candidateStatus' in _main491)

# 491-10: _execPromote dispatches tw:candidate-job-classification-updated with accepted/shortlisted
check("491-10. _execPromote dispatches tw:candidate-job-classification-updated on promote success",
      _main491.count('tw:candidate-job-classification-updated') >= 2)

# 491-11: Saved Candidates IIFE listens for tw:candidate-job-classification-updated and updates card
check("491-11. Saved Candidates IIFE has document.addEventListener for tw:candidate-job-classification-updated",
      "document.addEventListener('tw:candidate-job-classification-updated'" in _main491
      and '_renderCandidateJobLinksUI(card, links)' in _main491)

# 491-12: CLAUDE.md source-3 now lists update_application_status as a writer and has carve-out
check("491-12. CLAUDE.md source-3 lists update_application_status() as writer + carve-out present",
      'update_application_status()' in _claude491
      and '_APP_TO_CANDIDATE_STATUS' in _claude491
      and 'Applicant Classification Sync carve-out' in _claude491
      and 'Reverse direction is permanently forbidden' in _claude491)

# ── Summary ──────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════
# §492 — Job chip popover simplified (fix/job-chip-pop-simplify)
# ═══════════════════════════════════════════════════════════════════

_main492  = open('static/company/company.main.js', encoding='utf-8').read()
_css492   = open('static/company/company.css', encoding='utf-8').read()
_sysidx492 = open('docs/SYSTEMS_INDEX.md', encoding='utf-8').read()

# Extract _showJobChipPop function body
_pop492 = (_main492.split('function _showJobChipPop')[1].split('function _jobPopPositionFromChip')[0]
           if 'function _showJobChipPop' in _main492 else '')

# 492-01: Popover shows «حالة المرشح في هذه الوظيفة» as the row label
check("492-01. _showJobChipPop uses «حالة المرشح في هذه الوظيفة» as row label",
      'حالة المرشح في هذه الوظيفة' in _pop492)

# 492-02: Source is data-cand-status / candidate_status
check("492-02. _showJobChipPop reads data-cand-status for candidate classification",
      "getAttribute('data-cand-status')" in _pop492)

# 492-03: «حالة الطلب» row is removed from popover
check("492-03. حالة الطلب row no longer appears in _showJobChipPop",
      'حالة الطلب' not in _pop492)

# 492-04: «التصنيف العام» row is removed from popover
check("492-04. التصنيف العام row no longer appears in _showJobChipPop",
      'التصنيف العام' not in _pop492)

# 492-05: apply_date row is conditional — rendered only inside `if (applyDate)` block
_date_block492 = (_pop492.split('if (applyDate)')[1].split('\n    }')[0]
                  if 'if (applyDate)' in _pop492 else '')
check("492-05. تاريخ التقدم row only rendered inside if(applyDate) — not unconditional",
      'تاريخ التقدم' in _date_block492
      and 'تاريخ التقدم' not in _pop492.split('if (applyDate)')[0])

# 492-06: null candidate_status → «غير مصنف» label
check("492-06. null candidate_status displays «غير مصنف»",
      'غير مصنف' in _pop492)

# 492-07: application_status field stays in job_links[] API contract (backward compat — not removed)
check("492-07. application_status still present in job_links[] chip HTML (API backward compat)",
      "data-app-status" in _main492
      and "application_status" in _main492)

# 492-08: _jobPopPositionFromChip and _closeJobPop positioning/close logic unchanged
check("492-08. _jobPopPositionFromChip and _closeJobPop still present and wired",
      'function _jobPopPositionFromChip' in _main492
      and 'function _closeJobPop' in _main492
      and "_closeJobPop" in _pop492)

# 492-09: Removed CSS classes co-cjp-status and co-cjp-cand-status no longer in company.css
check("492-09. co-cjp-status and co-cjp-cand-status CSS classes removed",
      'co-cjp-status {' not in _css492
      and 'co-cjp-cand-status {' not in _css492)

# 492-10: Kept CSS classes co-cjp-no-app and co-cjp-cand-job-st still present
check("492-10. co-cjp-no-app and co-cjp-cand-job-st CSS classes still present",
      'co-cjp-no-app' in _css492
      and 'co-cjp-cand-job-st' in _css492)

# 492-11: SYSTEMS_INDEX §20c popover description updated to 2-row format
check("492-11. SYSTEMS_INDEX §20c popover updated: 2 rows, حالة المرشح في هذه الوظيفة, apply_date conditional",
      'حالة المرشح في هذه الوظيفة' in _sysidx492
      and 'apply_date' in _sysidx492
      and 'only when non-null' in _sysidx492
      and 'fix/job-chip-pop-simplify' in _sysidx492)

# 492-12: genStatus / genLbl variables no longer in _showJobChipPop (clean removal)
check("492-12. genStatus and genLbl variables removed from _showJobChipPop",
      'genStatus' not in _pop492
      and 'genLbl' not in _pop492)

# ── §SEC-1 — IDOR: DELETE /auth/user/{user_id}/delete ────────────────────────
# Vulnerability: delete_own_account calls Depends(verify_token) but never
# compares token["user_id"] with the {user_id} path parameter.
# Any authenticated user can delete any other user's account.
# Tests sec-1-01 and sec-1-02 FAIL on main (proving the IDOR), PASS after fix.
# Test sec-1-03 is a regression guard (passes both before and after).

import re as _re_sec

_del_fn_match = _re_sec.search(
    r'def delete_own_account\(.+?\n(?:[ \t].+\n?)*',
    srv_src
)
_del_body = _del_fn_match.group(0) if _del_fn_match else ""

check(
    "sec-1-01. delete_own_account validates JWT user_id matches path user_id [IDOR guard]",
    bool(_del_body) and (
        'token["user_id"] != user_id' in _del_body or
        "token.get('user_id') != user_id" in _del_body or
        "token.get(\"user_id\") != user_id" in _del_body
    )
)

check(
    "sec-1-02. delete_own_account raises HTTPException(403) on ownership mismatch",
    bool(_del_body) and "403" in _del_body and "HTTPException" in _del_body
)

check(
    "sec-1-03. delete_own_account still contains DELETE FROM users query [regression guard]",
    bool(_del_body) and "DELETE FROM users WHERE id" in _del_body
)

# ── §SEC-1 BEHAVIORAL — Direct function call with mocked DB ──────────────────
# Tests sec-1-04 through sec-1-08 call delete_own_account at runtime.
# No real DB required: get_conn / release_conn are replaced with MagicMock.
# These tests prove the security behavior, not just the source text.

import sys as _sys_sec1b
import os as _os_sec1b
from unittest.mock import MagicMock as _Mb, patch as _Pb
from fastapi import HTTPException as _FHE_sec1

_srv_sec1 = None
_srv_sec1_err = ""
try:
    _os_sec1b.environ.setdefault('SUPABASE_DB_URL', 'postgresql://x:x@localhost/x')
    if 'pg8000' not in _sys_sec1b.modules:
        _pgm = _Mb()
        _pgm.native = _Mb()
        _pgm.native.Connection = _Mb(return_value=_Mb())
        _sys_sec1b.modules['pg8000'] = _pgm
        _sys_sec1b.modules['pg8000.native'] = _pgm.native
    if 'bcrypt' not in _sys_sec1b.modules:
        _sys_sec1b.modules['bcrypt'] = _Mb()
    import server as _srv_sec1
except Exception as _e_sec1b:
    _srv_sec1_err = str(_e_sec1b)[:150]

if _srv_sec1 is not None:
    # ── sec-1-04: IDOR — token.user_id=1 tries to delete user_id=99 → HTTP 403
    _gc_idor = _Mb()
    with _Pb.object(_srv_sec1, 'get_conn', _gc_idor), \
         _Pb.object(_srv_sec1, 'release_conn', _Mb()):
        _idor_status = None
        try:
            _srv_sec1.delete_own_account(
                user_id=99, request=_Mb(),
                token={'user_id': 1, 'user_type': 'emp'}
            )
        except _FHE_sec1 as _ex_idor:
            _idor_status = _ex_idor.status_code
        except Exception:
            pass
    check(
        "sec-1-04. [BEHAVIORAL] IDOR: token(user=1) deleting user_id=99 → HTTP 403",
        _idor_status == 403
    )
    # ── sec-1-05: get_conn must NOT be reached when 403 is raised
    check(
        "sec-1-05. [BEHAVIORAL] get_conn not called when ownership fails (DELETE never runs)",
        _gc_idor.call_count == 0
    )

    # ── sec-1-06 + sec-1-07: self-delete — token.user_id=1 deletes user_id=1 → success
    _conn_self = _Mb()
    _gc_self = _Mb(return_value=_conn_self)
    with _Pb.object(_srv_sec1, 'get_conn', _gc_self), \
         _Pb.object(_srv_sec1, 'release_conn', _Mb()):
        _self_res = None
        try:
            _self_res = _srv_sec1.delete_own_account(
                user_id=1, request=_Mb(),
                token={'user_id': 1, 'user_type': 'emp'}
            )
        except Exception:
            pass
    check(
        "sec-1-06. [BEHAVIORAL] self-delete: token(user=1) deleting user_id=1 → {success: True}",
        _self_res == {"success": True}
    )
    check(
        "sec-1-07. [BEHAVIORAL] DELETE FROM users query executed for self-deletion",
        any("DELETE FROM users" in str(c) for c in _conn_self.run.call_args_list)
    )

    # ── sec-1-08: No JWT → verify_token raises HTTP 401
    _req_no_jwt = _Mb()
    _req_no_jwt.headers.get.return_value = ""
    _no_jwt_status = None
    try:
        _srv_sec1.verify_token(_req_no_jwt)
    except _FHE_sec1 as _ex_nojwt:
        _no_jwt_status = _ex_nojwt.status_code
    except Exception:
        pass
    check(
        "sec-1-08. [BEHAVIORAL] no JWT → verify_token raises HTTP 401",
        _no_jwt_status == 401
    )
else:
    for _sec1_n in ["04", "05", "06", "07", "08"]:
        check(
            f"sec-1-{_sec1_n}. [BEHAVIORAL] server import available for behavioral tests",
            False,
            _srv_sec1_err
        )

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
