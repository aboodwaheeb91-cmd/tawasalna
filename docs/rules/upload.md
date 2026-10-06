# Shared Upload Client — رفع الصور

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Shared Upload Client Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`static/shared/tw-upload.js` is the only approved client for `POST /upload/image`.** Do NOT write a new `fetch('/upload/image', ...)` call in any page module, HTML file, or IIFE.

2. **`TW.uploadImage(opts)` is the single entry point.** Signature: `TW.uploadImage({ userId, bucket, filename, dataUrl, jwt })`. Returns `Promise<{ ok: boolean, data: object }>`. All callers must handle the `{ok, data}` shape — never assume a direct `res.url`.

3. **Load order is mandatory.** `tw-upload.js` must appear in the HTML `<script>` list before any module that calls `TW.uploadImage`. Current pages: `profile-showcase.html` (before `profile-v2.api.js`) · `company-profile.html` (before `company.main.js`).

4. **Each page keeps its own UX.** File picking, validation, canvas crop, loading state, and saving the returned URL to the DB are each page's responsibility. `tw-upload.js` only does the HTTP upload — nothing else.

5. **Forbidden patterns:**
   ```
   ❌ fetch('/upload/image', ...) called directly from any page module
   ❌ A second upload helper function in a page file
   ❌ Storing base64 data_url as-is in the DB (dev fallback only — do not make it the primary path)
   ❌ Bypassing TW.uploadImage for "simplicity" in a new page
   ```
