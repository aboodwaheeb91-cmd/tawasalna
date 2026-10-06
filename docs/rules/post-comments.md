# Post Comments — التعليقات

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Post Comments System Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §65`.

1. **`company_post_comments` is the only table for post comments.** Do not create a second table for the same purpose.

2. **V1 supports 1-level reply threading via `reply_to_comment_id`.** Max depth is 1 — the server auto-resolves deeper replies to the root. Do not implement deeper nesting without a dedicated PR. `reply_to_comment_id` is a nullable FK to `company_post_comments(id) ON DELETE SET NULL`.

3. **`comments_enabled` is enforced server-side.** When `comments_enabled=false`, `create_company_post_comment()` raises `PermissionError` → HTTP 403. Do not rely on hiding the button alone.

4. **Permissions are server-side only:**
   - Edit: comment author only (`owner_id == user_id`)
   - Delete: comment author OR company page owner (`company_id == user_id`)
   - `viewer_can_edit` / `viewer_can_delete` flags are returned per-comment from `GET /company/posts/{post_id}/comments`
   - Never gate permissions on frontend state alone

5. **`comments_count` is the only source of truth for the count.** It comes from `get_company_posts()` LEFT JOIN. Do not count comments client-side or cache a count in localStorage.

6. **Soft delete is mandatory.** `delete_company_post_comment()` sets `status='deleted'` and `deleted_at=NOW()`. Hard delete is forbidden. `get_company_post_comments()` filters `status='active'` only.

7. **XSS protection is mandatory.** Comment `body` must only be rendered via `textContent` — never `innerHTML`. The `_cmtBuildItem()` function enforces this. Do not introduce `innerHTML` rendering of any API text in the comments panel.

8. **No localStorage for comments.** Comment data, counts, and state come from the API only. Do not cache comments or counts in `localStorage` or `sessionStorage`.

9. **`_toggleCommentPanel(postId)` is the single entry point** for opening/closing the comments panel. Do not add a second trigger or duplicate panel-open logic.

10. **No notifications in this PR.** The `comment_created` event is a future hook for Phase 3 (Notifications). Do not create a `notifications` table or send notifications in the comments PR.

11. **Do not change the appreciation system or save system.** The comments implementation must not modify `company_post_appreciations`, `company_post_saves`, their endpoints, or their frontend queue variables.

12. **Rate limits are permanent:** 10 create / 60s per (user, post), 10 edits / 60s per (user, comment). Do not remove or relax without a documented security review.

13. **Comment edit flow is a permanent contract (fix/comment-edit-ux):**
   - **Insert-first rule:** `editWrap` must be inserted into `.pc-cmt-content` BEFORE `bodyEl.style.display = 'none'`. Never hide the body before the editor is in the DOM.
   - **Correct parent:** `content.insertBefore(editWrap, acts)` where `content = item.querySelector('.pc-cmt-content')`. Do NOT use `item.insertBefore(editWrap, acts)` — `acts` is not a direct child of `item`.
   - **In-flight guard:** `_cmtEditInFlight[commentId]` prevents concurrent PATCH requests on the same comment. Check it at the top of `_cmtHandleEdit` AND inside the save handler.
   - **Optimistic UI:** `_renderCommentBody(bodyEl, newBody, mentionName, mentionTwId, knownNames, itemMentions)` (XSS-safe) BEFORE the fetch call. On PATCH failure, rollback with original args. `mentionName = item.dataset.replyToAuthor || null`, `mentionTwId = item.dataset.replyToAuthorTwId || null`, `itemMentions` read from `item.dataset.mentionsJson`.
   - **XSS contract:** ALL text assignments in the edit flow use `textContent`/`_renderCommentBody` — never `innerHTML`. This applies to `newBody`, `originalText`, and `res.data.comment.body`.
   - **Cancel:** restores body instantly, no request. `bodyEl.style.display = ''` + `editWrap.remove()`.
   - **"تم التعديل" badge** added to `.pc-cmt-meta-row` on success (idempotent — only if not already present). Do NOT append it to `.pc-cmt-header` or `.pc-cmt-header-left` — it belongs in the meta row alongside time and reply button.
   - **visual-reply class is NOT changed in `_cmtHandleEdit`.** `reply_to_comment_id` is immutable per comment. On rollback, restore `wasVisualReply` from `item.classList.contains('pc-cmt-visual-reply')` captured at start.

14. **Comment UX contracts (feat/comment-ui-polish) — permanent:**
   - **Auto-resize textarea (both send and edit):** `_autoResizeTextarea(ta)` sets `ta.style.height = 'auto'` then clamps to `Math.min(ta.scrollHeight, 120)`. Both the send textarea (`_cmtPopulatePanel`) and the edit textarea (`_cmtHandleEdit`) start at `rows=1` and have an `input` listener. For the edit textarea, `_autoResizeTextarea(editTa)` is also called once after `editWrap` is inserted into the DOM (so `scrollHeight` reflects the pre-filled text). Height resets to `''` after a successful send. Do NOT set `rows` > 1 on either textarea.
   - **RTL input row order:** `sendBtn` is appended to `.pc-cmts-input-row` BEFORE `ta`. In RTL flex row, this makes the button appear on the right and the textarea fill the left. Do NOT reverse this order.
   - **Send button is outlined, not solid:** `background: transparent`, `border: 1.5px solid var(--ac)`, `color: var(--ac)`. Glow on hover. Never revert to `background: var(--ac)` (solid fill).
   - **Three-dot ⋮ menu uses portal pattern** (feat/comment-ux-polish-2): `_cmtBuildItem` adds a `.pc-cmt-menu-btn` button with `data-can-edit` / `data-can-delete` attributes. Click → `_cmtShowPortalMenu(btn, cmtId, postId, canEdit, canDelete)` positions `#pc-cmt-portal-menu` (single div on `document.body`, `position:fixed`) using `getBoundingClientRect()`. Portal closes on: outside click, list scroll, page scroll. `_cmtOpenMenuId` tracks open state. Do NOT use inline `position:absolute` menu — it gets clipped by `overflow-y:auto`.
   - **`.pc-cmt-acts` is kept as an empty DOM anchor** for `_cmtHandleEdit`'s `insertBefore`. Do NOT remove it from `_cmtBuildItem`.
   - **Relative time:** `_formatRelativeTime(ts)` returns Arabic relative strings (`منذ لحظة`, `منذ N دقائق`, …). `_ICO_CLOCK` is a static inline SVG. Both appear inside `.pc-cmt-meta-row`. Do NOT pass API text through `innerHTML`.
   - **Comments list max-height is 280px.** Do NOT increase above 300px without a dedicated PR.

