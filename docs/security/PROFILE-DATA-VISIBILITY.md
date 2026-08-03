# Profile Data Visibility System V1

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
`viewer_type`, skills[], experience[], education[], courses[], links[], languages[], `verify_requests` (approved only — `status='approved'`)

### Tier 2 — Owner-Only (JWT required, `token.user_id == uid`)
Returned by `GET /profile/{user_id}/full` when caller owns the profile.

Includes all Tier 1 fields plus:  
`phone`, `dob`, `country_code`, `created_at`, `email` (from users), `avail` (writable form value)

### Tier 3 — KYC Owner (JWT required, `token.user_id == uid`)
Returned by `GET /kyc/status/{user_id}` when caller owns the KYC record.

Allowlist: `kyc_status`, `email_verified`, `phone_verified`, `docs_submitted`, `is_verified`, `created_at`, `updated_at`

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
| `GET /user/lookup/{tw_id}` | Optional | None (public tw_id lookup) | Limited fields only |

---

## Cross-User Lookup: `/user/lookup/{tw_id}`

For cases where one user needs basic info (name, avatar, tw_id) about another user (e.g. messaging), use this public lookup endpoint. It returns only: `tw_id`, `full_name`, `avatar_url`, `user_type`. It never returns `email`, `phone`, `dob`.

`/auth/user/{id}` is **owner-only** — it must not be called with another user's ID.

---

## Fail Closed Rule

When adding a new DB column:
1. Determine its tier (Public / Owner / KYC / Never).
2. If Public: add to `project_public_profile()` allowlist in `auth.py`.
3. If Owner: add to `project_owner_profile()` allowlist in `auth.py`.
4. If KYC: add to `project_owner_kyc_status()` allowlist in `auth.py`.
5. If Never or unsure: do NOT add it anywhere. It stays hidden by default.

The `{**user, **profile}` dict-merge pattern is **permanently forbidden** for any sensitive endpoint. Only explicit projection functions are allowed.

---

## Cache Boundary

`profile:{user_id}` in Redis/memory cache stores **owner-tier data**. The public code path (`GET /profile/{user_id}`) must NOT read from this cache key. Public responses are projected fresh from DB every time, or cached under a separate `public_profile:{user_id}` key.

---

## Response Projection Functions (auth.py)

- `project_public_profile(raw_dict) → dict` — strips to Tier 1 allowlist
- `project_owner_profile(raw_dict) → dict` — returns Tier 1 + Tier 2 fields
- `project_owner_kyc_status(raw_dict) → dict` — returns Tier 3 KYC allowlist only

---

## OTP Security

- `dev_code` must never appear in production API responses.
- Raw OTP values must not appear in production application logs.
- Dev visibility is controlled by `DEV_OTP_LOG` environment variable (default: disabled).
- `email_code` and `phone_code` columns must never appear in `GET /kyc/status` response.

---

## Version History

| Version | PR | Date | Description |
|---------|----|------|-------------|
| V1 | fix/profile-kyc-privacy-boundary | 2026-08-03 | Initial privacy boundary enforcement |
