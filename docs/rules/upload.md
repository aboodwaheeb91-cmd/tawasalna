# Shared Upload Client — رفع الصور

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Shared Upload Client Rules (mandatory for all AI sessions)

These rules are permanent and apply to all future AI sessions.

1. **`static/shared/tw-upload.js` is the only approved client for `POST /upload/image`.** Do NOT write a new `fetch('/upload/image', ...)` call in any page module, HTML file, or IIFE.

2. **`TW.uploadImage(opts)` is the single entry point.** Signature (PR-7a): `TW.uploadImage({ kind, dataUrl, jwt })`. Returns `Promise<{ ok: boolean, data: object }>`. All callers must handle the `{ok, data}` shape — never assume a direct `res.url`. On `!ok` show `TW.uploadErrorText(res, fallback)` in the page toast and stop — never save the data URL.

3. **Load order is mandatory.** `tw-upload.js` must appear in the HTML `<script>` list before any module that calls `TW.uploadImage`. Current pages: `profile-showcase.html` (before `profile-v2.api.js`) · `company-profile.html` (before `company.main.js`) · `settings.html` (KYC — before `static/settings/settings.js`).

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

6. **Server contract (PR-7a — upload security).** `server.py → _UPLOAD_KINDS` is the only kind → bucket map (`employee-avatar→avatars` · `employee-cover→avatars` · `company-logo→avatars` · `company-cover→avatars` · `kyc-id-front→kyc-docs` · `kyc-selfie→kyc-docs`); unknown kind → 400. `kyc-docs` is **private** (`_PRIVATE_BUCKETS`): the response is `{status, path}` with `path = kyc-docs/{name}` — never a `/object/public/` URL; admin viewing via signed URL → rule 9. File name = `{user_id}_{kind}_{random}.{ext}` (JWT user_id only, no upsert). `_validate_image_data_url()`: JPEG/PNG/WebP only, magic bytes must match the declared mime, no SVG, data URL ≤ 7MB (413), decoded ≤ 5MB (413), bad base64 → 400. `_store_image()`: storage failure → 502, missing keys → 503, generic messages only (details in logs); data URL returned only when `TW_DEV_UPLOAD=1` and keys are missing. `POST /admin/logo` uses the same two helpers.

7. **Saving an image URL (PR-7a).** Every endpoint that stores an image URL calls `_validate_stored_image_url(url, kind, uid, current)` in `server.py` — currently `PUT /profile/{id}` (`avatar_url`: `employee-avatar`, or `company-logo` for a `co` account · `cover_url`: `employee-cover`), `PUT /company/profile/{id}` + `PUT /company/cover/{id}` (`company-cover`), `POST /kyc/docs` (`kyc-id-front` / `kyc-selfie`). Allowed: `null`/`""` (clear) · the currently stored value unchanged (legacy) · exactly `{SUPABASE_URL}/storage/v1/object/public/{bucket of kind}/{uid}_{kind}_{12 hex}.{jpg|png|webp}` — for KYC (private) exactly `kyc-docs/{uid}_{kind}_{12 hex}.{jpg|png|webp}` instead. `data:` only with `TW_DEV_UPLOAD=1`. Anything else → 400. ❌ A new image-URL field or endpoint without this gate.