15. **Comment UX contracts (feat/comment-ux-polish-2, updated feat/comment-ux-polish-3) — permanent:**
   - **Column header layout:** `.pc-cmt-header-left` uses `flex-direction:column`. Row 1 = `.pc-cmt-author` (name). Row 2 = `.pc-cmt-meta-row` (time · edited badge only). Avatar is 32px.
   - **Portal ⋮ menu is mandatory** — never revert to inline `position:absolute`. See ARCHITECTURE.md §65.
   - **"رد" reply button is below `.pc-cmt-body`**, NOT inside `.pc-cmt-meta-row`. DOM order: header → body → replyBtn → acts. Color: `rgba(37,99,255,.65)` (soft blue). Do NOT move it back into the meta row.
   - `_cmtHandleReply(postId, authorName, commentId)` prefills textarea with `@authorName `, updates `_cmtReplyTarget[postId]` + `_cmtReplyTargetId[postId]`, shows "رداً على" strip. Cancel via `_cmtCancelReply(postId)` strips the mention and clears both state variables.
   - **"رداً على" strip** sits between `.pc-cmts-loading` and `.pc-cmts-input-row` in the panel DOM. `_cmtHandleSend` clears it on successful send.
   - **XSS:** all API-sourced text in reply flow uses `textContent`. `nameSpan.textContent = authorName` is the only approved assignment for the strip name.
   - **`_cmtReplyTarget` and `_cmtReplyTargetId`** are the only state stores for active reply per panel (per postId). Do NOT persist to localStorage.

