# Post Appreciation — أقدّر

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Post Appreciation System Rules — أقدّر (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **Button label is frozen: "أقدّر".** Do not rename it, translate it, or change it to "أعجبني", "تقدير", or any other word. The word "أقدّر" was chosen deliberately and is permanent.

2. **Use the idempotent `PUT` endpoint.** `PUT /company/posts/{post_id}/appreciation` with `{"appreciated": bool}` is the canonical endpoint. The legacy `POST /appreciate` toggle was deleted (PR-4) — do not re-add a toggle endpoint.

3. **`INSERT ... ON CONFLICT DO NOTHING` is mandatory.** The DB operation must be idempotent. Never use a simple `INSERT` that can throw a unique-constraint error on rapid clicks.

4. **Rate limiter: 10 requests per 10 seconds per (user, post) pair.** The `_check_appr_rate` function in `server.py` enforces this. Do not remove it or relax the limits without an explicit security review.

5. **Desired State Queue is mandatory (no-flicker architecture).** The three module-level variables in `company.posts.js` are the core of the fast-click safety:
   - `_apprDesired[postId]` — the user's last-intended state
   - `_apprInFlight[postId]` — `true` while a request is in flight
   - `_apprOrigState[postId]` — the known-good state before the first in-flight request
   Do not simplify this to a plain toggle. Do not remove any of the three variables.

6. **No-flicker rule: check desired BEFORE rendering server response.** In `_dispatchAppreciation`, always check `desired !== undefined && desired !== srvActive` BEFORE calling `_renderAppreciationButton`. If stale, update `_apprOrigState`, dispatch follow-up, and `return` without rendering. Only render when server state matches desired.

7. **Self-appreciation is forbidden server-side.** The endpoint checks `owner_id === user_id` and returns HTTP 403. Do not add client-side bypasses.

8. **`company_post_appreciations` is the only table for post appreciations.** Do not create a second table for the same purpose.

9. **`_renderAppreciationButton(btn, active, count)` is the only DOM update point** for appreciation state. Do not update `.appr-active` class or `data-appr-count` anywhere else in `company.posts.js`.
