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

6. **Server contract (PR-7a — upload security).** `server.py → _UPLOAD_KINDS` is the only kind → bucket map (`employee-avatar→avatars` · `employee-cover→avatars` · `company-logo→avatars` · `company-cover→avatars` · `kyc-id-front→kyc-docs` · `kyc-selfie→kyc-docs`); unknown kind → 400. `kyc-docs` is **private** (`_PRIVATE_BUCKETS`): the response is `{status, path}` with `path = kyc-docs/{name}` — never a `/object/public/` URL; admin viewing via signed URL is a separate PR (`docs/FUTURE_ROADMAP.md` P0). File name = `{user_id}_{kind}_{random}.{ext}` (JWT user_id only, no upsert). `_validate_image_data_url()`: JPEG/PNG/WebP only, magic bytes must match the declared mime, no SVG, data URL ≤ 7MB (413), decoded ≤ 5MB (413), bad base64 → 400. `_store_image()`: storage failure → 502, missing keys → 503, generic messages only (details in logs); data URL returned only when `TW_DEV_UPLOAD=1` and keys are missing. `POST /admin/logo` uses the same two helpers.

7. **Saving an image URL (PR-7a).** Every endpoint that stores an image URL calls `_validate_stored_image_url(url, kind, uid, current)` in `server.py` — currently `PUT /profile/{id}` (`avatar_url`: `employee-avatar`, or `company-logo` for a `co` account · `cover_url`: `employee-cover`), `PUT /company/profile/{id}` + `PUT /company/cover/{id}` (`company-cover`), `POST /kyc/docs` (`kyc-id-front` / `kyc-selfie`). Allowed: `null`/`""` (clear) · the currently stored value unchanged (legacy) · exactly `{SUPABASE_URL}/storage/v1/object/public/{bucket of kind}/{uid}_{kind}_{12 hex}.{jpg|png|webp}` — for KYC (private) exactly `kyc-docs/{uid}_{kind}_{12 hex}.{jpg|png|webp}` instead. `data:` only with `TW_DEV_UPLOAD=1`. Anything else → 400. ❌ A new image-URL field or endpoint without this gate.

8. **Error classes (fix/upload-error-classes).** `TW.uploadImage` never rejects: it resolves `{ ok, status, data, errorType }` (`errorType`: `null` · `network` · `non_json` · `server`); `TW.uploadResult(r)` classifies the save-URL response the same way. Every image flow (avatar · cover · company logo/cover · KYC) throws `TW.uploadError(res, fallback, stage)` for a failed upload **and** a failed save step, and its catch shows `TW.uploadFailureMessage(e, fallback)` — session expired (401 / client guard `session_invalid`) · network · server text · `fallback (رمز {status})` for a non-JSON reply. `console.error` logs kind / status / errorType / payloadBytes only. Server: `SUPABASE_URL` is read only via `_supabase_base_url()` (trimmed, no trailing `/`) so the stored URL always passes `_validate_stored_image_url`.
   ```
   ❌ One generic toast for every failure in an image flow
   ❌ Dropping the server error of the save step (PUT /profile …)
   ❌ Logging the data URL
   ❌ Reading os.environ["SUPABASE_URL"] for storage outside _supabase_base_url()
   ```

Test: `python -m pytest test_upload_security.py -q` · `node test_upload_client_runtime.js`. Full spec: `ARCHITECTURE.md → Image Upload Security Contract (PR-7a — §29a)`.
