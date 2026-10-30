# Authentication & Identity — المصادقة والهوية

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Authentication System (`auth.py`)

### Password Handling
- Hashed with **bcrypt** (salted)
- Minimum 6 characters enforced
- `hash_password(plain)` / `verify_password(plain, hashed)`
- **One rule (PR 1.2):** `_password_policy_error(pw)` in `server.py` — used by `POST /auth/register`, `PUT /auth/password` and `PUT /admin/user/{id}/password` (task 5.0c — weak → 422, field `password`; the admin page has no own length check). ❌ a second length check. Signed-in change: `PUT /auth/password` (JWT + bcrypt check of the current password, new ≠ current, rate limited) — never verify a password by calling `/auth/login` from the client. → SYSTEMS_INDEX §1a.

### User ID Format (tw_id)
Every user gets a unique platform ID:
```
{PREFIX}{COUNTRY_CODE}{10_RANDOM_HEX_CHARS}

Examples:
  U9620ec95e9c5ca  →  Jordanian employee
  C9660a1b2c3d4e5  →  Saudi company
  T9710f0e1d2c3b4  →  UAE educational institution
```

Prefixes: `U` = Employee, `C` = Company, `T` = Training/Education  
Country codes: JO=9620, SA=9660, AE=9710, EG=2000, IQ=9640, SY=9630 …

### Session Management
Sessions are stored in **localStorage** (client-side only) as JSON:
```json
{
  "id": 42,
  "tw_id": "U9620...",
  "full_name": "أحمد",
  "email": "ahmed@example.com",
  "user_type": "emp",
  "country_code": "9620",
  "created_at": "2025-01-01T00:00:00"
}
```

### Session Version + Password Change (task 5.0b — SYSTEMS_INDEX §2a)
1. **`auth.set_user_password(uid, pw)` is the only writer of `password_hash`** — one statement (one transaction): new hash + `password_changed_at` + `users.session_version + 1` + **DELETE every row of the user in `password_reset_tokens` (all purposes: `email_change`, `password_reset`, any future one)**. Returns `{changed, sv}` (`None` = no such user). Covers all three paths: `PUT /auth/password` · `POST /auth/password-reset/confirm` · `PUT /admin/user/{id}/password`.
2. **User JWT claim `sv`** = `users.session_version` at issue: login (read with the password check — `session_version` is popped, never sent to the client) · register (`0`) · `PUT /auth/password` (the new `sv` from `set_user_password`). A token with `sv` is valid only while `sv == users.session_version` — no clock, so a token issued in the same second as the change dies too.
3. **Tokens without `sv` (issued before 5.0b, 2026-10-15)** kept the PR 1.8 check (`iat < password_changed_at` → rejected) while they could still be alive (7-day JWT). **From `server._NO_SV_REJECT_FROM` = 2026-10-23T00:00Z a token without `sv` → 401** (task 5.0f — the compatibility path is closed, no DB lookup).
3a. **Deleted account (task 5.0f):** `get_session_state` → `None` (no such user) → the token is rejected (401). Not cached — every request of a deleted account's token reads the DB; the delete paths (`DELETE /auth/user/{id}/delete` · `DELETE /admin/user/{id}`) drop the cache entry. A DB **error** on the lookup is a different case: logged + allowed (nobody is logged out by a DB blip).
3b. **Account type change (task 5.3b2):** `user_type` lives inside the JWT, so `auth.set_user_type(uid, type)` (the only writer of `user_type` after register — `PUT /admin/user/{id}/type`) bumps `session_version` in the same statement and returns `{changed, sv}`. Every admin path that bumps it ends the sessions through **`server._end_user_sessions(uid, state, reason)`** = `_password_changed_cache_set` + `_ws_revoke_user` (one place — admin password reset uses it too). Old token → 401; the next login carries the new type.
4. **One check, one cache:** `server._jwt_decode` → `_jwt_revoked_by_password_change` → `_session_state(uid)` (`auth.get_session_state` → `{changed, sv}` through `_pwd_changed_cache`, TTL 60s) · `_password_changed_cache_set(uid, state)` right after every write.
- ❌ writing `password_hash` outside `set_user_password` / `session_version` outside `set_user_password` + `set_user_type` · ❌ a password change that leaves emailed tokens alive · ❌ a second session-version cache or check · ❌ `sv` in an API response body · ❌ issuing a user JWT without `sv` · ❌ treating «no such user» like a DB error.
- Test: `python -m pytest tests/test_security_50f.py -q` (PostgreSQL — deleted account · no-`sv` cutoff).
- Test: `python -m pytest tests/test_session_version_tokens.py -q` (PostgreSQL) · type change: `python -m pytest tests/test_admin_user_actions.py -q`.