8. **Error classes (fix/upload-error-classes).** `TW.uploadImage` never rejects: it resolves `{ ok, status, data, errorType }` (`errorType`: `null` · `network` · `non_json` · `server`); `TW.uploadResult(r)` classifies the save-URL response the same way. Every image flow (avatar · cover · company logo/cover · KYC) throws `TW.uploadError(res, fallback, stage)` for a failed upload **and** a failed save step, and its catch shows `TW.uploadFailureMessage(e, fallback)` — session expired (401 / client guard `session_invalid`) · network · server text · `fallback (رمز {status})` for a non-JSON reply. `console.error` logs kind / status / errorType / payloadBytes only. Server: `SUPABASE_URL` is read only via `_supabase_base_url()` (trimmed, no trailing `/`) so the stored URL always passes `_validate_stored_image_url`.
   ```
   ❌ One generic toast for every failure in an image flow
   ❌ Dropping the server error of the save step (PUT /profile …)
   ❌ Logging the data URL
   ❌ Reading os.environ["SUPABASE_URL"] for storage outside _supabase_base_url()
   ```
   **Supabase settings (fix/supabase-settings-key-migration):** `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` are read only via `_supabase_url_status()` / `_supabase_base_url()` and `_supabase_key_status()` / `_supabase_service_key()` — cleaned of whitespace, Unicode Cf (bidi U+200E/F · U+202A–E · U+2066–9 · BOM U+FEFF · zero-width) and surrounding quotes. URL must be exactly `https://<project>.supabase.co` (custom domains are **not** accepted — decision: one canonical host avoids a pasted wrong domain silently passing; add a documented allowlist if a custom domain is ever adopted). Key: `sb_secret_…` (new) or a legacy `service_role` JWT (payload decoded only, no signature check); anon JWT → "anon key, not service_role", `sb_publishable_…` / anything else → not configured (= 503, same as missing). Storage auth headers come only from `_supabase_auth_headers()`: `sb_secret_` → `{apikey}` only (not a JWT — never Bearer) · legacy JWT → `{apikey, Authorization: Bearer}`. Used by `_store_image` (uploads, `POST /admin/logo`, PR-7c migration) and `_sign_kyc_doc`. Startup logs one line `Supabase storage: OK (key type: legacy JWT | secret)` or `NOT CONFIGURED — <reason>` + a deprecation warning for legacy keys — never the key, any part of it, or the URL. Test: `test_supabase_settings.py`.
   ```
   ❌ Reading SUPABASE_SERVICE_KEY outside _supabase_key_status() · a hand-written "Authorization": f"Bearer {key}" for Supabase
   ❌ Sending an sb_secret_ key as Authorization: Bearer (it is not a JWT)
   ❌ Logging the key (or any part of it) or a raw/invalid SUPABASE_URL — reasons only
   ```

9. **KYC admin viewing (PR-7c).** `GET /admin/kyc/{submission_id}/docs` (`check_admin`) is the only admin way to view KYC documents (the owner's own download — `POST /me/export/kyc-docs`, task 8.5b — signs the caller's own paths through the same `_kyc_doc_path_reason` + `_sign_kyc_doc`, TTL `LIMITS["data_export_kyc_url_ttl_s"]` — `docs/rules/data-export.md`): short-lived (300s) signed URL from `POST {_supabase_base_url()}/storage/v1/object/sign/kyc-docs/{name}`, only for a path exactly `kyc-docs/{user_id of the submission}_{kind}_{12 hex}.{ext}`; anything else → `url: null` + `reason`. `Cache-Control: no-store`. `GET /admin/kyc` returns the explicit allowlist `auth._ADMIN_KYC_LIST_COLUMNS` only — never `email_code` / `phone_code` / `id_front_url` / `selfie_url` (no `SELECT ks.*`). `admin.html` checks the URL starts with `{storage_base}/storage/v1/object/sign/kyc-docs/` before `src`.
   ```
   ❌ Logging a signed URL / token
   ❌ A public URL or a list endpoint exposing kyc-docs paths
   ❌ Signing a path of another user
   ```

10. **Legacy `data:` migration (PR-7c).** `POST /admin/maintenance/migrate-data-images?dry_run=1` (`check_admin`, dry run by default) — every `data:` value in `profiles.avatar_url` (`co` → `company-logo`, else `employee-avatar`) · `profiles.cover_url` (`employee-cover`) · `company_profiles.cover_url` (`company-cover`) · `kyc_submissions.id_front_url` / `selfie_url` · `site_settings` `logo_wide` / `logo_tall` goes through `_validate_image_data_url` → `_store_image` → `UPDATE … WHERE col = <old value> RETURNING 1` (never overwrite a newer value). Invalid values are left and reported, never deleted. Idempotent. Response = counts + reasons only.

