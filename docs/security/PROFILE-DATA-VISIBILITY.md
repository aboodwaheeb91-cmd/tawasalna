# Profile Data Visibility System V1.2

**Status:** Active — enforced server-side since PR fix/profile-kyc-privacy-boundary  
**Principle:** Fail Closed — every new DB column is Private by default until explicitly added to a tier allowlist.

---

## Field Visibility Tiers

### Tier 1 — Public (no auth required)
Returned by `GET /profile/{user_id}` to any caller including unauthenticated requests.

**`users` table:**  
`id`, `tw_id`, `full_name`, `user_type`, `is_verified`

**`profiles` table:**  
`headline`, `bio`, `location`, `country`, `city`, `avatar_url`, `cover_url`, `avail`, `website`

**Derived / computed:**  
`viewer_type`, skills[], experience[], education[], courses[], links[], languages[], `following_count`, `age`

> `age` is an integer derived from `dob` inside the backend projection boundary.  
> The source field `dob` is **never** copied into the public response — only the derived `age` is exposed.  
> Returns `null`/absent when `dob` is missing, invalid, future, pre-1940, or results in age < 15.  
> **Projection rule:** Derived public fields may be computed from private source fields only inside the Backend projection boundary (`project_public_profile()` / `project_owner_profile()`). The private source field must never be copied into the public response.

### Tier 2 — Owner-Only (JWT required, `token.user_id == uid`)
Returned by `GET /profile/{user_id}/full` when caller owns the profile.

Includes all Tier 1 fields plus:  
`phone`, `dob`, `country_code`, `created_at`, `email` (from users), `avail` (writable form value)

### Tier 3 — KYC Owner (JWT required, `token.user_id == uid`)
Returned by `GET /kyc/status/{user_id}` when caller owns the KYC record.

Allowlist: `step`, `status`, `email_verified`, `phone_verified`, `is_verified`, `submitted_at`, `reviewed_at`

**Never returned:** `email_code`, `phone_code`, `otp_*` columns, any raw OTP value

### Tier 4 — Never Returned via API
`password_hash`, `email_code`, `phone_code`, any raw OTP, internal tokens, admin flags

---

## Endpoint Ownership Contract

| Endpoint | Auth | Ownership Check | Notes |
|----------|------|----------------|-------|
| `GET /profile/{id}` | Optional JWT | `viewer_type` set if JWT present | Public fields only |
| `GET /profile/{id}/full` | **Required JWT** | `token.user_id == uid` → 403 | Owner fields |
| `GET /auth/user/{id}` | **Required JWT** | `token.user_id == uid` → 403 | Owner refresh only |
| `GET /kyc/status/{id}` | **Required JWT** | `token.user_id == uid` → 403 | KYC allowlist only |
| `POST /kyc/start` | **Required JWT** | `uid = token.user_id` | No body user_id |
| `POST /kyc/email/send` | **Required JWT** | `uid = token.user_id` | No body user_id |
| `POST /kyc/email/verify` | **Required JWT** | `uid = token.user_id` | No body user_id |
| `POST /kyc/phone/send` | **Required JWT** | `uid = token.user_id` | No body user_id |
| `POST /kyc/phone/verify` | **Required JWT** | `uid = token.user_id` | No body user_id |
| `POST /kyc/docs` | **Required JWT** | `uid = token.user_id` | No body user_id |
| `GET /user/lookup/{tw_id}` | **Required JWT** | None (caller must be authenticated) | `id`, `tw_id`, `full_name`, `user_type` only |

---

## Cross-User Lookup: `/user/lookup/{tw_id}`

For cases where one authenticated user needs basic info about another user (e.g. opening a message thread), use this endpoint. **JWT is required.** It returns only: `id`, `tw_id`, `full_name`, `user_type`. It never returns `email`, `phone`, `dob`, or `avatar_url`.

`/auth/user/{id}` is **owner-only** — it must not be called with another user's ID.

---

## Fail Closed Rule

When adding a new DB column:
1. Determine its tier (Public / Owner / KYC / Never).
2. If Public: add to `project_public_profile()` allowlist in `auth.py`.
3. If Owner: add to `project_owner_profile()` allowlist in `auth.py`.
4. If KYC: add to `project_owner_kyc_status()` allowlist in `auth.py`.
5. If Never or unsure: do NOT add it anywhere. It stays hidden by default.