### User Login Lock under Concurrency (task 8.4c-0b — SYSTEMS_INDEX §54n)
1. **`POST /auth/login` reserves the three locks (`login_email` · `login_ip` · `login_ip_email`) BEFORE bcrypt** — `_login_reserve(email, ip)` = `_rate_reserve_window` (the one check-and-count, `_rate_reserve` of task 8.4c-0, under `_rate_lock`): one lock full → the same 429 `login_locked` (`limits.login_locked`, minutes from that lock's window), nothing counted. Wrong password → the reservation stays (that is the failure count). Success → `_rate_release(held)` then `_login_email_reset(email, ip)` as before. 30 parallel wrong passwords → 401s ≤ the smallest lock, the rest 429.
- ❌ a check then a separate count (the old `_login_locked` + `_login_fail` — deleted) · ❌ a second lock implementation.
- Test: `python -m pytest tests/test_security_84c0b.py -q`.

### Email Links + OTP Shape + HSTS (task 8.4c-0b)
1. **`auth.email_token_issue`** runs `BEGIN` → `pg_advisory_xact_lock(hashtextextended('tw_email_token:' || user_id, 0))` → the DELETE + INSERT → `COMMIT`: parallel issues for one user wait for each other → one valid link per (user, purpose), and one for both email change purposes together.
2. **OTP shape — `auth.otp_code_valid(code)`** (the one check): exactly `auth.OTP_LENGTH` (6 — `generate_code` uses it) ASCII digits after `strip`. `KYCCodeInput.code` (field validator) → 422 in the form error shape (`{error, details:[{loc:["body","code"], type}]}`) · `POST /support/guest/tickets` → 422 `invalid_code` · `_otp_verify` / `guest_otp_verify` / `support.guest_verify` return «wrong» before the attempt UPDATE — a wrong shape never uses an attempt.
3. **`Strict-Transport-Security: max-age=31536000; includeSubDomains`** on every response (the `security_headers` middleware, next to `nosniff`). ❌ `preload` · CSP is a separate task.
- Test: `python -m pytest tests/test_security_84c0b.py -q`.

### Login Lock after Password Reset (task 7.5b — SYSTEMS_INDEX §54n)
1. **A successful `POST /auth/password-reset/confirm`** (after `set_user_password` changed the password) calls `_login_email_reset(email, every_ip=True)`: clears `login_email:{email}` **and every `login_ip_email:{ip}|{email}` key of that email from any IP** (`_rate_store` section `login_ip_email`, under `_rate_lock`). The owner proved the inbox, so the locks on that address end.
2. `login_ip` (per IP, any email) and every general rate stay as they are. A failed / invalid reset clears nothing. A successful login still clears only its own email + its own IP pair.
- ❌ clearing `login_ip` on a reset · ❌ unlocking before the password is really changed.
- Test: `python -m pytest tests/test_password_reset_email.py -q` (old password refused, new works · pair lock from another IP cleared · IP lock kept).

### Organisation Account Gate (task 5.0f — SYSTEMS_INDEX §54l)
1. **Every company action checks the account type as it is NOW** — `server._require_org_account(token, allowed=("co","edu"), message)` reads `users.user_type` through `auth.get_current_user_type(uid)` (no user → 401 · other type → 403). The JWT `user_type` claim and job / post ownership alone are never enough.
2. Callers: `GET /jobs/{id}/applicants` · `PUT /jobs/applications/{id}/status` · `POST /jobs/applications/{id}/promote` · `POST/PATCH/DELETE /company/posts…` (co / edu) · Talent Bank `/company/saved-candidates*` + `/company/candidate-suggestions` via `_require_company_owner` (co) · appointments `POST /api/appointments` · `/api/schedule/jobs|open|people` · `/api/appointments/{id}/send|reschedule|complete|close` (co).
- ❌ `token.get("user_type")` as the gate of a company action · ❌ a per-endpoint type query. Test: `python -m pytest tests/test_security_50f.py -q`.

### Verified Badge — one source (task 5.0c — SYSTEMS_INDEX §23)
1. **`profiles.is_verified` is the public «موثّق» badge** (public profile · job company badge · completion · admin). **`auth.set_user_verified(user_id, verified, conn)` is its only writer** — KYC approve (TRUE) · KYC reject (FALSE) · `PUT /admin/user/{id}/verify` `{is_verified: true|false}` (required boolean → else 422).
2. **`users.is_verified` is legacy** — no writer, no reader (column kept). `company_profiles.verified_co` has no writer (F30 — open).
3. **KYC review:** approve / reject only a submission at `step='review'` + `status='pending'` → `step = status = approved | rejected`; otherwise 409. `POST /kyc/docs` only after email + phone are verified (`step ∈ {id_upload, rejected}`) → otherwise 409. **Reject reason (task 8.1):** `PUT /admin/kyc/{id}/reject` needs `reason` (shown to the user — trimmed, ≤ `kyc_reject_reason_max`, blank → 422 field `reason`) + optional internal `note`; stored in `kyc_submissions.reject_reason` (approve / new documents → `NULL`, same transaction); `GET /kyc/status` returns it only while `status = rejected`, never `admin_note`. Result notification `kyc_approved` / `kyc_rejected` → `/settings` after the COMMIT (non-fatal) + email without the reason — SYSTEMS_INDEX §23.
4. **Startup carry-over `verified_source` runs ONCE** (task 5.0f — `app_migrations` mark via `_migration_claim_once`) and never overwrites an existing `profiles` row → a badge the admin withdrew stays withdrawn across restarts.
- ❌ an UPDATE of `profiles.is_verified` / `users.is_verified` anywhere else · ❌ approving without a submission in review · ❌ a default `True` on the verify endpoint · ❌ a badge migration that re-runs on every boot.
- Test: `python -m pytest tests/test_entity_map_fixes_50c.py -q` (PostgreSQL).

### Admin Authentication
- All secrets are environment variables — no hardcoded values in source
- `ADMIN_TOKEN` (Railway Variable): random 32+ byte hex — the admin **login password only** (PR 1.5)
- `ADMIN_JWT_SECRET` (Railway Variable): random 32+ byte hex, different from `JWT_SECRET` and `ADMIN_TOKEN` — signs admin session JWTs. Missing → admin login + admin endpoints return 503 (never falls back to `JWT_SECRET`)
- `POST <panel>/login` (`/tw-ctrl-{ADMIN_URL_TOKEN}/login`; the old `/tw-ctrl-login` deleted in 5.3b) — two steps since task 8.4b: password (owner) / email + password (staff) → a 5-minute ticket; ticket + authenticator / recovery code → an admin JWT (owner `role=admin`, `sub=owner`, `perms=["*"]` · staff `role=staff`, `sub=staff:<id>` · both with `sv`, 1h) — never the raw `ADMIN_TOKEN`. Rules + owner recovery: `docs/rules/admin-staff.md`
- All admin API endpoints require the header: `X-Admin-Token: <admin JWT>`; `check_admin` accepts ONLY that JWT (raw `ADMIN_TOKEN` / user JWT / expired → 401)
- Admin pages hold the token only via `static/shared/admin-session.js` (`TwAdminSession`); 401/403 or expiry → login screen with a clear message
- Admin panel URL: `/tw-ctrl-{ADMIN_URL_TOKEN}` — ADMIN_URL_TOKEN is an environment variable
- Spec: `ARCHITECTURE.md §57 → Token Authentication` · SYSTEMS_INDEX §25
