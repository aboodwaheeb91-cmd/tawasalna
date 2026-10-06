# Shared Upload Client — رفع الصور

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Shared Upload Client Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`static/shared/tw-upload.js` is the only approved client for `POST /upload/image`.** Do NOT write a new `fetch('/upload/image', ...)` call in any page module, HTML file, or IIFE.

2. **`TW.uploadImage(opts)` is the single entry point.** Signature (PR-7a): `TW.uploadImage({ kind, dataUrl, jwt })`. Returns `Promise<{ ok: boolean, data: object }>`. All callers must handle the `{ok, data}` shape — never assume a direct `res.url`. On `!ok` show `TW.uploadErrorText(res, fallback)` in the page toast and stop — never save the data URL.

3. **Load order is mandatory.** `tw-upload.js` must appear in the HTML `<script>` list before any module that calls `TW.uploadImage`. Current pages: `profile-showcase.html` (before `profile-v2.api.js`) · `company-profile.html` (before `company.main.js`) · `settings.html` (KYC).

4. **Each page keeps its own UX.** File picking, validation, canvas crop, loading state, and saving the returned URL to the DB are each page's responsibility. `tw-upload.js` only does the HTTP upload — nothing else.

5. **Forbidden patterns:**
   ```
   ❌ fetch('/upload/image', ...) called directly from any page module
   ❌ A second upload helper function in a page file
   ❌ Storing base64 data_url as-is in the DB (the server never returns one in production — PR-7a)
   ❌ Bypassing TW.uploadImage for "simplicity" in a new page
   ❌ Sending bucket / filename / user_id from the client (server decides from `kind` + JWT)
   ❌ A new upload `kind` without adding it to `_UPLOAD_KINDS` in `server.py` + this file + SYSTEMS_INDEX §29a
   ```

6. **Server contract (PR-7a — upload security).** `server.py → _UPLOAD_KINDS` is the only kind → bucket map (`employee-avatar→avatars` · `employee-cover→covers` · `company-logo→avatars` · `company-cover→avatars` · `kyc-id-front→kyc-docs` · `kyc-selfie→kyc-docs`); unknown kind → 400. File name = `{user_id}_{kind}_{random}.{ext}` (JWT user_id only, no upsert). `_validate_image_data_url()`: JPEG/PNG/WebP only, magic bytes must match the declared mime, no SVG, data URL ≤ 7MB (413), decoded ≤ 5MB (413), bad base64 → 400. `_store_image()`: storage failure → 502, missing keys → 503, generic messages only (details in logs); data URL returned only when `TW_DEV_UPLOAD=1` and keys are missing. `POST /admin/logo` uses the same two helpers. Test: `python -m pytest test_upload_security.py -q`. Full spec: `ARCHITECTURE.md → Image Upload Security Contract (PR-7a — §29a)`.