16. **Comment UX contracts (feat/comment-ux-polish-3, updated feat/reply-threading-v1) — permanent:**
   - **`_renderCommentBody(bodyEl, text, mentionName, mentionTwId, knownNames, mentions)` is the only approved function** for setting comment body content. It uses `textContent`/`createTextNode` exclusively — never `innerHTML` for API data. Full-text scan left-to-right — finds `@name` at any position in text, not just the start. Used in: `_cmtBuildItem`, `_cmtHandleEdit` (optimistic, success, rollback).
   - **`.pc-cmt-visual-reply` class** is driven by `c.reply_to_comment_id != null` (not `c.body.charAt(0) === '@'`). CSS-only indentation (`margin-inline-start:28px`). `_cmtHandleEdit` does NOT change this class — it is immutable per comment.
   - **Scrollbar hidden on `.pc-cmts-list`** (`scrollbar-width:none` + `::-webkit-scrollbar {display:none}`). This prevents the RTL scrollbar track from appearing as a vertical line on the left side. Do NOT remove these rules.
   - **No vertical line** in the comments list. Do not add `border-left`, `border-inline-start`, or visible pseudo-elements to `.pc-cmts-list`, `.pc-cmt-item`, or `.pc-cmt-content`.

17. **Reply Threading V1 contracts (feat/reply-threading-v1) — permanent:**
   - **`reply_to_comment_id` is the single source of truth** for whether a comment is a reply. Do NOT derive this from the body `@` prefix.
   - **Max depth = 1.** Server resolves depth in `create_company_post_comment`: if the target comment itself has a `reply_to_comment_id`, the server uses that value as the resolved parent. Client must not bypass.
   - **Same POST endpoint.** `POST /company/posts/{post_id}/comments` accepts optional `reply_to_comment_id`. Do NOT create a separate reply endpoint.
   - **`_cmtRenderComments(comments, list)`** is the only approved function for rendering the initial comment list. It groups replies under their parent. Orphan replies (parent deleted) are appended at the end. Do NOT use a plain `forEach` over the API array.
   - **`_cmtInsertReply(list, newComment, knownNames)`** inserts a new reply immediately after the parent's last sibling reply in the DOM. Do NOT `list.appendChild` a reply unconditionally.
   - **`_cmtReplyTargetId[postId]`** stores the commentId to send as `reply_to_comment_id`. Both `_cmtReplyTarget` (authorName) and `_cmtReplyTargetId` (commentId) are cleared on send + cancel.
   - **`data-reply-to-id` + `data-reply-to-author`** are set on `.pc-cmt-item` by `_cmtBuildItem` when `reply_to_comment_id != null`. These are used by `_cmtInsertReply` and `_cmtHandleEdit`.

18. **@ Mention Autocomplete contracts (feat/comment-mention-autocomplete, updated feat/comment-author-links, updated feat/mention-ux-fixes) — permanent:**
   - **One portal `#pc-cmt-mention-menu` on `document.body`.** Lazy-created by `_cmtGetMentionMenu()`. Do NOT create a per-panel dropdown — it would be clipped by `overflow-y:auto`.
   - **Candidates are objects `{name, tw_id, avatar}` — not plain strings.** `_cmtCollectMentionCandidates(postId)` reads `data-author-tw-id` + `data-author-avatar` from `.pc-cmt-item[data-author-tw-id]` elements + `companyState.profile` (correct path). Do NOT use `companyState.full_name` (wrong — it was a bug).
   - **`_cmtFilterMentionCandidates` filters on `.name` property.** Do NOT filter on the candidate object itself.
   - **`_cmtOpenMentionMenu` renders avatar (22px circle) + name text per item.** All text via `textContent`. Stores `btn.dataset.mentionName = cand.name`.
   - **`_cmtFindMentionStart(ta)` stops at space/newline.** Do NOT trigger the dropdown for `@` that appears in the middle of a word.
   - **Insertion via `_cmtInsertMention(ta, name)`.** Replaces from `@` index to cursor. Fires `input` event so auto-resize runs. Name insertion always uses string concatenation into `ta.value` — never `innerHTML`.
   - **Max 6 suggestions.** `_cmtFilterMentionCandidates` returns at most 6 results.
   - **XSS-safe.** All candidate names via `btn.textContent`/`nameSpan.textContent`. Never `innerHTML` for any API or DOM-sourced string.
   - **Keyboard nav:** ArrowDown/Up cycles `activeIdx`, Enter inserts only when `activeIdx >= 0`, Escape closes.
   - **Closes on:** outside click, page scroll, list scroll, successful insertion.
   - **`_cmtMentionState` is the only store for active mention session.** Do NOT persist to localStorage/sessionStorage.
   - **CSS namespace:** `.pc-cmt-mention-menu`, `.pc-cmt-mention-item`, `.pc-cmt-mention-active`, `.pc-cmt-mention-ava`, `.pc-cmt-mention-name` in `static/company/company.css` only.
   - **`_cmtPositionMentionMenu(ta)` uses actual `menu.offsetHeight` — NOT hardcoded 160.** Call sequence in `_cmtOpenMentionMenu`: set `visibility:hidden; display:block` → call `_cmtPositionMentionMenu(ta)` (reads accurate `offsetHeight`) → clear `visibility`. Do NOT call `_cmtPositionMentionMenu` while menu is `display:none` (offsetHeight would be 0).
   - **`_cmtKnownNames(postId)` is the helper** that extracts all candidate names sorted longest-first for free-mention compound matching. Returns string array. Do NOT inline this logic inside `_renderCommentBody`.

