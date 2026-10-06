# Post Save — حفظ المنشور

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Post Save System Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.
Full technical specification: `ARCHITECTURE.md §64`.

1. **`company_post_saves` is the only table for post saves.** Schema: `id, post_id FK (ON DELETE CASCADE), user_id FK (ON DELETE CASCADE), created_at` with `UNIQUE(post_id, user_id)`. Do not create a second table for the same purpose.

2. **Use the idempotent `PUT` endpoint.** `PUT /company/posts/{post_id}/save` with `{"saved": bool}` is the canonical endpoint. `INSERT ... ON CONFLICT DO NOTHING` for save=true; plain `DELETE` (no-op if absent) for save=false.

3. **`viewer_saved` is the only source of truth for save state.** It is returned per-post from `GET /company/posts/{company_id}` when a JWT is present. Do not use localStorage as the save source.

4. **Save count is private.** Do not expose how many users saved a post publicly. There is no public save counter on the card.

5. **Owner can save their own post.** Unlike appreciation, there is no self-save restriction. The endpoint has no 403 for the post owner.

6. **Desired State Queue is mandatory.** The three module-level variables in `company.posts.js` mirror the appreciation queue pattern: `_saveDesired`, `_saveInFlight`, `_saveOrigState`. Do not simplify to a plain toggle.

7. **No-flicker rule applies to saves.** In `_dispatchSave`, check `desired !== undefined && desired !== srvActive` BEFORE calling `_renderSaveButton`. If stale, update `_saveOrigState`, dispatch follow-up, and `return` without rendering.

8. **`_renderSaveButton(btn, active)` is the only DOM update point** for save state. Do not update `.save-active` class, `data-saved`, or the button's icon/text anywhere else in `company.posts.js`. Button states are a permanent contract:
   - `active=true` → icon: `_ICO_BOOKMARK_CHECK` (filled bookmark + dark checkmark ✓), text: `'محفوظ'`, class: `save-active` (yellow `#fbbf24`)
   - `active=false` → icon: `_ICO_BOOKMARK_OUTLINE` (outline bookmark), text: `'حفظ'`, class: none (gray)

   `company.render.js` initial render must produce the same states using `icoBookmarkCheck` / `icoBookmark`. Any icon/text change must update both files in the same PR.

9. **Guest toast message is fixed:** `'سجّل دخولك لحفظ المنشور'`. Do not change this wording.