11. **Storage delete (task 8.5c).** `server.storage_delete(bucket, name)` is the ONLY delete of a storage object — sync, `DELETE {_supabase_base_url()}/storage/v1/object/{bucket}/{name}` with `_supabase_auth_headers()` → `{ok, status, reason}`: 200 / 204 = deleted · **404 (or the older 400 + `{"statusCode": "404"}`) = already gone = success** · anything else / network / not configured = failure, logged as bucket + status only. Its companion `server.storage_list(bucket, prefix)` (`POST …/object/list/{bucket}`, paged, names filtered by `startswith(prefix)`) → list | `None` on failure. Both are registered into `account_purge.set_storage` — the final account purge (`docs/rules/account-deletion.md` «الحذف النهائي») deletes only names `{uid}_{kind}_{12 hex}.{ext}` of the purged account. The other callers: `POST /admin/logo` deletes the object it just stored when the `site_settings` save fails (orphan, task 8.11a) — see rule 12 · the certificate endpoints delete the replaced / orphaned `cert-docs` object (task 8.7) — see rule 13.
    ```
    ❌ A second storage delete / list (httpx call to /storage/v1/object outside these two + _store_image + _sign_kyc_doc)
    ❌ Treating 404 as a failure (a retry would never finish)
    ❌ Logging the object name with the key, a signed URL or the response body
    ```

12. **Admin logo save (task 8.11a).** `POST /admin/logo`: `_store_image` → `set_site_setting` (DB first; returns False or raises = failure) → only then `_html_cache[slot] = url` + `{"status":"success"}`. Save failure → `_server_error("upload_logo", e)` 500, `_html_cache` untouched, the stored `site/{slot}_{hex}{ext}` deleted via `server.storage_delete` (dev data URL = nothing to delete); a failed delete is logged with slot + reason only (never the name) and the answer stays 500. `ensure_site_settings_table` stays on the path until a startup migration creates `site_settings`. Admin page (`static/admin/admin.js`): success toast only on `res.ok` (`TwAdminShell.run`); a failed upload puts the saved logo back in the preview.
    ```
    ❌ Caching / answering success before the DB save · ❌ swallowing a set_site_setting failure
    ```
13. **Certificate PDFs (task 8.7 — `docs/rules/certificates.md`).** Private bucket `cert-docs` (in `_PRIVATE_BUCKETS`; production SQL `docs/migrations/8.7_certificates.sql`) — not an `_UPLOAD_KINDS` kind and not `POST /upload/image` / `TW.uploadImage`: its own endpoints `POST` / `DELETE /course|education/{id}/certificate` (`{data_url}`, check = `cert_access.validate_pdf` — magic `%PDF-` + size + no encryption / scripts; the declared type decides nothing) · name `{uid}_cert_{12hex}.pdf` from the server · stored through the same `_store_image` (result must be `cert-docs/{name}` — the dev data-URL fallback → 503, never kept) · DB first, then the old object via `server.storage_delete` (a third caller next to the purge and the logo rollback) · signed view links through the same **`_sign_kyc_doc(name, ttl, bucket="cert-docs")`** (one signing function for both private buckets).
    ```
    ❌ A certificate through POST /upload/image · ❌ a second signing function · ❌ a public URL for cert-docs
    ```
Test: `python -m pytest tests/test_upload_security.py -q` · `python -m pytest tests/test_certificates_87.py -q` (certificates) · `python -m pytest tests/test_account_purge_85c.py -q` (storage delete) · `python -m pytest tests/test_logo_upload_save_811a.py -q` (logo save) · `node tests/test_upload_client_runtime.js` · `python -m pytest tests/test_kyc_docs_migration.py -q`. Full spec: `ARCHITECTURE.md → Image Upload Security Contract (PR-7a — §29a)`.