19. **Author Links & Clickable @mention contracts (feat/comment-author-links, updated feat/mention-ux-fixes, updated feat/comment-ux-v2) — permanent:**
   - **Author avatar and name open `/u/{author_tw_id}`.** They are `<a>` elements when `author_tw_id` is present, plain `<div>`/`<span>` when absent. Created in `_cmtBuildItem`.
   - **`_renderCommentBody(bodyEl, text, mentionName, mentionTwId, knownNames, mentions)` — 6-arg signature is final.** All args after `text` may be `null`. `mentions` is `[{name, tw_id}]` from `company_post_comment_mentions` junction table (arg 6). All text via `textContent` — never `innerHTML`.
   - **Priority order inside `_renderCommentBody`:** (1) exact reply-author match → `<a>` if mentionTwId present · (2) junction-table mentions (`mentions[]`) → `<a href="/u/tw_id">` per matched entry · (3) `knownNames` longest compound match → `<span>` only · (4) `@\S+` last resort → `<span>` · (5) plain text. Scan is full-text left-to-right (not just `text.startsWith`).
   - **Free @mentions from autocomplete are stored in DB via junction table.** `_cmtInsertMention(ta, name, twId)` pushes `{name, tw_id}` into `_cmtMentionedCandidates[postId]` (array). On send, `mentioned_tw_ids: [tw_id1, tw_id2, ...]` is included in the POST payload. Server validates each user exists, inserts into `company_post_comment_mentions` atomically with the comment. Response returns `mentions: [{name, tw_id}, ...]`.
   - **`_cmtMentionedCandidates[postId]` is the only state for pending @mentions.** It is an array `[{name, tw_id}]` — supports multiple mentions. Cleared to `[]` after successful send. Never persisted to localStorage.
   - **Guaranteed clickable @mentions:** (a) reply-author: `reply_to_author_tw_id` from API → `<a>` · (b) junction-table mentions: `mentions[]` from API → `<a href="/u/tw_id">` per entry. All other @mentions remain `<span>`.
   - **`mentionTwId` source: `c.reply_to_author_tw_id` (API) / `item.dataset.replyToAuthorTwId` (edit flow).** `mentions` source: `c.mentions` (API array) / `JSON.parse(item.dataset.mentionsJson)` (edit flow).
   - **Forbidden link targets:** Never use `/profile?id=`, `/company-profile`, or numeric `id` in author/mention links. Only `/u/{tw_id}`.
   - **If `author_tw_id` is absent, no `href` is created.** Do NOT construct a link from author_name alone.
   - **CSS:** `a.pc-cmt-author { text-decoration:none; color:inherit; }` · `a.pc-cmt-ava { display:flex; text-decoration:none; }` · `a.pc-cmt-mention { text-decoration:none; }` — all in `static/company/company.css`.