The `{**user, **profile}` dict-merge pattern is **permanently forbidden** for all endpoints that return user data to external callers. Passing the raw merged dict directly as a response leaks all DB columns including those that should never be public. Only `project_public_profile()`, `project_owner_profile()`, or `project_owner_kyc_status()` may be used to shape responses. The dict-merge `{**user, **profile, **extras}` is still used internally (inside `get_full_profile()`, `get_public_profile()`) as input to these projection functions — that is correct and intentional. What is forbidden is bypassing the projection step and returning the raw merged dict directly.

---

## Cache Boundary

`profile:{user_id}` in Redis/memory cache stores **owner-tier data**. The public code path (`GET /profile/{user_id}`) must NOT read from this cache key. Public responses are projected fresh from DB every time, or cached under a separate `public_profile:{user_id}` key.

---

## Response Projection Functions (auth.py)

- `project_public_profile(raw_dict) → dict` — strips to Tier 1 allowlist; derives `age` from `raw_dict["dob"]` internally (dob never copied to result)
- `project_owner_profile(raw_dict) → dict` — returns Tier 1 + Tier 2 fields; also adds derived `age` for UI convenience
- `project_owner_kyc_status(raw_dict) → dict` — returns Tier 3 KYC allowlist only
- `calculate_age_from_dob(dob) → int | None` — calendar-accurate age derivation helper; returns None for missing/invalid/future/pre-1940/under-15 values

---

## OTP Security

- `dev_code` must never appear in production API responses.
- Raw OTP codes must never appear in any log, response, or error message — not even under `DEV_OTP_LOG`.
- `DEV_OTP_LOG` environment variable enables event-only logging (e.g. "KYC Email triggered for uid=5") — it logs the event, never the code value itself.
- `email_code` and `phone_code` columns must never appear in `GET /kyc/status` response.

---

## OTP Delivery Fail-Closed Contract

**Generating an OTP code ≠ Delivering it.** `send_email_code()` and `send_phone_code()` in `auth.py` only store the code in DB. Without a real delivery provider, the user has no way to receive the code.

### When no provider is configured (current state):

`POST /kyc/email/send` and `POST /kyc/phone/send` return:

```
HTTP 503 Service Unavailable
{
  "detail": {
    "code": "otp_delivery_unavailable",
    "message": "خدمة إرسال رمز التحقق غير متاحة حالياً"
  }
}
```

**Behavior contract:**
- No OTP is generated.
- No OTP is stored in DB.
- KYC state is not mutated.
- `status=success` is never returned.
- `send_email_code()` / `send_phone_code()` are never called.
- The user sees a clear message in the UI (settings.html).

### Availability gates:

`is_email_otp_delivery_available()` and `is_phone_otp_delivery_available()` in `server.py` return `False` by default. These must return `True` **only when** a real provider is integrated, tested, and configured with production credentials. `DEV_OTP_LOG` does NOT make a provider available.

### Test / Mock contract:

When tests need a success path:
- Patch `server.is_email_otp_delivery_available` / `server.is_phone_otp_delivery_available` to return `True` in the test only.
- Patch `auth.send_email_code` / `auth.send_phone_code` to capture the call without hitting the DB.
- The OTP code must not appear in any HTTP response.
- Tests capture the code internally from the Mock only.
- Mock must never be activated outside the test scope.

### Frontend (settings.html):

On 503 with `code=otp_delivery_unavailable`:
- Show: `خدمة إرسال رمز التحقق غير متاحة حالياً، وسيتم توفيرها قريباً.`
- Stop loading state.
- Do NOT show the code input field.
- Do NOT show a success toast.
- Do NOT advance to the next step.

On 401: show session-expired message.
On other errors: show safe generic message from `detail.message` if present.

---

## Version History

| Version | PR | Date | Description |
|---------|----|------|-------------|
| V1 | fix/profile-kyc-privacy-boundary | 2026-08-03 | Initial privacy boundary enforcement |
| V1.1 | fix/profile-kyc-privacy-boundary | 2026-08-03 | OTP Delivery Fail-Closed contract; `is_*_otp_delivery_available()` helpers; 503 on send endpoints; settings.html 503 handling; owner hydration toast feedback |
| V1.2 | fix/profile-public-derived-age | 2026-08-03 | Restore public derived `age` field; `calculate_age_from_dob()` helper; projection functions compute age at boundary; frontend uses `p.age` never `p.dob` |
