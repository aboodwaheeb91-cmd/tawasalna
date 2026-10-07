# Authentication & Identity — المصادقة والهوية

> منقول حرفياً من `CLAUDE.md` (PR-3b — تقصير CLAUDE.md) بدون حذف أو تعديل في نص القواعد. القواعد هنا **إلزامية** بنفس قوة `CLAUDE.md` لأي مهمة تلمس هذا النظام.
> أي إشارة داخل النص بصيغة `CLAUDE.md → <اسم قسم>` تشير إلى القسم المنقول — مكانه في جدول **"قوانين الأنظمة"** بآخر `CLAUDE.md`.

## Authentication System (`auth.py`)

### Password Handling
- Hashed with **bcrypt** (salted)
- Minimum 6 characters enforced
- `hash_password(plain)` / `verify_password(plain, hashed)`
- **One rule (PR 1.2):** `_password_policy_error(pw)` in `server.py` — used by `POST /auth/register` and `PUT /auth/password`. ❌ a second length check. Signed-in change: `PUT /auth/password` (JWT + bcrypt check of the current password, new ≠ current, rate limited) — never verify a password by calling `/auth/login` from the client. → SYSTEMS_INDEX §1a.

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

### Admin Authentication
- All secrets are environment variables — no hardcoded values in source
- `ADMIN_TOKEN` (Railway Variable): random 32+ byte hex used as both login password and API header value
- All admin API endpoints require the header: `X-Admin-Token: <ADMIN_TOKEN>`
- Admin panel URL: `/tw-ctrl-{ADMIN_URL_TOKEN}` — ADMIN_URL_TOKEN is an environment variable