20. **Comment UX V2 contracts (feat/comment-ux-v2) — permanent:**

   **Collapsible long comments:**
   - **`is-collapsed` is always added to `bodyEl` in `_cmtBuildItem`.** `_cmtCheckCollapse(el)` removes it (and the moreBtn) if `scrollHeight ≤ clientHeight + 2` after DOM insertion. Never add `is-collapsed` in the CSS rule — it starts as a JS class.
   - **`_cmtCheckCollapse(el)` must be called after every `_cmtBuildItem` insertion** in `_cmtRenderComments` (via `_cmtInitCollapseAll`), `_cmtHandleSend` (top-level comment), and `_cmtInsertReply` (new reply).
   - **`.pc-cmt-more-btn` / `.pc-cmt-less-btn` toggle class is permanent.** Click delegation: `pc-cmt-more-btn` → remove `is-collapsed`, change className to `pc-cmt-less-btn`; `pc-cmt-less-btn` → add `is-collapsed`, change className to `pc-cmt-more-btn`.
   - **`_cmtHandleEdit` hides moreBtn** (`moreToggle.style.display = 'none'`) when the edit textarea is shown, and restores it on cancel, success, and error.

   **Collapsed replies by default:**
   - **Reply DOM structure is `toggle + box`, not inline.** Each parent comment is followed by `.pc-cmt-replies-toggle[data-parent-id]` + `.pc-cmt-replies-box[data-parent-id][hidden]` in the list.
   - **`_cmtSetToggleState(toggle, box, open, count)` is the only function** that changes toggle text, toggle class, and box visibility. Do NOT update them independently.
   - **`_cmtBuildRepliesGroup(parentId, replies, knownNames)`** builds toggle + box with all replies inside. Never insert replies directly into the list.
   - **`_cmtInsertReply` finds or creates the replies-box.** Auto-opens on new reply. Returns the new item element.
   - **`_cmtHandleDelete` cleans up the replies group:**
     - Reply deleted: count remaining; if 0 → remove toggle+box; else update toggle count.
     - Parent deleted: also remove `pc-cmt-replies-toggle` + `pc-cmt-replies-box` with matching `data-parent-id`.
   - **`_cmtReplyCountText(n)` is the Arabic label helper.** Never hardcode reply count text.

---

## Post Comments — Mention Atomicity Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §65`.

21. **Comment + mentions are a single atomic unit (feat/mention-multi-fix) — permanent:**

   **Transaction contract:**
   - `create_company_post_comment()` in `auth.py` wraps the comment INSERT + all mention INSERTs in a single `BEGIN / COMMIT / ROLLBACK` transaction.
   - If any mention INSERT fails → `ROLLBACK` is issued immediately → the comment row is NOT saved → a clear `RuntimeError("فشل حفظ التعليق والمنشنات: ...")` is raised → HTTP 500 is returned to the client.
   - `except: pass` is **permanently forbidden** inside this transaction block.
   - The `committed = False / committed = True` guard ensures ROLLBACK is only attempted when COMMIT has not already succeeded.

   **No orphan comments:**
   - After a transaction failure, no `company_post_comments` row exists. Refreshing the page will not reveal a comment without its mentions.
   - Never split the operation into separate try/except blocks where the comment survives a mention failure.

   **Junction table is the only store for multi-mention:**
   - `company_post_comment_mentions(comment_id, mentioned_tw_id)` with `UNIQUE(comment_id, mentioned_tw_id)` and `ON DELETE CASCADE`.
   - `ON CONFLICT (comment_id, mentioned_tw_id) DO NOTHING` is used for idempotent INSERT (safe for duplicate mention of same user).
   - Do NOT store multiple mentions as a comma-separated string or JSON blob in `company_post_comments`.

   **API contract (permanent):**
   - Request payload: `mentioned_tw_ids: [tw_id1, tw_id2, ...]` (array of strings, optional).
   - Response (create): `mentions: [{name, tw_id}, ...]` (resolved from DB after COMMIT).
   - Response (list): `mentions: [{name, tw_id}, ...]` per comment, batch-fetched from junction table.
   - `mentioned_tw_id` (singular) in the response is **removed**. Backward compat: old comments without junction entries get `mentions: []`.

   **No silent failure — ever:**
   - The server must never return HTTP 200 with a comment that has missing or partially-saved mentions.
   - If `mentioned_tw_ids` contains an invalid `tw_id` (user not found), the server raises `ValueError` → transaction is aborted → no comment created.
   - Do NOT add `try/except pass` around any `conn.run()` inside the transaction block.
